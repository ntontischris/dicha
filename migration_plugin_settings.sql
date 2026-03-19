-- =====================================================================
-- Migration: Plugin Settings table
--
-- Stores per-plugin configuration/settings for each project.
-- Backward compatible — no existing tables are modified.
--
-- Run in Supabase SQL Editor after schema_full.sql
-- =====================================================================


-- ═════════════════════════════════════════════════════════════════════
-- 1. New table: plugin_settings
-- ═════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS plugin_settings (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_id  text NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  plugin_slug text NOT NULL,
  plugin_name text DEFAULT '',
  plugin_file text DEFAULT '',
  settings    jsonb DEFAULT '{}',
  synced_at   timestamptz DEFAULT now(),
  UNIQUE (project_id, plugin_slug)
);

CREATE INDEX IF NOT EXISTS plugin_settings_project_idx ON plugin_settings(project_id);

ALTER TABLE plugin_settings ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access" ON plugin_settings
  FOR ALL USING (true) WITH CHECK (true);


-- ═════════════════════════════════════════════════════════════════════
-- 2. Update clear_project_data — add plugin_settings cleanup
-- ═════════════════════════════════════════════════════════════════════

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


-- ═════════════════════════════════════════════════════════════════════
-- 3. Update get_project_context — add plugin_settings column
-- ═════════════════════════════════════════════════════════════════════

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
-- 4. Verify
-- ═════════════════════════════════════════════════════════════════════

SELECT 'plugin_settings table created' AS status
WHERE EXISTS (
  SELECT 1 FROM information_schema.tables
  WHERE table_schema = 'public' AND table_name = 'plugin_settings'
);
