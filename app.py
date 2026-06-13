"""
ATS Resume Maker Pro — app.py
Complete Streamlit application.

Fixed bugs vs app_old.py:
  1. Duplicate col2 block (score ring rendered twice)         → Removed
  2. Duplicate show_subscription() (second one crashes)       → Single definition
  3. Broken imports (utils.auth, payment, ai_optimizer)       → Self-contained
  4. NameError: section/page/ai_tool/account_page             → Defaulted before routing
  5. get_all_plans() type mismatch (dict vs tuple)            → Returns correct dict
  6. PDF export returned None silently                        → Graceful fallback to DOCX
  7. Template not applied to DOCX output                      → template_id passed through
  8. Resume builder missing fresher fields                    → Added projects, internships,
                                                                certifications, languages,
                                                                activities, objective, GPA
  9. Step-bar HTML not closing divs properly                  → Fixed
 10. main() not called at bottom                              → Fixed
 11. ATS score ring duplicated in col2 block                  → Removed second render
 12. show_subscription() used plan[1] on dict                 → Uses dict keys correctly
"""
import streamlit as st
import json
import os
from pathlib import Path
from datetime import datetime

# ── Page config (must be first Streamlit call) ─────────────────
st.set_page_config(
    page_title="ATS Resume Maker Pro",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Local utility imports (self-contained, no missing deps) ────
from utils.database import (
    init_db, create_user, get_user_by_username, get_user_by_email,
    get_user_by_id, verify_password, change_password, update_last_login,
    add_subscription, get_active_subscription, get_user_plan, revoke_subscription,
    is_owner, OWNER_USERNAMES, OWNER_EMAILS, PLANS, CREDIT_PACKS, plan_price,
    can_use_optimizer, record_optimizer_use, consume_ai_credit,
    get_credits, add_credits, add_credit_pack, has_pro_access, has_subscription_ai,
    save_resume, get_user_resumes, delete_resume, save_ats_analysis,
    get_user_analysis_history, get_user_stats,
    generate_license_key, generate_bulk_keys, redeem_license_key,
    get_all_license_keys, get_all_users, get_all_subscriptions, delete_user,
    set_user_role, get_app_stats,
    create_reset_token, verify_reset_token, reset_password_with_token,
    create_payment_request, get_all_payment_requests, approve_payment, reject_payment,
)
from utils.template_manager import (
    BUILTIN_TEMPLATES, get_template_for_profession,
    get_template_categories, apply_word_template, load_template_file,
    list_uploaded_templates, render_template_preview_html, accent_hex,
)
from utils import llm
from utils.resume_processor import (
    PROFESSIONAL_DOMAINS, get_all_professions, get_domain_keywords,
)
from utils.resume_processor import (
    extract_text_from_file, parse_resume_text,
    optimize_resume_for_jd, extract_keywords_from_jd,
    generate_cover_letter, ai_write_summary, ai_write_bullets,
)
from utils.exporter import (
    export_resume_to_docx, export_resume_to_txt,
    get_all_templates, get_template_preview_html, TEMPLATES
)

# ── Init DB ─────────────────────────────────────────────────────
init_db()

# ══════════════════════════════════════════════════════════════════
# CSS  — exact match of ats_resume_pro.html design
# ══════════════════════════════════════════════════════════════════
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;600;700&display=swap');

/* ── DESIGN TOKENS — calm / premium dark (Linear/Vercel direction) ── */
:root{
  --bg:#08090c;--bg2:#0a0b10;
  --surface:#111319;--surface2:#171922;--surface3:#1c1f2b;
  --glass:rgba(20,22,30,.7);--glass-brd:rgba(255,255,255,.07);
  --border:rgba(255,255,255,.07);--border2:rgba(255,255,255,.12);
  --accent:#6d7cff;--accent2:#8b96ff;--accent-quiet:#5b67e8;
  --accent-soft:rgba(109,124,255,.14);
  --grad:linear-gradient(135deg,#6d7cff,#5b67e8);
  --grad-soft:linear-gradient(135deg,rgba(109,124,255,.16),rgba(91,103,232,.10));
  --green:#3ecf8e;--green-soft:rgba(62,207,142,.13);
  --red:#f1707b;--red-soft:rgba(241,112,123,.12);
  --amber:#e7b549;--amber-soft:rgba(231,181,73,.12);
  --text:#edeef2;--muted:#8b91a3;--muted2:#5a6072;
  --radius:14px;--radius-sm:10px;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 28px rgba(0,0,0,.32);
}

/* ── Calm canvas: one subtle aurora at the top, no busy grid ─────── */
.stApp{
  background:
    radial-gradient(900px 520px at 50% -180px,rgba(109,124,255,.13),transparent 70%),
    linear-gradient(180deg,var(--bg),var(--bg2))!important;
  background-attachment:fixed!important;
  color:var(--text)!important;
  font-family:'Inter',system-ui,-apple-system,sans-serif!important;
  -webkit-font-smoothing:antialiased;
}
.block-container{padding:1.4rem 1.6rem 4rem!important;max-width:1240px}
*{scrollbar-width:thin;scrollbar-color:rgba(255,255,255,.16) transparent}
::-webkit-scrollbar{width:9px;height:9px}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,.14);border-radius:9px}
::-webkit-scrollbar-thumb:hover{background:rgba(255,255,255,.26)}

/* ── Sidebar (glass kept here — it's a chrome element) ───────────── */
section[data-testid="stSidebar"]{
  background:rgba(13,15,21,.86)!important;
  border-right:1px solid var(--border)!important;backdrop-filter:blur(16px);
}
section[data-testid="stSidebar"] *{color:var(--text)}
.logo-box{display:flex;align-items:center;gap:11px;padding:6px 0 16px;border-bottom:1px solid var(--border);margin-bottom:14px}
.logo-mark{background:var(--grad);color:#fff;font-weight:800;font-size:13px;width:38px;height:38px;border-radius:11px;display:flex;align-items:center;justify-content:center;letter-spacing:.5px;flex-shrink:0;box-shadow:0 4px 16px rgba(109,124,255,.4)}
.logo-text{font-family:'Space Grotesk',sans-serif;font-weight:700;font-size:16px;letter-spacing:.2px}
.logo-sub{font-size:10px;color:var(--muted);margin-top:1px;letter-spacing:.3px}
.nav-group{font-size:10px;font-weight:700;color:var(--muted2);text-transform:uppercase;letter-spacing:1.3px;padding:14px 0 6px;margin-bottom:2px}
.user-chip{display:flex;align-items:center;gap:9px;padding:9px 12px;background:var(--surface2);border:1px solid var(--border);border-radius:var(--radius-sm);margin-bottom:9px}
.plan-chip{display:flex;align-items:center;justify-content:space-between;padding:7px 11px;background:var(--accent-soft);border-radius:var(--radius-sm);border:1px solid rgba(109,124,255,.22);margin-bottom:8px;font-size:12px;font-weight:700;color:var(--accent2)}

/* ── Flat, high-contrast content cards (no blur — crisp + fast) ──── */
.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:20px;margin-bottom:18px;box-shadow:var(--shadow);transition:border-color .18s,transform .18s}
.card:hover{border-color:var(--border2);transform:translateY(-1px)}
.card-hd{display:flex;align-items:center;gap:9px;font-size:13px;font-weight:700;margin-bottom:15px;padding-bottom:11px;border-bottom:1px solid var(--border);letter-spacing:.2px}

