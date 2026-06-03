CREATE TABLE file_versions (
    id SERIAL PRIMARY KEY,
    tenant VARCHAR(255) NOT NULL,
    filename VARCHAR(512) NOT NULL,
    sha256 CHAR(64) NOT NULL,
    object_key TEXT NOT NULL,
    index_key TEXT,
    file_size BIGINT,
    uploaded_by VARCHAR(255),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tenant, filename, sha256)
);

CREATE TABLE dataset_versions (
    dataset_id UUID PRIMARY KEY,
    tenant VARCHAR(255) NOT NULL,
    name VARCHAR(255),
    version INT,
    parent_version INT,
    metadata JSONB,
    created_at TIMESTAMPTZ
);
