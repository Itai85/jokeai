// src/utils/redis.ts
import Redis from 'ioredis';
export const redis = new Redis(process.env.REDIS_URL || 'redis://localhost:6379', {
  maxRetriesPerRequest: 3,
  lazyConnect: true,
});

redis.on('error', (err) => console.error('Redis error:', err));

// ─────────────────────────────────────────────────────────────────────────────
// src/utils/logger.ts
export const logger = {
  info:  (msg: string, ...args: any[]) => console.log(`[INFO]  ${msg}`, ...args),
  warn:  (msg: string, ...args: any[]) => console.warn(`[WARN]  ${msg}`, ...args),
  error: (msg: string, ...args: any[]) => console.error(`[ERROR] ${msg}`, ...args),
  debug: (msg: string, ...args: any[]) => process.env.NODE_ENV !== 'production' && console.debug(`[DEBUG] ${msg}`, ...args),
};

// ─────────────────────────────────────────────────────────────────────────────
// src/middleware/errorHandler.ts
import { Request, Response, NextFunction } from 'express';

export class AppError extends Error {
  constructor(public statusCode: number, message: string) {
    super(message);
    this.name = 'AppError';
  }
}

export function errorHandler(err: any, _req: Request, res: Response, _next: NextFunction) {
  if (err instanceof AppError) {
    return res.status(err.statusCode).json({ error: err.message });
  }
  if (err.name === 'ZodError') {
    return res.status(400).json({ error: 'Validation failed', details: err.errors });
  }
  console.error('[ERROR]', err);
  res.status(500).json({ error: 'Internal server error' });
}

// ─────────────────────────────────────────────────────────────────────────────
// src/services/storage.ts — S3-compatible upload (works with AWS S3, Cloudflare R2, etc.)
import { S3Client, PutObjectCommand, GetObjectCommand } from '@aws-sdk/client-s3';
import { getSignedUrl } from '@aws-sdk/s3-request-presigner';

const s3 = new S3Client({
  region: process.env.S3_REGION || 'auto',
  endpoint: process.env.S3_ENDPOINT, // Set for R2/MinIO
  credentials: {
    accessKeyId: process.env.S3_ACCESS_KEY!,
    secretAccessKey: process.env.S3_SECRET_KEY!,
  },
});

const BUCKET = process.env.S3_BUCKET!;
const PUBLIC_URL = process.env.S3_PUBLIC_URL!; // e.g. https://cdn.jokeai.com

export async function uploadToS3(
  buffer: Buffer,
  key: string,
  contentType: string
): Promise<string> {
  await s3.send(new PutObjectCommand({
    Bucket: BUCKET,
    Key: key,
    Body: buffer,
    ContentType: contentType,
    CacheControl: 'public, max-age=31536000',
  }));
  return `${PUBLIC_URL}/${key}`;
}

export async function getPresignedUploadUrl(key: string, contentType: string): Promise<string> {
  const cmd = new PutObjectCommand({ Bucket: BUCKET, Key: key, ContentType: contentType });
  return getSignedUrl(s3, cmd, { expiresIn: 300 });
}
