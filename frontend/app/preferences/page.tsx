// app/preferences/page.tsx — Humor Preferences Setup
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import toast, { Toaster } from 'react-hot-toast';
import { api } from '@/lib/api';

const HUMOR_TYPES = [
  { key: 'dad jokes',         icon: '👨', label: 'Dad Jokes',         desc: 'Groan-worthy classics' },
  { key: 'tech jokes',        icon: '💻', label: 'Tech Humor',         desc: 'For nerds & devs' },
  { key: 'relationship jokes',icon: '💕', label: 'Relationship',       desc: 'Dating & couples' },
  { key: 'absurd humor',      icon: '🌀', label: 'Absurd / Surreal',   desc: 'Random & weird' },
  { key: 'dark humor',        icon: '🖤', label: 'Dark Humor',         desc: 'Not for everyone' },
  { key: 'work humor',        icon: '💼', label: 'Work Humor',         desc: 'Office life pain' },
];

const LANGUAGES = [
  { key: 'en', label: '🇺🇸 English' },
  { key: 'he', label: '🇮🇱 Hebrew' },
];

export default function PreferencesPage() {
  const [selectedTypes, setSelectedTypes] = useState<string[]>(['dad jokes', 'absurd humor']);
  const [intensity, setIntensity] = useState(3);
  const [language, setLanguage]   = useState('en');
  const [safeMode, setSafeMode]   = useState(true);
  const [sexual, setSexual]       = useState(false);
  const [loading, setLoading]     = useState(false);
  const [ageVerified, setAgeVerified] = useState(false);

  useEffect(() => {
    // Try to load existing prefs
    api.getProfile().then(p => {
      if (p.humor_types) setSelectedTypes(p.humor_types);
      if (p.intensity)   setIntensity(p.intensity);
      if (p.language)    setLanguage(p.language);
      if (p.safe_mode !== undefined) setSafeMode(p.safe_mode);
      if (p.sexual_content !== undefined) setSexual(p.sexual_content);
      setAgeVerified(p.age_verified);
    }).catch(() => {});
  }, []);

  const toggleType = (key: string) => {
    setSelectedTypes(prev =>
      prev.includes(key) ? prev.filter(k => k !== key) : [...prev, key]
    );
  };

  const save = async () => {
    if (selectedTypes.length === 0) { toast.error('Pick at least one humor style!'); return; }
    setLoading(true);
    try {
      await api.updatePreferences({ humor_types: selectedTypes, intensity, language, safe_mode: safeMode, sexual_content: sexual });
      toast.success('Preferences saved! 🎉');
      setTimeout(() => window.location.href = '/', 600);
    } catch (e: any) {
      toast.error(e.response?.data?.error || 'Save failed.');
    } finally { setLoading(false); }
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 pb-24">
      <Toaster position="top-center" />

      <header className="sticky top-0 bg-white/90 dark:bg-zinc-950/90 backdrop-blur border-b border-zinc-100 dark:border-zinc-800 px-4 py-3 flex items-center gap-3">
        <a href="/" className="text-zinc-500 hover:text-zinc-700">←</a>
        <h1 className="font-bold text-zinc-800 dark:text-zinc-100">Humor Preferences</h1>
      </header>

      <div className="max-w-lg mx-auto px-4 py-6 space-y-8">

        {/* Humor types */}
        <section>
          <h2 className="text-lg font-bold text-zinc-800 dark:text-zinc-100 mb-3">What makes you laugh?</h2>
          <div className="grid grid-cols-2 gap-2">
            {HUMOR_TYPES.map(({ key, icon, label, desc }) => {
              const selected = selectedTypes.includes(key);
              return (
                <motion.button key={key} whileTap={{ scale: 0.95 }}
                  onClick={() => toggleType(key)}
                  className={`flex flex-col items-start gap-1 p-4 rounded-2xl border-2 text-left transition-all ${
                    selected
                      ? 'border-amber-400 bg-amber-50 dark:bg-amber-900/20'
                      : 'border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900'
                  }`}
                >
                  <span className="text-2xl">{icon}</span>
                  <span className={`font-semibold text-sm ${selected ? 'text-amber-700 dark:text-amber-400' : 'text-zinc-800 dark:text-zinc-100'}`}>{label}</span>
                  <span className="text-xs text-zinc-500">{desc}</span>
                </motion.button>
              );
            })}
          </div>
        </section>

        {/* Intensity */}
        <section>
          <h2 className="text-lg font-bold text-zinc-800 dark:text-zinc-100 mb-1">Intensity</h2>
          <p className="text-sm text-zinc-500 mb-4">How edgy can we go?</p>
          <div className="space-y-2">
            <input type="range" min={1} max={5} value={intensity}
              onChange={e => setIntensity(parseInt(e.target.value))}
              className="w-full accent-amber-500"
            />
            <div className="flex justify-between text-xs text-zinc-500">
              <span>😇 Very mild</span>
              <span className="font-semibold text-amber-600">Level {intensity}</span>
              <span>😈 Extreme</span>
            </div>
          </div>
        </section>

        {/* Language */}
        <section>
          <h2 className="text-lg font-bold text-zinc-800 dark:text-zinc-100 mb-3">Language</h2>
          <div className="flex gap-2">
            {LANGUAGES.map(({ key, label }) => (
              <button key={key} onClick={() => setLanguage(key)}
                className={`flex-1 py-3 rounded-xl border-2 font-semibold text-sm transition-all ${
                  language === key ? 'border-amber-400 bg-amber-50 dark:bg-amber-900/20 text-amber-700 dark:text-amber-400' : 'border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400'
                }`}
              >{label}</button>
            ))}
          </div>
        </section>

        {/* Safe mode */}
        <section className="space-y-3">
          <h2 className="text-lg font-bold text-zinc-800 dark:text-zinc-100">Content Settings</h2>
          <div className="flex items-center justify-between p-4 rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-100 dark:border-zinc-800">
            <div>
              <p className="font-semibold text-zinc-800 dark:text-zinc-100 text-sm">Safe Humor Mode</p>
              <p className="text-xs text-zinc-500">Avoid offensive or extreme content</p>
            </div>
            <button onClick={() => setSafeMode(!safeMode)}
              className={`relative w-12 h-6 rounded-full transition-all ${safeMode ? 'bg-amber-400' : 'bg-zinc-300 dark:bg-zinc-600'}`}
            >
              <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all ${safeMode ? 'left-6' : 'left-0.5'}`} />
            </button>
          </div>

          {ageVerified && (
            <div className="flex items-center justify-between p-4 rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-100 dark:border-zinc-800">
              <div>
                <p className="font-semibold text-zinc-800 dark:text-zinc-100 text-sm">Adult Humor</p>
                <p className="text-xs text-zinc-500">Age-verified · 18+ only</p>
              </div>
              <button onClick={() => setSexual(!sexual)}
                className={`relative w-12 h-6 rounded-full transition-all ${sexual ? 'bg-red-400' : 'bg-zinc-300 dark:bg-zinc-600'}`}
              >
                <span className={`absolute top-0.5 w-5 h-5 bg-white rounded-full shadow transition-all ${sexual ? 'left-6' : 'left-0.5'}`} />
              </button>
            </div>
          )}
        </section>

        <motion.button whileTap={{ scale: 0.97 }}
          onClick={save} disabled={loading}
          className="w-full py-4 rounded-2xl bg-gradient-to-r from-amber-400 to-orange-500 text-white font-bold text-lg shadow-lg disabled:opacity-60"
        >{loading ? 'Saving...' : 'Save Preferences 🎉'}</motion.button>
      </div>
    </div>
  );
}
