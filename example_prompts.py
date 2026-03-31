from typing import Tuple, Dict
from langchain_openai import OpenAIEmbeddings
import numpy as np
from pydantic import SecretStr
import mysql.connector
from mysql.connector import Error as MySQLError
from app.services.source_repository.mysql_connector import get_mysql_connection
import sqlparse
from langchain_core.output_parsers import CommaSeparatedListOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.output_parsers import StrOutputParser
from langchain_core.output_parsers import JsonOutputParser
from langchain_postgres import PGVector

from app.core.text_to_sql.attribute_formatters import *
from app.core.text_to_sql.state_models import *
from app.core.text_to_sql.state_models import GraphState
from app.config import OPENAI_KEY, PG_CONN
from app.models.chat_models import (
    ChatFinalResponse,
    ChatGeoJsonResponse,
    ChatIntermediateResponse,
)
from app.routers.websocket_helper import send_ws_update
from app.services.metadata_repository.metadata_entities import *
from app.services.graph_repository.relationship_graph import (
    find_multi_table_join_paths,
)
from app.services.text_to_sql.df_summarizer import summarize_dataframe
from app.services.text_to_sql.geometry_parser import (
    convert_geometry_columns_to_geojson,
    detect_spatial_columns,
)

# ----------------------------------------------------
#  Retrieval functions
# ----------------------------------------------------


async def get_similar_tables_node(state: GraphState) -> GraphState:
    """Tool to retrieve table candidates for sql query generation"""
    await send_ws_update(
        state.websocket,
        ChatIntermediateResponse(status="Retrieving table candidates..."),
    )
    question = state.question
    open_ai_embeddings = state.embedding_model
    pg_vector = PGVector(
        connection=PG_CONN,
        embeddings=open_ai_embeddings,
        collection_name=f"table_descriptions_{state.project_id}",
    )
    retriever = pg_vector.as_retriever(search_kwargs={'k': 15})
    results = retriever.invoke(question)

    retrieved_tables = [
        StateRetrievedTableDescription(
            description=result.page_content, 
            schema=result.metadata.get("schema_name", ""),
            table_name=result.metadata.get("table_name", "")
        )
        for result in results
    ]
    state.retrieved_tables = retrieved_tables
    return state


async def get_highlevel_rules_node(state: GraphState) -> GraphState:
    metadata_repository = state.metadata_repository
    db = state.connected_db
    retrieved_tables = state.retrieved_tables

    db_rules = metadata_repository.get_rules_for_database(db.id) 
    schemas = list(set([table.schema for table in retrieved_tables]))

    schemas_metadata: List[StateSchemaMetadata] = [
        StateSchemaMetadata(
            schema_name=schema, rules=metadata_repository.get_rules_for_schema(schema)
        )
        for schema in schemas
    ]
    state.schemas_metadata = schemas_metadata
    state.db_rules = db_rules
    return state


async def get_table_metadata_node(state: GraphState) -> GraphState:
    await send_ws_update(
        state.websocket, ChatIntermediateResponse(status="Retrieving table metadata...")
    )

    metadata_repository = state.metadata_repository
    selected_tables = state.selected_tables

    results_metadatas: List[StateTableMetadata] = []

    for selected_pair in selected_tables:
        table_name = selected_pair.table_name
        schema_name = selected_pair.schema_name
        
        fetched_table = metadata_repository.get_table_by_table_and_schema_name(
            table_name=table_name,
            schema_name=schema_name
        )
        
        columns = metadata_repository.get_columns_for_table(table_name)
        table_rules = metadata_repository.get_rules_for_table(table_name)
        table_metadata = StateTableMetadata(
            table_name=table_name,
            table_schema=fetched_table.schema,
            table_description=fetched_table.description,
            columns=columns,
            rules=table_rules,
        )
        results_metadatas.append(table_metadata)

    state.table_metadata = results_metadatas
    return state

# ----------------------------------------------------
#  Missing table functionality
# ----------------------------------------------------

