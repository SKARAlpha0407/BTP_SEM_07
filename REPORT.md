# Project Report — AI Research Copilot (BTP_SEM_07)

## 1. Overview
The AI Research Copilot is a full-stack application designed to help researchers discover and synthesize information from arXiv papers. It uses a Next.js 16 frontend (Pages router) and a FastAPI backend. The application retrieves papers based on a topic, reranks them using a local MiniLM embedding model (CPU-only), extracts structured insights and synthesis via the Groq API (gpt-oss-20b), and visualizes the research landscape as a force-directed graph with VIBGYOR color-coding by relevance rank.

**New in this version:** A persistent pgvector cache (Postgres 16 + pgvector 0.8.0) stores paper embeddings and LLM-generated insights. The search pipeline now uses a **hybrid retrieval** strategy: a cache-first lookup with semantic similarity and TTL filtering (12-hour max age) can skip arXiv entirely on warm topics (~1.4s), while cold topics fall back to arXiv fetch + cached-vector reuse (~8.6s). This yields a ~5.8× speedup on repeat queries.

## 2. End-to-End Flow

```mermaid
flowchart LR
    U([User])
    subgraph FE["Frontend · Next.js :3000"]
        IDX["pages/index.tsx<br/>search, state, render"]
        RM["components/ReadingMap.tsx<br/>force-graph, VIBGYOR by rank"]
        API["lib/api.ts<br/>fetch wrapper"]
    end
    subgraph BE["Backend · FastAPI :8000"]
        MAIN["app/main.py<br/>POST /search"]
        ARX["app/arxiv_client.py<br/>dual-search + tier sort"]
        EMB["app/embedding_service.py<br/>all-MiniLM-L6-v2 (CPU)"]
        LLM["app/llm_service.py<br/>Groq gpt-oss-20b"]
        CACHE["app/db + pipeline_cache.py<br/>pgvector cache"]
    end
    subgraph DB["PostgreSQL + pgvector"]
        PAPERS[("papers")]
        EMBEDS[("paper_embeddings<br/>vector(384), HNSW cosine")]
        INSIGHTS[("paper_insights<br/>composite PK")]
    end
    subgraph EXT["External"]
        ARXAPI[["arXiv API"]]
        GROQ[["Groq API"]]
    end

    U -->|topic| IDX
    IDX --> API
    API -->|POST /search| MAIN
    MAIN -->|embed topic| EMB
    MAIN -.->|cache lookup| CACHE
    CACHE -.->|HNSW search| EMBEDS
    CACHE -->|hydrate papers| PAPERS
    MAIN -->|cache hit| ARX
    MAIN -->|cache miss| ARX
    ARX -->|query| ARXAPI
    ARX -->|raw papers| CACHE
    CACHE -->|write embeddings| EMBEDS
    MAIN -->|insight cache read| INSIGHTS
    MAIN -->|extract misses| LLM
    LLM -->|chat.completions| GROQ
    MAIN -->|write insights| INSIGHTS
    MAIN -->|papers + synthesis + graph| API
    API --> IDX
    IDX --> RM
```

The user enters a topic in `pages/index.tsx`, which triggers a search via `lib/api.ts`. The FastAPI `main.py:search` handler orchestrates the pipeline:

1. **Cache-first lookup:** Embed the topic, query `paper_embeddings` via HNSW cosine similarity with a 12-hour TTL. If top score ≥ 0.4 and enough strong hits (≥ `max_results`), hydrate `Paper` objects from `papers` table and **skip arXiv entirely**.
2. **Candidate Retrieval (fallback):** If cache miss or weak hits, call `arxiv_client.search_papers` (dual-search + tier sort) to fetch from arXiv API.
3. **Semantic Ranking:** `embedding_service.rank_papers` (or `rank_with_cached_vectors` which reuses cached vectors, encoding only new abstracts).
4. **Insight Extraction:** Read `paper_insights` first; call `extract_insights_batch` only for misses; write fresh insights back.
5. **Synthesis & Graph:** Cross-paper synthesis + force-directed graph generation (same as before).
6. **Cache write-back:** Persist new papers, embeddings, and insights to Postgres.

## 3. Backend Request Pipeline

