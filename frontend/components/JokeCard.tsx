// components/JokeCard.tsx — Core joke display with actions
'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';
import { useAuthStore } from '@/store/authStore';

interface Joke {
  id: string;
  text: string;
  category: string;
  source: 'cache' | 'embedding' | 'ai';
}

interface JokeCardProps {
  joke: Joke;
  onNext: () => void;
  onLoading: boolean;
}

export function JokeCard({ joke, onNext, onLoading }: JokeCardProps) {
  const { isAuthenticated } = useAuthStore();
  const [rating, setRating] = useState<'like' | 'dislike' | 'favorite' | null>(null);
  const [showShare, setShowShare] = useState(false);

  const handleRate = async (r: 'like' | 'dislike' | 'favorite') => {
    if (!isAuthenticated) {
      toast('Sign in to rate jokes!', { icon: '😄' });
      return;
    }
    setRating(r);
    await api.rateJoke(joke.id, r);
    if (r === 'like' || r === 'favorite') {
      toast(r === 'favorite' ? 'Added to favorites! ❤️' : 'Liked! 👍', { duration: 1500 });
    }
  };

  const handleShare = async (platform: string) => {
    const text = `😂 Joke from JokeAI\n\n${joke.text}\n\nTry it yourself:\n${window.location.origin}`;

    if (platform === 'copy') {
      await navigator.clipboard.writeText(text);
      toast.success('Copied to clipboard!');
    } else if (platform === 'whatsapp') {
      window.open(`https://wa.me/?text=${encodeURIComponent(text)}`);
    } else if (platform === 'telegram') {
      window.open(`https://t.me/share/url?url=${encodeURIComponent(window.location.origin)}&text=${encodeURIComponent(`😂 ${joke.text}`)}`);
    }

    if (isAuthenticated) {
      await api.rateJoke(joke.id, rating || 'like', true);
    }
    setShowShare(false);
  };

  const handleMeme = async () => {
    toast.loading('Creating meme...', { id: 'meme' });
    try {
      const { url } = await api.generateMeme(joke.id, joke.text);
      toast.dismiss('meme');
      window.open(url, '_blank');
    } catch {
      toast.error('Could not generate meme', { id: 'meme' });
    }
  };

  return (
    <AnimatePresence mode="wait">
      <motion.div
        key={joke.id}
        initial={{ opacity: 0, y: 40, scale: 0.95 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -40, scale: 0.95 }}
        transition={{ type: 'spring', stiffness: 300, damping: 28 }}
        className="relative w-full max-w-lg mx-auto"
      >
        {/* Main card */}
        <div className="bg-white dark:bg-zinc-900 rounded-3xl shadow-2xl overflow-hidden border border-zinc-100 dark:border-zinc-800">
          
          {/* Category badge */}
          <div className="px-6 pt-6 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-widest text-amber-500 bg-amber-50 dark:bg-amber-900/20 px-3 py-1 rounded-full">
              {joke.category}
            </span>
            <span className="text-xs text-zinc-400">
              {joke.source === 'ai' ? '✨ Fresh AI' : joke.source === 'embedding' ? '🔍 Matched' : '⚡ Cached'}
            </span>
          </div>

          {/* Joke text */}
          <div className="px-8 py-10 min-h-[200px] flex items-center justify-center">
            <p className="text-2xl md:text-3xl font-semibold text-zinc-800 dark:text-zinc-100 text-center leading-relaxed">
              {joke.text}
            </p>
          </div>

          {/* Action bar */}
          <div className="px-6 pb-6 space-y-3">
            {/* Rating buttons */}
            <div className="flex items-center justify-center gap-3">
              {[
                { key: 'like',     icon: '👍', label: 'Like'     },
                { key: 'dislike',  icon: '👎', label: 'Dislike'  },
                { key: 'favorite', icon: '❤️',  label: 'Favorite' },
              ].map(({ key, icon, label }) => (
                <motion.button
                  key={key}
                  whileTap={{ scale: 0.88 }}
                  onClick={() => handleRate(key as any)}
                  className={`flex flex-col items-center gap-1 px-4 py-2 rounded-2xl text-sm font-medium transition-all ${
                    rating === key
                      ? 'bg-amber-400 text-amber-900 shadow-md'
                      : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-700'
                  }`}
                >
                  <span className="text-xl">{icon}</span>
                  <span>{label}</span>
                </motion.button>
              ))}
            </div>

            {/* Secondary actions */}
            <div className="flex gap-2">
              <motion.button
                whileTap={{ scale: 0.96 }}
                onClick={() => setShowShare(!showShare)}
                className="flex-1 flex items-center justify-center gap-2 py-3 rounded-2xl bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 font-medium hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-all"
              >
                📤 Share
              </motion.button>
              <motion.button
                whileTap={{ scale: 0.96 }}
                onClick={handleMeme}
                className="flex-1 flex items-center justify-center gap-2 py-3 rounded-2xl bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 font-medium hover:bg-zinc-200 dark:hover:bg-zinc-700 transition-all"
              >
                🖼️ Meme
              </motion.button>
            </div>

            {/* Share panel */}
            <AnimatePresence>
              {showShare && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="flex gap-2 overflow-hidden"
                >
                  {[
                    { key: 'whatsapp', icon: '💬', label: 'WhatsApp' },
                    { key: 'telegram', icon: '✈️', label: 'Telegram' },
                    { key: 'copy',     icon: '📋', label: 'Copy'     },
                  ].map(({ key, icon, label }) => (
                    <button
                      key={key}
                      onClick={() => handleShare(key)}
                      className="flex-1 flex flex-col items-center gap-1 py-3 rounded-xl bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 text-sm font-medium hover:bg-blue-100 transition-all"
                    >
                      <span className="text-lg">{icon}</span>
                      <span>{label}</span>
                    </button>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Next button */}
        <motion.button
          whileTap={{ scale: 0.95 }}
          onClick={onNext}
          disabled={onLoading}
          className="mt-4 w-full py-4 rounded-2xl bg-gradient-to-r from-amber-400 to-orange-500 text-white font-bold text-lg shadow-lg hover:shadow-xl transition-all disabled:opacity-50"
        >
          {onLoading ? '✨ Generating...' : 'Next Joke ➡'}
        </motion.button>
      </motion.div>
    </AnimatePresence>
  );
}
