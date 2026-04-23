// src/routes/profile.ts
import { Router, Response } from 'express';
import multer from 'multer';
import sharp from 'sharp';
import Anthropic from '@anthropic-ai/sdk';
import { query } from '../db/pool';
import { uploadToS3 } from '../services/storage';
import { requireAuth, AuthRequest } from '../middleware/auth';
import { AppError } from '../middleware/errorHandler';

export const profileRouter = Router();
const upload = multer({ storage: multer.memoryStorage(), limits: { fileSize: 8 * 1024 * 1024 } });
const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

// ─── GET PROFILE ──────────────────────────────────────────────────────────────
profileRouter.get('/me', requireAuth, async (req: AuthRequest, res: Response) => {
  const { rows } = await query(
    `SELECT p.*, u.email, u.age_verified, u.created_at,
            hp.humor_types, hp.intensity, hp.language, hp.safe_mode, hp.sexual_content
     FROM profiles p
     JOIN users u ON u.id = p.user_id
     LEFT JOIN humor_preferences hp ON hp.user_id = p.user_id
     WHERE p.user_id = $1`,
    [req.userId]
  );
  if (!rows[0]) throw new AppError(404, 'Profile not found.');
  res.json(rows[0]);
});

// ─── UPLOAD PHOTO ─────────────────────────────────────────────────────────────
profileRouter.post('/photo', requireAuth, upload.single('photo'), async (req: AuthRequest, res: Response) => {
  if (!req.file) throw new AppError(400, 'No photo provided.');

  const allowed = ['image/jpeg', 'image/png', 'image/webp'];
  if (!allowed.includes(req.file.mimetype)) throw new AppError(400, 'Invalid image format.');

  // Resize to max 512x512 to save storage
  const resized = await sharp(req.file.buffer)
    .resize(512, 512, { fit: 'cover' })
    .jpeg({ quality: 85 })
    .toBuffer();

  const key = `avatars/${req.userId}/original.jpg`;
  const url = await uploadToS3(resized, key, 'image/jpeg');

  await query(
    'UPDATE profiles SET original_photo_url=$1, updated_at=NOW() WHERE user_id=$2',
    [url, req.userId]
  );

  res.json({ url });
});

// ─── GENERATE CARTOON AVATAR ──────────────────────────────────────────────────
// Note: True image generation requires an image gen API (DALL-E, Stable Diffusion, etc.)
// This endpoint uses Claude to describe what cartoon to generate, then calls the image API.
profileRouter.post('/cartoon', requireAuth, async (req: AuthRequest, res: Response) => {
  // Check if user has a photo
  const { rows } = await query(
    'SELECT original_photo_url FROM profiles WHERE user_id=$1', [req.userId]
  );
  if (!rows[0]?.original_photo_url) throw new AppError(400, 'Upload a photo first.');

  // Check if cartoon already exists (only generate once unless forced)
  const existing = await query<{ cartoon_photo_url: string }>(
    'SELECT cartoon_photo_url FROM profiles WHERE user_id=$1 AND cartoon_photo_url IS NOT NULL',
    [req.userId]
  );
  if (existing.rows[0] && !req.body.force) {
    return res.json({ url: existing.rows[0].cartoon_photo_url, cached: true });
  }

  // Fetch original photo and analyze it with Claude
  const photoRes = await fetch(rows[0].original_photo_url);
  const photoBuffer = Buffer.from(await photoRes.arrayBuffer());
  const base64 = photoBuffer.toString('base64');

  // Claude analyzes the photo to create a cartoon description
  const descMsg = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 300,
    messages: [{
      role: 'user',
      content: [
        {
          type: 'image',
          source: { type: 'base64', media_type: 'image/jpeg', data: base64 },
        },
        {
          type: 'text',
          text: `Describe this person in a way suitable for generating a fun cartoon avatar.
Focus on: hair color/style, general features, expression, any accessories.
Do NOT mention skin color or race.
Keep it brief (2-3 sentences). This will be used as a DALL-E prompt.
Format: "A cartoon character with [description]. Animated style, colorful, friendly expression."`,
        },
      ],
    }],
  });

  const cartoonPrompt = (descMsg.content[0] as any).text;

  // Call image generation API (DALL-E 3)
  const { OpenAI } = await import('openai');
  const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });

  const imgRes = await openai.images.generate({
    model: 'dall-e-3',
    prompt: `${cartoonPrompt} Cartoon avatar style, cute and fun, white background, digital art.`,
    size: '1024x1024',
    quality: 'standard',
    n: 1,
  });

  const imageUrl = imgRes.data[0].url!;

  // Download and store in our S3
  const imgBuffer = Buffer.from(await (await fetch(imageUrl)).arrayBuffer());
  const key = `avatars/${req.userId}/cartoon.jpg`;
  const storedUrl = await uploadToS3(imgBuffer, key, 'image/jpeg');

  await query(
    'UPDATE profiles SET cartoon_photo_url=$1, updated_at=NOW() WHERE user_id=$2',
    [storedUrl, req.userId]
  );

  res.json({ url: storedUrl });
});

// ─── SET ACTIVE AVATAR ────────────────────────────────────────────────────────
profileRouter.put('/avatar-type', requireAuth, async (req: AuthRequest, res: Response) => {
  const { type } = req.body;
  if (!['original', 'cartoon'].includes(type)) throw new AppError(400, 'Invalid avatar type.');
  await query(
    'UPDATE profiles SET active_avatar_type=$1 WHERE user_id=$2', [type, req.userId]
  );
  res.json({ success: true });
});

// ─── UPDATE USERNAME/BIO ──────────────────────────────────────────────────────
profileRouter.put('/me', requireAuth, async (req: AuthRequest, res: Response) => {
  const { username, bio } = req.body;

  if (username) {
    if (!/^[a-z0-9_]{3,30}$/i.test(username)) {
      throw new AppError(400, 'Username must be 3-30 chars, letters/numbers/underscores only.');
    }
    const { rows } = await query(
      'SELECT user_id FROM profiles WHERE username=$1 AND user_id!=$2', [username, req.userId]
    );
    if (rows.length > 0) throw new AppError(409, 'Username already taken.');
  }

  await query(
    `UPDATE profiles SET
       username = COALESCE($1, username),
       bio = COALESCE($2, bio),
       updated_at = NOW()
     WHERE user_id = $3`,
    [username || null, bio || null, req.userId]
  );
  res.json({ success: true });
});