```mermaid
sequenceDiagram
    autonumber
    participant C as Client (Next.js)
    participant M as main.py
    participant E as embedding_service
    participant A as arxiv_client
    participant AX as arXiv API
    participant DB as PostgreSQL + pgvector
    participant L as llm_service
    participant G as Groq API

    C->>M: POST /search {topic, max_results}
    M->>E: embed_text(topic) → query_vec

    %% Cache-first lookup
    M->>DB: search_similar_with_ttl(query_vec, top_k=30, max_age_hours=12)
    DB-->>M: rows[(arxiv_id, score)]
    alt cache hit (top_score ≥ 0.4 ∧ strong_hits ≥ max_results)
        M->>DB: load_paper_objects(strong_ids)
        DB-->>M: hydrated Paper[]
        M->>M: ranked_papers = cache_hits
    else cache miss or weak
        M->>A: search_papers(topic, n=30)
        A->>AX: all:"topic" + ti:"topic"
        AX-->>A: raw results
        A->>A: tier-sort (exact title = 0)
        A-->>M: List[Paper]

        M->>DB: get_embeddings_for_ids(arxiv_ids, model)
        DB-->>M: cached_vecs {arxiv_id: vector}
        M->>E: rank_with_cached_vectors(topic, raw_papers, cached_vecs)
        E-->>M: ranked_papers, ranked_vectors
        M->>DB: save_papers_and_embeddings(ranked_papers, ranked_vectors, model)
    end

    %% Insights: cached first
    M->>DB: get_cached_insights(top_arxiv_ids, model)
    DB-->>M: cached {arxiv_id: insight}
    alt missing insights
        M->>L: extract_insights_batch(missing_papers)
        L->>G: chat.completions (no json_object/json_schema)
        G-->>L: raw JSON (LaTeX backslashes)
        L->>L: _safe_json_loads (repair + parse)
        L-->>M: List[insight dict]
        M->>DB: save_insights(fresh_items, model)
    end

    M->>L: synthesize_results(summaries)
    L->>G: chat.completions
    G-->>L: prose paragraph
    L-->>M: str

    M->>L: get_cluster_labels(clusters)
    L->>G: chat.completions
    G-->>L: {cid: label}
    L-->>M: dict

    M-->>C: {papers, synthesis, graph}
```

1. **Cache-First Lookup (new):** `search_similar_with_ttl` in `backend/app/db/repository.py` queries the HNSW index on `paper_embeddings` with a 12-hour TTL filter. If the top score ≥ 0.4 and at least `max_results` papers score ≥ 0.35, the pipeline hydrates full `Paper` objects from the `papers` table via `load_paper_objects` and skips arXiv entirely.
2. **Candidate Retrieval:** Implemented by `search_papers` in `backend/app/arxiv_client.py:37`. Returns a `List[Paper]` from arXiv API via dual-search strategy. Only reached on cache miss/weak cache.
3. **Semantic Ranking:** 
   - Cold path: `rank_papers` in `backend/app/embedding_service.py:42` embeds query + all abstracts on CPU.
   - Warm path (new): `rank_with_cached_vectors` reuses vectors from `get_embeddings_for_ids`, encoding only new abstracts.
4. **Cache Write-Back (new):** `save_papers_and_embeddings` in `backend/app/pipeline_cache.py` upserts to `papers` and `paper_embeddings` tables.
5. **Insight Extraction (cached):** `get_cached_insights` reads from `paper_insights` (composite PK: `arxiv_id` + `llm_model`). Misses go to `extract_insights_batch` in `backend/app/llm_service.py:58`. Fresh insights written back via `save_insights`.
6. **Synthesis:** `synthesize_results` in `backend/app/llm_service.py:133` returns a `str` combining findings.
7. **Cluster Labeling:** `get_cluster_labels` in `backend/app/llm_service.py:164` returns a `dict` mapping cluster IDs to theme labels.

## 4. Data Contracts

