# Batch 1 Report — HTTP & Routing

## Summary
12 principles checked against backend/app/main.py. Result: 8 [OK], 1 [FRAMEWORK], 3 [N/A], 0 [PARTIAL], 0 [MISSING] after fixes. Two genuine gaps (catch-all 404, cache-control) were identified and fixed during this batch. Runtime verification confirmed /search registers before the catch-all.

## Verdict Counts
- [OK]: 8
- [PARTIAL]: 0
- [MISSING]: 0
- [FRAMEWORK]: 1
- [N/A]: 3

## Code Changes Made During Batch 1
1. Added `@app.middleware("http") add_cache_control` — sets Cache-Control: no-store, scoped to skip /docs, /redoc, /openapi.
2. Added `@app.exception_handler(RequestValidationError)` — returns 400 instead of FastAPI's default 422.
3. Replaced `@app.exception_handler(404)` with `@app.api_route("/{full_path:path}")` — preserves search's own 404 messages while giving unmatched routes a friendly JSON response.

## Framework-Handled (no action needed)
- OPTIONS preflight (B1.7) — Starlette CORSMiddleware

## Not Applicable to This Project
- B1.4 Idempotency — read-only endpoint
- B1.9 Dynamic routes — single-endpoint API
- B1.10 Query parameters — search uses JSON body

## Accepted Trade-offs
- GET on a POST-only path now returns 404 instead of 405. Minor REST purity cost; acceptable for a single-endpoint internal API.

## Verification
- Syntax: `ast.parse` passed
- Runtime: route registration order confirmed (search before catch-all)
- Frontend: no 422/400 status checks found; the 400 change is backward-compatible

## Confidence
High. Two clean audit rounds; runtime verification passed; frontend contract unaffected.
