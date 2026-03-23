-- Migration: Plugin Settings Collection Enhancement
-- Run in Supabase SQL Editor

-- 1. Shipping methods: add full settings + form_fields columns
ALTER TABLE shipping_methods
    ADD COLUMN IF NOT EXISTS settings jsonb DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS form_fields_meta jsonb DEFAULT '{}';

-- 2. Theme settings: new table
CREATE TABLE IF NOT EXISTS theme_settings (
    project_id text NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
    theme_slug text NOT NULL,
    source text NOT NULL DEFAULT 'customizer',
    settings jsonb DEFAULT '{}',
    synced_at timestamptz DEFAULT now(),
    PRIMARY KEY (project_id, theme_slug)
);

ALTER TABLE theme_settings ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access" ON theme_settings FOR ALL USING (true) WITH CHECK (true);

-- 3. Update clear_project_data to include theme_settings + settings docs
CREATE OR REPLACE FUNCTION clear_project_data(p_project_id text)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
  -- Vector documents (only project-scoped, NEVER global)
  DELETE FROM documents        WHERE project_id = p_project_id AND scope = 'project';
  -- Safety net: explicit settings doc cleanup
  DELETE FROM documents        WHERE project_id = p_project_id AND type = 'plugin_settings_doc';

  -- Structured tables
  DELETE FROM theme_settings   WHERE project_id = p_project_id;
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

-- 4. Update get_project_context to include theme_settings
CREATE OR REPLACE FUNCTION get_project_context(p_project_id text)
RETURNS TABLE (
  project          jsonb,
  payment_gateways jsonb,
  shipping_zones   jsonb,
  shipping_methods jsonb,
  tax_settings     jsonb,
  wc_general_settings jsonb,
  active_plugins   jsonb,
  plugin_settings  jsonb,
  theme_settings   jsonb
)
LANGUAGE sql
AS $$
  SELECT
    (SELECT to_jsonb(p.*) FROM projects p WHERE p.project_id = p_project_id),
    COALESCE(
      (SELECT jsonb_agg(to_jsonb(pg.*)) FROM payment_gateways pg WHERE pg.project_id = p_project_id),
      '[]'::jsonb
    ),
    COALESCE(
      (SELECT jsonb_agg(to_jsonb(sz.*)) FROM shipping_zones sz WHERE sz.project_id = p_project_id),
      '[]'::jsonb
    ),
    COALESCE(
      (SELECT jsonb_agg(to_jsonb(sm.*)) FROM shipping_methods sm WHERE sm.project_id = p_project_id),
      '[]'::jsonb
    ),
    (SELECT to_jsonb(ts.*) FROM tax_settings ts WHERE ts.project_id = p_project_id),
    (SELECT to_jsonb(gs.*) FROM wc_general_settings gs WHERE gs.project_id = p_project_id),
    COALESCE(
      (SELECT jsonb_agg(to_jsonb(ap.*)) FROM active_plugins ap WHERE ap.project_id = p_project_id),
      '[]'::jsonb
    ),
    COALESCE(
      (SELECT jsonb_agg(to_jsonb(ps.*)) FROM plugin_settings ps WHERE ps.project_id = p_project_id),
      '[]'::jsonb
    ),
    COALESCE(
      (SELECT jsonb_agg(to_jsonb(ths.*)) FROM theme_settings ths WHERE ths.project_id = p_project_id),
      '[]'::jsonb
    );
$$;
