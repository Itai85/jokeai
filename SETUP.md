# ─── JokeAI Environment Variables ────────────────────────────────────────────
# Copy this to .env and fill in your values

# Server
NODE_ENV=production
PORT=4000

# Frontend (for CORS and share links)
FRONTEND_URL=https://jokeai.vercel.app
APP_URL=https://jokeai.vercel.app

# Database
DATABASE_URL=postgresql://jokeai:STRONG_PASSWORD@localhost:5432/jokeai

# Redis
REDIS_URL=redis://localhost:6379

# JWT
JWT_SECRET=CHANGE_THIS_TO_64_RANDOM_CHARS_MINIMUM

# Anthropic (Claude - for joke generation)
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI (for embeddings + DALL-E cartoon avatars)
OPENAI_API_KEY=sk-...

# S3-compatible storage (use AWS S3, Cloudflare R2, or MinIO)
S3_REGION=us-east-1
S3_ENDPOINT=                    # Leave empty for AWS S3; set for R2/MinIO
S3_BUCKET=jokeai-media
S3_ACCESS_KEY=your_access_key
S3_SECRET_KEY=your_secret_key
S3_PUBLIC_URL=https://cdn.jokeai.com   # Your CDN or bucket public URL

# Google OAuth (optional)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=

---
# docker-compose.yml
version: '3.9'

services:
  postgres:
    image: pgvector/pgvector:pg16
    restart: unless-stopped
    environment:
      POSTGRES_DB: jokeai
      POSTGRES_USER: jokeai
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme}
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./schema.sql:/docker-entrypoint-initdb.d/01-schema.sql
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U jokeai"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --maxmemory 256mb --maxmemory-policy allkeys-lru
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 3s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    env_file: .env
    ports:
      - "4000:4000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

  worker:
    build:
      context: ./backend
      dockerfile: Dockerfile.worker
    restart: unless-stopped
    env_file: .env
    command: ["node", "dist/workers/jokeWorker.js"]
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy

volumes:
  pgdata:

---
# backend/Dockerfile
FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
RUN apk add --no-cache vips-dev
COPY package*.json ./
RUN npm ci --production
COPY --from=builder /app/dist ./dist
EXPOSE 4000
CMD ["node", "dist/index.js"]