async def get_join_paths_node(state: GraphState) -> GraphState:
    """
    Given state.selected_tables (list of SelectedPair),
    find join paths in Neo4j, then populate missing_tables
    with all schema–table pairs that are absent on either side.
    """

    await send_ws_update(
        state.websocket,
        ChatIntermediateResponse(status="Retrieving FK relationships..."),
    )

    graph = state.relationships_graph
    metadata_repository = state.metadata_repository

    # `selected_tables` is a list of SelectedPair(schema_name, table_name)
    selected_pairs: List[SelectedPair] = state.selected_tables

    # Resolve real schema names (PGVector metadata may have empty schemas)
    resolved_pairs: List[SelectedPair] = []
    for sp in selected_pairs:
        if sp.schema_name:
            resolved_pairs.append(sp)
        else:
            try:
                fetched = metadata_repository.get_table_by_table_and_schema_name(
                    table_name=sp.table_name, schema_name=sp.schema_name
                )
                resolved_pairs.append(
                    SelectedPair(schema_name=fetched.schema, table_name=sp.table_name)
                )
            except Exception:
                resolved_pairs.append(sp)  # Keep original if lookup fails
    selected_pairs = resolved_pairs
    state.selected_tables = resolved_pairs  # Update state for downstream nodes

    join_paths: List[JoinPath] = []
    missing_tables: List[MissingTable] = []

    if len(selected_pairs) > 1:
        # 1) Retrieve relationships among the selected pairs
        join_paths = find_multi_table_join_paths(graph, selected_pairs)

        # 2) Build a set of (schema, table) from the join paths
        fk_pairs = {(jp.fk_schema, jp.fk_table) for jp in join_paths}
        pk_pairs = {(jp.pk_schema, jp.pk_table) for jp in join_paths}
        path_pairs = fk_pairs | pk_pairs

        # 3) Build a set of (schema, table) from selected_pairs
        selected_set = {
            (sp.schema_name, sp.table_name) for sp in selected_pairs
        }

        # a) not_in_join = pairs the user selected but not in any path
        not_in_join = selected_set - path_pairs

        # b) bridging_missing = pairs in the path but not selected by the user
        bridging_missing = path_pairs - selected_set

        # 4) Combine them into total_missing
        total_missing = not_in_join.union(bridging_missing)

        # 5) Build MissingTable objects
        missing_tables = [
            MissingTable(table_schema=schema, table_name=table)
            for (schema, table) in total_missing
        ]
    else:
        # If there's only one or zero selected pairs, treat them all as missing
        missing_tables = [
            MissingTable(table_schema=sp.schema_name, table_name=sp.table_name)
            for sp in selected_pairs
        ]

    # Store results in the state
    state.join_paths = join_paths
    state.missing_tables = missing_tables

    return state



async def get_missing_tables(state: GraphState) -> GraphState:
    await send_ws_update(
        state.websocket, ChatIntermediateResponse(status="Fetching missing tables...")
    )

    missing_tables: List[MissingTable] = state.missing_tables
    metadata_repository = state.metadata_repository

    
    results_metadatas: List[StateTableMetadata] = []

    for selected_pair in missing_tables:
        table_name = selected_pair.table_name
        schema_name = selected_pair.table_schema
        
        fetched_table = metadata_repository.get_table_by_table_and_schema_name(
            table_name=table_name,
            schema_name=schema_name
        )
        
        columns = metadata_repository.get_columns_for_table(table_name)
        table_rules = metadata_repository.get_rules_for_table(table_name)
        table_metadata = StateTableMetadata(
            table_name=table_name,
            table_schema=fetched_table.schema,
            table_description=fetched_table.description,
            columns=columns,
            rules=table_rules,
        )
        results_metadatas.append(table_metadata)

    state.table_metadata.extend(results_metadatas)
    return state


# ----------------------------------------------------
#  Metadata filtering functions
# ----------------------------------------------------


