import streamlit as st
import random, json
from datetime import datetime

try:
    from supabase import create_client
    import os
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
except Exception:
    supabase = None

st.set_page_config(page_title="AI-900 Practice Quiz for Microsoft Azure", page_icon="\U0001F916", layout="centered")

@st.cache_data(ttl=3600)
def load_questions():
    if supabase:
        res = supabase.table("questions").select("*").execute()
        return res.data
    # Fallback fichier local si Supabase non configuré
    with open("questions.json", encoding="utf-8") as f:
        return json.load(f)

QUESTIONS = load_questions()

DOMAINS = ["All"] + sorted(set(q["domain"] for q in QUESTIONS))
DOMAIN_COLORS = {
    "Vision": "#0078D4", "NLP": "#107C10", "ML": "#FFB900",
    "Generative AI": "#8764B8", "Responsible AI": "#D13438", "AI Workloads": "#00B7C3"
}

def save_result(username, score, total, domain_scores):
    if not supabase:
        return
    try:
        supabase.table("quiz_results").insert({
            "username": username, "score": score, "total": total,
            "percentage": round(score / total * 100),
            "domain_scores": json.dumps(domain_scores),
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        st.warning(f"Supabase save error: {e}")

def get_leaderboard():
    if not supabase:
        return []
    try:
        return supabase.table("quiz_results").select("*").order("percentage", desc=True).limit(10).execute().data
    except Exception:
        return []

defaults = {
    "started": False, "done": False, "idx": 0, "score": 0,
    "answers": {}, "domain_scores": {}, "questions": [],
    "domain": "All", "username": "Mathieu", "nb": 10
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ---- HOME ----
if not st.session_state.started:
    st.title("\U0001F916 AI-900 Practice Quiz")
    st.caption("Microsoft Azure AI Fundamentals — Exam Prep")
    c1, c2 = st.columns(2)
    with c1:
        st.session_state.username = st.text_input("Ton prenom", value=st.session_state.username)
    with c2:
        st.session_state.domain = st.selectbox("Domaine", DOMAINS)
    st.session_state.nb = st.slider("Nombre de questions", 5, 20, st.session_state.nb)

    if st.button("Lancer le quiz", type="primary", use_container_width=True):
        pool = [q for q in QUESTIONS if st.session_state.domain == "All" or q["domain"] == st.session_state.domain]
        st.session_state.questions = random.sample(pool, min(st.session_state.nb, len(pool)))
        st.session_state.started = True
        st.session_state.done = False
        st.session_state.idx = 0
        st.session_state.score = 0
        st.session_state.answers = {}
        st.session_state.domain_scores = {}
        st.rerun()

    lb = get_leaderboard()
    if lb:
        st.markdown("---")
        st.subheader("\U0001F3C6 Classement")
        for i, row in enumerate(lb):
            medal = ["\U0001F947","\U0001F948","\U0001F949"][i] if i < 3 else f"{i+1}."
            st.write(f"{medal} **{row['username']}** — {row['percentage']}%  ({row['score']}/{row['total']})")

# ---- QUIZ ----
elif not st.session_state.done:
    questions = st.session_state.questions
    idx = st.session_state.idx
    q = questions[idx]
    total = len(questions)
    multi = len(q["answers"]) > 1

    st.progress(idx / total)
    color = DOMAIN_COLORS.get(q["domain"], "#555")
    st.markdown(f"<span style='background:{color};color:white;padding:3px 12px;border-radius:12px;font-size:0.82em;font-weight:600'>{q['domain']}</span>", unsafe_allow_html=True)
    st.markdown(f"**Question {idx+1}/{total}**")
    st.markdown(f"### {q['question']}")
    if multi:
        st.caption("Plusieurs bonnes reponses — cochez toutes les bonnes.")

    answered = idx in st.session_state.answers

    if not answered:
        if multi:
            selected = [i for i, c in enumerate(q["choices"]) if st.checkbox(c, key=f"cb{idx}_{i}")]
        else:
            choice = st.radio("Votre reponse :", q["choices"], key=f"r{idx}", index=None)
            selected = [q["choices"].index(choice)] if choice else []

        if st.button("Valider", type="primary", disabled=not selected, use_container_width=True):
            correct = sorted(selected) == sorted(q["answers"])
            st.session_state.answers[idx] = {"selected": selected, "correct": correct}
            if correct:
                st.session_state.score += 1
            dom = q["domain"]
            ds = st.session_state.domain_scores
            if dom not in ds:
                ds[dom] = {"correct": 0, "total": 0}
            ds[dom]["total"] += 1
            if correct:
                ds[dom]["correct"] += 1
            st.rerun()
    else:
        res = st.session_state.answers[idx]
        if res["correct"]:
            st.success("Bonne reponse !")
        else:
            correct_labels = ", ".join(q["choices"][i] for i in q["answers"])
            st.error(f"Incorrect. Bonne(s) reponse(s) : **{correct_labels}**")
        st.info(f"\U0001F4A1 {q['explanation']}")
        st.caption(f"\U0001F4DA {q['ref']}")

        if idx < total - 1:
            if st.button("Question suivante", type="primary", use_container_width=True):
                st.session_state.idx += 1
                st.rerun()
        else:
            if st.button("\U0001F3C1 Voir les resultats", type="primary", use_container_width=True):
                st.session_state.done = True
                save_result(st.session_state.username, st.session_state.score, total, st.session_state.domain_scores)
                st.rerun()

# ---- RESULTS ----
else:
    total = len(st.session_state.questions)
    score = st.session_state.score
    pct = round(score / total * 100)
    st.title("\U0001F4CA Resultats")
    if pct >= 80:
        st.balloons()
        st.success(f"Excellent ! {score}/{total} — {pct}%  Pret pour l'examen !")
    elif pct >= 60:
        st.warning(f"Pas mal ! {score}/{total} — {pct}%  Continue !")
    else:
        st.error(f"{score}/{total} — {pct}%  Encore un peu de revision !")

    st.markdown("---")
    st.subheader("Resultats par domaine")
    for dom, data in st.session_state.domain_scores.items():
        p = round(data["correct"] / data["total"] * 100)
        color = DOMAIN_COLORS.get(dom, "#555")
        icon = "\u2705" if p >= 70 else "\u26A0\uFE0F" if p >= 50 else "\u274C"
        st.markdown(f"{icon} <span style='background:{color};color:white;padding:2px 10px;border-radius:10px'>{dom}</span> **{data['correct']}/{data['total']}** ({p}%)", unsafe_allow_html=True)

    st.markdown("---")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("\U0001F504 Recommencer", use_container_width=True):
            pool = [q for q in QUESTIONS if st.session_state.domain == "All" or q["domain"] == st.session_state.domain]
            st.session_state.questions = random.sample(pool, min(len(st.session_state.questions), len(pool)))
            st.session_state.idx = 0; st.session_state.score = 0
            st.session_state.answers = {}; st.session_state.domain_scores = {}
            st.session_state.done = False
            st.rerun()
    with c2:
        if st.button("\U0001F3E0 Accueil", use_container_width=True):
            st.session_state.started = False; st.session_state.done = False
            st.session_state.idx = 0; st.session_state.score = 0
            st.session_state.answers = {}; st.session_state.domain_scores = {}
            st.session_state.questions = []
            st.rerun()