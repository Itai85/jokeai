"""
HaHaTown — Full Backend Server
Flask · In-memory DB (SQLite) · JWT Auth · Anthropic AI · Pillow Meme Generator
Run: python3 server.py
"""

import os, json, uuid, time, base64, io, hashlib, re, textwrap, random, sqlite3
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path

# ── Flask ─────────────────────────────────────────────────────────────────────
from flask import Flask, request, jsonify, send_file, g

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB uploads

@app.errorhandler(Exception)
def handle_exception(e):
    import traceback
    tb = traceback.format_exc()
    print(f"[ERROR] {e}\n{tb}")
    return jsonify({"error": str(e), "type": type(e).__name__}), 500

@app.errorhandler(404)
def handle_404(e):
    return jsonify({"error": "Not found"}), 404

# _ensure_db defined below after SCHEMA/SEED constants

# ── JWT ───────────────────────────────────────────────────────────────────────
import jwt as pyjwt
JWT_SECRET = os.getenv("JWT_SECRET", "hahahtown-dev-secret-change-in-production")
JWT_ALGO   = "HS256"
JWT_EXP    = 30  # days

def sign_token(user_id: str) -> str:
    payload = {"sub": user_id, "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXP)}
    return pyjwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)

def verify_token(token: str) -> dict:
    return pyjwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])

# ── Paths (cross-platform: Windows local & Railway/cloud) ─────────────────────
BASE_DIR = Path(__file__).parent.resolve()

# Detect cloud environment
_is_cloud = bool(os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RAILWAY_STATIC_URL") or os.getenv("RENDER") or os.getenv("DYNO") or os.getenv("PORT"))

# DB: /tmp on cloud (writable), local file on Windows
_db_env  = os.getenv("DATABASE_PATH")
if _db_env:
    DB_PATH = Path(_db_env)
elif _is_cloud:
    DB_PATH = Path("/tmp/jokeai.db")
else:
    DB_PATH = BASE_DIR / "jokeai.db"

# Media dirs
_media_base = Path("/tmp/hahahtown") if _is_cloud else BASE_DIR

print(f"[PATHS] BASE_DIR={BASE_DIR} DB={DB_PATH} cloud={_is_cloud}")

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(str(DB_PATH))
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
        g.db.execute("PRAGMA foreign_keys=ON")
    return g.db

@app.teardown_appcontext
def close_db(e=None):
    db = g.pop("db", None)
    if db:
        db.close()

def db_exec(sql, params=()):
    db = get_db()
    cur = db.execute(sql, params)
    db.commit()
    return cur

def db_one(sql, params=()):
    cur = get_db().execute(sql, params)
    row = cur.fetchone()
    return dict(row) if row else None

def db_all(sql, params=()):
    cur = get_db().execute(sql, params)
    return [dict(r) for r in cur.fetchall()]

# ── Schema ────────────────────────────────────────────────────────────────────
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT,
    provider TEXT DEFAULT 'email',
    age_verified INTEGER DEFAULT 0,
    accepted_tos INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);
