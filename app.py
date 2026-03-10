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

# ── Mistral ───────────────────────────────────────────────────────────────────
try:
    from mistralai import Mistral
    _mistral_key = os.environ.get("MISTRAL_API_KEY", "")
    mistral_client = Mistral(api_key=_mistral_key) if _mistral_key else None
except Exception:
    mistral_client = None

MISTRAL_MODEL = "mistral-small-latest"

def mistral_chat(prompt: str, system: str = "") -> str:
    if not mistral_client:
        return "⚠️ Mistral non configuré (MISTRAL_API_KEY manquant)."
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    try:
        res = mistral_client.chat.complete(model=MISTRAL_MODEL, messages=messages)
        return res.choices[0].message.content.strip()
    except Exception as e:
        return f"⚠️ Erreur Mistral : {e}"

# ── Config ────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="AI-900 Practice Quiz",
    page_icon="🤖",
    layout="centered",
    initial_sidebar_state="collapsed"
)

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
  .ai-box {
    background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
    border: 1px solid #8764B8;
    border-radius: 12px;
    padding: 16px 20px;
    margin-top: 12px;
    color: #e0e0e0;
  }
  .ai-box .ai-header {
    color: #b39ddb;
    font-size: 0.82em;
    font-weight: 700;
    letter-spacing: 0.08em;
    margin-bottom: 8px;
  }
</style>
""", unsafe_allow_html=True)

DOMAIN_COLORS = {
    "Vision": "#0078D4", "NLP": "#107C10", "ML": "#FFB900",
    "Generative AI": "#8764B8", "Responsible AI": "#D13438", "AI Workloads": "#00B7C3"
}

def badge(domain):
    color = DOMAIN_COLORS.get(domain, "#555")
    return f"<span class='domain-badge' style='background:{color}'>{domain}</span>"

def ai_box(content: str, header: str = "✨ MISTRAL AI"):
    st.markdown(
        f"<div class='ai-box'><div class='ai-header'>{header}</div>{content}</div>",
        unsafe_allow_html=True
    )

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
            "username": username, "score": score, "total": total,
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
    "domain": "Tous les domaines", "username": "", "nb": 15,
    "hint": None, "hint_idx": -1,
    "ai_explanation": None, "ai_explanation_idx": -1,
    "coach_report": None,
    "generated_q": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

def reset_quiz(keep_settings=True):
    for k in ["idx","score","answers","domain_scores","done","hint","hint_idx","ai_explanation","ai_explanation_idx","coach_report","generated_q"]:
        st.session_state[k] = DEFAULTS[k]
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
    st.markdown("**Microsoft Azure AI Fundamentals** — Propulsé par Mistral AI ✨")
    st.divider()

    c1, c2, c3 = st.columns(3)
    c1.metric("Questions", len(QUESTIONS))
    c2.metric("Domaines", len(set(q["domain"] for q in QUESTIONS)))
    c3.metric("Score cible", "≥ 700/1000")

    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        st.session_state.username = st.text_input("👤 Ton prénom", value=st.session_state.username, placeholder="Ex : Mathieu")
    with col2:
        st.session_state.domain = st.selectbox("🎯 Domaine", DOMAINS,
            index=DOMAINS.index(st.session_state.domain) if st.session_state.domain in DOMAINS else 0)

    st.session_state.nb = st.slider("📝 Nombre de questions", 5, min(30, len(QUESTIONS)), st.session_state.nb)

    if st.session_state.domain != "Tous les domaines":
        n = sum(1 for q in QUESTIONS if q["domain"] == st.session_state.domain)
        st.markdown(f"{badge(st.session_state.domain)} **{n} questions** disponibles", unsafe_allow_html=True)

    st.markdown("")
    disabled = not st.session_state.username.strip()
    if st.button("🚀 Lancer le quiz", type="primary", use_container_width=True, disabled=disabled):
        start_quiz()
        st.rerun()
    if disabled:
        st.caption("⬆️ Entre ton prénom pour commencer")

    # ── Brique Mistral 3 : Génération de question à la volée ──────────────────
    st.divider()
    st.markdown("### ✨ Génère une question Mistral AI")
    st.caption("Mistral crée une question inédite sur le domaine de ton choix — hors bank officielle.")

    gen_domain = st.selectbox("Domaine", [d for d in DOMAINS if d != "Tous les domaines"], key="gen_domain")
    gen_difficulty = st.select_slider("Difficulté", ["Facile", "Moyen", "Difficile"], value="Moyen")

    if st.button("⚡ Générer une question", use_container_width=True):
        st.session_state.generated_q = None
        with st.spinner("Mistral génère une question…"):
            prompt = f"""Génère une question QCM de niveau {gen_difficulty} sur le domaine "{gen_domain}" pour la certification Microsoft AI-900.
