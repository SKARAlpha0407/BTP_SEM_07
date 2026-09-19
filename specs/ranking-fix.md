# Ranking Fix Specification and Status

## Task 1: ReadingMap Visual Rework
**Status:** IMPLEMENTED

### Changes
- **Node Size:** Implemented linear interpolation of radius (14px $\rightarrow$ 5px) based on relevance rank.
- **Node Color:** Implemented linear hue interpolation (0° $\rightarrow$ 280°) based on relevance rank (VIBGYOR order).
- **Node Spacing:** Added `d3Force('charge').strength(-600)` and `d3Force('link').distance(180)` to reduce overlap.
- **Legend:** Replaced cluster list with a relevance gradient strip (Red $\rightarrow$ Violet).
- **Edges:** Adjusted `linkColor` and `linkWidth` for better visibility.

---

## Task 2: Canonical Paper Ranking Fix
**Status:** IMPLEMENTED (Logic verified, API delivery blocked by Env)

### Root Cause
The `/search` endpoint pipeline follows: `arxiv_client.search_papers()` $\rightarrow$ `embedding_service.rank_papers()`. While `search_papers` correctly prioritized the canonical paper via title-matching, `rank_papers` performed a semantic re-sort based on abstract embeddings, clobbering the priority order.

### Implementation
Modified `backend/app/embedding_service.py` to introduce a two-tier sort key:
1. **Tier 0 (Priority):** Exact normalized title match with the query.
2. **Tier 1 (Semantic):** Cosine similarity score of the abstract.

The sort key `(is_exact, relevance_score)` ensures that any paper matching the title exactly is pinned to the top, regardless of its semantic embedding score.

### Verification Results
- **Function-level test:** PASS. Calling `rank_papers` directly with "Attention is all you need" correctly returned `1706.03762` at index 0.
- **API-level test:** UNABLE TO VERIFY. The server encountered `[Errno 48] Address already in use` during restart attempts, preventing the latest code from being served via the API.

### Acceptance Criteria Summary
| Criterion | Status | Note |
| :--- | :--- | :--- |
| `npx next build` exits 0 | PASS | |
| `curl localhost:3000` $\rightarrow$ 200 | PASS | |
| 1706.03762 is line 1 | FAIL | Logic correct, API delivery blocked by port conflict |
| Loose query still reranks | PASS | Verified "graph neural networks" still uses semantic ranking |
