"""
template_manager.py — Handles 113 Word template files.

Where to store your 113 templates:
  /your_app/templates/word/          ← all .docx template files go here
  /your_app/templates/previews/      ← auto-generated PNG thumbnails
  /your_app/templates/metadata/      ← template_catalog.json (auto-generated)

Each template .docx is a REAL Word document with the layout, fonts, colors
exactly as you want. When a user selects it, CVIQ maps their resume content
into that template's structure using python-docx paragraph/style matching.
"""
from __future__ import annotations  # safe `bytes | None` annotation on Python 3.7+

import io
import json
import re
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH

BASE_DIR       = Path(__file__).parent.parent
TEMPLATE_DIR   = BASE_DIR / "templates" / "word"
PREVIEW_DIR    = BASE_DIR / "templates" / "previews"
CATALOG_FILE   = BASE_DIR / "templates" / "metadata" / "catalog.json"

# ── Professional category → template IDs mapping ─────────────────
PROFESSION_TEMPLATE_MAP = {
    "Drug Discovery / Pharma":        ["pharma_01","pharma_02","science_01","academic_01"],
    "Cancer Biology":                 ["science_01","science_02","pharma_01","academic_01"],
    "Bioinformatics":                 ["tech_01","science_01","academic_01","minimal_01"],
    "Computational Chemistry":        ["science_01","academic_01","pharma_01","tech_01"],
    "Microbiology / Biotechnology":   ["science_02","pharma_02","academic_01","classic_01"],
    "Environmental Science":          ["science_02","classic_01","government_01","academic_01"],
    "Medicine / Clinical":            ["medical_01","medical_02","classic_01","executive_01"],
    "Public Health / Epidemiology":   ["government_01","academic_01","classic_01","medical_01"],
    "Data Science / AI / ML":         ["tech_01","tech_02","minimal_01","modern_01"],
    "Software Engineering":           ["tech_01","tech_02","minimal_01","creative_01"],
    "MBA / Management":               ["executive_01","business_01","classic_01","modern_01"],
    "Marketing / Growth":             ["creative_01","modern_01","business_01","colorful_01"],
    "Finance / Investment":           ["executive_01","business_01","classic_01","finance_01"],
    "Law / Legal":                    ["legal_01","executive_01","classic_01","government_01"],
    "Mechanical / Civil Engineering": ["engineering_01","classic_01","technical_01","modern_01"],
    "Electrical / Electronics Engineering": ["technical_01","engineering_01","tech_01","minimal_01"],
    "Academia / Research":            ["academic_01","academic_02","science_01","classic_01"],
}