Format JSON strict :
{{
  "question": "...",
  "choices": ["A. ...", "B. ...", "C. ...", "D. ..."],
  "answer_index": 0,
  "explanation": "..."
}}
Réponds UNIQUEMENT avec le JSON, sans markdown, sans texte autour."""
            raw = mistral_chat(prompt, system="Tu es un expert Microsoft Azure AI certifié. Tu génères des QCM précis et pédagogiques en français.")
            try:
                clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
                st.session_state.generated_q = json.loads(clean)
            except Exception:
                st.session_state.generated_q = {"error": raw}

    if st.session_state.generated_q:
        gq = st.session_state.generated_q
        if "error" in gq:
            st.error(f"Parsing échoué : {gq['error']}")
        else:
            st.markdown(f"**{gq['question']}**")
            for c in gq["choices"]:
                st.markdown(f"- {c}")
            with st.expander("Voir la réponse"):
                ans_idx = gq.get("answer_index", 0)
                st.success(f"✅ {gq['choices'][ans_idx]}")
                st.info(f"💡 {gq['explanation']}")

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

    if idx >= len(questions):
        st.session_state.idx = 0
        st.rerun()

    q = questions[idx]
    total = len(questions)
    multi = len(q["answers"]) > 1

    col_prog, col_score = st.columns([3, 1])
    with col_prog:
        st.markdown(f"<p style='font-size:0.82em;color:#888'>Question {idx+1} sur {total}</p>", unsafe_allow_html=True)
        st.progress(idx / total)
    with col_score:
        st.metric("Score", f"{st.session_state.score}/{idx}")

    st.markdown(badge(q["domain"]), unsafe_allow_html=True)
    st.markdown(f"### {q['question']}")

    if multi:
        st.info("✏️ Plusieurs bonnes réponses — cochez toutes les bonnes.")

    answered = idx in st.session_state.answers

    if not answered:
        # ── Brique Mistral 1 : Indice dynamique ───────────────────────────────
        col_hint, _ = st.columns([1, 3])
        with col_hint:
            if st.button("💡 Indice Mistral", key=f"hint_btn_{idx}"):
                if st.session_state.hint_idx != idx:
                    with st.spinner("Mistral réfléchit…"):
                        prompt = f"""Question AI-900 : "{q['question']}"
Choix : {json.dumps(q['choices'], ensure_ascii=False)}
Donne un indice court (2-3 phrases max) qui aide à trouver la bonne réponse SANS la révéler directement. Reste orienté Azure."""
                        st.session_state.hint = mistral_chat(prompt, system="Tu es un formateur Microsoft Azure bienveillant. Tu donnes des indices pédagogiques sans spoiler.")
                        st.session_state.hint_idx = idx

        if st.session_state.hint and st.session_state.hint_idx == idx:
            ai_box(st.session_state.hint, "💡 INDICE MISTRAL")

        st.markdown("")

        if multi:
            selected = [i for i, c in enumerate(q["choices"]) if st.checkbox(c, key=f"cb{idx}_{i}")]
        else:
            choice = st.radio("", q["choices"], key=f"r{idx}", index=None, label_visibility="collapsed")
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
            st.session_state.hint = None
            st.rerun()

    else:
        res = st.session_state.answers[idx]
        if res["correct"]:
            st.success("✅ Bonne réponse !")
        else:
            correct_labels = " / ".join(f"**{q['choices'][i]}**" for i in q["answers"])
            st.error(f"❌ Incorrect — Bonne(s) réponse(s) : {correct_labels}")

        # Explication standard
        with st.expander("📚 Explication officielle", expanded=True):
            st.write(q["explanation"])
            st.caption(f"📖 {q['ref']}")

        # ── Brique Mistral 2 : Explication enrichie ───────────────────────────
        if not res["correct"]:
            if st.button("🧠 Explication approfondie par Mistral", key=f"explain_btn_{idx}"):
                if st.session_state.ai_explanation_idx != idx:
                    with st.spinner("Mistral prépare une explication…"):
                        correct_ans = [q["choices"][i] for i in q["answers"]]
                        prompt = f"""Question AI-900 : "{q['question']}"
Bonne réponse : {correct_ans}
Explication officielle : {q['explanation']}

