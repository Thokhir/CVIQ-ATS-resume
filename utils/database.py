"""
database.py — CVIQ Resume Maker Pro
Full subscription management, usage tracking, template registry,
professional domains, and multi-plan billing.

Plans:
  trial    — ₹100 one-time, 1 use only (resume optimizer + download)
  monthly  — ₹500/month, 10 resume updates + all AI tools, renews monthly
  yearly   — ₹2,999/year, 1 resume/day + all AI tools, renews yearly
  agency   — Owner/internal only
"""
import sqlite3, hashlib, json, secrets, string
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "cviq.db"

# ── Owner config ──────────────────────────────────────────────────
OWNER_USERNAMES = {"thokhir"}
OWNER_EMAILS    = {"thokhircareer@gmail.com"}
_OWNER_PW       = "Admin@800822"

# ── Pricing ───────────────────────────────────────────────────────
PLANS = {
    "trial": {
        # Kept for backward-compatibility with previously-issued TRL keys.
        # The UI now offers the Starter credit pack instead of a trial plan.
        "name":        "Starter",
        "price_inr":   49,
        "price_label": "₹49",
        "desc":        "Single use — optimise 1 resume",
        "days":        None,       # never expires, but usage limited
        "max_resumes": 1,          # total uses
        "daily_limit": 1,
        "ai_tools":    False,
        "featured":    False,
    },
    "monthly": {
        "name":        "Monthly Pro",
        "price_inr":   399,
        "price_label": "₹399/month",
        "desc":        "30 resume optimizations + all AI tools for 30 days",
        "days":        30,
        "max_resumes": 30,         # per subscription period
        "daily_limit": 30,
        "ai_tools":    True,
        "featured":    True,
    },
    "yearly": {
        "name":        "Annual Pro",
        "price_inr":   2499,
        "price_label": "₹2,499/year",
        "desc":        "Unlimited optimizations (fair use) + all AI tools for 365 days",
        "days":        365,
        "max_resumes": 9999,       # effectively unlimited (fair use)
        "daily_limit": 25,
        "ai_tools":    True,
        "featured":    False,
    },
    "agency": {
        "name":        "Agency / Owner",
        "price_inr":   7999,
        "price_label": "₹7,999/year",
        "desc":        "Multi-seat, white-label & full access",
        "days":        365,
        "max_resumes": -1,         # unlimited
        "daily_limit": -1,
        "ai_tools":    True,
        "featured":    False,
    },
}

# ── Credit packs (pay-per-use, no recurring billing) ──────────────
# 1 credit = 1 resume optimization OR 1 cover-letter generation.
# Keyword analysis, ATS scoring and interview prep stay free.
CREDIT_PACKS = {
    "pack_starter": {
        "name":        "Starter",
        "credits":     1,
        "price_inr":   49,
        "price_label": "₹49",
        "desc":        "1 credit — try it on one application",
        "featured":    False,
    },
    "pack_jobhunt": {
        "name":        "Job Hunt",
        "credits":     10,
        "price_inr":   299,
        "price_label": "₹299",
        "desc":        "10 credits — ₹30 each · most popular",
        "featured":    True,
    },
    "pack_pro": {
        "name":        "Pro Pack",
        "credits":     30,
        "price_inr":   699,
        "price_label": "₹699",
        "desc":        "30 credits — ₹23 each · best value",
        "featured":    False,
    },
}


def plan_price(plan_or_pack: str) -> int:
    """Price in INR for either a subscription plan or a credit pack."""
    if plan_or_pack in PLANS:
        return PLANS[plan_or_pack].get("price_inr", 0)
    if plan_or_pack in CREDIT_PACKS:
        return CREDIT_PACKS[plan_or_pack].get("price_inr", 0)
    return 0


