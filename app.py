import streamlit as st
import random, json, os
from datetime import datetime

# ── Supabase ──────────────────────────────────────────────────────────────────
try:
    from supabase import create_client
    _url = os.environ.get("SUPABASE_URL", "")
    _key = os.environ.get("SUPABASE_KEY", "")
    supabase = create_client(_url, _key) if _url and _key else None
except Exception:
    supabase = None

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI-900 Practice Quiz",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
  .domain-badge {
    display: inline-block;
    padding: 3px 14px;
    border-radius: 20px;
    font-size: 0.78em;
    font-weight: 700;
    letter-spacing: 0.03em;
    color: white;
    margin-bottom: 8px;
  }
  .result-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 0;
    border-bottom: 1px solid #f0f0f0;
  }
  .progress-label {
    font-size: 0.82em;
    color: #888;
    margin-bottom: 4px;
  }
  div[data-testid="stButton"] button {
    border-radius: 10px;
  }
</style>
""", unsafe_allow_html=True)

DOMAIN_COLORS = {
    "Vision": "#0078D4",
    "NLP": "#107C10",
    "ML": "#FFB900",
    "Generative AI": "#8764B8",
    "Responsible AI": "#D13438",
    "AI Workloads": "#00B7C3"
}

# ── Data ──────────────────────────────────────────────────────────────────────
@st.cache_data(ttl=3600, show_spinner="Chargement des questions…")
def load_questions():
    if supabase:
        try:
            res = supabase.table("questions").select("*").execute()
            if res.data:
                return res.data
        except Exception:
            pass
    with open("questions.json", encoding="utf-8") as f:
        return json.load(f)

def save_result(username, score, total, domain_scores):
    if not supabase:
        return
    try:
        supabase.table("quiz_results").insert({
            "username": username,
            "score": score,
            "total": total,
            "percentage": round(score / total * 100),
            "domain_scores": json.dumps(domain_scores),
            "created_at": datetime.utcnow().isoformat()
        }).execute()
    except Exception as e:
        st.toast(f"⚠️ Score non sauvegardé : {e}", icon="⚠️")

@st.cache_data(ttl=60)
def get_leaderboard():
    if not supabase:
        return []
    try:
        return supabase.table("quiz_results").select("*").order("percentage", desc=True).limit(10).execute().data
    except Exception:
        return []

QUESTIONS = load_questions()
DOMAINS = ["Tous les domaines"] + sorted(set(q["domain"] for q in QUESTIONS))

# ── Session state ─────────────────────────────────────────────────────────────
DEFAULTS = {
    "started": False, "done": False, "idx": 0, "score": 0,
    "answers": {}, "domain_scores": {}, "questions": [],
    "domain": "Tous les domaines", "username": "", "nb": 15
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── Helpers ───────────────────────────────────────────────────────────────────
def badge(domain):
    color = DOMAIN_COLORS.get(domain, "#555")
    return f"<span class='domain-badge' style='background:{color}'>{domain}</span>"

def reset_quiz(keep_settings=True):
    st.session_state.idx = 0
    st.session_state.score = 0
    st.session_state.answers = {}
    st.session_state.domain_scores = {}
    st.session_state.done = False
    if not keep_settings:
        st.session_state.started = False
        st.session_state.questions = []

def start_quiz():
    domain = st.session_state.domain
    pool = [q for q in QUESTIONS if domain == "Tous les domaines" or q["domain"] == domain]
    if not pool:
        st.error("Aucune question disponible pour ce domaine.")
        return
    reset_quiz()
    st.session_state.questions = random.sample(pool, min(st.session_state.nb, len(pool)))
    st.session_state.started = True

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE : ACCUEIL
# ═══════════════════════════════════════════════════════════════════════════════
if not st.session_state.started:

    st.markdown("# 🤖 AI-900 Practice Quiz")
    st.markdown("**Microsoft Azure AI Fundamentals** — Prépare-toi à l'examen avec des questions proches du vrai test.")
    st.divider()

    # Stats globales
    total_q = len(QUESTIONS)
    domains_count = len(set(q["domain"] for q in QUESTIONS))
    c1, c2, c3 = st.columns(3)
    c1.metric("Questions disponibles", total_q)
    c2.metric("Domaines couverts", domains_count)
    c3.metric("Score cible examen", "≥ 700 / 1000")

    st.divider()

    # Config
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.username = st.text_input(
            "👤 Ton prénom",
            value=st.session_state.username,
            placeholder="Ex : Mathieu"
        )
    with col2:
        st.session_state.domain = st.selectbox("🎯 Domaine à cibler", DOMAINS,
            index=DOMAINS.index(st.session_state.domain) if st.session_state.domain in DOMAINS else 0)

    st.session_state.nb = st.slider("📝 Nombre de questions", 5, min(30, total_q), st.session_state.nb)

    # Info domaine sélectionné
    if st.session_state.domain != "Tous les domaines":
        n = sum(1 for q in QUESTIONS if q["domain"] == st.session_state.domain)
        color = DOMAIN_COLORS.get(st.session_state.domain, "#555")
        st.markdown(f"{badge(st.session_state.domain)} **{n} questions** disponibles dans ce domaine", unsafe_allow_html=True)

    st.markdown("")
    disabled = not st.session_state.username.strip()
    if st.button("🚀 Lancer le quiz", type="primary", use_container_width=True, disabled=disabled):
        start_quiz()
        st.rerun()
    if disabled:
        st.caption("⬆️ Entre ton prénom pour commencer")

    # Leaderboard
    lb = get_leaderboard()
    if lb:
        st.divider()
        st.subheader("🏆 Classement")
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(lb):
            icon = medals[i] if i < 3 else f"**{i+1}.**"
            pct = row.get("percentage", 0)
            bar_color = "#107C10" if pct >= 80 else "#FFB900" if pct >= 60 else "#D13438"
            st.markdown(
                f"{icon} **{row['username']}** — "
                f"<span style='color:{bar_color};font-weight:700'>{pct}%</span> "
                f"<span style='color:#888;font-size:0.85em'>({row['score']}/{row['total']})</span>",
                unsafe_allow_html=True
            )

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE : QUIZ
# ═══════════════════════════════════════════════════════════════════════════════
elif not st.session_state.done:
    questions = st.session_state.questions
    idx = st.session_state.idx

    # Guard anti-IndexError
    if idx >= len(questions):
        st.session_state.idx = 0
        st.rerun()

    q = questions[idx]
    total = len(questions)
    multi = len(q["answers"]) > 1

    # Header
    col_prog, col_score = st.columns([3, 1])
    with col_prog:
        st.markdown(f"<p class='progress-label'>Question {idx+1} sur {total}</p>", unsafe_allow_html=True)
        st.progress((idx) / total)
    with col_score:
        st.metric("Score", f"{st.session_state.score}/{idx}", delta=None)

    st.markdown(badge(q["domain"]), unsafe_allow_html=True)
    st.markdown(f"### {q['question']}")

    if multi:
        st.info("✏️ Plusieurs bonnes réponses — cochez toutes les bonnes.")

    answered = idx in st.session_state.answers

    # Réponse
    if not answered:
        if multi:
            selected = [i for i, c in enumerate(q["choices"]) if st.checkbox(c, key=f"cb{idx}_{i}")]
        else:
            choice = st.radio("Votre réponse :", q["choices"], key=f"r{idx}", index=None, label_visibility="collapsed")
            selected = [q["choices"].index(choice)] if choice else []

        st.markdown("")
        if st.button("✅ Valider", type="primary", disabled=not selected, use_container_width=True):
            correct = sorted(selected) == sorted(q["answers"])
            st.session_state.answers[idx] = {"selected": selected, "correct": correct}
            if correct:
                st.session_state.score += 1
            dom = q["domain"]
            ds = st.session_state.domain_scores
            ds.setdefault(dom, {"correct": 0, "total": 0})
            ds[dom]["total"] += 1
            if correct:
                ds[dom]["correct"] += 1
            st.rerun()

    else:
        res = st.session_state.answers[idx]
        if res["correct"]:
            st.success("✅ Bonne réponse !")
        else:
            correct_labels = " / ".join(f"**{q['choices'][i]}**" for i in q["answers"])
            st.error(f"❌ Incorrect — Bonne(s) réponse(s) : {correct_labels}")

        with st.expander("💡 Explication", expanded=True):
            st.write(q["explanation"])
            st.caption(f"📚 {q['ref']}")

        st.markdown("")
        if idx < total - 1:
            if st.button("➡️ Question suivante", type="primary", use_container_width=True):
                st.session_state.idx += 1
                st.rerun()
        else:
            if st.button("🏁 Voir mes résultats", type="primary", use_container_width=True):
                st.session_state.done = True
                save_result(st.session_state.username, st.session_state.score, total, st.session_state.domain_scores)
                get_leaderboard.clear()
                st.rerun()

    # Bouton abandon discret
    with st.sidebar:
        st.markdown(f"👤 **{st.session_state.username}**")
        st.markdown(f"🎯 Domaine : `{st.session_state.domain}`")
        st.markdown(f"📊 Score : **{st.session_state.score}/{idx}**")
        st.divider()
        if st.button("🏠 Quitter le quiz", use_container_width=True):
            reset_quiz(keep_settings=False)
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE : RÉSULTATS
# ═══════════════════════════════════════════════════════════════════════════════
else:
    total = len(st.session_state.questions)
    score = st.session_state.score
    pct = round(score / total * 100)

    # Header résultat
    if pct >= 80:
        st.balloons()
        st.success(f"## Excellent ! {score}/{total} — {pct}%")
        st.markdown("Tu es prêt(e) pour l'examen AI-900 ! Vise 80%+ en conditions réelles.")
    elif pct >= 60:
        st.warning(f"## Pas mal ! {score}/{total} — {pct}%")
        st.markdown("Tu progresses bien. Encore un peu de révision sur les domaines faibles.")
    else:
        st.error(f"## {score}/{total} — {pct}%")
        st.markdown("Continue à réviser, tu vas y arriver ! Cible les domaines en rouge ci-dessous.")

    st.divider()

    # Résultats par domaine
    st.subheader("📊 Performance par domaine")
    for dom, data in sorted(st.session_state.domain_scores.items()):
        p = round(data["correct"] / data["total"] * 100)
        color = DOMAIN_COLORS.get(dom, "#555")
        icon = "✅" if p >= 70 else "⚠️" if p >= 50 else "❌"
        col_b, col_stat = st.columns([3, 1])
        with col_b:
            st.markdown(f"{icon} {badge(dom)}", unsafe_allow_html=True)
            st.progress(p / 100)
        with col_stat:
            st.metric("", f"{data['correct']}/{data['total']}", f"{p}%")

    st.divider()

    # Actions
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🔄 Rejouer (même config)", use_container_width=True, type="primary"):
            start_quiz()
            st.rerun()
    with c2:
        # Cibler les domaines faibles automatiquement
        weak = [d for d, data in st.session_state.domain_scores.items()
                if round(data["correct"] / data["total"] * 100) < 70]
        if weak:
            worst = min(st.session_state.domain_scores,
                        key=lambda d: st.session_state.domain_scores[d]["correct"] / st.session_state.domain_scores[d]["total"])
            if st.button(f"🎯 Cibler : {worst}", use_container_width=True):
                st.session_state.domain = worst
                st.session_state.nb = 15
                start_quiz()
                st.rerun()
    with c3:
        if st.button("🏠 Accueil", use_container_width=True):
            reset_quiz(keep_settings=False)
            st.rerun()