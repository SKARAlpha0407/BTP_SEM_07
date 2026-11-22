-- One-off cache cleanup (audit batch 6). Safe to re-run: every step is a no-op
-- once applied. Take a backup first:
--   pg_dump -d research -Fc -f db_backups/research_<date>.dump
-- Run:   psql -d research -v ON_ERROR_STOP=1 -f backend/scripts/cleanup_2026_11.sql
-- The final statement is COMMIT; replace it with ROLLBACK to rehearse.

BEGIN;

SELECT 'before' AS stage,
  (SELECT count(*) FROM papers) AS papers,
  (SELECT count(*) FROM paper_embeddings) AS embeddings,
  (SELECT count(*) FROM paper_insights) AS insights;

-- 1. Old-style arXiv IDs were stored without their archive (hep-th/9804003v2
--    was stored as 9804003v2). Re-key them from arxiv_url, keeping their
--    embeddings and summaries.
CREATE TEMP TABLE rekey ON COMMIT DROP AS
  SELECT arxiv_id AS old_id,
         regexp_replace(arxiv_url, '^.*arxiv\.org/abs/', '') AS new_id
  FROM papers
  WHERE arxiv_url ~ 'arxiv\.org/abs/'
    AND arxiv_id <> regexp_replace(arxiv_url, '^.*arxiv\.org/abs/', '');

SELECT count(*) AS ids_to_rekey FROM rekey;

INSERT INTO papers (arxiv_id, title, abstract, authors, categories, published, arxiv_url, pdf_url, fetched_at)
  SELECT r.new_id, p.title, p.abstract, p.authors, p.categories, p.published, p.arxiv_url, p.pdf_url, p.fetched_at
  FROM papers p JOIN rekey r ON p.arxiv_id = r.old_id
  ON CONFLICT (arxiv_id) DO NOTHING;

UPDATE paper_embeddings e SET arxiv_id = r.new_id
  FROM rekey r
  WHERE e.arxiv_id = r.old_id
    AND NOT EXISTS (SELECT 1 FROM paper_embeddings x WHERE x.arxiv_id = r.new_id);

UPDATE paper_insights i SET arxiv_id = r.new_id
  FROM rekey r
  WHERE i.arxiv_id = r.old_id
    AND NOT EXISTS (SELECT 1 FROM paper_insights x WHERE x.arxiv_id = r.new_id AND x.llm_model = i.llm_model);

DELETE FROM papers p USING rekey r WHERE p.arxiv_id = r.old_id;  -- cascades to anything left behind

-- 2. Several versions of one paper: keep only the highest version.
DELETE FROM papers p
WHERE EXISTS (
  SELECT 1 FROM papers q
  WHERE regexp_replace(q.arxiv_id, 'v[0-9]+$', '') = regexp_replace(p.arxiv_id, 'v[0-9]+$', '')
    AND coalesce(substring(q.arxiv_id FROM 'v([0-9]+)$')::int, 0)
      > coalesce(substring(p.arxiv_id FROM 'v([0-9]+)$')::int, 0)
);

-- 3. Summaries with no content ('Error' after a failed LLM call, or all 'N/A').
--    The backend no longer stores these; old ones are removed so they are refetched.
DELETE FROM paper_insights
WHERE upper(btrim(coalesce(tldr, '')))       IN ('', 'N/A', 'NA', 'ERROR')
  AND upper(btrim(coalesce(problem, '')))    IN ('', 'N/A', 'NA', 'ERROR')
  AND upper(btrim(coalesce(methods, '')))    IN ('', 'N/A', 'NA', 'ERROR')
  AND upper(btrim(coalesce(benchmarks, ''))) IN ('', 'N/A', 'NA', 'ERROR');

SELECT 'after' AS stage,
  (SELECT count(*) FROM papers) AS papers,
  (SELECT count(*) FROM paper_embeddings) AS embeddings,
  (SELECT count(*) FROM paper_insights) AS insights,
  (SELECT count(*) FROM papers WHERE arxiv_id <> regexp_replace(arxiv_url, '^.*arxiv\.org/abs/', '')) AS bad_ids_left,
  (SELECT count(*) FROM (SELECT regexp_replace(arxiv_id, 'v[0-9]+$', '') FROM papers GROUP BY 1 HAVING count(*) > 1) d) AS duplicate_versions_left,
  (SELECT count(*) FROM paper_insights WHERE tldr = 'Error') AS error_rows_left;

COMMIT;
