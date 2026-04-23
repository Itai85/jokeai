// src/services/memeGenerator.ts — Template-based meme generation (low-cost)
import sharp from 'sharp';
import { query } from '../db/pool';
import { uploadToS3 } from './storage';
import { logger } from '../utils/logger';

interface MemeTemplate {
  id: string;
  name: string;
  image_url: string;
  top_text_pos: { x: number; y: number; maxWidth: number };
  bottom_text_pos: { x: number; y: number; maxWidth: number };
}

export async function generateMeme(
  jokeText: string,
  templateId?: string
): Promise<{ url: string; memeId?: string }> {

  // Get template (random if not specified)
  const template = await getTemplate(templateId);

  // Download template image
  const templateRes = await fetch(template.image_url);
  if (!templateRes.ok) throw new Error('Could not fetch meme template');
  const templateBuffer = Buffer.from(await templateRes.arrayBuffer());

  // Get image dimensions
  const meta = await sharp(templateBuffer).metadata();
  const width = meta.width || 800;
  const height = meta.height || 600;

  // Split joke into top/bottom text
  const { topText, bottomText } = splitJokeText(jokeText);

  // Build SVG text overlay
  const svgOverlay = buildTextOverlay(topText, bottomText, width, height, template);

  // Composite: template + text overlay
  const outputBuffer = await sharp(templateBuffer)
    .composite([{
      input: Buffer.from(svgOverlay),
      top: 0,
      left: 0,
    }])
    .jpeg({ quality: 85 })
    .toBuffer();

  // Upload to S3
  const key = `memes/${Date.now()}-${Math.random().toString(36).slice(2)}.jpg`;
  const url = await uploadToS3(outputBuffer, key, 'image/jpeg');

  logger.debug(`Meme generated: ${key}`);
  return { url };
}

function buildTextOverlay(
  topText: string,
  bottomText: string,
  width: number,
  height: number,
  template: MemeTemplate
): string {
  const fontSize = Math.max(24, Math.min(48, width / 15));
  const strokeWidth = fontSize / 12;

  const textStyle = `
    font-family: Impact, 'Arial Black', sans-serif;
    font-size: ${fontSize}px;
    font-weight: 900;
    text-anchor: middle;
    text-transform: uppercase;
    letter-spacing: 1px;
  `;

  const topX = (template.top_text_pos.x / 100) * width;
  const topY = (template.top_text_pos.y / 100) * height + fontSize;
  const botX = (template.bottom_text_pos.x / 100) * width;
  const botY = (template.bottom_text_pos.y / 100) * height;
  const maxW = (template.top_text_pos.maxWidth / 100) * width;

  // Wrap text into lines
  const topLines = wrapText(topText, maxW, fontSize);
  const botLines = wrapText(bottomText, maxW, fontSize);

  const renderLines = (lines: string[], startX: number, startY: number, direction: 1 | -1) =>
    lines.map((line, i) => `
      <text x="${startX}" y="${startY + direction * i * (fontSize * 1.1)}"
        style="${textStyle}" stroke="black" stroke-width="${strokeWidth}" paint-order="stroke">
        ${escapeXml(line)}
      </text>
      <text x="${startX}" y="${startY + direction * i * (fontSize * 1.1)}"
        style="${textStyle}" fill="white">
        ${escapeXml(line)}
      </text>
    `).join('');

  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">
    ${renderLines(topLines, topX, topY, 1)}
    ${renderLines(botLines.reverse(), botX, botY, -1)}
  </svg>`;
}

function wrapText(text: string, maxWidth: number, fontSize: number): string[] {
  const approxCharWidth = fontSize * 0.55;
  const charsPerLine = Math.floor(maxWidth / approxCharWidth);
  const words = text.split(' ');
  const lines: string[] = [];
  let current = '';

  for (const word of words) {
    if ((current + ' ' + word).trim().length > charsPerLine) {
      if (current) lines.push(current);
      current = word;
    } else {
      current = (current + ' ' + word).trim();
    }
  }
  if (current) lines.push(current);
  return lines;
}

function splitJokeText(text: string): { topText: string; bottomText: string } {
  // Try to split at sentence boundary
  const sentences = text.match(/[^.!?]+[.!?]+/g) || [text];
  if (sentences.length >= 2) {
    const mid = Math.ceil(sentences.length / 2);
    return {
      topText: sentences.slice(0, mid).join(' ').trim(),
      bottomText: sentences.slice(mid).join(' ').trim(),
    };
  }
  // Split at word midpoint
  const words = text.split(' ');
  const mid = Math.ceil(words.length / 2);
  return {
    topText: words.slice(0, mid).join(' '),
    bottomText: words.slice(mid).join(' '),
  };
}

async function getTemplate(templateId?: string): Promise<MemeTemplate> {
  if (templateId) {
    const { rows } = await query<MemeTemplate>(
      'SELECT * FROM meme_templates WHERE id=$1 AND active=true', [templateId]
    );
    if (rows[0]) return rows[0];
  }
  // Random active template
  const { rows } = await query<MemeTemplate>(
    'SELECT * FROM meme_templates WHERE active=true ORDER BY RANDOM() LIMIT 1'
  );
  if (!rows[0]) throw new Error('No meme templates available.');
  return rows[0];
}

function escapeXml(str: string): string {
  return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
