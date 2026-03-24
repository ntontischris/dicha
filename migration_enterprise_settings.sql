-- Migration: Enterprise Settings Retrieval
-- Run in Supabase SQL Editor

ALTER TABLE payment_gateways
    ADD COLUMN IF NOT EXISTS form_fields_meta jsonb DEFAULT '{}';
