// app/profile/page.tsx — Full Profile Page
'use client';

import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import toast, { Toaster } from 'react-hot-toast';
import { api } from '@/lib/api';

interface Profile {
  username: string;
  bio: string;
  email: string;
  original_photo_url: string | null;
  cartoon_photo_url: string | null;
  active_avatar_type: 'original' | 'cartoon';
  age_verified: boolean;
  created_at: string;
}

export default function ProfilePage() {
  const [profile, setProfile]       = useState<Profile | null>(null);
  const [loading, setLoading]       = useState(true);
  const [uploadingPhoto, setUploadingPhoto]   = useState(false);
  const [generatingAvatar, setGeneratingAvatar] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.getProfile()
      .then(setProfile)
      .catch(() => { toast.error('Could not load profile.'); window.location.href = '/auth'; })
      .finally(() => setLoading(false));
  }, []);

  const handlePhotoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return;
    setUploadingPhoto(true);
    try {
      const data = await api.uploadPhoto(file);
      setProfile(p => p ? { ...p, original_photo_url: data.url } : p);
      toast.success('Photo uploaded!');
    } catch { toast.error('Upload failed.'); } finally { setUploadingPhoto(false); }
  };

  const handleGenerateCartoon = async () => {
    setGeneratingAvatar(true);
    toast.loading('Creating your cartoon avatar... This takes ~20 seconds', { id: 'cartoon', duration: 30000 });
    try {
      const data = await api.generateCartoon();
      setProfile(p => p ? { ...p, cartoon_photo_url: data.url } : p);
      toast.dismiss('cartoon');
      toast.success('Cartoon avatar ready! 🎨');
    } catch {
      toast.dismiss('cartoon');
      toast.error('Avatar generation failed.');
    } finally { setGeneratingAvatar(false); }
  };

  const setAvatarType = async (type: 'original' | 'cartoon') => {
    await api.setAvatarType(type).catch(() => {});
    setProfile(p => p ? { ...p, active_avatar_type: type } : p);
    toast.success(`Using ${type === 'cartoon' ? 'cartoon' : 'original'} avatar`);
  };

  const logout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('userId');
    window.location.href = '/';
  };

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-5xl animate-bounce">😂</div>
    </div>
  );

  if (!profile) return null;

  const activeAvatar = profile.active_avatar_type === 'cartoon'
    ? profile.cartoon_photo_url : profile.original_photo_url;

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 pb-24">
      <Toaster position="top-center" />

      <header className="sticky top-0 bg-white/90 dark:bg-zinc-950/90 backdrop-blur border-b border-zinc-100 dark:border-zinc-800 px-4 py-3 flex items-center gap-3">
        <a href="/" className="text-zinc-500 hover:text-zinc-700">←</a>
        <h1 className="font-bold text-zinc-800 dark:text-zinc-100">My Profile</h1>
      </header>

      <div className="max-w-lg mx-auto px-4 py-6 space-y-6">

        {/* Avatar section */}
        <div className="bg-white dark:bg-zinc-900 rounded-3xl border border-zinc-100 dark:border-zinc-800 p-6">
          <div className="flex flex-col items-center gap-4">
            {/* Avatar display */}
            <div className="relative">
              {activeAvatar ? (
                <img src={activeAvatar} alt="Avatar"
                  className="w-24 h-24 rounded-full object-cover border-4 border-amber-400 shadow-lg"
                />
              ) : (
                <div className="w-24 h-24 rounded-full bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center text-4xl shadow-lg border-4 border-amber-300">
                  {profile.username[0].toUpperCase()}
                </div>
              )}
              <button onClick={() => fileInputRef.current?.click()}
                className="absolute -bottom-1 -right-1 w-8 h-8 bg-amber-400 hover:bg-amber-500 rounded-full flex items-center justify-center shadow-md transition-all"
              >📷</button>
            </div>
            <input ref={fileInputRef} type="file" accept="image/*" className="hidden" onChange={handlePhotoUpload} />

            <div className="text-center">
              <p className="text-xl font-bold text-zinc-800 dark:text-zinc-100">@{profile.username}</p>
              <p className="text-sm text-zinc-500">{profile.email}</p>
              {profile.bio && <p className="text-sm text-zinc-600 dark:text-zinc-400 mt-1">{profile.bio}</p>}
            </div>

            {/* Avatar type switcher */}
            {profile.original_photo_url && (
              <div className="flex gap-2 w-full">
                <button onClick={() => setAvatarType('original')}
                  className={`flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all border-2 ${
                    profile.active_avatar_type === 'original' ? 'border-amber-400 bg-amber-50 dark:bg-amber-900/20 text-amber-700' : 'border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400'
                  }`}
                >📷 Original</button>
                <button
                  onClick={profile.cartoon_photo_url ? () => setAvatarType('cartoon') : handleGenerateCartoon}
                  disabled={generatingAvatar || uploadingPhoto}
                  className={`flex-1 py-2.5 rounded-xl text-sm font-semibold transition-all border-2 disabled:opacity-50 ${
                    profile.active_avatar_type === 'cartoon' ? 'border-purple-400 bg-purple-50 dark:bg-purple-900/20 text-purple-700' : 'border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400'
                  }`}
                >
                  {generatingAvatar ? '✨ Generating...' : profile.cartoon_photo_url ? '🎨 Cartoon' : '✨ Generate Cartoon'}
                </button>
              </div>
            )}

            {!profile.original_photo_url && (
              <button onClick={() => fileInputRef.current?.click()}
                disabled={uploadingPhoto}
                className="w-full py-3 rounded-2xl border-2 border-dashed border-zinc-300 dark:border-zinc-700 text-zinc-500 font-semibold text-sm"
              >{uploadingPhoto ? 'Uploading...' : '📷 Upload a photo to unlock cartoon avatar'}</button>
            )}
          </div>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: 'Member since', value: new Date(profile.created_at).toLocaleDateString('en', { month: 'short', year: 'numeric' }) },
            { label: 'Age verified', value: profile.age_verified ? '✅ Yes' : '❌ No' },
            { label: 'Status', value: '😂 Active' },
          ].map(({ label, value }) => (
            <div key={label} className="bg-white dark:bg-zinc-900 rounded-2xl p-3 border border-zinc-100 dark:border-zinc-800 text-center">
              <p className="text-xs text-zinc-500 mb-1">{label}</p>
              <p className="text-sm font-semibold text-zinc-800 dark:text-zinc-100">{value}</p>
            </div>
          ))}
        </div>

        {/* Actions */}
        <div className="space-y-2">
          {[
            { href: '/favorites', icon: '❤️', label: 'My Favorites' },
            { href: '/history', icon: '📜', label: 'Joke History' },
            { href: '/preferences', icon: '⚙️', label: 'Humor Preferences' },
          ].map(({ href, icon, label }) => (
            <a key={href} href={href}
              className="flex items-center gap-3 px-5 py-4 rounded-2xl bg-white dark:bg-zinc-900 border border-zinc-100 dark:border-zinc-800 text-zinc-700 dark:text-zinc-300 font-semibold hover:bg-zinc-50 transition-all"
            >
              <span className="text-xl">{icon}</span>
              <span>{label}</span>
              <span className="ml-auto text-zinc-400">→</span>
            </a>
          ))}
        </div>

        <button onClick={logout}
          className="w-full py-4 rounded-2xl border-2 border-red-200 dark:border-red-900 text-red-600 dark:text-red-400 font-semibold hover:bg-red-50 dark:hover:bg-red-900/20 transition-all"
        >Sign Out</button>
      </div>
    </div>
  );
}
