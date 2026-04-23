// src/services/jokeAI.ts — Hybrid AI Joke Generation Service
// Strategy: cache → embedding search → AI generation (cost-optimized)

import Anthropic from '@anthropic-ai/sdk';
import { query } from '../db/pool';
import { redis } from '../utils/redis';
import { logger } from '../utils/logger';

const client = new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY });

export interface JokePreferences {
  humor_types: string[];
  intensity: number;
  language: string;
  safe_mode: boolean;
  sexual_content: boolean;
}

export interface GeneratedJoke {
  id: string;
  text: string;
  category: string;
  source: 'cache' | 'embedding' | 'ai';
}

// ─── MAIN ENTRY POINT ─────────────────────────────────────────────────────────
export async function getJoke(
  prefs: JokePreferences,
  seenJokeIds: string[] = []
): Promise<GeneratedJoke> {
  const cacheKey = buildCacheKey(prefs);

  // 1. Check Redis cache for this exact preference combo
  const cached = await getCachedJoke(cacheKey, seenJokeIds);
  if (cached) {
    logger.debug(`Joke served from cache [${cacheKey}]`);
    await incrementMetric('cache_hits');
    return { ...cached, source: 'cache' };
  }

  // 2. Embedding-based search from existing joke pool
  const similar = await getJokeByEmbedding(prefs, seenJokeIds);
  if (similar) {
    logger.debug(`Joke served from embedding search`);
    await cacheJoke(cacheKey, similar);
    return { ...similar, source: 'embedding' };
  }

  // 3. Generate fresh joke with AI
  logger.debug(`Generating fresh AI joke`);
  await incrementMetric('ai_calls');
  const fresh = await generateWithAI(prefs);
  await storeJoke(fresh, prefs);
  await cacheJoke(cacheKey, fresh);
  return { ...fresh, source: 'ai' };
}

// ─── AI GENERATION ────────────────────────────────────────────────────────────
async function generateWithAI(prefs: JokePreferences): Promise<Omit<GeneratedJoke, 'source'>> {
  const prompt = buildJokePrompt(prefs);

  const msg = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 300,
    messages: [{ role: 'user', content: prompt }],
  });

  const text = (msg.content[0] as any).text.trim();
  const category = prefs.humor_types[0] || 'general';

  // Store immediately so future users can reuse
  const { rows } = await query<{ id: string }>(
    `INSERT INTO jokes (text, category, language, intensity, safe, sexual, source)
     VALUES ($1, $2, $3, $4, $5, $6, 'ai') RETURNING id`,
    [text, category, prefs.language, prefs.intensity, prefs.safe_mode, prefs.sexual_content]
  );

  // Async: generate embedding for future similarity searches (non-blocking)
  generateAndStoreEmbedding(rows[0].id, text).catch((e) =>
    logger.warn('Embedding generation failed', e)
  );

  return { id: rows[0].id, text, category };
}

// ─── PROMPT ENGINEERING ───────────────────────────────────────────────────────
export function buildJokePrompt(prefs: JokePreferences): string {
  const intensityLabel = ['very mild', 'mild', 'moderate', 'edgy', 'extreme'][prefs.intensity - 1];
  const langInstr = prefs.language === 'he'
    ? 'Write the joke in Hebrew (עברית).'
    : 'Write the joke in English.';

  return `You are a professional comedy writer specializing in personalized humor.

Generate ONE short, original joke. Return ONLY the joke text — no title, no explanation, no preamble.

User preferences:
- Humor styles: ${prefs.humor_types.join(', ')}
- Intensity level: ${intensityLabel} (${prefs.intensity}/5)
- Language: ${langInstr}
- Safe mode: ${prefs.safe_mode ? 'YES — avoid anything offensive, sexual, or extreme' : 'NO — edgy content allowed'}
- Sexual humor: ${prefs.sexual_content ? 'allowed (user is adult and consented)' : 'NOT allowed'}

Rules:
- Keep it 1–3 sentences maximum
- Make it genuinely funny, not generic
- Avoid overused joke formats (why did the chicken cross the road, etc.)
- Never start with "Why did..." or "What do you call..."
- Be creative and unexpected`;
}

