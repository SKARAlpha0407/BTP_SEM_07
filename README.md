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
2. Copy `.env.example` to `backend/.env` and set `GROQ_API_KEY` and
   `DATABASE_URL` (the built-in default points at the original developer's
   local user, so set your own).
3. `createdb research && psql research -c "CREATE EXTENSION IF NOT EXISTS vector;"`
4. `cd backend && alembic upgrade head && cd ..`
5. `./dev.sh` (backend on :8000 with auto-reload, frontend on :3000)

Open http://localhost:3000. API docs are at http://localhost:8000/docs (served
to this machine only; tunnel visitors get 404 unless `EXPOSE_DOCS=1`).

## Using the deployed site (phones, Safari, other computers)

The site at https://btp-sem-07.vercel.app is only the frontend; searches run on
the backend on your laptop. To reach it from anywhere:

```bash
./dev.sh        # terminal 1: backend on localhost:8000
./tunnel.sh     # terminal 2: prints a link like
                # https://btp-sem-07.vercel.app/?api=https://<name>.trycloudflare.com
```

Open or share that link. Each device remembers the backend address for 24
hours, so later visits work without `?api=`; the address is forgotten when it
stops answering, and the status bar has a reset control. The tunnel URL changes
every time `./tunnel.sh` starts, and search works only while both commands run. For a
permanent backend, host it (e.g. with `docker-compose.yml`) and set
`NEXT_PUBLIC_API_BASE` in the Vercel project.

**Before a demo:** search each topic you plan to show once in advance. Papers,
embeddings and summaries are then stored, so repeat searches need fewer LLM
calls (summaries are reused; the synthesis and cluster names are always
written fresh).

## Features

- **Semantic ranking** with a swappable embedder (`EMBED_MODEL`, default
  `all-MiniLM-L6-v2` on CPU). Scores are a sigmoid-calibrated cosine with a
  boost for titles containing the query; exact-title matches are pinned first.
- **Hybrid retrieval** (on by default; `HYBRID_RETRIEVAL=0` for dense only):
  hand-written BM25 and the dense ranking are fused by Reciprocal Rank Fusion
  to choose the top results; those results are then shown in order of their
  calibrated dense score (with the title boost).
- **Persistent cache** in Postgres + pgvector (cosine; HNSW index): papers,
  embeddings and LLM summaries are stored. Short topics (two words or fewer)
  searched within 12 hours can skip arXiv; stored summaries are reused for any
  paper seen before. Failed summaries are never stored.
- **LLM summaries** (Groq) requested 8 papers per call with defensive JSON
  parsing, and a **grounding check** reporting how many summary terms appear in
  the abstract.
- **arXiv politeness:** requests are paced (3 s apart, 20 s timeout), results
  are cached per topic for 6 hours, a 429 pauses arXiv calls for 60 s, and the
  closest stored papers are shown (marked "Stored copy") when arXiv is down.
  Searches are limited to 10 per visitor and 30 in total per minute.
- **Explainability:** each result lists the query terms it matched, highlighted
  in its title.
- **Reading map:** 3D graph of up to 30 papers. Links combine abstract
  similarity, shared categories and shared authors; clusters are named by the
  LLM. Colour = publication year (one-hue ramp), size = number of links.
  Hover a paper for its arXiv page and PDF; click to see its closest papers.
- **Observability:** `GET /metrics` (latency per stage and cache path, cache
  hit rates, LLM calls saved; this machine only) and `GET /health` (active
  models and database status).
- **Interface:** start page with live backend status, three-pane results
  (ranked list, reader with synthesis / paper tabs, map), light and dark
  themes, reduced-motion support.

## Results (Sem 6 noise protocol applied to retrieval)

816 arXiv papers from six categories; each paper's title is the query and its
abstract the relevant document; 5 noise seeds. The full nDCG@10 tables are in
[REPORT.md §8](REPORT.md#8-evaluation-and-results) and `eval/results/summary.md`.

In absolute nDCG@10, the dense WordPiece models lose the most under
out-of-vocabulary noise (MiniLM −0.426 at 50%), echoing the Sem 6 finding for
BERT; hybrid retrieval cuts MiniLM's loss by about 44% (to −0.237) but still
loses more than BM25 (−0.140). BM25 leads here partly because a paper's title
shares most of its words with its own abstract, which favours exact word
matching. The only subword baseline is a weak hashed embedder, so this
benchmark does not settle how a real subword model compares. Details and
caveats: [REPORT.md §8](REPORT.md#8-evaluation-and-results).

Reproduce:

    python -m eval.build_dataset --per-category 150       # corpus from arXiv (~1 min)
    python -m eval.run_benchmark --models all-MiniLM-L6-v2 BAAI/bge-small-en-v1.5 \
        hash-ngram bm25 hybrid:all-MiniLM-L6-v2           # noise robustness, 5 seeds
    python -m eval.calibrate_thresholds                   # data-driven cache thresholds
    python -m eval.embedding_map                          # t-SNE + silhouette

Outputs land in `eval/results/` (`summary.md`, CSV, JSON, plots).

## Tests

    python -m pytest tests -q        # offline tests: no network, database or API key needed
    python qa/regression_v2.py       # live API regression (server must be running)
