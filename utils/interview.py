"""
interview.py — generic, profession-agnostic interview-question generator.

Always returns EXACTLY the requested number of questions, distributed across the
selected categories and tailored using the job description's keywords. Each
question comes with a STAR / coaching answer scaffold (guidance the candidate
fills with their own experience — never fabricated). Uses a local LLM for
question wording when available, otherwise pure templates.
"""
import re
from utils.resume_processor import extract_keywords_from_jd


def _llm_interview_questions(resume: str, jd: str, types: list, count: int):
    """Ask a local LLM for tailored question texts. Returns list[str] or None."""
    try:
        from utils import llm
    except Exception:
        return None
    if not llm.ollama_available():
        return None
    tset = ", ".join(types) if types else "Behavioral, Technical"
    prompt = (f"You are an interview coach. Generate exactly {count} realistic interview questions "
              f"for this candidate and job. Mix these categories: {tset}. Prefix each question with its "
              f"category in square brackets, e.g. '[Technical] ...'. One question per line, numbered 1..{count}. "
              f"Tailor to the job description and the candidate's resume. Questions only, no answers.\n\n"
              f"=== RESUME ===\n{(resume or '')[:2500]}\n\n=== JOB DESCRIPTION ===\n{(jd or '')[:2500]}")
    out = llm.generate(prompt, temperature=0.5, timeout=90)
    if not out:
        return None
    qs = []
    for line in out.splitlines():
        line = re.sub(r'^\s*\d+[\.\)]\s*', '', line.strip())
        if len(line) > 12 and line.endswith("?"):
            qs.append(line)
    return qs or None


TEMPLATES = {
    "Behavioral": [
        "Tell me about a time you led a project involving {k0}. What was the outcome?",
        "Describe a challenging problem you solved related to {k1}.",
        "Give an example of a conflict with a teammate and how you resolved it.",
        "Tell me about a time results were unexpected. How did you respond?",
        "Describe a time you mentored or helped a colleague grow.",
        "Tell me about a time you delivered {k0} work under a tight deadline.",
        "Describe a time you had to adapt quickly to a major change.",
        "Give an example of when you took initiative beyond your role.",
        "Tell me about a time you persuaded stakeholders to back your idea on {k2}.",
        "Describe how you balanced multiple priorities at once.",
    ],
    "Technical": [
        "Walk me through your hands-on experience with {k0}.",
        "How would you approach {k1} in a new project from scratch?",
        "What tools and methods do you use for {k2}, and why?",
        "Explain a concept central to this role ({k0}) to a non-expert.",
        "How do you ensure quality and correctness in your {k0} work?",
        "Describe the most technically challenging problem you solved using {k1}.",
        "How do you stay current with developments in {k0}?",
        "How would you troubleshoot when {k2} gives unexpected results?",
        "What metrics define success for {k0} in this role?",
        "How would you scale or improve an existing {k1} process?",
    ],
    "Situational": [
        "Mid-project, a key tool or resource fails with a deadline looming. What do you do?",
        "You get contradictory data from two sources for {k2}. How do you resolve it?",
        "A stakeholder requests a change that risks the timeline. How do you respond?",
        "You disagree with your manager's approach to {k0}. What do you do?",
        "You're assigned a {k1} task you've never done before. How do you proceed?",
        "Two priorities are due the same day. How do you decide?",
        "A teammate isn't delivering their part of a {k0} project. How do you handle it?",
        "You discover an error in already-delivered work. What's your next step?",
        "You're given an ambiguous brief for {k1}. How do you create clarity?",
        "Budget is cut mid-project. How do you still deliver on {k0}?",
    ],
    "Culture Fit": [
        "Why do you want to work here, and how does this role fit your goals?",
        "What kind of team environment helps you do your best work?",
        "How do you handle feedback and criticism?",
        "What values matter most to you in a workplace?",
        "How do you contribute to a positive team culture?",
        "Describe your ideal manager and working relationship.",
        "What motivates you day to day?",
        "How do you handle disagreement with a company decision?",
    ],
    "HR / Salary": [
        "Walk me through your background and why this role.",
        "What are your salary expectations for this position?",
        "Why are you leaving (or did you leave) your current role?",
        "What are your strengths and what are you working to improve?",
        "Where do you see yourself in 3-5 years?",
        "What is your availability / notice period?",
        "Do you have other offers, and what's your timeline?",
        "Why should we hire you over other candidates?",
    ],
}

