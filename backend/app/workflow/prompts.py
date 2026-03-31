from langchain_core.prompts import ChatPromptTemplate

# 1. Rewrite User Question
REWRITE_QUESTION_PROMPT = ChatPromptTemplate.from_messages([
    ("human", """You are a database question rewriter. Your task is to rewrite the user's current question into a concise, direct, and well-structured query formatted as "Action -> What -> Filter".

Preprocessing:
- If the user's current question contains multiple sentences or clauses, merge them into one logical query by combining the action, target, and constraints into a single short sentence before rewriting.

Rules:
- Include any named entities, codes, identifiers, time periods, or other filters exactly as provided, without unnecessary expansion.
- If the question contains filtering phrases (e.g., "for", "in", "under", "by", "from", "handled by", "during"), preserve these terms as filters.
- If multiple entities are mentioned, merge them into one clear query.
- Do NOT add or assume details that the user did not explicitly include.
- Keep the rewritten question as short as possible.

Examples:
User: "Show me all orders"
Rewrite: "Show information about orders"

User: "List products in the Electronics category"
Rewrite: "List products in the Electronics category"

User: "Find total revenue for the Gold Collection"
Rewrite: "Find total revenue for the Gold Collection category"

User: "Which customers are in the Platinum segment?"
Rewrite: "List customers in the Platinum segment"

User: "Show all delivered orders in fiscal year 2024"
Rewrite: "List delivered orders in fiscal year 2024"

User: "Give me revenue by region for last year"
Rewrite: "Find revenue grouped by region for fiscal year 2023"

Conversation Context:

Previous question:
Current question: {user_question}

Task:
Rewrite the current question into a single, short, clear, and structured query that preserves any filtering terms exactly as provided.
""")
])

# 2. Filter Tables
FILTER_TABLES_PROMPT = ChatPromptTemplate.from_messages([
    ("human", """You are a table-selection engine for a text-to-SQL system.

Your task is to read:
1) the rewritten user question,
2) the available candidate tables with their descriptions,
3) the domain rules,

and return the set of tables that is sufficient to answer the question correctly.

Selection rules:
- Include every table that is directly needed to answer the question.
- Include any table needed for joins, foreign-key traversal, lookup values, bridge/mapping relationships, filtering, grouping, aggregation, time logic, status logic, hierarchy logic, or domain-specific rule enforcement.
- If a table is required by the rules_text, include it even if it is not explicitly mentioned in the question.
- If multiple tables are connected and the question involves any data from that relationship, include all tables needed to safely join and interpret the result.
- Prefer recall over precision: it is better to include one extra relevant table than to omit a necessary one.
- Never include tables that are clearly unrelated to the question.
- Never invent table names.
- Use only table names that appear in candidate_tables_text.
- Preserve the table names exactly as written.
- Do not duplicate table names.
- If the question can only be answered with a fact table plus lookup/dimension tables, include both the fact table and every lookup/dimension table needed to interpret the output.
- If the question mentions a concept that is stored indirectly, include the table that stores the concept and any table required to decode, map, or constrain it.
- If a table description says it stores labels, codes, mappings, parent-child links, history, or metadata that help interpret records, treat it as potentially necessary whenever the question depends on that information.
- If unsure whether a table is needed, include it.


### Question: {rewritten_question}

### **Available Tables:**
{candidate_tables_text}

### **Domain Rules:**
{rules_text}

### **STRICT OUTPUT FORMAT (MANDATORY):**
- Your response MUST contain ONLY a Python-style list of table names.
- Do NOT include explanations, reasoning, comments, markdown, or any additional text.
- Do NOT include phrases like "The relevant tables are".
- Do NOT include code blocks or formatting.
- Output ONLY the list.

Correct output examples:
["tbl_product", "tbl_product_category"]
["tbl_customer"]

Incorrect outputs (DO NOT DO THIS):
The relevant tables are ["tbl_product"]
Here are the tables: ["tbl_customer", "tbl_region"]
""")
])

PRUNE_COLUMNS_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a SQL column selection expert for a text-to-SQL pipeline.

Your task is to read the rewritten question, table schemas, join paths, and domain rules, then return the minimum set of columns needed to generate correct SQL.

### Selection Rules
For every table, include all columns needed for any of the following:

1. FILTER columns
   - Columns used in WHERE, HAVING, ON, EXISTS, NOT EXISTS, IN, BETWEEN, LIKE, comparison, or rule-based filtering.
   - Include implicit filter columns required by domain rules, even if the user did not mention them.

2. DISPLAY columns
   - Columns the final result should show directly to the user.

3. COMPUTATION columns
   - Columns needed for COUNT, SUM, AVG, MIN, MAX, GROUP BY, ORDER BY, DISTINCT, CASE logic, ranking, window functions, and subqueries.

4. JOIN columns
   - Always include primary keys, foreign keys, bridge keys, mapping keys, and any columns required to join the selected tables.
   - If a join path references a column, include that column even if it is not otherwise needed.

5. ENTITY PROTECTION Rule
   - The following columns represent named entities used for downstream entity resolution.
   - If these columns exist in the provided table schemas, they MUST be included:
   {entity_columns_text}

6. Domain Rule Priority
   - If a column is required by rules_text, include it even if the question does not explicitly mention it.

