-- =====================================================================
-- DICHA: Complete Database Schema
--
-- Τρέξε ΟΛΟ αυτό στο Supabase SQL Editor (μία φορά)
-- Αν υπάρχουν ήδη tables τα κάνει DROP και τα ξαναφτιάχνει CLEAN
--
-- ΠΡΟΣΟΧΗ: Αυτό ΣΒΗΝΕΙ τα υπάρχοντα data. Αν θέλεις να κρατήσεις
-- κάτι, κάνε backup πριν τρέξεις.
-- =====================================================================


-- ═════════════════════════════════════════════════════════════════════
-- STEP 0: Extensions
-- ═════════════════════════════════════════════════════════════════════

CREATE EXTENSION IF NOT EXISTS vector;    -- pgvector for embeddings


-- ═════════════════════════════════════════════════════════════════════
-- STEP 1: Drop everything (clean slate)
-- ═════════════════════════════════════════════════════════════════════

DROP TRIGGER IF EXISTS documents_fts_update ON documents;
DROP FUNCTION IF EXISTS documents_fts_trigger CASCADE;
DROP FUNCTION IF EXISTS hybrid_search CASCADE;
DROP FUNCTION IF EXISTS search_by_hook CASCADE;
DROP FUNCTION IF EXISTS clear_project_data CASCADE;
DROP FUNCTION IF EXISTS get_project_context CASCADE;
DROP FUNCTION IF EXISTS match_documents CASCADE;

DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS plugin_settings CASCADE;
DROP TABLE IF EXISTS active_plugins CASCADE;
DROP TABLE IF EXISTS wc_general_settings CASCADE;
DROP TABLE IF EXISTS tax_settings CASCADE;
DROP TABLE IF EXISTS shipping_methods CASCADE;
DROP TABLE IF EXISTS shipping_zones CASCADE;
DROP TABLE IF EXISTS payment_gateways CASCADE;
DROP TABLE IF EXISTS projects CASCADE;


-- ═════════════════════════════════════════════════════════════════════
-- STEP 2: Tables
-- ═════════════════════════════════════════════════════════════════════

-- ── projects ─────────────────────────────────────────────────────────
CREATE TABLE projects (
  project_id          text PRIMARY KEY,
  site_url            text,
  wp_version          text,
  php_version         text,
  wc_version          text,
  wc_active           boolean DEFAULT false,
  theme_name          text,
  theme_version       text,
  is_child_theme      boolean DEFAULT false,
  parent_theme        text,
  active_plugins_count integer DEFAULT 0,
  last_sync           timestamptz DEFAULT now(),
  created_at          timestamptz DEFAULT now()
);


-- ── payment_gateways ─────────────────────────────────────────────────
CREATE TABLE payment_gateways (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_id          text NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  gateway_id          text NOT NULL,
  title               text DEFAULT '',
  method_title        text DEFAULT '',
  enabled             boolean DEFAULT false,
  description         text DEFAULT '',
  supports            jsonb DEFAULT '[]',
  settings            jsonb DEFAULT '{}',
  synced_at           timestamptz DEFAULT now(),
  UNIQUE (project_id, gateway_id)
);


-- ── shipping_zones ───────────────────────────────────────────────────
CREATE TABLE shipping_zones (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_id          text NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  zone_id             integer NOT NULL,
  zone_name           text DEFAULT '',
  locations           text DEFAULT '',
  locations_json      jsonb DEFAULT '[]',
  synced_at           timestamptz DEFAULT now(),
  UNIQUE (project_id, zone_id)
);


-- ── shipping_methods ─────────────────────────────────────────────────
CREATE TABLE shipping_methods (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_id          text NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  zone_id             integer,
  zone_name           text DEFAULT '',
  instance_id         integer,
  method_id           text DEFAULT '',
  method_title        text DEFAULT '',
  enabled             boolean DEFAULT false,
  cost                text,
  tax_status          text DEFAULT 'taxable',
  requires            text,
  min_amount          text,
  class_costs         jsonb,
  no_class_cost       text,
  synced_at           timestamptz DEFAULT now(),
  UNIQUE (project_id, zone_id, instance_id)
);


-- ── tax_settings ─────────────────────────────────────────────────────
CREATE TABLE tax_settings (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_id          text NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  tax_enabled         boolean DEFAULT false,
  prices_include_tax  boolean DEFAULT false,
  tax_based_on        text DEFAULT '',
  tax_display_shop    text DEFAULT '',
  tax_display_cart    text DEFAULT '',
  tax_classes         jsonb DEFAULT '[]',
  tax_rates           jsonb DEFAULT '[]',
  synced_at           timestamptz DEFAULT now(),
  UNIQUE (project_id)
);