SCAFFOLD = {
    "Behavioral": (
        "**How to answer — STAR:**\n\n"
        "- **Situation:** Set the context — the project, team and your role (tie it to {k0} if relevant).\n"
        "- **Task:** Your specific responsibility or the challenge.\n"
        "- **Action:** The concrete steps *you* took — be specific, use \"I\".\n"
        "- **Result:** Quantify the outcome (%, time, revenue, users) and what you learned.\n\n"
        "💡 Pick a real example from your resume involving **{k0}** or **{k1}**. Keep it ~90 seconds."),
    "Technical": (
        "**How to answer:**\n\n"
        "- Briefly define the concept, then give a concrete example from your work with **{k0}**.\n"
        "- Name the specific tools/methods you used and *why*.\n"
        "- State the measurable result, and how you'd validate or scale it.\n\n"
        "💡 If unsure, explain your reasoning step by step — structured thinking scores well."),
    "Situational": (
        "**How to answer:**\n\n"
        "- Clarify the constraints and assumptions first.\n"
        "- Give a prioritised plan: immediate → short-term → fallback.\n"
        "- Emphasise stakeholder communication and risk mitigation.\n"
        "- Close with the outcome you'd target. Tie to **{k0}** where natural."),
    "Culture Fit": (
        "**How to answer:**\n\n"
        "- Be authentic; connect your values to what the company actually does.\n"
        "- Give a short example that shows the trait in action.\n"
        "- Show self-awareness and a collaborative mindset.\n\n"
        "💡 Research the company's mission and reference it specifically."),
    "HR / Salary": (
        "**How to answer:**\n\n"
        "- Keep it concise, positive and forward-looking (no negativity about past employers).\n"
        "- For salary: give a researched range and tie it to the value you bring.\n"
        "- Reaffirm your genuine interest in the role.\n\n"
        "💡 Know your market range before the call and anchor confidently."),
}


def generate_interview_questions(resume: str, jd: str, types: list, count: int) -> dict:
    """Return EXACTLY `count` {question: answer} pairs across the selected types."""
    if not types:
        types = ["Behavioral", "Technical"]

    kws = extract_keywords_from_jd(jd) if jd else []
    resume_lower = (resume or "").lower()
    matching = [k for k in kws if k.lower() in resume_lower]
    pool, seen = [], set()
    for k in (matching + kws):
        kl = k.lower()
        if kl and kl not in seen:
            seen.add(kl); pool.append(k)
    pool += ["this role", "your core domain", "your toolset", "cross-functional teams",
             "your key project", "your area of expertise"]

    def f(i):
        return pool[i % len(pool)]

    def make_answer(cat):
        return SCAFFOLD.get(cat, SCAFFOLD["Behavioral"]).format(k0=f(0), k1=f(1), k2=f(2))

    # Large, varied list per category (template × keyword rotation).
    per_cat = {}
    for cat in types:
        templs = TEMPLATES.get(cat, TEMPLATES["Behavioral"])
        ans = make_answer(cat)
        qs, used, rnd = [], set(), 0
        while len(qs) < count + 2 and rnd < 25:
            for t in templs:
                q = t.format(k0=f(rnd), k1=f(rnd + 1), k2=f(rnd + 2), k3=f(rnd + 3))
                if q not in used:
                    used.add(q); qs.append((q, ans))
                if len(qs) >= count + 2:
                    break
            rnd += 1
        per_cat[cat] = qs

    output = {}

    # Optional LLM-tailored question wording.
    llm_qs = _llm_interview_questions(resume, jd, types, count)
    if llm_qs:
        for q in llm_qs:
            cat, qtext = "Behavioral", q
            if q.startswith("["):
                m = q.find("]")
                if m != -1:
                    cat = q[1:m].strip() or "Behavioral"
                    qtext = q[m + 1:].strip()
            if cat not in SCAFFOLD:
                cat = types[0] if types[0] in SCAFFOLD else "Behavioral"
            key, base, n = f"[{cat}] {qtext}", f"[{cat}] {qtext}", 2
            while key in output:
                key = f"{base} ({n})"; n += 1
            output[key] = make_answer(cat)
            if len(output) >= count:
                break

    # Fill remainder round-robin across the selected types.
    idxs = {c: 0 for c in types}
    while len(output) < count:
        progressed = False
        for c in types:
            lst = per_cat.get(c, [])
            if idxs[c] < len(lst):
                q, a = lst[idxs[c]]; idxs[c] += 1
                key, base, n = f"[{c}] {q}", f"[{c}] {q}", 2
                while key in output:
                    key = f"{base} ({n})"; n += 1
                output[key] = a; progressed = True
            if len(output) >= count:
                break
        if not progressed:
            break

    return dict(list(output.items())[:count])