### Important Constraints
- Be high-recall: include a column whenever omitting it could break SQL generation.
- Prefer including extra necessary columns over missing a required one.
- Do NOT invent column names.
- Use only column names that appear in the provided table schemas.
- Preserve exact spelling and casing from the schemas.
- Do NOT duplicate columns within the same table.
- Do NOT include tables or columns that are clearly unrelated.

### Output Format
- Return ONLY a JSON object mapping table_name -> [column_names].
- Include only tables that actually need at least one column.
- Example:
  {{"tbl_customer": ["customer_id", "customer_name", "segment_id"], "tbl_order": ["order_id", "fiscal_year", "total_amount"]}}
- Do NOT include any explanation, markdown, or extra text outside the JSON object."""),

    ("human", """### Question:
{rewritten_question}

### Table Schemas:
{table_schemas_text}

### Join Paths:
{join_paths_text}

### Domain Rules:
{rules_text}""")
])

# 4. Generate SQL Query
GENERATE_QUERY_PROMPT = ChatPromptTemplate.from_messages([
    ("human", """You are an expert SQL developer for MySQL. Generate a single SELECT query to answer the user's question.

## User's question
{rewritten_question}
{error_context}

## Query rules
- Always select top 1000 rows.
- If the user's question implies summarizing or measuring data, generate an aggregated query using the appropriate SQL aggregation function instead of returning individual rows.
- NEVER generate DML queries like INSERT, UPDATE, DELETE.
- When joining tables, rely exclusively on the relationships defined in JOIN_PATHS.
- If the selected tables do not share a direct or indirect path in JOIN_PATHS, do not join them.
- Always reference the FK → PK pairs exactly as stated — no custom columns or assumed relationships.
- DO NOT include a WHERE statement if the user did not specify a condition or filtering in the question.
- Do not use columns that are not listed in the `Available Columns` section and never use `*` in the SELECT statement. If you need all columns, specify their names explicitly.
- Aliases must be distinguishable.
- Entity names in the rewritten question appear as `'CANONICAL NAME'(entity_type)` — these MUST appear as exact-match WHERE filters in the SQL.

### **Available Columns:**
{pruned_columns_text}

### **Join Paths:**
{join_paths_text}

### **Domain Rules:**
{rules_text}

### **Upstream Warnings / Entity Confidence:**
{confidence_flags_text}

### **Output Format:**
- Output ONLY the SQL query, no explanation.
- Do not use markdown backticks.
- Use only the provided tables, columns, and join paths.
- Follow all domain rules strictly.
""")
])

# 5. Validate SQL Query
VALIDATE_QUERY_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a SQL syntax and schema validation expert. Your ONLY job is to check:
1. SQL is syntactically valid for MySQL.
2. All tables and columns used in the query exist in the provided schema.
3. JOINs reference the correct columns.

### **IMPORTANT RULES:**
- Do NOT evaluate business logic or judge whether the filter conditions make business sense.
- Do NOT flag queries as invalid just because the WHERE clause seems "logically inconsistent" from a general perspective — domain data can have counter-intuitive combinations.
- Column value enums and their meanings are defined in the schema descriptions. Trust them.
- If the SQL is syntactically correct and uses valid columns, respond with exactly 'VALID'.
- Only respond with 'INVALID: <specific SQL syntax or schema issue>' if there is a real SQL or schema error."""),
    ("human", """### **Question:**
{rewritten_question}

### **SQL:**
{generated_sql}

### **Available Schema (with column descriptions and valid values):**
{pruned_columns_text}

### **Join Paths:**
{join_paths_text}""")
])

SUMMARIZE_RESULT_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a careful data analyst. Summarize the SQL query results for the user.

The raw data table is already shown separately above, so do NOT output a markdown table.

### Core Truthfulness Rules
- Use ONLY the provided SQL results.
- Do NOT invent, infer, or assume facts that are not directly supported by the results.
- Before summarizing, check whether the returned results actually answer the user's question.
- If the results are unrelated, insufficient, contradictory, or too ambiguous to answer the question, say so clearly.
- If the results do not support a reliable answer, respond with a cautious statement such as:
  - "I can't determine that from the returned results."
  - "The returned data does not appear to answer the question."
  - "The query results are not sufficient to conclude this."

### Rules based on row count
- If the result is empty (0 rows), say clearly that no results were found.
- If there are fewer than 10 rows and the results are relevant, write a brief summary that covers each row or item.
- If there are 10 or more rows and the results are relevant, write only a short generalized summary (1–3 sentences) highlighting the total count and any clear patterns. Then tell the user to refer to the data table above for full details.

### Result relevance checks
- If the SQL or result preview appears to target the wrong entity, wrong time period, wrong table, or wrong metric, do not pretend it answers the question.
- If the result set is partial or seems unrelated to the question, explicitly say that the answer cannot be determined from the returned data.
- If the question asks for a specific value but the results do not contain that value, do not guess it.

### Formatting
- Format numbers with commas for readability.
- You may use bold text or bullet points for readability.
- Do NOT include markdown tables.
- Do NOT mention internal uncertainty labels or hidden reasoning.
- Keep the response concise and grounded in the results.

### Output style
- If relevant and complete: summarize clearly.
- If empty: say no results were found.
- If irrelevant or insufficient: say you cannot determine the answer from the returned results."""),
    ("human", """### Question:
{user_question}

### SQL:
{generated_sql}

### Results ({row_count} rows):
{result_preview}""")
])