// ─── ROAST A FRIEND ───────────────────────────────────────────────────────────
export async function generateFriendRoast(
  name: string, job: string, fact: string
): Promise<string> {
  const msg = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 200,
    messages: [{
      role: 'user',
      content: `You are a comedy roast writer. Write ONE playful roast joke about a person.

Person: ${name}
Job: ${job}
Fun fact: ${fact}

Rules:
- Playful and witty, NOT cruel or mean-spirited
- 2-3 sentences maximum
- Focus on the job or fun fact, not appearance
- Make it something they'd actually laugh at
- Return ONLY the roast text, nothing else`,
    }],
  });

  return (msg.content[0] as any).text.trim();
}

// ─── PHOTO ROAST ──────────────────────────────────────────────────────────────
export async function generatePhotoRoast(imageBase64: string, mimeType: string): Promise<string> {
  const msg = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 200,
    messages: [{
      role: 'user',
      content: [
        {
          type: 'image',
          source: { type: 'base64', media_type: mimeType as any, data: imageBase64 },
        },
        {
          type: 'text',
          text: `Look at this photo and write ONE playful, witty joke about what you see in the context or situation.

Rules:
- NEVER comment on physical appearance or body
- Focus only on the situation, setting, expression, activity, or vibe
- Keep it warm and funny, not cruel
- 1-2 sentences maximum
- Return ONLY the joke text`,
        },
      ],
    }],
  });

  return (msg.content[0] as any).text.trim();
}

// ─── DAILY PERSONALIZED JOKE ──────────────────────────────────────────────────
export async function generateDailyJoke(
  prefs: JokePreferences,
  recentActivity: string
): Promise<string> {
  const msg = await client.messages.create({
    model: 'claude-sonnet-4-20250514',
    max_tokens: 300,
    messages: [{
      role: 'user',
      content: `You are a personalized comedy writer. Generate ONE daily joke tailored specifically to this user.

User humor style: ${prefs.humor_types.join(', ')}
Intensity: ${prefs.intensity}/5
Recent activity: ${recentActivity}
Time of day context: ${getDayPart()}

Create a joke that feels personally delivered to them today. 1-3 sentences. Return ONLY the joke.`,
    }],
  });

  return (msg.content[0] as any).text.trim();
}

// ─── EMBEDDING SEARCH ─────────────────────────────────────────────────────────
async function getJokeByEmbedding(
  prefs: JokePreferences,
  seenIds: string[]
): Promise<Omit<GeneratedJoke, 'source'> | null> {
  try {
    // Create a preference description to embed
    const prefText = `${prefs.humor_types.join(' ')} joke intensity ${prefs.intensity} ${prefs.language}`;
    const embedding = await getEmbedding(prefText);

    const excludeClause = seenIds.length > 0
      ? `AND id NOT IN (${seenIds.map((_, i) => `$${i + 6}`).join(',')})`
      : '';

    const { rows } = await query<{ id: string; text: string; category: string }>(
      `SELECT id, text, category
       FROM jokes
       WHERE language = $1
         AND safe = $2
         AND sexual <= $3
         AND intensity BETWEEN $4 AND $5
         ${excludeClause}
         AND embedding IS NOT NULL
       ORDER BY embedding <=> $${seenIds.length + 6}::vector
       LIMIT 1`,
      [
        prefs.language,
        prefs.safe_mode,
        prefs.sexual_content ? true : false,
        Math.max(1, prefs.intensity - 1),
        Math.min(5, prefs.intensity + 1),
        ...seenIds,
        JSON.stringify(embedding),
      ]
    );

    return rows[0] || null;
  } catch (e) {
    logger.warn('Embedding search failed, falling back to AI', e);
    return null;
  }
}

