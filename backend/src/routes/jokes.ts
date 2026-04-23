// src/routes/jokes.ts
import { Router, Response } from 'express';
import { z } from 'zod';
import { query } from '../db/pool';
import { getJoke } from '../services/jokeAI';
import { requireAuth, optionalAuth, AuthRequest } from '../middleware/auth';
import { AppError } from '../middleware/errorHandler';

export const jokesRouter = Router();

// ─── GET PREFERENCES ──────────────────────────────────────────────────────────
async function getUserPrefs(userId: string) {
  const { rows } = await query(
    `SELECT humor_types, intensity, language, safe_mode, sexual_content
     FROM humor_preferences WHERE user_id = $1`,
    [userId]
  );
  return rows[0] || {
    humor_types: ['dad jokes'],
    intensity: 3,
    language: 'en',
    safe_mode: true,
    sexual_content: false,
  };
}

// ─── GENERATE JOKE ────────────────────────────────────────────────────────────
jokesRouter.get('/generate', optionalAuth, async (req: AuthRequest, res: Response) => {
  // Seen joke IDs from query (client tracks locally)
  const seenParam = req.query.seen as string || '';
  const seenIds = seenParam ? seenParam.split(',').filter(Boolean) : [];

  let prefs;
  if (req.userId) {
    prefs = await getUserPrefs(req.userId);
  } else {
    // Guest users get default safe preferences
    prefs = {
      humor_types: ['dad jokes', 'absurd humor'],
      intensity: 2,
      language: 'en',
      safe_mode: true,
      sexual_content: false,
    };
  }

  const joke = await getJoke(prefs, seenIds);

  // Track history for authenticated users
  if (req.userId) {
    await query(
      `INSERT INTO joke_history (user_id, joke_id) VALUES ($1, $2)`,
      [req.userId, joke.id]
    ).catch(() => {}); // Non-critical
  }

  res.json(joke);
});

// ─── RATE JOKE ────────────────────────────────────────────────────────────────
const rateSchema = z.object({
  joke_id: z.string().uuid(),
  rating:  z.enum(['like', 'dislike', 'favorite']),
  shared:  z.boolean().optional().default(false),
});

jokesRouter.post('/rate', requireAuth, async (req: AuthRequest, res: Response) => {
  const parsed = rateSchema.safeParse(req.body);
  if (!parsed.success) throw new AppError(400, 'Invalid rating data.');

  const { joke_id, rating, shared } = parsed.data;

  await query(
    `INSERT INTO joke_ratings (user_id, joke_id, rating, shared)
     VALUES ($1, $2, $3, $4)
     ON CONFLICT (user_id, joke_id) DO UPDATE
     SET rating = $3, shared = $4`,
    [req.userId, joke_id, rating, shared]
  );

  if (shared) {
    await query(
      `INSERT INTO daily_metrics (date, shares_total)
       VALUES (CURRENT_DATE, 1)
       ON CONFLICT (date) DO UPDATE SET shares_total = daily_metrics.shares_total + 1`
    );
  }

  res.json({ success: true });
});

// ─── JOKE HISTORY ─────────────────────────────────────────────────────────────
jokesRouter.get('/history', requireAuth, async (req: AuthRequest, res: Response) => {
  const page = parseInt(req.query.page as string) || 1;
  const limit = 20;
  const offset = (page - 1) * limit;

  const { rows } = await query(
    `SELECT j.id, j.text, j.category, j.created_at,
            jr.rating, jr.shared
     FROM joke_history jh
     JOIN jokes j ON j.id = jh.joke_id
     LEFT JOIN joke_ratings jr ON jr.joke_id = j.id AND jr.user_id = $1
     WHERE jh.user_id = $1
     ORDER BY jh.viewed_at DESC
     LIMIT $2 OFFSET $3`,
    [req.userId, limit, offset]
  );

  res.json({ jokes: rows, page, limit });
});

// ─── FAVORITES ────────────────────────────────────────────────────────────────
jokesRouter.get('/favorites', requireAuth, async (req: AuthRequest, res: Response) => {
  const { rows } = await query(
    `SELECT j.id, j.text, j.category, jr.created_at
     FROM joke_ratings jr
     JOIN jokes j ON j.id = jr.joke_id
     WHERE jr.user_id = $1 AND jr.rating = 'favorite'
     ORDER BY jr.created_at DESC`,
    [req.userId]
  );
  res.json({ favorites: rows });
});

// ─── UPDATE PREFERENCES ───────────────────────────────────────────────────────
const prefsSchema = z.object({
  humor_types:    z.array(z.string()).min(1),
  intensity:      z.number().int().min(1).max(5),
  language:       z.enum(['en', 'he']),
  safe_mode:      z.boolean(),
  sexual_content: z.boolean(),
});

jokesRouter.put('/preferences', requireAuth, async (req: AuthRequest, res: Response) => {
  const parsed = prefsSchema.safeParse(req.body);
  if (!parsed.success) throw new AppError(400, 'Invalid preferences.');

  const { humor_types, intensity, language, safe_mode, sexual_content } = parsed.data;

  // Sexual content requires age verification
  if (sexual_content) {
    const { rows } = await query(
      'SELECT age_verified FROM users WHERE id=$1', [req.userId]
    );
    if (!rows[0]?.age_verified) {
      throw new AppError(403, 'Age verification required for adult content.');
    }
  }

  await query(
    `UPDATE humor_preferences
     SET humor_types=$1, intensity=$2, language=$3, safe_mode=$4, sexual_content=$5, updated_at=NOW()
     WHERE user_id=$6`,
    [humor_types, intensity, language, safe_mode, sexual_content, req.userId]
  );

  res.json({ success: true });
});
