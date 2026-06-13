# CVIQ — ATS Resume Maker Pro

100% offline, privacy-first ATS resume optimizer, builder, keyword engine, cover-letter writer and interview-prep tool. No API keys, no cloud — optionally powered by a **local** LLM (Ollama).

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
# open http://localhost:8501   ·   owner login: thokhir / Admin@800822
```

### (Optional) Enable on-device AI

The app runs fully on a rule-based engine out of the box. To turn on real AI rewriting — still 100% offline, no API key:

```bash
# install Ollama from https://ollama.com, then:
ollama pull mistral      # or llama3.1 / phi3:mini / llama3.2:3b
```

When Ollama is running, the cover-letter writer and summary optimizer use it automatically; the live status shows in **Account → Settings**. If it's not running, the built-in engine is used instead.

## Monetization — credits + subscriptions

Both models are live (configure amounts in `utils/database.py` → `PLANS` and `CREDIT_PACKS`):

**Credits (pay-per-use)** — 1 credit = 1 optimization OR 1 cover letter. Keyword analysis, ATS scoring and interview prep are free.

| Pack | Credits | Price | Per use |
|------|---------|-------|---------|
| Starter | 1 | ₹49 | ₹49 |
| Job Hunt | 10 | ₹299 | ₹30 |
| Pro Pack | 30 | ₹699 | ₹23 |

**Subscriptions**

| Plan | Price | Includes |
|------|-------|----------|
| Monthly Pro | ₹399/mo | 30 optimizations + all AI tools + all templates |
| Annual Pro | ₹2,499/yr | unlimited fair-use + all AI tools + priority support |
| Agency | ₹7,999/yr | multi-seat + white-label + commercial license |

New users get **1 free welcome credit**. Payments are by UPI (QR + UTR) approved in the Admin Panel, or via license keys (`MON-`/`YRL-`/`AGE-` activate plans, `CRD-` add credits).

## Features

- **Resume Optimizer** — JD-driven rewrite of Summary/Experience/Skills, ATS score ring, keyword cloud, change-log diff, DOCX + TXT export in the selected template.
- **Resume Builder** — full fresher/professional form, exports in any template.
- **Deep Analysis** — ATS score, platform bars, section breakdown, keyword gap.
- **Templates** — 21 profession-tuned, ATS-safe templates with **live visual previews**; the selected template is the exact layout/font/section-order applied to every export.
- **Keyword Engine · Cover Letter AI · Interview Prep** — all JD-aware; cover letters are built from your own resume (never generic boilerplate).
- **Account** — settings, password reset (offline OTP), credits & subscription, admin panel (users, payments, keys, credit grants).

## Templates (21, by profession)

Life Sciences (Pharma Pro, Life Science Elite, Research Scientist, Lab Scientist) · Healthcare (Medical Professional, Clinical Researcher) · Technology (Tech Modern, Developer Pro, Minimal Clean) · Business (Executive Leader, Business Professional, Modern Professional, Creative Design) · Engineering (Engineering Professional, Technical Expert) · Academic, Legal, Government, Finance · Universal (Classic Professional, Fresh Graduate).

`utils/template_manager.py` → `BUILTIN_TEMPLATES` is the single source of truth; `utils/exporter.py` resolves any of them so the gallery, builder, optimizer and DOCX export always agree.

## Architecture

```
app.py                      # Streamlit UI (auth, pages, routing)
utils/database.py           # SQLite: users, subscriptions, credits, payments, keys, PLANS, CREDIT_PACKS
utils/resume_processor.py   # parsing, keyword extraction, rule-based optimizer + cover letter
utils/exporter.py           # template-aware DOCX/TXT builder (resolves all template ids)
utils/template_manager.py   # BUILTIN_TEMPLATES + export spec + live HTML previews
utils/llm.py                # optional local Ollama bridge (stdlib only)
data/cviq.db                # auto-created on first run
```