CREATE TABLE IF NOT EXISTS profiles (
    user_id TEXT PRIMARY KEY REFERENCES users(id),
    username TEXT UNIQUE NOT NULL,
    original_photo_url TEXT,
    cartoon_photo_url TEXT,
    active_avatar_type TEXT DEFAULT 'original',
    bio TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS humor_preferences (
    user_id TEXT PRIMARY KEY REFERENCES users(id),
    humor_types TEXT NOT NULL DEFAULT '["dad jokes"]',
    intensity INTEGER DEFAULT 3,
    language TEXT DEFAULT 'en',
    safe_mode INTEGER DEFAULT 1,
    sexual_content INTEGER DEFAULT 0,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jokes (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    category TEXT NOT NULL,
    language TEXT DEFAULT 'en',
    intensity INTEGER DEFAULT 3,
    safe INTEGER DEFAULT 1,
    sexual INTEGER DEFAULT 0,
    source TEXT DEFAULT 'ai',
    score INTEGER DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS joke_ratings (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    joke_id TEXT NOT NULL REFERENCES jokes(id),
    rating TEXT NOT NULL,
    shared INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    UNIQUE(user_id, joke_id)
);
CREATE TABLE IF NOT EXISTS joke_history (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    joke_id TEXT NOT NULL,
    viewed_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS meme_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT DEFAULT 'general',
    active INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS memes (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    joke_id TEXT,
    template_id TEXT,
    image_path TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS joke_battles (
    id TEXT PRIMARY KEY,
    challenger_id TEXT NOT NULL,
    joke_a_id TEXT NOT NULL,
    joke_b_id TEXT,
    votes_a INTEGER DEFAULT 0,
    votes_b INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    share_token TEXT UNIQUE NOT NULL,
    created_at TEXT NOT NULL,
    ends_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS battle_votes (
    id TEXT PRIMARY KEY,
    battle_id TEXT NOT NULL,
    voter_id TEXT,
    voted_for TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

SEED_TEMPLATES = """
INSERT OR IGNORE INTO meme_templates (id, name, category) VALUES
    ('t1','Drake Approves','reaction'),
    ('t2','This Is Fine','reaction'),
    ('t3','Two Buttons','choices'),
    ('t4','Expanding Brain','escalation'),
    ('t5','Distracted Boyfriend','comparison'),
    ('t6','Change My Mind','opinion'),
    ('t7','One Does Not Simply','warning'),
    ('t8','Is This A Pigeon?','confusion');
"""

SEED_JOKES = [
    # ── DAD JOKES (17) ──────────────────────────────────────────────────────────
    ("Why don't scientists trust atoms? Because they make up everything.", "dad jokes"),
    ("I'm reading a book about anti-gravity. It's impossible to put down.", "dad jokes"),
    ("Dad, are we pyromaniacs? Yes, we arson.", "dad jokes"),
    ("I used to hate facial hair, but then it grew on me.", "dad jokes"),
    ("What do you call a fake noodle? An impasta.", "dad jokes"),
    ("I'm on a seafood diet. I see food and I eat it.", "dad jokes"),
    ("What did the ocean say to the beach? Nothing, it just waved.", "dad jokes"),
    ("I told my wife she was drawing her eyebrows too high. She seemed surprised.", "dad jokes"),
    ("Why do fathers take an extra pair of socks when they go golfing? In case they get a hole in one.", "dad jokes"),
    ("I got fired from the calendar factory. All I did was take a day off.", "dad jokes"),
    ("What do you call a bear with no teeth? A gummy bear.", "dad jokes"),
    ("I would tell you a construction joke, but I'm still working on it.", "dad jokes"),
    ("Why did the scarecrow win an award? He was outstanding in his field.", "dad jokes"),
    ("What do you call cheese that isn't yours? Nacho cheese.", "dad jokes"),
    ("I used to play piano by ear, but now I use my hands.", "dad jokes"),
    ("What did the grape do when it got stepped on? Nothing, it just let out a little wine.", "dad jokes"),
    ("I'm afraid for the calendar. Its days are numbered.", "dad jokes"),

    # ── TECH JOKES (17) ─────────────────────────────────────────────────────────
    ("I told my computer I needed a break. Now it won't stop sending me Kit-Kat ads.", "tech jokes"),
    ("A SQL query walks into a bar, walks up to two tables and asks... Can I join you?", "tech jokes"),
    ("Why did the developer go broke? Because he used up all his cache.", "tech jokes"),
    ("There are only 10 types of people in the world: those who understand binary and those who don't.", "tech jokes"),
    ("A programmer's wife tells him: go to the store and get a loaf of bread. If they have eggs, get a dozen. He comes home with 12 loaves.", "tech jokes"),
    ("Why do programmers prefer dark mode? Because light attracts bugs.", "tech jokes"),
    ("It works on my machine. Then we'll ship your machine.", "tech jokes"),
    ("I changed my password to 'incorrect' so whenever I forget it, the computer tells me.", "tech jokes"),
    ("Debugging is like being the detective in a crime movie where you're also the murderer.", "tech jokes"),
    ("The best thing about a Boolean is that even if you're wrong, you're only off by a bit.", "tech jokes"),
    ("Why was the JavaScript developer sad? Because he didn't Node how to Express himself.", "tech jokes"),
    ("A QA engineer walks into a bar. Orders 1 beer. Orders 0 beers. Orders 99999 beers. Orders -1 beers. Orders a lizard.", "tech jokes"),
    ("My code doesn't have bugs. It has random features.", "tech jokes"),
    ("To understand recursion, you must first understand recursion.", "tech jokes"),
    ("I would tell you a UDP joke, but you might not get it.", "tech jokes"),
    ("The cloud is just someone else's computer that you're paying rent on.", "tech jokes"),
    ("Git commit -m 'fixed everything'. Narrator: he had not fixed everything.", "tech jokes"),

    # ── RELATIONSHIP JOKES (17) ─────────────────────────────────────────────────
    ("My wife told me I had to stop acting like a flamingo. I had to put my foot down.", "relationship jokes"),
    ("Our relationship is like a software update: I never know when it's happening and it always takes longer than expected.", "relationship jokes"),
    ("I love you more than coffee. Please don't make me prove it.", "relationship jokes"),
    ("Sometimes I think the WiFi password is the most intimate thing two people can share.", "relationship jokes"),
    ("My husband said I should embrace my mistakes. So I hugged him.", "relationship jokes"),
    ("Love is sharing your popcorn. True love is letting them have the last handful.", "relationship jokes"),
    ("My partner said I never listen to them. At least I think that's what they said.", "relationship jokes"),
    ("Marriage is like a deck of cards. In the beginning all you need is two hearts and a diamond. By the end, you wish you had a club and a spade.", "relationship jokes"),
    ("I asked my wife what she wanted for her birthday. She said nothing would make her happier than a diamond necklace. So I got her nothing.", "relationship jokes"),
    ("My girlfriend told me to go out and get something that makes her look sexy. So I got drunk.", "relationship jokes"),
    ("Relationships are a lot like algebra. Have you ever looked at your X and wondered Y?", "relationship jokes"),
    ("My wife says I only have two faults: I don't listen, and something else.", "relationship jokes"),
    ("I love being married. It's so great to find one special person you want to annoy for the rest of your life.", "relationship jokes"),
    ("Behind every successful man is a surprised woman.", "relationship jokes"),
    ("My partner and I laugh about how competitive we are. But I laugh more.", "relationship jokes"),
    ("A good relationship is like Wi-Fi. You don't notice it until it stops working.", "relationship jokes"),
    ("They say love is blind. Marriage is the eye-opener.", "relationship jokes"),

    # ── ABSURD HUMOR (17) ───────────────────────────────────────────────────────
    ("I asked the universe for a sign. It sent me a stop sign. I'm still not sure what it means.", "absurd humor"),
    ("Existence is just the universe's way of debugging itself, and we are all unresolved stack traces.", "absurd humor"),
    ("If you rearrange the letters of 'postman', you get 'stop man'. The postman was not amused.", "absurd humor"),
    ("I tried to sue the airline for losing my luggage. I lost my case.", "absurd humor"),
    ("Time flies like an arrow. Fruit flies like a banana.", "absurd humor"),
    ("I told my suitcase there will be no vacation this year. Now I'm dealing with emotional baggage.", "absurd humor"),
    ("The rotation of Earth really makes my day.", "absurd humor"),
    ("I once ate a watch. It was time consuming.", "absurd humor"),
    ("A man walks into a bar. The second one ducks.", "absurd humor"),
    ("Parallel lines have so much in common. Too bad they'll never meet.", "absurd humor"),
    ("I stayed up all night wondering where the sun went. Then it dawned on me.", "absurd humor"),
    ("What happens when you put a duck in a blender? Quark.", "absurd humor"),
    ("I want to die peacefully in my sleep, like my grandfather. Not screaming and yelling like the passengers in his car.", "absurd humor"),
    ("If tomatoes are a fruit, then ketchup is a smoothie.", "absurd humor"),
    ("My therapist says I have a preoccupation with vengeance. We'll see about that.", "absurd humor"),
    ("I used to think the brain was the most important organ. Then I realized what was telling me that.", "absurd humor"),
    ("A plateau is the highest form of flattery.", "absurd humor"),

    # ── DARK HUMOR (17) ─────────────────────────────────────────────────────────
    ("I have a fish that can breakdance. Only for 20 seconds though, and only once.", "dark humor"),
    ("I told my psychiatrist I was hearing voices. He said I don't have a psychiatrist.", "dark humor"),
    ("The doctor gave me one year to live, so I shot him. The judge gave me 15 years. Problem solved.", "dark humor"),
    ("My grandfather has the heart of a lion. And a lifetime ban from the zoo.", "dark humor"),
    ("I have a joke about trickle-down economics. But 99 percent of you will never get it.", "dark humor"),
    ("Dark humor is like food. Not everybody gets it.", "dark humor"),
    ("What's the difference between a well-dressed man on a bicycle and a poorly-dressed man on a unicycle? Attire.", "dark humor"),
    ("I was wondering why the frisbee was getting bigger. Then it hit me.", "dark humor"),
    ("I asked my North Korean friend how things were going. He said he couldn't complain.", "dark humor"),
    ("I have a stepladder. Not my real ladder.", "dark humor"),
    ("Welcome to Plastic Surgery Addicts Anonymous. I see a lot of new faces.", "dark humor"),
    ("My wife left me because I'm too insecure. No wait, she's back. She just went to get coffee.", "dark humor"),
    ("The cemetery is so crowded. People must be dying to get in there.", "dark humor"),
    ("I threw a boomerang a few years ago. I now live in constant fear.", "dark humor"),
    ("I'm not saying my cooking is bad, but the smoke alarm cheers me on.", "dark humor"),
    ("My parents raised me as an only child, which was tough on my brother.", "dark humor"),

    # ── WORK HUMOR (17) ─────────────────────────────────────────────────────────
    ("The meeting could have been an email. The email could have been a text. The text could have been silence.", "work humor"),
    ("I told my boss three companies were after me and I needed a raise. He asked which ones. I said gas, electric, and water.", "work humor"),
    ("My calendar says I have a meeting with Future Successful Me. He cancelled again.", "work humor"),
    ("My boss told me to have a good day. So I went home.", "work humor"),
    ("I'm not lazy. I'm on energy-saving mode.", "work humor"),
    ("The only thing I spread at work is misinformation.", "work humor"),
    ("Experience is what you get when you didn't get what you wanted.", "work humor"),
    ("Nothing ruins a Friday more than realizing it's only Wednesday.", "work humor"),
    ("Teamwork means never having to take all the blame yourself.", "work humor"),
    ("My resume is just a list of things I never want to do again.", "work humor"),
    ("I always give 100 percent at work: 10 percent Monday, 23 percent Tuesday, 40 percent Wednesday, 22 percent Thursday, 5 percent Friday.", "work humor"),
    ("The closest to being organized I've ever been is that one time I put two things in the same drawer.", "work humor"),
    ("I'm great at multitasking. I can waste time, be unproductive, and procrastinate all at once.", "work humor"),
    ("My work-life balance is a coffee in one hand and anxiety in the other.", "work humor"),
    ("HR said I should focus on my strengths. So now I nap with confidence.", "work humor"),
    ("I put my heart and soul into my work. That's why my heart stopped and my soul left.", "work humor"),
    ("If at first you don't succeed, redefine success.", "work humor"),
]

def init_db():
    """Initialize DB — fast startup, seeds only if empty."""
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(DB_PATH))
        db.executescript(SCHEMA)
        db.executescript(SEED_TEMPLATES)
        # Only seed if jokes table is empty (skip on restart)
        count = db.execute("SELECT COUNT(*) FROM jokes").fetchone()[0]
        if count == 0:
            now = datetime.now(timezone.utc).isoformat()
            for text, category in SEED_JOKES:
                jid = str(uuid.uuid4())
                try:
                    db.execute(
                        "INSERT OR IGNORE INTO jokes "
                        "(id,text,category,language,intensity,safe,sexual,source,score,created_at) "
                        "VALUES (?,?,?,\'en\',2,1,0,\'seed\',10,?)",
                        (jid, text, category, now)
                    )
                except Exception:
                    pass
            db.commit()
            print(f"[DB] Seeded {len(SEED_JOKES)} jokes")
        else:
            print(f"[DB] {count} jokes already in DB, skipping seed")
        db.close()
        print(f"[DB] Ready at {DB_PATH}")
    except Exception as e:
        print(f"[DB] Init FAILED: {e}")
        raise

# ── Run at import time (works with gunicorn AND direct python) ─────────────────
init_db()

# ── Auth helpers ───────────────────────────────────────────────────────────────
def hash_password(pw: str) -> str:
    return hashlib.sha256((pw + JWT_SECRET).encode()).hexdigest()

def check_password(pw: str, hashed: str) -> bool:
    return hash_password(pw) == hashed

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            return jsonify({"error": "Authentication required"}), 401
        try:
            payload = verify_token(token)
            g.user_id = payload["sub"]
        except Exception:
            return jsonify({"error": "Invalid or expired token"}), 401
        return f(*args, **kwargs)
    return decorated

def optional_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        g.user_id = None
        if token:
            try:
                payload = verify_token(token)
                g.user_id = payload["sub"]
            except Exception:
                pass
        return f(*args, **kwargs)
    return decorated

def get_prefs(user_id: str) -> dict:
    row = db_one("SELECT * FROM humor_preferences WHERE user_id=?", (user_id,))
    if not row:
        return {"humor_types": ["dad jokes"], "intensity": 3, "language": "en", "safe_mode": 1, "sexual_content": 0}
    row["humor_types"] = json.loads(row["humor_types"])
    return row

# ── AI Joke Generation ─────────────────────────────────────────────────────────
GROQ_KEY   = os.getenv("GROQ_API_KEY", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
AI_KEY     = GROQ_KEY or GEMINI_KEY
AI_PROVIDER = "groq" if GROQ_KEY else ("gemini" if GEMINI_KEY else "")

def call_ai(prompt: str, system: str = "", max_tokens: int = 300) -> str:
    """Try Groq first (if key set), then Gemini — 8s timeout each."""
    import urllib.request

    def _try_groq():
        if not GROQ_KEY:
            return None
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        body = json.dumps({
            "model": "llama-3.3-70b-versatile",
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.9
        }).encode()
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {GROQ_KEY}"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()

    def _try_gemini():
        if not GEMINI_KEY:
            return None
        full = (system + "\n\n" + prompt) if system else prompt
        body = json.dumps({
            "contents": [{"parts": [{"text": full}]}],
            "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.9}
        }).encode()
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}",
            data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read())["candidates"][0]["content"]["parts"][0]["text"].strip()

    providers = []
    if GROQ_KEY:   providers.append(("groq",   _try_groq))
    if GEMINI_KEY: providers.append(("gemini", _try_gemini))

    for name, fn in providers:
        try:
            result = fn()
            if result:
                print(f"[AI] {name} OK")
                return result
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:200]
            print(f"[AI] {name} {e.code}: {body}")
        except Exception as e:
            print(f"[AI] {name} failed: {type(e).__name__}: {e}")

    print("[AI] All providers failed — using pool")
    return _fallback_joke(prompt)


def call_ai_vision(prompt: str, image_b64: str, mime: str) -> str:
    """Vision: try Groq Llama Vision, fallback to Gemini."""
    import urllib.request
    FALLBACK = "He looks like someone who just realized he sent that message to the wrong chat."

    def _try_groq_vision():
        if not GROQ_KEY:
            return None
        body = json.dumps({
            "model": "llama-3.2-90b-vision-preview",
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                {"type": "text", "text": prompt}
            ]}],
            "max_tokens": 200, "temperature": 0.9
        }).encode()
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {GROQ_KEY}"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())["choices"][0]["message"]["content"].strip()

    def _try_gemini_vision():
        if not GEMINI_KEY:
            return None
        body = json.dumps({
            "contents": [{"parts": [
                {"inline_data": {"mime_type": mime, "data": image_b64}},
                {"text": prompt}
            ]}],
            "generationConfig": {"maxOutputTokens": 200, "temperature": 0.9}
        }).encode()
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}",
            data=body, headers={"Content-Type": "application/json"}, method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read())["candidates"][0]["content"]["parts"][0]["text"].strip()

    providers = []
    if GROQ_KEY:   providers.append(("groq",   _try_groq_vision))
    if GEMINI_KEY: providers.append(("gemini", _try_gemini_vision))

    for name, fn in providers:
        try:
            result = fn()
            if result:
                return result
        except Exception as e:
            print(f"[AI] {name} vision failed: {type(e).__name__}: {e}")

    return FALLBACK


