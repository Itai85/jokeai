// app/page.tsx — Main JokeAI app page
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import toast, { Toaster } from 'react-hot-toast';
import { api } from '@/lib/api';

// ─── Types ────────────────────────────────────────────────────────────────────
interface Joke { id: string; text: string; category: string; source: string; }

type Tab = 'jokes' | 'roast' | 'battle' | 'profile';

// ─── Main Page ────────────────────────────────────────────────────────────────
export default function HomePage() {
  const [tab, setTab]             = useState<Tab>('jokes');
  const [joke, setJoke]           = useState<Joke | null>(null);
  const [loading, setLoading]     = useState(false);
  const [seenIds, setSeenIds]     = useState<string[]>([]);
  const [rating, setRating]       = useState<string | null>(null);
  const [showShare, setShowShare] = useState(false);
  const [showDisclaimer, setShowDisclaimer] = useState(false);
  const [tosAccepted, setTosAccepted]       = useState(false);

  // Check TOS on first load
  useEffect(() => {
    const accepted = localStorage.getItem('tos_accepted');
    if (!accepted) setShowDisclaimer(true);
    else { setTosAccepted(true); fetchJoke([]); }
  }, []);

  const fetchJoke = useCallback(async (seen: string[]) => {
    setLoading(true);
    setRating(null);
    setShowShare(false);
    try {
      const data = await api.getJoke(seen);
      setJoke(data);
      setSeenIds(prev => [...prev.slice(-49), data.id]);
    } catch {
      toast.error('Could not load joke. Try again!');
    } finally { setLoading(false); }
  }, []);

  const acceptTos = () => {
    localStorage.setItem('tos_accepted', '1');
    setTosAccepted(true);
    setShowDisclaimer(false);
    fetchJoke([]);
  };

  const handleRate = async (r: string) => {
    if (!joke) return;
    setRating(r);
    const token = localStorage.getItem('token');
    if (!token) { toast('Sign in to save ratings', { icon: '😊' }); return; }
    try { await api.rateJoke(joke.id, r); } catch {}
    if (r === 'favorite') toast.success('Added to favorites! ❤️');
  };

  const handleShare = async (platform: string) => {
    if (!joke) return;
    const text = `😂 Joke from JokeAI\n\n${joke.text}\n\nTry it: ${window.location.origin}`;
    if (platform === 'copy') { await navigator.clipboard.writeText(text); toast.success('Copied!'); }
    else if (platform === 'whatsapp') window.open(`https://wa.me/?text=${encodeURIComponent(text)}`);
    else if (platform === 'telegram') window.open(`https://t.me/share/url?url=${encodeURIComponent(window.location.origin)}&text=${encodeURIComponent(`😂 ${joke.text}`)}`);
    setShowShare(false);
  };

  const handleMeme = async () => {
    if (!joke) return;
    const toastId = toast.loading('Creating meme...');
    try {
      const { url } = await api.generateMeme(joke.id, joke.text);
      toast.dismiss(toastId);
      window.open(url, '_blank');
      toast.success('Meme ready! 🖼️');
    } catch { toast.error('Meme failed', { id: toastId }); }
  };

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 font-sans">
      <Toaster position="top-center" toastOptions={{ style: { borderRadius: '14px', fontWeight: '500' } }} />

      {/* Disclaimer Modal */}
      <AnimatePresence>
        {showDisclaimer && (
          <motion.div
            initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={{ background: 'rgba(0,0,0,0.6)' }}
          >
            <motion.div
              initial={{ scale: 0.9, y: 20 }} animate={{ scale: 1, y: 0 }}
              className="bg-white dark:bg-zinc-900 rounded-3xl p-8 max-w-sm w-full text-center shadow-2xl"
            >
              <div className="text-5xl mb-4">😂</div>
              <h2 className="text-xl font-bold text-zinc-800 dark:text-zinc-100 mb-3">Welcome to JokeAI</h2>
              <p className="text-zinc-600 dark:text-zinc-400 text-sm leading-relaxed mb-6">
                This app generates jokes for entertainment purposes. Some jokes may include satire or provocative humor. Personalized to your taste — always your choice.
              </p>
              <button
                onClick={acceptTos}
                className="w-full py-4 rounded-2xl bg-gradient-to-r from-amber-400 to-orange-500 text-white font-bold text-lg"
              >I Get It, Let's Laugh! 😄</button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Header */}
      <header className="sticky top-0 z-40 bg-white/90 dark:bg-zinc-950/90 backdrop-blur border-b border-zinc-100 dark:border-zinc-800">
        <div className="max-w-lg mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-2xl">😂</span>
            <span className="text-lg font-bold text-zinc-800 dark:text-zinc-100 tracking-tight">JokeAI</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => window.location.href = '/auth'}
              className="text-sm font-medium text-amber-600 hover:text-amber-700 px-3 py-1.5 rounded-lg hover:bg-amber-50 transition-all"
            >Sign In</button>
          </div>
        </div>
      </header>

      {/* Tab navigation */}
      <div className="max-w-lg mx-auto px-4 py-3">
        <div className="flex gap-1 bg-zinc-100 dark:bg-zinc-900 rounded-2xl p-1">
          {([
            { key: 'jokes',   icon: '😂', label: 'Jokes'   },
            { key: 'roast',   icon: '🔥', label: 'Roast'   },
            { key: 'battle',  icon: '⚔️', label: 'Battle'  },
            { key: 'profile', icon: '👤', label: 'Me'      },
          ] as const).map(({ key, icon, label }) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-xl text-sm font-semibold transition-all ${
                tab === key
                  ? 'bg-white dark:bg-zinc-800 text-zinc-800 dark:text-zinc-100 shadow-sm'
                  : 'text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300'
              }`}
            >
              <span>{icon}</span>
              <span className="hidden sm:inline">{label}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Main content */}
      <main className="max-w-lg mx-auto px-4 pb-24">
        <AnimatePresence mode="wait">

          {/* ── JOKES TAB ── */}
          {tab === 'jokes' && (
            <motion.div key="jokes"
              initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }}
            >
              {loading && !joke ? (
                <div className="flex flex-col items-center justify-center py-20 gap-4">
                  <div className="text-5xl animate-bounce">😂</div>
                  <p className="text-zinc-500">Crafting your perfect joke...</p>
                </div>
              ) : joke ? (
                <div className="space-y-4 pt-2">
                  {/* Joke card */}
                  <AnimatePresence mode="wait">
                    <motion.div key={joke.id}
                      initial={{ opacity: 0, y: 30 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -30 }}
                      className="bg-white dark:bg-zinc-900 rounded-3xl shadow-xl border border-zinc-100 dark:border-zinc-800 overflow-hidden"
                    >
                      <div className="px-6 pt-5 flex items-center justify-between">
                        <span className="text-xs font-bold uppercase tracking-widest text-amber-500 bg-amber-50 dark:bg-amber-900/20 px-3 py-1 rounded-full">
                          {joke.category}
                        </span>
                        <span className="text-xs text-zinc-400">
                          {joke.source === 'ai' ? '✨ Fresh' : joke.source === 'embedding' ? '🔍 Matched' : '⚡ Fast'}
                        </span>
                      </div>
                      <div className="px-8 py-10 min-h-48 flex items-center justify-center">
                        <p className="text-2xl font-semibold text-center text-zinc-800 dark:text-zinc-100 leading-relaxed">
                          {joke.text}
                        </p>
                      </div>
                    </motion.div>
                  </AnimatePresence>

                  {/* Ratings */}
                  <div className="flex gap-2">
                    {[['👍','like'],['👎','dislike'],['❤️','favorite']].map(([icon, r]) => (
                      <motion.button key={r} whileTap={{ scale: 0.85 }}
                        onClick={() => handleRate(r)}
                        className={`flex-1 flex flex-col items-center gap-1 py-3 rounded-2xl text-sm font-semibold transition-all ${
                          rating === r ? 'bg-amber-400 text-amber-900 shadow-md' : 'bg-zinc-100 dark:bg-zinc-800 text-zinc-500 hover:bg-zinc-200'
                        }`}
                      >
                        <span className="text-xl">{icon}</span>
                        <span className="capitalize">{r}</span>
                      </motion.button>
                    ))}
                  </div>

                  {/* Actions */}
                  <div className="flex gap-2">
                    <motion.button whileTap={{ scale: 0.96 }}
                      onClick={() => setShowShare(!showShare)}
                      className="flex-1 py-3.5 rounded-2xl bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 font-semibold"
                    >📤 Share</motion.button>
                    <motion.button whileTap={{ scale: 0.96 }}
                      onClick={handleMeme}
                      className="flex-1 py-3.5 rounded-2xl bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 font-semibold"
                    >🖼️ Meme</motion.button>
                  </div>

                  {/* Share options */}
                  <AnimatePresence>
                    {showShare && (
                      <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: 'auto' }} exit={{ opacity: 0, height: 0 }} className="flex gap-2">
                        {[['💬','whatsapp','WhatsApp'],['✈️','telegram','Telegram'],['📋','copy','Copy']].map(([icon, key, label]) => (
                          <button key={key} onClick={() => handleShare(key)}
                            className="flex-1 flex flex-col items-center gap-1 py-3 rounded-xl bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 text-sm font-semibold"
                          ><span className="text-lg">{icon}</span><span>{label}</span></button>
                        ))}
                      </motion.div>
                    )}
                  </AnimatePresence>

                  {/* Next button */}
                  <motion.button whileTap={{ scale: 0.97 }}
                    onClick={() => fetchJoke(seenIds)}
                    disabled={loading}
                    className="w-full py-4 rounded-2xl bg-gradient-to-r from-amber-400 to-orange-500 text-white font-bold text-lg shadow-lg hover:shadow-xl transition-all disabled:opacity-60"
                  >{loading ? '✨ Generating...' : 'Next Joke ➡'}</motion.button>
                </div>
              ) : null}
            </motion.div>
          )}

          {/* ── ROAST TAB ── */}
          {tab === 'roast' && (
            <motion.div key="roast" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
              <RoastSection />
            </motion.div>
          )}

          {/* ── BATTLE TAB ── */}
          {tab === 'battle' && (
            <motion.div key="battle" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
              <BattleSection />
            </motion.div>
          )}

          {/* ── PROFILE TAB ── */}
          {tab === 'profile' && (
            <motion.div key="profile" initial={{ opacity: 0, x: 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -20 }}>
              <ProfileSection />
            </motion.div>
          )}

        </AnimatePresence>
      </main>
    </div>
  );
}

// ─── ROAST SECTION ────────────────────────────────────────────────────────────
function RoastSection() {
  const [mode, setMode] = useState<'friend' | 'photo'>('friend');
  const [form, setForm] = useState({ name: '', job: '', fact: '' });
  const [result, setResult] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleFriendRoast = async () => {
    if (!form.name || !form.job || !form.fact) { toast.error('Fill all fields!'); return; }
    setLoading(true);
    try {
      const data = await api.roastFriend(form.name, form.job, form.fact);
      setResult(data.text);
    } catch { toast.error('Roast failed!'); } finally { setLoading(false); }
  };

  const handlePhotoRoast = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return;
    setLoading(true);
    try {
      const data = await api.roastPhoto(file);
      setResult(data.text);
    } catch { toast.error('Photo roast failed!'); } finally { setLoading(false); }
  };

  return (
    <div className="pt-2 space-y-4">
      <h2 className="text-2xl font-bold text-zinc-800 dark:text-zinc-100">🔥 Roast Mode</h2>
      <div className="flex gap-1 bg-zinc-100 dark:bg-zinc-900 rounded-2xl p-1">
        {(['friend','photo'] as const).map(m => (
          <button key={m} onClick={() => { setMode(m); setResult(null); }}
            className={`flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all ${mode===m?'bg-white dark:bg-zinc-800 shadow-sm text-zinc-800 dark:text-zinc-100':'text-zinc-500'}`}
          >{m === 'friend' ? '👫 Roast a Friend' : '📸 Roast My Photo'}</button>
        ))}
      </div>

      {result ? (
        <motion.div initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="space-y-4">
          <div className="bg-gradient-to-br from-red-50 to-orange-50 dark:from-red-900/20 dark:to-orange-900/20 rounded-2xl p-6 border border-red-100 dark:border-red-800">
            <p className="text-xl font-semibold text-zinc-800 dark:text-zinc-100">{result}</p>
          </div>
          <div className="flex gap-2">
            <button onClick={() => { navigator.clipboard.writeText(`😂 ${result}`); toast.success('Copied!'); }} className="flex-1 py-3 rounded-xl bg-zinc-100 dark:bg-zinc-800 text-zinc-700 font-semibold">📋 Copy</button>
            <button onClick={() => window.open(`https://wa.me/?text=${encodeURIComponent(`😂 ${result}\n\nRoast yourself: ${window.location.origin}`)}`)} className="flex-1 py-3 rounded-xl bg-green-100 text-green-700 font-semibold">💬 WhatsApp</button>
          </div>
          <button onClick={() => setResult(null)} className="w-full py-2 text-zinc-500 text-sm">← Try another</button>
        </motion.div>
      ) : mode === 'friend' ? (
        <div className="space-y-3">
          {[['name',"Friend's name",'e.g. Alex'],['job','Their job','e.g. Software Engineer'],['fact','A fun fact','e.g. Always late to meetings']].map(([k,l,p]) => (
            <div key={k}>
              <label className="text-sm font-medium text-zinc-600 dark:text-zinc-400 mb-1 block">{l}</label>
              <input type="text" placeholder={p} value={(form as any)[k]}
                onChange={e => setForm({...form,[k]:e.target.value})}
                className="w-full px-4 py-3 rounded-xl border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 text-zinc-800 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-orange-400"
              />
            </div>
          ))}
          <motion.button whileTap={{ scale: 0.96 }} onClick={handleFriendRoast} disabled={loading}
            className="w-full py-4 rounded-2xl bg-gradient-to-r from-red-500 to-orange-500 text-white font-bold text-lg disabled:opacity-60"
          >{loading ? '🔥 Roasting...' : '🔥 Roast Them!'}</motion.button>
        </div>
      ) : (
        <div className="space-y-4">
          <label className={`flex flex-col items-center justify-center gap-3 py-12 rounded-2xl border-2 border-dashed cursor-pointer transition-all ${loading ? 'border-orange-300 bg-orange-50 dark:bg-orange-900/10' : 'border-zinc-200 dark:border-zinc-700 hover:border-orange-300 hover:bg-orange-50 dark:hover:bg-orange-900/10'}`}>
            {loading ? <><span className="text-4xl animate-spin">🔄</span><span className="text-zinc-500">Analyzing photo...</span></>
              : <><span className="text-4xl">📸</span><span className="font-semibold text-zinc-700 dark:text-zinc-300">Upload a photo to roast</span><span className="text-sm text-zinc-500">Max 5MB · JPEG, PNG, WebP</span></>}
            <input type="file" accept="image/*" className="hidden" onChange={handlePhotoRoast} disabled={loading} />
          </label>
        </div>
      )}
    </div>
  );
}