-- ── wc_general_settings ──────────────────────────────────────────────
CREATE TABLE wc_general_settings (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_id          text NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  currency            text DEFAULT '',
  currency_position   text DEFAULT '',
  store_country       text DEFAULT '',
  store_city          text DEFAULT '',
  enable_coupons      boolean DEFAULT false,
  enable_guest_checkout boolean DEFAULT false,
  manage_stock        boolean DEFAULT false,
  settings_json       jsonb DEFAULT '{}',
  synced_at           timestamptz DEFAULT now(),
  UNIQUE (project_id)
);


-- ── active_plugins ───────────────────────────────────────────────────
CREATE TABLE active_plugins (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_id          text NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  plugin_name         text DEFAULT '',
  version             text DEFAULT '',
  author              text DEFAULT '',
  description         text DEFAULT '',
  plugin_file         text DEFAULT '',
  synced_at           timestamptz DEFAULT now(),
  UNIQUE (project_id, plugin_file)
);


-- ── plugin_settings ─────────────────────────────────────────────────
CREATE TABLE plugin_settings (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_id  text NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  plugin_slug text NOT NULL,
  plugin_name text DEFAULT '',
  plugin_file text DEFAULT '',
  settings    jsonb DEFAULT '{}',
  synced_at   timestamptz DEFAULT now(),
  UNIQUE (project_id, plugin_slug)
);


-- ── documents (vector search + embeddings) ───────────────────────────
CREATE TABLE documents (
  id                  bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_id          text NOT NULL,
  source_id           text,

  -- Content
  title               text DEFAULT '',
  text                text DEFAULT '',
  type                text DEFAULT '',

  -- Multi-tenant scope
  scope               text NOT NULL DEFAULT 'project',     -- 'project' | 'global'

  -- Categorization
  category            text NOT NULL DEFAULT 'general',
  subcategory         text DEFAULT '',
  language            text DEFAULT '',

  -- Auto-extracted metadata
  hooks               text[] DEFAULT '{}',
  keywords            text[] DEFAULT '{}',
  is_active           boolean DEFAULT true,
  priority            smallint DEFAULT 3,                   -- 1=critical, 2=important, 3=normal

  -- Parent-child chunking
  parent_id           bigint REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index         smallint DEFAULT 0,
  is_parent           boolean DEFAULT false,

  -- Contextual retrieval
  context_text        text DEFAULT '',
  section_path        text DEFAULT '',

  -- Vector embedding
  embedding           vector(1536),

  -- Flexible metadata (extra fields)
  metadata            jsonb DEFAULT '{}',

  -- Timestamps
  synced_at           timestamptz DEFAULT now(),
  created_at          timestamptz DEFAULT now(),

  -- Unique constraint: one source_id per project
  UNIQUE (project_id, source_id)
);

-- Weighted Full-Text Search column (populated by trigger — not GENERATED, because
-- to_tsvector is not IMMUTABLE in PostgreSQL)
-- Weight A (1.0): title + keywords — exact term matches get top score
-- Weight B (0.4): hooks + category — hook name search, category relevance
-- Weight C (0.2): context_text — contextual retrieval summary
-- Weight D (0.1): full text body — broadest but lowest weight
ALTER TABLE documents ADD COLUMN fts tsvector;

-- Trigger function that builds the weighted tsvector on INSERT/UPDATE
CREATE OR REPLACE FUNCTION documents_fts_trigger()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.fts :=
    setweight(to_tsvector('simple', coalesce(NEW.title, '')), 'A') ||
    setweight(to_tsvector('simple', coalesce(array_to_string(NEW.keywords, ' '), '')), 'A') ||
    setweight(to_tsvector('simple', coalesce(array_to_string(NEW.hooks, ' '), '')), 'B') ||
    setweight(to_tsvector('simple', coalesce(NEW.category, '') || ' ' || coalesce(NEW.subcategory, '')), 'B') ||
    setweight(to_tsvector('simple', coalesce(NEW.context_text, '')), 'C') ||
    setweight(to_tsvector('simple', coalesce(NEW.text, '')), 'D');
  RETURN NEW;
END;
$$;

CREATE TRIGGER documents_fts_update
  BEFORE INSERT OR UPDATE ON documents
  FOR EACH ROW
  EXECUTE FUNCTION documents_fts_trigger();


-- ═════════════════════════════════════════════════════════════════════
-- STEP 3: Indexes
-- ═════════════════════════════════════════════════════════════════════

-- Weighted FTS (GIN)
CREATE INDEX documents_fts_idx ON documents USING gin(fts);