async function generateAndStoreEmbedding(jokeId: string, text: string) {
  const embedding = await getEmbedding(text);
  await query(
    'UPDATE jokes SET embedding = $1 WHERE id = $2',
    [JSON.stringify(embedding), jokeId]
  );
}

async function getEmbedding(text: string): Promise<number[]> {
  // Using OpenAI text-embedding-ada-002 for embeddings (cheap & fast)
  // If you want to use only Anthropic: implement via voyage-ai or similar
  const { OpenAI } = await import('openai');
  const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY });
  const res = await openai.embeddings.create({
    model: 'text-embedding-ada-002',
    input: text.slice(0, 8000),
  });
  return res.data[0].embedding;
}

// ─── BATCH GENERATION (called by cron worker) ─────────────────────────────────
export async function batchGenerateJokes(count = 50): Promise<number> {
  const categories = ['dad jokes', 'tech jokes', 'work humor', 'absurd humor', 'relationship jokes'];
  const languages = ['en', 'he'];
  let generated = 0;

  for (const category of categories) {
    for (const language of languages) {
      for (let intensity = 1; intensity <= 3; intensity++) {
        const prefs: JokePreferences = {
          humor_types: [category],
          intensity,
          language,
          safe_mode: true,
          sexual_content: false,
        };

        try {
          await generateWithAI(prefs);
          generated++;
        } catch (e) {
          logger.error(`Batch generation failed for ${category}/${language}`, e);
        }
      }
    }
  }

  logger.info(`Batch generation complete: ${generated} jokes created`);
  return generated;
}

// ─── CACHE HELPERS ────────────────────────────────────────────────────────────
function buildCacheKey(prefs: JokePreferences): string {
  return `joke:${prefs.humor_types.sort().join('+')}:${prefs.intensity}:${prefs.language}:${prefs.safe_mode}:${prefs.sexual_content}`;
}

async function getCachedJoke(
  cacheKey: string,
  seenIds: string[]
): Promise<Omit<GeneratedJoke, 'source'> | null> {
  const keys = await redis.keys(`${cacheKey}:*`);
  const available = keys.filter((k) => {
    const id = k.split(':').pop();
    return id && !seenIds.includes(id);
  });

  if (available.length === 0) return null;

  const pick = available[Math.floor(Math.random() * available.length)];
  const cached = await redis.get(pick);
  if (!cached) return null;

  return JSON.parse(cached);
}

async function cacheJoke(cacheKey: string, joke: Omit<GeneratedJoke, 'source'>) {
  await redis.setex(
    `${cacheKey}:${joke.id}`,
    3600 * 24, // 24 hour TTL
    JSON.stringify(joke)
  );
}

async function storeJoke(joke: Omit<GeneratedJoke, 'source'>, prefs: JokePreferences) {
  await query(
    `INSERT INTO jokes (id, text, category, language, intensity, safe, sexual, source)
     VALUES ($1, $2, $3, $4, $5, $6, $7, 'ai')
     ON CONFLICT (id) DO NOTHING`,
    [joke.id, joke.text, joke.category, prefs.language, prefs.intensity, prefs.safe_mode, prefs.sexual_content]
  );
}

// ─── UTILS ────────────────────────────────────────────────────────────────────
function getDayPart(): string {
  const h = new Date().getHours();
  if (h < 6)  return 'late night';
  if (h < 12) return 'morning';
  if (h < 17) return 'afternoon';
  if (h < 21) return 'evening';
  return 'night';
}

async function incrementMetric(field: string) {
  await query(
    `INSERT INTO daily_metrics (date, ${field}) VALUES (CURRENT_DATE, 1)
     ON CONFLICT (date) DO UPDATE SET ${field} = daily_metrics.${field} + 1`
  );
}