def get_conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            username     TEXT UNIQUE NOT NULL,
            email        TEXT UNIQUE NOT NULL,
            password     TEXT NOT NULL,
            role         TEXT DEFAULT 'user',
            profession   TEXT DEFAULT '',
            created      TEXT DEFAULT (datetime('now')),
            last_login   TEXT
        );
        CREATE TABLE IF NOT EXISTS subscriptions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            plan         TEXT NOT NULL,
            method       TEXT DEFAULT 'upi',
            license_key  TEXT,
            started      TEXT DEFAULT (datetime('now')),
            expires      TEXT,
            status       TEXT DEFAULT 'active',
            resumes_used INTEGER DEFAULT 0,
            granted_by   TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS daily_usage (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            date         TEXT NOT NULL,
            count        INTEGER DEFAULT 0,
            UNIQUE(user_id, date),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS license_keys (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            key_code     TEXT UNIQUE NOT NULL,
            plan         TEXT NOT NULL,
            used         INTEGER DEFAULT 0,
            used_by      INTEGER,
            used_at      TEXT,
            created_by   TEXT,
            created      TEXT DEFAULT (datetime('now')),
            expires      TEXT
        );
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            token        TEXT UNIQUE NOT NULL,
            created      TEXT DEFAULT (datetime('now')),
            expires      TEXT NOT NULL,
            used         INTEGER DEFAULT 0,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS resumes (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            title        TEXT,
            content      TEXT,
            ats_score    INTEGER DEFAULT 0,
            template_id  TEXT DEFAULT 'classic_professional',
            profession   TEXT DEFAULT '',
            created      TEXT DEFAULT (datetime('now')),
            updated      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS ats_analysis (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            resume_id    INTEGER,
            score        INTEGER,
            data         TEXT,
            jd_snippet   TEXT,
            profession   TEXT DEFAULT '',
            created      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS template_registry (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            template_id  TEXT UNIQUE NOT NULL,
            name         TEXT NOT NULL,
            category     TEXT,
            professions  TEXT,
            file_path    TEXT,
            preview_path TEXT,
            font_family  TEXT,
            accent_color TEXT,
            is_active    INTEGER DEFAULT 1,
            created      TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS payment_requests (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            plan         TEXT NOT NULL,
            amount_inr   INTEGER NOT NULL,
            utr_number   TEXT,
            screenshot_note TEXT,
            status       TEXT DEFAULT 'pending',
            created      TEXT DEFAULT (datetime('now')),
            verified_at  TEXT,
            verified_by  TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
        CREATE TABLE IF NOT EXISTS credit_ledger (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            delta        INTEGER NOT NULL,
            balance      INTEGER NOT NULL,
            reason       TEXT,
            granted_by   TEXT,
            created      TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(id)
        );
    """)

    # Schema upgrades
    for sql in [
        "ALTER TABLE users ADD COLUMN profession TEXT DEFAULT ''",
        "ALTER TABLE users ADD COLUMN credits INTEGER DEFAULT 0",
        "ALTER TABLE users ADD COLUMN temp_access_until TEXT",
        "ALTER TABLE subscriptions ADD COLUMN resumes_used INTEGER DEFAULT 0",
    ]:
        try: c.execute(sql); conn.commit()
        except: pass

    # Owner account
    row = c.execute("SELECT id FROM users WHERE username='thokhir'").fetchone()
    if not row:
        c.execute("INSERT OR IGNORE INTO users (username,email,password,role) VALUES (?,?,?,?)",
                  ("thokhir","thokhircareer@gmail.com",_hash(_OWNER_PW),"owner"))
        conn.commit()
        row = c.execute("SELECT id FROM users WHERE username='thokhir'").fetchone()
    if row:
        oid = row["id"]
        c.execute("UPDATE users SET role='owner' WHERE id=?", (oid,))
        existing = c.execute("SELECT id FROM subscriptions WHERE user_id=? AND status='active'", (oid,)).fetchone()
        if not existing:
            c.execute("INSERT INTO subscriptions (user_id,plan,method,expires,status,granted_by) VALUES (?,?,?,?,?,?)",
                      (oid,"agency","owner","2099-12-31","active","system"))
        conn.commit()

    conn.close()


def _hash(pw): return hashlib.sha256(pw.encode()).hexdigest()

def is_owner(username="", email=""):
    return username.lower() in OWNER_USERNAMES or (email and email.lower() in OWNER_EMAILS)


# ── Users ─────────────────────────────────────────────────────────

def create_user(username, email, password, profession=""):
    try:
        conn = get_conn()
        c = conn.cursor()
        if username.strip().lower() in OWNER_USERNAMES:
            conn.close(); return None
        role = "owner" if is_owner(username, email) else "user"
        c.execute("INSERT INTO users (username,email,password,role,profession) VALUES (?,?,?,?,?)",
                  (username.strip(), email.strip().lower(), _hash(password), role, profession))
        uid = c.lastrowid
        conn.commit()
        if role == "owner":
            c.execute("INSERT INTO subscriptions (user_id,plan,method,expires,status,granted_by) VALUES (?,?,?,?,?,?)",
                      (uid,"agency","owner","2099-12-31","active","system"))
            conn.commit()
        conn.close()
        return uid
    except sqlite3.IntegrityError:
        return None

def get_user_by_username(username):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_email(email):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email=?", (email.lower(),)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(uid):
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return dict(row) if row else None

def verify_password(stored, pw): return stored == _hash(pw)

def change_password(uid, new_pw):
    conn = get_conn()
    conn.execute("UPDATE users SET password=? WHERE id=?", (_hash(new_pw), uid))
    conn.commit(); conn.close()

def update_last_login(uid):
    conn = get_conn()
    conn.execute("UPDATE users SET last_login=datetime('now') WHERE id=?", (uid,))
    conn.commit(); conn.close()

def get_all_users():
    conn = get_conn()
    rows = conn.execute("""
        SELECT u.id, u.username, u.email, u.role, u.profession, u.created, u.last_login,
               COALESCE(s.plan,'none') as plan, s.expires, s.status, s.resumes_used
        FROM users u
        LEFT JOIN subscriptions s ON s.user_id=u.id AND s.status='active'
        ORDER BY u.created DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_user(uid):
    conn = get_conn()
    for t in ("subscriptions","resumes","ats_analysis","daily_usage","password_reset_tokens"):
        conn.execute(f"DELETE FROM {t} WHERE user_id=?", (uid,))
    conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit(); conn.close()

def set_user_role(uid, role):
    conn = get_conn()
    conn.execute("UPDATE users SET role=? WHERE id=?", (role, uid))
    conn.commit(); conn.close()


# ── Credits (pay-per-use) ─────────────────────────────────────────

def get_credits(uid) -> int:
    conn = get_conn()
    row = conn.execute("SELECT credits FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return int(row["credits"]) if row and row["credits"] is not None else 0

def add_credits(uid, amount, reason="purchase", granted_by="system") -> int:
    """Add (or remove, if negative) credits and record a ledger entry. Returns new balance."""
    conn = get_conn()
    c = conn.cursor()
    row = c.execute("SELECT credits FROM users WHERE id=?", (uid,)).fetchone()
    current = int(row["credits"]) if row and row["credits"] is not None else 0
    new_bal = max(0, current + int(amount))
    c.execute("UPDATE users SET credits=? WHERE id=?", (new_bal, uid))
    c.execute("INSERT INTO credit_ledger (user_id,delta,balance,reason,granted_by) VALUES (?,?,?,?,?)",
              (uid, int(amount), new_bal, reason, granted_by))
    conn.commit(); conn.close()
    return new_bal

def deduct_credits(uid, amount=1, reason="usage") -> bool:
    """Deduct credits if the balance is sufficient. Returns True on success."""
    conn = get_conn()
    c = conn.cursor()
    row = c.execute("SELECT credits FROM users WHERE id=?", (uid,)).fetchone()
    current = int(row["credits"]) if row and row["credits"] is not None else 0
    if current < amount:
        conn.close(); return False
    new_bal = current - amount
    c.execute("UPDATE users SET credits=? WHERE id=?", (new_bal, uid))
    c.execute("INSERT INTO credit_ledger (user_id,delta,balance,reason,granted_by) VALUES (?,?,?,?,?)",
              (uid, -amount, new_bal, reason, "system"))
    conn.commit(); conn.close()
    return True

def add_credit_pack(uid, pack_id, granted_by="system") -> int:
    """Credit a purchased pack to the user. Returns new balance."""
    pack = CREDIT_PACKS.get(pack_id)
    if not pack:
        return get_credits(uid)
    return add_credits(uid, pack["credits"], reason=f"pack:{pack_id}", granted_by=granted_by)


# ── Temporary full access (owner-granted, time-boxed) ─────────────
def get_temp_access_until(uid):
    conn = get_conn()
    row = conn.execute("SELECT temp_access_until FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return row["temp_access_until"] if row else None

def has_temp_access(uid) -> bool:
    """True if the user currently has an active owner-granted full-access window."""
    until = get_temp_access_until(uid)
    if not until:
        return False
    try:
        return datetime.strptime(until, "%Y-%m-%d %H:%M:%S") > datetime.now()
    except Exception:
        return False

def grant_temporary_full_access(email, hours=24, granted_by="owner"):
    """Give the account with this email FULL access for `hours` hours.
    Does NOT touch their subscription/credits — it's an independent window."""
    user = get_user_by_email((email or "").strip())
    if not user:
        return {"ok": False, "message": "No account found with that email. Ask them to sign up first."}
    until = (datetime.now() + timedelta(hours=int(hours))).strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    conn.execute("UPDATE users SET temp_access_until=? WHERE id=?", (until, user["id"]))
    conn.commit(); conn.close()
    return {"ok": True, "until": until, "username": user["username"],
            "message": f"✅ Granted {hours}h full access to {user['username']} ({email}) until {until}."}

def revoke_temp_access(uid):
    conn = get_conn()
    conn.execute("UPDATE users SET temp_access_until=NULL WHERE id=?", (uid,))
    conn.commit(); conn.close()

def get_active_temp_grants():
    """List users whose temp full-access window is still active."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, username, email, temp_access_until FROM users "
        "WHERE temp_access_until IS NOT NULL AND temp_access_until > ? ORDER BY temp_access_until DESC",
        (now,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── Subscriptions & Usage ─────────────────────────────────────────

def has_subscription_ai(uid, username="", email="") -> bool:
    """True if the user's active plan includes AI tools (owner/admin always do)."""
    plan = get_user_plan(uid, username, email)
    return bool(PLANS.get(plan, {}).get("ai_tools", False))

def has_pro_access(uid, username="", email="") -> bool:
    """Pro features unlock with an AI subscription OR any remaining credits."""
    return has_subscription_ai(uid, username, email) or get_credits(uid) > 0


def get_active_subscription(uid):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM subscriptions WHERE user_id=? AND status='active' ORDER BY id DESC LIMIT 1",
        (uid,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_plan(uid, username="", email=""):
    if is_owner(username, email): return "agency"
    conn = get_conn()
    role_row = conn.execute("SELECT role FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    if role_row and role_row["role"] in ("owner","admin"): return "agency"
    if has_temp_access(uid): return "agency"   # owner-granted 24h full access
    sub = get_active_subscription(uid)
    if not sub: return "none"
    # Check expiry for time-based plans
    plan_key = sub.get("plan","none")
    plan_info = PLANS.get(plan_key, {})
    if plan_info.get("days") and sub.get("expires"):
        try:
            exp = datetime.strptime(sub["expires"], "%Y-%m-%d")
            if exp < datetime.now(): return "expired"
        except: pass
    return plan_key

def can_use_optimizer(uid, username="", email=""):
    """
    Returns (allowed: bool, reason: str, remaining: int)
    Checks plan, expiry, period quota, and daily quota.
    """
    # Owner-granted temporary full access = unlimited while the window is open.
    if has_temp_access(uid):
        return True, "ok", 999

    credits  = get_credits(uid)
    plan_key = get_user_plan(uid, username, email)
    sub      = get_active_subscription(uid)
    plan     = PLANS.get(plan_key, {})

    # ── Path 1: active subscription ──────────────────────────────
    if plan_key not in ("none", "expired") and sub:
        # Unlimited (agency/owner)
        if plan.get("max_resumes") == -1:
            return True, "ok", 999

        used_total = sub.get("resumes_used", 0)
        max_total  = plan.get("max_resumes", 1)
        period_left = used_total < max_total

        # Daily limit check
        daily_ok = True
        daily_limit = plan.get("daily_limit", 1)
        if daily_limit != -1:
            today = datetime.now().strftime("%Y-%m-%d")
            conn  = get_conn()
            row   = conn.execute(
                "SELECT count FROM daily_usage WHERE user_id=? AND date=?", (uid, today)
            ).fetchone()
            conn.close()
            daily_used = row["count"] if row else 0
            daily_ok = daily_used < daily_limit

        if period_left and daily_ok:
            return True, "ok", max_total - used_total
        # Subscription exhausted but credits can still be used
        if credits > 0:
            return True, "credits", credits
        if not period_left:
            return False, "quota_exhausted", 0
        return False, "daily_limit", 0

    # ── Path 2: no/expired subscription — credits only ───────────
    if credits > 0:
        return True, "credits", credits

    return False, "no_plan", 0

def record_optimizer_use(uid, username="", email=""):
    """
    Charge one optimization. Subscription quota is used first; if the user has
    no active subscription quota, one credit is deducted instead.
    Returns the charge method: 'subscription' | 'credit' | 'free'.
    """
    # Owner-granted temporary full access charges nothing.
    if has_temp_access(uid):
        return "free"

    plan_key = get_user_plan(uid, username, email)
    plan     = PLANS.get(plan_key, {})
    sub      = get_active_subscription(uid)
    today    = datetime.now().strftime("%Y-%m-%d")

    # Owner/agency = unlimited, charge nothing
    if plan.get("max_resumes") == -1 and sub:
        return "free"

    use_sub = False
    if plan_key not in ("none", "expired") and sub:
        used_total = sub.get("resumes_used", 0)
        max_total  = plan.get("max_resumes", 1)
        if used_total < max_total:
            # also respect daily limit
            daily_limit = plan.get("daily_limit", 1)
            daily_ok = True
            if daily_limit != -1:
                conn = get_conn()
                row  = conn.execute("SELECT count FROM daily_usage WHERE user_id=? AND date=?",
                                    (uid, today)).fetchone()
                conn.close()
                daily_ok = (row["count"] if row else 0) < daily_limit
            use_sub = daily_ok

    if use_sub:
        conn = get_conn()
        conn.execute(
            "UPDATE subscriptions SET resumes_used=resumes_used+1 WHERE user_id=? AND status='active'",
            (uid,))
        conn.execute("""
            INSERT INTO daily_usage (user_id, date, count) VALUES (?,?,1)
            ON CONFLICT(user_id, date) DO UPDATE SET count=count+1
        """, (uid, today))
        conn.commit(); conn.close()
        return "subscription"

    # Fall back to a credit
    if deduct_credits(uid, 1, reason="resume_optimization"):
        return "credit"
    return "free"

def consume_ai_credit(uid, username="", email="", reason="ai_tool") -> bool:
    """
    Charge for an AI-tool generation (e.g. cover letter). Subscriptions with
    AI tools are free; otherwise one credit is consumed. Returns True if the
    action is permitted (and any charge was applied).
    """
    if has_subscription_ai(uid, username, email):
        return True
    return deduct_credits(uid, 1, reason=reason)

def add_subscription(uid, plan, method="manual", granted_by="admin",
                     expires_days=None, license_key=""):
    plan_info = PLANS.get(plan, {})
    d = expires_days if expires_days is not None else plan_info.get("days")
    expires = (datetime.now() + timedelta(days=d)).strftime("%Y-%m-%d") if d else "2099-12-31"
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE subscriptions SET status='replaced' WHERE user_id=? AND status='active'", (uid,))
    c.execute(
        "INSERT INTO subscriptions (user_id,plan,method,expires,status,granted_by,license_key,resumes_used) "
        "VALUES (?,?,?,?,?,?,?,0)",
        (uid, plan, method, expires, "active", granted_by, license_key)
    )
    conn.commit(); conn.close()

def revoke_subscription(uid):
    conn = get_conn()
    conn.execute("UPDATE subscriptions SET status='revoked' WHERE user_id=? AND status='active'", (uid,))
    conn.commit(); conn.close()

def get_all_subscriptions():
    conn = get_conn()
    rows = conn.execute("""
        SELECT s.*, u.username, u.email
        FROM subscriptions s JOIN users u ON u.id=s.user_id
        ORDER BY s.started DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ── License Keys ──────────────────────────────────────────────────

def _gen_key(prefix):
    chars = string.ascii_uppercase + string.digits
    part  = lambda n: "".join(secrets.choice(chars) for _ in range(n))
    return f"{prefix}-{part(4)}-{part(4)}-{part(4)}"

_KEY_PREFIXES = {"trial":"TRL","monthly":"MON","yearly":"YRL","agency":"AGE",
                 "pack_starter":"CRD","pack_jobhunt":"CRD","pack_pro":"CRD"}

def generate_license_key(plan, created_by, expires_days=None):
    prefix  = _KEY_PREFIXES.get(plan,"GEN")
    key     = _gen_key(prefix)
    plan_d  = PLANS.get(plan,{}).get("days") if expires_days is None else expires_days
    expires = (datetime.now() + timedelta(days=plan_d)).strftime("%Y-%m-%d") if plan_d else "2099-12-31"
    conn = get_conn()
    conn.execute("INSERT INTO license_keys (key_code,plan,created_by,expires) VALUES (?,?,?,?)",
                 (key, plan, created_by, expires))
    conn.commit(); conn.close()
    return key

def generate_bulk_keys(plan, count, created_by, expires_days=None):
    return [generate_license_key(plan, created_by, expires_days) for _ in range(count)]

def get_all_license_keys():
    conn = get_conn()
    rows = conn.execute("""
        SELECT lk.*, u.username as used_by_username
        FROM license_keys lk LEFT JOIN users u ON u.id=lk.used_by
        ORDER BY lk.created DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def redeem_license_key(key_code, uid):
    conn = get_conn()
    row  = conn.execute("SELECT * FROM license_keys WHERE key_code=?",
                        (key_code.strip().upper(),)).fetchone()
    if not row: conn.close(); return {"ok":False,"plan":"","message":"Invalid key — check for typos."}
    row = dict(row)
    if row["used"]: conn.close(); return {"ok":False,"plan":"","message":"This key has already been used."}
    if row["expires"] and datetime.strptime(row["expires"],"%Y-%m-%d") < datetime.now():
        conn.close(); return {"ok":False,"plan":"","message":"This key has expired."}
    conn.execute("UPDATE license_keys SET used=1,used_by=?,used_at=datetime('now') WHERE id=?",
                 (uid, row["id"]))
    conn.commit(); conn.close()
    if row["plan"] in CREDIT_PACKS:
        pack = CREDIT_PACKS[row["plan"]]
        bal  = add_credit_pack(uid, row["plan"], granted_by="key_redemption")
        return {"ok":True,"plan":"credits",
                "message":f"🎉 {pack['credits']} credits added! Balance: {bal}.",
                "credits":bal}
    add_subscription(uid, row["plan"], method="license_key",
                     granted_by="key_redemption", license_key=key_code)
    plan_name = PLANS.get(row["plan"],{}).get("name", row["plan"])
    return {"ok":True,"plan":row["plan"],
            "message":f"🎉 {plan_name} activated successfully!"}


# ── Payment Requests ──────────────────────────────────────────────

def create_payment_request(uid, plan, utr=None, note=None):
    amount = plan_price(plan)
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO payment_requests (user_id,plan,amount_inr,utr_number,screenshot_note) VALUES (?,?,?,?,?)",
        (uid, plan, amount, utr, note)
    )
    rid = c.lastrowid; conn.commit(); conn.close()
    return rid

def get_all_payment_requests():
    conn = get_conn()
    rows = conn.execute("""
        SELECT pr.*, u.username, u.email
        FROM payment_requests pr JOIN users u ON u.id=pr.user_id
        ORDER BY pr.created DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def approve_payment(request_id, admin_username):
    conn = get_conn()
    row = conn.execute("SELECT * FROM payment_requests WHERE id=?", (request_id,)).fetchone()
    if not row: conn.close(); return False
    row = dict(row)
    conn.execute(
        "UPDATE payment_requests SET status='approved',verified_at=datetime('now'),verified_by=? WHERE id=?",
        (admin_username, request_id)
    )
    conn.commit(); conn.close()
    if row["plan"] in CREDIT_PACKS:
        add_credit_pack(row["user_id"], row["plan"], granted_by=admin_username)
    else:
        add_subscription(row["user_id"], row["plan"], method="upi_payment",
                         granted_by=admin_username)
    return True

def reject_payment(request_id, admin_username):
    conn = get_conn()
    conn.execute(
        "UPDATE payment_requests SET status='rejected',verified_at=datetime('now'),verified_by=? WHERE id=?",
        (admin_username, request_id)
    )
    conn.commit(); conn.close()


# ── Template Registry ─────────────────────────────────────────────

def register_template(template_id, name, category, professions,
                      file_path, preview_path="", font_family="Calibri",
                      accent_color="#1F497D"):
    conn = get_conn()
    conn.execute("""
        INSERT OR REPLACE INTO template_registry
        (template_id,name,category,professions,file_path,preview_path,font_family,accent_color)
        VALUES (?,?,?,?,?,?,?,?)
    """, (template_id, name, category,
          json.dumps(professions) if isinstance(professions, list) else professions,
          file_path, preview_path, font_family, accent_color))
    conn.commit(); conn.close()

def get_templates(category=None, profession=None):
    conn = get_conn()
    if category and category != "All":
        rows = conn.execute(
            "SELECT * FROM template_registry WHERE is_active=1 AND category=? ORDER BY name",
            (category,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM template_registry WHERE is_active=1 ORDER BY category,name"
        ).fetchall()
    conn.close()
    result = [dict(r) for r in rows]
    if profession and profession != "All":
        result = [r for r in result if profession.lower() in r.get("professions","").lower() or "all" in r.get("professions","").lower()]
    return result

def get_template_by_id(template_id):
    conn = get_conn()
    row = conn.execute("SELECT * FROM template_registry WHERE template_id=?", (template_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ── Resumes & Analysis ────────────────────────────────────────────

def save_resume(uid, title, content, template_id="classic_professional", profession=""):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO resumes (user_id,title,content,template_id,profession) VALUES (?,?,?,?,?)",
        (uid, title, json.dumps(content, ensure_ascii=False), template_id, profession)
    )
    rid = c.lastrowid; conn.commit(); conn.close()
    return rid

def get_user_resumes(uid):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM resumes WHERE user_id=? ORDER BY updated DESC", (uid,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def delete_resume(rid, uid):
    conn = get_conn()
    conn.execute("DELETE FROM resumes WHERE id=? AND user_id=?", (rid, uid))
    conn.commit(); conn.close()

def save_ats_analysis(uid, resume_id, score, data, jd_snippet="", profession=""):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO ats_analysis (user_id,resume_id,score,data,jd_snippet,profession) VALUES (?,?,?,?,?,?)",
        (uid, resume_id, score, json.dumps(data, ensure_ascii=False), jd_snippet[:200], profession)
    )
    rid = c.lastrowid; conn.commit(); conn.close()
    return rid

def get_user_analysis_history(uid):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM ats_analysis WHERE user_id=? ORDER BY created DESC LIMIT 50", (uid,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_stats(uid):
    conn = get_conn()
    total    = conn.execute("SELECT COUNT(*) FROM resumes WHERE user_id=?", (uid,)).fetchone()[0]
    avg_row  = conn.execute("SELECT AVG(score) FROM ats_analysis WHERE user_id=?", (uid,)).fetchone()
    analyses = conn.execute("SELECT COUNT(*) FROM ats_analysis WHERE user_id=?", (uid,)).fetchone()[0]
    conn.close()
    return {"total_resumes": total, "avg_score": round(avg_row[0] or 0), "total_analyses": analyses}

def get_app_stats():
    conn = get_conn()
    tu = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    tr = conn.execute("SELECT COUNT(*) FROM resumes").fetchone()[0]
    ta = conn.execute("SELECT COUNT(*) FROM ats_analysis").fetchone()[0]
    ps = conn.execute("SELECT COUNT(DISTINCT user_id) FROM subscriptions WHERE status='active' AND plan NOT IN ('none','agency')").fetchone()[0]
    ki = conn.execute("SELECT COUNT(*) FROM license_keys").fetchone()[0]
    ku = conn.execute("SELECT COUNT(*) FROM license_keys WHERE used=1").fetchone()[0]
    pp = conn.execute("SELECT COUNT(*) FROM payment_requests WHERE status='pending'").fetchone()[0]
    conn.close()
    return {"total_users":tu,"total_resumes":tr,"total_analyses":ta,
            "paid_users":ps,"keys_issued":ki,"keys_used":ku,"pending_payments":pp}


# ── Password Reset ────────────────────────────────────────────────

def create_reset_token(uid):
    token   = "".join(secrets.choice(string.digits) for _ in range(6))
    expires = (datetime.now() + timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S")
    conn    = get_conn()
    conn.execute("UPDATE password_reset_tokens SET used=1 WHERE user_id=? AND used=0", (uid,))
    conn.execute("INSERT INTO password_reset_tokens (user_id,token,expires) VALUES (?,?,?)",
                 (uid, token, expires))
    conn.commit(); conn.close()
    return token

def verify_reset_token(uid, token):
    conn = get_conn()
    row  = conn.execute(
        "SELECT * FROM password_reset_tokens WHERE user_id=? AND token=? AND used=0",
        (uid, token.strip())
    ).fetchone()
    if not row: conn.close(); return False
    row = dict(row)
    if datetime.strptime(row["expires"],"%Y-%m-%d %H:%M:%S") < datetime.now():
        conn.close(); return False
    conn.execute("UPDATE password_reset_tokens SET used=1 WHERE id=?", (row["id"],))
    conn.commit(); conn.close()
    return True

def reset_password_with_token(username_or_email, token, new_password):
    user = get_user_by_username(username_or_email) or get_user_by_email(username_or_email)
    if not user: return {"ok":False,"message":"No account found."}
    if len(new_password) < 6: return {"ok":False,"message":"Password must be at least 6 characters."}
    if not verify_reset_token(user["id"], token): return {"ok":False,"message":"Invalid or expired code."}
    change_password(user["id"], new_password)
    return {"ok":True,"message":"Password reset! Please log in."}