-- Vector search (IVFFlat, cosine similarity)
-- NOTE: IVFFlat requires data to build. Run REINDEX after first big data load.
CREATE INDEX documents_embedding_idx
  ON documents USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);

-- Multi-tenant: project + scope (every query uses this)
CREATE INDEX documents_project_scope_idx ON documents(project_id, scope);

-- Category filter
CREATE INDEX documents_category_idx ON documents(category);

-- Hooks array lookup (GIN)
CREATE INDEX documents_hooks_idx ON documents USING gin(hooks);

-- Parent-child lookup
CREATE INDEX documents_parent_idx ON documents(parent_id) WHERE parent_id IS NOT NULL;

-- Source dedup
CREATE INDEX documents_source_idx ON documents(project_id, source_id);

-- Structured tables: project_id indexes (for clear/query)
CREATE INDEX payment_gateways_project_idx ON payment_gateways(project_id);
CREATE INDEX shipping_zones_project_idx ON shipping_zones(project_id);
CREATE INDEX shipping_methods_project_idx ON shipping_methods(project_id);
CREATE INDEX tax_settings_project_idx ON tax_settings(project_id);
CREATE INDEX wc_general_settings_project_idx ON wc_general_settings(project_id);
CREATE INDEX active_plugins_project_idx ON active_plugins(project_id);
CREATE INDEX plugin_settings_project_idx ON plugin_settings(project_id);


-- ═════════════════════════════════════════════════════════════════════
-- STEP 4: RPC Functions
-- ═════════════════════════════════════════════════════════════════════

-- ── hybrid_search ────────────────────────────────────────────────────
-- Vector + Weighted FTS + RRF scoring + priority boost + parent expansion
-- Searches: project's own docs + global docs (company knowledge base)