async def filter_tables_node(state: GraphState) -> GraphState:
    await send_ws_update(
        state.websocket, ChatIntermediateResponse(status="Selecting tables...")
    )


    model = state.llm_model
    question = state.question
    retrieved_tables = state.retrieved_tables
    schemas_metadata = state.schemas_metadata
    db_rules = state.db_rules

    interpretation_rules = []
    filter_tables_prompt = PromptTemplate(
    template="""
You are a Database model expert assistant. 
Use the explanations of the following tables to identify which schema/table pairs 
are most relevant to answer the question.

Question: {question}

Your output MUST be a valid JSON array of objects, each with keys "schema" and "table".
No additional keys, no extra text.

### **Rules for Selection:**
- Select 1 table for each distinct entity mentioned in the user's question.
- For each entity, choose only the table that most comprehensively represents it.
- Include additional tables only if the user's question provides further details for that entity.
- Select **only tables that explicitly match the entity requested by the user**.
- If multiple tables cover the same entity, select only one table for that entity.
- If a table name **ends with '_PT', '_PG', or '_LN'**, include a corresponding '_PARENT' table if available.
- Do NOT include unrelated tables, even if they contain vaguely related concepts.
- If you are unsure, select at least one table that you find most relevant: [].

### **Entity-Based Selection:**
- You MUST **only** select tables that contain data about the entity described in the user's question.  
  For questions involving multiple entities, ensure each distinct entity is handled separately.

### **Available Tables:**
{context}

Interpretation rules:
{interpretation_rules}

Return a JSON array in the format:
[
{{"schema": "SCHEMA_NAME", "table": "TABLE_NAME"}},
...
]
    """,
        input_variables=["question", "context", "interpretation_rules"],
    )


    table_filter_chain = filter_tables_prompt | model | JsonOutputParser()
    interpretation_rules += [rule.description for rule in db_rules]

    for schema in schemas_metadata:
        interpretation_rules += [f"- {rule}\n\n" for rule in schema.rules]

    documents = [
        f"""Schema: {table.schema} 
        Table Name: {table.table_name}
        Table Description: {table.description} \n\n """
        for table in retrieved_tables
    ]

    rules_box = "\n".join(interpretation_rules)
    context_box = "\n".join(documents)

    raw_output = table_filter_chain.invoke(
        {
            "context": context_box,
            "question": question,
            "interpretation_rules": rules_box,
        }
    )
    

    unique_pairs = set()
    selected_pairs: List[SelectedPair] = []

    # Map: lowercase_table_name -> schema_name
    valid_table_schema_map = {
        rt.table_name.lower(): rt.schema for rt in retrieved_tables
    }

    for entry in raw_output:
        schema = entry.get("schema")
        table = entry.get("table")

        if schema and table:
            # Check if schema is valid, if not try to correct it
            # Perform case-insensitive check
            t_lower = table.lower()
            if t_lower in valid_table_schema_map:
                correct_schema = valid_table_schema_map[t_lower]
                if schema != correct_schema:
                    print(f"Correcting schema for table {table}: {schema} -> {correct_schema}")
                    schema = correct_schema
            
            if (schema, table) not in unique_pairs:
                unique_pairs.add((schema, table))
                selected_pairs.append(
                    SelectedPair(schema_name=schema, table_name=table)
                )


    state.selected_tables = selected_pairs
    return state