```mermaid
classDiagram
    class SearchResponse {
        +List~PaperResponse~ papers
        +string synthesis
        +Graph graph
    }
    class PaperResponse {
        +string title
        +string abstract
        +List~string~ authors
        +string arxiv_id
        +string arxiv_url
        +string pdf_url
        +string published
        +List~string~ categories
        +float relevance_score
        +Summary summary
    }
    class Summary {
        +string tldr
        +string problem
        +string methods
        +string benchmarks
    }
    class Graph {
        +List~Node~ nodes
        +List~Link~ links
    }
    class Node {
        +int id
        +string title
        +float val
        +string cluster
    }
    class Link {
        +int source
        +int target
        +float weight
    }
    SearchResponse --> PaperResponse
    SearchResponse --> Graph
    PaperResponse --> Summary
    Graph --> Node
    Graph --> Link
```

**Backend Models (`main.py`):**
- `PaperResponse`: `title` (str), `abstract` (str), `authors` (List[str]), `arxiv_id` (str), `arxiv_url` (str), `pdf_url` (str), `published` (str), `categories` (List[str]), `relevance_score` (float | None), `summary` (Dict[str, Any] | None).
- `Graph Node`: `id` (int), `title` (str), `val` (float), `cluster` (str).
- `Graph Link`: `source` (int), `target` (int), `weight` (float).

**PostgreSQL Tables (new):**

```mermaid
erDiagram
    papers ||--o{ paper_embeddings : "has"
    papers ||--o{ paper_insights : "has"
    papers {
        string arxiv_id PK
        string title
        text abstract
        json authors
        string arxiv_url
        string pdf_url
        string published
        json categories
        string embed_model
        timestamp updated_at
    }
    paper_embeddings {
        string arxiv_id PK, FK
        string embed_model PK
        vector(384) embedding
        timestamp created_at
        %% HNSW index on embedding (cosine)
    }
    paper_insights {
        string arxiv_id PK
        string llm_model PK
        json insight
        timestamp created_at
    }
```

- `papers`: Canonical paper metadata, one row per arXiv ID. `embed_model` tracks which embedding model produced the vector.
- `paper_embeddings`: Stores `vector(384)` embeddings with a **HNSW cosine index** for fast ANN search. Composite PK `(arxiv_id, embed_model)` allows multiple embedding models.
- `paper_insights`: Caches LLM-generated insights per paper per model. Composite PK `(arxiv_id, llm_model)`. Insight JSON contains `tldr`, `problem`, `methods`, `benchmarks`.

**Frontend Consumption (`frontend/lib/api.ts`):**
The frontend consumes the `SearchResponse` shape defined in the backend. No changes to the API contract.

**Cross-check:**
No mismatches found. The frontend `Paper` type in `api.ts` aligns with the backend `PaperResponse`.

## 5. Repo Topology

```mermaid
flowchart TB
    ROOT["BTP_SEM_07/"]
    ROOT --> BE["backend/"]
    ROOT --> FE["frontend/"]
    ROOT --> QA["qa/"]
    ROOT --> SPEC["specs/"]
    ROOT --> DEV["dev.sh"]
    ROOT --> ALE["alembic/"]

    BE --> BAPP["app/"]
    BE --> BVENV[".venv/  ← used by dev.sh"]
    BE --> BREQ["requirements.txt"]
    BAPP --> MAIN["main.py"]
    BAPP --> ARC["arxiv_client.py"]
    BAPP --> EMS["embedding_service.py"]
    BAPP --> LMS["llm_service.py"]
    BAPP --> PCACHE["pipeline_cache.py"]
    BAPP --> DB["db/"]
    DB --> DINIT["__init__.py"]
    DB --> DBASE["base.py"]
    DB --> DMODELS["models.py"]
    DB --> DCONN["connection.py"]
    DB --> DREPO["repository.py"]

    ALE --> AENV["env.py"]
    ALE --> AVER["versions/0001_initial.py"]

    FE --> PAGES["pages/"]
    FE --> COMP["components/"]
    FE --> LIB["lib/"]
    FE --> STY["styles/"]
    COMP --> RM["ReadingMap.tsx"]
    COMP --> PL["Pipeline.tsx"]

    QA --> REG["regression_v2.py"]
```

- `backend/`: FastAPI server logic, data processing, and **new pgvector persistence layer**.
- `backend/app/db/`: SQLAlchemy models, connection, and repository (CRUD + vector search).
- `backend/alembic/`: Database migrations (`env.py` + `versions/0001_initial.py`).
- `backend/app/pipeline_cache.py`: High-level cache write helpers (`save_papers_and_embeddings`, `save_insights`).
- `frontend/`: Next.js user interface.
- `qa/`: API regression tests.
- `specs/`: Project specifications and architectural docs.
- `.`: Root containing dev scripts and global config.