CREATE OR REPLACE FUNCTION hybrid_search(
  query_text      text,
  query_embedding vector(1536),
  match_count     int,
  p_project_id    text,
  p_category      text DEFAULT NULL,
  rrf_k           int DEFAULT 50,
  p_doc_types     text[] DEFAULT NULL
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
  -- Scope: this project's docs + global docs, optional category + doc_type filter
  -- Exclude parent-only rows (search children, expand to parents)
  eligible AS (
    SELECT d.id
    FROM documents d
    WHERE (d.project_id = p_project_id OR d.scope = 'global')
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

  -- Top results with parent deduplication:
  -- If multiple children share the same parent, keep only the best scorer
  -- This prevents flooding the agent with repeated parent context
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

  -- Return child text with context — no parent text replacement
  -- The child's context_text (from contextual retrieval) already provides
  -- document-level context. Returning child text keeps results specific.
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


-- ── search_by_hook ──────────────────────────────────────────────────
-- Direct hook lookup using GIN index on hooks[] array

CREATE OR REPLACE FUNCTION search_by_hook(
  p_hook_name  text,
  p_project_id text,
  match_count  int DEFAULT 10
)
RETURNS TABLE (
  id        bigint,
  title     text,
  body      text,
  doc_type  text,
  hooks     text[],
  is_active boolean,
  metadata  jsonb
)
LANGUAGE sql
AS $$
  SELECT
    d.id,
    d.title,
    d.text AS body,
    d.type AS doc_type,
    d.hooks,
    d.is_active,
    d.metadata
  FROM documents d
  WHERE (d.project_id = p_project_id OR d.scope = 'global')
    AND p_hook_name = ANY(d.hooks)
    AND d.is_parent = false
  ORDER BY d.is_active DESC, d.priority ASC
  LIMIT match_count;
$$;


-- ── match_documents (legacy, used by old tools.py) ───────────────────
-- Kept for backward compatibility. Simple vector search with filter.

CREATE OR REPLACE FUNCTION match_documents(
  query_embedding vector(1536),
  match_count     int,
  filter          jsonb DEFAULT '{}'
)
RETURNS TABLE (
  id         bigint,
  title      text,
  text       text,
  type       text,
  metadata   jsonb,
  similarity float
)
LANGUAGE plpgsql
AS $$
DECLARE
  _project_id text;
BEGIN
  _project_id := filter ->> 'project_id';

  RETURN QUERY
  SELECT
    d.id,
    d.title,
    d.text,
    d.type,
    d.metadata,
    1 - (d.embedding <=> query_embedding) AS similarity
  FROM documents d
  WHERE (_project_id IS NULL OR d.project_id = _project_id)
    AND d.embedding IS NOT NULL
  ORDER BY d.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;


-- ── clear_project_data ──────────────────────────────────────────────
-- Clears ALL data for a project EXCEPT global docs
-- Called by webhook before re-sync

CREATE OR REPLACE FUNCTION clear_project_data(p_project_id text)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  -- Vector documents (only project-scoped, NEVER global)
  DELETE FROM documents        WHERE project_id = p_project_id AND scope = 'project';

  -- Structured tables
  DELETE FROM plugin_settings  WHERE project_id = p_project_id;
  DELETE FROM active_plugins   WHERE project_id = p_project_id;
  DELETE FROM wc_general_settings WHERE project_id = p_project_id;
  DELETE FROM tax_settings     WHERE project_id = p_project_id;
  DELETE FROM shipping_methods WHERE project_id = p_project_id;
  DELETE FROM shipping_zones   WHERE project_id = p_project_id;
  DELETE FROM payment_gateways WHERE project_id = p_project_id;

  -- Projects: DON'T delete — upsert keeps history
END;
$$;


-- ── get_project_context ─────────────────────────────────────────────
-- Returns all structured data for a project in one aggregated JSON

CREATE OR REPLACE FUNCTION get_project_context(p_project_id text)
RETURNS TABLE (
  project          jsonb,
  payment_gateways jsonb,
  shipping_zones   jsonb,
  shipping_methods jsonb,
  tax_settings     jsonb,
  wc_general_settings jsonb,
  active_plugins   jsonb,
  plugin_settings  jsonb
)
LANGUAGE sql
AS $$
  SELECT
    -- Project info
    (SELECT to_jsonb(p.*) FROM projects p WHERE p.project_id = p_project_id),

    -- Payment gateways
    COALESCE(
      (SELECT jsonb_agg(to_jsonb(pg.*)) FROM payment_gateways pg WHERE pg.project_id = p_project_id),
      '[]'::jsonb
    ),

    -- Shipping zones
    COALESCE(
      (SELECT jsonb_agg(to_jsonb(sz.*)) FROM shipping_zones sz WHERE sz.project_id = p_project_id),
      '[]'::jsonb
    ),

    -- Shipping methods
    COALESCE(
      (SELECT jsonb_agg(to_jsonb(sm.*)) FROM shipping_methods sm WHERE sm.project_id = p_project_id),
      '[]'::jsonb
    ),

    -- Tax settings
    (SELECT to_jsonb(ts.*) FROM tax_settings ts WHERE ts.project_id = p_project_id),

    -- General settings
    (SELECT to_jsonb(gs.*) FROM wc_general_settings gs WHERE gs.project_id = p_project_id),

    -- Active plugins
    COALESCE(
      (SELECT jsonb_agg(to_jsonb(ap.*)) FROM active_plugins ap WHERE ap.project_id = p_project_id),
      '[]'::jsonb
    ),

    -- Plugin settings
    COALESCE(
      (SELECT jsonb_agg(to_jsonb(ps.*)) FROM plugin_settings ps WHERE ps.project_id = p_project_id),
      '[]'::jsonb
    );
$$;


-- ═════════════════════════════════════════════════════════════════════
-- STEP 5: RLS (Row Level Security) — Optional but recommended
-- ═════════════════════════════════════════════════════════════════════

-- Enable RLS on all tables
ALTER TABLE projects            ENABLE ROW LEVEL SECURITY;
ALTER TABLE payment_gateways    ENABLE ROW LEVEL SECURITY;
ALTER TABLE shipping_zones      ENABLE ROW LEVEL SECURITY;
ALTER TABLE shipping_methods    ENABLE ROW LEVEL SECURITY;
ALTER TABLE tax_settings        ENABLE ROW LEVEL SECURITY;
ALTER TABLE wc_general_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE active_plugins      ENABLE ROW LEVEL SECURITY;
ALTER TABLE plugin_settings     ENABLE ROW LEVEL SECURITY;
ALTER TABLE documents           ENABLE ROW LEVEL SECURITY;

-- Service role can do everything (webhook uses service_role key)
CREATE POLICY "Service role full access" ON projects            FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON payment_gateways    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON shipping_zones      FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON shipping_methods    FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON tax_settings        FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON wc_general_settings FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON active_plugins      FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON plugin_settings     FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access" ON documents           FOR ALL USING (true) WITH CHECK (true);


-- ═════════════════════════════════════════════════════════════════════
-- STEP 6: Verify
-- ═════════════════════════════════════════════════════════════════════

-- List all tables
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;

-- List all functions
SELECT routine_name, routine_type
FROM information_schema.routines
WHERE routine_schema = 'public'
  AND routine_name IN ('hybrid_search', 'search_by_hook', 'clear_project_data', 'get_project_context')
ORDER BY routine_name;

-- Count indexes on documents
SELECT indexname
FROM pg_indexes
WHERE tablename = 'documents'
ORDER BY indexname;
