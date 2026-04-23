// src/index.ts — JokeAI Backend Entry Point
import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';

import { authRouter } from './routes/auth';
import { jokesRouter } from './routes/jokes';
import { roastRouter } from './routes/roast';
import { memeRouter } from './routes/meme';
import { profileRouter } from './routes/profile';
import { battleRouter } from './routes/battle';
import { errorHandler } from './middleware/errorHandler';
import { logger } from './utils/logger';

const app = express();

// ─── SECURITY ──────────────────────────────────────────────────────────────────
app.use(helmet());
app.use(cors({
  origin: process.env.FRONTEND_URL || 'http://localhost:3000',
  credentials: true,
}));

// ─── RATE LIMITING ─────────────────────────────────────────────────────────────
const limiter = rateLimit({
  windowMs: 15 * 60 * 1000, // 15 minutes
  max: 100,
  standardHeaders: true,
  legacyHeaders: false,
});

const aiLimiter = rateLimit({
  windowMs: 60 * 1000, // 1 minute
  max: 10, // 10 AI requests/minute per IP
  message: { error: 'Too many AI requests, please wait a moment.' },
});

app.use(limiter);
app.use(express.json({ limit: '10mb' }));
app.use(express.urlencoded({ extended: true }));

// ─── ROUTES ────────────────────────────────────────────────────────────────────
app.use('/api/auth',    authRouter);
app.use('/api/profile', profileRouter);
app.use('/api/jokes',   aiLimiter, jokesRouter);
app.use('/api/roast',   aiLimiter, roastRouter);
app.use('/api/meme',    memeRouter);
app.use('/api/battle',  battleRouter);

app.get('/health', (_req, res) => res.json({ status: 'ok', ts: Date.now() }));

// ─── ERROR HANDLING ────────────────────────────────────────────────────────────
app.use(errorHandler);

const PORT = process.env.PORT || 4000;
app.listen(PORT, () => logger.info(`JokeAI API running on :${PORT}`));

export default app;