# ── Built-in template definitions (before uploading real .docx files) ────────
# These are programmatic templates that work without .docx files
BUILTIN_TEMPLATES = {
    # ── Life Sciences ────────────────────────────────────────────
    "pharma_01": {
        "name": "Pharma Pro",
        "category": "Life Sciences",
        "professions": ["Drug Discovery / Pharma","Cancer Biology","Microbiology / Biotechnology"],
        "font": "Calibri", "name_size": 20, "body_size": 11, "heading_size": 12,
        "accent": (123, 31, 162),      # purple
        "heading_style": "border",
        "margins": (2.0, 1.5, 2.0, 1.5),
        "section_order": ["summary","experience","education","skills","certifications",
                          "publications","patents","awards"],
        "desc": "Purple accent · Pharma/biotech standard · Publication-ready",
    },
    "pharma_02": {
        "name": "Life Science Elite",
        "category": "Life Sciences",
        "professions": ["Drug Discovery / Pharma","Cancer Biology","Computational Chemistry"],
        "font": "Calibri", "name_size": 18, "body_size": 11, "heading_size": 12,
        "accent": (0, 102, 153),       # teal-blue
        "heading_style": "border",
        "margins": (2.0, 1.5, 2.0, 1.5),
        "section_order": ["summary","experience","publications","education","skills","certifications"],
        "desc": "Teal-blue · Publications-prominent · Senior scientist profile",
    },
    "academic_01": {
        "name": "Academic Research",
        "category": "Academic",
        "professions": ["Academia / Research","Bioinformatics","all"],
        "font": "Times New Roman", "name_size": 18, "body_size": 11, "heading_size": 12,
        "accent": (68, 114, 196),      # academic blue
        "heading_style": "underline",
        "margins": (2.0, 2.0, 2.0, 2.0),
        "section_order": ["summary","education","publications","patents","experience",
                          "skills","certifications","awards"],
        "desc": "Times New Roman · Traditional academic · Publications first",
    },
    "science_01": {
        "name": "Research Scientist",
        "category": "Life Sciences",
        "professions": ["Cancer Biology","Bioinformatics","Environmental Science","all"],
        "font": "Calibri", "name_size": 18, "body_size": 11, "heading_size": 12,
        "accent": (22, 160, 133),      # emerald
        "heading_style": "border",
        "margins": (2.0, 1.5, 2.0, 1.5),
        "section_order": ["summary","experience","education","skills","certifications",
                          "publications","awards","languages"],
        "desc": "Emerald green · Research-focused · Clean and professional",
    },
    "science_02": {
        "name": "Lab Scientist",
        "category": "Life Sciences",
        "professions": ["Microbiology / Biotechnology","Environmental Science","Medicine / Clinical"],
        "font": "Calibri", "name_size": 18, "body_size": 11, "heading_size": 12,
        "accent": (0, 128, 128),       # teal
        "heading_style": "border",
        "margins": (2.0, 1.5, 2.0, 1.5),
        "section_order": ["summary","skills","experience","education","certifications","awards"],
        "desc": "Teal · Skills-first · Lab expertise highlighted",
    },
    # ── Healthcare ───────────────────────────────────────────────
    "medical_01": {
        "name": "Medical Professional",
        "category": "Healthcare",
        "professions": ["Medicine / Clinical","Public Health / Epidemiology"],
        "font": "Calibri", "name_size": 20, "body_size": 11, "heading_size": 12,
        "accent": (192, 0, 0),         # medical red
        "heading_style": "border",
        "margins": (2.0, 1.5, 2.0, 1.5),
        "section_order": ["summary","education","experience","certifications",
                          "skills","awards","publications"],
        "desc": "Medical red · Healthcare standard · Education-first",
    },
    "medical_02": {
        "name": "Clinical Researcher",
        "category": "Healthcare",
        "professions": ["Medicine / Clinical","Public Health / Epidemiology"],
        "font": "Garamond", "name_size": 18, "body_size": 11, "heading_size": 12,
        "accent": (0, 70, 127),        # navy
        "heading_style": "border",
        "margins": (2.2, 2.0, 2.2, 2.0),
        "section_order": ["summary","experience","education","publications",
                          "certifications","skills","awards"],
        "desc": "Garamond · Clinical research profile · Navy accent",
    },
    # ── Technology ───────────────────────────────────────────────
    "tech_01": {
        "name": "Tech Modern",
        "category": "Technology",
        "professions": ["Data Science / AI / ML","Software Engineering","Bioinformatics"],
        "font": "Arial", "name_size": 20, "body_size": 10, "heading_size": 11,
        "accent": (0, 137, 123),       # teal
        "heading_style": "border",
        "margins": (1.8, 1.5, 1.8, 1.5),
        "section_order": ["summary","skills","experience","projects","education",
                          "certifications","awards"],
        "desc": "Arial · Tech-forward · Skills first · Compact",
    },
    "tech_02": {
        "name": "Developer Pro",
        "category": "Technology",
        "professions": ["Software Engineering","Data Science / AI / ML"],
        "font": "Calibri", "name_size": 20, "body_size": 10, "heading_size": 11,
        "accent": (100, 44, 145),      # deep purple
        "heading_style": "border",
        "margins": (1.8, 1.5, 1.8, 1.5),
        "section_order": ["summary","skills","experience","projects","education","certifications"],
        "desc": "Deep purple · Developer profile · GitHub-ready",
    },
    "minimal_01": {
        "name": "Minimal Clean",
        "category": "Technology",
        "professions": ["Software Engineering","Data Science / AI / ML","all"],
        "font": "Arial", "name_size": 18, "body_size": 10, "heading_size": 11,
        "accent": (0, 0, 0),           # pure black
        "heading_style": "underline",
        "margins": (1.8, 1.5, 1.8, 1.5),
        "section_order": ["summary","skills","experience","education","certifications"],
        "desc": "Minimal black · ATS-safe · Universal",
    },
    # ── Business ─────────────────────────────────────────────────
    "executive_01": {
        "name": "Executive Leader",
        "category": "Business",
        "professions": ["MBA / Management","Finance / Investment","Law / Legal"],
        "font": "Georgia", "name_size": 20, "body_size": 11, "heading_size": 12,
        "accent": (26, 26, 46),        # near-black navy
        "heading_style": "border",
        "margins": (2.2, 2.0, 2.2, 2.0),
        "section_order": ["summary","experience","education","skills","certifications","awards"],
        "desc": "Georgia serif · C-suite · Senior leadership",
    },
    "business_01": {
        "name": "Business Professional",
        "category": "Business",
        "professions": ["MBA / Management","Marketing / Growth","Finance / Investment"],
        "font": "Calibri", "name_size": 18, "body_size": 11, "heading_size": 12,
        "accent": (31, 73, 125),       # navy blue
        "heading_style": "border",
        "margins": (2.0, 1.5, 2.0, 1.5),
        "section_order": ["summary","experience","education","skills","certifications","awards"],
        "desc": "Navy · Business standard · Clean and impactful",
    },
    "modern_01": {
        "name": "Modern Professional",
        "category": "Business",
        "professions": ["Marketing / Growth","MBA / Management","all"],
        "font": "Calibri", "name_size": 20, "body_size": 11, "heading_size": 12,
        "accent": (46, 117, 182),      # medium blue
        "heading_style": "border",
        "margins": (1.8, 1.5, 1.8, 1.5),
        "section_order": ["summary","experience","skills","education","certifications"],
        "desc": "Modern blue · Contemporary · All-purpose",
    },
    "creative_01": {
        "name": "Creative Design",
        "category": "Business",
        "professions": ["Marketing / Growth","Software Engineering"],
        "font": "Arial", "name_size": 20, "body_size": 10, "heading_size": 11,
        "accent": (234, 67, 53),       # Google red
        "heading_style": "border",
        "margins": (1.8, 1.5, 1.8, 1.5),
        "section_order": ["summary","skills","experience","projects","education","certifications"],
        "desc": "Bold red · Creative roles · Portfolio-ready",
    },
    # ── Legal & Government ────────────────────────────────────────
    "legal_01": {
        "name": "Legal Professional",
        "category": "Legal",
        "professions": ["Law / Legal"],
        "font": "Times New Roman", "name_size": 18, "body_size": 11, "heading_size": 12,
        "accent": (0, 0, 128),         # traditional navy
        "heading_style": "underline",
        "margins": (2.5, 2.0, 2.5, 2.0),
        "section_order": ["summary","experience","education","certifications","skills","awards"],
        "desc": "Times New Roman · Traditional law format · Conservative",
    },
    "government_01": {
        "name": "Government / Public Service",
        "category": "Government",
        "professions": ["Public Health / Epidemiology","Environmental Science","Law / Legal"],
        "font": "Calibri", "name_size": 18, "body_size": 11, "heading_size": 12,
        "accent": (0, 70, 127),        # government navy
        "heading_style": "border",
        "margins": (2.2, 2.0, 2.2, 2.0),
        "section_order": ["summary","experience","education","certifications","skills","awards"],
        "desc": "Government navy · Public sector · Formal structure",
    },
    # ── Engineering ───────────────────────────────────────────────
    "engineering_01": {
        "name": "Engineering Professional",
        "category": "Engineering",
        "professions": ["Mechanical / Civil Engineering","Electrical / Electronics Engineering"],
        "font": "Calibri", "name_size": 18, "body_size": 11, "heading_size": 12,
        "accent": (0, 90, 156),        # engineering blue
        "heading_style": "border",
        "margins": (2.0, 1.5, 2.0, 1.5),
        "section_order": ["summary","skills","experience","projects","education","certifications"],
        "desc": "Engineering blue · Technical roles · Projects-prominent",
    },
    "technical_01": {
        "name": "Technical Expert",
        "category": "Engineering",
        "professions": ["Electrical / Electronics Engineering","Software Engineering"],
        "font": "Arial", "name_size": 18, "body_size": 10, "heading_size": 11,
        "accent": (0, 120, 212),       # Microsoft blue
        "heading_style": "border",
        "margins": (1.8, 1.5, 1.8, 1.5),
        "section_order": ["summary","skills","experience","projects","certifications","education"],
        "desc": "Technical blue · Engineer/Developer · Compact format",
    },
    # ── Finance ───────────────────────────────────────────────────
    "finance_01": {
        "name": "Finance Professional",
        "category": "Finance",
        "professions": ["Finance / Investment"],
        "font": "Garamond", "name_size": 18, "body_size": 11, "heading_size": 12,
        "accent": (0, 51, 102),        # dark navy
        "heading_style": "border",
        "margins": (2.2, 2.0, 2.2, 2.0),
        "section_order": ["summary","experience","education","certifications","skills","awards"],
        "desc": "Garamond · Finance/banking · Traditional prestige",
    },
    # ── Universal ─────────────────────────────────────────────────
    "classic_professional": {
        "name": "Classic Professional",
        "category": "Universal",
        "professions": ["all"],
        "font": "Calibri", "name_size": 18, "body_size": 11, "heading_size": 12,
        "accent": (31, 73, 125),       # dark navy
        "heading_style": "border",
        "margins": (2.0, 1.5, 2.0, 1.5),
        "section_order": ["summary","experience","education","skills","certifications",
                          "publications","patents","awards","projects","languages"],
        "desc": "Universal · Maximum ATS-safe · Works for all roles",
    },
    "fresh_graduate": {
        "name": "Fresh Graduate",
        "category": "Universal",
        "professions": ["all"],
        "font": "Calibri", "name_size": 18, "body_size": 11, "heading_size": 12,
        "accent": (5, 120, 91),        # emerald
        "heading_style": "border",
        "margins": (2.0, 1.5, 2.0, 1.5),
        "section_order": ["summary","education","skills","projects","experience",
                          "certifications","awards","activities","languages"],
        "desc": "Emerald · Education-first · Perfect for freshers",
    },
}


