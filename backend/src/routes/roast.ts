// src/routes/roast.ts
import { Router, Response } from 'express';
import { z } from 'zod';
import multer from 'multer';
import { generateFriendRoast, generatePhotoRoast } from '../services/jokeAI';
import { requireAuth, AuthRequest } from '../middleware/auth';
import { AppError } from '../middleware/errorHandler';

export const roastRouter = Router();
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 5 * 1024 * 1024 } });

// ─── ROAST A FRIEND ────────────────────────────────────────────────────────────
const friendSchema = z.object({
  name: z.string().min(1).max(50),
  job:  z.string().min(1).max(100),
  fact: z.string().min(1).max(200),
});

roastRouter.post('/friend', optionalAuth, async (req: AuthRequest, res: Response) => {
  const parsed = friendSchema.safeParse(req.body);
  if (!parsed.success) throw new AppError(400, 'Missing roast info.');

  const { name, job, fact } = parsed.data;
  const text = await generateFriendRoast(name, job, fact);

  res.json({
    text,
    shareText: `😂 JokeAI just roasted ${name}:\n\n"${text}"\n\nTry it: ${process.env.APP_URL}`,
  });
});

// ─── ROAST A PHOTO ─────────────────────────────────────────────────────────────
roastRouter.post('/photo', requireAuth, upload.single('photo'), async (req: AuthRequest, res: Response) => {
  if (!req.file) throw new AppError(400, 'No photo uploaded.');

  const allowed = ['image/jpeg', 'image/png', 'image/webp'];
  if (!allowed.includes(req.file.mimetype)) {
    throw new AppError(400, 'Only JPEG, PNG, or WebP images are accepted.');
  }

  const base64 = req.file.buffer.toString('base64');
  const text = await generatePhotoRoast(base64, req.file.mimetype);

  res.json({
    text,
    shareText: `😂 JokeAI roasted my photo:\n\n"${text}"\n\nGet roasted: ${process.env.APP_URL}`,
  });
});

function optionalAuth(req: AuthRequest, _res: any, next: any) {
  const token = req.headers.authorization?.replace('Bearer ', '');
  if (token) {
    try {
      const jwt = require('jsonwebtoken');
      const payload = jwt.verify(token, process.env.JWT_SECRET!) as { sub: string };
      req.userId = payload.sub;
    } catch {}
  }
  next();
}