async def prune_columns_node(state: GraphState):
    await send_ws_update(
        state.websocket, ChatIntermediateResponse(status="Pruning columns...")
    )

    question = state.question
    db_rules = state.db_rules
    schema_metadata = state.schemas_metadata
    join_paths = state.join_paths
    table_metadata = state.table_metadata
    model = state.llm_model

    class SelectedColumnsOutputParser(JsonOutputParser):
        def get_format_instructions(self) -> str:
            return """
    Return a JSON object with **valid JSON keys** (do not use SQL-style double quotes around schema/table names).

    Correct format:
    {
        "selected_columns": {
            "SCHEMA_NAME_1.TABLE_NAME_1": ["COLUMN_A", "COLUMN_B"],
            "SCHEMA_NAME_2.TABLE_NAME_2": ["COLUMN_C", "COLUMN_D"]
        }
    }

    **Rules:**
    - Table names should be formatted as "SCHEMA_NAME.TABLE_NAME" (without extra quotes).
    - The JSON structure must be **valid**.
    - No extra text, comments, or explanations.
            """

    COLUMN_PRUNING_PROMPT = PromptTemplate(
        template="""
    You are a database assistant. 

    **User's Question:**
    {question}

    We have the following rules:

    1) **Database Rules** (apply to all tables):
    - Always include primary keys when selecting columns for every table that was selected
    - Always include primary and foreign key columns that are needed for joins
    {db_rules_str}

    2) **Schema Rules** (apply to all tables in that schema):
    {schema_rules_str}

    3) **Table Rules** (apply only to the specific table):
    {table_rules_str}

    **Relevant Tables and Columns:**
    {table_columns_str}

    **Join Paths (Important for selecting join columns)**:
    {join_paths_str}

    Your job:
    - Pick the columns that are needed to answer the user's question.
    - Respect all rules above (DB, schema, table).
    - If a table is used, ensure any required **join columns** are also included if needed for linking data across tables.
    - Output JSON with the structure shown below.

        {format_instructions}
        """,
        input_variables=[
            "question",
            "db_rules_str",
            "schema_rules_str",
            "table_rules_str",
            "table_columns_str",
            "join_paths_str",
            "format_instructions",
        ],
    )

    parser = SelectedColumnsOutputParser()
    format_instructions = parser.get_format_instructions()

    column_selector = COLUMN_PRUNING_PROMPT | model | SelectedColumnsOutputParser()

    input_dict = {
        "question": question,
        "db_rules_str": rules_to_str(db_rules),
        "schema_rules_str": schema_rules_to_str(schema_metadata),
        "table_rules_str": table_rules_to_str(table_metadata),
        "table_columns_str": table_columns_to_str(table_metadata),
        "join_paths_str": join_paths_to_str(join_paths),
        "format_instructions": format_instructions,
    }

    response = column_selector.invoke(input_dict)

    filtered_table_metadata = []
    selected_columns = response["selected_columns"]  #

    for tm in table_metadata:
        col_list = []

        needed_cols = (
            selected_columns.get(f"{tm.table_schema}.{tm.table_name}")
            or selected_columns.get(tm.table_name, [])
        )
        for col in tm.columns:
            if col.name in needed_cols:
                col_list.append(col)

        new_tm = StateTableMetadata(
            table_name=tm.table_name,
            table_schema=tm.table_schema,
            table_description=tm.table_description,
            columns=col_list,
            rules=tm.rules,
        )
        filtered_table_metadata.append(new_tm)

    state.selected_metadata = filtered_table_metadata
    return state




# ----------------------------------------------------
#  Query processing functions
# ----------------------------------------------------


async def rewrite_question_node(state: GraphState) -> GraphState:
    metadata_repository = state.metadata_repository
    chat_info = state.chat_info
    model = state.llm_model
    
    last_state: ChatState | None = metadata_repository.get_last_state_for_chat(chat_info.chat_id)

    prompt_input = {}
    
    QUERY_REWRITE_PROMPT = PromptTemplate(
        template="""
You are a geodata question rewriter. Your task is to rewrite the user's current question into a concise, direct, and well-structured query formatted as "Action -> What -> How".

### **Rules:**
- Include any filters, locations, or specific details exactly as provided, without unnecessary expansion.
- If the question contains spatial phrases (e.g., "in", "at", "near", "around", "next to", "on map"), preserve these terms as filters.
- If multiple entities are mentioned, merge them into one clear query.
- Do NOT add or assume details that the user did not explicitly include.
- Keep the rewritten question as short as possible.

### **Examples:**
1. **User:** "Show me waterways"  
   **Rewrite:** "Show information about waterways"

2. **User:** "List rivers in Germany sorted by length"  
   **Rewrite:** "List rivers in Germany by length"

3. **User:** "Find lakes and reservoirs with area > 1000 sq km"  
   **Rewrite:** "Find lakes and reservoirs over 1000 sq km"

4. **User:** "What are the deepest rivers and lakes in Europe?"  
   **Rewrite:** "List the deepest rivers and lakes in Europe"

5. **User:** "Show bridges on map"  
   **Rewrite:** "Show bridges on map"

6. **User:** "Can I dock at a berth named Lomelse Sahara?"  
   **Rewrite:** "Find berth named 'Lomelse Sahara'"

### **Conversation Context:**
Previous question: {previous_question}
Current question: {current_question}

### **Task:**
Rewrite the current question into a single, short, clear, and structured query that preserves any spatial or filtering terms exactly as provided.
 """,
        input_variables=["previous_question", "current_question"]
    )
    
    if last_state:
        prompt_input = {
            "previous_question": last_state.question,
            "current_question": state.question
        }
    else:
        prompt_input = {
            "previous_question": "",
            "current_question": state.question
        }
    
    query_rewrite_chain = QUERY_REWRITE_PROMPT | model | StrOutputParser()

    rewritten_question = query_rewrite_chain.invoke(prompt_input)
    await send_ws_update(
        state.websocket, ChatIntermediateResponse(status=f"Rewritten prompt: {rewritten_question}")
    )
    state.question = rewritten_question
    return state

    

