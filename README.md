# Text-to-SQL Agent

**Ask questions about a large, interconnected database in plain English and get validated SQL, results and a readable answer.**

![Text-to-SQL architecture](docs/architecture.svg)

## The problem

Sending a whole schema to an LLM breaks down on real databases: hundreds of columns with cryptic names, tables that only make sense when joined correctly, and user wording that doesn't match the stored values ("Gold" could be a product category or a customer segment). This project adds a knowledge base and a multi-step LangGraph workflow so the model sees only what it needs and every query is checked before it runs.

## How it works

**Offline (run once, resumable):** `rebuild_kb.py` has an LLM describe every column and stores those docs in pgvector, then loads foreign keys into Neo4j. `rebuild_entity_kb.py` embeds the real values of the columns listed in `entities.yaml`.

**Online (per question):** a LangGraph workflow rewrites the question, retrieves and filters tables, gets column docs, asks Neo4j for the join path, prunes columns, resolves entities, generates SQL, validates it, executes it, and summarises the result.

## Key design decisions

- **Retrieve the schema, don't paste it.** Table and column docs live in pgvector. The workflow selects relevant tables, filters them, then prunes columns, so the prompt stays small and the model has fewer chances to invent a column.
- **Joins come from a graph, not from the model.** Tables are Neo4j nodes and foreign keys are edges. The workflow asks for the shortest join path, and if that path needs a table that wasn't selected, a branch fetches it.
- **Ambiguity is resolved with the user.** Candidate entities are matched against real database values in pgvector. When a value is ambiguous the entity-resolution subgraph calls LangGraph's `interrupt()`, asks the user to choose, and resumes the same run using the same `conversation_id`.
- **Validate before executing.** Generated SQL goes through `EXPLAIN` on MySQL first. Errors loop back to query generation, and unrecoverable ones end in a graceful fallback message.
- **Business rules are configuration.** Definitions such as what "active" means live in `domain_rules.yaml` and are injected into generation without code changes.

## Tech stack

FastAPI · LangGraph · SQLAlchemy · OpenAI · MySQL (source data) · PostgreSQL + pgvector · Neo4j · React · TypeScript · Vite · Tailwind · Docker

## Run locally

Requires Docker Desktop, Python 3.10+, Node 18+ and a MySQL instance with the source database.

```bash
cp backend/.env.example backend/.env     # OpenAI key, MySQL, Postgres, Neo4j credentials
docker-compose up -d                     # pgvector Postgres + Neo4j

cd backend
pip install -r requirements.txt
python scripts/rebuild_kb.py             # schema docs + Neo4j join graph (run first)
python scripts/rebuild_entity_kb.py      # entity embeddings (run second)
uvicorn app.main:app --reload            # API on :8000

cd ../frontend
npm install && npm run dev               # app on :5173
```

Both rebuild scripts accept `--resume`, `--status` and `--clear-checkpoint`.

## More documentation

- [architecture.md](architecture.md): how the pieces connect
- [workflow.md](workflow.md): full LangGraph diagram, including the entity-resolution subgraph
- [example_prompts.py](example_prompts.py): sample questions

<!-- Add a "Contributors" section describing who built which part. -->