def get_all_builtin_templates():
    return BUILTIN_TEMPLATES


# ── Canonical spec + preview helpers (single source of truth) ────────────────
SECTION_LABELS = {
    "summary": "Professional Summary", "experience": "Work Experience",
    "education": "Education", "skills": "Skills", "projects": "Projects",
    "certifications": "Certifications", "publications": "Publications",
    "patents": "Patents", "awards": "Awards & Honours", "languages": "Languages",
    "activities": "Activities", "credentials": "Credentials",
}

# Short realistic sample lines per section, used to render template previews.
_PREVIEW_SAMPLE = {
    "summary": ["Results-driven professional with proven impact across cross-functional teams and measurable outcomes."],
    "experience": ["Senior Specialist | Acme Corp", "• Drove 32% efficiency gain across core delivery pipeline"],
    "education": ["M.Sc., University of Excellence", "2019 – 2021 · First Class"],
    "skills": ["Python · SQL · Project Management · Stakeholder Comms · Analytics"],
    "projects": ["Automation Platform — Python, Docker", "• Cut manual effort by 60%"],
    "certifications": ["Certified Professional (2023)"],
    "publications": ["First-author paper, peer-reviewed journal (2022)"],
    "patents": ["Granted patent — process optimisation method"],
    "awards": ["Top Performer Award, 2023"],
    "languages": ["English (Native) · Hindi (Fluent)"],
    "activities": ["Volunteer mentor, student career program"],
    "credentials": ["Licensed practitioner · Board certified"],
}