async def generate_query_node(state: GraphState) -> GraphState:
    model = state.llm_model
    db = state.connected_db
    question = state.question
    missing_tables = state.missing_tables
    db_rules = state.db_rules
    schemas_metadata = state.schemas_metadata
    table_metadata = state.table_metadata
    join_paths = state.join_paths
    generated_query = state.generated_query
    error_node = state.node_error
    selected_metadata = state.selected_metadata

    QUERY_GENERATION_PROMPT = PromptTemplate(
        template="""
    {prompt_base}

    ## User's Question
    {question}

    ## Query rules
    - Always select top 1000 rows
    - If the user's question implies summarizing or measuring data - generate an aggregated query using the appropriate SQL aggregation function instead of returning individual rows.
    - NEVER generate DML queries like INSERT, UPDATE, DELETE.
    - When joining tables, rely exclusively on the relationships of <schema>.<table>.<id> objects defined in JOIN_PATHS. 
        - If the selected tables do not share a direct or indirect path in JOIN_PATHS, do not join them. 
        - Always reference the FK → PK pairs exactly as stated-no custom columns or assumed relationships. 
    - DO NOT include a where statement if user did not specify a condition or selection filtering in question 
    - Do not use columns that are not listed in `Available Tables & Columns section`
    - Aliases must be distinguishable

    ## Database Rules (Apply to All Tables)
    - If `geometry` type column is used, always format it with ST_AsText(column_name)
    {db_rules_str}

    ## Schema Rules (Apply to All Tables Within Each Schema)
    {schema_rules_str}

    ## Table Rules (Specific to a corresponding Table)
    {table_rules_str}
    

    ## Available Tables & Columns
    {table_metadata_str}

    ## JOIN_PATHS (Only these relationships are allowed for joining):
    {join_paths_str}


    ### Task
    1. Respect all rules and guidelines above.
    2. Generate a single valid {db_type} SQL query that answers the user question.
    3. Use only the join relationships listed in the JOIN_PATHS section. Do not use any additional columns for joining.
    4. Return only the SQL query as plain text-without Markdown formatting, explanations, or comments.

    """,
        input_variables=[
            "prompt_base",
            "question",
            "db_type",
            "db_rules_str",
            "schema_rules_str",
            "table_rules_str",
            "table_metadata_str",
            "join_paths_str",
        ],
    )

    query_generator_chain = QUERY_GENERATION_PROMPT | model | StrOutputParser()

    initial_prompt_base = """You are a database assistant. The user has asked a question, and we need to construct a valid MySQL SQL query."""
    query_fix_prompt_base = """You are a database assistant. You from past has written a `{db_type}` SQL script that has failed to run. 
**Error Message:**
{error_description} 

**Failed Query:** 
{generated_query}
    
Fix the query according to the following prioritized guidelines:

1. **Syntax & Intent Preservation:**  
   - Correct any {db_type} syntax errors (punctuation, keywords, parentheses, quotes) without changing the intended selected columns, filters, or joins.

2. **Column Validation:**  
   - Only use columns that appear in the Available Tables & Columns.  
   - If a filter or join references a column that does not exist, then:
     - If a valid alternative exists (as indicated in the schema metadata), substitute it.
     - Otherwise, remove that filter or join.
     
3. **Filter Handling:**  
   - If a WHERE condition references a column that does not exist, consult the Available Tables & Columns section.
   - If an alternative column that conveys the same filtering intent exists (e.g., use "WW_NAME" for waterway names instead of "NAME"), substitute it.
   - Do not remove the filtering condition if it is crucial to the user's query; always attempt to preserve the filtering intent.

3. **Join Conditions:**  
   - Use only the exact join relationships defined in JOIN_PATHS (FK → PK). Do not invent additional join conditions.
   
4. **Handling Geometry Columns in Aggregations:**  
   - **Do not include geometry columns directly in the GROUP BY clause** since geometry types are not comparable.

5. **No Hallucination:**  
   - Do not add any new columns or relationships that are not present in the provided schema metadata.

6. **Output Requirement:**  
   - Return only the corrected SQL query as plain text-without markdown formatting, explanations, or comments.
    """

    prompt_base = initial_prompt_base

    if error_node:
        await send_ws_update(
            state.websocket, ChatIntermediateResponse(status="Fixing the query...")
        )
        generated_query = generated_query
        prompt_base = query_fix_prompt_base.format(
            db_type=db.db_type,
            error_description=error_node.message,
            generated_query=generated_query,
        )
    else:
        await send_ws_update(
            state.websocket, ChatIntermediateResponse(status="Generating query...")
        )
        prompt_base.format(db_type=db.db_type)

    # Summarize missing tables
    missing_table_lines = []
    for mt in missing_tables:
        missing_table_lines.append(f"{mt.table_name}")
    missing_tables_str = (
        "\n".join(missing_table_lines) if missing_table_lines else "None"
    )

    join_path_text = "Select 1 of tables that most likely refer to asked entity by user question."
    if join_paths:
        join_path_text = join_paths_to_str(join_paths)

    prompt_input = {
        "prompt_base": prompt_base,
        "db_type": db.db_type,
        "question": question,
        "db_rules_str": rules_to_str(db_rules),
        "schema_rules_str": schema_rules_to_str(schemas_metadata),
        "table_rules_str": table_rules_to_str(table_metadata),
        "table_metadata_str": table_metadata_to_str(selected_metadata),
        "join_paths_str": join_path_text,
    }

    # final_prompt = QUERY_GENERATION_PROMPT.format(**prompt_input)
    response = query_generator_chain.invoke(prompt_input)

    state.generated_query = response
    return state


