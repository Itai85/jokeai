// app/auth/page.tsx — Login & Registration
'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast, { Toaster } from 'react-hot-toast';
import { api } from '@/lib/api';

type Mode = 'login' | 'register';

export default function AuthPage() {
  const [mode, setMode] = useState<Mode>('login');
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    email: '', password: '', username: '',
    age_verified: false, accepted_tos: false,
  });

  const set = (k: string, v: any) => setForm(f => ({ ...f, [k]: v }));

  const handleSubmit = async () => {
    setLoading(true);
    try {
      let data;
      if (mode === 'login') {
        data = await api.login(form.email, form.password);
      } else {
        if (!form.accepted_tos) { toast.error('Accept the terms to continue.'); setLoading(false); return; }
        data = await api.register(form);
      }
      localStorage.setItem('token', data.token);
      localStorage.setItem('userId', data.userId);
      toast.success(mode === 'login' ? 'Welcome back! 😄' : 'Account created! 🎉');
      setTimeout(() => window.location.href = '/', 800);
    } catch (e: any) {
      toast.error(e.response?.data?.error || 'Something went wrong.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 flex flex-col items-center justify-center p-4">
      <Toaster position="top-center" />

      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="text-6xl mb-3">😂</div>
          <h1 className="text-3xl font-bold text-zinc-800 dark:text-zinc-100">JokeAI</h1>
          <p className="text-zinc-500 mt-1">Humor, personalized by AI</p>
        </div>

        {/* Card */}
        <div className="bg-white dark:bg-zinc-900 rounded-3xl shadow-xl border border-zinc-100 dark:border-zinc-800 p-6 space-y-4">
          {/* Mode toggle */}
          <div className="flex gap-1 bg-zinc-100 dark:bg-zinc-800 rounded-2xl p-1">
            {(['login', 'register'] as Mode[]).map(m => (
              <button key={m} onClick={() => setMode(m)}
                className={`flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all capitalize ${
                  mode === m ? 'bg-white dark:bg-zinc-700 shadow-sm text-zinc-800 dark:text-zinc-100' : 'text-zinc-500'
                }`}
              >{m === 'login' ? 'Sign In' : 'Register'}</button>
            ))}
          </div>

          <AnimatePresence mode="wait">
            <motion.div key={mode} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="space-y-3">

              {mode === 'register' && (
                <div>
                  <label className="text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1 block">Username</label>
                  <input type="text" placeholder="e.g. jokester99" value={form.username}
                    onChange={e => set('username', e.target.value)}
                    className="w-full px-4 py-3 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-400"
                  />
                </div>
              )}

              <div>
                <label className="text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1 block">Email</label>
                <input type="email" placeholder="you@example.com" value={form.email}
                  onChange={e => set('email', e.target.value)}
                  className="w-full px-4 py-3 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-400"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1 block">Password</label>
                <input type="password" placeholder="Min. 8 characters" value={form.password}
                  onChange={e => set('password', e.target.value)}
                  className="w-full px-4 py-3 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-amber-400"
                />
              </div>

              {mode === 'register' && (
                <div className="space-y-2 pt-1">
                  {[
                    { key: 'age_verified', label: 'I confirm I am 18 years or older' },
                    { key: 'accepted_tos', label: 'I accept the Terms of Service and understand jokes may include satire' },
                  ].map(({ key, label }) => (
                    <label key={key} className="flex items-start gap-3 cursor-pointer">
                      <input type="checkbox" checked={(form as any)[key]}
                        onChange={e => set(key, e.target.checked)}
                        className="mt-0.5 w-4 h-4 rounded accent-amber-500"
                      />
                      <span className="text-sm text-zinc-600 dark:text-zinc-400">{label}</span>
                    </label>
                  ))}
                </div>
              )}

              <motion.button whileTap={{ scale: 0.97 }}
                onClick={handleSubmit} disabled={loading}
                className="w-full py-4 rounded-2xl bg-gradient-to-r from-amber-400 to-orange-500 text-white font-bold text-base shadow-lg disabled:opacity-60 mt-2"
              >
                {loading ? '...' : mode === 'login' ? 'Sign In 🚀' : 'Create Account 🎉'}
              </motion.button>
            </motion.div>
          </AnimatePresence>
        </div>

        <p className="text-center text-sm text-zinc-500 mt-4">
          <a href="/" className="hover:text-zinc-700 dark:hover:text-zinc-300 transition-colors">← Back to jokes</a>
        </p>
      </div>
    </div>
  );
}
