// src/workers/jokeWorker.ts — Background workers for batch generation & daily jokes
import 'dotenv/config';
import Bull from 'bull';
import { batchGenerateJokes, generateDailyJoke } from '../services/jokeAI';
import { query } from '../db/pool';
import { logger } from '../utils/logger';

const REDIS_URL = process.env.REDIS_URL || 'redis://localhost:6379';

// ─── QUEUES ───────────────────────────────────────────────────────────────────
const batchQueue  = new Bull('batch-joke-generation', REDIS_URL);
const dailyQueue  = new Bull('daily-joke-notifications', REDIS_URL);

// ─── BATCH GENERATION WORKER ──────────────────────────────────────────────────
// Runs every hour — generates 50 jokes pre-emptively to fill the pool
batchQueue.process(async (job) => {
  logger.info(`Batch job started: ${job.id}`);
  const count = await batchGenerateJokes(50);
  logger.info(`Batch job complete: ${count} jokes generated`);
  return { count };
});

// Schedule: every hour
batchQueue.add({}, { repeat: { cron: '0 * * * *' } });

// ─── DAILY JOKE WORKER ────────────────────────────────────────────────────────
dailyQueue.process(async (job) => {
  const { userId, prefs } = job.data;
  logger.debug(`Generating daily joke for user ${userId}`);

  // Get recent activity summary
  const { rows } = await query(
    `SELECT category, COUNT(*) as cnt
     FROM joke_history jh JOIN jokes j ON j.id = jh.joke_id
     WHERE jh.user_id = $1 AND jh.viewed_at > NOW() - INTERVAL '7 days'
     GROUP BY category ORDER BY cnt DESC LIMIT 3`,
    [userId]
  );
  const recentActivity = rows.length > 0
    ? `Mostly liked ${rows.map((r: any) => r.category).join(', ')} jokes`
    : 'No recent activity';

  const text = await generateDailyJoke(prefs, recentActivity);

  // Store the daily joke for this user
  const { rows: inserted } = await query(
    `INSERT INTO jokes (text, category, language, intensity, safe, sexual, source)
     VALUES ($1, 'daily', $2, $3, $4, $5, 'ai') RETURNING id`,
    [text, prefs.language, prefs.intensity, prefs.safe_mode, prefs.sexual_content]
  );

  // In production: send push notification or email here
  logger.info(`Daily joke ${inserted[0].id} ready for user ${userId}`);
  return { jokeId: inserted[0].id, text };
});

// Schedule: queue daily jokes for all users at 8 AM
async function scheduleDailyJokes() {
  const { rows } = await query(
    `SELECT u.id, hp.humor_types, hp.intensity, hp.language, hp.safe_mode, hp.sexual_content
     FROM users u
     JOIN humor_preferences hp ON hp.user_id = u.id
     WHERE u.last_login_at > NOW() - INTERVAL '14 days'` // Only active users
  );

  logger.info(`Scheduling daily jokes for ${rows.length} active users`);

  for (const user of rows) {
    await dailyQueue.add({
      userId: user.id,
      prefs: {
        humor_types: user.humor_types,
        intensity: user.intensity,
        language: user.language,
        safe_mode: user.safe_mode,
        sexual_content: user.sexual_content,
      },
    }, {
      delay: Math.random() * 60000, // Stagger over 1 minute to avoid thundering herd
      attempts: 3,
      backoff: { type: 'exponential', delay: 2000 },
    });
  }
}

// Run scheduler at 8 AM daily
const schedulerQueue = new Bull('daily-scheduler', REDIS_URL);
schedulerQueue.process(async () => scheduleDailyJokes());
schedulerQueue.add({}, { repeat: { cron: '0 8 * * *' } });

logger.info('JokeAI workers running...');
