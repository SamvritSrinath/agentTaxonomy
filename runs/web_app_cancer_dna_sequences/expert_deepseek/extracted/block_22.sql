-- database/migrations/001_initial.sql
CREATE TABLE tenants (
    id UUID PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    plan VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE users (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    email VARCHAR(255) UNIQUE,
    roles TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW()
);
