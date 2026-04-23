// src/routes/meme.ts
import { Router, Response } from 'express';
import { z } from 'zod';
import { query } from '../db/pool';
import { generateMeme } from '../services/memeGenerator';
import { requireAuth, optionalAuth, AuthRequest } from '../middleware/auth';
import { AppError } from '../middleware/errorHandler';

export const memeRouter = Router();

// ─── GENERATE MEME ────────────────────────────────────────────────────────────
memeRouter.post('/generate', optionalAuth, async (req: AuthRequest, res: Response) => {
  const { joke_id, joke_text, template_id } = req.body;

  let text: string;
  if (joke_id) {
    const { rows } = await query<{ text: string }>('SELECT text FROM jokes WHERE id=$1', [joke_id]);
    if (!rows[0]) throw new AppError(404, 'Joke not found.');
    text = rows[0].text;
  } else if (joke_text) {
    text = joke_text;
  } else {
    throw new AppError(400, 'Provide joke_id or joke_text.');
  }

  const { url } = await generateMeme(text, template_id);

  // Save meme record for authenticated users
  let memeId: string | undefined;
  if (req.userId && joke_id) {
    const { rows } = await query<{ id: string }>(
      `INSERT INTO memes (user_id, joke_id, template_id, image_url)
       VALUES ($1, $2, $3, $4) RETURNING id`,
      [req.userId, joke_id, template_id || null, url]
    );
    memeId = rows[0].id;
  }

  res.json({ url, memeId });
});

// ─── LIST TEMPLATES ───────────────────────────────────────────────────────────
memeRouter.get('/templates', async (_req, res: Response) => {
  const { rows } = await query(
    `SELECT id, name, image_url, category FROM meme_templates WHERE active=true ORDER BY name`
  );
  res.json({ templates: rows });
});


// ─────────────────────────────────────────────────────────────────────────────
// src/routes/battle.ts (inline for brevity)
// ─────────────────────────────────────────────────────────────────────────────
import { Router as BattleRouter } from 'express';
import { getJoke } from '../services/jokeAI';

export const battleRouter = BattleRouter();

// ─── CREATE BATTLE ────────────────────────────────────────────────────────────
battleRouter.post('/create', requireAuth, async (req: AuthRequest, res: Response) => {
  const prefs = {
    humor_types: ['absurd humor', 'dad jokes'],
    intensity: 3,
    language: 'en',
    safe_mode: true,
    sexual_content: false,
  };

  const jokeA = await getJoke(prefs);

  const { rows } = await query<{ id: string; share_token: string }>(
    `INSERT INTO joke_battles (challenger_id, joke_a_id)
     VALUES ($1, $2) RETURNING id, share_token`,
    [req.userId, jokeA.id]
  );

  await query(
    `INSERT INTO daily_metrics (date, battles_started) VALUES (CURRENT_DATE, 1)
     ON CONFLICT (date) DO UPDATE SET battles_started = daily_metrics.battles_started + 1`
  );

  res.json({
    battleId: rows[0].id,
    shareToken: rows[0].share_token,
    jokeA: jokeA.text,
    challengeUrl: `${process.env.APP_URL}/battle/${rows[0].share_token}`,
  });
});

// ─── JOIN BATTLE ──────────────────────────────────────────────────────────────
battleRouter.post('/join/:token', optionalAuth, async (req: AuthRequest, res: Response) => {
  const { token } = req.params;

  const { rows } = await query(
    `SELECT id, joke_a_id, status FROM joke_battles WHERE share_token=$1`, [token]
  );
  if (!rows[0]) throw new AppError(404, 'Battle not found.');
  if (rows[0].status !== 'pending') throw new AppError(400, 'Battle already started.');

  const prefs = {
    humor_types: ['absurd humor'],
    intensity: 3,
    language: 'en',
    safe_mode: true,
    sexual_content: false,
  };
  const jokeB = await getJoke(prefs, [rows[0].joke_a_id]);

  await query(
    `UPDATE joke_battles SET joke_b_id=$1, opponent_id=$2, status='active' WHERE id=$3`,
    [jokeB.id, req.userId || null, rows[0].id]
  );

  const jokeA = await query<{ text: string }>('SELECT text FROM jokes WHERE id=$1', [rows[0].joke_a_id]);

  res.json({ battleId: rows[0].id, jokeA: jokeA.rows[0].text, jokeB: jokeB.text });
});

// ─── VOTE ON BATTLE ───────────────────────────────────────────────────────────
battleRouter.post('/:battleId/vote', optionalAuth, async (req: AuthRequest, res: Response) => {
  const { battleId } = req.params;
  const { voted_for } = req.body;

  if (!['a', 'b'].includes(voted_for)) throw new AppError(400, 'Vote must be a or b.');

  const { rows } = await query(
    'SELECT status FROM joke_battles WHERE id=$1', [battleId]
  );
  if (!rows[0] || rows[0].status !== 'active') throw new AppError(400, 'Battle not active.');

  await query(
    `INSERT INTO battle_votes (battle_id, voter_id, voted_for) VALUES ($1,$2,$3)`,
    [battleId, req.userId || null, voted_for]
  );

  const field = voted_for === 'a' ? 'votes_a' : 'votes_b';
  await query(`UPDATE joke_battles SET ${field} = ${field} + 1 WHERE id=$1`, [battleId]);

  res.json({ success: true });
});

// ─── GET BATTLE RESULTS ───────────────────────────────────────────────────────
battleRouter.get('/:token', async (req, res: Response) => {
  const { token } = req.params;
  const { rows } = await query(
    `SELECT jb.*, ja.text as joke_a_text, jb2.text as joke_b_text
     FROM joke_battles jb
     JOIN jokes ja ON ja.id = jb.joke_a_id
     LEFT JOIN jokes jb2 ON jb2.id = jb.joke_b_id
     WHERE jb.share_token=$1`,
    [token]
  );
  if (!rows[0]) throw new AppError(404, 'Battle not found.');
  res.json(rows[0]);
});
