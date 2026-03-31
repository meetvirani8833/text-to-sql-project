from langchain_core.prompts import ChatPromptTemplate

EXTRACT_CANDIDATE_PHRASES_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a simple named-entity phrase extractor.
Your ONLY job is to extract all named values, proper nouns, abbreviations, and informal references from the user's question.

RULES:
- Extract obvious names, acronyms, and codes (e.g., "Gold Collection", "NCR", "Arjun Sharma").
- Extract informal references or longer descriptive names (e.g., "north central area", "platinum customers").
- DO NOT extract structural words alone (e.g., "list", "show", "how many", "revenue", "orders").
- DO NOT apply any domain rules or database logic. Just extract anything that looks like a name or reference.

Return ONLY a JSON list of strings (e.g., ["Gold Collection", "NCR"]). Return [] if nothing found."""),
    ("human", "{question}")
])

# 1. Detect Entities (Context-Aware)
# This prompt now receives column/schema context from the pruning stage,
# allowing it to distinguish between FILTERS (column values, boolean flags)
# and true ENTITIES (needing KB resolution).
DETECT_ENTITIES_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an entity detection expert for a text-to-sql system.
Your job is to identify ONLY the mentions in the user's question that refer to **text-valued filters** (named text values) which require resolution against a knowledge base.

## Runtime Context (populated at runtime)
### Available Text Filter Types (from Knowledge Base)
{entity_types_text}
### Available Database Columns (from the selected tables)
{column_context_text}
### KB Similarity Hints (for reference, DO NOT solely rely on this)
These are raw similarity search results from the KB based on the user's question. Use them to understand what values exist, but DO NOT extract them blindly unless they match the text in the user's question according to the extraction rules below.
{kb_hints_text}

## DEFINITIONS
- **BOOLEAN/STATUS/NUMERIC FILTERS:** Mentions that map to status codes, boolean flags, or numeric/year values in the schema (e.g., "active records", "cancelled orders", "fiscal year 2024", "delivered items"). **Do not extract these.**
- **TEXT FILTERS:** Named text values (possibly abbreviated or informal) that map to entity type columns listed in the `Available Text Filter Types` section above. **Always extract these when present.**

## STRICT DECISION PROCESS (must be followed in this order)
0. **Type-word noun-phrase check (highest priority).** Look at the entity type names listed in `Available Text Filter Types`. Derive the relevant type-words from those names (e.g., if `region_name` is a type, "region" is a type-word; if `category_name` is a type, "category" is a type-word). If a phrase in the question contains a type-word immediately adjacent to a named value (immediately before OR immediately after, ignoring punctuation), treat it as a TEXT FILTER. **Extract only the named value** (see Extraction rules below).
1. If the mention unambiguously matches a boolean/status/numeric filter → SKIP (do not extract).
2. Else if the mention contains a named text value that maps to any type listed in `Available Text Filter Types` → EXTRACT it as a TEXT FILTER.
3. If uncertain and the token looks like a proper noun / named value → PREFER extraction and list all plausible candidate types (but only those present in `Available Text Filter Types`).

## EXTRACTION RULES (deterministic)
- **If phrase contains a type-word (see step 0):** remove the type-word and extract the remaining contiguous named-value substring. Return that substring **exactly as it appears** in the question (preserve characters, spacing, case).
- **If the user gives a single-word or short token** that plausibly maps to multiple types, extract the token and list **all candidate types** from `Available Text Filter Types` that are reasonable.
- **Do not canonicalize or normalize** (do not expand abbreviations or correct spelling). Return the span exactly as found (except removal of the type-word as above).
- **Do not extract structural nouns alone** (e.g., "customers", "products", "orders") unless they are part of a phrase with an adjacent named value (step 0).
- **Ambiguity note:** If the KB similarity hints show that a mention matches values in multiple different entity type columns, list all those types as candidate types so disambiguation can fire.

## CANDIDATE TYPES
- Candidate types listed for each mention MUST be chosen only from the items provided in `Available Text Filter Types` (do not invent types).

## OUTPUT FORMAT (strict JSON only)
Return **ONLY** a JSON array of objects, exactly in this shape (double quotes required):

[
  {{
    "text": "<extracted_text>",
    "candidate_types": ["type1", "type2"]
  }},
  ...
]

Return `[]` if there are no text filters to resolve. Do not output any other text, explanation, or markup.

## REQUIRED EXAMPLES (illustrative — actual entity types come from Available Text Filter Types above)
1) Input: `Show total revenue for the Gold Collection category in 2024`
   (Assuming `category_name` is in Available Text Filter Types)
Output:
[
  {{"text": "Gold Collection", "candidate_types": ["category_name"]}}
]

2) Input: `How many customers are in the North Central Region?`
   (Assuming `region_name` is in Available Text Filter Types)
Output:
[
  {{"text": "North Central", "candidate_types": ["region_name"]}}
]

3) Input: `List orders handled by Arjun`
   (Assuming `rep_name` is in Available Text Filter Types)
Output:
[
  {{"text": "Arjun", "candidate_types": ["rep_name"]}}
]

4) Input: `Show active customers with delivered orders`
   (No named text values — only status/boolean filters)
Output:
[]

5) Input: `Revenue from Gold customers in fiscal year 2023`
   (Assuming `segment_name` and `category_name` are both in Available Text Filter Types and KB hints show "Gold" matches both)
Output:
[
  {{"text": "Gold", "candidate_types": ["segment_name", "category_name"]}}
]

## IMPORTANT
- ALWAYS follow the Decision Process order above.
- Candidate types must be restricted to `Available Text Filter Types`.
- Output must be valid JSON and nothing else.
- Ambiguity is determined at runtime from KB similarity hints and entity type coverage — do NOT hardcode which specific values are ambiguous.
"""),
    ("human", "{rewritten_question}")
])

