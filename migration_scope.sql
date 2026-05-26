-- Migration: Add p_scope parameter to hybrid_search
-- Run this in Supabase SQL Editor
-- Safe to run multiple times (CREATE OR REPLACE)

CREATE OR REPLACE FUNCTION hybrid_search(
  query_text      text,
  query_embedding vector(1536),
  match_count     int,
  p_project_id    text,
  p_category      text DEFAULT NULL,
  rrf_k           int DEFAULT 50,
  p_doc_types     text[] DEFAULT NULL,
  p_scope         text DEFAULT 'project_and_plugins'
)
RETURNS TABLE (
  id           bigint,
  title        text,
  body         text,
  doc_type     text,
  category     text,
  scope        text,
  section_path text,
  context_text text,
  is_active    boolean,
  hooks        text[],
  metadata     jsonb,
  score        float
)
LANGUAGE sql
AS $$
  WITH
  -- Scope filter:
  --   'project'              = only this shop's docs
  --   'project_and_plugins'  = shop docs + ALL global docs (default)
  --   'all'                  = shop docs + ALL global docs (alias)
  -- Note: 'project_and_plugins' used to filter to category='plugin_docs' only,
  -- which hid every admin-uploaded global doc that wasn't tagged that way.
  -- Now any scope='global' row is visible — owners can upload manuals under
  -- any category and the agent will still find them.
  eligible AS (
    SELECT d.id
    FROM documents d
    WHERE (
      CASE p_scope
        WHEN 'project' THEN
          d.project_id = p_project_id
        ELSE
          d.project_id = p_project_id OR d.scope = 'global'
      END
    )
      AND (p_category IS NULL OR d.category = p_category)
      AND (p_doc_types IS NULL OR d.type = ANY(p_doc_types))
      AND (d.is_parent = false)
  ),

  -- Vector search: semantic similarity (cosine distance)
  vector_ranked AS (
    SELECT d.id,
      ROW_NUMBER() OVER (ORDER BY d.embedding <=> query_embedding) AS rank
    FROM documents d
    INNER JOIN eligible e ON e.id = d.id
    WHERE d.embedding IS NOT NULL
    LIMIT match_count * 4
  ),

  -- FTS: weighted keyword matching
  fts_ranked AS (
    SELECT d.id,
      ROW_NUMBER() OVER (
        ORDER BY ts_rank_cd('{0.1, 0.2, 0.4, 1.0}', d.fts,
          websearch_to_tsquery('simple', query_text)) DESC
      ) AS rank
    FROM documents d
    INNER JOIN eligible e ON e.id = d.id
    WHERE d.fts @@ websearch_to_tsquery('simple', query_text)
    LIMIT match_count * 4
  ),

  -- RRF combination with priority boost
  combined AS (
    SELECT
      COALESCE(v.id, f.id) AS doc_id,
      COALESCE(1.0 / (rrf_k + v.rank), 0.0)
        + COALESCE(1.0 / (rrf_k + f.rank), 0.0)
        + CASE d.priority
            WHEN 1 THEN 0.020
            WHEN 2 THEN 0.010
            ELSE 0.0
          END
        + CASE WHEN d.is_active = true THEN 0.005 ELSE 0.0 END
        AS rrf_score
    FROM vector_ranked v
    FULL OUTER JOIN fts_ranked f ON v.id = f.id
    JOIN documents d ON d.id = COALESCE(v.id, f.id)
  ),

  -- Top results with parent deduplication
  top_results AS (
    SELECT doc_id, rrf_score
    FROM (
      SELECT
        doc_id,
        rrf_score,
        ROW_NUMBER() OVER (
          PARTITION BY COALESCE(d.parent_id, d.id)
          ORDER BY rrf_score DESC
        ) AS parent_rank
      FROM combined c
      JOIN documents d ON d.id = c.doc_id
    ) ranked
    WHERE parent_rank = 1
    ORDER BY rrf_score DESC
    LIMIT match_count
  )

  SELECT
    d.id,
    d.title,
    d.text AS body,
    d.type AS doc_type,
    d.category,
    d.scope,
    d.section_path,
    d.context_text,
    d.is_active,
    d.hooks,
    d.metadata,
    t.rrf_score AS score
  FROM top_results t
  JOIN documents d ON d.id = t.doc_id
  ORDER BY t.rrf_score DESC;
$$;
