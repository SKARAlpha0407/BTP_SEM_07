# Research Copilot

AI-powered research agent for ML papers on arXiv, with a persistent
pgvector-backed cache for fast repeat queries.

## Setup

### Prerequisites
- macOS with Homebrew
- Python 3.12 (conda env `btp2`)
- PostgreSQL 16 + pgvector 0.8.0 (`brew install postgresql@16` then build
  pgvector from source against that version)
- Node.js for the frontend
- Groq API key (https://console.groq.com/keys)

### Backend
1. conda activate btp2
2. cd backend
3. pip install -r requirements.txt
4. Create `backend/.env` with:
       GROQ_API_KEY=<your key>
       GROQ_MODEL=openai/gpt-oss-20b
5. createdb research
6. psql research -c "CREATE EXTENSION IF NOT EXISTS vector;"
7. alembic upgrade head
8. uvicorn backend.app.main:app --reload --port 8000

### Frontend
1. cd frontend
2. npm install
3. npm run dev  (runs on localhost:3000)

## Features
- **Semantic ranking:** SentenceTransformers (all-MiniLM-L6-v2, CPU).
- **Persistent cache:** Postgres + pgvector stores papers, embeddings, and
  Groq insights. Warm queries skip arXiv and Groq entirely (~1.4s vs ~8.6s cold).
- **LLM insight extraction:** Groq gpt-oss-20b with defensive JSON parsing.
- **Graph visualization:** force-directed graph with VIBGYOR color-coding by
  relevance rank.