def _fallback_joke(ctx: str = "") -> str:
    """Return a random seeded joke when AI is unavailable."""
    rows = db_all("SELECT text FROM jokes ORDER BY RANDOM() LIMIT 1")
    if rows:
        return rows[0]["text"]
    return "Why do programmers prefer dark mode? Because light attracts bugs."

def build_joke_prompt(prefs: dict) -> str:
    labels = ["very mild","mild","moderate","edgy","extreme"]
    intensity_label = labels[min(prefs.get("intensity", 3) - 1, 4)]
    humor_types = prefs.get("humor_types", ["dad jokes"])
    if isinstance(humor_types, str):
        humor_types = json.loads(humor_types)
    lang = prefs.get("language", "en")
    if lang == "he":
        lang_instruction = "IMPORTANT: Write the joke entirely in Hebrew (עברית). Every word must be in Hebrew."
    else:
        lang_instruction = "Write the joke in English."
    safe = prefs.get("safe_mode", 1)
    sexual = prefs.get("sexual_content", 0)
    return f"""You are a professional comedy writer. Generate ONE short, original joke.
Return ONLY the joke text — no title, no explanation, no preamble.

Preferences:
- Humor styles: {', '.join(humor_types)}
- Intensity: {intensity_label} ({prefs.get('intensity',3)}/5)
- {lang_instruction}
- Safe mode: {"YES — avoid offensive or extreme content" if safe else "NO"}
- Sexual humor: {"allowed (adult user)" if sexual else "NOT allowed"}

Rules:
- 1–3 sentences max
- Be original and genuinely funny
- Avoid clichéd openings like "Why did the chicken..."
- Be creative and unexpected
- Intensity {prefs.get('intensity',3)}/5 means {"keep it very clean and family-friendly" if prefs.get('intensity',3) <= 2 else "push boundaries, be edgy and surprising" if prefs.get('intensity',3) >= 4 else "balanced humor"}"""

def get_joke_for_user(prefs: dict, seen_ids: list) -> dict:
    """AI-first: generate fresh jokes with Gemini, pool as fallback."""
    humor_types = prefs.get("humor_types", ["dad jokes"])
    if isinstance(humor_types, str):
        humor_types = json.loads(humor_types)
    lang = prefs.get("language", "en")
    safe = int(prefs.get("safe_mode", 1))
    intensity = prefs.get("intensity", 3)
    category = humor_types[0] if humor_types else "general"

    # ── 1. If AI is available → generate fresh joke ────────────────────────
    if AI_KEY:
        text = call_ai(build_joke_prompt(prefs))
        # Check it's not a fallback (fallback returns pool jokes)
        pool_texts = [j[0] for j in SEED_JOKES]
        if text and text not in pool_texts:
            jid = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()
            db_exec(
                "INSERT INTO jokes (id,text,category,language,intensity,safe,sexual,source,score,created_at) VALUES (?,?,?,?,?,?,?,'ai',0,?)",
                (jid, text, category, lang, intensity, safe, int(prefs.get("sexual_content", 0)), now)
            )
            return {"id": jid, "text": text, "category": category, "source": "ai"}

    # ── 2. Fallback: serve from pool ───────────────────────────────────────
    exclude = ""
    params = [lang, safe, max(1, intensity-1), min(5, intensity+1)]
    if seen_ids:
        placeholders = ",".join("?" * len(seen_ids))
        exclude = f"AND id NOT IN ({placeholders})"
        params += seen_ids

    cat_filter = " OR ".join(["category=?" for _ in humor_types])
    cat_params = list(humor_types)

    row = db_one(
        f"""SELECT * FROM jokes
            WHERE language=? AND safe>=? AND intensity BETWEEN ? AND ?
            {exclude}
            AND ({cat_filter})
            ORDER BY score DESC, RANDOM() LIMIT 1""",
        params + cat_params
    )

    if not row:
        row = db_one(
            f"SELECT * FROM jokes WHERE language=? AND safe>=? {exclude} ORDER BY RANDOM() LIMIT 1",
            [lang, safe] + (seen_ids if seen_ids else [])
        )

    if row:
        return {**row, "source": "pool"}

    return {"id": str(uuid.uuid4()), "text": "Why did the programmer quit? No more arrays of sunshine.", "category": "tech jokes", "source": "fallback"}

# ── Meme Generator (Pillow) ────────────────────────────────────────────────────
MEME_DIR = _media_base / "memes"
MEME_DIR.mkdir(parents=True, exist_ok=True)

