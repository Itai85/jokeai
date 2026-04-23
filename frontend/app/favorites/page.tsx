// app/favorites/page.tsx
'use client';
import { useState, useEffect } from 'react';
import toast, { Toaster } from 'react-hot-toast';
import { api } from '@/lib/api';

interface Joke { id: string; text: string; category: string; created_at: string; }

export default function FavoritesPage() {
  const [jokes, setJokes] = useState<Joke[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getFavorites()
      .then(d => setJokes(d.favorites))
      .catch(() => toast.error('Could not load favorites'))
      .finally(() => setLoading(false));
  }, []);

  const share = async (joke: Joke, platform: string) => {
    const text = `😂 Joke from JokeAI\n\n${joke.text}\n\nTry it: ${window.location.origin}`;
    if (platform === 'copy') { await navigator.clipboard.writeText(text); toast.success('Copied!'); }
    else if (platform === 'whatsapp') window.open(`https://wa.me/?text=${encodeURIComponent(text)}`);
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 pb-24">
      <Toaster position="top-center" />
      <header className="sticky top-0 bg-white/90 dark:bg-zinc-950/90 backdrop-blur border-b border-zinc-100 dark:border-zinc-800 px-4 py-3 flex items-center gap-3">
        <a href="/" className="text-zinc-500">←</a>
        <h1 className="font-bold text-zinc-800 dark:text-zinc-100">❤️ My Favorites</h1>
      </header>
      <div className="max-w-lg mx-auto px-4 py-6 space-y-3">
        {loading ? (
          <div className="flex justify-center py-20"><div className="text-5xl animate-bounce">❤️</div></div>
        ) : jokes.length === 0 ? (
          <div className="text-center py-20">
            <div className="text-5xl mb-4">😅</div>
            <p className="text-zinc-500">No favorites yet. Go like some jokes!</p>
            <a href="/" className="mt-4 inline-block px-6 py-3 rounded-2xl bg-gradient-to-r from-amber-400 to-orange-500 text-white font-bold">Get Jokes →</a>
          </div>
        ) : jokes.map(joke => (
          <div key={joke.id} className="bg-white dark:bg-zinc-900 rounded-2xl border border-zinc-100 dark:border-zinc-800 p-5">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-bold uppercase tracking-wide text-amber-500 bg-amber-50 dark:bg-amber-900/20 px-2 py-0.5 rounded-full">{joke.category}</span>
              <span className="text-xs text-zinc-400">{new Date(joke.created_at).toLocaleDateString()}</span>
            </div>
            <p className="text-zinc-800 dark:text-zinc-100 font-medium leading-relaxed mb-3">{joke.text}</p>
            <div className="flex gap-2">
              <button onClick={() => share(joke, 'copy')} className="flex-1 py-2 rounded-xl bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-400 text-sm font-semibold">📋 Copy</button>
              <button onClick={() => share(joke, 'whatsapp')} className="flex-1 py-2 rounded-xl bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 text-sm font-semibold">💬 Share</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