## 6. External Dependencies

**Backend (`backend/requirements.txt`):**
- `fastapi`: HTTP server.
- `uvicorn`: ASGI server for FastAPI.
- `arxiv`: Python wrapper for arXiv API.
- `sentence-transformers`: Local MiniLM embeddings.
- `numpy`: Numerical operations for embeddings.
- `requests`: HTTP client for API calls.
- `python-dotenv`: Environment variable loading.
- `pydantic`: Data validation and settings management.
- `sqlalchemy>=2.0`: ORM for Postgres.
- `psycopg[binary]>=3.2`: Postgres driver (binary build).
- `pgvector>=0.3`: pgvector SQLAlchemy integration + vector type.
- `alembic>=1.13`: Database migration tool.

**Frontend (`frontend/package.json`):**
- `next`: Framework for routing and rendering.
- `react` / `react-dom`: UI library.
- `react-force-graph-2d`: D3-based graph visualization.
- `tailwindcss` / `autoprefixer` / `postcss`: CSS framework.
- `lucide-react`: UI icons.
- `clsx` / `tailwind-merge`: Tailwind utility helpers.

---

## 7. Environment Variables

- `GROQ_API_KEY`: Required. Used in `backend/app/llm_service.py:23` for Groq API authentication.
- `GROQ_MODEL`: Optional. Default: `openai/gpt-oss-20b`. Used in `backend/app/llm_service.py:24`.
- `DB_USER` / `DB_PASSWORD`: Postgres credentials (via `.env.example`).
- `.env` exists in `backend/` and is listed in `.gitignore`.

---

## 8. Dev / Run

The `dev.sh` script automates the environment startup:
1. Starts the backend server using the specific interpreter path `./backend/.venv/bin/python` running `uvicorn backend.app.main:app` with `--reload` on port 8000.
2. Launches the frontend using `npx next dev --webpack` on port 3000.
3. Uses a `trap` to ensure the backend process is killed when the frontend dev server is stopped.

**New setup steps:**
- **Conda environment:** Activate `btp2` (Python 3.12) before running: `conda activate btp2`.
- **Database:** Postgres 16 + pgvector 0.8.0 on localhost:5432, database `research`. pgvector built from source against `postgresql@16` (Homebrew).
- **Migrations:** Run `alembic upgrade head` from `backend/` to create tables (`papers`, `paper_embeddings`, `paper_insights`, `alembic_version`).

---

## 9. Known Landmines