def accent_hex(template_id: str) -> str:
    tpl = BUILTIN_TEMPLATES.get(template_id, BUILTIN_TEMPLATES["classic_professional"])
    r, g, b = tpl.get("accent", (31, 73, 125))
    return f"#{r:02x}{g:02x}{b:02x}"


def get_export_spec(template_id: str) -> dict:
    """
    Return a normalised spec usable by the DOCX exporter for ANY built-in
    template id. This is what lets the gallery (21 templates) and the exporter
    share one source of truth so the *selected* template actually applies.
    """
    tpl = BUILTIN_TEMPLATES.get(template_id, BUILTIN_TEMPLATES["classic_professional"])
    r, g, b = tpl.get("accent", (31, 73, 125))
    return {
        "name":         tpl.get("name", template_id),
        "desc":         tpl.get("desc", ""),
        "font":         tpl.get("font", "Calibri"),
        "font_size":    tpl.get("body_size", 11),
        "heading_font": tpl.get("font", "Calibri"),
        "heading_size": tpl.get("heading_size", 12),
        "name_size":    tpl.get("name_size", 18),
        "accent":       RGBColor(r, g, b),
        "text_color":   RGBColor(0x11, 0x11, 0x11),
        "heading_style": tpl.get("heading_style", "border"),
        "margins":      tpl.get("margins", (2.0, 1.5, 2.0, 1.5)),
        "line_spacing": 1.15,
        "section_order": tpl.get("section_order",
                                 ["summary", "experience", "education", "skills",
                                  "certifications", "projects", "awards", "languages"]),
    }


