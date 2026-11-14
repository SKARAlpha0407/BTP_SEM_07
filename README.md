# Research Copilot

AI-powered research agent for ML papers on arXiv: semantic (optionally hybrid)
ranking, a persistent pgvector cache, LLM insight extraction, and a reading-map
graph. It is also the Semester 7 continuation of our Semester 6 study,
*Comparison of word embedding methods in NLP: classification under textual
noise* — see [docs/SEM6_CONTINUITY.md](docs/SEM6_CONTINUITY.md).

## Quick start (Docker)

    GROQ_API_KEY=<your key> docker compose up --build     # Postgres+pgvector and API on :8000
    cd frontend && npm install && npm run dev             # UI on :3000

## Manual setup

Prerequisites: Python 3.12, PostgreSQL 16 with pgvector, Node.js, a Groq API key
(https://console.groq.com/keys).

1. `pip install -r backend/requirements.txt`
2. Copy `.env.example` to `backend/.env` and set `GROQ_API_KEY`
3. `createdb research && psql research -c "CREATE EXTENSION IF NOT EXISTS vector;"`
4. `cd backend && alembic upgrade head && cd ..`
5. `./dev.sh` (backend on :8000, frontend on :3000)

## Features

- **Semantic ranking** with a swappable embedder (`EMBED_MODEL`, default
  all-MiniLM-L6-v2 on CPU); exact-title matches are pinned first.
- **Hybrid retrieval** (`HYBRID_RETRIEVAL=1`): BM25 + dense, fused with
  Reciprocal Rank Fusion.
- **Persistent cache**: Postgres + pgvector (HNSW, cosine) stores papers,
  embeddings and LLM insights; warm queries skip arXiv and the LLM.
- **LLM insights** (Groq) with defensive JSON parsing and a **grounding check**
  that flags summary terms missing from the abstract.
- **Explainability**: each result lists the query terms it matched.
- **Observability**: `GET /metrics` reports p50/p95 latency by cache path,
  cache hit rate and LLM calls saved; `GET /health` reports the active models.
- **Reading map**: force-directed graph coloured by relevance rank.

## Evaluation (Sem 6 protocol applied to retrieval)

    python -m eval.build_dataset --per-category 150       # corpus from arXiv (~1 min)
    python -m eval.run_benchmark --models all-MiniLM-L6-v2 BAAI/bge-small-en-v1.5 \
        hash-ngram bm25 hybrid:all-MiniLM-L6-v2           # noise robustness, 5 seeds
    python -m eval.calibrate_thresholds                   # data-driven thresholds
    python -m eval.embedding_map                          # t-SNE + silhouette

Results land in `eval/results/` (`summary.md`, CSV, plots).

## Tests

    python -m pytest tests -q        # no network, database or API key needed
    python qa/regression_v2.py       # live API regression (server must be running)
