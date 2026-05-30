-- Run this once in the Supabase SQL editor before deploying.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS memories (
    id           TEXT PRIMARY KEY,
    user_id      TEXT DEFAULT 'default',
    content      TEXT NOT NULL,
    type         TEXT DEFAULT 'fact',
    tags         JSONB DEFAULT '[]',
    category     TEXT DEFAULT 'general',
    mood         TEXT,
    emotion_tags JSONB DEFAULT '[]',
    importance   INTEGER DEFAULT 5,
    source       TEXT DEFAULT 'unknown',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS goals (
    id          TEXT PRIMARY KEY,
    user_id     TEXT DEFAULT 'default',
    title       TEXT NOT NULL,
    category    TEXT NOT NULL,
    progress    INTEGER DEFAULT 0,
    milestones  JSONB DEFAULT '[]',
    deadline    TEXT,
    status      TEXT DEFAULT 'active',
    notes       TEXT,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id               TEXT PRIMARY KEY,
    user_id          TEXT DEFAULT 'default',
    title            TEXT NOT NULL,
    category         TEXT NOT NULL,
    event_date       TEXT NOT NULL,
    people_involved  JSONB DEFAULT '[]',
    outcome          TEXT,
    follow_up_sent   INTEGER DEFAULT 0,
    notes            TEXT,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS financial_facts (
    id               TEXT PRIMARY KEY,
    user_id          TEXT DEFAULT 'default',
    type             TEXT NOT NULL,
    asset            TEXT NOT NULL,
    amount           REAL NOT NULL,
    currency         TEXT DEFAULT 'INR',
    transaction_date TEXT NOT NULL,
    status           TEXT DEFAULT 'active',
    notes            TEXT,
    follow_up_sent   INTEGER DEFAULT 0,
    created_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS skills (
    id             TEXT PRIMARY KEY,
    user_id        TEXT DEFAULT 'default',
    name           TEXT NOT NULL,
    domain         TEXT NOT NULL,
    proficiency    TEXT DEFAULT 'intermediate',
    actively_using INTEGER DEFAULT 1,
    notes          TEXT,
    updated_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS relationships (
    id                TEXT PRIMARY KEY,
    user_id           TEXT DEFAULT 'default',
    name              TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    notes             TEXT,
    last_mentioned    TEXT NOT NULL,
    created_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS delegated_tasks (
    id            TEXT PRIMARY KEY,
    user_id       TEXT DEFAULT 'default',
    description   TEXT NOT NULL,
    category      TEXT NOT NULL,
    source        TEXT DEFAULT 'unknown',
    status        TEXT DEFAULT 'active',
    check_in_date TEXT,
    outcome       TEXT,
    created_at    TEXT NOT NULL,
    updated_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS followups (
    id                 TEXT PRIMARY KEY,
    user_id            TEXT DEFAULT 'default',
    question           TEXT NOT NULL,
    source_entity_type TEXT NOT NULL,
    source_entity_id   TEXT NOT NULL,
    status             TEXT DEFAULT 'pending',
    answer             TEXT,
    created_at         TEXT NOT NULL,
    answered_at        TEXT
);

CREATE TABLE IF NOT EXISTS user_profile (
    user_id TEXT NOT NULL DEFAULT 'default',
    key     TEXT NOT NULL,
    value   TEXT NOT NULL,
    PRIMARY KEY (user_id, key)
);

CREATE TABLE IF NOT EXISTS memory_embeddings (
    id        TEXT PRIMARY KEY,
    user_id   TEXT DEFAULT 'default',
    embedding vector(768),
    content   TEXT,
    metadata  JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_memories_user ON memories (user_id);
CREATE INDEX IF NOT EXISTS idx_goals_user ON goals (user_id);
CREATE INDEX IF NOT EXISTS idx_events_user ON events (user_id);
CREATE INDEX IF NOT EXISTS idx_financial_user ON financial_facts (user_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_user ON memory_embeddings (user_id);