def render_template_preview_html(template_id: str, max_sections: int = 5) -> str:
    """Render a realistic mini-resume preview in the template's own font, accent
    colour, heading style and section order — so users can SEE each template."""
    tpl   = BUILTIN_TEMPLATES.get(template_id, BUILTIN_TEMPLATES["classic_professional"])
    acc   = accent_hex(template_id)
    font  = tpl.get("font", "Calibri")
    hstyle = tpl.get("heading_style", "border")
    order = tpl.get("section_order", ["summary", "experience", "education", "skills"])

    # Every section heading shows a full-width divider line beneath it.
    head_css = f"border-bottom:1.4px solid {acc};padding-bottom:1px"

    blocks = [
        f'<div style="text-align:center;font-size:13px;font-weight:800;color:{acc};letter-spacing:.3px">ALEX MORGAN</div>',
        '<div style="text-align:center;font-size:6.5px;color:#777;margin-bottom:1px">✉ alex.morgan@email.com · ☎ +91 98765 43210 · 🔗 linkedin.com/in/alex</div>',
        '<div style="text-align:center;font-size:6.5px;color:#999;margin-bottom:6px">📍 Bengaluru, India</div>',
    ]
    for key in order[:max_sections]:
        label = SECTION_LABELS.get(key, key.title())
        lines = _PREVIEW_SAMPLE.get(key, [])
        blocks.append(
            f'<div style="font-size:7.5px;font-weight:700;color:{acc};{head_css};'
            f'margin:5px 0 2px;text-transform:uppercase;letter-spacing:.4px">{label}</div>'
        )
        for ln in lines:
            bold = "font-weight:700;" if ("|" in ln or "—" in ln or "," in ln and key in ("experience", "projects", "education")) else ""
            blocks.append(f'<div style="font-size:7px;color:#333;{bold}line-height:1.35">{ln}</div>')

    return (f'<div style="background:#fff;border-radius:6px;padding:12px 13px;'
            f'font-family:\'{font}\',Arial,sans-serif;min-height:230px">'
            + "".join(blocks) + "</div>")