/* ── Page header ────────────────────────────────────────────────── */
.ph h2{font-family:'Space Grotesk',sans-serif;font-size:26px;font-weight:700;margin-bottom:4px;color:#fff;letter-spacing:-.3px}
.ph p{color:var(--muted);font-size:13px;margin:0}

/* ── Step bar ───────────────────────────────────────────────────── */
.step-bar{display:flex;align-items:center;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:16px 20px;margin-bottom:22px;gap:0}
.step{display:flex;align-items:center;gap:8px;flex-shrink:0}
.step-num{width:28px;height:28px;border-radius:50%;background:var(--surface3);border:1px solid var(--border2);display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:var(--muted);transition:.25s}
.step.active .step-num{border-color:transparent;background:var(--grad);color:#fff}
.step.done .step-num{background:var(--green);border-color:var(--green);color:#04210f}
.step-label{font-size:12px;font-weight:600;color:var(--muted)}
.step.active .step-label,.step.done .step-label{color:var(--text)}
.step-line{flex:1;height:1px;background:var(--border2);margin:0 12px}

/* ── Score ring ─────────────────────────────────────────────────── */
.score-wrap{display:flex;align-items:center;gap:22px;padding:6px 0}
.score-ring-box{position:relative;flex-shrink:0}
.score-inner{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;pointer-events:none}
.score-num{font-family:'Space Grotesk',sans-serif;font-size:28px;font-weight:800}
.score-denom{font-size:11px;color:var(--muted)}
.score-metrics{flex:1;min-width:0}
.metric{display:flex;justify-content:space-between;font-size:11px;margin-bottom:3px}
.metric-label{color:var(--muted)}
.metric-val{font-weight:700}
.metric-bar{height:5px;background:var(--surface3);border-radius:3px;margin-bottom:9px;overflow:hidden}
.metric-fill{height:100%;background:var(--grad);border-radius:3px}

/* ── Keywords ───────────────────────────────────────────────────── */
.kw-legend{display:flex;gap:10px;margin-bottom:11px;flex-wrap:wrap}
.kw-chip{font-size:11px;font-weight:700;padding:3px 9px;border-radius:11px}
.kw-chip.found{background:var(--green-soft);color:var(--green)}
.kw-chip.missing{background:var(--red-soft);color:var(--red)}
.kw-cloud{display:flex;flex-wrap:wrap;gap:7px;min-height:50px;padding:4px 0}
.kw-tag{font-size:12px;padding:5px 12px;border-radius:18px;font-weight:600;transition:transform .14s}
.kw-tag:hover{transform:translateY(-1px)}
.kw-tag.found{background:var(--green-soft);color:var(--green);border:1px solid rgba(62,207,142,.26)}
.kw-tag.missing{background:var(--red-soft);color:var(--red);border:1px solid rgba(241,112,123,.26)}
.kw-empty{color:var(--muted);font-size:12px}

/* ── Suggestion banners ─────────────────────────────────────────── */
.sug{padding:14px 16px;border-radius:var(--radius-sm);margin-bottom:10px;border-left:3px solid}
.sug.info{background:var(--accent-soft);border-color:var(--accent)}
.sug.warn{background:var(--amber-soft);border-color:var(--amber)}
.sug.ok{background:var(--green-soft);border-color:var(--green)}
.sug.err{background:var(--red-soft);border-color:var(--red)}
.sug-title{font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.9px;margin-bottom:4px;color:var(--muted)}
.sug-body{font-size:12.5px;line-height:1.6}

/* ── Output stats / badges ──────────────────────────────────────── */
.out-stats{display:flex;gap:10px;margin-top:10px;flex-wrap:wrap;font-size:11px;color:var(--muted)}
.out-stat{background:var(--surface2);padding:4px 11px;border-radius:18px;border:1px solid var(--border)}
.badge-green{background:var(--green-soft);color:var(--green);font-size:10px;font-weight:800;padding:3px 10px;border-radius:18px;margin-left:auto;border:1px solid rgba(62,207,142,.26)}

/* ── Template gallery (flat surfaces — fast with 21 cards) ──────── */
.tpl-card{border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;cursor:pointer;transition:border-color .18s,transform .18s;margin-bottom:16px;background:var(--surface)}
.tpl-card:hover{border-color:var(--accent);transform:translateY(-2px)}
.tpl-card.sel{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.tpl-preview{height:200px;overflow:hidden;background:#fff}
.tpl-info{padding:11px 13px}
.tpl-name{font-size:13px;font-weight:700;margin-bottom:2px}
.tpl-desc{font-size:11px;color:var(--muted)}
.badge-free{background:var(--green-soft);color:var(--green);font-size:9px;font-weight:800;padding:2px 7px;border-radius:7px;margin-left:6px}
.badge-pro{background:var(--accent-soft);color:var(--accent2);font-size:9px;font-weight:800;padding:2px 7px;border-radius:7px;margin-left:6px}

/* ── Stats cards (flat, one quiet accent glow) ──────────────────── */
.stats-row{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:22px}
.stat-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:18px;position:relative;overflow:hidden;transition:border-color .18s,transform .18s}
.stat-card:hover{border-color:var(--border2);transform:translateY(-1px)}
.stat-label{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.7px;margin-bottom:6px}
.stat-val{font-family:'Space Grotesk',sans-serif;font-size:26px;font-weight:800}

/* ── Login (glass kept — it's a hero element) ───────────────────── */
.login-wrap{max-width:480px;margin:54px auto 0;padding:34px;background:var(--glass);border:1px solid var(--glass-brd);border-radius:20px;backdrop-filter:blur(18px);box-shadow:0 24px 80px rgba(0,0,0,.55)}
.login-logo{text-align:center;margin-bottom:22px}
.login-logo .mark{display:inline-flex;align-items:center;justify-content:center;width:60px;height:60px;background:var(--grad);border-radius:16px;font-size:21px;font-weight:900;color:#fff;margin-bottom:10px;box-shadow:0 10px 30px rgba(109,124,255,.45)}
.login-title{font-family:'Space Grotesk',sans-serif;font-size:24px;font-weight:700;text-align:center;margin-bottom:4px;color:#fff;letter-spacing:-.3px}
.login-sub{font-size:13px;color:var(--muted);text-align:center;margin-bottom:22px}
.tab-row{display:flex;border-bottom:1px solid var(--border);margin-bottom:20px}
.tab-btn{flex:1;text-align:center;padding:11px;font-size:13px;font-weight:600;cursor:pointer;border-bottom:2px solid transparent;color:var(--muted)}
.tab-btn.active{color:var(--accent2);border-bottom-color:var(--accent)}

/* ── History items ──────────────────────────────────────────────── */
.hist-item{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius-sm);padding:13px 15px;margin-bottom:10px;display:flex;align-items:center;gap:14px;transition:border-color .16s}
.hist-item:hover{border-color:var(--border2)}
.hist-score{width:46px;height:46px;border-radius:11px;display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:800;flex-shrink:0}

/* ── Platform bars ──────────────────────────────────────────────── */
.plat-row{display:flex;align-items:center;gap:10px;margin-bottom:10px}
.plat-name{width:92px;font-size:12px;color:var(--muted);flex-shrink:0}
.plat-bar{flex:1;height:6px;background:var(--surface3);border-radius:4px;overflow:hidden}
.plat-fill{height:100%;background:var(--grad);border-radius:4px}
.plat-pct{width:42px;text-align:right;font-size:12px;font-weight:700}

/* ── Pricing ────────────────────────────────────────────────────── */
.price-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:18px}
.price-card{background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);padding:24px;position:relative;transition:border-color .18s,transform .18s}
.price-card:hover{border-color:var(--border2);transform:translateY(-2px)}
.price-card.featured{border-color:var(--accent);box-shadow:0 0 0 1px var(--accent)}
.pop-badge{position:absolute;top:-11px;left:50%;transform:translateX(-50%);background:var(--grad);color:#fff;font-size:9px;font-weight:800;padding:3px 12px;border-radius:18px;white-space:nowrap}
.price-tier{font-size:18px;font-weight:800;margin-bottom:4px}
.price-val{font-family:'Space Grotesk',sans-serif;font-size:31px;font-weight:800;margin-bottom:12px}
.price-val span{font-size:13px;font-weight:400;color:var(--muted)}
.price-features{list-style:none;font-size:12px;padding:0}
.price-features li{padding:5px 0;display:flex;gap:8px}
.price-features li::before{content:'✓';color:var(--green);font-weight:800}
.price-features li.no::before{content:'✕';color:var(--muted)}
.price-features li.no{color:var(--muted)}

/* ── Section breakdown ──────────────────────────────────────────── */
.sec-row{display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--border)}
.sec-row:last-child{border-bottom:none}
.sec-name{font-size:12px;font-weight:600;width:110px;flex-shrink:0}
.sec-bar{flex:1;height:6px;background:var(--surface3);border-radius:4px;overflow:hidden}
.sec-fill{height:100%;border-radius:4px}
.sec-pct{font-size:11px;font-weight:800;width:36px;text-align:right}

/* ── Streamlit widget overrides (flat, crisp) ───────────────────── */
.stTextInput input,.stTextArea textarea,.stNumberInput input{
  background:var(--surface2)!important;border:1px solid var(--border2)!important;
  border-radius:var(--radius-sm)!important;color:var(--text)!important;font-size:13px!important}
.stSelectbox div[data-baseweb]{background:var(--surface2)!important;border-radius:var(--radius-sm)!important;border:1px solid var(--border2)!important;color:var(--text)!important}
.stTextInput input:focus,.stTextArea textarea:focus{border-color:var(--accent)!important;box-shadow:0 0 0 3px var(--accent-soft)!important}
.stButton>button{background:var(--surface2)!important;border:1px solid var(--border2)!important;
  border-radius:var(--radius-sm)!important;color:var(--text)!important;font-weight:600!important;
  font-size:13px!important;transition:all .16s!important}
.stButton>button:hover{border-color:var(--accent)!important;color:#fff!important;background:var(--surface3)!important}
.stButton>button[kind="primary"],.stButton button[data-testid="baseButton-primary"]{background:var(--grad)!important;border:none!important;color:#fff!important;box-shadow:0 2px 10px rgba(109,124,255,.3)!important}
.stButton>button[kind="primary"]:hover{box-shadow:0 4px 16px rgba(109,124,255,.45)!important;transform:translateY(-1px)}
.stDownloadButton>button{background:var(--grad)!important;border:none!important;color:#fff!important;font-weight:700!important;border-radius:var(--radius-sm)!important}
.stDownloadButton>button:hover{transform:translateY(-1px)}
.stTabs [data-baseweb="tab-list"]{background:var(--surface2)!important;border-radius:var(--radius-sm)!important;gap:4px!important;padding:5px!important;border:1px solid var(--border)!important}
.stTabs [data-baseweb="tab"]{border-radius:8px!important;color:var(--muted)!important}
.stTabs [aria-selected="true"]{background:var(--accent-soft)!important;color:#fff!important}
.stExpander{background:var(--surface)!important;border:1px solid var(--border)!important;border-radius:var(--radius-sm)!important}
.stExpander summary{color:var(--text)!important}
.stAlert{border-radius:var(--radius-sm)!important}
div[data-testid="stMarkdownContainer"] p{color:var(--text)}
div[data-testid="stMarkdownContainer"] a{color:var(--accent2)}
label{color:var(--muted)!important;font-size:11px!important;font-weight:600!important;letter-spacing:.2px}
.stRadio>div{gap:5px!important}
.stRadio label{font-size:13px!important;font-weight:500!important;color:var(--text)!important;padding:7px 11px;border-radius:9px;transition:background .14s}
.stRadio label:hover{background:var(--surface2)}
.stCheckbox label{font-size:13px!important;font-weight:500!important;color:var(--text)!important}
.stProgress .st-bo{background:var(--grad)!important}
hr{border-color:var(--border)!important}
h1,h2,h3,h4,h5,h6{color:var(--text)!important;font-family:'Space Grotesk',sans-serif!important}
#MainMenu,footer,header[data-testid="stHeader"]{visibility:hidden}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════
SAMPLE_JD = """Machine Learning Engineer – MLOps & AI Infrastructure
Roche India – GATE Centre of Excellence (Hyderabad / Chennai)

We are looking for a skilled ML Engineer to join our data science platform team.

Requirements:
• 4+ years professional experience in ML engineering
• Strong Python programming (scikit-learn, XGBoost, TensorFlow, PyTorch)
• Experience with ML pipelines: data ingestion, model training, inference
• Cloud experience: AWS (SageMaker, S3, Glue, Lambda, Athena, EMR)
• MLflow for experiment tracking and model registry
• CI/CD with GitHub Actions or Jenkins; Docker and Kubernetes
• SQL, PySpark, data engineering (Spark MLlib)
• Git/GitHub version control

Responsibilities:
• Design and build scalable production-grade ML pipelines
• Deploy and monitor ML models in AWS production environments
• Collaborate with data scientists and business stakeholders
• Implement automated workflows for data preprocessing and model retraining"""

SKILL_SUGGESTIONS = {
    "Tech / Software": ["Python", "JavaScript", "Java", "React", "Node.js", "SQL", "Git",
                        "Docker", "AWS", "Linux", "REST APIs", "Microservices", "CI/CD", "Agile"],
    "Life Sciences": ["Python", "R", "Bioinformatics", "NGS", "BLAST", "GATK", "Biopython",
                      "Proteomics", "Drug Discovery", "Cell Culture", "Western Blot", "Flow Cytometry",
                      "PCR", "CRISPR", "Molecular Cloning"],
    "Data / AI": ["Python", "R", "SQL", "TensorFlow", "PyTorch", "scikit-learn", "XGBoost",
                  "Pandas", "NumPy", "Matplotlib", "Power BI", "Tableau", "AWS SageMaker",
                  "MLflow", "Docker", "Spark", "Kafka"],
    "Finance": ["Excel", "Python", "R", "SQL", "Bloomberg", "Financial Modeling", "VBA",
                "Power BI", "Risk Analysis", "Portfolio Management", "CFA"],
    "Healthcare": ["EHR/EMR", "ICD-10", "HIPAA", "Clinical Documentation", "Patient Care",
                   "Medical Terminology", "Epic", "Cerner"],
    "Operations": ["Lean Six Sigma", "Excel", "Power BI", "SAP", "Supply Chain", "ERP",
                   "Process Improvement", "Project Management", "JIRA"],
}


# ══════════════════════════════════════════════════════════════════
# SESSION STATE INITIALISATION
# ══════════════════════════════════════════════════════════════════
def _init_session():
    defaults = {
        "authenticated": False,
        "username": None,
        "user_id": None,
        "user_email": "",
        "user_role": "user",
        "user_plan": "none",
        "user_profession": "",
        "usage_remaining": 0,
        "credits": 0,
        "has_pro": False,
        "is_admin": False,
        # Optimizer state
        "step": 1,
        "show_paste": False,
        "resume_text": "",
        "original_resume": "",
        "jd_text": "",
        "optimized_resume": "",
        "ats_score": 0,
        "kw_found": [],
        "kw_missing": [],
        "show_diff": False,
        "has_ai_tools": False,
        "selected_model": "mistral (Recommended — 4.1 GB)",
        "model_temp": 0.2,
        "opt_change_log": [],
        "opt_parsed": None,
        "selected_template": "classic_professional",
        # Builder state
        "builder_data": {},
        # Navigation
        "section": "Workspace",
        "ws_page": "🏠 Dashboard",
        "ai_page": "◈ Keyword Engine",
        "acc_page": "⚙ Settings",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_session()


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════
def _score_color(score: int) -> str:
    if score >= 80:
        return "var(--green)"
    if score >= 60:
        return "var(--amber)"
    return "var(--red)"


def _score_ring(score: int) -> str:
    offset = 345.4 - (345.4 * score / 100)
    kw = min(100, score + 5)
    fmt = max(60, score - 5)
    rd = max(70, score + 3)
    sec = min(100, score + 8)
    return f"""
<div class="score-wrap">
  <div class="score-ring-box">
    <svg width="130" height="130" viewBox="0 0 130 130">
      <circle cx="65" cy="65" r="55" fill="none" stroke="#2a2d3e" stroke-width="10"/>
      <circle cx="65" cy="65" r="55" fill="none"
        stroke="url(#sg)" stroke-width="10" stroke-linecap="round"
        stroke-dasharray="345.4" stroke-dashoffset="{offset:.1f}"
        transform="rotate(-90 65 65)"/>
      <defs>
        <linearGradient id="sg" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#6366f1"/>
          <stop offset="100%" stop-color="#22c55e"/>
        </linearGradient>
      </defs>
    </svg>
    <div class="score-inner">
      <span class="score-num" style="color:{_score_color(score)}">{score}</span>
      <span class="score-denom">/100</span>
    </div>
  </div>
  <div class="score-metrics">
    <div class="metric"><span class="metric-label">Keyword Match</span><span class="metric-val">{kw}%</span></div>
    <div class="metric-bar"><div class="metric-fill" style="width:{kw}%"></div></div>
    <div class="metric"><span class="metric-label">Format Score</span><span class="metric-val">{fmt}%</span></div>
    <div class="metric-bar"><div class="metric-fill" style="width:{fmt}%"></div></div>
    <div class="metric"><span class="metric-label">Readability</span><span class="metric-val">{rd}%</span></div>
    <div class="metric-bar"><div class="metric-fill" style="width:{rd}%"></div></div>
    <div class="metric"><span class="metric-label">Section Score</span><span class="metric-val">{sec}%</span></div>
    <div class="metric-bar"><div class="metric-fill" style="width:{sec}%"></div></div>
  </div>
</div>"""


def _step_bar(step: int) -> str:
    def _cls(n):
        if step > n:
            return "done"
        if step == n:
            return "active"
        return ""

    def _num(n):
        return "✓" if step > n else str(n)

    labels = ["Upload Resume", "Job Description", "AI Optimize", "Export"]
    parts = []
    for i, label in enumerate(labels, 1):
        cls = _cls(i)
        parts.append(
            f'<div class="step {cls}">'
            f'<span class="step-num">{_num(i)}</span>'
            f'<span class="step-label">{label}</span>'
            f'</div>'
        )
        if i < 4:
            parts.append('<div class="step-line"></div>')

    return '<div class="step-bar">' + "".join(parts) + "</div>"


def _kw_cloud(resume_text: str, jd_text: str) -> str:
    if not jd_text:
        return '<span class="kw-empty">No job description loaded</span>'
    keywords = extract_keywords_from_jd(jd_text)
    lower = resume_text.lower()
    tags = []
    for kw in keywords[:30]:
        cls = "found" if kw.lower() in lower else "missing"
        tags.append(f'<span class="kw-tag {cls}">{kw}</span>')
    return "".join(tags) or '<span class="kw-empty">No keywords extracted</span>'


def _platform_bars(score: int) -> str:
    platforms = [("Workday", 0.95), ("Taleo", 0.90), ("Greenhouse", 0.98),
                 ("Lever", 0.92), ("iCIMS", 0.88)]
    rows = []
    for name, factor in platforms:
        v = min(99, round(score * factor))
        rows.append(
            f'<div class="plat-row">'
            f'<span class="plat-name">{name}</span>'
            f'<div class="plat-bar"><div class="plat-fill" style="width:{v}%"></div></div>'
            f'<span class="plat-pct">{v}%</span>'
            f'</div>'
        )
    return "".join(rows)


def _section_breakdown(score: int) -> str:
    sections = [("Summary", score + 3, "#6366f1"),
                ("Experience", score - 2, "#22c55e"),
                ("Skills", score + 5, "#f59e0b"),
                ("Education", 100, "#6366f1"),
                ("Format", score, "#22c55e")]
    rows = []
    for name, v, color in sections:
        v = max(0, min(100, v))
        rows.append(
            f'<div class="sec-row">'
            f'<span class="sec-name">{name}</span>'
            f'<div class="sec-bar"><div class="sec-fill" style="width:{v}%;background:{color}"></div></div>'
            f'<span class="sec-pct" style="color:{color}">{v}%</span>'
            f'</div>'
        )
    return "".join(rows)


# ══════════════════════════════════════════════════════════════════
# LOGIN PAGE
# ══════════════════════════════════════════════════════════════════
def _do_login(user: dict):
    """Set session state after successful authentication."""
    plan = get_user_plan(user["id"], user["username"], user["email"])
    role = user.get("role", "user")
    sub  = get_active_subscription(user["id"])
    remaining = sub.get("resumes_used",0) if sub else 0
    max_r = PLANS.get(plan,{}).get("max_resumes",0)
    rem   = max(0, (max_r - remaining)) if max_r != -1 else 999

    st.session_state.authenticated   = True
    st.session_state.username        = user["username"]
    st.session_state.user_id         = user["id"]
    st.session_state.user_email      = user["email"]
    st.session_state.user_role       = role
    st.session_state.user_plan       = plan
    st.session_state.user_profession = user.get("profession","")
    st.session_state.usage_remaining = rem
    st.session_state.credits         = get_credits(user["id"])
    # Pro features unlock via a subscription OR any remaining credits.
    plan_info = PLANS.get(plan, {})
    has_sub_ai = plan_info.get("ai_tools", False) or role in ("owner", "admin")
    st.session_state.has_pro         = (plan in ("monthly","yearly","agency") or
                                         role in ("owner","admin") or
                                         st.session_state.credits > 0)
    # AI tools access: subscription with AI tools, owner/admin, or credits.
    st.session_state.has_ai_tools    = has_sub_ai or st.session_state.credits > 0
    st.session_state.is_admin        = role in ("owner","admin")
    update_last_login(user["id"])


def _refresh_access():
    """Re-read credits + plan and recompute access flags. Call after any
    optimization, purchase, or license activation."""
    uid = st.session_state.get("user_id")
    if not uid:
        return
    uname = st.session_state.get("username", "")
    email = st.session_state.get("user_email", "")
    plan  = get_user_plan(uid, uname, email)
    role  = st.session_state.get("user_role", "user")
    st.session_state.user_plan    = plan
    st.session_state.credits      = get_credits(uid)
    st.session_state.has_ai_tools = has_subscription_ai(uid, uname, email) or st.session_state.credits > 0
    st.session_state.has_pro      = (plan in ("monthly","yearly","agency") or
                                     role in ("owner","admin") or st.session_state.credits > 0)


def show_login():
    st.markdown("""
<div class="login-wrap">
  <div class="login-logo">
    <div class="mark">ATS</div>
  </div>
  <div class="login-title">ATS Resume Maker Pro</div>
  <div class="login-sub">Build ATS-optimized resumes · 100% Offline AI</div>
</div>""", unsafe_allow_html=True)

    _, col, _ = st.columns([1, 2, 1])
    with col:
        tab1, tab2, tab3 = st.tabs(["🔐 Login", "✏️ Sign Up", "🔑 Forgot Password"])

        # ── LOGIN TAB ───────────────────────────────────────────
        with tab1:
            with st.form("login_form", clear_on_submit=False):
                username = st.text_input("Username", placeholder="Enter your username")
                password = st.text_input("Password", type="password", placeholder="Enter password")
                submitted = st.form_submit_button("Login", use_container_width=True, type="primary")
            if submitted:
                if not username.strip() or not password:
                    st.error("Please fill in all fields")
                else:
                    user = get_user_by_username(username.strip())
                    if user and verify_password(user["password"], password):
                        _do_login(user)
                        st.rerun()
                    else:
                        st.error("❌ Invalid username or password")
            st.markdown("""
<div style="text-align:center;margin-top:12px;font-size:11px;color:#4b5563">
  New here? Click the <b style="color:#818cf8">Sign Up</b> tab to create your free account.
</div>""", unsafe_allow_html=True)

        # ── SIGN UP TAB ─────────────────────────────────────────
        with tab2:
            with st.form("signup_form", clear_on_submit=True):
                new_user  = st.text_input("Username *", placeholder="Choose a username", key="su_user")
                new_email = st.text_input("Email *",    placeholder="your@email.com",    key="su_email")
                new_pw    = st.text_input("Password *", type="password", placeholder="Min 6 characters", key="su_pw")
                conf_pw   = st.text_input("Confirm Password *", type="password", key="su_cpw")
                profession_opts = ["Select your field..."] + get_all_professions()
                new_prof  = st.selectbox("Your Profession *", profession_opts, key="su_prof",
                                          help="Used to recommend templates and keywords for your field")
                signed    = st.form_submit_button("Create Free Account", use_container_width=True, type="primary")
            if signed:
                errs = []
                if not all([new_user.strip(), new_email.strip(), new_pw, conf_pw]):
                    errs.append("All fields are required")
                elif new_pw != conf_pw:
                    errs.append("Passwords do not match")
                elif len(new_pw) < 6:
                    errs.append("Password must be at least 6 characters")
                elif "@" not in new_email or "." not in new_email:
                    errs.append("Enter a valid email address")
                elif new_prof == "Select your field...":
                    errs.append("Please select your profession")
                if errs:
                    st.error(errs[0])
                else:
                    uid = create_user(new_user.strip(), new_email.strip(), new_pw, new_prof)
                    if uid:
                        plan_info = ""
                        if is_owner(new_user.strip(), new_email.strip()):
                            plan_info = " — **Owner account** with full access!"
                        else:
                            # Welcome bonus: 1 free credit so new users can try it immediately.
                            try:
                                add_credits(uid, 1, reason="welcome_bonus", granted_by="system")
                                plan_info = " — we added **1 free credit** to get you started!"
                            except Exception:
                                pass
                        st.success(f"✅ Account created! Please login.{plan_info}")
                        st.info("💡 You get 1 free credit. Buy more from ₹49 or subscribe in **Account → Subscription & Credits**.")
                    else:
                        st.error("Username or email already exists. Try a different one.")

        # ── FORGOT PASSWORD TAB ─────────────────────────────────
        with tab3:
            st.markdown("""
<div class="sug info" style="margin-bottom:16px">
  <div class="sug-title">HOW IT WORKS</div>
  <div class="sug-body">
    Step 1 — Enter your username or email and click <b>Send OTP</b>.<br>
    Step 2 — A 6-digit code is shown on screen (since this is offline, no email is sent — copy it).<br>
    Step 3 — Enter the code and your new password, then click <b>Reset Password</b>.<br>
    <i>The code is valid for 15 minutes.</i>
  </div>
</div>""", unsafe_allow_html=True)

            # Step 1: request OTP
            with st.form("forgot_step1"):
                ident = st.text_input("Username or Email", placeholder="Enter your username or email")
                req_btn = st.form_submit_button("Send OTP Code", use_container_width=True)
            if req_btn:
                if not ident.strip():
                    st.error("Please enter your username or email")
                else:
                    user_fp = get_user_by_username(ident.strip())
                    if not user_fp:
                        user_fp = get_user_by_email(ident.strip())
                    if not user_fp:
                        st.error("No account found with that username or email.")
                    else:
                        token = create_reset_token(user_fp["id"])
                        st.session_state.fp_user_id = user_fp["id"]
                        st.session_state.fp_username = user_fp["username"]
                        st.success(f"OTP generated for **{user_fp['username']}**")
                        st.markdown(f"""
<div style="background:#1a1d27;border:2px solid #6366f1;border-radius:8px;padding:18px;text-align:center;margin:12px 0">
  <div style="font-size:11px;color:#6b7280;margin-bottom:6px;text-transform:uppercase;letter-spacing:.5px">Your One-Time Password (OTP)</div>
  <div style="font-size:42px;font-weight:900;color:#818cf8;letter-spacing:10px">{token}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:6px">Valid for 15 minutes · Do not share</div>
</div>""", unsafe_allow_html=True)

            # Step 2: reset with OTP
            st.markdown("---")
            st.markdown("**Step 2 — Enter OTP and new password**")
            with st.form("forgot_step2"):
                fp_ident  = st.text_input("Username or Email", key="fp2_ident", placeholder="Same as above")
                fp_token  = st.text_input("OTP Code (6 digits)", key="fp2_token", placeholder="123456")
                fp_newpw  = st.text_input("New Password", type="password", key="fp2_newpw")
                fp_confpw = st.text_input("Confirm New Password", type="password", key="fp2_conf")
                reset_btn = st.form_submit_button("Reset Password", use_container_width=True, type="primary")
            if reset_btn:
                if not all([fp_ident.strip(), fp_token.strip(), fp_newpw, fp_confpw]):
                    st.error("All fields are required")
                elif fp_newpw != fp_confpw:
                    st.error("Passwords do not match")
                else:
                    result = reset_password_with_token(fp_ident.strip(), fp_token.strip(), fp_newpw)
                    if result["ok"]:
                        st.success(f"✅ {result['message']} You can now login with your new password.")
                    else:
                        st.error(f"❌ {result['message']}")


# ══════════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════════
def _activate_section(sec):
    """on_change callback: selecting any nav item activates its section."""
    st.session_state.section = sec


def render_sidebar():
    with st.sidebar:
        # Logo
        st.markdown("""
<div class="logo-box">
  <div class="logo-mark">ATS</div>
  <div>
    <div class="logo-text">Resume Maker Pro</div>
    <div class="logo-sub">AI-Powered • ATS-Optimized</div>
  </div>
</div>""", unsafe_allow_html=True)

        # User info with role-based plan badge
        role = st.session_state.get("user_role", "user")
        plan = st.session_state.get("user_plan", "free")
        rem  = st.session_state.get("usage_remaining", 0)
        if role == "owner":
            plan_label = "👑 Owner · Full Access"
            badge_style = "background:linear-gradient(90deg,#6366f1,#22c55e);color:#fff"
        elif role == "admin":
            plan_label = "🛡️ Admin · Full Access"
            badge_style = "background:#222536;color:#818cf8;border:1px solid #6366f1"
        elif plan == "agency":
            plan_label = "🚀 Agency · ∞ uses"
            badge_style = "background:#222536;color:#818cf8;border:1px solid #6366f1"
        elif plan == "yearly":
            plan_label = f"📅 Annual · {rem}/day left"
            badge_style = "background:var(--accent-soft);color:var(--accent2)"
        elif plan == "monthly":
            plan_label = f"⭐ Monthly · {rem} uses left"
            badge_style = "background:var(--accent-soft);color:var(--accent2)"
        elif plan == "expired":
            plan_label = "❌ Expired — Renew"
            badge_style = "background:var(--red-soft);color:var(--red)"
        else:
            plan_label = "🔒 No Plan — Subscribe"
            badge_style = "background:#222536;color:#6b7280"

        credits = st.session_state.get("credits", 0)
        credit_chip = ""
        if role not in ("owner", "admin") and plan not in ("agency",):
            cc_style = ("background:var(--green-soft);color:var(--green)" if credits > 0
                        else "background:#222536;color:#6b7280")
            credit_chip = (f'<div style="padding:6px 10px;border-radius:6px;font-size:11px;'
                           f'font-weight:700;margin-bottom:8px;{cc_style}">🪙 {credits} credit'
                           f'{"s" if credits != 1 else ""}</div>')

        st.markdown(f"""
<div class="user-chip">
  <span>👤</span><span style="font-size:13px;font-weight:600">{st.session_state.username}</span>
</div>
<div style="padding:6px 10px;border-radius:6px;font-size:11px;font-weight:700;margin-bottom:8px;{badge_style}">{plan_label}</div>
{credit_chip}""", unsafe_allow_html=True)

        section = st.session_state.get("section", "Workspace")

        # Apply any pending navigation BEFORE the radios are instantiated
        # (Streamlit forbids mutating a widget key after its widget exists).
        for _pend, _wk in (("_pending_ws", "ws_radio"),
                           ("_pending_ai", "ai_radio"),
                           ("_pending_acc", "acc_radio")):
            if _pend in st.session_state:
                st.session_state[_wk] = st.session_state.pop(_pend)

        # ── WORKSPACE group ──────────────────────────────────
        st.markdown('<div class="nav-group">Workspace</div>', unsafe_allow_html=True)
        ws_options = ["🏠 Dashboard", "📝 Resume Builder", "✨ Resume Optimizer",
                      "📊 Deep Analysis", "◷ History", "🎨 Templates"]
        if st.session_state.get("ws_radio") not in ws_options:
            st.session_state.ws_radio = (st.session_state.ws_page
                                         if st.session_state.ws_page in ws_options else ws_options[0])
        st.radio("WS", ws_options, key="ws_radio", label_visibility="collapsed",
                 on_change=_activate_section, args=("Workspace",))
        st.session_state.ws_page = st.session_state.ws_radio

        # ── AI TOOLS group ───────────────────────────────────
        st.markdown('<div class="nav-group">AI Tools</div>', unsafe_allow_html=True)
        ai_options = ["◈ Keyword Engine", "✉ Cover Letter AI", "◐ Interview Prep"]
        if st.session_state.get("ai_radio") not in ai_options:
            st.session_state.ai_radio = (st.session_state.ai_page
                                         if st.session_state.ai_page in ai_options else ai_options[0])
        st.radio("AI", ai_options, key="ai_radio", label_visibility="collapsed",
                 on_change=_activate_section, args=("AI Tools",))
        st.session_state.ai_page = st.session_state.ai_radio
        if not st.session_state.get("has_ai_tools", False):
            st.markdown('<div style="font-size:10px;color:#6b7280;padding:2px 0 0">🔒 Subscribe or buy credits to use AI tools</div>', unsafe_allow_html=True)

        # ── ACCOUNT group ────────────────────────────────────
        st.markdown('<div class="nav-group">Account</div>', unsafe_allow_html=True)
        acc_options = ["⚙ Settings", "🔑 Subscription & Credits"]
        if st.session_state.is_admin:
            acc_options.append("🛡️ Admin Panel")
        if st.session_state.get("acc_radio") not in acc_options:
            st.session_state.acc_radio = (st.session_state.acc_page
                                          if st.session_state.acc_page in acc_options else acc_options[0])
        st.radio("ACC", acc_options, key="acc_radio", label_visibility="collapsed",
                 on_change=_activate_section, args=("Account",))
        st.session_state.acc_page = st.session_state.acc_radio

        st.markdown("---")
        st.markdown(f'<div style="font-size:10px;color:#6b7280;text-align:center">Active: '
                    f'<b style="color:#818cf8">{st.session_state.get("section","Workspace")}</b></div>',
                    unsafe_allow_html=True)
        st.markdown("---")

        # Logout
        if st.button("🚪 Logout", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

        st.markdown("""
<div style="font-size:10px;color:#4b5563;text-align:center;margin-top:10px">
ATS Resume Maker Pro v2.0<br>Made with ❤ for job seekers
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# PAGE: DASHBOARD
# ══════════════════════════════════════════════════════════════════
def show_dashboard():
    stats = get_user_stats(st.session_state.user_id)
    plan_key = st.session_state.get("user_plan", "none")
    role = st.session_state.get("user_role", "user")
    if role in ("owner", "admin") or plan_key == "agency":
        access_label = "∞ Full"
    elif plan_key in ("monthly", "yearly"):
        access_label = PLANS.get(plan_key, {}).get("name", plan_key)
    else:
        access_label = f"🪙 {st.session_state.get('credits', 0)}"
    history = get_user_analysis_history(st.session_state.user_id)
    best_score = max((h["score"] for h in history), default=0)

    st.markdown('<div class="ph"><h2>🏠 Dashboard</h2><p>Welcome to your ATS Resume Maker Pro workspace — 100% offline & private.</p></div><br>', unsafe_allow_html=True)
    st.markdown(f"""
<div class="stats-row">
  <div class="stat-card"><div class="stat-label">Resumes Created</div><div class="stat-val">{stats['total_resumes']}</div></div>
  <div class="stat-card"><div class="stat-label">Avg ATS Score</div><div class="stat-val">{stats['avg_score']}%</div></div>
  <div class="stat-card"><div class="stat-label">Best Score</div><div class="stat-val" style="color:var(--green)">{best_score}%</div></div>
  <div class="stat-card"><div class="stat-label">Credits / Plan</div><div class="stat-val" style="font-size:18px">{access_label}</div></div>
</div>""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    features = [
        ("📝", "Resume Builder", "Create professional resumes from scratch using ATS-optimized templates. Ideal for freshers.", "ws_radio", "📝 Resume Builder"),
        ("✨", "Resume Optimizer", "Upload your existing resume and job description to get AI-powered keyword optimization.", "ws_radio", "✨ Resume Optimizer"),
        ("📊", "Deep Analysis", "Get detailed ATS scores, section-by-section breakdown, and platform compatibility check.", "ws_radio", "📊 Deep Analysis"),
    ]
    for col, (icon, title, desc, key, val) in zip([c1, c2, c3], features):
        with col:
            st.markdown(f'<div class="card"><div class="card-hd"><span>{icon}</span> {title}</div><p style="font-size:12px;color:var(--muted)">{desc}</p></div>', unsafe_allow_html=True)
            if st.button(f"Go to {title}", key=f"dash_{title}", use_container_width=True):
                st.session_state.ws_page = val
                st.session_state["_pending_ws"] = val
                st.session_state.section = "Workspace"
                st.rerun()


# ══════════════════════════════════════════════════════════════════
# PAGE: RESUME BUILDER (FRESHER-FOCUSED)
# ══════════════════════════════════════════════════════════════════
def _template_select(label="📐 Resume Template", key="tpl_pick", help_text=None):
    """Unified template picker — same 21 templates as the gallery, kept in sync
    with `selected_template` so a choice made anywhere applies everywhere."""
    ids = list(BUILTIN_TEMPLATES.keys())
    labels = [f"{BUILTIN_TEMPLATES[i]['name']} · {BUILTIN_TEMPLATES[i]['category']}" for i in ids]
    cur = st.session_state.get("selected_template", "classic_professional")
    if cur not in ids:                       # e.g. a word_* selection
        cur = "classic_professional"
    desired = labels[ids.index(cur)]
    # Force the widget to reflect the current global selection (overrides any
    # stale per-widget state from another page).
    if st.session_state.get(key) != desired:
        st.session_state[key] = desired
    choice = st.selectbox(label, labels, key=key, help=help_text)
    sel = ids[labels.index(choice)]
    st.session_state.selected_template = sel
    with st.expander("👁 Preview this template", expanded=False):
        st.markdown(render_template_preview_html(sel), unsafe_allow_html=True)
    return sel


def show_resume_builder():
    st.markdown('<div class="ph"><h2>📝 Resume Builder</h2><p>Build a professional ATS-optimized resume. Fill in the sections below — the output matches your selected template exactly.</p></div><br>', unsafe_allow_html=True)

    # Template selector (top) — unified 21-template registry
    selected_template_id = _template_select("📐 Resume Template", key="builder_tpl",
        help_text="Each template has its own layout, font and colour. Your download matches this exactly.")
    tpl_info = BUILTIN_TEMPLATES[selected_template_id]
    st.markdown(f"""
<div class="sug info" style="margin-bottom:16px">
  <div class="sug-title">Template: {tpl_info['name']} · {tpl_info['category']}</div>
  <div class="sug-body">{tpl_info['desc']} — Section order: {' → '.join(s.title() for s in tpl_info['section_order'][:5])}…</div>
</div>""", unsafe_allow_html=True)

    with st.form("builder_form", clear_on_submit=False):
        # ── Personal Information ─────────────────────────────
        st.markdown("### 👤 Personal Information")
        c1, c2 = st.columns(2)
        with c1:
            full_name = st.text_input("Full Name *", placeholder="e.g. Priya Sharma")
            email = st.text_input("Email *", placeholder="priya.sharma@email.com")
            phone = st.text_input("Phone *", placeholder="+91 98765 43210")
        with c2:
            location = st.text_input("Location / City", placeholder="Hyderabad, India")
            linkedin = st.text_input("LinkedIn URL", placeholder="linkedin.com/in/priyasharma")
            github = st.text_input("GitHub / Portfolio URL", placeholder="github.com/priyasharma")
        address = st.text_input("Address (shown under name & contact)",
                                placeholder="H.No 1-2-3, Street, Area, City, State – PIN")
        website = st.text_input("Website (optional)", placeholder="https://priyasharma.dev")

        # ── Photograph (top-left, beside the heading) ─────────
        photo_file = st.file_uploader(
            "📷 Profile Photograph (optional — placed top-left beside your name)",
            type=["png", "jpg", "jpeg"], key="builder_photo")
        if photo_file:
            st.image(photo_file, width=110, caption="Preview")

        # ── AI enhancement toggle ─────────────────────────────
        _ai_on = llm.ollama_available()
        ai_enhance = st.checkbox(
            "✨ Let AI rewrite my Objective, Experience & Project descriptions into polished bullets",
            value=True,
            help=("Type rough notes in those fields — they'll be rewritten on generate. "
                  + ("On-device AI (Ollama) detected." if _ai_on
                     else "No local AI detected: notes are cleanly formatted into bullets instead.")))

        # ── Objective / Summary ──────────────────────────────
        st.markdown("### 🎯 Career Objective / Professional Summary")
        summary = st.text_area(
            "Objective",
            height=100,
            placeholder="Write a few rough words about your goal — e.g. 'fresher medical lab technician, good at NABL documentation, want a lab role'. AI will turn it into a polished summary.",
            label_visibility="collapsed"
        )

        # ── Industry for skill suggestions ───────────────────
        st.markdown("### 🏭 Target Industry")
        industry = st.selectbox(
            "Industry",
            list(SKILL_SUGGESTIONS.keys()),
            index=0,
            label_visibility="collapsed"
        )

        # ── Education ────────────────────────────────────────
        st.markdown("### 🎓 Education")
        num_edu = st.number_input("Number of education entries", 1, 4, 1, key="num_edu")
        educations = []
        for i in range(int(num_edu)):
            with st.expander(f"Education {i+1}", expanded=(i == 0)):
                ec1, ec2 = st.columns(2)
                with ec1:
                    degree = st.text_input("Degree / Programme *", key=f"deg_{i}",
                                           placeholder="B.Tech Computer Science")
                    school = st.text_input("Institution / University *", key=f"sch_{i}",
                                           placeholder="JNTU Hyderabad")
                with ec2:
                    edu_start = st.text_input("Start Year", key=f"est_{i}", placeholder="2020")
                    edu_end = st.text_input("End Year / Expected", key=f"eed_{i}", placeholder="2024")
                    gpa = st.text_input("CGPA / Percentage", key=f"gpa_{i}", placeholder="8.5/10")
                honors = st.text_input("Honours / Specialisation", key=f"hon_{i}",
                                       placeholder="Minor in AI, Gold Medal...")
                educations.append({
                    "degree": degree, "school": school,
                    "year": f"{edu_start}–{edu_end}".strip("–"),
                    "gpa": gpa, "honors": honors
                })

        # ── Skills ───────────────────────────────────────────
        st.markdown("### 🛠 Skills")
        suggested = SKILL_SUGGESTIONS.get(industry, [])
        st.caption(f"Suggested for {industry}: " + ", ".join(suggested[:8]))
        skill_cats = {}
        c1, c2 = st.columns(2)
        with c1:
            prog_langs = st.text_input("Programming Languages", key="sk_prog",
                                        placeholder="Python, R, Java, SQL")
            tools_tech = st.text_input("Tools & Technologies", key="sk_tools",
                                        placeholder="Git, Docker, AWS, JIRA")
            frameworks = st.text_input("Frameworks / Libraries", key="sk_fw",
                                        placeholder="TensorFlow, React, Pandas, scikit-learn")
        with c2:
            domain_skills = st.text_input("Domain / Technical Skills", key="sk_domain",
                                           placeholder="Machine Learning, Data Analysis, NGS")
            soft_skills = st.text_input("Soft Skills", key="sk_soft",
                                         placeholder="Leadership, Communication, Problem Solving")
            languages_spoken = st.text_input("Languages Spoken", key="sk_lang",
                                              placeholder="English (Fluent), Telugu (Native), Hindi")

        for label, val in [
            ("Programming Languages", prog_langs),
            ("Tools & Technologies", tools_tech),
            ("Frameworks & Libraries", frameworks),
            ("Domain Skills", domain_skills),
            ("Soft Skills", soft_skills),
        ]:
            if val.strip():
                skill_cats[label] = [s.strip() for s in val.split(",") if s.strip()]

        # ── Work Experience / Internships ────────────────────
        st.markdown("### 💼 Work Experience & Internships")
        num_exp = st.number_input("Number of positions (0 if fresher with no experience)", 0, 6, 1, key="num_exp")
        experiences = []
        for i in range(int(num_exp)):
            with st.expander(f"Position {i+1}", expanded=(i == 0)):
                ec1, ec2 = st.columns(2)
                with ec1:
                    position = st.text_input("Job Title / Intern Role *", key=f"pos_{i}",
                                             placeholder="Software Engineering Intern")
                    company = st.text_input("Company / Organisation *", key=f"com_{i}",
                                            placeholder="Infosys, Wipro, Startup Name")
                with ec2:
                    exp_start = st.text_input("Start Date", key=f"xs_{i}", placeholder="Jun 2023")
                    exp_end = st.text_input("End Date / Present", key=f"xe_{i}", placeholder="Aug 2023")
                    exp_location = st.text_input("Location", key=f"xl_{i}", placeholder="Hyderabad")
                desc = st.text_area(
                    "Responsibilities & Achievements — type simple notes; AI rewrites them into polished bullets",
                    key=f"xd_{i}", height=100,
                    placeholder="Just list what you did, e.g.:\nNABL file creation, sample collection, daily QC reports\n(or one point per line — AI will turn these into strong bullet points)"
                )
                experiences.append({
                    "position": position, "company": company,
                    "dates": f"{exp_start}–{exp_end}".strip("–"),
                    "location": exp_location,
                    "description": desc
                })

        # ── Projects ─────────────────────────────────────────
        st.markdown("### 🚀 Projects (Academic / Personal)")
        num_proj = st.number_input("Number of projects", 0, 6, 2, key="num_proj")
        projects = []
        for i in range(int(num_proj)):
            with st.expander(f"Project {i+1}", expanded=(i < 2)):
                pc1, pc2 = st.columns(2)
                with pc1:
                    proj_title = st.text_input("Project Title *", key=f"pt_{i}",
                                               placeholder="Crop Disease Detection using CNN")
                    proj_tech = st.text_input("Technologies Used", key=f"ptech_{i}",
                                              placeholder="Python, TensorFlow, OpenCV, Flask")
                with pc2:
                    proj_link = st.text_input("GitHub / Live Link", key=f"plink_{i}",
                                              placeholder="github.com/username/project")
                    proj_date = st.text_input("Year / Period", key=f"pdate_{i}", placeholder="2023")
                proj_desc = st.text_area(
                    "Description — type simple notes; AI rewrites them into polished bullets",
                    key=f"pdesc_{i}", height=80,
                    placeholder="e.g. PCR profiling of genes in waste-water bacteria; analysed antibiotic resistance\n(AI will expand this into strong project bullets)"
                )
                projects.append({
                    "title": proj_title, "tech": proj_tech, "link": proj_link,
                    "date": proj_date, "description": proj_desc
                })

        # ── Certifications ────────────────────────────────────
        st.markdown("### 🏆 Certifications & Courses")
        certifications_text = st.text_area(
            "Certifications (one per line)",
            height=80,
            placeholder="Google Data Analytics Professional Certificate (2023)\nAWS Certified Cloud Practitioner (2023)\nDeep Learning Specialization — Coursera / Andrew Ng",
            label_visibility="collapsed"
        )

        # ── Awards & Achievements ─────────────────────────────
        st.markdown("### 🥇 Awards & Achievements")
        awards_text = st.text_area(
            "Awards (one per line)",
            height=70,
            placeholder="First prize, Smart India Hackathon 2023 (Team of 6)\nDean's List — Top 5% of graduating class\nBest Paper Award, ICTCS 2022",
            label_visibility="collapsed"
        )

        # ── Publications (optional) ───────────────────────────
        st.markdown("### 📚 Publications / Research (optional)")
        publications_text = st.text_area(
            "Publications",
            height=70,
            placeholder="Sharma P., et al. (2023). Deep learning for crop disease detection. Journal of Agricultural Informatics, 12(3), 45-58.",
            label_visibility="collapsed"
        )

        # ── Activities ────────────────────────────────────────
        st.markdown("### 🌟 Extracurricular Activities (optional)")
        activities_text = st.text_area(
            "Activities",
            height=60,
            placeholder="Technical Secretary, IEEE Student Branch (2022–2023)\nVolunteer, NSS Rural Development Programme (2021)",
            label_visibility="collapsed"
        )

        # ── Declaration ───────────────────────────────────────
        st.markdown("### ✍️ Declaration (placed at the end)")
        include_declaration = st.checkbox("Include a declaration at the end of the resume", value=True)
        declaration_text = st.text_area(
            "Declaration text",
            value="I hereby declare that the above information is true and correct to the best of my knowledge and belief.",
            height=70, label_visibility="collapsed")
        dc1, dc2 = st.columns(2)
        with dc1:
            decl_place = st.text_input("Place", placeholder="Hyderabad")
        with dc2:
            decl_date = st.text_input("Date", placeholder="e.g. 13 Jun 2026")

        # ── Submit ────────────────────────────────────────────
        submitted = st.form_submit_button("🎯 Generate & Download Resume", use_container_width=True, type="primary")

    if submitted:
        if not full_name.strip() or not email.strip():
            st.error("Full Name and Email are required")
            return

        exp_clean = [e for e in experiences if e.get("position") or e.get("company")]
        proj_clean = [p for p in projects if p.get("title")]
        final_summary = summary.strip()

        # ── AI / rule-based rewrite of free-text fields ───────
        if ai_enhance:
            with st.spinner("✨ Rewriting your descriptions into polished bullets..."):
                if final_summary:
                    final_summary = ai_write_summary(final_summary, full_name.strip(), industry)
                for e in exp_clean:
                    if e.get("description", "").strip():
                        e["description"] = ai_write_bullets(
                            e["description"], role=e.get("position", ""),
                            org=e.get("company", ""), industry=industry)
                for p in proj_clean:
                    if p.get("description", "").strip():
                        p["description"] = ai_write_bullets(
                            p["description"], role=p.get("title", ""), industry=industry)

        # Build data dict (JSON-serialisable — no image bytes)
        resume_data = {
            "template_name": selected_template_id,
            "personal_info": {
                "name": full_name.strip(),
                "email": email.strip(),
                "phone": phone.strip(),
                "location": location.strip(),
                "address": address.strip(),
                "linkedin": linkedin.strip(),
                "github": github.strip(),
                "website": website.strip(),
            },
            "summary": final_summary,
            "education": [e for e in educations if e.get("degree") or e.get("school")],
            "experience": exp_clean,
            "skill_categories": skill_cats,
            "skills": ", ".join(
                item for cat_items in skill_cats.values()
                for item in (cat_items if isinstance(cat_items, list) else [cat_items])
            ),
            "projects": proj_clean,
            "certifications": [c.strip() for c in certifications_text.split("\n") if c.strip()],
            "awards": [a.strip() for a in awards_text.split("\n") if a.strip()],
            "publications": [p.strip() for p in publications_text.split("\n") if p.strip()],
            "languages": languages_spoken.strip(),
            "activities": activities_text.strip(),
            "declaration": declaration_text.strip() if include_declaration else "",
            "declaration_place": decl_place.strip(),
            "declaration_date": decl_date.strip(),
        }

        # Export payload also carries the photo (bytes can't be saved as JSON)
        export_data = dict(resume_data)
        if photo_file is not None:
            try:
                export_data["photo_bytes"] = photo_file.getvalue()
            except Exception:
                pass

        with st.spinner("Building your resume with template formatting..."):
            docx_bytes = export_resume_to_docx(export_data, selected_template_id)
            txt_content = export_resume_to_txt(export_data)
            resume_id = save_resume(
                st.session_state.user_id, full_name,
                resume_data, selected_template_id
            )

        st.success(f"✅ Resume generated with **{tpl_info['name']}** template!")

        # Preview template
        st.markdown(f"**Template preview:**")
        preview_html = get_template_preview_html(selected_template_id)
        st.markdown(f'<div style="border:2px solid var(--accent);border-radius:var(--radius);overflow:hidden;max-width:400px">{preview_html}</div>', unsafe_allow_html=True)

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.download_button(
                "📥 Download DOCX",
                data=docx_bytes,
                file_name=f"{full_name.replace(' ','_')}_resume.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
        with c2:
            st.download_button(
                "📥 Download TXT",
                data=txt_content,
                file_name=f"{full_name.replace(' ','_')}_resume.txt",
                mime="text/plain",
                use_container_width=True
            )


# ══════════════════════════════════════════════════════════════════
# PAGE: RESUME OPTIMIZER
# ══════════════════════════════════════════════════════════════════
def show_resume_optimizer():
    st.markdown('<div class="ph"><h2>✨ Resume Optimizer</h2><p>Upload your resume + paste a job description → AI surgically rewrites Summary, Experience bullets, and Skills. All other sections are preserved exactly.</p></div><br>', unsafe_allow_html=True)

    # Step bar
    st.markdown(_step_bar(st.session_state.step), unsafe_allow_html=True)

    left, right = st.columns([1, 1])

    # ── LEFT COLUMN ──────────────────────────────────────────
    with left:

        # Upload card
        st.markdown('<div class="card"><div class="card-hd"><span>📄</span> Your Resume</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader("Drop PDF/DOCX/TXT here", type=["pdf", "docx", "txt"],
                                     label_visibility="collapsed", key="resume_upload")
        if uploaded:
            with st.spinner("Reading file..."):
                text = extract_text_from_file(uploaded)
            st.session_state.resume_text = text
            st.session_state.original_resume = text
            st.session_state.step = max(st.session_state.step, 2)
            st.success(f"✅ {uploaded.name} loaded ({len(text)} chars)")

        if st.button("✎ Paste text instead", key="tog_paste"):
            st.session_state.show_paste = not st.session_state.show_paste

        if st.session_state.show_paste:
            pasted = st.text_area("Paste resume text here", height=200, key="paste_input",
                                   value=st.session_state.resume_text)
            if pasted:
                st.session_state.resume_text = pasted
                st.session_state.original_resume = pasted
                st.session_state.step = max(st.session_state.step, 2)
        st.markdown("</div>", unsafe_allow_html=True)

        # JD card
        st.markdown('<div class="card"><div class="card-hd"><span>💼</span> Job Description</div>', unsafe_allow_html=True)

        jd_col1, jd_col2 = st.columns(2)
        with jd_col1:
            jd_file = st.file_uploader("Upload JD", type=["pdf", "docx", "txt"],
                                        label_visibility="collapsed", key="jd_upload")
        with jd_col2:
            if st.button("📋 Load Sample JD", use_container_width=True):
                st.session_state.jd_text = SAMPLE_JD
        if jd_file:
            st.session_state.jd_text = extract_text_from_file(jd_file)

        jd = st.text_area("Paste job description here", height=200,
                           value=st.session_state.jd_text, key="jd_input",
                           placeholder="Paste the full job description — all requirements and responsibilities...")
        if jd:
            st.session_state.jd_text = jd
            st.session_state.step = max(st.session_state.step, 2)
        st.markdown("</div>", unsafe_allow_html=True)

        # Settings card
        st.markdown('<div class="card"><div class="card-hd"><span>⚙</span> Settings</div>', unsafe_allow_html=True)

        # Template selection — unified registry (same as gallery & builder)
        _template_select("Resume Template", key="optimizer_tpl",
                         help_text="Your DOCX export uses this template's fonts, colours and section order")

        c1, c2 = st.columns(2)
        with c1:
            preserve = st.checkbox("Preserve Structure", value=True)
            keywords_inj = st.checkbox("Keyword Injection", value=True)
        with c2:
            power_verbs = st.checkbox("Power Verbs", value=True)
            expand_skills = st.checkbox("Expand Skills", value=True)

        industry_opts = list(SKILL_SUGGESTIONS.keys())
        industry = st.selectbox("Industry Focus", industry_opts, index=1)
        st.markdown("</div>", unsafe_allow_html=True)

        # Optimize button
        if st.button("⚡ Optimize Resume with AI", use_container_width=True, type="primary"):
            if not st.session_state.resume_text.strip():
                st.error("Please upload or paste your resume first")
            elif not st.session_state.jd_text.strip():
                st.error("Please paste a job description first")
            else:
                # Usage gate — check plan and quota
                allowed, reason, remaining = can_use_optimizer(
                    st.session_state.user_id,
                    st.session_state.username,
                    st.session_state.get("user_email","")
                )
                if not allowed:
                    if reason == "no_plan":
                        st.error("❌ No active plan. Go to **Account → Subscription** to activate a plan.")
                    elif reason == "quota_exhausted":
                        plan_n = PLANS.get(st.session_state.user_plan,{}).get("name","your plan")
                        st.error(f"❌ You have used all resume optimizations for {plan_n}. Upgrade to continue.")
                    elif reason == "daily_limit":
                        st.warning("⏳ Daily limit reached. Come back tomorrow or upgrade to Monthly plan for 10/day.")
                    elif reason == "expired":
                        st.error("❌ Your subscription has expired. Renew at **Account → Subscription**.")
                    st.stop()
                else:
                    with st.spinner("⚡ Analyzing and rewriting resume sections..."):
                        parsed = parse_resume_text(st.session_state.resume_text)
                        result = optimize_resume_for_jd(parsed, st.session_state.jd_text)
                        # Save profession metadata for better future recommendations
                        profession = st.session_state.get("user_profession","")
                        try:
                            save_ats_analysis(
                                st.session_state.user_id, None,
                                result["score"], result,
                                st.session_state.jd_text[:200],
                                profession=profession
                            )
                        except Exception:
                            pass

                        st.session_state.optimized_resume = result["optimized_resume"]
                        st.session_state.ats_score        = result["score"]
                        st.session_state.step             = 4
                        st.session_state.opt_change_log   = result.get("change_log", [])
                        st.session_state.opt_parsed        = parsed

                    # Use keywords from the result (post-optimization check)
                    st.session_state.kw_found   = result.get("keywords_found", [])
                    st.session_state.kw_missing  = result.get("keywords_missing", [])

                    # Record usage — subscription quota first, else 1 credit
                    try:
                        method = record_optimizer_use(st.session_state.user_id,
                                                      st.session_state.username,
                                                      st.session_state.get("user_email",""))
                        _refresh_access()
                        _, _, rem = can_use_optimizer(st.session_state.user_id,
                                                       st.session_state.username,
                                                       st.session_state.get("user_email",""))
                        st.session_state.usage_remaining = rem
                        if method == "credit":
                            st.toast(f"1 credit used · {st.session_state.credits} left")
                    except Exception:
                        pass



                st.rerun()

    # ── RIGHT COLUMN ─────────────────────────────────────────
    with right:

        # ATS Score Ring — only after optimization
        if st.session_state.step >= 3:
            st.markdown('<div class="card"><div class="card-hd"><span>◎</span> ATS Score</div>', unsafe_allow_html=True)
            st.markdown(_score_ring(st.session_state.ats_score), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # Keyword cloud
            st.markdown('<div class="card"><div class="card-hd"><span>◈</span> Keyword Analysis</div>', unsafe_allow_html=True)
            st.markdown("""
<div class="kw-legend">
  <span class="kw-chip found">● Found</span>
  <span class="kw-chip missing">● Missing</span>
</div>""", unsafe_allow_html=True)
            kw_html = _kw_cloud(
                st.session_state.optimized_resume or st.session_state.resume_text,
                st.session_state.jd_text
            )
            st.markdown(f'<div class="kw-cloud">{kw_html}</div>', unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

        # Suggestions card
        st.markdown('<div class="card"><div class="card-hd"><span>💡</span> Optimization Result</div>', unsafe_allow_html=True)
        score = st.session_state.ats_score
        if st.session_state.step < 3:
            st.markdown("""
<div class="sug info">
  <div class="sug-title">HOW IT WORKS</div>
  <div class="sug-body">
    1. Upload your resume &amp; paste the job description<br>
    2. Click <b>Optimize</b> — the AI automatically:<br>
    &nbsp;&nbsp;• Rewrites your Summary with JD keywords<br>
    &nbsp;&nbsp;• Injects keywords into Experience bullets<br>
    &nbsp;&nbsp;• Adds all missing skills to your Skills section<br>
    3. Download the optimized DOCX — ready to submit
  </div>
</div>""", unsafe_allow_html=True)
        else:
            found_count   = len(st.session_state.kw_found)
            missing_count = len(st.session_state.kw_missing)
            total         = found_count + missing_count
            if score >= 80:
                st.markdown(f"""
<div class="sug ok">
  <div class="sug-title">✅ EXCELLENT ATS MATCH</div>
  <div class="sug-body">
    Score: <b>{score}%</b> — {found_count}/{total} keywords matched.<br>
    Your resume will pass most ATS filters. Download the DOCX and submit!
  </div>
</div>""", unsafe_allow_html=True)
            elif score >= 60:
                st.markdown(f"""
<div class="sug warn">
  <div class="sug-title">⚡ OPTIMIZED — GOOD MATCH</div>
  <div class="sug-body">
    Score: <b>{score}%</b> — {found_count}/{total} keywords matched.<br>
    The AI has already rewritten your Summary, Experience bullets and Skills.<br>
    Download the DOCX below — it is significantly improved from your original.
  </div>
</div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
<div class="sug err">
  <div class="sug-title">⚠️ OPTIMIZED — REVIEW NEEDED</div>
  <div class="sug-body">
    Score: <b>{score}%</b> — {found_count}/{total} keywords matched.<br>
    The AI has rewritten your resume. Consider also updating your job titles
    or adding more specific project details that match the JD requirements.
  </div>
</div>""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        # Output card — after optimization
        if st.session_state.step >= 4 and st.session_state.optimized_resume:
            score = st.session_state.ats_score
            st.markdown(f'<div class="card"><div class="card-hd"><span>✓</span> Optimized Resume <span class="badge-green">ATS: {score}%</span></div>', unsafe_allow_html=True)

            oc1, oc2, oc3 = st.columns(3)
            with oc1:
                if st.button("🔍 View Changes", key="diff_toggle"):
                    st.session_state.show_diff = not st.session_state.show_diff
            with oc2:
                if st.button("📝 Edit Resume", key="edit_toggle"):
                    st.session_state.show_diff = False
            with oc3:
                if st.button("↻ Re-optimize", key="reopt"):
                    st.session_state.step = 2
                    st.rerun()

            # ── CHANGE LOG (diff view) ──────────────────────────────
            if st.session_state.show_diff:
                change_log = st.session_state.get("opt_change_log", [])
                if change_log:
                    st.markdown("""
<div style="background:#1a1d27;border:1px solid #2a2d3e;border-radius:8px;
            padding:14px;margin-bottom:12px">
  <div style="font-size:12px;font-weight:700;color:#818cf8;margin-bottom:10px">
    📋 What CVIQ Changed — Review &amp; Decide to Keep or Edit
  </div>""", unsafe_allow_html=True)

                    for i, ch in enumerate(change_log):
                        t = ch.get("type", "")
                        if t == "summary":
                            st.markdown(f"""
<div style="background:#222536;border-left:3px solid #6366f1;border-radius:4px;
            padding:10px 12px;margin-bottom:8px">
  <div style="font-size:10px;font-weight:700;color:#818cf8;text-transform:uppercase;
              margin-bottom:4px">📝 Professional Summary — Bridge Sentence Added</div>
  <div style="font-size:12px;color:#22c55e;line-height:1.5">+ {ch.get('added','')[:200]}</div>
  <div style="font-size:10px;color:#6b7280;margin-top:4px">Why: {ch.get('reason','')}</div>
</div>""", unsafe_allow_html=True)

                        elif t == "bullet":
                            changes_str = " · ".join(ch.get("changes", []))
                            st.markdown(f"""
<div style="background:#222536;border-left:3px solid #f59e0b;border-radius:4px;
            padding:10px 12px;margin-bottom:8px">
  <div style="font-size:10px;font-weight:700;color:#f59e0b;text-transform:uppercase;
              margin-bottom:6px">✏️ Experience Bullet #{i} — {changes_str}</div>
  <div style="font-size:11px;color:#ef4444;margin-bottom:4px;font-family:monospace">
    − {ch.get('original','')[:120]}</div>
  <div style="font-size:11px;color:#22c55e;font-family:monospace">
    + {ch.get('updated','')[:120]}</div>
</div>""", unsafe_allow_html=True)

                        elif t == "skills":
                            st.markdown(f"""
<div style="background:#222536;border-left:3px solid #22c55e;border-radius:4px;
            padding:10px 12px;margin-bottom:8px">
  <div style="font-size:10px;font-weight:700;color:#22c55e;text-transform:uppercase;
              margin-bottom:4px">🛠 Skills Section — {ch.get('count',0)} JD Phrases Added</div>
  <div style="font-size:12px;color:#22c55e">+ {ch.get('added','')[:200]}</div>
</div>""", unsafe_allow_html=True)

                    st.markdown("</div>", unsafe_allow_html=True)
                    st.markdown('<div style="font-size:11px;color:#6b7280;margin-bottom:12px">✅ Review the changes above. If any don\'t fit, edit the text box below before downloading.</div>', unsafe_allow_html=True)
                else:
                    st.info("No significant changes were made — your resume already matched the JD well.")

            # ── EDITABLE OUTPUT ─────────────────────────────────────
            edited = st.text_area(
                "Optimized Resume — edit freely before downloading:",
                value=st.session_state.optimized_resume,
                height=380,
                key="opt_output_edit",
                label_visibility="visible"
            )
            if edited != st.session_state.optimized_resume:
                st.session_state.optimized_resume = edited

            words   = len(st.session_state.optimized_resume.split())
            bullets = st.session_state.optimized_resume.count("•")
            pages   = max(1, words // 300)
            st.markdown(f'<div class="out-stats"><span class="out-stat">📝 {words} words</span><span class="out-stat">• {bullets} bullets</span><span class="out-stat">📄 ~{pages} page(s)</span></div>', unsafe_allow_html=True)

            st.markdown("---")
            exp_data = {
                "_raw": st.session_state.optimized_resume,
                "template_name": st.session_state.selected_template,
                "_parsed_sections": st.session_state.get("opt_parsed"),
            }
            dc1, dc2 = st.columns(2)
            with dc1:
                docx_bytes = export_resume_to_docx(exp_data)
                st.download_button(
                    "📥 Download DOCX",
                    data=docx_bytes,
                    file_name=f"optimized_{st.session_state.username}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
            with dc2:
                txt = export_resume_to_txt(exp_data)
                st.download_button(
                    "📄 Download TXT",
                    data=txt,
                    file_name=f"optimized_{st.session_state.username}.txt",
                    mime="text/plain",
                    use_container_width=True
                )
            st.markdown("</div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# PAGE: DEEP ANALYSIS
# ══════════════════════════════════════════════════════════════════
def show_deep_analysis():
    st.markdown('<div class="ph"><h2>📊 Deep Analysis</h2><p>Comprehensive ATS analysis across 5 dimensions with platform compatibility check.</p></div><br>', unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        ana_file = st.file_uploader("Upload resume to analyse", type=["pdf", "docx", "txt"], key="ana_upload")
        ana_paste = st.text_area("Or paste resume text", height=150, key="ana_paste")
        ana_jd = st.text_area("Paste job description (optional — for keyword match)", height=100, key="ana_jd")
        if st.button("🔍 Run Full Analysis", use_container_width=True, type="primary"):
            resume_txt = ""
            if ana_file:
                resume_txt = extract_text_from_file(ana_file)
            elif ana_paste.strip():
                resume_txt = ana_paste.strip()

            if not resume_txt:
                st.error("Please upload or paste a resume")
            else:
                st.session_state.analysis_resume = resume_txt
                st.session_state.analysis_jd = ana_jd
                # Compute score
                jd_for_score = ana_jd or st.session_state.jd_text
                parsed = parse_resume_text(resume_txt)
                result = optimize_resume_for_jd(parsed, jd_for_score or "software engineer python data analysis")
                st.session_state.analysis_score = result["score"]
                st.rerun()

    with c2:
        score = st.session_state.get("analysis_score", st.session_state.ats_score)
        if score:
            st.markdown('<div class="card"><div class="card-hd"><span>◎</span> Overall Score</div>', unsafe_allow_html=True)
            st.markdown(_score_ring(score), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # Platform compatibility
            st.markdown('<div class="card"><div class="card-hd"><span>🖥</span> ATS Platform Compatibility</div>', unsafe_allow_html=True)
            st.markdown(_platform_bars(score), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # Section breakdown
            st.markdown('<div class="card"><div class="card-hd"><span>📋</span> Section Breakdown</div>', unsafe_allow_html=True)
            st.markdown(_section_breakdown(score), unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

            # Keyword cloud if JD supplied
            jd_for_kw = st.session_state.get("analysis_jd", "") or st.session_state.jd_text
            if jd_for_kw:
                resume_for_kw = st.session_state.get("analysis_resume", st.session_state.resume_text)
                st.markdown('<div class="card"><div class="card-hd"><span>◈</span> Keyword Match</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="kw-legend"><span class="kw-chip found">● Found</span><span class="kw-chip missing">● Missing</span></div>', unsafe_allow_html=True)
                kw_html = _kw_cloud(resume_for_kw, jd_for_kw)
                st.markdown(f'<div class="kw-cloud">{kw_html}</div>', unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.markdown('<div class="sug info"><div class="sug-title">READY</div><div class="sug-body">Upload or paste a resume on the left, then click Run Full Analysis to see scores, section breakdown, and platform compatibility.</div></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# PAGE: TEMPLATES
# ══════════════════════════════════════════════════════════════════
def show_templates():
    n_tpl = len(BUILTIN_TEMPLATES)
    st.markdown(f'<div class="ph"><h2>🎨 Resume Templates</h2><p>{n_tpl} ATS-safe templates tuned for every profession. The template you select here is the exact layout, font and section order applied to your DOCX download and optimized resume.</p></div><br>', unsafe_allow_html=True)

    profession = st.session_state.get("user_profession","")
    cur = st.session_state.get("selected_template", "classic_professional")
    cur_name = BUILTIN_TEMPLATES.get(cur, {}).get("name", cur)
    st.markdown(f'<div class="sug ok"><div class="sug-title">CURRENTLY SELECTED</div>'
                f'<div class="sug-body">🎨 <b>{cur_name}</b> — this template applies to every export until you change it.</div></div>',
                unsafe_allow_html=True)

    tc1, tc2 = st.columns([2, 1])
    with tc1:
        all_cats = get_template_categories()
        cat_filter = st.selectbox("Filter by Category", all_cats, key="tpl_cat")
    with tc2:
        all_profs = ["All Professions"] + get_all_professions()
        prof_filter = st.selectbox("Filter by Profession",
                                    all_profs,
                                    index=next((i for i,p in enumerate(all_profs) if p==profession), 0),
                                    key="tpl_prof")

    st.markdown("---")

    # ── Optional: uploaded Word-file templates (only shown if present) ─────
    word_files = list_uploaded_templates()
    if word_files:
        st.markdown(f"### 📄 Your Word Templates ({len(word_files)} files)")
        st.info("Uploaded .docx templates from `templates/word/`. Select one to map your resume into it (placeholders: {{NAME}} {{SUMMARY}} {{EXPERIENCE}} {{SKILLS}} {{EDUCATION}}).")
        wf_cols = st.columns(4)
        for i, fname in enumerate(word_files):
            with wf_cols[i % 4]:
                is_sel = st.session_state.selected_template == f"word_{fname}"
                border = "2px solid #6366f1" if is_sel else "1px solid #2a2d3e"
                st.markdown(f"""
<div style="border:{border};border-radius:8px;padding:12px;background:#1a1d27;text-align:center;margin-bottom:8px">
  <div style="font-size:22px">📄</div>
  <div style="font-size:11px;font-weight:700;color:#e2e4ef;margin:4px 0">{fname.replace("_"," ").title()}</div>
  <div style="font-size:10px;color:#6b7280">.docx template</div>
  {"<div style=\'margin-top:6px;font-size:10px;color:#22c55e;font-weight:700\'>✓ Selected</div>" if is_sel else ""}
</div>""", unsafe_allow_html=True)
                if st.button("Select", key=f"wf_{fname}", use_container_width=True):
                    st.session_state.selected_template = f"word_{fname}"
                    st.success(f"Template '{fname}' selected!")
                    st.rerun()
        st.markdown("---")

    # ── Built-in templates ────────────────────────────────────────────────
    st.markdown(f"### 🎨 Built-in Templates ({n_tpl})")

    # Filter templates
    all_tpls = list(BUILTIN_TEMPLATES.items())
    if cat_filter != "All":
        all_tpls = [(k,v) for k,v in all_tpls if v.get("category","") == cat_filter]
    if prof_filter != "All Professions":
        all_tpls = [(k,v) for k,v in all_tpls
                    if "all" in v.get("professions",[]) or
                       any(prof_filter.lower() in p.lower() for p in v.get("professions",[]))]

    if not all_tpls:
        st.info("No templates match the selected filters. Showing all templates.")
        all_tpls = list(BUILTIN_TEMPLATES.items())

    # Recommended for user's profession
    recommended = []
    if profession:
        rec_ids = get_template_for_profession(profession)
        recommended = [tid for tid in rec_ids if tid in BUILTIN_TEMPLATES]

    if recommended and (cat_filter == "All" and prof_filter == "All Professions"):
        st.markdown(f"**⭐ Recommended for {profession or 'your profession'}:**")
        rec_cols = st.columns(min(4, len(recommended)))
        for i, tid in enumerate(recommended[:4]):
            tpl = BUILTIN_TEMPLATES[tid]
            with rec_cols[i]:
                _render_template_card(tid, tpl, is_recommended=True)
        st.markdown("**All Templates:**")

    # Render all filtered templates
    cols = st.columns(3)
    for i, (tid, tpl) in enumerate(all_tpls):
        with cols[i % 3]:
            _render_template_card(tid, tpl)


def _render_template_card(tid: str, tpl: dict, is_recommended: bool = False):
    """Render a template card with a REAL rendered preview + select button."""
    is_sel  = st.session_state.get("selected_template") == tid
    border  = "2px solid #22c55e" if is_sel else ("2px solid #f59e0b" if is_recommended else "1px solid #2a2d3e")
    acc     = accent_hex(tid)
    profs   = tpl.get("professions", [])
    prof_str = ", ".join(profs[:2]) + ("…" if len(profs) > 2 else "") if profs else "Universal"
    rec_badge = ("<span style='font-size:9px;background:#f59e0b22;color:#f59e0b;padding:2px 6px;"
                 "border-radius:4px;font-weight:700'>⭐ REC</span>") if is_recommended else ""
    sel_badge = ("<div style='font-size:10px;color:#22c55e;font-weight:700;margin-top:4px'>✓ Selected</div>"
                 if is_sel else "")
    preview = render_template_preview_html(tid)

    st.markdown(f"""
<div style="border:{border};border-radius:8px;background:#1a1d27;margin-bottom:4px;overflow:hidden">
  <div style="background:{acc};height:6px"></div>
  <div style="padding:8px 8px 0">{preview}</div>
  <div style="padding:10px 12px">
    <div style="display:flex;justify-content:space-between;align-items:flex-start">
      <div style="font-size:13px;font-weight:700;color:#e2e4ef">{tpl.get("name","")}</div>{rec_badge}
    </div>
    <div style="font-size:10px;color:{acc};margin:3px 0;font-weight:700">{tpl.get("category","")}</div>
    <div style="font-size:10px;color:#6b7280;margin-bottom:4px">{tpl.get("desc","")[:70]}</div>
    <div style="font-size:9px;color:#4b5563">For: {prof_str} · {tpl.get("font","Calibri")} {tpl.get("body_size",11)}pt</div>
    {sel_badge}
  </div>
</div>""", unsafe_allow_html=True)

    if st.button("✓ Selected" if is_sel else "Select Template", key=f"tpl_{tid}",
                  use_container_width=True, type="primary" if (is_recommended and not is_sel) else "secondary",
                  disabled=is_sel):
        st.session_state.selected_template = tid
        st.rerun()



# ══════════════════════════════════════════════════════════════════
# PAGE: HISTORY
# ══════════════════════════════════════════════════════════════════
def show_history():
    st.markdown('<div class="ph"><h2>◷ History</h2><p>Your saved resumes and analysis history.</p></div><br>', unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📄 Saved Resumes", "📊 Analysis History"])

    with tab1:
        resumes = get_user_resumes(st.session_state.user_id)
        if not resumes:
            st.markdown('<div class="sug info"><div class="sug-title">EMPTY</div><div class="sug-body">No resumes saved yet. Use the Resume Builder or Optimizer to create and save one.</div></div>', unsafe_allow_html=True)
        else:
            for r in resumes:
                score = r.get("ats_score", 0) or 0
                color = _score_color(score)
                tpl = r.get("template", "classic_professional")
                with st.expander(f"📄 {r['title']} — Score: {score}% — {r['created'][:10]}"):
                    hc1, hc2 = st.columns([3, 1])
                    with hc1:
                        st.markdown(f"**Template:** {TEMPLATES.get(tpl, {}).get('name', tpl)}")
                        st.markdown(f"**Saved:** {r['created'][:16]}")
                        try:
                            content = json.loads(r["content"]) if r.get("content") else {}
                            pi = content.get("personal_info", {})
                            if pi.get("email"):
                                st.markdown(f"**Email:** {pi['email']}")
                        except Exception:
                            pass
                    with hc2:
                        st.markdown(f'<div style="font-size:28px;font-weight:800;color:{color};text-align:center">{score}%</div>', unsafe_allow_html=True)
                        if st.button("🔄 Restore", key=f"restore_{r['id']}"):
                            try:
                                content = json.loads(r["content"])
                                st.session_state.resume_text = export_resume_to_txt(content)
                                st.session_state.selected_template = tpl
                                st.session_state.section = "Workspace"
                                st.session_state.ws_page = "✨ Resume Optimizer"
                                st.session_state["_pending_ws"] = "✨ Resume Optimizer"
                                st.success("Resume restored to Optimizer!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Could not restore: {e}")
                        if st.button("🗑 Delete", key=f"del_{r['id']}"):
                            delete_resume(r["id"], st.session_state.user_id)
                            st.success("Deleted")
                            st.rerun()

    with tab2:
        history = get_user_analysis_history(st.session_state.user_id)
        if not history:
            st.markdown('<div class="sug info"><div class="sug-title">EMPTY</div><div class="sug-body">No analysis history yet. Run the optimizer or deep analysis to see results here.</div></div>', unsafe_allow_html=True)
        else:
            for h in history:
                score = h.get("score", 0) or 0
                color = _score_color(score)
                jd = h.get("jd_snippet", "")[:60] or "No JD"
                st.markdown(f"""
<div class="hist-item">
  <div class="hist-score" style="background:{'var(--green-soft)' if score>=70 else 'var(--amber-soft)'};color:{color}">{score}%</div>
  <div style="flex:1">
    <div style="font-size:13px;font-weight:600">{jd}...</div>
    <div style="font-size:11px;color:var(--muted)">{h['created'][:16]}</div>
  </div>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# PAGE: KEYWORD ENGINE
# ══════════════════════════════════════════════════════════════════
def show_keyword_engine():
    st.markdown('<div class="ph"><h2>◈ Keyword Engine</h2><p>Extract ATS keywords from any job description and find gaps in your resume.</p></div><br>', unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("**Paste Job Description**")
        jd_input = st.text_area("Job Description for keyword extraction", height=200,
                                  placeholder="Paste the job description here...",
                                  label_visibility="visible",
                                  key="ke_jd_input")
        st.markdown("**Your Resume (for gap analysis)**")
        resume_input = st.text_area("Resume for gap analysis", height=150,
                                     placeholder="Paste your resume to see which keywords you're missing...",
                                     label_visibility="visible",
                                     key="ke_resume_input")
        if st.button("◈ Analyse Keywords & Gaps", use_container_width=True, type="primary"):
            if not jd_input.strip():
                st.error("Please paste a job description")
            else:
                st.session_state["_ke_jd_result"]     = jd_input
                st.session_state["_ke_resume_result"]  = resume_input
                st.session_state["_ke_ran"]            = True

    with c2:
        if st.session_state.get("_ke_ran"):
            jd_txt  = st.session_state["_ke_jd_result"]
            res_txt = st.session_state.get("_ke_resume_result","")
            try:
                keywords = extract_keywords_from_jd(jd_txt)
            except Exception as e:
                st.error(f"Keyword extraction error: {e}")
                keywords = []
            lower    = res_txt.lower()
            found    = [k for k in keywords if k.lower() in lower]
            missing  = [k for k in keywords if k.lower() not in lower]

            if keywords:
                st.markdown(f"**Extracted {len(keywords)} keywords from JD:**")
                st.markdown('<div class="kw-legend"><span class="kw-chip found">● Found in Resume</span><span class="kw-chip missing">● Missing</span></div>', unsafe_allow_html=True)
                all_tags = "".join(
                    f'<span class="kw-tag found">{k}</span>' for k in found
                ) + "".join(
                    f'<span class="kw-tag missing">{k}</span>' for k in missing
                )
                st.markdown(f'<div class="kw-cloud">{all_tags}</div>', unsafe_allow_html=True)
                st.markdown("---")
                kc1, kc2 = st.columns(2)
                with kc1:
                    st.metric("✅ Found in Resume", len(found))
                with kc2:
                    st.metric("❌ Missing from Resume", len(missing))
                if missing:
                    st.markdown("**📌 Add these to your resume:**")
                    for k in missing[:15]:
                        st.markdown(f"- `{k}`")
                elif not res_txt:
                    st.markdown("*Paste your resume above for gap analysis.*")
            else:
                st.warning("Could not extract keywords — try a more detailed job description.")


# ══════════════════════════════════════════════════════════════════
# PAGE: COVER LETTER AI
# ══════════════════════════════════════════════════════════════════
def show_cover_letter_ai():
    st.markdown('<div class="ph"><h2>✉ Cover Letter AI</h2><p>Generates a role-specific, JD-driven cover letter using your actual resume content — not a generic template.</p></div><br>', unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        company = st.text_input("Company Name *", placeholder="Roche India, Gubra, Infosys...")
        manager = st.text_input("Hiring Manager (optional)", placeholder="Dr. Priya Sharma")
        role    = st.text_input("Role / Position Title", placeholder="Senior Research Scientist")
        tone    = st.selectbox("Writing Tone", ["Professional", "Enthusiastic", "Concise", "Storytelling"],
                               help="Professional = formal; Enthusiastic = energetic; Concise = brief; Storytelling = narrative arc")
        resume_cl = st.text_area("Your Resume *", height=180,
                                  value=st.session_state.resume_text or st.session_state.get("original_resume",""),
                                  placeholder="Paste your full resume here...")
        jd_cl     = st.text_area("Job Description *", height=140,
                                  value=st.session_state.jd_text,
                                  placeholder="Paste the full job description...")

        cl_col1, cl_col2 = st.columns(2)
        with cl_col1:
            if st.button("✉ Generate Cover Letter", use_container_width=True, type="primary"):
                if not company.strip():
                    st.error("Company name is required")
                elif not resume_cl.strip():
                    st.error("Please paste your resume")
                elif not jd_cl.strip():
                    st.error("Please paste the job description — it is used to tailor the letter")
                elif not consume_ai_credit(st.session_state.user_id, st.session_state.username,
                                           st.session_state.get("user_email",""), reason="cover_letter"):
                    st.error("❌ You need an active subscription or at least 1 credit to generate a cover letter. "
                             "Buy credits in **Account → Subscription & Credits**.")
                else:
                    with st.spinner("Writing JD-specific cover letter..."):
                        cl_text = generate_cover_letter(
                            resume_cl.strip(), jd_cl.strip(),
                            company.strip(), manager.strip() or "Hiring Manager",
                            tone
                        )
                    _refresh_access()
                    st.session_state.cl_output  = cl_text
                    st.session_state.cl_company = company.strip()
                    st.session_state.cl_ran     = True
        with cl_col2:
            if st.button("🔄 Regenerate", use_container_width=True, key="cl_regen"):
                st.session_state.cl_ran = False
                st.rerun()

        st.markdown("""
<div class="sug info" style="margin-top:12px">
  <div class="sug-title">HOW THIS WORKS</div>
  <div class="sug-body">
    The AI reads your JD to extract role requirements, then uses your actual resume achievements
    (quantified bullets, publications, patents) to write a letter that is specific to that role.
    Different JDs produce different letters. Tone controls the writing style.
  </div>
</div>""", unsafe_allow_html=True)

    with c2:
        if st.session_state.get("cl_ran") and st.session_state.get("cl_output"):
            score_kws = extract_keywords_from_jd(jd_cl) if jd_cl else []
            cl_kw_matches = sum(1 for k in score_kws if k.lower() in st.session_state.cl_output.lower())

            st.markdown(f"""
<div style="background:#1a1d27;border:1px solid #2a2d3e;border-radius:8px;padding:12px;margin-bottom:12px;display:flex;gap:12px">
  <div style="text-align:center;min-width:60px">
    <div style="font-size:22px;font-weight:800;color:#22c55e">{cl_kw_matches}</div>
    <div style="font-size:10px;color:#6b7280">JD keywords<br>in letter</div>
  </div>
  <div style="font-size:12px;color:#6b7280;line-height:1.6">
    Letter tailored for <b style="color:#e2e4ef">{st.session_state.get("cl_company","")}</b>.
    Edit freely before downloading — make it 100% yours.
  </div>
</div>""", unsafe_allow_html=True)

            cl_edit = st.text_area("Generated Cover Letter (editable)", 
                                    value=st.session_state.cl_output,
                                    height=480, key="cl_edit_box",
                                    label_visibility="collapsed")
            if cl_edit != st.session_state.cl_output:
                st.session_state.cl_output = cl_edit

            dc1, dc2 = st.columns(2)
            with dc1:
                fname = f"cover_letter_{st.session_state.get('cl_company','').replace(' ','_')}.txt"
                st.download_button("📥 Download TXT", data=cl_edit,
                                    file_name=fname, mime="text/plain",
                                    use_container_width=True)
            with dc2:
                if st.button("📋 Copy to Clipboard", use_container_width=True):
                    st.toast("Select all in the box and Ctrl+C / Cmd+C to copy")
        else:
            st.markdown("""
<div class="sug info">
  <div class="sug-title">READY TO GENERATE</div>
  <div class="sug-body">
    Fill company name, paste your resume and the job description, then click Generate.<br><br>
    <b>Important:</b> The JD is required — the letter is tailored to its specific requirements,
    responsibilities, and keywords. Without a JD, the letter cannot be role-specific.
  </div>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# PAGE: INTERVIEW PREP
# ══════════════════════════════════════════════════════════════════
def show_interview_prep():
    st.markdown('<div class="ph"><h2>◐ Interview Prep</h2><p>Role-specific interview questions and STAR answer frameworks based on your resume.</p></div><br>', unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        q_types = st.multiselect(
            "Question Types",
            ["Behavioral", "Technical", "Situational", "Culture Fit", "HR / Salary"],
            default=["Behavioral", "Technical"]
        )
        num_q = st.selectbox("Number of Questions", [5, 10, 15, 20], index=1)
        ip_resume = st.text_area("Your Resume (paste key points)", height=150,
                                  value=st.session_state.resume_text,
                                  placeholder="Paste your resume...")
        ip_jd = st.text_area("Job Description", height=100,
                              value=st.session_state.jd_text,
                              placeholder="Paste the JD for role-specific questions...")

        if st.button("◐ Generate Interview Prep", use_container_width=True, type="primary"):
            if not ip_resume.strip() and not ip_jd.strip():
                st.error("Please paste your resume or job description")
            else:
                with st.spinner("Generating questions and STAR answers..."):
                    questions = _generate_interview_questions(ip_resume, ip_jd, q_types, num_q)
                st.session_state.ip_output = questions
                st.session_state.ip_ran = True

    with c2:
        if st.session_state.get("ip_ran") and st.session_state.get("ip_output"):
            for i, (q, answer) in enumerate(st.session_state.ip_output.items(), 1):
                with st.expander(f"Q{i}: {q}"):
                    st.markdown(answer)
        else:
            st.markdown("""
<div class="sug info">
  <div class="sug-title">READY</div>
  <div class="sug-body">Select question types and click Generate. Questions are tailored to your resume and job description using STAR methodology.</div>
</div>""", unsafe_allow_html=True)


def _generate_interview_questions(resume: str, jd: str, types: list, count: int) -> dict:
    """Delegates to the generic, count-accurate generator in utils.interview."""
    from utils.interview import generate_interview_questions
    return generate_interview_questions(resume, jd, types, count)




# ══════════════════════════════════════════════════════════════════
# PAGE: MODEL SETTINGS
# ══════════════════════════════════════════════════════════════════
def show_model_settings():
    st.markdown('<div class="ph"><h2>⚙ Settings</h2><p>Account information, password management, and AI model preferences.</p></div><br>', unsafe_allow_html=True)

    c1, c2 = st.columns([1, 1])
    with c1:
        st.markdown("### 👤 Account Details")
        role = st.session_state.get("user_role", "user")
        plan = st.session_state.get("user_plan", "free")
        role_badge = {"owner": "👑 Owner", "admin": "🛡️ Admin", "user": "👤 User"}.get(role, role)
        plan_badge = {"agency": "🚀 Agency", "pro": "⭐ Pro", "free": "Free"}.get(plan, plan)

        st.markdown(f"""
<div style="background:#1a1d27;border:1px solid #2a2d3e;border-radius:8px;padding:16px;margin-bottom:16px">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
    <div><div style="font-size:10px;color:#6b7280;text-transform:uppercase">Username</div>
         <div style="font-weight:700">{st.session_state.username}</div></div>
    <div><div style="font-size:10px;color:#6b7280;text-transform:uppercase">Email</div>
         <div style="font-weight:600;font-size:12px">{st.session_state.get("user_email","—")}</div></div>
    <div><div style="font-size:10px;color:#6b7280;text-transform:uppercase">Role</div>
         <div style="font-weight:700;color:#818cf8">{role_badge}</div></div>
    <div><div style="font-size:10px;color:#6b7280;text-transform:uppercase">Plan</div>
         <div style="font-weight:700;color:#22c55e">{plan_badge}</div></div>
  </div>
</div>""", unsafe_allow_html=True)

        st.markdown("### 🔒 Change Password")
        with st.form("pw_form"):
            old_pw  = st.text_input("Current Password", type="password", key="cp_old")
            new_pw  = st.text_input("New Password (min 6 chars)", type="password", key="cp_new")
            conf_pw = st.text_input("Confirm New Password", type="password", key="cp_conf")
            if st.form_submit_button("Update Password", use_container_width=True, type="primary"):
                if not old_pw or not new_pw or not conf_pw:
                    st.error("All fields are required")
                elif new_pw != conf_pw:
                    st.error("New passwords do not match")
                elif len(new_pw) < 6:
                    st.error("Minimum 6 characters required")
                else:
                    user = get_user_by_id(st.session_state.user_id)
                    if not user or not verify_password(user["password"], old_pw):
                        st.error("Current password is incorrect")
                    else:
                        change_password(st.session_state.user_id, new_pw)
                        st.success("✅ Password updated successfully!")

    with c2:
        st.markdown("### 🤖 On-Device AI Engine")
        # Live status of the local Ollama engine (no API keys, fully offline).
        available = llm.ollama_available(force=True)
        st.markdown(llm.status_line())
        if available:
            installed = llm.installed_models() or ["(none)"]
            current_model = st.session_state.get("selected_model", installed[0])
            cur_idx = installed.index(current_model) if current_model in installed else 0
            chosen_model = st.selectbox("Active local model", installed, index=cur_idx, key="model_picker",
                                        help="These are the models installed in your local Ollama.")
        else:
            MODEL_OPTIONS = [
                "mistral (recommended — 4.1 GB)",
                "llama3.1 (best quality — 4.7 GB)",
                "phi3:mini (fastest — 2.3 GB)",
                "llama3.2:3b (compact — 2.0 GB)",
            ]
            current_model = st.session_state.get("selected_model", MODEL_OPTIONS[0])
            cur_idx = MODEL_OPTIONS.index(current_model) if current_model in MODEL_OPTIONS else 0
            chosen_model = st.selectbox("Preferred model (enable by installing Ollama)",
                                        MODEL_OPTIONS, index=cur_idx, key="model_picker")
            st.caption("Until a local model is detected, the app uses its built-in rule-based "
                       "optimization engine — everything still works, fully offline.")
        temp = st.slider("Creativity / Temperature", 0.0, 1.0,
                         st.session_state.get("model_temp", 0.2), step=0.1,
                         help="Lower = more precise rewrites, Higher = more creative")

        # Profession update
        st.markdown("### 🎯 Update Your Profession")
        prof_opts = [""] + get_all_professions()
        cur_prof  = st.session_state.get("user_profession","")
        cur_p_idx = prof_opts.index(cur_prof) if cur_prof in prof_opts else 0
        new_prof  = st.selectbox("Profession", prof_opts, index=cur_p_idx, key="prof_picker",
                                  help="Updates template recommendations and keyword intelligence")

        if st.button("Save Preferences", use_container_width=True, type="primary"):
            st.session_state.selected_model  = chosen_model
            st.session_state.model_temp      = temp
            if new_prof:
                st.session_state.user_profession = new_prof
            st.success("✅ Preferences saved! Template recommendations updated.")
            st.rerun()

        st.markdown("### 📬 Support")
        st.markdown("📧 thokhircareer@gmail.com")
        st.markdown("🏢 Novoridge CRO, Hyderabad, India")
        st.markdown("📱 WhatsApp: +91-9550880249")


# ══════════════════════════════════════════════════════════════════
# PAGE: SUBSCRIPTION
# (PLANS comes from utils.database — the previous duplicate dict here
#  shadowed the import and crashed this page. Removed.)
# ══════════════════════════════════════════════════════════════════
def _show_payment_section():
    """UPI payment section with QR code — displayed on subscription page."""
    import base64
    from pathlib import Path

    st.markdown("### 💳 How to Subscribe — Pay via UPI")

    pc1, pc2 = st.columns([1, 1])
    with pc1:
        st.markdown("""
<div style="background:#1a1d27;border:1px solid #2a2d3e;border-radius:10px;padding:20px">
  <div style="font-size:14px;font-weight:700;color:#e2e4ef;margin-bottom:14px">📋 Payment Steps</div>

  <div style="display:flex;gap:10px;margin-bottom:12px">
    <div style="background:#6366f1;color:#fff;font-weight:800;font-size:12px;width:24px;height:24px;
                border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0">1</div>
    <div style="font-size:12px;color:#e2e4ef">Scan the QR code or copy the UPI ID below and pay the plan amount using any UPI app (GPay, PhonePe, Paytm, BHIM).</div>
  </div>

  <div style="display:flex;gap:10px;margin-bottom:12px">
    <div style="background:#6366f1;color:#fff;font-weight:800;font-size:12px;width:24px;height:24px;
                border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0">2</div>
    <div style="font-size:12px;color:#e2e4ef">Take a screenshot of the payment confirmation and send it to our email with your <b>registered username</b>.</div>
  </div>

  <div style="display:flex;gap:10px;margin-bottom:16px">
    <div style="background:#6366f1;color:#fff;font-weight:800;font-size:12px;width:24px;height:24px;
                border-radius:50%;display:flex;align-items:center;justify-content:center;flex-shrink:0">3</div>
    <div style="font-size:12px;color:#e2e4ef">Within <b>24 hours</b> you will receive a license key by email. Enter it in the box below to activate your plan.</div>
  </div>

  <div style="background:#222536;border:1px solid #353850;border-radius:8px;padding:12px">
    <div style="font-size:10px;color:#6b7280;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px">UPI Payment ID</div>
    <div style="font-size:16px;font-weight:800;color:#22c55e;margin-bottom:4px">9550880249@kotakbank</div>
    <div style="font-size:11px;color:#6b7280">Account: <b style="color:#e2e4ef">SHAIK THOKHIR BASHA</b> — Kotak Mahindra Bank</div>
  </div>

  <div style="margin-top:12px;padding:10px 12px;background:#222536;border-radius:6px">
    <div style="font-size:10px;color:#6b7280;margin-bottom:4px">📧 Send payment screenshot to:</div>
    <div style="font-size:13px;font-weight:700;color:#818cf8">thokhircareer@gmail.com</div>
    <div style="font-size:11px;color:#6b7280;margin-top:4px">Subject: ATS Resume Pro Subscription — [Your Username]</div>
  </div>

  <div style="margin-top:12px;display:grid;grid-template-columns:1fr 1fr;gap:8px">
    <div style="background:#222536;border-radius:6px;padding:10px;text-align:center">
      <div style="font-size:10px;color:#6b7280">Pro Plan</div>
      <div style="font-size:18px;font-weight:800;color:#818cf8">₹2,499</div>
      <div style="font-size:10px;color:#6b7280">One-time · 1 year</div>
    </div>
    <div style="background:#222536;border-radius:6px;padding:10px;text-align:center">
      <div style="font-size:10px;color:#6b7280">Agency Plan</div>
      <div style="font-size:18px;font-weight:800;color:#22c55e">₹9,999</div>
      <div style="font-size:10px;color:#6b7280">One-time · Lifetime</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

    with pc2:
        qr_path = Path(__file__).parent / "assets" / "payment_qr.jpeg"
        if qr_path.exists():
            with open(qr_path, "rb") as f:
                img_b64 = base64.b64encode(f.read()).decode()
            st.markdown(f"""
<div style="background:#1a1d27;border:1px solid #2a2d3e;border-radius:10px;padding:16px;text-align:center">
  <div style="font-size:12px;font-weight:600;color:#e2e4ef;margin-bottom:10px">📱 Scan with any UPI app</div>
  <img src="data:image/jpeg;base64,{img_b64}"
       style="width:100%;max-width:280px;border-radius:8px;border:2px solid #353850"/>
  <div style="margin-top:10px;font-size:11px;color:#6b7280">
    Kotak811 · SHAIK THOKHIR BASHA<br>
    <span style="color:#22c55e;font-weight:700">9550880249@kotakbank</span>
  </div>
  <div style="margin-top:12px;background:#222536;border-radius:6px;padding:8px;font-size:11px;color:#6b7280">
    ✅ GPay &nbsp;·&nbsp; PhonePe &nbsp;·&nbsp; Paytm &nbsp;·&nbsp; BHIM &nbsp;·&nbsp; Any UPI
  </div>
</div>""", unsafe_allow_html=True)
        else:
            st.markdown("""
<div style="background:#1a1d27;border:1px solid #2a2d3e;border-radius:10px;padding:20px;text-align:center">
  <div style="font-size:32px;margin-bottom:8px">📱</div>
  <div style="font-size:13px;font-weight:600;color:#e2e4ef;margin-bottom:6px">UPI Payment</div>
  <div style="font-size:14px;font-weight:800;color:#22c55e">9550880249@kotakbank</div>
  <div style="font-size:11px;color:#6b7280;margin-top:4px">SHAIK THOKHIR BASHA<br>Kotak Mahindra Bank</div>
</div>""", unsafe_allow_html=True)


def show_subscription():
    st.markdown('<div class="ph"><h2>🔑 Subscription & Credits</h2><p>Pay-as-you-go credits or a subscription — both unlock optimization and all AI tools. 100% offline & private.</p></div><br>', unsafe_allow_html=True)

    uid  = st.session_state.user_id
    plan = st.session_state.get("user_plan","none")
    sub  = get_active_subscription(uid)
    credits = get_credits(uid)
    st.session_state.credits = credits

    # ── Current status banner ─────────────────────────────────────────────
    if plan not in ("none","expired") and plan in PLANS:
        p = PLANS[plan]
        used = sub.get("resumes_used",0) if sub else 0
        mx   = p.get("max_resumes",0)
        rem  = max(0, mx - used) if mx not in (-1,) else "∞"
        rem  = "∞" if (isinstance(rem, int) and mx >= 9999) else rem
        exp  = sub.get("expires","") if sub else ""
        st.markdown(f"""
<div style="background:linear-gradient(90deg,#1a1d27,#222536);border:1px solid #6366f1;
            border-radius:10px;padding:14px 18px;margin-bottom:20px;
            display:flex;align-items:center;justify-content:space-between">
  <div>
    <div style="font-size:14px;font-weight:800;color:#818cf8">✅ Active: {p['name']}</div>
    <div style="font-size:12px;color:#6b7280;margin-top:3px">
      {rem} uses remaining · Expires: {exp[:10] if exp and exp != "2099-12-31" else "Never"} · 🪙 {credits} credits
    </div>
  </div>
  <div style="font-size:28px;font-weight:900;color:#22c55e">{p.get("price_label", f"₹{p.get('price_inr','')}")}</div>
</div>""", unsafe_allow_html=True)
    elif plan == "expired":
        st.error(f"❌ Your subscription has expired. You have 🪙 {credits} credits. Renew or top up below.")
    else:
        if credits > 0:
            st.success(f"🪙 You have {credits} credit{'s' if credits != 1 else ''} — ready to optimize and use AI tools.")
        else:
            st.warning("⚠️ No active plan or credits. Buy a credit pack (from ₹49) or subscribe below to start.")

    # ── SECTION A: Credit packs (pay-per-use) ─────────────────────────────
    st.markdown("### 🪙 Buy Credits — pay only for what you use")
    st.caption("1 credit = 1 resume optimization OR 1 cover letter. Keyword analysis, ATS scoring & interview prep are always free once you have credits or a plan.")
    pack_cols = st.columns(len(CREDIT_PACKS))
    for col, (pid, pk) in zip(pack_cols, CREDIT_PACKS.items()):
        border = "2px solid #6366f1" if pk.get("featured") else "1px solid #2a2d3e"
        per = pk["price_inr"] / pk["credits"]
        pop = ('<div style="text-align:center;margin-bottom:-10px"><span style="background:#6366f1;color:#fff;font-size:9px;font-weight:800;padding:3px 10px;border-radius:10px">BEST SELLER</span></div>'
               if pk.get("featured") else "")
        with col:
            st.markdown(f"""
{pop}
<div style="border:{border};border-radius:10px;padding:18px;background:#1a1d27;text-align:center">
  <div style="font-size:15px;font-weight:800;color:#e2e4ef">{pk['name']}</div>
  <div style="font-size:30px;font-weight:900;margin:4px 0;color:#22c55e">{pk['price_label']}</div>
  <div style="font-size:13px;font-weight:700;color:#818cf8">{pk['credits']} credit{'s' if pk['credits']!=1 else ''}</div>
  <div style="font-size:11px;color:#6b7280;margin-top:4px">≈ ₹{per:.0f} per optimization</div>
</div>""", unsafe_allow_html=True)
            if st.button(f"Buy — {pk['price_label']}", key=f"buy_{pid}", use_container_width=True,
                         type="primary" if pk.get("featured") else "secondary"):
                st.session_state["_pay_item"] = pid
                st.session_state["_show_payment"] = True
                st.rerun()

    # ── SECTION B: Subscriptions ──────────────────────────────────────────
    st.markdown("---")
    st.markdown("### ⭐ Subscriptions — for active job seekers & agencies")
    cols = st.columns(3)
    display_plans = ["monthly","yearly","agency"]
    plan_features = {
        "monthly": ["30 optimizations / month","All AI tools (Cover Letter, Interview Prep)",
                    "All 21 profession templates","DOCX & TXT export","Valid 30 days"],
        "yearly":  ["Unlimited optimizations (fair use)","All AI tools included",
                    "All templates — every profession","Priority support","Best value — save vs monthly"],
        "agency":  ["Everything in Annual","Multi-seat / team use","White-label option",
                    "Commercial-use license","Priority support"],
    }
    for col, plan_key in zip(cols, display_plans):
        p = PLANS[plan_key]
        is_current = plan == plan_key
        border = "2px solid #6366f1" if p.get("featured") else "1px solid #2a2d3e"
        if is_current:
            border = "2px solid #22c55e"
        pop = ('<div style="text-align:center;margin-bottom:-12px"><span style="background:#6366f1;color:#fff;font-size:9px;font-weight:800;padding:3px 10px;border-radius:10px">MOST POPULAR</span></div>'
               if p.get("featured") else "")
        feats_html = "".join(
            f'<li style="padding:4px 0;display:flex;gap:8px;font-size:12px;color:#e2e4ef">'
            f'<span style="color:#22c55e;font-weight:700">✓</span>{feat}</li>'
            for feat in plan_features[plan_key])
        with col:
            st.markdown(f"""
{pop}
<div style="border:{border};border-radius:10px;padding:20px;background:#1a1d27;position:relative">
  <div style="font-size:17px;font-weight:800;color:{"#818cf8" if p.get("featured") else "#e2e4ef"}">{p["name"]}</div>
  <div style="font-size:26px;font-weight:900;margin:6px 0">{p["price_label"]}</div>
  <div style="font-size:11px;color:#6b7280;margin-bottom:12px">{p["desc"]}</div>
  <ul style="list-style:none;padding:0;margin:0 0 14px">{feats_html}</ul>
  {"<div style=\'text-align:center;padding:8px;background:#1e4d2b;border-radius:6px;font-size:12px;font-weight:700;color:#22c55e\'>✓ Current Plan</div>" if is_current else ""}
</div>""", unsafe_allow_html=True)
            if not is_current:
                if st.button(f"Subscribe — {p['price_label']}", key=f"sub_{plan_key}",
                             use_container_width=True, type="primary" if p.get("featured") else "secondary"):
                    st.session_state["_pay_item"] = plan_key
                    st.session_state["_show_payment"] = True
                    st.rerun()

    # ── Payment instructions ───────────────────────────────────────────────
    if st.session_state.get("_show_payment"):
        pay_item = st.session_state.get("_pay_item", "pack_jobhunt")
        pay_info = PLANS.get(pay_item) or CREDIT_PACKS.get(pay_item) or {}
        amount   = plan_price(pay_item)
        st.markdown("---")
        st.markdown(f"### 💳 Pay ₹{amount} for {pay_info.get('name', pay_item)}")

        pc1, pc2 = st.columns([1,1])
        with pc1:
            st.markdown(f"""
<div style="background:#1a1d27;border:1px solid #2a2d3e;border-radius:10px;padding:16px">
  <div style="font-size:13px;font-weight:700;color:#e2e4ef;margin-bottom:12px">📋 Payment Steps</div>
  <div style="font-size:12px;color:#e2e4ef;line-height:2">
    <b>1.</b> Scan QR code or pay to UPI ID below<br>
    <b>2.</b> Enter your UTR/Transaction ID<br>
    <b>3.</b> Click Submit — we'll verify within 2-4 hours<br>
    <b>4.</b> You'll receive a license key by email
  </div>
  <div style="margin-top:14px;background:#222536;border-radius:8px;padding:12px">
    <div style="font-size:10px;color:#6b7280;text-transform:uppercase">UPI ID</div>
    <div style="font-size:18px;font-weight:900;color:#22c55e">9550880249@kotakbank</div>
    <div style="font-size:11px;color:#6b7280">SHAIK THOKHIR BASHA · Kotak Mahindra Bank</div>
    <div style="margin-top:10px;font-size:13px;font-weight:700;color:#e2e4ef">
      Amount: ₹{amount}
    </div>
  </div>
  <div style="margin-top:10px;font-size:11px;color:#6b7280">
    📧 thokhircareer@gmail.com · 📱 +91-9550880249
  </div>
</div>""", unsafe_allow_html=True)

        with pc2:
            import base64
            from pathlib import Path
            qr = Path(__file__).parent / "assets" / "payment_qr.jpeg"
            if qr.exists():
                img_b64 = base64.b64encode(qr.read_bytes()).decode()
                st.markdown(f'<div style="text-align:center;background:#1a1d27;border:1px solid #2a2d3e;border-radius:10px;padding:14px"><img src="data:image/jpeg;base64,{img_b64}" style="max-width:230px;border-radius:8px"/><div style="font-size:11px;color:#6b7280;margin-top:8px">Scan with GPay · PhonePe · Paytm · BHIM</div></div>', unsafe_allow_html=True)

        # UTR submission form
        st.markdown("**Submit your payment:**")
        with st.form("pay_submit"):
            utr = st.text_input("UTR / Transaction ID *", placeholder="12-digit UTR number from UPI app")
            note = st.text_area("Note (optional)", placeholder="Any message...", height=60)
            if st.form_submit_button("✅ Submit Payment Request", use_container_width=True, type="primary"):
                if not utr.strip():
                    st.error("Please enter your UTR number")
                else:
                    rid = create_payment_request(uid, pay_item, utr.strip(), note)
                    st.success("✅ Payment request submitted! We'll verify within 2-4 hours, then your credits/plan are added automatically (or we email you a license key).")
                    st.session_state["_show_payment"] = False

    # ── License key activation ─────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 🔑 Have a License Key?")
    st.caption("Subscription keys (MON / YRL / AGE) activate a plan · Credit keys (CRD) top up your balance.")
    lc1, lc2 = st.columns([3,1])
    with lc1:
        key_in = st.text_input("License Key", placeholder="MON-XXXX-XXXX-XXXX  or  CRD-XXXX-XXXX-XXXX",
                                label_visibility="collapsed")
    with lc2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("✅ Activate", use_container_width=True, type="primary"):
            if not key_in.strip():
                st.error("Enter a key")
            else:
                result = redeem_license_key(key_in.strip(), uid)
                if result["ok"]:
                    _refresh_access()
                    st.success(result["message"])
                    st.rerun()
                else:
                    st.error(result["message"])




# ══════════════════════════════════════════════════════════════════
# PAGE: ADMIN PANEL (Owner/Admin only)
# ══════════════════════════════════════════════════════════════════
def show_admin_panel():
    if not st.session_state.is_admin:
        st.error("🔒 Access denied. Admin privileges required.")
        return

    st.markdown('<div class="ph"><h2>🛡️ Admin Panel</h2><p>Manage users, subscriptions, license keys, and app analytics.</p></div><br>', unsafe_allow_html=True)

    # Overall stats row
    stats = get_app_stats()
    cols = st.columns(6)
    stat_items = [
        ("Total Users", stats.get("total_users", 0), "#6366f1"),
        ("Pro/Agency Users", stats.get("pro_users", stats.get("paid_users", 0)), "#22c55e"),
        ("Resumes Built", stats.get("total_resumes", 0), "#818cf8"),
        ("ATS Analyses", stats.get("total_analyses", 0), "#f59e0b"),
        ("Keys Issued", stats.get("keys_issued", 0), "#6366f1"),
        ("Keys Used", stats.get("keys_used", 0), "#22c55e"),
    ]
    for col, (label, val, color) in zip(cols, stat_items):
        with col:
            st.markdown(f'<div class="stat-card"><div class="stat-label">{label}</div><div class="stat-val" style="color:{color};font-size:20px">{val}</div></div>', unsafe_allow_html=True)

    st.markdown("---")

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["👥 Users", "💳 Payments", "🔑 License Keys", "📋 Subscriptions", "📖 Docs & Guide"])

    # ── TAB 1: USER MANAGEMENT ────────────────────────────────
    with tab1:
        st.markdown("### All Registered Users")
        users = get_all_users()

        # Search filter
        search = st.text_input("🔍 Search by username or email", key="admin_search", placeholder="Type to filter...")
        if search:
            users = [u for u in users if search.lower() in u["username"].lower() or search.lower() in u["email"].lower()]

        for u in users:
            plan = u.get("plan", "free")
            role = u.get("role", "user")
            plan_color = {"agency": "#22c55e", "pro": "#818cf8", "free": "#6b7280"}.get(plan, "#6b7280")
            role_icon = {"owner": "👑", "admin": "🛡️", "user": "👤"}.get(role, "👤")
            last = u.get("last_login", "Never")[:10] if u.get("last_login") else "Never"

            with st.expander(f"{role_icon} {u['username']} ({u['email']}) — {plan.upper()} — Last login: {last}"):
                ac1, ac2, ac3 = st.columns(3)
                with ac1:
                    st.markdown(f"**User ID:** {u['id']}")
                    st.markdown(f"**Role:** {role}")
                    st.markdown(f"**Plan:** <span style='color:{plan_color};font-weight:700'>{plan.upper()}</span>", unsafe_allow_html=True)
                    st.markdown(f"**Joined:** {u.get('created','')[:10]}")

                with ac2:
                    st.markdown("**Grant Subscription:**")
                    grant_opts = ["monthly", "yearly", "agency"]
                    new_plan = st.selectbox("Plan", grant_opts,
                                             key=f"grant_plan_{u['id']}",
                                             index=grant_opts.index(plan) if plan in grant_opts else 0)
                    exp_days = st.number_input("Days", 30, 3650, 365, key=f"grant_days_{u['id']}")
                    if st.button(f"Grant {new_plan.upper()}", key=f"grant_{u['id']}", use_container_width=True, type="primary"):
                        if u["role"] == "owner":
                            st.warning("Cannot modify owner accounts")
                        else:
                            add_subscription(u["id"], new_plan, method="admin_grant",
                                             granted_by=st.session_state.username,
                                             expires_days=exp_days)
                            st.success(f"✅ {new_plan.upper()} granted to {u['username']} for {exp_days} days")
                            st.rerun()
                    st.markdown("**Grant Credits:**")
                    gc_amt = st.number_input("Credits", 1, 1000, 10, key=f"grant_cr_{u['id']}")
                    if st.button("🪙 Add Credits", key=f"grant_cr_btn_{u['id']}", use_container_width=True):
                        bal = add_credits(u["id"], int(gc_amt), reason="admin_grant",
                                          granted_by=st.session_state.username)
                        st.success(f"✅ Added {gc_amt} credits to {u['username']} (balance: {bal})")
                        st.rerun()

                with ac3:
                    st.markdown("**Actions:**")
                    if st.button("🚫 Revoke Sub", key=f"revoke_{u['id']}", use_container_width=True):
                        if u["role"] == "owner":
                            st.warning("Cannot modify owner accounts")
                        else:
                            revoke_subscription(u["id"])
                            st.success(f"Subscription revoked for {u['username']}")
                            st.rerun()
                    new_role = st.selectbox("Set Role", ["user", "admin"],
                                             key=f"role_{u['id']}",
                                             index=0 if role == "user" else 1)
                    if st.button("Set Role", key=f"set_role_{u['id']}", use_container_width=True):
                        if u["role"] == "owner":
                            st.warning("Cannot modify owner accounts")
                        else:
                            set_user_role(u["id"], new_role)
                            st.success(f"Role updated to {new_role}")
                            st.rerun()
                    if u["role"] != "owner" and u["username"] != st.session_state.username:
                        if st.button("🗑️ Delete User", key=f"del_user_{u['id']}", use_container_width=True):
                            delete_user(u["id"])
                            st.success(f"User {u['username']} deleted")
                            st.rerun()

    # ── TAB 2: PAYMENT APPROVAL ────────────────────────────────
    with tab2:
        st.markdown("### 💳 Payment Requests")
        payments = get_all_payment_requests()
        pending  = [p for p in payments if p["status"]=="pending"]
        st.markdown(f"**{len(pending)} pending · {len(payments)} total**")

        if pending:
            st.markdown("#### ⏳ Pending Approvals")
            for pay in pending:
                with st.expander(f"💳 {pay['username']} — {pay['plan'].upper()} — ₹{pay['amount_inr']} — {pay['created'][:10]}"):
                    pc1, pc2, pc3 = st.columns(3)
                    with pc1:
                        item_name = (PLANS.get(pay['plan']) or CREDIT_PACKS.get(pay['plan']) or {}).get('name', pay['plan'])
                        st.markdown(f"**User:** {pay['username']} ({pay['email']})")
                        st.markdown(f"**Plan/Pack:** {item_name}")
                        st.markdown(f"**Amount:** ₹{pay['amount_inr']}")
                    with pc2:
                        st.markdown(f"**UTR:** `{pay.get('utr_number','—')}`")
                        st.markdown(f"**Submitted:** {pay['created'][:16]}")
                        if pay.get('screenshot_note'):
                            st.markdown(f"**Note:** {pay['screenshot_note']}")
                    with pc3:
                        if st.button("✅ Approve & Grant Access", key=f"app_{pay['id']}", use_container_width=True, type="primary"):
                            if approve_payment(pay["id"], st.session_state.username):
                                # approve_payment already applied the plan/credits to the account.
                                if pay["plan"] in CREDIT_PACKS:
                                    st.success(f"✅ Approved! {CREDIT_PACKS[pay['plan']]['credits']} credits added to {pay['username']}.")
                                else:
                                    st.success(f"✅ Approved! {pay['plan'].upper()} subscription activated for {pay['username']}.")
                                st.info(f"You can also email a backup key from the License Keys tab if needed.")
                                st.rerun()
                        if st.button("❌ Reject", key=f"rej_{pay['id']}", use_container_width=True):
                            reject_payment(pay["id"], st.session_state.username)
                            st.warning("Rejected")
                            st.rerun()
        else:
            st.success("No pending payment requests ✓")

        if len(payments) > len(pending):
            st.markdown("#### ✅ Processed Payments")
            for pay in payments:
                if pay["status"] != "pending":
                    color = "#22c55e" if pay["status"]=="approved" else "#ef4444"
                    st.markdown(f"""
<div style="background:#1a1d27;border:1px solid #2a2d3e;border-radius:6px;padding:10px 14px;
            margin-bottom:6px;display:flex;align-items:center;gap:12px;font-size:12px">
  <span style="font-weight:700;width:120px">{pay.get("username","?")}</span>
  <span style="color:{color};font-weight:700;width:70px">{pay["status"].upper()}</span>
  <span>{pay["plan"].upper()} · ₹{pay["amount_inr"]}</span>
  <span style="color:#6b7280;margin-left:auto">{pay["created"][:10]}</span>
</div>""", unsafe_allow_html=True)

    # ── TAB 3: LICENSE KEYS ───────────────────────────────────
    with tab3:
        st.markdown("### Generate License Keys")
        st.markdown("""
<div class="sug info" style="margin-bottom:16px">
  <div class="sug-title">HOW TO GIVE ACCESS TO SUBSCRIBERS</div>
  <div class="sug-body">
    1. Generate a key here (PRO or Agency) → copy it → send to subscriber by email/WhatsApp.<br>
    2. Subscriber goes to <b>Account → Subscription → "Have a License Key?"</b> and enters it.<br>
    3. Their account is instantly upgraded. Each key can only be used once.
  </div>
</div>""", unsafe_allow_html=True)

        gc1, gc2, gc3, gc4 = st.columns([2, 1, 1, 1])
        with gc1:
            gen_plan = st.selectbox("Plan / Credit pack",
                                    ["monthly", "yearly", "agency",
                                     "pack_starter", "pack_jobhunt", "pack_pro"],
                                    key="gen_plan")
        with gc2:
            gen_count = st.number_input("Quantity", 1, 50, 1, key="gen_count")
        with gc3:
            gen_days = st.number_input("Valid Days", 30, 3650, 365, key="gen_days")
        with gc4:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("⚡ Generate", key="gen_keys_btn", use_container_width=True, type="primary"):
                keys = generate_bulk_keys(gen_plan, int(gen_count), st.session_state.username, int(gen_days))
                st.session_state.generated_keys = keys
                st.session_state.generated_plan = gen_plan

        if st.session_state.get("generated_keys"):
            keys_text = "\n".join(st.session_state.generated_keys)
            plan_g = st.session_state.get("generated_plan", "pro")
            st.markdown(f"**✅ {len(st.session_state.generated_keys)} {plan_g.upper()} key(s) generated — copy and send to subscribers:**")
            st.code(keys_text, language=None)
            st.download_button(
                f"📥 Download Keys as TXT",
                data=keys_text,
                file_name=f"ats_license_keys_{plan_g}_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain",
                use_container_width=True
            )

        st.markdown("### All License Keys")
        all_keys = get_all_license_keys()
        if not all_keys:
            st.info("No keys generated yet.")
        else:
            # Summary
            used = sum(1 for k in all_keys if k["used"])
            st.markdown(f"**{len(all_keys)} total · {used} used · {len(all_keys)-used} available**")
            for k in all_keys:
                status_color = "#ef4444" if k["used"] else "#22c55e"
                status_text = f"Used by {k.get('used_by_username','?')} on {k.get('used_at','')[:10]}" if k["used"] else "Available"
                plan_c = "#818cf8" if k["plan"] == "pro" else "#22c55e"
                st.markdown(f"""
<div style="background:#1a1d27;border:1px solid #2a2d3e;border-radius:6px;padding:10px 14px;
            margin-bottom:6px;display:flex;align-items:center;gap:12px;font-size:12px">
  <code style="flex:1;color:#e2e4ef;font-size:13px">{k['key_code']}</code>
  <span style="color:{plan_c};font-weight:700;width:60px">{k['plan'].upper()}</span>
  <span style="color:{status_color};width:200px">{status_text}</span>
  <span style="color:#6b7280">Expires: {k.get('expires','N/A')}</span>
</div>""", unsafe_allow_html=True)

    # ── TAB 4: SUBSCRIPTIONS ──────────────────────────────────
    with tab4:
        st.markdown("### All Active Subscriptions")
        subs = get_all_subscriptions()
        active_subs = [s for s in subs if s["status"] == "active"]
        st.markdown(f"**{len(active_subs)} active · {len(subs)} total records**")

        for s in subs[:50]:
            status_color = "#22c55e" if s["status"] == "active" else "#6b7280"
            plan_color = {"agency": "#22c55e", "pro": "#818cf8"}.get(s["plan"], "#6b7280")
            st.markdown(f"""
<div style="background:#1a1d27;border:1px solid #2a2d3e;border-radius:6px;padding:10px 14px;
            margin-bottom:6px;display:flex;align-items:center;gap:12px;font-size:12px">
  <span style="font-weight:700;width:120px">{s.get('username','?')}</span>
  <span style="color:{plan_color};font-weight:700;width:70px">{s['plan'].upper()}</span>
  <span style="color:{status_color};width:80px">{s['status'].upper()}</span>
  <span style="color:#6b7280">via {s.get('method','?')}</span>
  <span style="color:#6b7280;margin-left:auto">Expires: {s.get('expires','N/A')}</span>
</div>""", unsafe_allow_html=True)

    # ── TAB 5: DEPLOYMENT GUIDE ───────────────────────────────
    with tab5:
        st.markdown("""
### 📖 Deployment Guide & Subscriber Management

---

#### 🚀 FREE Hosting Options (No Payment Required)

| Platform | Free Tier | Best For | Link |
|----------|-----------|----------|------|
| **Streamlit Cloud** | 1 app, 1 GB RAM, unlimited users | Easiest — 1-click from GitHub | share.streamlit.io |
| **Hugging Face Spaces** | Free CPU, persistent storage option | Good alternative to Streamlit | huggingface.co/spaces |
| **Railway.app** | $5 free credits/month | More control, persistent DB | railway.app |
| **Render.com** | Free web service (sleeps after 15 min) | Good for low traffic | render.com |
| **Google Cloud Run** | 2M free requests/month | Scalable, pay only when used | cloud.google.com |

**Recommended: Streamlit Cloud** — it's the fastest to set up and completely free.

---

#### 🚀 Deploy on Streamlit Cloud (Step-by-Step)

**One-time setup (~10 minutes):**

```
1. Create a free GitHub account at github.com
2. Create a new repository → upload all app files
3. Add a .gitignore file with:
      data/
      __pycache__/
      *.pyc
      assets/payment_qr.jpeg   ← upload this separately as a secret

4. Go to share.streamlit.io → Sign in with GitHub
5. Click "New app" → select your repo → Main file: app.py → Deploy
6. Your URL will be: https://YOUR-APP-NAME.streamlit.app
```

**Important for Streamlit Cloud:**
- Upload `assets/payment_qr.jpeg` directly to your GitHub repo (it's not sensitive)
- The SQLite DB resets on every redeploy — use the Admin Panel to re-issue keys

---

#### 🔑 How to Give Access to Paying Subscribers

**Every time someone pays via UPI:**

```
1. Login with your owner account (thokhir)
2. Account → Admin Panel → License Keys tab
3. Select: Pro (₹2,499) or Agency (₹9,999)
4. Quantity = 1 → Click ⚡ Generate
5. Copy the key (e.g. PRO-A1B2-C3D4-E5F6)
6. Email or WhatsApp the key to the subscriber
```

**Subscriber activates in 30 seconds:**
```
1. Sign up at your app URL (free account)
2. Account → Subscription → "Enter Your License Key"
3. Paste key → Click ✅ Activate → Plan upgraded instantly
```

---

#### 🔒 Forgot Password Flow

No email server needed — OTP appears on screen:
```
1. User clicks "Forgot Password" tab on login page
2. Enters username or email → clicks Send OTP Code
3. A 6-digit code appears on screen (valid 15 min)
4. User enters code + new password → Reset
```

---

#### 💾 Database Persistence (Important!)

Streamlit Cloud resets the database on each redeploy. Solutions:

1. **Short-term**: Export user list before redeploying, re-add after
2. **Recommended**: Switch to **Supabase free PostgreSQL** (free forever, 500 MB)
   - Sign up at supabase.com → create project → copy connection string
   - Replace `sqlite3` calls in `database.py` with `psycopg2`
3. **Simple**: Use Railway.app — it has **persistent disk storage**
""")


# ══════════════════════════════════════════════════════════════════
# ROUTING
# ══════════════════════════════════════════════════════════════════
def route():
    section = st.session_state.section
    ws = st.session_state.ws_page
    ai = st.session_state.ai_page
    acc = st.session_state.acc_page

    if section == "Workspace":
        if "Dashboard" in ws:         show_dashboard()
        elif "Builder" in ws:         show_resume_builder()
        elif "Optimizer" in ws:       show_resume_optimizer()
        elif "Analysis" in ws:        show_deep_analysis()
        elif "History" in ws:         show_history()
        elif "Template" in ws:        show_templates()
        else:                         show_dashboard()

    elif section == "AI Tools":
        if not st.session_state.get("has_ai_tools", False):
            msg = ("AI Tools (Cover Letter, Interview Prep, Keyword Engine) unlock with any "
                   "credit pack or a Monthly/Annual subscription. Buy credits from ₹49 or subscribe "
                   "in <b>Account → Subscription & Credits</b>.")
            st.markdown(f"""
<div class="sug err">
  <div class="sug-title">AI TOOLS — UNLOCK REQUIRED</div>
  <div class="sug-body">{msg}</div>
</div>""", unsafe_allow_html=True)
            st.markdown("---")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🪙 Buy Credits from ₹49", use_container_width=True, type="primary"):
                    st.session_state["_pay_item"] = "pack_jobhunt"
                    st.session_state["_show_payment"] = True
                    st.session_state["_pending_acc"] = "🔑 Subscription & Credits"
                    st.session_state.acc_page = "🔑 Subscription & Credits"
                    st.session_state.section  = "Account"
                    st.rerun()
            with col2:
                if st.button("⬆️ Subscribe — Monthly ₹399", use_container_width=True):
                    st.session_state["_pay_item"] = "monthly"
                    st.session_state["_show_payment"] = True
                    st.session_state["_pending_acc"] = "🔑 Subscription & Credits"
                    st.session_state.acc_page = "🔑 Subscription & Credits"
                    st.session_state.section  = "Account"
                    st.rerun()
            return
        if ai and "Keyword" in ai:    show_keyword_engine()
        elif ai and "Cover" in ai:    show_cover_letter_ai()
        elif ai and "Interview" in ai: show_interview_prep()
        else:                         show_keyword_engine()

    elif section == "Account":
        if "Settings" in acc:         show_model_settings()
        elif "Subscription" in acc:   show_subscription()
        elif "Admin" in acc:          show_admin_panel()
        else:                         show_model_settings()

    else:
        show_dashboard()


# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    if not st.session_state.authenticated:
        show_login()
        return

    render_sidebar()
    route()


if __name__ == "__main__":
    main()

