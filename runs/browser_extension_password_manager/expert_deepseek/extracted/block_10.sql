CREATE TABLE users (
  id UUID PRIMARY KEY,
  federated_id TEXT UNIQUE,        -- from OAuth provider
  provider TEXT,
  email TEXT,
  salt BYTEA,
  wrapped_master_key BYTEA,        -- encrypted with recovery key
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE webauthn_credentials (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  credential_id TEXT UNIQUE,
  public_key TEXT,
  sign_count INTEGER DEFAULT 0,
  transports TEXT[],
  aaguid TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE vault_metadata (
  user_id UUID PRIMARY KEY REFERENCES users(id),
  version_vector JSONB,            -- for conflict resolution
  last_updated TIMESTAMPTZ
);

CREATE TABLE audit_log (
  id BIGSERIAL PRIMARY KEY,
  user_id UUID REFERENCES users(id),
  event TEXT,
  ip INET,
  user_agent TEXT,
  timestamp TIMESTAMPTZ DEFAULT now(),
  details JSONB
);
