-- JokeAI Database Schema
-- PostgreSQL + pgvector extension
-- Run: psql -d jokeai -f schema.sql

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";

-- ─── USERS & AUTH ─────────────────────────────────────────────────────────────

CREATE TABLE users (
  id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  email         TEXT UNIQUE NOT NULL,
  password_hash TEXT,                          -- NULL for OAuth users
  provider      TEXT DEFAULT 'email',          -- 'email' | 'google' | 'apple'
  provider_id   TEXT,                          -- OAuth provider sub/id
  age_verified  BOOLEAN NOT NULL DEFAULT FALSE,
  accepted_tos  BOOLEAN NOT NULL DEFAULT FALSE,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  last_login_at TIMESTAMPTZ
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_provider ON users(provider, provider_id);

-- ─── PROFILES ─────────────────────────────────────────────────────────────────

CREATE TABLE profiles (
  user_id              UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  username             TEXT UNIQUE NOT NULL,
  original_photo_url   TEXT,
  cartoon_photo_url    TEXT,
  active_avatar_type   TEXT NOT NULL DEFAULT 'original' CHECK (active_avatar_type IN ('original','cartoon')),
  bio                  TEXT,
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── HUMOR PREFERENCES ────────────────────────────────────────────────────────

CREATE TABLE humor_preferences (
  user_id         UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  humor_types     TEXT[]    NOT NULL DEFAULT ARRAY['dad jokes'],
  intensity       SMALLINT  NOT NULL DEFAULT 3 CHECK (intensity BETWEEN 1 AND 5),
  language        TEXT      NOT NULL DEFAULT 'en' CHECK (language IN ('en','he')),
  safe_mode       BOOLEAN   NOT NULL DEFAULT TRUE,
  sexual_content  BOOLEAN   NOT NULL DEFAULT FALSE,
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── JOKES ────────────────────────────────────────────────────────────────────

CREATE TABLE jokes (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  text        TEXT NOT NULL,
  category    TEXT NOT NULL,               -- 'dad','tech','relationship','absurd','dark','work','roast','meme'
  language    TEXT NOT NULL DEFAULT 'en',
  intensity   SMALLINT NOT NULL DEFAULT 3,
  safe        BOOLEAN NOT NULL DEFAULT TRUE,
  sexual      BOOLEAN NOT NULL DEFAULT FALSE,
  source      TEXT NOT NULL DEFAULT 'ai',  -- 'ai' | 'batch' | 'cached'
  score       INT NOT NULL DEFAULT 0,      -- likes*3 + shares*5 - dislikes*2
  embedding   vector(1536),               -- OpenAI ada-002 / Claude embedding
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_jokes_category ON jokes(category);
CREATE INDEX idx_jokes_language ON jokes(language);
CREATE INDEX idx_jokes_safe ON jokes(safe, sexual);
CREATE INDEX idx_jokes_score ON jokes(score DESC);
CREATE INDEX idx_jokes_embedding ON jokes USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ─── JOKE RATINGS ─────────────────────────────────────────────────────────────

CREATE TABLE joke_ratings (
  id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  joke_id    UUID NOT NULL REFERENCES jokes(id) ON DELETE CASCADE,
  rating     TEXT NOT NULL CHECK (rating IN ('like','dislike','favorite')),
  shared     BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE(user_id, joke_id)
);

CREATE INDEX idx_ratings_user ON joke_ratings(user_id);
CREATE INDEX idx_ratings_joke ON joke_ratings(joke_id);

-- ─── JOKE HISTORY ─────────────────────────────────────────────────────────────

CREATE TABLE joke_history (
  id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  joke_id    UUID NOT NULL REFERENCES jokes(id) ON DELETE CASCADE,
  viewed_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_history_user ON joke_history(user_id, viewed_at DESC);

-- ─── MEME TEMPLATES ───────────────────────────────────────────────────────────

CREATE TABLE meme_templates (
  id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  name           TEXT NOT NULL,
  image_url      TEXT NOT NULL,
  category       TEXT NOT NULL,
  top_text_pos   JSONB NOT NULL DEFAULT '{"x":50,"y":10,"maxWidth":80}',
  bottom_text_pos JSONB NOT NULL DEFAULT '{"x":50,"y":90,"maxWidth":80}',
  active         BOOLEAN NOT NULL DEFAULT TRUE,
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── MEMES ────────────────────────────────────────────────────────────────────

CREATE TABLE memes (
  id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  joke_id     UUID REFERENCES jokes(id),
  template_id UUID REFERENCES meme_templates(id),
  image_url   TEXT NOT NULL,
  share_count INT NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_memes_user ON memes(user_id, created_at DESC);

-- ─── JOKE BATTLES ─────────────────────────────────────────────────────────────

CREATE TABLE joke_battles (
  id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  challenger_id UUID NOT NULL REFERENCES users(id),
  opponent_id   UUID REFERENCES users(id),
  joke_a_id    UUID NOT NULL REFERENCES jokes(id),
  joke_b_id    UUID REFERENCES jokes(id),
  votes_a      INT NOT NULL DEFAULT 0,
  votes_b      INT NOT NULL DEFAULT 0,
  status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','active','ended')),
  share_token  TEXT UNIQUE NOT NULL DEFAULT encode(gen_random_bytes(8),'hex'),
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  ends_at      TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '24 hours'
);

CREATE INDEX idx_battles_token ON joke_battles(share_token);

-- ─── BATTLE VOTES ─────────────────────────────────────────────────────────────

CREATE TABLE battle_votes (
  id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  battle_id  UUID NOT NULL REFERENCES joke_battles(id),
  voter_id   UUID REFERENCES users(id),
  voted_for  TEXT NOT NULL CHECK (voted_for IN ('a','b')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─── METRICS ──────────────────────────────────────────────────────────────────

CREATE TABLE daily_metrics (
  date                DATE PRIMARY KEY DEFAULT CURRENT_DATE,
  jokes_generated     INT NOT NULL DEFAULT 0,
  likes_total         INT NOT NULL DEFAULT 0,
  shares_total        INT NOT NULL DEFAULT 0,
  dau                 INT NOT NULL DEFAULT 0,
  memes_shared        INT NOT NULL DEFAULT 0,
  battles_started     INT NOT NULL DEFAULT 0,
  ai_calls            INT NOT NULL DEFAULT 0,
  cache_hits          INT NOT NULL DEFAULT 0
);

-- ─── SCORE UPDATE FUNCTION ────────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION update_joke_score()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE jokes SET score = (
    SELECT COALESCE(SUM(CASE rating WHEN 'like' THEN 3 WHEN 'favorite' THEN 4 WHEN 'dislike' THEN -2 ELSE 0 END), 0)
         + COALESCE(SUM(CASE WHEN shared THEN 5 ELSE 0 END), 0)
    FROM joke_ratings WHERE joke_id = NEW.joke_id
  ) WHERE id = NEW.joke_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_score
AFTER INSERT OR UPDATE ON joke_ratings
FOR EACH ROW EXECUTE FUNCTION update_joke_score();