# ----------------------------------------------------
#  Error handling functions
# ----------------------------------------------------


async def query_validation_node(state: GraphState) -> GraphState:
    await send_ws_update(
        state.websocket, ChatIntermediateResponse(status="Validating query...")
    )

    query = state.generated_query
    db = state.connected_db
    retry_count = state.retry_count

    parsed = sqlparse.parse(query)

    if retry_count >= ERROR_RETRY_LIMIT:
        state.node_error = NodeError(
            error_type="TOO_MANY_ATTEMPTS",
            message=f"Exceeded {ERROR_RETRY_LIMIT} retries",
            node_name="query_validation_node.__name__",
        )
        return state

    if len(parsed) == 0:
        state.node_error = NodeError(
            error_type="SYNTAX_ERROR",
            message="Invalid syntax.",
            node_name=query_validation_node.__name__,
        )
        state.retry_count += 1
        return state

    conn = None
    try:
        conn = get_mysql_connection(db.source_conn_string)
    except Exception as e:
        print(f"❌ Validation: MySQL connection failed: {e}")
        state.node_error = NodeError(
            error_type="CONNECTION_ERROR",
            message=f"Cannot connect to database: {e}",
            node_name=query_validation_node.__name__,
        )
        return state

    try:
        cursor = conn.cursor(buffered=True)
        for statement in query.strip().split(";"):
            stmt = statement.strip()
            if stmt:
                cursor.execute(stmt)
        state.node_error = None
        state.retry_count = 0
        cursor.close()
    except Exception as e:
        print(f"⚠️ Validation: Query execution error (retry {retry_count + 1}): {e}")
        state.node_error = NodeError(
            error_type="SEMANTIC_ERROR",
            message=str(e),
            node_name=query_validation_node.__name__,
        )
        state.retry_count += 1
    finally:
        if conn:
            conn.close()
        return state

async def handle_empty_data(state: GraphState)-> GraphState:
    ... 

async def fallback_node(state: GraphState) -> GraphState:
    
    result_message = "Please rewrite your question or use `Docs` option to answer your question."
    
    if state.node_error:
        result_message = state.node_error.message + result_message
    
    await send_ws_update(
        state.websocket,
        ChatFinalResponse(response=f"Fallback: {result_message}"),
    )
    return state


# ----------------------------------------------------
#  Result processing functions
# ----------------------------------------------------


