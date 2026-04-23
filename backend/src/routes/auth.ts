// src/routes/auth.ts
import { Router, Request, Response } from 'express';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { z } from 'zod';
import { query } from '../db/pool';
import { AppError } from '../middleware/errorHandler';

export const authRouter = Router();

const JWT_SECRET = process.env.JWT_SECRET!;
const JWT_EXPIRES = '30d';

function signToken(userId: string) {
  return jwt.sign({ sub: userId }, JWT_SECRET, { expiresIn: JWT_EXPIRES });
}

// ─── REGISTER ──────────────────────────────────────────────────────────────────
const registerSchema = z.object({
  email:    z.string().email(),
  password: z.string().min(8),
  username: z.string().min(3).max(30).regex(/^[a-z0-9_]+$/i),
  age_verified: z.boolean(),
  accepted_tos: z.boolean(),
});

authRouter.post('/register', async (req: Request, res: Response) => {
  const parsed = registerSchema.safeParse(req.body);
  if (!parsed.success) throw new AppError(400, parsed.error.message);

  const { email, password, username, age_verified, accepted_tos } = parsed.data;
  if (!accepted_tos) throw new AppError(400, 'You must accept the terms of service.');

  // Check existing
  const { rows } = await query('SELECT id FROM users WHERE email=$1', [email]);
  if (rows.length > 0) throw new AppError(409, 'Email already registered.');

  const userCheck = await query('SELECT user_id FROM profiles WHERE username=$1', [username]);
  if (userCheck.rows.length > 0) throw new AppError(409, 'Username taken.');

  const password_hash = await bcrypt.hash(password, 12);

  const result = await query<{ id: string }>(
    `INSERT INTO users (email, password_hash, age_verified, accepted_tos)
     VALUES ($1, $2, $3, $4) RETURNING id`,
    [email, password_hash, age_verified, accepted_tos]
  );
  const userId = result.rows[0].id;

  await query(
    `INSERT INTO profiles (user_id, username) VALUES ($1, $2)`,
    [userId, username]
  );

  await query(
    `INSERT INTO humor_preferences (user_id) VALUES ($1)`,
    [userId]
  );

  const token = signToken(userId);
  res.status(201).json({ token, userId });
});

// ─── LOGIN ─────────────────────────────────────────────────────────────────────
const loginSchema = z.object({
  email:    z.string().email(),
  password: z.string(),
});

authRouter.post('/login', async (req: Request, res: Response) => {
  const parsed = loginSchema.safeParse(req.body);
  if (!parsed.success) throw new AppError(400, 'Invalid credentials.');

  const { email, password } = parsed.data;

  const { rows } = await query<{ id: string; password_hash: string }>(
    'SELECT id, password_hash FROM users WHERE email=$1 AND provider=$2',
    [email, 'email']
  );
  if (rows.length === 0) throw new AppError(401, 'Invalid credentials.');

  const valid = await bcrypt.compare(password, rows[0].password_hash);
  if (!valid) throw new AppError(401, 'Invalid credentials.');

  await query('UPDATE users SET last_login_at=NOW() WHERE id=$1', [rows[0].id]);

  const token = signToken(rows[0].id);
  res.json({ token, userId: rows[0].id });
});

// ─── GOOGLE OAUTH CALLBACK ─────────────────────────────────────────────────────
authRouter.post('/google', async (req: Request, res: Response) => {
  const { google_id, email, name, picture } = req.body;
  if (!google_id || !email) throw new AppError(400, 'Missing Google profile data.');

  let { rows } = await query<{ id: string }>(
    'SELECT id FROM users WHERE provider=$1 AND provider_id=$2',
    ['google', google_id]
  );

  let userId: string;
  if (rows.length > 0) {
    userId = rows[0].id;
    await query('UPDATE users SET last_login_at=NOW() WHERE id=$1', [userId]);
  } else {
    // Create new user from Google
    const newUser = await query<{ id: string }>(
      `INSERT INTO users (email, provider, provider_id, age_verified, accepted_tos)
       VALUES ($1,'google',$2,false,true) RETURNING id`,
      [email, google_id]
    );
    userId = newUser.rows[0].id;

    const baseUsername = (name || email.split('@')[0])
      .toLowerCase()
      .replace(/[^a-z0-9]/g, '_')
      .slice(0, 25);
    const username = `${baseUsername}_${Math.floor(Math.random() * 9000 + 1000)}`;

    await query(
      `INSERT INTO profiles (user_id, username, original_photo_url) VALUES ($1,$2,$3)`,
      [userId, username, picture || null]
    );
    await query(`INSERT INTO humor_preferences (user_id) VALUES ($1)`, [userId]);
  }

  const token = signToken(userId);
  res.json({ token, userId });
});

// ─── VERIFY AGE ────────────────────────────────────────────────────────────────
authRouter.post('/verify-age', async (req: Request, res: Response) => {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (!token) throw new AppError(401, 'Unauthorized');

  const payload = jwt.verify(token, JWT_SECRET) as { sub: string };
  await query('UPDATE users SET age_verified=true WHERE id=$1', [payload.sub]);
  res.json({ success: true });
});
