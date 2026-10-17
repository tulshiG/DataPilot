-- DataPilot AI v2 — Phase 2 Database Migration
-- Run this against your PostgreSQL database to create the semantic layer tables.

-- Table: semantic_metrics
CREATE TABLE IF NOT EXISTS semantic_metrics (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    dataset_id INTEGER REFERENCES datasets(id),

    name VARCHAR(200) NOT NULL,
    key VARCHAR(100) NOT NULL,
    description TEXT,

    expression TEXT NOT NULL,
    aggregation VARCHAR(30),
    table_name VARCHAR(200) NOT NULL,
    column_name VARCHAR(200),

    data_type VARCHAR(30) DEFAULT 'numeric',
    format_pattern VARCHAR(50),
    unit VARCHAR(50),

    default_dimensions JSONB,
    time_dimension VARCHAR(200),
    synonyms JSONB,

    is_auto BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,
    confidence FLOAT DEFAULT 0.8,

    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_semantic_metrics_workspace ON semantic_metrics(workspace_id);
CREATE INDEX IF NOT EXISTS idx_semantic_metrics_key ON semantic_metrics(key);

-- Table: semantic_dimensions
CREATE TABLE IF NOT EXISTS semantic_dimensions (
    id SERIAL PRIMARY KEY,
    workspace_id INTEGER NOT NULL REFERENCES workspaces(id),
    dataset_id INTEGER REFERENCES datasets(id),

    name VARCHAR(200) NOT NULL,
    key VARCHAR(100) NOT NULL,
    description TEXT,

    table_name VARCHAR(200) NOT NULL,
    column_name VARCHAR(200) NOT NULL,

    distinct_count INTEGER,
    sample_values JSONB,
    synonyms JSONB,

    parent_dimension_key VARCHAR(100),

    is_auto BOOLEAN DEFAULT TRUE,
    is_active BOOLEAN DEFAULT TRUE,

    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_semantic_dimensions_workspace ON semantic_dimensions(workspace_id);
CREATE INDEX IF NOT EXISTS idx_semantic_dimensions_key ON semantic_dimensions(key);
