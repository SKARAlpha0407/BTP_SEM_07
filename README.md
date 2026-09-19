
# Research Copilot

AI-powered research agent for ML papers on arXiv.

## Setup

### Backend
1. cd backend
2. python3 -m venv .venv
3. source .venv/bin/activate
4. pip install -r requirements.txt
5. Ensure Ollama is running (`ollama serve`) and llama3 is pulled (`ollama pull llama3`).
6. uvicorn app.main:app --reload --port 8000

### Frontend
1. cd frontend
2. npm install
3. npm run dev (runs on localhost:3000)

## Features
- Semantic Ranking: uses SentenceTransformers for cosine similarity.
- Local LLM: uses Ollama for structured insight extraction.
- Graph Visualization: maps paper relationships using react-force-graph.
