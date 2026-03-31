# Sales Agent: Architecture & Handover Guide

## I have tried to give short and simple explanation of the project instead creating a large documentation.

## It will give you all the information about what is going on where and how things are connected.

## If you feel stuck somewhere, you can simply asks your AI assistant to explain that part in detail.

Welcome to the Sales Agent! This document explains the complete, deeply integrated architecture of this project. It is structured to help you rapidly understand not just _what_ the technologies are, but _how_ and _why_ they interact.

---

## 1. System Overview & Technology Stack

This project is an **AI-powered Text-to-SQL Agent** designed to intelligently navigate and query a highly interconnected enterprise sales database.

It is divided into two operational halves: an **Offline Knowledge Base Pipeline** (for data ingestion and relationship mapping) and an **Online Inference Pipeline** (a real-time LangGraph agent that answers user queries).

### Core Technologies:

- **Frontend**: React + TypeScript + Vite. Communicates with the backend via stateless REST APIs.
- **Backend API**: FastAPI.
- **AI Orchestration**: **LangGraph** & LangChain. Orchestrates a graph of specialized LLM nodes (using GPT models) to safely build, audit, and execute SQL.
- **Primary Database (Source of Truth)**: **MySQL**. Contains the actual university data. Generated SQL is executed against this database.
- **Vector Database**: **pgvector** (Postgres 16 with pgvector extension) running in **Docker**. Stores semantic embeddings of database entities (like regions, products, customer segments) to allow fuzzy human-language matching.
- **Graph Database**: **Neo4j** running in **Docker**. Specifically used to store database schema relationships. Tables are nodes; Foreign Keys are edges. It calculates the exact shortest `JOIN` paths between arbitrary tables.

---

## 2. Infrastructure & Local Setup

The system relies on Docker to manage the complex graph and vector database dependencies.

### Starting the Infrastructure

1. Open the root directory and start the databases:
   ```bash
   docker-compose up -d
   ```
   _This starts **pgvector** on port 9010 (as `dfuse_postgres`) and **Neo4j** on ports 9011/9012 (as `dfuse_neo4j`)._

### Booting the Application

2. **Backend**:
   - Navigate to `backend/`
   - Setup `.env` with required variables (`OPENAI_API_KEY`, `MYSQL_URL`, POSTGRES and NEO4J credentials).
   - `pip install -r requirements.txt`
   - Start the server: `uvicorn app.main:app --reload` (Runs on port 8000)
3. **Frontend**:
   - Navigate to `frontend/`
   - `npm install`
   - Start Vite: `npm run dev`

---

## 3. The Offline Pipeline (Knowledge Base Setup)

Before the agent can intelligently write SQL, it must digest the sales schema and entity values. This offline process is handled by scripts in `backend/scripts/`.

### Configuration Rules (`.yaml` Files)

The entire ingestion and runtime logic is dictated by configuration files located in the codebase:

- **`entities.yaml`**: Defines which columns in the MySQL database represent important "Entities". For example, it tells the system that `tbl_region.region_name` is an entity. The scripts will extract all region names into the vector database.
- **`domain_rules.yaml`**: Hardcoded business logic instructing the LLM on specific definitions (e.g., "Active means `status=1`"). This is injected dynamically during SQL generation.

### The Checkpoint System

Because indexing thousands of rows via LLMs is slow and prone to API timeouts, the pipeline uses a robust **Checkpoint System**. (This is just for testing, you can modify for production later)

- **State Storage**: Progress is tracked automatically in `backend/app/.rebuild_checkpoints/`.
  - `entity_rebuild_checkpoint.json`
  - `kb_rebuild_checkpoint.json`
- **Commands**: If a script gets stuck, you can safely `Ctrl+C` and restart it using the `--resume` flag to pick up exactly where it left off, potentially saving hours of API calls. You can also view `--status` or use `--clear-checkpoint`.

### Ingestion Steps: (Please do them in this order only, because rebuild_kb.py vipes out the whole pgvector)

1. **`rebuild_kb.py`**: Reads the MySQL schema. Uses LLMs to write plain-english descriptions for every column, and pushes the Foreign Key mapping to **Neo4j**.

#### ALWAYS MAKE LANGCHAIN_TRACING_V2 = FALSE BEFORE REBUILDING IT (it gives thousands of parallel calls to LLM for generating alias)

2. **`rebuild_entity_kb.py`**: Scans table columns (defined in `entities.yaml`), generates embeddings via OpenAI, and stores them in **pgvector**.