# 2. Resolve Entity Type
RESOLVE_ENTITY_TYPE_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an NLP assistant. Given an entity mention, its candidate types, and the full question context, determine the most likely entity type.

### **CRITICAL: Ambiguity Detection**
- If the mention has multiple candidate types AND the question context does not clearly resolve which one the user means, trigger user clarification:
  - Set confidence to "low"
  - Example: mention has candidate_types=["type_a", "type_b"] and neither context word settles it
  - → Set confidence="low" so the user can clarify

### **Rules:**
- If context clearly indicates one type (e.g., a type-word adjacent to the mention, or the question's phrasing leaves no ambiguity): confidence="high"
- If the mention alone is ambiguous without more context: confidence="low"
- Output a JSON object with two keys: `resolved_type` (a string from the candidate list) and `confidence` (must be "high", "medium", or "low").
- Assign "high" if context makes it obvious. Assign "low" if it's genuinely ambiguous.
- Example: {{"resolved_type": "category_name", "confidence": "high"}}
- Output ONLY valid JSON, no markdown."""),
    ("human", """### **Question:**
{rewritten_question}

### **Mention:**
"{mention}"

### **Candidate Types:**
{candidate_types}""")
])

# 3. Rerank Candidates
RERANK_CANDIDATES_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an entity linking expert. Given an entity mention and a list of retrieved candidate database entities, rank them by relevance to the mention.

### **Input Candidates Format:**
Each candidate is represented as JSON with a `canonical_name`, `alias` (the matched string), and `score`.

### **Rules:**
- Rank the candidates based on how well they match the mention logically and textually.
- Output a JSON object with:
  1. `ranked`: A list of candidate dictionaries (include exactly what was provided, plus a `confidence` field from 0.0 to 1.0).
  2. `auto_resolve`: true or false. Map to true ONLY if the top candidate is extremely likely (confidence > 0.85). If it could reasonably be multiple things, set to false.
- Output ONLY valid JSON, no markdown.
- Example: {{"ranked": [{{"canonical_name": "North Central Region", "alias": "NCR", "confidence": 0.95}}], "auto_resolve": true}}"""),
    ("human", """### **Question:**
{rewritten_question}

### **Mention:**
"{mention}" (Type: {entity_type})

### **Candidates:**
{candidates_json}""")
])

# 4. Rewrite Question with Entities
REWRITE_WITH_ENTITIES_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a query rewriting expert. Rewrite the user's question by replacing ONLY the entity mentions with their fully resolved canonical names AND their entity types.

### **Rules:**
- Use the provided list of resolved entities mapping.
- Wrap the inserted canonical names in single quotes.
- After each canonical name, include the entity type as a descriptor word (e.g., "region", "segment", "category", "product", "rep").
- **PRESERVATION RULE (CRITICAL):** You must keep EVERY other word from the original question EXACTLY as it is. Do NOT drop, rephrase, or simplify any non-entity words.
- Output ONLY the rewritten question string, without any preamble or markdown blocks.

### **Examples:**
Original: "show revenue from gold customers in the north"
Resolved: gold -> Gold (segment_name), north -> North Central Region (region_name)
Rewrite: "Show revenue from 'Gold'(segment_name) customers in the 'North Central Region'(region_name)."

Original: "what products are in the gold collection and how many were sold last year"
Resolved: gold collection -> Gold Collection (category_name)
Rewrite: "What products are in the 'Gold Collection'(category_name) and how many were sold last year."

Original: "show orders handled by arjun in the west region"
Resolved: arjun -> Arjun Sharma (rep_name), west region -> West Region (region_name)
Rewrite: "Show orders handled by 'Arjun Sharma'(rep_name) in the 'West Region'(region_name)." """),
    ("human", """### **Original Question:**
{rewritten_question}

### **Resolved Entities:**
{resolved_entities_text}""")
])