def get_template_for_profession(profession: str) -> list:
    """Return recommended template IDs for a profession."""
    for domain, tpl_ids in PROFESSION_TEMPLATE_MAP.items():
        if profession.lower() in domain.lower() or domain.lower() in profession.lower():
            return tpl_ids
    return ["classic_professional","modern_01","minimal_01"]

def get_template_categories() -> list:
    cats = list(dict.fromkeys(t["category"] for t in BUILTIN_TEMPLATES.values()))
    return ["All"] + sorted(cats)

def apply_word_template(template_docx_bytes: bytes, resume_data: dict) -> bytes:
    """
    Apply a user's uploaded Word template to resume data.
    Opens the template, finds placeholder sections, and replaces with resume content.
    Preserves ALL formatting (fonts, colors, margins, styles) from the template.
    """
    doc = Document(io.BytesIO(template_docx_bytes))

    # Build resume content blocks
    pi       = resume_data.get("personal_info", {})
    sections = resume_data.get("_sections", {})
    order    = resume_data.get("_order", [])

    # Simple approach: map template paragraph placeholders to content
    # Placeholders in template: {{NAME}}, {{CONTACT}}, {{SUMMARY}}, etc.
    PLACEHOLDER_MAP = {
        "{{NAME}}":           pi.get("name",""),
        "{{EMAIL}}":          pi.get("email",""),
        "{{PHONE}}":          pi.get("phone",""),
        "{{LOCATION}}":       pi.get("location",""),
        "{{LINKEDIN}}":       pi.get("linkedin",""),
        "{{CONTACT_LINE}}":   " | ".join(v for v in [pi.get("email",""), pi.get("phone",""), pi.get("location","")] if v),
        "{{SUMMARY}}":        sections.get("summary","").replace("PROFESSIONAL SUMMARY\n","").strip(),
        "{{SKILLS}}":         sections.get("skills","").replace("TECHNICAL SKILLS\n","").replace("SKILLS\n","").strip(),
        "{{EXPERIENCE}}":     sections.get("experience","").replace("WORK EXPERIENCE\n","").strip(),
        "{{EDUCATION}}":      sections.get("education","").replace("EDUCATION\n","").strip(),
        "{{CERTIFICATIONS}}": sections.get("certifications","").replace("CERTIFICATIONS\n","").strip(),
        "{{PUBLICATIONS}}":   sections.get("publications","").replace("PUBLICATIONS\n","").strip(),
    }

    # Replace placeholders in all paragraphs
    for para in doc.paragraphs:
        for placeholder, value in PLACEHOLDER_MAP.items():
            if placeholder in para.text:
                # Preserve formatting by replacing in each run
                for run in para.runs:
                    if placeholder in run.text:
                        run.text = run.text.replace(placeholder, value)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def load_template_file(template_id: str) -> bytes | None:
    """Load a .docx template file from disk."""
    path = TEMPLATE_DIR / f"{template_id}.docx"
    if path.exists():
        return path.read_bytes()
    return None


def list_uploaded_templates() -> list:
    """List all .docx files in the templates/word/ directory."""
    if not TEMPLATE_DIR.exists():
        return []
    return [f.stem for f in TEMPLATE_DIR.glob("*.docx")]


def save_template_metadata(templates_info: list):
    """Save template catalog to JSON."""
    CATALOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CATALOG_FILE, "w") as f:
        json.dump(templates_info, f, indent=2)


def load_template_metadata() -> list:
    """Load template catalog from JSON."""
    if CATALOG_FILE.exists():
        with open(CATALOG_FILE) as f:
            return json.load(f)
    return []
