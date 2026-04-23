# JokeAI — Full Stack MVP

AI-powered viral humor app. Personalized jokes, meme generation, friend roasts, photo roasts, and joke battles.

---

## 📁 Project Structure

```
jokeai/
├── schema.sql                  # PostgreSQL schema (run first)
├── SETUP.md                    # Docker compose + env vars
│
├── backend/                    # Node.js / Express API
│   ├── package.json
│   ├── tsconfig.json
│   └── src/
│       ├── index.ts            # App entry point
│       ├── db/pool.ts          # PostgreSQL connection pool
│       ├── middleware/
│       │   ├── auth.ts         # JWT auth middleware
│       │   └── errorHandler.ts # Global error handler
│       ├── routes/
│       │   ├── auth.ts         # Register, login, Google OAuth
│       │   ├── jokes.ts        # Generate, rate, history, prefs
│       │   ├── roast.ts        # Friend roast, photo roast
│       │   ├── meme.ts         # Meme generation + battle routes
│       │   └── profile.ts      # Profile, photo upload, cartoon
│       ├── services/
│       │   ├── jokeAI.ts       # Hybrid AI generation (cache-first)
│       │   └── memeGenerator.ts # Template-based meme rendering
│       ├── utils/
│       │   └── shared.ts       # Redis, logger, error class, S3
│       └── workers/
│           └── jokeWorker.ts   # Bull queues: batch gen + daily jokes
│
└── frontend/                   # Next.js 14 PWA
    ├── package.json
    ├── next.config.js          # PWA config
    ├── tailwind.config.ts
    ├── public/manifest.json    # PWA manifest
    └── app/
        ├── layout.tsx          # Root layout + metadata
        ├── globals.css         # Tailwind + custom styles
        ├── page.tsx            # Main app: jokes, roast, battle tabs
        ├── auth/page.tsx       # Login / register
        ├── preferences/page.tsx # Humor settings onboarding
        ├── profile/page.tsx    # Profile + avatar management
        └── favorites/page.tsx  # Saved favorites
```

---

## 🚀 Quick Start

### 1. Prerequisites
- Node.js 20+
- PostgreSQL 16+ with pgvector extension
- Redis 7+
- Anthropic API key (for joke generation)
- OpenAI API key (for embeddings + DALL-E avatars)
- S3-compatible storage (AWS S3, Cloudflare R2, or MinIO)

### 2. Database Setup
```bash
# Install pgvector
# Ubuntu: apt install postgresql-16-pgvector
# macOS: brew install pgvector

psql -U postgres -c "CREATE DATABASE jokeai;"
psql -U postgres -d jokeai -f schema.sql
```

### 3. Backend Setup
```bash
cd backend
cp .env.example .env        # Fill in your keys
npm install
npm run dev                  # API on :4000
# In another terminal:
npm run worker               # Background job worker
```

### 4. Frontend Setup
```bash
cd frontend
cp .env.local.example .env.local
npm install
npm run dev                  # UI on :3000
```

### 5. Docker (recommended for production)
```bash
cp SETUP.md docker-compose.yml   # Extract the compose config
cp SETUP.md .env                 # Extract the env template, fill values
docker compose up -d
```

---

## 🏗️ Architecture Decisions

### Hybrid Joke Generation (Cost-Optimized)
```
Request → Redis cache check → if hit: serve cached (80% of requests)
       → Embedding similarity search → if match: serve & cache
       → AI generation (Claude) → store + embed + cache
```
**Expected AI usage reduction: ~80%**

### Batch Pre-generation
Every hour, a Bull worker generates 50 jokes across all categories.
New users get instant responses from the pool, not waiting for AI.

### Embedding Search
Every AI-generated joke gets an OpenAI embedding stored in pgvector.
New requests are matched semantically — if prefs match a cached joke, no AI call needed.

### Joke Scoring
```
score = likes×3 + favorites×4 + shares×5 - dislikes×2
```
High-score jokes are served more often. Top jokes are nearly free to distribute.

---

## 🔌 API Reference