---

## 4. The Online Pipeline (Agent Workflow)

When a user submits a question, it enters the **LangGraph** workflow. The graph passes a powerful `state` dictionary between Python nodes step-by-step.

### Phase 1: Clarification & Resolution

1. **`rewrite_question`**: Normalizes the user question into a coherent "Action -> Target -> Filter" sentence.

### Phase 2: Schema Assembly & Joining

2. **`retrieve_tables`**: Identifies which tables are needed based on the resolved entities and keywords.
3. **`prune_columns`**: LLM removes irrelevant columns from the schema context payload to prevent overflowing context windows and hallucinated columns.
4. **`get_join_paths`**: The backend asks **Neo4j**: _"I need to query `customers` and `products`. How do I join them?"_ Neo4j dynamically returns the exact shortest SQL `JOIN` path constraints.
5. **`extract_entities`**: An LLM extracts potential named variables (e.g., "Electronics") and immediately searches **pgvector** to find the closest official database strings.
6. **`entity_resolution` (Subgraph)**:
   - Uses `backend/app/entity_resolution/cache.py` to prevent redundant LLM lookups for already-resolved entities.
   - If an entity is ambiguous (e.g., "Gold" exists as both a Product Category and a Customer Segment), the workflow generates a LangGraph `interrupt()`.
   - **Interrupts**: The API returns a `status: "awaiting_clarification"`. Processing pauses. When the user selects an option on the frontend, the frontend sends the response using the SAME `conversation_id`, and the backend resumes the exact point in the graph using `Command(resume=...)`.

### Phase 3: SQL Generation & Judging

7. **`generate_query`**: Ingests the rewritten question, pruned schema, Neo4j join path, and `domain_rules.yaml`. The LLM writes the raw MySQL query.
8. **`validate_query`**: Passes the SQL to the actual MySQL engine using the `EXPLAIN` keyword. If MySQL throws a syntax or schema error, it rejects it before attempting an actual data pull.

### Phase 4: Output

9. **`execute_and_summarize`**: Once validated, the SQL runs. The raw data payload is bundled as HTML to render in the frontend's grid table view, and an LLM converts the data into a conversational message result.

---

## 5. Important Commands

Here is a quick-reference list of terminal commands needed for setting up and running the project:

### Infrastructure

```bash
# Start Neo4j and pgvector in the background
docker-compose up -d

# Stop infrastructure
docker-compose down
```

### Knowledge Base Pipeline (Backend)

_Always run these from the `backend/` directory with your virtual environment activated._

```bash
# 1. Rebuild Schema Knowledge Base (Tables, Columns, Neo4j Joins)
# Note: Always run this FIRST if you are starting fresh!
python scripts/rebuild_kb.py

# 2. Rebuild Entity Knowledge Base (pgvector Embeddings)
# Note: Run this AFTER rebuild_kb.py
python scripts/rebuild_entity_kb.py

# At this point, your knowledge base setup is complete, you can start using the application

# Checkpoint Flags (Works for both scripts)
python scripts/rebuild_entity_kb.py --resume             # Resume from an interrupted rebuild
python scripts/rebuild_entity_kb.py --status             # Check current completion percentage
python scripts/rebuild_entity_kb.py --clear-checkpoint   # Wipe checkpoints and start fresh
```

### Starting the Applications

```bash
# Start Backend (Run inside the `backend/` directory)
uvicorn app.main:app --reload

# Start Frontend (Run inside the `frontend/` directory)
npm run dev
```

---

## 6. Development Handover Summary

If you are modifying or extending the system, keep these rules in mind:

- **Adding new search properties?** Update `entities.yaml` and run `python scripts/rebuild_entity_kb.py --resume`. The pgvector DB will automatically grab the new fields.
- **Is the agent generating incorrect filtering logic?** Inject explicit business instructions into `backend/config/domain_rules.yaml`.
- **Modifying Prompts?** Almost all LLM system prompts are centralized cleanly in `backend/app/workflow/prompts.py` and `backend/app/entity_resolution/prompts.py`.
- **Database Migrations?** If the underlying MySQL tables change structures, you must run `python scripts/rebuild_kb.py --clear-checkpoint` so that Neo4j can rebuild the join paths.

This architecture specifically segregates responsibilities (Neo4j for joins, pgvector for semantic entity matching, MySQL for data, LLMs for reasoning) to maximize accuracy without requiring an LLM to blindly guess your company's internal structure.