// ─── BATTLE SECTION ───────────────────────────────────────────────────────────
function BattleSection() {
  const [battle, setBattle] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [voted, setVoted] = useState<'a'|'b'|null>(null);

  const createBattle = async () => {
    setLoading(true);
    try {
      const data = await api.createBattle();
      setBattle(data);
    } catch { toast.error('Could not start battle!'); } finally { setLoading(false); }
  };

  const vote = async (side: 'a'|'b') => {
    if (voted || !battle) return;
    setVoted(side);
    await api.voteBattle(battle.battleId, side).catch(() => {});
    toast.success(`Voted for Joke ${side.toUpperCase()}!`);
  };

  return (
    <div className="pt-2 space-y-4">
      <h2 className="text-2xl font-bold text-zinc-800 dark:text-zinc-100">⚔️ Joke Battle</h2>
      <p className="text-zinc-500 text-sm">Challenge a friend! Each gets an AI joke. People vote who's funnier.</p>
      {!battle ? (
        <motion.button whileTap={{ scale: 0.96 }} onClick={createBattle} disabled={loading}
          className="w-full py-4 rounded-2xl bg-gradient-to-r from-purple-500 to-blue-500 text-white font-bold text-lg"
        >{loading ? '⚔️ Creating...' : '⚔️ Start a Battle!'}</motion.button>
      ) : (
        <div className="space-y-4">
          {/* Share link */}
          <div className="bg-purple-50 dark:bg-purple-900/20 rounded-2xl p-4 flex items-center justify-between gap-3">
            <div><p className="text-xs text-purple-600 font-semibold uppercase tracking-wide">Battle Link</p><p className="text-sm text-zinc-600 dark:text-zinc-400 truncate">{battle.challengeUrl}</p></div>
            <button onClick={() => { navigator.clipboard.writeText(battle.challengeUrl); toast.success('Link copied!'); }}
              className="shrink-0 px-3 py-2 rounded-lg bg-purple-100 dark:bg-purple-800 text-purple-700 dark:text-purple-200 text-sm font-semibold"
            >Copy</button>
          </div>
          {/* Jokes */}
          <div className="space-y-3">
            {['a','b'].map(side => (
              <motion.button key={side} whileTap={{ scale: 0.97 }}
                onClick={() => vote(side as 'a'|'b')}
                className={`w-full text-left p-5 rounded-2xl border-2 transition-all ${voted === side ? 'border-amber-400 bg-amber-50 dark:bg-amber-900/20' : voted ? 'border-zinc-100 dark:border-zinc-800 opacity-50' : 'border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-900 hover:border-amber-300'}`}
              >
                <div className="text-xs font-bold uppercase text-zinc-400 mb-2">Joke {side.toUpperCase()}</div>
                <p className="font-semibold text-zinc-800 dark:text-zinc-100">{side === 'a' ? battle.jokeA : '🤔 Waiting for your friend...'}</p>
                {voted === side && <div className="mt-2 text-amber-600 text-sm font-bold">✓ You voted for this!</div>}
              </motion.button>
            ))}
          </div>
          <button onClick={() => setBattle(null)} className="w-full py-2 text-zinc-500 text-sm">← Create new battle</button>
        </div>
      )}
    </div>
  );
}