async def execute_query_node(state: GraphState) -> GraphState:
    """
    Executes the generated SQL query against the connected database.
    Returns either a result set or an error message.
    """
    await send_ws_update(
        state.websocket, ChatIntermediateResponse(status="Executing query...")
    )
    db = state.connected_db
    query = state.generated_query



    try:
        conn = get_mysql_connection(db.source_conn_string)
            
        print("▶ Executing query:\n", query)

        df = pd.read_sql_query(state.generated_query, conn) # type: ignore
        
        state.result_data = df.loc[:, df.notna().any(axis=0)]
        conn.close()
            
    except mysql.connector.ProgrammingError as e:
        state.node_error = NodeError(
            error_type="QUERY_EXECUTION_ERROR",
            message=str(e),
            node_name=execute_query_node.__name__,
        )
    except MySQLError as e:
        state.node_error = NodeError(
            error_type="DB_EXECUTION_ERROR",
            message=str(e),
            node_name=execute_query_node.__name__,
        )
    finally:
        return state


async def send_geo_data_node(state: GraphState) -> GraphState:
    await send_ws_update(
        state.websocket, ChatIntermediateResponse(status="Collecting geojson data...")
    )

    result_df = state.result_data
    geo_columns = detect_spatial_columns(result_df)
    
    if geo_columns:
        geo_json_objects = convert_geometry_columns_to_geojson(result_df, geo_columns)

        await send_ws_update(
            state.websocket, ChatGeoJsonResponse(geo_objects=geo_json_objects)
        )

    return state


async def summarize_result_node(state: GraphState) -> GraphState:
    user_question = state.question
    result_data = state.result_data
    db = state.connected_db
    model = state.llm_model
    
    await send_ws_update(
        state.websocket, ChatIntermediateResponse(status="Summarizing results...")
    )

    generated_summary = summarize_dataframe(result_data)

    table_preview = result_data.head(1).to_string(index=False)
    messages = [
    SystemMessage(content=f"You are a {db.db_type} data analyst assistant."),
    HumanMessage(
        content=f"""Here is a summary of the retrieved table:
        
        **Table Overview:** 
        {generated_summary}

        **Column Details:**
        ```
        {table_columns_to_str(state.selected_metadata)}
        ```

        **Sample Data :**
        ```
        {table_preview}
        ```

        **User's Question:**
        {user_question}

        Summarize the table contents.
        """
    ),
]
    response: AIMessage = model.invoke(messages)
    await send_ws_update(
        state.websocket, ChatFinalResponse(response=str(response.content))
    )

    return state


# ----------------------------------------------------
#  Conditional Routing Functions
# ----------------------------------------------------


def route_on_missing_tables(state: GraphState) -> str:
    return "join tables are missing" if state.missing_tables else "prune columns"


def route_on_validation(state: GraphState) -> str:
    error = state.node_error
    
    if not error:
        return "execute_query"
    elif error.error_type == "SYNTAX_ERROR" or error.error_type == "SEMANTIC_ERROR":
        return "regenerate_query"
    else:
        return "unknown_error"


def route_on_execution(state: GraphState) -> str:
    error = state.node_error

    if not error:
        return "end"
    elif error.error_type == "QUERY_EXECUTION_ERROR":
        return "regenerate_query"
    else:
        return "unknown_error"
    
    
async def route_on_existing_data(state: GraphState) -> str:
    is_df_empty = state.result_data.empty or state.result_data.shape[1] == 0
    
    if is_df_empty: 
        state.node_error = NodeError(
            error_type="NO_RESULT_DATA",
            message="Query returned empty results.",
            node_name=execute_query_node.__name__,
        )
        await send_ws_update(
            state.websocket, ChatIntermediateResponse(status="No data found...")
        )
    
    return  "fallback" if is_df_empty else "proceed"
    
        
async def route_on_safety(state: GraphState) -> str:
    model = state.llm_model
    prompt = f"""
    You are a security checker. 
    Examine the following user question for possible SQL injection attempts:
    
    Question: {state.question}
    
    Reply with exactly one word: "SAFE" or "UNSAFE".
    """

    response = model.invoke(prompt)

    classification = response.content.strip().upper()
    is_safe = (classification == "SAFE")
    return "proceed" if is_safe else "unsafe_question"
