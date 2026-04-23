"""
JokeAI — Full Backend Server
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
JWT_SECRET = os.getenv("JWT_SECRET", "jokeai-dev-secret-change-in-production")
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
_media_base = Path("/tmp/jokeai") if _is_cloud else BASE_DIR

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
    ("Why don't scientists trust atoms? Because they make up everything.", "dad jokes"),
    ("I told my computer I needed a break. Now it won't stop sending me Kit-Kat ads.", "tech jokes"),
    ("My wife told me I had to stop acting like a flamingo. I had to put my foot down.", "relationship jokes"),
    ("I asked the universe for a sign. It sent me a stop sign. I'm still not sure what it means.", "absurd humor"),
    ("The meeting could have been an email. The email could have been a text. The text could have been silence.", "work humor"),
    ("A SQL query walks into a bar, walks up to two tables and asks... 'Can I join you?'", "tech jokes"),
    ("I'm reading a book about anti-gravity. It's impossible to put down.", "dad jokes"),
    ("Our relationship is like a software update: I never know when it's happening and it always takes longer than expected.", "relationship jokes"),
    ("I told my boss three companies were after me and I needed a raise. He asked which ones. I said gas, electric, and water.", "work humor"),
    ("Existence is just the universe's way of debugging itself, and we are all unresolved stack traces.", "absurd humor"),
    ("Why did the developer go broke? Because he used up all his cache.", "tech jokes"),
    ("I love you more than coffee. Please don't make me prove it.", "relationship jokes"),
    ("My calendar says I have a meeting with 'Future Successful Me'. He cancelled again.", "work humor"),
    ("Dad, are we pyromaniacs? Yes, we arson.", "dad jokes"),
    ("Sometimes I think the WiFi password is the most intimate thing two people can share.", "relationship jokes"),
]

def init_db():
    """Initialize DB — called at module level so gunicorn picks it up."""
    try:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(str(DB_PATH))
        db.executescript(SCHEMA)
        db.executescript(SEED_TEMPLATES)
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
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")

def call_claude(prompt: str, system: str = "", max_tokens: int = 300) -> str:
    """Call Anthropic Claude API directly via HTTP (no SDK needed)."""
    import urllib.request
    if not ANTHROPIC_KEY:
        return _fallback_joke(prompt)
    body = json.dumps({
        "model": "claude-3-5-haiku-20241022",
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
        **({"system": system} if system else {})
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"[AI] Claude call failed: {e}")
        return _fallback_joke(prompt)

def call_claude_vision(prompt: str, image_b64: str, mime: str) -> str:
    """Call Claude with an image."""
    import urllib.request
    if not ANTHROPIC_KEY:
        return "He looks like someone who just realized he sent that message to the wrong chat."
    body = json.dumps({
        "model": "claude-3-5-haiku-20241022",
        "max_tokens": 200,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image", "source": {"type": "base64", "media_type": mime, "data": image_b64}},
                {"type": "text", "text": prompt}
            ]
        }]
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={"Content-Type": "application/json", "x-api-key": ANTHROPIC_KEY, "anthropic-version": "2023-06-01"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read())
            return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"[AI] Vision call failed: {e}")
        return "He looks like someone who just realized he sent that message to the wrong chat."

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
    lang = "Hebrew (עברית)" if prefs.get("language") == "he" else "English"
    safe = prefs.get("safe_mode", 1)
    sexual = prefs.get("sexual_content", 0)
    return f"""You are a professional comedy writer. Generate ONE short, original joke.
Return ONLY the joke text — no title, no explanation, no preamble.

Preferences:
- Humor styles: {', '.join(humor_types)}
- Intensity: {intensity_label} ({prefs.get('intensity',3)}/5)
- Language: {lang}
- Safe mode: {"YES — avoid offensive or extreme content" if safe else "NO"}
- Sexual humor: {"allowed (adult user)" if sexual else "NOT allowed"}