def generate_meme_image(joke_text: str, template_name: str = "Drake Approves") -> Path:
    """Generate a real meme image using Pillow."""
    from PIL import Image, ImageDraw, ImageFont
    import textwrap

    W, H = 800, 500
    img = Image.new("RGB", (W, H), color=(30, 30, 36))
    draw = ImageDraw.Draw(img)

    # Background gradient effect
    for y in range(H):
        r = int(20 + (y / H) * 30)
        g_val = int(20 + (y / H) * 20)
        b = int(36 + (y / H) * 40)
        draw.line([(0, y), (W, y)], fill=(r, g_val, b))

    # Emoji-style template icon (top)
    TEMPLATE_ICONS = {
        "Drake Approves": "👍", "This Is Fine": "🔥", "Two Buttons": "🤔",
        "Expanding Brain": "🧠", "Distracted Boyfriend": "👀",
        "Change My Mind": "💬", "One Does Not Simply": "⚠️", "Is This A Pigeon?": "🦋",
    }
    icon = TEMPLATE_ICONS.get(template_name, "😂")

    # Try to load a font — check Windows and Linux locations
    def _try_fonts(size):
        candidates = [
            # Windows
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/impact.ttf",
            "C:/Windows/Fonts/verdanab.ttf",
            # Linux
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        for c in candidates:
            if Path(c).exists():
                try:
                    return ImageFont.truetype(c, size)
                except Exception:
                    continue
        return ImageFont.load_default()

    try:
        font_big   = _try_fonts(52)
        font_med   = _try_fonts(34)
        font_small = _try_fonts(22)
        font_tag   = _try_fonts(18)
    except Exception:
        font_big = font_med = font_small = font_tag = ImageFont.load_default()

    # Header bar
    draw.rectangle([(0, 0), (W, 80)], fill=(245, 158, 11))
    draw.text((W // 2, 40), "😂  HaHaTown", font=font_big, fill=(20, 20, 20), anchor="mm")

    # Template badge
    badge_text = f"[ {template_name} ]"
    draw.text((W // 2, 108), badge_text, font=font_small, fill=(180, 180, 200), anchor="mm")

    # Divider
    draw.line([(40, 128), (W - 40, 128)], fill=(70, 70, 90), width=1)

    # Joke text — wrapped
    max_chars = 42
    wrapped = textwrap.wrap(joke_text, width=max_chars)
    text_start_y = 170
    line_h = 52
    for i, line in enumerate(wrapped[:5]):
        y = text_start_y + i * line_h
        # Shadow
        draw.text((W // 2 + 2, y + 2), line, font=font_med, fill=(0, 0, 0, 120), anchor="mm")
        # Text
        draw.text((W // 2, y), line, font=font_med, fill=(255, 255, 255), anchor="mm")

    # Bottom bar
    draw.rectangle([(0, H - 50), (W, H)], fill=(20, 20, 26))
    draw.text((W // 2, H - 25), "jokeai.app  •  Share the laugh 😂", font=font_tag, fill=(120, 120, 140), anchor="mm")

    # Accent dots
    for x_pos in [30, 60, 90]:
        draw.ellipse([(x_pos - 6, H - 31), (x_pos + 6, H - 19)], fill=(245, 158, 11))

    # Save
    filename = f"meme_{uuid.uuid4().hex[:12]}.png"
    path = MEME_DIR / filename
    img.save(str(path), "PNG", optimize=True)
    return path

# ══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ══════════════════════════════════════════════════════════════════════════════

# ── CORS ──────────────────────────────────────────────────────────────────────
@app.after_request
def add_cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type,Authorization"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,PUT,DELETE,OPTIONS"
    return resp

@app.route("/api/<path:p>", methods=["OPTIONS"])
def options_handler(p):
    return "", 204

# ── HEALTH ────────────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    return jsonify({"status": "ok", "ts": int(time.time()), "ai_configured": bool(AI_KEY), "provider": AI_PROVIDER})

# ── AUTH ──────────────────────────────────────────────────────────────────────
@app.route("/api/auth/register", methods=["POST"])
def register():
    d = request.json or {}
    email    = (d.get("email") or "").strip().lower()
    password = d.get("password", "")
    username = (d.get("username") or "").strip()
    age_ok   = bool(d.get("age_verified"))
    tos_ok   = bool(d.get("accepted_tos"))

    if not email or "@" not in email:
        return jsonify({"error": "Valid email required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if not username or len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters"}), 400
    if not tos_ok:
        return jsonify({"error": "You must accept the terms of service"}), 400

    if db_one("SELECT id FROM users WHERE email=?", (email,)):
        return jsonify({"error": "Email already registered"}), 409
    if db_one("SELECT user_id FROM profiles WHERE username=?", (username,)):
        return jsonify({"error": "Username already taken"}), 409

    uid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    pw_hash = hash_password(password)

    db_exec(
        "INSERT INTO users (id,email,password_hash,age_verified,accepted_tos,created_at) VALUES (?,?,?,?,?,?)",
        (uid, email, pw_hash, int(age_ok), 1, now)
    )
    db_exec("INSERT INTO profiles (user_id,username,updated_at) VALUES (?,?,?)", (uid, username, now))
    db_exec(
        "INSERT INTO humor_preferences (user_id,humor_types,intensity,language,safe_mode,sexual_content,updated_at) VALUES (?,?,3,'en',1,0,?)",
        (uid, '["dad jokes","absurd humor"]', now)
    )

    return jsonify({"token": sign_token(uid), "userId": uid}), 201

@app.route("/api/auth/login", methods=["POST"])
def login():
    d = request.json or {}
    email    = (d.get("email") or "").strip().lower()
    password = d.get("password", "")

    user = db_one("SELECT * FROM users WHERE email=? AND provider='email'", (email,))
    if not user or not check_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid credentials"}), 401

    db_exec("UPDATE users SET last_login_at=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), user["id"]))
    return jsonify({"token": sign_token(user["id"]), "userId": user["id"]})

@app.route("/api/auth/verify-age", methods=["POST"])
@require_auth
def verify_age():
    db_exec("UPDATE users SET age_verified=1 WHERE id=?", (g.user_id,))
    return jsonify({"success": True})

# ── PROFILE ───────────────────────────────────────────────────────────────────
@app.route("/api/profile/me")
@require_auth
def get_profile():
    row = db_one(
        """SELECT p.*, u.email, u.age_verified, u.created_at,
                  hp.humor_types, hp.intensity, hp.language, hp.safe_mode, hp.sexual_content
           FROM profiles p
           JOIN users u ON u.id=p.user_id
           LEFT JOIN humor_preferences hp ON hp.user_id=p.user_id
           WHERE p.user_id=?""",
        (g.user_id,)
    )
    if not row:
        return jsonify({"error": "Profile not found"}), 404
    if row.get("humor_types"):
        row["humor_types"] = json.loads(row["humor_types"])
    return jsonify(row)

@app.route("/api/profile/me", methods=["PUT"])
@require_auth
def update_profile():
    d = request.json or {}
    username = d.get("username")
    bio = d.get("bio")
    if username:
        if not re.match(r"^[a-zA-Z0-9_]{3,30}$", username):
            return jsonify({"error": "Invalid username format"}), 400
        taken = db_one("SELECT user_id FROM profiles WHERE username=? AND user_id!=?", (username, g.user_id))
        if taken:
            return jsonify({"error": "Username already taken"}), 409
    db_exec(
        "UPDATE profiles SET username=COALESCE(?,username), bio=COALESCE(?,bio), updated_at=? WHERE user_id=?",
        (username, bio, datetime.now(timezone.utc).isoformat(), g.user_id)
    )
    return jsonify({"success": True})

@app.route("/api/profile/photo", methods=["POST"])
@require_auth
def upload_photo():
    if "photo" not in request.files:
        return jsonify({"error": "No photo provided"}), 400
    file = request.files["photo"]
    if file.mimetype not in ["image/jpeg", "image/png", "image/webp"]:
        return jsonify({"error": "Only JPEG, PNG, or WebP accepted"}), 400

    from PIL import Image
    img = Image.open(file.stream).convert("RGB")
    img.thumbnail((512, 512), Image.LANCZOS)

    photos_dir = _media_base / "avatars"
    photos_dir.mkdir(exist_ok=True)
    filename = f"{g.user_id}_original.jpg"
    path = photos_dir / filename
    img.save(str(path), "JPEG", quality=85)

    url = f"/avatars/{filename}"
    db_exec("UPDATE profiles SET original_photo_url=?, updated_at=? WHERE user_id=?",
            (url, datetime.now(timezone.utc).isoformat(), g.user_id))
    return jsonify({"url": url})

@app.route("/api/profile/avatar-type", methods=["PUT"])
@require_auth
def set_avatar_type():
    t = (request.json or {}).get("type", "original")
    if t not in ("original", "cartoon"):
        return jsonify({"error": "Invalid avatar type"}), 400
    db_exec("UPDATE profiles SET active_avatar_type=? WHERE user_id=?", (t, g.user_id))
    return jsonify({"success": True})

@app.route("/avatars/<filename>")
def serve_avatar(filename):
    path = _media_base / "avatars" / filename
    if not path.exists():
        return jsonify({"error": "Not found"}), 404
    return send_file(str(path))

# ── JOKES ─────────────────────────────────────────────────────────────────────
@app.route("/api/jokes/generate")
@optional_auth
def generate_joke():
    seen_param = request.args.get("seen", "")
    seen_ids = [s for s in seen_param.split(",") if s.strip()]

    # Accept lang/intensity/types overrides from query string (used by UI)
    qs_lang      = request.args.get("lang", "")
    qs_intensity = request.args.get("intensity", "")
    qs_types     = request.args.get("types", "")

    if g.user_id:
        prefs = get_prefs(g.user_id)
    else:
        prefs = {"humor_types": ["dad jokes", "absurd humor"], "intensity": 2, "language": "en", "safe_mode": 1, "sexual_content": 0}

    # Apply query string overrides
    if qs_lang in ("en", "he"):
        prefs["language"] = qs_lang
    if qs_intensity.isdigit():
        prefs["intensity"] = max(1, min(5, int(qs_intensity)))
    if qs_types:
        types = [t.strip() for t in qs_types.split(",") if t.strip()]
        if types:
            prefs["humor_types"] = types

    joke = get_joke_for_user(prefs, seen_ids)

    if g.user_id:
        db_exec(
            "INSERT INTO joke_history (id,user_id,joke_id,viewed_at) VALUES (?,?,?,?)",
            (str(uuid.uuid4()), g.user_id, joke["id"], datetime.now(timezone.utc).isoformat())
        )

    return jsonify({"id": joke["id"], "text": joke["text"], "category": joke.get("category","general"), "source": joke.get("source","pool")})

@app.route("/api/jokes/rate", methods=["POST"])
@require_auth
def rate_joke():
    d = request.json or {}
    joke_id = d.get("joke_id")
    rating  = d.get("rating")
    shared  = int(bool(d.get("shared", False)))

    if rating not in ("like", "dislike", "favorite"):
        return jsonify({"error": "Invalid rating"}), 400
    if not db_one("SELECT id FROM jokes WHERE id=?", (joke_id,)):
        return jsonify({"error": "Joke not found"}), 404

    rid = str(uuid.uuid4())
    try:
        db_exec(
            "INSERT INTO joke_ratings (id,user_id,joke_id,rating,shared,created_at) VALUES (?,?,?,?,?,?)",
            (rid, g.user_id, joke_id, rating, shared, datetime.now(timezone.utc).isoformat())
        )
    except sqlite3.IntegrityError:
        db_exec(
            "UPDATE joke_ratings SET rating=?, shared=? WHERE user_id=? AND joke_id=?",
            (rating, shared, g.user_id, joke_id)
        )

    # Update score: likes*3 + favorites*4 + shares*5 - dislikes*2
    db_exec("""
        UPDATE jokes SET score = (
            SELECT COALESCE(SUM(CASE rating WHEN 'like' THEN 3 WHEN 'favorite' THEN 4 WHEN 'dislike' THEN -2 ELSE 0 END)
                + SUM(CASE WHEN shared=1 THEN 5 ELSE 0 END), 0)
            FROM joke_ratings WHERE joke_id=?
        ) WHERE id=?
    """, (joke_id, joke_id))
    return jsonify({"success": True})

@app.route("/api/jokes/history")
@require_auth
def joke_history():
    page  = int(request.args.get("page", 1))
    limit = 20
    offset = (page - 1) * limit
    rows = db_all(
        """SELECT j.id, j.text, j.category, j.created_at, jr.rating, jr.shared
           FROM joke_history jh
           JOIN jokes j ON j.id=jh.joke_id
           LEFT JOIN joke_ratings jr ON jr.joke_id=j.id AND jr.user_id=?
           WHERE jh.user_id=?
           ORDER BY jh.viewed_at DESC LIMIT ? OFFSET ?""",
        (g.user_id, g.user_id, limit, offset)
    )
    return jsonify({"jokes": rows, "page": page, "limit": limit})

@app.route("/api/jokes/favorites")
@require_auth
def joke_favorites():
    rows = db_all(
        """SELECT j.id, j.text, j.category, jr.created_at
           FROM joke_ratings jr JOIN jokes j ON j.id=jr.joke_id
           WHERE jr.user_id=? AND jr.rating='favorite'
           ORDER BY jr.created_at DESC""",
        (g.user_id,)
    )
    return jsonify({"favorites": rows})

@app.route("/api/jokes/preferences", methods=["PUT"])
@require_auth
def update_preferences():
    d = request.json or {}
    humor_types    = d.get("humor_types", ["dad jokes"])
    intensity      = int(d.get("intensity", 3))
    language       = d.get("language", "en")
    safe_mode      = int(bool(d.get("safe_mode", True)))
    sexual_content = int(bool(d.get("sexual_content", False)))

    if not isinstance(humor_types, list) or len(humor_types) == 0:
        return jsonify({"error": "At least one humor type required"}), 400
    if not 1 <= intensity <= 5:
        return jsonify({"error": "Intensity must be 1-5"}), 400
    if sexual_content:
        user = db_one("SELECT age_verified FROM users WHERE id=?", (g.user_id,))
        if not user or not user["age_verified"]:
            return jsonify({"error": "Age verification required for adult content"}), 403

    db_exec(
        """INSERT INTO humor_preferences (user_id,humor_types,intensity,language,safe_mode,sexual_content,updated_at)
           VALUES (?,?,?,?,?,?,?)
           ON CONFLICT(user_id) DO UPDATE SET
             humor_types=excluded.humor_types, intensity=excluded.intensity,
             language=excluded.language, safe_mode=excluded.safe_mode,
             sexual_content=excluded.sexual_content, updated_at=excluded.updated_at""",
        (g.user_id, json.dumps(humor_types), intensity, language, safe_mode, sexual_content, datetime.now(timezone.utc).isoformat())
    )
    return jsonify({"success": True})

# ── ROAST ─────────────────────────────────────────────────────────────────────
@app.route("/api/roast/friend", methods=["POST"])
@optional_auth
def roast_friend():
    d = request.json or {}
    name = (d.get("name") or "").strip()
    job  = (d.get("job") or "").strip()
    fact = (d.get("fact") or "").strip()

    if not name or not job or not fact:
        return jsonify({"error": "name, job, and fact are required"}), 400

    prompt = f"""You are a comedy roast writer. Write ONE playful roast joke.

Person: {name}
Job: {job}
Fun fact: {fact}

Rules:
- Playful and witty, NOT cruel
- 2-3 sentences max
- Focus on the job or fact, never appearance
- Something they'd laugh at too
- Return ONLY the roast text"""

    text = call_ai(prompt)
    share_text = f"😂 HaHaTown just roasted {name}:\n\n\"{text}\"\n\nRoast your friends: {request.host_url}"
    return jsonify({"text": text, "shareText": share_text})

@app.route("/api/roast/photo", methods=["POST"])
@optional_auth
def roast_photo():
    if "photo" not in request.files:
        return jsonify({"error": "No photo uploaded"}), 400
    file = request.files["photo"]
    if file.mimetype not in ["image/jpeg", "image/png", "image/webp"]:
        return jsonify({"error": "Only JPEG, PNG, or WebP accepted"}), 400

    img_bytes = file.read()
    b64 = base64.b64encode(img_bytes).decode()
    prompt = """Look at this photo and write ONE playful, witty joke about the context or situation shown.

Rules:
- NEVER comment on physical appearance or body
- Focus only on situation, setting, expression, activity, or vibe
- Warm and funny, not cruel
- 1-2 sentences max
- Return ONLY the joke text"""

    text = call_ai_vision(prompt, b64, file.mimetype)
    share_text = f"😂 HaHaTown roasted my photo:\n\n\"{text}\"\n\nGet roasted: {request.host_url}"
    return jsonify({"text": text, "shareText": share_text})

# ── MEME ──────────────────────────────────────────────────────────────────────
@app.route("/api/meme/templates")
def list_templates():
    rows = db_all("SELECT id, name, category FROM meme_templates WHERE active=1 ORDER BY name")
    return jsonify({"templates": rows})

@app.route("/api/meme/generate", methods=["POST"])
@optional_auth
def create_meme():
    d = request.json or {}
    joke_id   = d.get("joke_id")
    joke_text = d.get("joke_text")
    template_id = d.get("template_id")

    if joke_id:
        row = db_one("SELECT text FROM jokes WHERE id=?", (joke_id,))
        if not row:
            return jsonify({"error": "Joke not found"}), 404
        text = row["text"]
    elif joke_text:
        text = joke_text
    else:
        return jsonify({"error": "Provide joke_id or joke_text"}), 400

    # Get template name
    template_name = "Drake Approves"
    if template_id:
        t = db_one("SELECT name FROM meme_templates WHERE id=?", (template_id,))
        if t:
            template_name = t["name"]
    else:
        templates = db_all("SELECT name FROM meme_templates WHERE active=1 ORDER BY RANDOM() LIMIT 1")
        if templates:
            template_name = templates[0]["name"]

    path = generate_meme_image(text, template_name)

    meme_id = str(uuid.uuid4())
    db_exec(
        "INSERT INTO memes (id,user_id,joke_id,template_id,image_path,created_at) VALUES (?,?,?,?,?,?)",
        (meme_id, g.user_id, joke_id, template_id, str(path), datetime.now(timezone.utc).isoformat())
    )

    return jsonify({"url": f"/memes/{path.name}", "memeId": meme_id})

@app.route("/memes/<filename>")
def serve_meme(filename):
    path = MEME_DIR / filename
    if not path.exists():
        return jsonify({"error": "Meme not found"}), 404
    return send_file(str(path), mimetype="image/png")

# ── BATTLE ────────────────────────────────────────────────────────────────────
@app.route("/api/battle/create", methods=["POST"])
@optional_auth
def create_battle():
    prefs = {"humor_types": ["absurd humor","dad jokes"], "intensity": 3, "language": "en", "safe_mode": 1, "sexual_content": 0}
    if g.user_id:
        prefs = get_prefs(g.user_id)

    joke_a = get_joke_for_user(prefs, [])
    bid    = str(uuid.uuid4())
    token  = uuid.uuid4().hex[:10]
    now    = datetime.now(timezone.utc).isoformat()
    ends   = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
    challenger = g.user_id or "anonymous"

    db_exec(
        "INSERT INTO joke_battles (id,challenger_id,joke_a_id,status,share_token,created_at,ends_at) VALUES (?,?,?,'pending',?,?,?)",
        (bid, challenger, joke_a["id"], token, now, ends)
    )
    host = request.host_url.rstrip("/")
    return jsonify({
        "battleId": bid,
        "shareToken": token,
        "jokeA": joke_a["text"],
        "challengeUrl": f"{host}/battle/{token}",
    })

@app.route("/api/battle/join/<token>", methods=["POST"])
@optional_auth
def join_battle(token):
    battle = db_one("SELECT * FROM joke_battles WHERE share_token=?", (token,))
    if not battle:
        return jsonify({"error": "Battle not found"}), 404
    if battle["status"] != "pending":
        return jsonify({"error": "Battle already started"}), 400

    prefs = {"humor_types": ["absurd humor"], "intensity": 3, "language": "en", "safe_mode": 1, "sexual_content": 0}
    joke_b = get_joke_for_user(prefs, [battle["joke_a_id"]])

    db_exec(
        "UPDATE joke_battles SET joke_b_id=?, opponent_id=?, status='active' WHERE id=?",
        (joke_b["id"], g.user_id or "anonymous", battle["id"])
    )
    joke_a = db_one("SELECT text FROM jokes WHERE id=?", (battle["joke_a_id"],))
    return jsonify({"battleId": battle["id"], "jokeA": joke_a["text"], "jokeB": joke_b["text"]})

@app.route("/api/battle/<battle_id>/vote", methods=["POST"])
@optional_auth
def vote_battle(battle_id):
    voted_for = (request.json or {}).get("voted_for")
    if voted_for not in ("a", "b"):
        return jsonify({"error": "Vote must be 'a' or 'b'"}), 400

    battle = db_one("SELECT * FROM joke_battles WHERE id=?", (battle_id,))
    if not battle or battle["status"] != "active":
        return jsonify({"error": "Battle not active"}), 400

    db_exec(
        "INSERT INTO battle_votes (id,battle_id,voter_id,voted_for,created_at) VALUES (?,?,?,?,?)",
        (str(uuid.uuid4()), battle_id, g.user_id or "anon", voted_for, datetime.now(timezone.utc).isoformat())
    )
    field = "votes_a" if voted_for == "a" else "votes_b"
    db_exec(f"UPDATE joke_battles SET {field}={field}+1 WHERE id=?", (battle_id,))
    return jsonify({"success": True})

@app.route("/api/battle/<token>")
def get_battle(token):
    battle = db_one("SELECT * FROM joke_battles WHERE share_token=? OR id=?", (token, token))
    if not battle:
        return jsonify({"error": "Battle not found"}), 404
    ja = db_one("SELECT text FROM jokes WHERE id=?", (battle["joke_a_id"],))
    jb = db_one("SELECT text FROM jokes WHERE id=?", (battle["joke_b_id"],)) if battle["joke_b_id"] else None
    return jsonify({**battle, "joke_a_text": ja["text"] if ja else None, "joke_b_text": jb["text"] if jb else None})

# ── DEMO API EXPLORER (HTML) ───────────────────────────────────────────────────
@app.route("/")
def index():
    providers_active = []
    if GROQ_KEY:   providers_active.append("Groq")
    if GEMINI_KEY: providers_active.append("Gemini")
    ai_status = ("✅ " + " + ".join(providers_active) + " Connected") if providers_active else "⚠️ Using joke pool"
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>HaHaTown 😂</title>
<style>
  :root {
    --bg: #0d0d14;
    --surface: #16161f;
    --surface2: #1e1e2e;
    --border: #2a2a3d;
    --accent: #f5a623;
    --accent2: #ff6b6b;
    --accent3: #7c6aff;
    --accent4: #00d2ff;
    --text: #f0f0ff;
    --text2: #9898b8;
    --green: #00e676;
    --radius: 16px;
  }
  .header-login { background: rgba(245,166,35,.15); color: var(--accent); border: 1px solid rgba(245,166,35,.3);
                  border-radius: 999px; padding: .35rem .9rem; font-size: .78rem; font-weight: 700;
                  cursor: pointer; transition: all .18s; }
  .header-login:hover { background: rgba(245,166,35,.3); }
  .header-login.logged-in { background: rgba(0,230,118,.12); color: var(--green);
                            border-color: rgba(0,230,118,.3); }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         background: var(--bg); color: var(--text); min-height: 100vh; }

  /* HEADER */
  .header {
    background: linear-gradient(135deg, #1a0533 0%, #0d1544 50%, #0d2233 100%);
    border-bottom: 1px solid var(--border);
    padding: 1rem 1.5rem;
    display: flex; align-items: center; justify-content: space-between;
    position: sticky; top: 0; z-index: 100;
    backdrop-filter: blur(20px);
  }
  .logo { font-size: 1.6rem; font-weight: 900; letter-spacing: -1px;
          background: linear-gradient(135deg, #f5a623, #ff6b6b);
          -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .ai-badge { font-size: .75rem; padding: .3rem .75rem; border-radius: 999px;
              background: rgba(0,230,118,.12); color: var(--green);
              border: 1px solid rgba(0,230,118,.3); font-weight: 600; }

  /* TABS */
  .tabs { display: flex; gap: .5rem; padding: 1rem 1.5rem .5rem;
          overflow-x: auto; scrollbar-width: none; }
  .tabs::-webkit-scrollbar { display: none; }
  .tab { flex-shrink: 0; padding: .55rem 1.2rem; border-radius: 999px; border: none;
         cursor: pointer; font-size: .88rem; font-weight: 700; transition: all .2s;
         background: var(--surface2); color: var(--text2); }
  .tab.active { background: linear-gradient(135deg, var(--accent), var(--accent2));
                color: #0d0d14; }

  /* MAIN */
  .main { max-width: 680px; margin: 0 auto; padding: 1rem 1.2rem 6rem; }
  .panel { display: none; }
  .panel.active { display: block; }

  /* CARDS */
  .card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 1.5rem;
    margin-bottom: 1rem;
  }
  .card-title { font-size: 1rem; font-weight: 800; margin-bottom: 1rem;
                display: flex; align-items: center; gap: .5rem; }

  /* JOKE DISPLAY */
  .joke-box {
    background: linear-gradient(135deg, #1a0a2e 0%, #0d1a3a 100%);
    border: 1px solid rgba(124,106,255,.3);
    border-radius: var(--radius);
    padding: 2rem 1.5rem;
    margin-bottom: 1rem;
    min-height: 140px;
    display: flex; flex-direction: column; justify-content: center; align-items: center;
    text-align: center; position: relative; overflow: hidden;
  }
  .joke-box::before {
    content: ""; position: absolute; inset: 0;
    background: radial-gradient(ellipse at 50% 0%, rgba(124,106,255,.15) 0%, transparent 70%);
  }
  .joke-text { font-size: 1.25rem; font-weight: 600; line-height: 1.6;
               color: var(--text); position: relative; z-index: 1; }
  .joke-meta { margin-top: .75rem; display: flex; gap: .5rem; justify-content: center;
               position: relative; z-index: 1; }
  .badge { font-size: .7rem; font-weight: 700; padding: .2rem .6rem; border-radius: 999px;
           text-transform: uppercase; letter-spacing: .05em; }
  .badge-cat { background: rgba(124,106,255,.2); color: #a89aff; border: 1px solid rgba(124,106,255,.3); }
  .badge-src { background: rgba(0,210,255,.1); color: var(--accent4); border: 1px solid rgba(0,210,255,.2); }
  .joke-empty { color: var(--text2); font-size: 1rem; }

  /* PILL FILTERS */
  .filters { margin-bottom: 1rem; }
  .filter-label { font-size: .78rem; color: var(--text2); font-weight: 600;
                  text-transform: uppercase; letter-spacing: .06em; margin-bottom: .5rem; }
  .pills { display: flex; flex-wrap: wrap; gap: .4rem; }
  .pill { padding: .4rem .85rem; border-radius: 999px; border: 1px solid var(--border);
          cursor: pointer; font-size: .82rem; font-weight: 600; transition: all .18s;
          background: var(--surface2); color: var(--text2); user-select: none; }
  .pill:hover { border-color: var(--accent); color: var(--accent); }
  .pill.on { background: linear-gradient(135deg, var(--accent), var(--accent2));
             color: #0d0d14; border-color: transparent; }



  /* LANG TOGGLE */
  .lang-row { display: flex; gap: .4rem; margin-bottom: 1rem; }
  .lang-btn { flex: 1; padding: .5rem; border-radius: 10px; border: 1px solid var(--border);
              cursor: pointer; font-size: .85rem; font-weight: 700; transition: all .18s;
              background: var(--surface2); color: var(--text2); }
  .lang-btn.on { background: rgba(0,210,255,.12); color: var(--accent4);
                 border-color: rgba(0,210,255,.4); }

  /* ACTION BUTTONS */
  .actions { display: flex; gap: .6rem; flex-wrap: wrap; margin-bottom: 1rem; }
  .btn { padding: .75rem 1.5rem; border-radius: 12px; border: none; cursor: pointer;
         font-size: .9rem; font-weight: 800; transition: all .18s; flex: 1;
         min-width: 120px; display: flex; align-items: center; justify-content: center; gap: .4rem; }
  .btn:disabled { opacity: .5; cursor: not-allowed; }
  .btn-primary { background: linear-gradient(135deg, var(--accent), #ff9500);
                 color: #0d0d14; box-shadow: 0 4px 20px rgba(245,166,35,.3); }
  .btn-primary:hover:not(:disabled) { box-shadow: 0 6px 28px rgba(245,166,35,.5); transform: translateY(-1px); }
  .btn-secondary { background: var(--surface2); color: var(--text); border: 1px solid var(--border); }
  .btn-secondary:hover:not(:disabled) { border-color: var(--accent3); color: var(--accent3); }
  .btn-danger { background: linear-gradient(135deg, var(--accent2), #ff4444);
                color: white; box-shadow: 0 4px 20px rgba(255,107,107,.3); }
  .btn-purple { background: linear-gradient(135deg, var(--accent3), #9c6aff);
                color: white; box-shadow: 0 4px 20px rgba(124,106,255,.3); }
  .btn-full { width: 100%; min-width: unset; }

  /* SHARE ROW */
  .share-row { display: flex; gap: .5rem; margin-top: .75rem; }
  .share-btn { flex: 1; padding: .6rem; border-radius: 10px; border: none; cursor: pointer;
               font-size: .8rem; font-weight: 700; transition: all .18s; }
  .share-wa { background: rgba(37,211,102,.12); color: #25d366; border: 1px solid rgba(37,211,102,.3); }
  .share-tg { background: rgba(0,136,204,.12); color: #0088cc; border: 1px solid rgba(0,136,204,.3); }
  .share-cp { background: var(--surface2); color: var(--text2); border: 1px solid var(--border); }
  .share-wa:hover { background: rgba(37,211,102,.25); }
  .share-tg:hover { background: rgba(0,136,204,.25); }
  .share-cp:hover { background: var(--border); }

  /* RATING ROW */
  .rating-row { display: flex; gap: .5rem; }
  .rate-btn { flex: 1; padding: .6rem; border-radius: 10px; border: 1px solid var(--border);
              cursor: pointer; font-size: .85rem; font-weight: 700; transition: all .18s;
              background: var(--surface2); color: var(--text2); }
  .rate-btn:hover { border-color: var(--accent); }
  .rate-btn.active { background: linear-gradient(135deg, var(--accent), var(--accent2));
                     color: #0d0d14; border-color: transparent; }

  /* FORM */
  .form-group { margin-bottom: .85rem; }
  .form-label { font-size: .78rem; color: var(--text2); font-weight: 600;
                text-transform: uppercase; letter-spacing: .06em;
                display: block; margin-bottom: .4rem; }
  .form-input { width: 100%; padding: .7rem 1rem; background: var(--surface2);
                border: 1px solid var(--border); border-radius: 10px; color: var(--text);
                font-size: .9rem; transition: border-color .18s; outline: none; }
  .form-input:focus { border-color: var(--accent3); }
  .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: .75rem; }

  /* RESULT CARD */
  .result-card {
    margin-top: 1rem; padding: 1.5rem;
    border-radius: var(--radius); border: 1px solid;
    display: none;
  }
  .result-card.show { display: block; }
  .result-joke { border-color: rgba(124,106,255,.4); background: linear-gradient(135deg, #1a0a2e, #0d1a3a); }
  .result-roast { border-color: rgba(255,107,107,.4); background: linear-gradient(135deg, #2e0a0a, #1a0d0d); }
  .result-meme { border-color: rgba(0,210,255,.3); background: var(--surface2); }
  .result-text { font-size: 1.1rem; font-weight: 600; line-height: 1.6; color: var(--text); }
  .result-img { width: 100%; border-radius: 10px; margin-top: .75rem; }

  /* BATTLE */
  .battle-link { background: rgba(124,106,255,.1); border: 1px solid rgba(124,106,255,.3);
                 border-radius: 10px; padding: 1rem; margin-bottom: 1rem;
                 font-size: .85rem; color: var(--text2); word-break: break-all; }
  .battle-link strong { color: var(--accent3); display: block; margin-bottom: .3rem; font-size: .75rem; text-transform: uppercase; }
  .joke-choice { width: 100%; text-align: left; padding: 1.25rem; border-radius: 12px;
                 border: 1px solid var(--border); background: var(--surface2); color: var(--text);
                 cursor: pointer; margin-bottom: .6rem; font-size: .95rem; font-weight: 600;
                 transition: all .2s; }
  .joke-choice:hover { border-color: var(--accent); }
  .joke-choice.voted { border-color: var(--accent); background: rgba(245,166,35,.1); }
  .joke-label { font-size: .7rem; font-weight: 800; text-transform: uppercase; letter-spacing: .08em;
                color: var(--accent); margin-bottom: .4rem; display: block; }

  /* AUTH */
  .auth-toggle { display: flex; gap: .4rem; background: var(--surface2);
                 border-radius: 12px; padding: .35rem; margin-bottom: 1.25rem; }
  .auth-tab { flex: 1; padding: .55rem; border-radius: 8px; border: none; cursor: pointer;
              font-size: .85rem; font-weight: 700; background: transparent; color: var(--text2); transition: all .18s; }
  .auth-tab.active { background: var(--surface); color: var(--text);
                     box-shadow: 0 2px 8px rgba(0,0,0,.3); }
  .token-badge { font-size: .72rem; padding: .2rem .6rem; border-radius: 999px;
                 background: rgba(0,230,118,.12); color: var(--green);
                 border: 1px solid rgba(0,230,118,.25); }

  /* MEME IMG */
  #meme-out { display: none; margin-top: 1rem; }
  #meme-out.show { display: block; }
  #meme-out img { width: 100%; border-radius: 12px; }

  /* TOAST */
  .toast { position: fixed; bottom: 1.5rem; left: 50%; transform: translateX(-50%) translateY(100px);
           background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
           padding: .75rem 1.25rem; font-size: .88rem; font-weight: 600; z-index: 999;
           transition: transform .3s; white-space: nowrap; }
  .toast.show { transform: translateX(-50%) translateY(0); }
</style>
</head>
<body>

<div class="header">
  <div class="logo">😂 HaHaTown</div>
  <div style="display:flex;align-items:center;gap:.75rem">
    <button class="header-login" id="header-login-btn" onclick="showTab('auth',document.querySelector('[onclick*=auth]'))">👤 Sign In</button>
    <div class="ai-badge" id="ai-badge">""" + ai_status + """</div>
  </div>
</div>

<div class="tabs">
  <button class="tab active" onclick="showTab('jokes',this)">😂 Jokes</button>
  <button class="tab" onclick="showTab('roast',this)">🔥 Roast</button>
  <button class="tab" onclick="showTab('meme',this)">🖼️ Meme</button>
  <button class="tab" onclick="showTab('battle',this)">⚔️ Battle</button>

</div>

<div class="main">

<!-- ── JOKES ── -->
<div class="panel active" id="panel-jokes">
  <div class="joke-box" id="joke-box">
    <p class="joke-empty">Hit "Get Joke" to start laughing 😄</p>
  </div>

  <div class="rating-row" id="rating-row" style="display:none;margin-bottom:.75rem">
    <button class="rate-btn" onclick="rate('like')">👍 Like</button>
    <button class="rate-btn" onclick="rate('dislike')">👎 Dislike</button>
    <button class="rate-btn" onclick="rate('favorite')">❤️ Save</button>
  </div>

  <div class="actions" id="joke-actions" style="display:none">
    <button class="btn btn-secondary" onclick="shareJoke('whatsapp')">💬 WhatsApp</button>
    <button class="btn btn-secondary" onclick="shareJoke('telegram')">✈️ Telegram</button>
    <button class="btn btn-secondary" onclick="shareJoke('copy')">📋 Copy</button>
  </div>

  <div class="card">
    <div class="card-title">🎛️ Customize</div>

    <div class="filters">
      <div class="filter-label">Humor Style</div>
      <div class="pills" id="humor-pills">
        <span class="pill on" data-val="dad jokes">👨 Dad Jokes</span>
        <span class="pill on" data-val="absurd humor">🌀 Absurd</span>
        <span class="pill" data-val="tech jokes">💻 Tech</span>
        <span class="pill" data-val="relationship jokes">💕 Relationship</span>
        <span class="pill" data-val="dark humor">🖤 Dark</span>
        <span class="pill" data-val="work humor">💼 Work</span>
      </div>
    </div>



    <div class="filter-label">Language</div>
    <div class="lang-row" style="margin-bottom:1rem">
      <button class="lang-btn on" id="lang-en" onclick="setLang('en')">🇺🇸 English</button>
      <button class="lang-btn" id="lang-he" onclick="setLang('he')">🇮🇱 עברית</button>
    </div>

    <button class="btn btn-primary btn-full" id="joke-btn" onclick="getJoke()">
      😂 Get Joke
    </button>
    <button class="btn btn-secondary btn-full" id="next-btn" onclick="getJoke()" style="margin-top:.5rem;display:none">
      ➡ Next Joke
    </button>
  </div>
</div>

<!-- ── ROAST ── -->
<div class="panel" id="panel-roast">
  <div class="card">
    <div class="card-title">🔥 Roast a Friend</div>
    <div class="form-row">
      <div class="form-group">
        <label class="form-label">Name</label>
        <input class="form-input" id="r-name" placeholder="e.g. Alex">
      </div>
      <div class="form-group">
        <label class="form-label">Job</label>
        <input class="form-input" id="r-job" placeholder="e.g. Developer">
      </div>
    </div>
    <div class="form-group">
      <label class="form-label">Fun Fact</label>
      <input class="form-input" id="r-fact" placeholder="e.g. Has 200 browser tabs open">
    </div>
    <button class="btn btn-danger btn-full" id="roast-btn" onclick="roastFriend()">🔥 Roast Them!</button>
    <div class="result-card result-roast" id="roast-result">
      <div class="result-text" id="roast-text"></div>
      <div class="share-row" style="margin-top:1rem">
        <button class="share-btn share-wa" onclick="shareRoast('whatsapp')">💬 WhatsApp</button>
        <button class="share-btn share-tg" onclick="shareRoast('telegram')">✈️ Telegram</button>
        <button class="share-btn share-cp" onclick="shareRoast('copy')">📋 Copy</button>
      </div>
    </div>
  </div>

  <div class="card">
    <div class="card-title">📸 Roast My Photo</div>
    <label style="display:flex;flex-direction:column;align-items:center;gap:.75rem;padding:2rem;border:1px dashed var(--border);border-radius:12px;cursor:pointer;transition:border-color .18s" id="photo-drop">
      <span style="font-size:2.5rem">📸</span>
      <span style="color:var(--text2);font-size:.9rem;font-weight:600" id="photo-label">Upload a photo to roast</span>
      <input type="file" accept="image/*" id="photo-input" style="display:none" onchange="roastPhoto(this)">
    </label>
    <div class="result-card result-roast" id="photo-result">
      <div class="result-text" id="photo-text"></div>
    </div>
  </div>
</div>

<!-- ── MEME ── -->
<div class="panel" id="panel-meme">
  <div class="card">
    <div class="card-title">🖼️ Generate a Meme</div>
    <div class="form-group">
      <label class="form-label">Joke Text</label>
      <input class="form-input" id="meme-text"
             placeholder="Enter a joke or get one from the Jokes tab"
             value="I told my computer I needed a break. Now it won't stop sending me Kit-Kat ads.">
    </div>
    <div class="form-group">
      <label class="form-label">Template</label>
      <select class="form-input" id="meme-template">
        <option value="">🎲 Random</option>
      </select>
    </div>
    <button class="btn btn-purple btn-full" id="meme-btn" onclick="makeMeme()">🖼️ Generate Meme</button>
    <div id="meme-out">
      <img id="meme-img" src="" alt="Generated meme">
      <div class="share-row" style="margin-top:.75rem">
        <button class="share-btn share-wa" onclick="shareMeme('whatsapp')">💬 WhatsApp</button>
        <button class="share-btn share-cp" onclick="shareMeme('copy')">🔗 Copy Link</button>
      </div>
    </div>
  </div>
</div>

<!-- ── BATTLE ── -->
<div class="panel" id="panel-battle">
  <div class="card">
    <div class="card-title">⚔️ Joke Battle</div>
    <p style="color:var(--text2);font-size:.9rem;margin-bottom:1rem">Challenge a friend! Each gets an AI joke. Vote who's funnier.</p>
    <div id="battle-lobby">
      <button class="btn btn-purple btn-full" id="battle-btn" onclick="createBattle()">⚔️ Start a Battle</button>
    </div>
    <div id="battle-active" style="display:none">
      <div class="battle-link">
        <strong>📤 Send this link to your friend</strong>
        <span id="battle-url"></span>
        <button class="share-btn share-cp" style="margin-top:.5rem;width:100%" onclick="copyBattleLink()">📋 Copy Link</button>
      </div>
      <button class="joke-choice" id="choice-a" onclick="vote('a')">
        <span class="joke-label">Your Joke</span>
        <span id="joke-a-text"></span>
      </button>
      <button class="joke-choice" id="choice-b" onclick="vote('b')" style="opacity:.5">
        <span class="joke-label">Friend's Joke</span>
        <span id="joke-b-text">Waiting for friend to join...</span>
      </button>
      <button class="btn btn-secondary btn-full" onclick="resetBattle()" style="margin-top:.5rem">← New Battle</button>
    </div>
  </div>
</div>

<!-- ── ACCOUNT ── -->
<div class="panel" id="panel-auth">
  <div class="card" id="auth-card">
    <div class="auth-toggle">
      <button class="auth-tab active" id="tab-login" onclick="setAuthMode('login')">Sign In</button>
      <button class="auth-tab" id="tab-register" onclick="setAuthMode('register')">Register</button>
    </div>
    <div class="form-group" id="username-group" style="display:none">
      <label class="form-label">Username</label>
      <input class="form-input" id="reg-username" placeholder="e.g. jokester99">
    </div>
    <div class="form-group">
      <label class="form-label">Email</label>
      <input class="form-input" id="auth-email" type="email" placeholder="you@example.com">
    </div>
    <div class="form-group">
      <label class="form-label">Password</label>
      <input class="form-input" id="auth-password" type="password" placeholder="Min 8 characters">
    </div>
    <div id="tos-group" style="display:none;margin-bottom:1rem">
      <label style="display:flex;align-items:flex-start;gap:.6rem;cursor:pointer;font-size:.83rem;color:var(--text2)">
        <input type="checkbox" id="tos-check" style="margin-top:2px;accent-color:var(--accent)">
        I'm 18+ and accept the Terms — jokes may include satire
      </label>
    </div>
    <button class="btn btn-primary btn-full" id="auth-btn" onclick="doAuth()">Sign In</button>
    <div class="result-card" id="auth-result" style="margin-top:.75rem;border-color:rgba(255,107,107,.3);background:rgba(255,107,107,.05)">
      <div class="result-text" id="auth-msg" style="font-size:.9rem"></div>
    </div>
  </div>
  <div class="card" id="profile-card" style="display:none">
    <div style="display:flex;align-items:center;gap:.75rem;margin-bottom:1rem">
      <div style="width:48px;height:48px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--accent2));display:flex;align-items:center;justify-content:center;font-size:1.4rem">😂</div>
      <div>
        <div style="font-weight:800" id="profile-name">—</div>
        <div class="token-badge">✅ Signed in</div>
      </div>
    </div>
    <button class="btn btn-secondary btn-full" onclick="logout()">Sign Out</button>
  </div>
</div>

</div><!-- /main -->

<div class="toast" id="toast"></div>

<script>
let TOKEN = localStorage.getItem('jk_token') || '';
let currentJoke = null;
let currentRoast = '';
let battleId = null;
let battleUrl = '';
let currentRating = null;
let lang = 'en';

// ── UTILS ─────────────────────────────────────────────────────────────────────
function toast(msg, dur=2500) {
  const t = document.getElementById('toast');
  t.textContent = msg; t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), dur);
}

async function api(method, path, body=null) {
  const h = {'Content-Type':'application/json'};
  if (TOKEN) h['Authorization'] = 'Bearer ' + TOKEN;
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 30000);
  try {
    const r = await fetch(path, {method, headers:h, body: body ? JSON.stringify(body) : null, signal: ctrl.signal});
    clearTimeout(timer);
    const ct = r.headers.get('content-type') || '';
    if (ct.includes('json')) return [r.ok, await r.json()];
    return [r.ok, {error: await r.text()}];
  } catch(e) {
    clearTimeout(timer);
    return [false, {error: e.name === 'AbortError' ? 'Request timed out' : e.message}];
  }
}

function setLoading(id, loading, text) {
  const b = document.getElementById(id);
  if (!b) return;
  b.disabled = loading;
  if (loading) { b.dataset.orig = b.innerHTML; b.innerHTML = '⏳ ' + text; }
  else if (b.dataset.orig) b.innerHTML = b.dataset.orig;
}

// ── TABS ──────────────────────────────────────────────────────────────────────
function showTab(id, el) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.getElementById('panel-' + id).classList.add('active');
  el.classList.add('active');
}

// ── FILTERS ───────────────────────────────────────────────────────────────────
document.querySelectorAll('#humor-pills .pill').forEach(p => {
  p.onclick = () => p.classList.toggle('on');
});

function getHumorTypes() {
  const pills = [...document.querySelectorAll('#humor-pills .pill.on')];
  return pills.length ? pills.map(p => p.dataset.val) : ['dad jokes'];
}

function setLang(l) {
  lang = l;
  document.getElementById('lang-en').classList.toggle('on', l === 'en');
  document.getElementById('lang-he').classList.toggle('on', l === 'he');
}

// ── JOKES ─────────────────────────────────────────────────────────────────────
async function getJoke() {
  setLoading('joke-btn', true, 'Generating...');
  const types = getHumorTypes();
  const [ok, data] = await api('GET', `/api/jokes/generate?lang=${lang}&intensity=${intensity}&types=${encodeURIComponent(types.join(','))}`);
  setLoading('joke-btn', false);
  if (!ok || data.error) { toast('❌ ' + (data.error || 'Failed')); return; }

  currentJoke = data;
  currentRating = null;
  document.querySelectorAll('.rate-btn').forEach(b => b.classList.remove('active'));

  const box = document.getElementById('joke-box');
  const srcLabel = data.source === 'ai' ? '✨ Fresh AI' : data.source === 'pool' ? '💾 Pool' : '⚡ Cached';
  box.innerHTML = `
    <p class="joke-text" dir="${lang==='he'?'rtl':'ltr'}">${data.text}</p>
    <div class="joke-meta">
      <span class="badge badge-cat">${data.category}</span>
      <span class="badge badge-src">${srcLabel}</span>
    </div>`;

  document.getElementById('rating-row').style.display = 'flex';
  document.getElementById('joke-actions').style.display = 'flex';
  document.getElementById('next-btn').style.display = 'block';
  document.getElementById('meme-text').value = data.text;
}

async function rate(r) {
  if (!currentJoke) return;
  currentRating = r;
  document.querySelectorAll('.rate-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  if (!TOKEN) { toast('Sign in to save ratings'); return; }
  await api('POST', '/api/jokes/rate', {joke_id: currentJoke.id, rating: r});
  toast(r === 'favorite' ? '❤️ Saved to favorites!' : r === 'like' ? '👍 Liked!' : '👎 Noted');
}

function shareJoke(platform) {
  if (!currentJoke) return;
  const text = `😂 HaHaTown\n\n${currentJoke.text}\n\nTry it: ${location.origin}`;
  if (platform === 'copy') { navigator.clipboard.writeText(text); toast('📋 Copied!'); }
  else if (platform === 'whatsapp') window.open('https://wa.me/?text=' + encodeURIComponent(text));
  else if (platform === 'telegram') window.open('https://t.me/share/url?url=' + encodeURIComponent(location.origin) + '&text=' + encodeURIComponent('😂 ' + currentJoke.text));
}

// ── ROAST ─────────────────────────────────────────────────────────────────────
async function roastFriend() {
  const name = document.getElementById('r-name').value.trim();
  const job  = document.getElementById('r-job').value.trim();
  const fact = document.getElementById('r-fact').value.trim();
  if (!name || !job || !fact) { toast('Fill in all fields!'); return; }
  setLoading('roast-btn', true, 'Roasting...');
  const [ok, data] = await api('POST', '/api/roast/friend', {name, job, fact});
  setLoading('roast-btn', false);
  if (!ok || data.error) { toast('❌ ' + (data.error || 'Failed')); return; }
  currentRoast = data.shareText || data.text;
  document.getElementById('roast-text').textContent = data.text || data.roast;
  document.getElementById('roast-result').classList.add('show');
}

function shareRoast(platform) {
  if (!currentRoast) return;
  if (platform === 'copy') { navigator.clipboard.writeText(currentRoast); toast('📋 Copied!'); }
  else if (platform === 'whatsapp') window.open('https://wa.me/?text=' + encodeURIComponent(currentRoast));
  else if (platform === 'telegram') window.open('https://t.me/share/url?url=' + encodeURIComponent(location.origin) + '&text=' + encodeURIComponent(currentRoast));
}

async function roastPhoto(input) {
  const file = input.files[0]; if (!file) return;
  document.getElementById('photo-label').textContent = '⏳ Analyzing photo...';
  const form = new FormData(); form.append('photo', file);
  const h = {}; if (TOKEN) h['Authorization'] = 'Bearer ' + TOKEN;
  try {
    const r = await fetch('/api/roast/photo', {method:'POST', headers:h, body:form});
    const data = await r.json();
    document.getElementById('photo-label').textContent = 'Upload a photo to roast';
    if (data.error) { toast('❌ ' + data.error); return; }
    document.getElementById('photo-text').textContent = data.text;
    document.getElementById('photo-result').classList.add('show');
  } catch(e) { document.getElementById('photo-label').textContent = 'Upload a photo to roast'; toast('❌ Failed'); }
}

// ── MEME ──────────────────────────────────────────────────────────────────────
async function loadTemplates() {
  const [ok, data] = await api('GET', '/api/meme/templates');
  if (!ok) return;
  const sel = document.getElementById('meme-template');
  data.templates.forEach(t => {
    const o = document.createElement('option');
    o.value = t.id; o.textContent = t.name;
    sel.appendChild(o);
  });
}

async function makeMeme() {
  const text = document.getElementById('meme-text').value.trim();
  const tid  = document.getElementById('meme-template').value;
  if (!text) { toast('Enter some joke text!'); return; }
  setLoading('meme-btn', true, 'Creating meme...');
  const body = {joke_text: text};
  if (tid) body.template_id = tid;
  const [ok, data] = await api('POST', '/api/meme/generate', body);
  setLoading('meme-btn', false);
  if (!ok || data.error) { toast('❌ ' + (data.error || 'Failed')); return; }
  document.getElementById('meme-img').src = data.url;
  document.getElementById('meme-out').classList.add('show');
}

function shareMeme(platform) {
  const url = location.origin + document.getElementById('meme-img').src.replace(location.origin,'');
  if (platform === 'copy') { navigator.clipboard.writeText(url); toast('🔗 Link copied!'); }
  else if (platform === 'whatsapp') window.open('https://wa.me/?text=' + encodeURIComponent('😂 Check this meme: ' + url));
}

// ── BATTLE ────────────────────────────────────────────────────────────────────
async function createBattle() {
  setLoading('battle-btn', true, 'Creating...');
  const [ok, data] = await api('POST', '/api/battle/create', {});
  setLoading('battle-btn', false);
  if (!ok || data.error) { toast('❌ ' + (data.error || 'Failed')); return; }
  battleId  = data.battleId;
  battleUrl = data.challengeUrl;
  document.getElementById('battle-url').textContent = battleUrl;
  document.getElementById('joke-a-text').textContent = data.jokeA;
  document.getElementById('battle-lobby').style.display = 'none';
  document.getElementById('battle-active').style.display = 'block';
}

function copyBattleLink() {
  navigator.clipboard.writeText(battleUrl); toast('🔗 Battle link copied!');
}

async function vote(side) {
  if (!battleId) return;
  const [ok] = await api('POST', `/api/battle/${battleId}/vote`, {voted_for: side});
  if (ok) {
    document.getElementById('choice-' + side).classList.add('voted');
    document.querySelectorAll('.joke-choice').forEach(b => b.disabled = true);
    toast(side === 'a' ? '✅ Voted for your joke!' : '✅ Voted for friend joke!');
  }
}

function resetBattle() {
  battleId = null; battleUrl = '';
  document.getElementById('battle-lobby').style.display = 'block';
  document.getElementById('battle-active').style.display = 'none';
  document.querySelectorAll('.joke-choice').forEach(b => { b.classList.remove('voted'); b.disabled = false; });
}

// ── AUTH ──────────────────────────────────────────────────────────────────────
function setAuthMode(mode) {
  document.getElementById('username-group').style.display = mode === 'register' ? 'block' : 'none';
  document.getElementById('tos-group').style.display = mode === 'register' ? 'block' : 'none';
  document.getElementById('auth-btn').textContent = mode === 'register' ? '🎉 Create Account' : '🚀 Sign In';
  document.getElementById('tab-login').classList.toggle('active', mode === 'login');
  document.getElementById('tab-register').classList.toggle('active', mode === 'register');
  document.getElementById('auth-btn').dataset.mode = mode;
}

async function doAuth() {
  const mode = document.getElementById('auth-btn').dataset.mode || 'login';
  const email = document.getElementById('auth-email').value.trim();
  const password = document.getElementById('auth-password').value;
  const username = document.getElementById('reg-username').value.trim();
  if (!email || !password) { toast('Fill in email and password'); return; }
  if (mode === 'register' && !document.getElementById('tos-check').checked) {
    toast('Please accept the terms'); return;
  }
  setLoading('auth-btn', true, mode === 'login' ? 'Signing in...' : 'Creating...');
  const body = mode === 'login'
    ? {email, password}
    : {email, password, username, age_verified: true, accepted_tos: true};
  const [ok, data] = await api('POST', `/api/auth/${mode}`, body);
  setLoading('auth-btn', false);
  if (data.token) {
    TOKEN = data.token;
    localStorage.setItem('jk_token', TOKEN);
    showProfile(username || email.split('@')[0]);
    toast('✅ Welcome!');
  } else {
    document.getElementById('auth-msg').textContent = data.error || 'Something went wrong';
    document.getElementById('auth-result').classList.add('show');
  }
}

function showProfile(name) {
  const hb = document.getElementById('header-login-btn');
  if (hb) { hb.textContent = '✅ ' + name; hb.classList.add('logged-in'); }
  document.getElementById('auth-card').style.display = 'none';
  document.getElementById('profile-card').style.display = 'block';
  document.getElementById('profile-name').textContent = '@' + name;
}

function logout() {
  const hb = document.getElementById('header-login-btn');
  if (hb) { hb.textContent = '👤 Sign In'; hb.classList.remove('logged-in'); }
  TOKEN = ''; localStorage.removeItem('jk_token');
  document.getElementById('auth-card').style.display = 'block';
  document.getElementById('profile-card').style.display = 'none';
  toast('👋 Signed out');
}

// ── INIT ──────────────────────────────────────────────────────────────────────
document.getElementById('auth-btn').dataset.mode = 'login';
loadTemplates();
if (TOKEN) {
  showProfile(localStorage.getItem('jk_username') || 'user');
}
</script>
</body>
</html>"""

# ── STARTUP ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", 4000))
    print(f"\n{'='*55}")
    print(f"  😂  HaHaTown API Server")
    print(f"{'='*55}")
    print(f"  URL:    http://localhost:{port}")
    print(f"  DB:     {DB_PATH}")
    if AI_KEY:
        print(f"  AI:     ✅ {AI_PROVIDER.title()} AI — live AI jokes!")
    else:
        print(f"  AI:     ⚠️  Using joke pool (no API key set)")
        print(f"")
        print(f"  To enable AI jokes, set your Groq key:")
        print(f"  Windows:  set GROQ_API_KEY=gsk_...")
        print(f"  Then restart:  python server.py")
    print(f"{'='*55}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
