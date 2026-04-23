// ─── lib/api.ts — Typed API client ────────────────────────────────────────────
import axios from 'axios';

const BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:4000/api';

const http = axios.create({ baseURL: BASE, timeout: 15000 });

// Attach token from localStorage
http.interceptors.request.use((config) => {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

export const api = {
  // Auth
  register: (data: any) => http.post('/auth/register', data).then(r => r.data),
  login: (email: string, password: string) =>
    http.post('/auth/login', { email, password }).then(r => r.data),
  loginGoogle: (googleData: any) =>
    http.post('/auth/google', googleData).then(r => r.data),
  verifyAge: () => http.post('/auth/verify-age').then(r => r.data),

  // Jokes
  getJoke: (seenIds: string[] = []) =>
    http.get('/jokes/generate', { params: { seen: seenIds.join(',') } }).then(r => r.data),
  rateJoke: (joke_id: string, rating: string, shared = false) =>
    http.post('/jokes/rate', { joke_id, rating, shared }).then(r => r.data),
  getHistory: (page = 1) =>
    http.get('/jokes/history', { params: { page } }).then(r => r.data),
  getFavorites: () =>
    http.get('/jokes/favorites').then(r => r.data),
  updatePreferences: (prefs: any) =>
    http.put('/jokes/preferences', prefs).then(r => r.data),

  // Profile
  getProfile: () => http.get('/profile/me').then(r => r.data),
  uploadPhoto: (file: File) => {
    const form = new FormData();
    form.append('photo', file);
    return http.post('/profile/photo', form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }).then(r => r.data);
  },
  generateCartoon: (force = false) =>
    http.post('/profile/cartoon', { force }).then(r => r.data),
  setAvatarType: (type: 'original' | 'cartoon') =>
    http.put('/profile/avatar-type', { type }).then(r => r.data),

  // Roast
  roastFriend: (name: string, job: string, fact: string) =>
    http.post('/roast/friend', { name, job, fact }).then(r => r.data),
  roastPhoto: (file: File) => {
    const form = new FormData();
    form.append('photo', file);
    return http.post('/roast/photo', form, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }).then(r => r.data);
  },

  // Meme
  generateMeme: (joke_id?: string, joke_text?: string, template_id?: string) =>
    http.post('/meme/generate', { joke_id, joke_text, template_id }).then(r => r.data),
  getMemeTemplates: () => http.get('/meme/templates').then(r => r.data),

  // Battle
  createBattle: () => http.post('/battle/create').then(r => r.data),
  joinBattle: (token: string) => http.post(`/battle/join/${token}`).then(r => r.data),
  voteBattle: (battleId: string, voted_for: 'a' | 'b') =>
    http.post(`/battle/${battleId}/vote`, { voted_for }).then(r => r.data),
  getBattle: (token: string) => http.get(`/battle/${token}`).then(r => r.data),
};


// ─── store/authStore.ts — Zustand global auth state ───────────────────────────
import { create } from 'zustand';

interface AuthState {
  token: string | null;
  userId: string | null;
  isAuthenticated: boolean;
  setAuth: (token: string, userId: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: typeof window !== 'undefined' ? localStorage.getItem('token') : null,
  userId: typeof window !== 'undefined' ? localStorage.getItem('userId') : null,
  isAuthenticated: typeof window !== 'undefined' ? !!localStorage.getItem('token') : false,
  setAuth: (token, userId) => {
    localStorage.setItem('token', token);
    localStorage.setItem('userId', userId);
    set({ token, userId, isAuthenticated: true });
  },
  logout: () => {
    localStorage.removeItem('token');
    localStorage.removeItem('userId');
    set({ token: null, userId: null, isAuthenticated: false });
  },
}));


// ─── store/jokeStore.ts — Joke session state ──────────────────────────────────
import { create } from 'zustand';

interface Joke {
  id: string;
  text: string;
  category: string;
  source: string;
}

interface JokeState {
  currentJoke: Joke | null;
  seenIds: string[];
  isLoading: boolean;
  setJoke: (joke: Joke) => void;
  setLoading: (v: boolean) => void;
  addSeen: (id: string) => void;
}

export const useJokeStore = create<JokeState>((set, get) => ({
  currentJoke: null,
  seenIds: [],
  isLoading: false,
  setJoke: (joke) => {
    set({ currentJoke: joke });
    get().addSeen(joke.id);
  },
  setLoading: (v) => set({ isLoading: v }),
  addSeen: (id) => set((s) => ({
    seenIds: [...s.seenIds.slice(-50), id] // Keep last 50
  })),
}));


// ─── components/RoastFriend.tsx ────────────────────────────────────────────────
'use client';
import { useState } from 'react';
import { motion } from 'framer-motion';
import toast from 'react-hot-toast';
import { api } from '@/lib/api';

export function RoastFriend() {
  const [form, setForm] = useState({ name: '', job: '', fact: '' });
  const [result, setResult] = useState<{ text: string; shareText: string } | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async () => {
    if (!form.name || !form.job || !form.fact) {
      toast.error('Fill in all fields!');
      return;
    }
    setLoading(true);
    try {
      const data = await api.roastFriend(form.name, form.job, form.fact);
      setResult(data);
    } catch {
      toast.error('Roast failed! Try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="w-full max-w-lg mx-auto space-y-4">
      <h2 className="text-2xl font-bold text-zinc-800 dark:text-zinc-100">🔥 Roast a Friend</h2>
      
      {!result ? (
        <div className="space-y-3">
          {[
            { key: 'name', label: "Friend's name",   placeholder: 'e.g. Alex' },
            { key: 'job',  label: "Their job",        placeholder: 'e.g. Software Engineer' },
            { key: 'fact', label: "A fun fact about them", placeholder: 'e.g. Always late to meetings' },
          ].map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="block text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1">{label}</label>
              <input
                type="text"
                placeholder={placeholder}
                value={(form as any)[key]}
                onChange={(e) => setForm({ ...form, [key]: e.target.value })}
                className="w-full px-4 py-3 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-400"
              />
            </div>
          ))}
          <motion.button
            whileTap={{ scale: 0.96 }}
            onClick={handleSubmit}
            disabled={loading}
            className="w-full py-4 rounded-2xl bg-gradient-to-r from-red-500 to-orange-500 text-white font-bold text-lg disabled:opacity-50"
          >
            {loading ? '🔥 Roasting...' : '🔥 Roast Them!'}
          </motion.button>
        </div>
      ) : (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="space-y-4"
        >
          <div className="bg-gradient-to-br from-red-50 to-orange-50 dark:from-red-900/20 dark:to-orange-900/20 rounded-2xl p-6 border border-red-100 dark:border-red-800">
            <p className="text-xl font-semibold text-zinc-800 dark:text-zinc-100">{result.text}</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => { navigator.clipboard.writeText(result.shareText); toast.success('Copied!'); }}
              className="flex-1 py-3 rounded-xl bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 font-medium"
            >📋 Copy</button>
            <button
              onClick={() => window.open(`https://wa.me/?text=${encodeURIComponent(result.shareText)}`)}
              className="flex-1 py-3 rounded-xl bg-green-100 dark:bg-green-900/20 text-green-700 dark:text-green-300 font-medium"
            >💬 WhatsApp</button>
          </div>
          <button
            onClick={() => setResult(null)}
            className="w-full py-3 text-zinc-500 hover:text-zinc-700 transition-colors"
          >← Roast someone else</button>
        </motion.div>
      )}
    </div>
  );
}