Rules:
- 1–3 sentences max
- Be original and genuinely funny
- Avoid clichéd openings like "Why did the chicken..."
- Be creative and unexpected"""

def get_joke_for_user(prefs: dict, seen_ids: list) -> dict:
    """Hybrid: DB pool first, AI fallback."""
    humor_types = prefs.get("humor_types", ["dad jokes"])
    if isinstance(humor_types, str):
        humor_types = json.loads(humor_types)
    lang = prefs.get("language", "en")
    safe = int(prefs.get("safe_mode", 1))
    intensity = prefs.get("intensity", 3)

    exclude = ""
    params = [lang, safe, max(1, intensity-1), min(5, intensity+1)]
    if seen_ids:
        placeholders = ",".join("?" * len(seen_ids))
        exclude = f"AND id NOT IN ({placeholders})"
        params += seen_ids

    # Try matching by category
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
        # Fallback: any matching joke
        row = db_one(
            f"SELECT * FROM jokes WHERE language=? AND safe>=? {exclude} ORDER BY RANDOM() LIMIT 1",
            [lang, safe] + (seen_ids if seen_ids else [])
        )

    if row:
        return {**row, "source": "pool"}

    # Generate with AI
    text = call_claude(build_joke_prompt(prefs))
    category = humor_types[0] if humor_types else "general"
    jid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    db_exec(
        "INSERT INTO jokes (id,text,category,language,intensity,safe,sexual,source,score,created_at) VALUES (?,?,?,?,?,?,?,'ai',0,?)",
        (jid, text, category, lang, intensity, safe, int(prefs.get("sexual_content", 0)), now)
    )
    return {"id": jid, "text": text, "category": category, "source": "ai"}

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
    draw.text((W // 2, 40), "😂  JokeAI", font=font_big, fill=(20, 20, 20), anchor="mm")

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
    return jsonify({"status": "ok", "ts": int(time.time()), "ai_configured": bool(ANTHROPIC_KEY)})

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

    if g.user_id:
        prefs = get_prefs(g.user_id)
    else:
        prefs = {"humor_types": ["dad jokes", "absurd humor"], "intensity": 2, "language": "en", "safe_mode": 1, "sexual_content": 0}

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

    text = call_claude(prompt)
    share_text = f"😂 JokeAI just roasted {name}:\n\n\"{text}\"\n\nRoast your friends: {request.host_url}"
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

    text = call_claude_vision(prompt, b64, file.mimetype)
    share_text = f"😂 JokeAI roasted my photo:\n\n\"{text}\"\n\nGet roasted: {request.host_url}"
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
    ai_status = "✅ Connected" if ANTHROPIC_KEY else "⚠️  Not configured (using joke pool)"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>JokeAI API</title>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#09090b;color:#e4e4e7;min-height:100vh;padding:2rem 1rem}}
  .wrap{{max-width:900px;margin:0 auto}}
  h1{{font-size:2.2rem;font-weight:800;color:#fbbf24;margin-bottom:.25rem}}
  .sub{{color:#71717a;margin-bottom:2rem;font-size:.95rem}}
  .status{{display:inline-flex;align-items:center;gap:.5rem;background:#18181b;border:1px solid #27272a;border-radius:8px;padding:.5rem 1rem;font-size:.85rem;margin-bottom:2rem}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:1rem;margin-bottom:2rem}}
  .card{{background:#18181b;border:1px solid #27272a;border-radius:12px;padding:1.25rem}}
  .card h3{{font-size:.9rem;font-weight:700;color:#fbbf24;margin-bottom:.75rem;text-transform:uppercase;letter-spacing:.05em}}
  .endpoint{{display:flex;align-items:center;gap:.5rem;padding:.4rem 0;border-bottom:1px solid #27272a;font-size:.82rem}}
  .endpoint:last-child{{border-bottom:none}}
  .method{{font-weight:700;font-size:.7rem;padding:2px 6px;border-radius:4px;min-width:38px;text-align:center}}
  .get{{background:#064e3b;color:#6ee7b7}}.post{{background:#1e1b4b;color:#a5b4fc}}.put{{background:#78350f;color:#fcd34d}}
  .path{{color:#d4d4d8;font-family:monospace;font-size:.8rem}}
  .try-section{{background:#18181b;border:1px solid #27272a;border-radius:12px;padding:1.5rem;margin-bottom:1rem}}
  .try-section h3{{color:#fbbf24;margin-bottom:1rem;font-size:1rem}}
  .btn{{background:#fbbf24;color:#09090b;border:none;border-radius:8px;padding:.6rem 1.2rem;font-weight:700;cursor:pointer;font-size:.85rem;transition:all .15s}}
  .btn:hover{{background:#f59e0b}}
  .btn-outline{{background:transparent;border:1px solid #27272a;color:#e4e4e7}}
  .btn-outline:hover{{background:#27272a}}
  .result{{background:#0a0a0a;border:1px solid #27272a;border-radius:8px;padding:1rem;margin-top:.75rem;font-family:monospace;font-size:.8rem;color:#86efac;white-space:pre-wrap;word-break:break-all;max-height:280px;overflow-y:auto;display:none}}
  .result.show{{display:block}}
  .row{{display:flex;gap:.5rem;flex-wrap:wrap;align-items:flex-end;margin-bottom:.5rem}}
  input,select{{background:#09090b;border:1px solid #27272a;border-radius:6px;padding:.5rem .75rem;color:#e4e4e7;font-size:.85rem;flex:1;min-width:120px}}
  label{{font-size:.78rem;color:#71717a;display:block;margin-bottom:.25rem}}
  .pill{{display:inline-block;background:#27272a;border-radius:999px;padding:.2rem .6rem;font-size:.72rem;margin:.1rem;cursor:pointer;user-select:none;transition:background .15s}}
  .pill.active{{background:#fbbf24;color:#09090b;font-weight:700}}
  .img-out{{margin-top:.75rem;display:none}}
  .img-out.show{{display:block}}
  .img-out img{{border-radius:8px;max-width:100%;border:1px solid #27272a}}
  footer{{text-align:center;color:#3f3f46;font-size:.75rem;margin-top:3rem}}
</style>
</head>
<body>
<div class="wrap">
  <h1>😂 JokeAI API</h1>
  <p class="sub">Production-ready AI humor platform · Running live</p>
  <div class="status">🤖 Claude AI: {ai_status}</div>

  <!-- QUICK DEMO -->
  <div class="try-section">
    <h3>⚡ Quick Demo — Get a Joke</h3>
    <div class="row">
      <div>
        <label>Humor Style</label>
        <div id="type-pills">
          {''.join(f'<span class="pill{" active" if t in ["dad jokes","absurd humor"] else ""}" onclick="togglePill(this)">{t}</span>'
            for t in ["dad jokes","tech jokes","relationship jokes","absurd humor","dark humor","work humor"])}
        </div>
      </div>
    </div>
    <div class="row">
      <div style="flex:1">
        <label>Intensity (1-5)</label>
        <input type="range" id="intensity-slider" min="1" max="5" value="3" oninput="document.getElementById('intensity-val').textContent=this.value" style="background:transparent;border:none;padding:.25rem 0">
        <span id="intensity-val" style="font-size:.8rem;color:#fbbf24">3</span>
      </div>
      <div style="flex:1">
        <label>Language</label>
        <select id="lang-select"><option value="en">🇺🇸 English</option><option value="he">🇮🇱 Hebrew</option></select>
      </div>
    </div>
    <button class="btn" onclick="getJoke()">😂 Get Joke</button>
    <div class="result" id="joke-result"></div>
  </div>

  <!-- ROAST DEMO -->
  <div class="try-section">
    <h3>🔥 Roast a Friend</h3>
    <div class="row">
      <div style="flex:1"><label>Name</label><input id="r-name" placeholder="e.g. Alex" value="Alex"></div>
      <div style="flex:1"><label>Job</label><input id="r-job" placeholder="e.g. Developer" value="Software Developer"></div>
    </div>
    <div class="row">
      <div style="flex:1"><label>Fun Fact</label><input id="r-fact" placeholder="e.g. Never closes browser tabs" value="Has 200 browser tabs open"></div>
    </div>
    <button class="btn" onclick="roastFriend()">🔥 Roast!</button>
    <div class="result" id="roast-result"></div>
  </div>

  <!-- MEME DEMO -->
  <div class="try-section">
    <h3>🖼️ Generate a Meme</h3>
    <div class="row">
      <div style="flex:1"><label>Joke Text</label><input id="meme-text" placeholder="Enter a joke..." value="I told my computer I needed a break. Now it won't stop sending me Kit-Kat ads."></div>
    </div>
    <button class="btn" onclick="makeMeme()">🖼️ Make Meme</button>
    <div class="result" id="meme-result"></div>
    <div class="img-out" id="meme-img-out"><img id="meme-img" src="" alt="Generated meme"></div>
  </div>

  <!-- REGISTER DEMO -->
  <div class="try-section">
    <h3>👤 Register Account</h3>
    <div class="row">
      <div style="flex:1"><label>Email</label><input id="reg-email" type="email" placeholder="test@example.com" value="demo@jokeai.app"></div>
      <div style="flex:1"><label>Username</label><input id="reg-username" placeholder="jokester" value="jokester99"></div>
    </div>
    <div class="row">
      <div style="flex:1"><label>Password</label><input id="reg-password" type="password" placeholder="min 8 chars" value="password123"></div>
    </div>
    <div style="margin:.5rem 0;font-size:.8rem;color:#71717a">✅ age_verified + accepted_tos auto-set to true for demo</div>
    <button class="btn" onclick="register()">Create Account</button>
    <button class="btn btn-outline" style="margin-left:.5rem" onclick="loginDemo()">Login with Demo Account</button>
    <div class="result" id="auth-result"></div>
  </div>

  <!-- ENDPOINTS REFERENCE -->
  <div class="grid">
    ${ _endpoint_cards() }
  </div>

  <footer>JokeAI MVP · Flask + SQLite + Anthropic Claude · Built with ❤️</footer>
</div>

<script>
let TOKEN = localStorage.getItem('jokeai_token') || '';

function togglePill(el) {{
  el.classList.toggle('active');
}}

function getSelectedTypes() {{
  return [...document.querySelectorAll('#type-pills .pill.active')].map(p => p.textContent);
}}

async function api(method, path, body=null, token=TOKEN) {{
  const headers = {{'Content-Type':'application/json'}};
  if (token) headers['Authorization'] = 'Bearer ' + token;
  const opts = {{method, headers}};
  if (body) opts.body = JSON.stringify(body);
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 30000);
  try {{
    const r = await fetch(path, {{...opts, signal: controller.signal}});
    clearTimeout(timeout);
    return [r.status, await r.json()];
  }} catch(e) {{
    clearTimeout(timeout);
    if (e.name === 'AbortError') return [408, {{error: 'Request timed out — please try again'}}];
    return [500, {{error: e.message}}];
  }}
}}

function show(id, data) {{
  const el = document.getElementById(id);
  el.textContent = JSON.stringify(data, null, 2);
  el.classList.add('show');
}}

function setBtn(id, loading, text) {{
  const b = document.getElementById(id);
  if (!b) return;
  b.disabled = loading;
  b.textContent = loading ? '⏳ ' + text : b.dataset.orig || b.textContent;
  if (!loading && b.dataset.orig) b.textContent = b.dataset.orig;
}}

document.addEventListener('DOMContentLoaded', () => {{
  document.querySelectorAll('.btn').forEach(b => b.dataset.orig = b.textContent);
}});

async function getJoke() {{
  const btn = document.querySelector('[onclick="getJoke()"]');
  const orig = btn.textContent; btn.disabled=true; btn.textContent='⏳ Thinking...';
  const lang = document.getElementById('lang-select').value;
  const [status, data] = await api('GET', `/api/jokes/generate?lang=${{lang}}`);
  btn.disabled=false; btn.textContent=orig;
  if (data.error) {{ show('joke-result', {{error: data.error}}); return; }}
  show('joke-result', {{
    joke: data.text,
    category: data.category,
    source: data.source,
    _hint: TOKEN ? 'Authenticated — ratings saved' : 'Sign in to save ratings'
  }});
}}

async function roastFriend() {{
  const btn = document.querySelector('[onclick="roastFriend()"]');
  const orig = btn.textContent; btn.disabled=true; btn.textContent='⏳ Roasting...';
  const name = document.getElementById('r-name').value;
  const job  = document.getElementById('r-job').value;
  const fact = document.getElementById('r-fact').value;
  if (!name || !job || !fact) {{ btn.disabled=false; btn.textContent=orig; show('roast-result', {{error: 'Fill in all fields!'}}); return; }}
  const [s, d] = await api('POST', '/api/roast/friend', {{name, job, fact}});
  btn.disabled=false; btn.textContent=orig;
  show('roast-result', d.error ? d : {{roast: d.text, share: d.shareText}});
}}

async function makeMeme() {{
  const btn = document.querySelector('[onclick="makeMeme()"]');
  const orig = btn.textContent; btn.disabled=true; btn.textContent='⏳ Creating meme...';
  const text = document.getElementById('meme-text').value;
  if (!text) {{ btn.disabled=false; btn.textContent=orig; show('meme-result', {{error: 'Enter some joke text!'}}); return; }}
  const [s, d] = await api('POST', '/api/meme/generate', {{joke_text: text}});
  btn.disabled=false; btn.textContent=orig;
  show('meme-result', d);
  if (d.url) {{
    const img = document.getElementById('meme-img');
    img.src = d.url;
    document.getElementById('meme-img-out').classList.add('show');
  }}
}}

async function register() {{
  const btn = document.querySelector('[onclick="register()"]');
  const orig = btn.textContent; btn.disabled=true; btn.textContent='⏳ Creating...';
  const email    = document.getElementById('reg-email').value;
  const username = document.getElementById('reg-username').value;
  const password = document.getElementById('reg-password').value;
  const [s, d] = await api('POST', '/api/auth/register', {{email, username, password, age_verified:true, accepted_tos:true}});
  btn.disabled=false; btn.textContent=orig;
  show('auth-result', d);
  if (d.token) {{ TOKEN = d.token; localStorage.setItem('jokeai_token', TOKEN); }}
}}

async function loginDemo() {{
  const email    = document.getElementById('reg-email').value;
  const password = document.getElementById('reg-password').value;
  const [s, d] = await api('POST', '/api/auth/login', {{email, password}});
  show('auth-result', d);
  if (d.token) {{ TOKEN = d.token; localStorage.setItem('jokeai_token', TOKEN); }}
}}
</script>
</body>
</html>"""