// ─── PROFILE SECTION ──────────────────────────────────────────────────────────
function ProfileSection() {
  const isLoggedIn = typeof window !== 'undefined' && !!localStorage.getItem('token');

  if (!isLoggedIn) return (
    <div className="pt-2 space-y-4 text-center py-12">
      <div className="text-6xl">👤</div>
      <h2 className="text-xl font-bold text-zinc-800 dark:text-zinc-100">Sign in to unlock everything</h2>
      <p className="text-zinc-500">Save favorites, get daily jokes, and earn your cartoon avatar.</p>
      <a href="/auth" className="block w-full py-4 rounded-2xl bg-gradient-to-r from-amber-400 to-orange-500 text-white font-bold text-lg">Sign In / Register</a>
    </div>
  );

  return (
    <div className="pt-2 space-y-4">
      <h2 className="text-2xl font-bold text-zinc-800 dark:text-zinc-100">👤 My Profile</h2>
      <a href="/profile" className="block w-full py-4 rounded-2xl bg-zinc-100 dark:bg-zinc-900 text-zinc-700 dark:text-zinc-300 font-semibold text-center">View Full Profile →</a>
      <a href="/favorites" className="block w-full py-4 rounded-2xl bg-zinc-100 dark:bg-zinc-900 text-zinc-700 dark:text-zinc-300 font-semibold text-center">❤️ My Favorites →</a>
      <a href="/history" className="block w-full py-4 rounded-2xl bg-zinc-100 dark:bg-zinc-900 text-zinc-700 dark:text-zinc-300 font-semibold text-center">📜 Joke History →</a>
      <a href="/preferences" className="block w-full py-4 rounded-2xl bg-zinc-100 dark:bg-zinc-900 text-zinc-700 dark:text-zinc-300 font-semibold text-center">⚙️ Humor Preferences →</a>
    </div>
  );
}
