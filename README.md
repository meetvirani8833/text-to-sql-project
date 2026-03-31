# Curriculum Agent (NL-to-SQL)

A Natural Language to SQL system for a university Curriculum Database, featuring a knowledge base (RAG + Graph) and a multi-step LangGraph workflow.

## Architecture
- **Backend**: FastAPI, LangGraph, SQLAlchemy
- **Frontend**: React, Vite, TailwindCSS
- **Databases**: 
  - Source: MySQL (External)
  - Metadata: PostgreSQL + pgvector (Docker)
  - Graph: Neo4j (Docker)

## Setup

### 1. Prerequisites
- Docker Desktop
- Python 3.10+
- Node.js 18+
- MySQL instance with Curriculum Database

### 2. Infrastructure (Docker)
```bash
cp backend/.env.example backend/.env
# Edit .env with your passwords and API keys
docker-compose up -d
```

### 3. Backend
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```
API: http://localhost:8000
Docs: http://localhost:8000/docs

### 4. Frontend
```bash
cd frontend
npm install
npm run dev
```
App: http://localhost:5173

## Project Structure
- `backend/app/knowledge_base`: Metadata models & RAG pipeline
- `backend/app/workflow`: LangGraph nodes & edges
- `backend/app/api`: WebSocket & REST endpoints
- `backend/docs/tables`: YAML documentation for tables
