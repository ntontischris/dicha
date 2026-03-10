-- =====================================================================
-- Migration: Search Quality Improvements
--
-- Safe to run multiple times (idempotent).
-- Run in Supabase SQL Editor after deploying code changes.
-- =====================================================================

-- 1. Replace (project_id, scope) index with (project_id, scope, type)
--    The hybrid_search eligible CTE filters on all three columns.
DROP INDEX IF EXISTS documents_project_scope_idx;
DROP INDEX IF EXISTS documents_project_scope_type_idx;
CREATE INDEX documents_project_scope_type_idx ON documents(project_id, scope, type);

-- 2. Partial index for is_parent = false queries
--    Every hybrid_search and search_by_hook filters is_parent = false.
DROP INDEX IF EXISTS documents_search_eligible_idx;
CREATE INDEX documents_search_eligible_idx
  ON documents(project_id, type, category)
  WHERE is_parent = false;

-- 3. Drop legacy match_documents function (dead code — tools.py uses hybrid_search)
DROP FUNCTION IF EXISTS match_documents CASCADE;

-- Verify indexes
SELECT indexname FROM pg_indexes WHERE tablename = 'documents' ORDER BY indexname;