def _endpoint_cards():
    cards = [
        ("Auth", [
            ("POST","/api/auth/register","Register new user"),
            ("POST","/api/auth/login","Login → JWT"),
            ("POST","/api/auth/verify-age","Mark 18+ verified"),
        ]),
        ("Jokes", [
            ("GET","/api/jokes/generate","Get personalized joke"),
            ("POST","/api/jokes/rate","Like / dislike / favorite"),
            ("GET","/api/jokes/history","View history (auth)"),
            ("GET","/api/jokes/favorites","Saved favorites (auth)"),
            ("PUT","/api/jokes/preferences","Update humor prefs"),
        ]),
        ("Roast", [
            ("POST","/api/roast/friend","Roast by name+job+fact"),
            ("POST","/api/roast/photo","Roast uploaded photo"),
        ]),
        ("Meme", [
            ("GET","/api/meme/templates","List meme templates"),
            ("POST","/api/meme/generate","Generate meme image"),
        ]),
        ("Battle", [
            ("POST","/api/battle/create","Start joke battle"),
            ("POST","/api/battle/join/:token","Accept challenge"),
            ("POST","/api/battle/:id/vote","Vote a or b"),
            ("GET","/api/battle/:token","Get battle results"),
        ]),
        ("Profile", [
            ("GET","/api/profile/me","Full profile + prefs"),
            ("PUT","/api/profile/me","Update username/bio"),
            ("POST","/api/profile/photo","Upload avatar photo"),
            ("PUT","/api/profile/avatar-type","Switch cartoon/original"),
        ]),
    ]
    method_class = {"GET":"get","POST":"post","PUT":"put"}
    html = ""
    for title, endpoints in cards:
        html += f'<div class="card"><h3>{title}</h3>'
        for method, path, desc in endpoints:
            html += f'<div class="endpoint"><span class="method {method_class[method]}">{method}</span><span class="path" title="{desc}">{path}</span></div>'
        html += "</div>"
    return html

# ── STARTUP ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", 4000))
    print(f"\n{'='*55}")
    print(f"  😂  JokeAI API Server")
    print(f"{'='*55}")
    print(f"  URL:    http://localhost:{port}")
    print(f"  DB:     {DB_PATH}")
    if ANTHROPIC_KEY:
        print(f"  AI:     ✅ Claude (Anthropic) — live AI jokes!")
    else:
        print(f"  AI:     ⚠️  Using joke pool (no API key set)")
        print(f"")
        print(f"  To enable AI jokes, set your Anthropic key:")
        print(f"  Windows:  set ANTHROPIC_API_KEY=sk-ant-...")
        print(f"  Then restart:  python server.py")
    print(f"{'='*55}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
