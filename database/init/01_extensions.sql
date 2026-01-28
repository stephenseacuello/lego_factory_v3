-- LEGO Factory v3 - Database Initialization
-- Enable required PostgreSQL extensions

-- TimescaleDB for time-series data
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Full-text search
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Verify extensions
SELECT extname, extversion FROM pg_extension WHERE extname IN ('timescaledb', 'uuid-ossp', 'pg_trgm');