### Auth
| Method | Path | Body | Description |
|--------|------|------|-------------|
| POST | /api/auth/register | email, password, username, age_verified, accepted_tos | Create account |
| POST | /api/auth/login | email, password | Get JWT |
| POST | /api/auth/google | google_id, email, name, picture | Google OAuth |
| POST | /api/auth/verify-age | — (JWT) | Mark user as 18+ |

### Jokes
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/jokes/generate?seen=id1,id2 | Optional | Get personalized joke |
| POST | /api/jokes/rate | Required | Rate a joke (like/dislike/favorite) |
| GET | /api/jokes/history | Required | Paginated view history |
| GET | /api/jokes/favorites | Required | All favorited jokes |
| PUT | /api/jokes/preferences | Required | Update humor preferences |

### Roast
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/roast/friend | Optional | Roast by name/job/fact |
| POST | /api/roast/photo | Required | Upload photo for roast |

### Meme
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/meme/generate | Optional | Generate meme image |
| GET | /api/meme/templates | — | List available templates |

### Battle
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | /api/battle/create | Required | Start a battle, get share URL |
| POST | /api/battle/join/:token | Optional | Accept challenge |
| POST | /api/battle/:id/vote | Optional | Vote for a joke |
| GET | /api/battle/:token | — | Get battle results |

### Profile
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | /api/profile/me | Required | Full profile + prefs |
| POST | /api/profile/photo | Required | Upload profile photo |
| POST | /api/profile/cartoon | Required | Generate cartoon avatar |
| PUT | /api/profile/avatar-type | Required | Switch original/cartoon |
| PUT | /api/profile/me | Required | Update username/bio |

---

## 🎯 Phase Roadmap

| Phase | Features | Est. Time |
|-------|----------|-----------|
| ✅ 1 | Architecture + DB schema | Done |
| ✅ 2 | Auth (email + Google) | Done |
| ✅ 3 | Core joke generation (hybrid) | Done |
| ✅ 4 | Roast features (friend + photo) | Done |
| ✅ 5 | Meme generator (template-based) | Done |
| ✅ 6 | Joke battles + viral sharing | Done |
| ✅ 7 | Profile + cartoon avatar | Done |
| 🔜 8 | Push notifications (Firebase) | ~1 day |
| 🔜 9 | Hebrew localization | ~0.5 day |
| 🔜 10 | Analytics dashboard | ~1 day |
| 🔜 11 | iOS/Android (React Native) | ~2 weeks |

---

## 💰 Cost Estimates (1K DAU)

| Service | Cost/month |
|---------|-----------|
| Anthropic (Claude) — 200 AI calls/day | ~$8 |
| OpenAI (embeddings + DALL-E) | ~$15 |
| PostgreSQL (Supabase free) | $0 |
| Redis (Upstash free tier) | $0 |
| Vercel (frontend) | $0 |
| Railway/Fly.io (backend) | ~$5 |
| S3 storage (Cloudflare R2) | ~$2 |
| **Total** | **~$30/month** |

At 100K DAU with caching: ~$200/month (95% cache hit rate).

---

## 🔒 Security Checklist
- [x] JWT with 30-day expiry
- [x] bcrypt password hashing (cost 12)
- [x] Rate limiting (100 req/15min global, 10 AI req/min)
- [x] Helmet.js security headers
- [x] Input validation with Zod
- [x] Age verification gate for adult content
- [x] File type + size validation for uploads
- [x] CORS restricted to frontend domain
- [ ] Image moderation (add AWS Rekognition or similar)
- [ ] CAPTCHA on registration

---

## 📱 PWA Features
- Installable on iOS + Android home screen
- Offline fallback page
- Push notification support (requires Firebase setup)
- Theme color + splash screen configured

---

## 🧪 Testing Commands
```bash
# Test joke generation
curl http://localhost:4000/api/jokes/generate

# Test roast
curl -X POST http://localhost:4000/api/roast/friend \
  -H "Content-Type: application/json" \
  -d '{"name":"Alex","job":"Developer","fact":"Never closes tabs"}'

# Health check
curl http://localhost:4000/health
```
