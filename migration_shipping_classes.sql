-- ═══════════════════════════════════════════════════════════════════
-- Migration: persist shipping classes (previously collected but DROPPED)
-- The WP plugin already sends woocommerce.shipping_classes on every sync,
-- but the backend ignored them. This stores them so the agent can use each
-- shop's REAL class slugs/IDs instead of inventing them.
--
-- Run ONCE in the Supabase SQL Editor. Additive + safe (no data loss).
-- After running it, trigger a fresh sync from WP so the table populates.
-- ═══════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS shipping_classes (
  id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  project_id  text NOT NULL REFERENCES projects(project_id) ON DELETE CASCADE,
  term_id     integer,
  name        text DEFAULT '',
  slug        text DEFAULT '',
  description text DEFAULT '',
  count       integer DEFAULT 0,
  synced_at   timestamptz DEFAULT now(),
  UNIQUE (project_id, slug)
);

CREATE INDEX IF NOT EXISTS idx_shipping_classes_project ON shipping_classes(project_id);

-- clear_project_data runs before every re-sync; it must also clear this table.
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
  DELETE FROM shipping_classes WHERE project_id = p_project_id;
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