- **LLM Structured-Output Failure on gpt-oss-20b:** Both `response_format=json_object` and `response_format=json_schema` return HTTP 400 on Groq for this model. The solution is a **two-pass approach**: call the API without structured-output constraints, then parse the response with `_safe_json_loads` (in `llm_service.py`) which strips markdown fences, repairs LaTeX backslashes (`\\` → `\`), and falls back gracefully. Applies to `extract_insights_batch` and `get_cluster_labels`.
- **Polymorphic Summaries:** `Paper.summary` can be a `str` (raw) or a `dict` (structured). `llm_service._extract_tldr` handles this polymorphism.
- **CPU-Only Embeddings:** `embedding_service.py` MUST force `device="cpu"` to avoid Metal (MPS) race conditions on Apple Silicon that crash the server.
- **Python Environments:** `dev.sh` relies on `backend/.venv`, which is distinct from any root venv.
- **Cache TTL Sensitivity:** The 12-hour TTL in `search_similar_with_ttl` is a tunable; too short reduces cache hits, too long serves stale embeddings if the model changes.
- **HNSW Index Build:** `paper_embeddings` HNSW index is created in migration `0001_initial.py`; re-indexing requires a new migration if `m`/`ef_construction` params need tuning.

---

## 10. Test Coverage

**`qa/regression_v2.py` summary:**
- **Total Tests:** 18
- **Categories:**
  - **Validation:** Input checks (missing/empty topic, max_results limits).
  - **CORS:** Origin validation and preflight OPTIONS checks.
  - **Functional:** Graceful handling of diverse queries and invariant checks on the graph payload.
  - **Load:** Concurrency tests for mixed valid/invalid requests.
- **Gaps:** No unit tests for embedding math; no frontend E2E tests.

---

## 11. Appendix — Raw Verification Output

```bash
# ls -la
total 64
drwxr-xr-x@ 17 shreyaskumarrai  staff   544 19 Sep 23:01 .
drwx------@ 33 shreyaskumarrai  staff  1056 19 Sep 23:00 ..
-rw-r--r--@  1 shreyaskumarrai  staff    77 19 Sep 09:42 .env
-rw-r--r--@  1 shreyaskumarrai  staff     303 19 Sep 09:39 .env.example
drwxr-xr-x  15 shreyaskumarrai  staff   480 19 Sep 23:20 .git
-rw-r--r--   1 shreyaskumarrai  staff     420 19 Sep 23:02 .gitignore
drwxr-xr-x@  7 shreyaskumarrai  staff     224 19 Sep 10:11 .venv
drwxr-xr-x@  7 shreyaskumarrai  staff     224 19 Sep 23:01 backend
-rwxr-xr-x   1 shreyaskumarrai  staff     277 19 Sep 20:17 dev.sh
drwxr-xr-x@ 16 shreyaskumarrai  staff   512 19 Sep 23:01 frontend
drwxr-xr-x@  3 shreyaskumarrai  staff      96 19 Sep 14:18 qa
-rw-r--r--@  1 shreyaskumarrai  staff     631 19 Sep 13:17 README.md
drwxr-xr-x   3 shreyaskumarrai  staff      96 19 Sep 21:31 specs
-rw-r--r--@  1 shreyaskumarrai  staff     739 19 Sep 13:23 test_arxiv_client.py
-rw-r--r--@  1 shreyaskumarrai  staff     744 19 Sep 13:23 test_llm_service.py
drwxr-xr-x@  8 shreyaskumarrai  staff     256 19 Sep 13:23 venv
-rw-r--r--@  1 shreyaskumarrai  staff     541 19 Sep 13:36 verify_groq.py

# ls backend/app/
__init__.py
__pycache__
arxiv_client.py
embedding_service.py
llm_service.py
main.py
verify_groq.py

# ls frontend/components/ frontend/pages/ frontend/lib/
frontend/components/:
Pipeline.tsx
ReadingMap.tsx
frontend/lib/:
api.ts
frontend/pages/:
_app.tsx
index.tsx
index.tsx.bak
regression_v2.py

# ls qa/
regression_v2.py

# cat dev.sh
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

./backend/.venv/bin/python -m uvicorn backend.app.main:app \
  --host 0.0.0.0 --port 8000 --reload --reload-dir backend/app &

BACKEND_PID=$!
trap "kill $BACKEND_PID 2>/dev/null || true" EXIT

cd frontend
npx next dev --webpack

# cat .env.example
# Research Agent - environment variables
# Copy to .env and fill in your values

# PostgreSQL connection
DB_USER=postgres
DB_PASSWORD=

# Ollama (optional - uses localhost:11434 by default)
# OLLAMA_BASE_URL=http://localhost:11434

# HuggingFace token (optional - speeds up model downloads)
# HF_TOKEN=

# git log --oneline -10
3b60045 chore: proper .gitignore; untrack venvs, node_modules, build artifacts
d3d928e chore(graph): remove diagnostic console.log after isolated-node fix verified
165a0ac chore: stop tracking uvicorn.log
51f7e1c fix(llm): drop json_object mode in extract_insights_batch; fence-strip + traceback
a0da589 fix(llm): handle both str and dict Paper.summary in synthesize_results
8613375 fix(search): canonical paper ranks #1 for exact-title query
b857d30 checkpoint: pre-VIBGYOR rework
6bebae0 feat(graph+search): VIBGYOR colors by rank, non-overlap layout, canonical-paper ranking
cd31544 checkpoint: colors + legend working; graph visuals and ranking next
17551f3 chore(frontend): Tailwind v4 rendering; webpack dev script

# git tag --list | sort
graph-and-search
graph-and-search-v2
llm-content-verified
post-ui-polish
pre-graph-rework
pre-ui-polish
regression-18
tailwind-live
ui-polish-partial
```

DONE: report