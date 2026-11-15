# Kavosh

*Kavosh (کاوش) is Persian for "exploration". Formerly Research Copilot.*

Kavosh finds, ranks, summarises and maps arXiv papers on a research topic. You
type a topic; it pulls candidate papers from arXiv, ranks them by meaning with a
sentence-embedding model, writes a TL;DR / problem / method / benchmarks summary
for each with an LLM (and checks that summary against the abstract), writes a
cross-paper synthesis, and draws a 3D reading map of how the papers relate.

It is also the Semester 7 continuation of our Semester 6 study, *Comparison of
word embedding methods in NLP: classification under textual noise*. See
[docs/SEM6_CONTINUITY.md](docs/SEM6_CONTINUITY.md) and the results below.

**Stack:** FastAPI · sentence-transformers (CPU) · PostgreSQL 16 + pgvector ·
Groq (`openai/gpt-oss-20b`) · Next.js 16 (pages router) · Tailwind v4 ·
react-force-graph-3d. Full write-up: [REPORT.md](REPORT.md).

## Quick start (Docker)

    GROQ_API_KEY=<your key> docker compose up --build     # Postgres+pgvector and API on :8000
    cd frontend && npm install && npm run dev             # UI on :3000

## Manual setup

Prerequisites: Python 3.12, PostgreSQL 16 with pgvector, Node.js 20+, a Groq API
key (https://console.groq.com/keys).

1. `pip install -r backend/requirements.txt`
2. Copy `.env.example` to `backend/.env` and set `GROQ_API_KEY` (and
   `DATABASE_URL` if your Postgres is not the default).
3. `createdb research && psql research -c "CREATE EXTENSION IF NOT EXISTS vector;"`
4. `cd backend && alembic upgrade head && cd ..`
5. `./dev.sh` (backend on :8000 with auto-reload, frontend on :3000)

Open http://localhost:3000. API docs are at http://localhost:8000/docs.

## Using the deployed site (phones, Safari, other computers)

The site at https://btp-sem-07.vercel.app is only the frontend; searches run on
the backend on your laptop. To reach it from anywhere:

```bash
./dev.sh        # terminal 1: backend on localhost:8000
./tunnel.sh     # terminal 2: prints a link like
                # https://btp-sem-07.vercel.app/?api=https://<name>.trycloudflare.com
```

Open or share that link. Each device remembers the backend address, so later
visits work without `?api=` until the next tunnel. The tunnel URL changes every
time `./tunnel.sh` starts, and search works only while both commands run. For a
permanent backend, host it (e.g. with `docker-compose.yml`) and set
`NEXT_PUBLIC_API_BASE` in the Vercel project.

**Before a demo:** search each topic you plan to show once in advance. Papers,
embeddings and summaries are then cached, so repeat searches are faster and
need fewer LLM calls.

## Features

- **Semantic ranking** with a swappable embedder (`EMBED_MODEL`, default
  `all-MiniLM-L6-v2` on CPU). Scores are a sigmoid-calibrated cosine with a
  boost for titles containing the query; exact-title matches are pinned first.
- **Optional hybrid retrieval** (`HYBRID_RETRIEVAL=1`): hand-written BM25 fused
  with the dense ranking by Reciprocal Rank Fusion.
- **Persistent cache** in Postgres + pgvector (HNSW, cosine): papers,
  embeddings and LLM summaries are stored; short repeat queries can skip arXiv
  and the LLM entirely.
- **LLM summaries** (Groq) in one batched call with defensive JSON parsing, and
  a **grounding check** reporting how many summary terms appear in the abstract.
- **Explainability:** each result lists the query terms it matched, highlighted
  in its title.
- **Reading map:** 3D graph of up to 30 papers. Links combine abstract
  similarity, shared categories and shared authors; clusters are named by the
  LLM. Colour = publication year (one-hue ramp), size = number of links.
  Hover a paper for its arXiv page and PDF; click to see its closest papers.
- **Observability:** `GET /metrics` (latency per stage and cache path, cache
  hit rates, LLM calls saved) and `GET /health` (active models).
- **Interface:** start page with live backend status, three-pane results
  (ranked list, reader with synthesis / paper tabs, map), light and dark
  themes, reduced-motion support.

## Results (Sem 6 noise protocol applied to retrieval)

816 arXiv papers from six categories; each paper's title is the query and its
abstract the relevant document; 5 noise seeds. nDCG@10:

| System | Clean | 50% character noise | 50% word dropout | 50% out-of-vocabulary |
|---|---|---|---|---|
| BM25 | 0.983 | 0.900 | 0.843 | 0.843 |
| Hybrid (BM25 + MiniLM) | 0.979 | 0.891 | 0.815 | 0.742 |
| bge-small-en-v1.5 | 0.961 | 0.804 | 0.718 | 0.607 |
| all-MiniLM-L6-v2 (default) | 0.950 | 0.777 | 0.698 | 0.524 |
| hash-ngram (subword baseline) | 0.301 | 0.236 | 0.224 | 0.158 |

Dense WordPiece models lose the most under out-of-vocabulary noise, echoing the
Sem 6 finding for BERT; hybrid retrieval halves that loss. BM25 leads here
partly because 78.6% of title words also appear in the abstract, which favours
exact word matching. Details and caveats: [REPORT.md §8](REPORT.md#8-evaluation-and-results).

Reproduce:

    python -m eval.build_dataset --per-category 150       # corpus from arXiv (~1 min)
    python -m eval.run_benchmark --models all-MiniLM-L6-v2 BAAI/bge-small-en-v1.5 \
        hash-ngram bm25 hybrid:all-MiniLM-L6-v2           # noise robustness, 5 seeds
    python -m eval.calibrate_thresholds                   # data-driven cache thresholds
    python -m eval.embedding_map                          # t-SNE + silhouette

Outputs land in `eval/results/` (`summary.md`, CSV, JSON, plots).

## Tests

    python -m pytest tests -q        # 21 offline tests: no network, database or API key needed
    python qa/regression_v2.py       # live API regression (server must be running)
