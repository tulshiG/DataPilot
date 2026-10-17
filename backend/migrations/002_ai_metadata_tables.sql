-- DataPilot AI v2 — Database Migration
-- Run this against your PostgreSQL database to create the metadata tables.
-- These tables are used by the Metadata Layer (registry.py) to store
-- structured column-level and table-level metadata for the AI engine.

-- Table: column_metadata
CREATE TABLE IF NOT EXISTS column_metadata (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    dataset_id INTEGER NOT NULL REFERENCES datasets(id),
    table_name VARCHAR(200) NOT NULL,
    column_name VARCHAR(200) NOT NULL,

    -- Data classification
    data_type VARCHAR(50),
    semantic_type VARCHAR(50),
    is_metric BOOLEAN DEFAULT FALSE,
    is_dimension BOOLEAN DEFAULT FALSE,
    is_identifier BOOLEAN DEFAULT FALSE,
    is_temporal BOOLEAN DEFAULT FALSE,

    -- Column statistics
    distinct_count INTEGER,
    null_percentage FLOAT,
    min_value VARCHAR(200),
    max_value VARCHAR(200),
    mean_value FLOAT,
    sample_values JSONB,

    -- Human-readable context
    description TEXT,
    synonyms JSONB,

    -- Quality
    quality_score FLOAT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_column_metadata_workspace ON column_metadata(workspace_id);
CREATE INDEX IF NOT EXISTS idx_column_metadata_dataset ON column_metadata(dataset_id);
CREATE INDEX IF NOT EXISTS idx_column_metadata_table ON column_metadata(table_name);

-- Table: table_metadata
CREATE TABLE IF NOT EXISTS table_metadata (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    dataset_id INTEGER NOT NULL REFERENCES datasets(id),
    table_name VARCHAR(200) NOT NULL UNIQUE,
    original_filename VARCHAR(300),

    row_count INTEGER,
    column_count INTEGER,
    domain VARCHAR(100),
    description TEXT,
    quality_score FLOAT,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_table_metadata_workspace ON table_metadata(workspace_id);
CREATE INDEX IF NOT EXISTS idx_table_metadata_dataset ON table_metadata(dataset_id);