Enrichis cette explication en 3-4 phrases avec :
1. Une analogie concrète du quotidien
2. Un exemple d'utilisation réelle sur Azure
3. Un moyen mnémotechnique pour retenir la bonne réponse
Réponds en français, de façon pédagogique et engageante."""
                        st.session_state.ai_explanation = mistral_chat(
                            prompt,
                            system="Tu es un expert Azure certifié et formateur passionné. Tu expliques avec des analogies concrètes et du storytelling."
                        )
                        st.session_state.ai_explanation_idx = idx

            if st.session_state.ai_explanation and st.session_state.ai_explanation_idx == idx:
                ai_box(st.session_state.ai_explanation.replace("\n", "<br>"), "🧠 EXPLICATION MISTRAL AI")

        st.markdown("")
        if idx < total - 1:
            if st.button("➡️ Question suivante", type="primary", use_container_width=True):
                st.session_state.idx += 1
                st.session_state.ai_explanation = None
                st.rerun()
        else:
            if st.button("🏁 Voir mes résultats", type="primary", use_container_width=True):
                st.session_state.done = True
                save_result(st.session_state.username, st.session_state.score, total, st.session_state.domain_scores)
                get_leaderboard.clear()
                st.rerun()

    with st.sidebar:
        st.markdown(f"👤 **{st.session_state.username}**")
        st.markdown(f"🎯 `{st.session_state.domain}`")
        st.markdown(f"📊 **{st.session_state.score}/{idx}**")
        st.divider()
        if st.button("🏠 Quitter", use_container_width=True):
            reset_quiz(keep_settings=False)
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE : RÉSULTATS + COACH MISTRAL
# ═══════════════════════════════════════════════════════════════════════════════
else:
    total = len(st.session_state.questions)
    score = st.session_state.score
    pct = round(score / total * 100)

    if pct >= 80:
        st.balloons()
        st.success(f"## 🎉 Excellent ! {score}/{total} — {pct}%")
        st.markdown("Tu es prêt(e) pour l'examen AI-900 !")
    elif pct >= 60:
        st.warning(f"## 💪 Pas mal ! {score}/{total} — {pct}%")
        st.markdown("Encore un peu de révision sur les domaines faibles.")
    else:
        st.error(f"## 📚 {score}/{total} — {pct}%")
        st.markdown("Continue à réviser, tu vas y arriver !")

    st.divider()

    # Résultats par domaine
    st.subheader("📊 Performance par domaine")
    domain_summary = []
    for dom, data in sorted(st.session_state.domain_scores.items()):
        p = round(data["correct"] / data["total"] * 100)
        domain_summary.append({"domain": dom, "pct": p, "correct": data["correct"], "total": data["total"]})
        color = DOMAIN_COLORS.get(dom, "#555")
        icon = "✅" if p >= 70 else "⚠️" if p >= 50 else "❌"
        col_b, col_stat = st.columns([3, 1])
        with col_b:
            st.markdown(f"{icon} {badge(dom)}", unsafe_allow_html=True)
            st.progress(p / 100)
        with col_stat:
            st.metric("", f"{data['correct']}/{data['total']}", f"{p}%")

    st.divider()

    # ── Brique Mistral 3 : Coach personnalisé ─────────────────────────────────
    st.subheader("🎓 Coach IA personnalisé")
    if st.button("✨ Générer mon plan de révision Mistral", type="primary", use_container_width=True):
        with st.spinner("Mistral analyse tes résultats et prépare ton plan…"):
            results_str = "\n".join([f"- {d['domain']} : {d['correct']}/{d['total']} ({d['pct']}%)" for d in domain_summary])
            prompt = f"""Un étudiant prépare la certification Microsoft AI-900.
Prénom : {st.session_state.username}
Score global : {pct}% ({score}/{total})
Résultats par domaine :
{results_str}

Génère un plan de révision personnalisé et motivant en français avec :
1. Un diagnostic rapide de son niveau actuel (2-3 phrases)
2. Les 2-3 domaines prioritaires à réviser avec pour chacun : pourquoi c'est important + 2 ressources Microsoft Learn spécifiques
3. Un planning concret sur 2 jours pour atteindre 80%+
4. Un message de motivation personnalisé pour {st.session_state.username}
Sois précis, concret et encourageant."""
            st.session_state.coach_report = mistral_chat(
                prompt,
                system="Tu es un coach expert en certifications Microsoft Azure, bienveillant et motivant. Tu donnes des conseils actionnables et personnalisés."
            )

    if st.session_state.coach_report:
        ai_box(st.session_state.coach_report.replace("\n", "<br>"), "🎓 TON COACH MISTRAL AI")

    st.divider()

    # Actions
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🔄 Rejouer", use_container_width=True, type="primary"):
            start_quiz()
            st.rerun()
    with c2:
        weak_domains = [d["domain"] for d in domain_summary if d["pct"] < 70]
        if weak_domains:
            worst = min(domain_summary, key=lambda d: d["pct"])["domain"]
            if st.button(f"🎯 Cibler : {worst}", use_container_width=True):
                st.session_state.domain = worst
                st.session_state.nb = 15
                start_quiz()
                st.rerun()
    with c3:
        if st.button("🏠 Accueil", use_container_width=True):
            reset_quiz(keep_settings=False)
            st.rerun()