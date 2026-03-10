import streamlit as st
import random, json, os, time
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
  .timer-ok { font-size: 1.4em; font-weight: 800; color: #107C10; }
  .timer-warn { font-size: 1.4em; font-weight: 800; color: #FFB900; }
  .timer-danger { font-size: 1.4em; font-weight: 800; color: #D13438; animation: pulse 1s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }
  .exam-banner {
    background: linear-gradient(90deg, #1a1a2e, #2d1b69);
    border: 2px solid #8764B8;
    border-radius: 12px;
    padding: 10px 18px;
    margin-bottom: 16px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
</style>
""", unsafe_allow_html=True)

DOMAIN_COLORS = {
    "Vision": "#0078D4", "NLP": "#107C10", "ML": "#FFB900",
    "Generative AI": "#8764B8", "Responsible AI": "#D13438", "AI Workloads": "#00B7C3"
}
EXAM_DURATION = 45 * 60  # 45 minutes en secondes

def badge(domain):
    color = DOMAIN_COLORS.get(domain, "#555")
    return f"<span class='domain-badge' style='background:{color}'>{domain}</span>"

def ai_box(content, header="✨ MISTRAL AI"):
    st.markdown(f"<div class='ai-box'><div class='ai-header'>{header}</div>{content}</div>", unsafe_allow_html=True)

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

def save_result(username, score, total, domain_scores, mode="practice"):
    if not supabase:
        return
    try:
        supabase.table("quiz_results").insert({
            "username": username, "score": score, "total": total,
            "percentage": round(score / total * 100),
            "domain_scores": json.dumps(domain_scores),
            "mode": mode,
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
    "mode": "practice",  # "practice" | "exam"
    "exam_start_ts": None,
    "debate_idx": -1, "debate_text": None, "debate_response": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

def reset_quiz(keep_settings=True):
    for k in ["idx","score","answers","domain_scores","done",
              "hint","hint_idx","ai_explanation","ai_explanation_idx",
              "coach_report","generated_q","exam_start_ts",
              "debate_idx","debate_text","debate_response"]:
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
    nb = st.session_state.nb if st.session_state.mode == "practice" else min(40, len(pool))
    st.session_state.questions = random.sample(pool, min(nb, len(pool)))
    st.session_state.started = True
    if st.session_state.mode == "exam":
        st.session_state.exam_start_ts = time.time()

# ── Radar chart ───────────────────────────────────────────────────────────────
def render_radar(domain_scores: dict, title: str = "Performance par domaine"):
    import plotly.graph_objects as go

    all_domains = list(DOMAIN_COLORS.keys())
    values = []
    for d in all_domains:
        if d in domain_scores:
            data = domain_scores[d]
            values.append(round(data["correct"] / data["total"] * 100))
        else:
            values.append(0)

    # Fermer le polygone
    cats = all_domains + [all_domains[0]]
    vals = values + [values[0]]

    fig = go.Figure()

    # Zone de passage (80%)
    fig.add_trace(go.Scatterpolar(
        r=[80] * (len(all_domains) + 1),
        theta=cats,
        fill="toself",
        fillcolor="rgba(16, 124, 16, 0.08)",
        line=dict(color="rgba(16,124,16,0.4)", dash="dash", width=1),
        name="Objectif 80%",
        hoverinfo="skip"
    ))

    # Score utilisateur
    fig.add_trace(go.Scatterpolar(
        r=vals,
        theta=cats,
        fill="toself",
        fillcolor="rgba(135, 100, 184, 0.25)",
        line=dict(color="#8764B8", width=3),
        marker=dict(size=8, color="#8764B8"),
        name="Ton score",
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True, range=[0, 100],
                ticksuffix="%", tickfont=dict(size=11),
                gridcolor="rgba(255,255,255,0.1)",
                linecolor="rgba(255,255,255,0.1)",
            ),
            angularaxis=dict(
                tickfont=dict(size=12, color="white"),
                gridcolor="rgba(255,255,255,0.15)",
            ),
            bgcolor="rgba(26,26,46,0.8)",
        ),
        paper_bgcolor="rgba(26,26,46,1)",
        plot_bgcolor="rgba(26,26,46,1)",
        font=dict(color="white"),
        title=dict(text=title, font=dict(size=16, color="white"), x=0.5),
        legend=dict(
            orientation="h", y=-0.15, x=0.5, xanchor="center",
            font=dict(color="white", size=11)
        ),
        margin=dict(t=60, b=40, l=40, r=40),
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Timer ─────────────────────────────────────────────────────────────────────
def render_timer():
    if st.session_state.exam_start_ts is None:
        return False
    elapsed = time.time() - st.session_state.exam_start_ts
    remaining = EXAM_DURATION - elapsed
    if remaining <= 0:
        return True  # Temps écoulé

    mins = int(remaining // 60)
    secs = int(remaining % 60)
    label = f"{mins:02d}:{secs:02d}"

    if remaining > 600:
        css_class = "timer-ok"
    elif remaining > 300:
        css_class = "timer-warn"
    else:
        css_class = "timer-danger"

    st.markdown(
        f"<div class='exam-banner'>"
        f"<span style='color:#b39ddb;font-weight:700'>⏱ MODE EXAMEN</span>"
        f"<span class='{css_class}'>{label}</span>"
        f"<span style='color:#888;font-size:0.85em'>{st.session_state.score}/{st.session_state.idx} pts</span>"
        f"</div>",
        unsafe_allow_html=True
    )
    return False

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

    # Mode selector
    st.markdown("#### Mode de quiz")
    mode_col1, mode_col2 = st.columns(2)
    with mode_col1:
        practice_selected = st.session_state.mode == "practice"
        if st.button(
            "📝 Mode Pratique" + (" ✓" if practice_selected else ""),
            use_container_width=True,
            type="primary" if practice_selected else "secondary"
        ):
            st.session_state.mode = "practice"
            st.rerun()
    with mode_col2:
        exam_selected = st.session_state.mode == "exam"
        if st.button(
            "⏱ Mode Examen" + (" ✓" if exam_selected else ""),
            use_container_width=True,
            type="primary" if exam_selected else "secondary"
        ):
            st.session_state.mode = "exam"
            st.rerun()

    if st.session_state.mode == "practice":
        st.session_state.nb = st.slider("📝 Nombre de questions", 5, min(30, len(QUESTIONS)), st.session_state.nb)
        st.caption("✅ Feedback immédiat après chaque réponse + indices Mistral disponibles")
    else:
        st.info("⏱ **40 questions · 45 minutes · Pas de feedback pendant l'examen** — Résultats et radar chart à la fin.")

    st.markdown("")
    disabled = not st.session_state.username.strip()
    label = "Lancer le quiz" if st.session_state.mode == "practice" else "⏱ Démarrer l'examen"
    if st.button(label, type="primary", use_container_width=True, disabled=disabled):
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
            mode_tag = f" `{row.get('mode','')}` " if row.get("mode") == "exam" else " "
            st.markdown(
                f"{icon} **{row['username']}**{mode_tag}— "
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
    is_exam = st.session_state.mode == "exam"

    # Timer exam + auto-submit si temps écoulé
    if is_exam:
        time_up = render_timer()
        if time_up:
            st.warning("⏰ Temps écoulé ! Fin de l'examen.")
            st.session_state.done = True
            save_result(st.session_state.username, st.session_state.score, total, st.session_state.domain_scores, mode="exam")
            get_leaderboard.clear()
            st.rerun()
        # Auto-refresh toutes les secondes en mode exam
        time.sleep(1)
        st.rerun() if idx in st.session_state.answers else None
    else:
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
        # Indice Mistral (mode pratique uniquement)
        if not is_exam:
            if st.button("💡 Indice Mistral", key=f"hint_btn_{idx}"):
                if st.session_state.hint_idx != idx:
                    with st.spinner("Mistral réfléchit…"):
                        prompt = f"""Question AI-900 : "{q['question']}"
Choix : {json.dumps(q['choices'], ensure_ascii=False)}
Donne un indice court (2-3 phrases max) qui aide à trouver la bonne réponse SANS la révéler. Reste orienté Azure."""
                        st.session_state.hint = mistral_chat(prompt, system="Tu es un formateur Microsoft Azure bienveillant.")
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

            # En mode exam : question suivante automatique
            if is_exam:
                if idx < total - 1:
                    st.session_state.idx += 1
                else:
                    st.session_state.done = True
                    save_result(st.session_state.username, st.session_state.score, total, st.session_state.domain_scores, mode="exam")
                    get_leaderboard.clear()
            st.rerun()

    else:
        # Mode pratique : feedback immédiat
        if not is_exam:
            res = st.session_state.answers[idx]
            if res["correct"]:
                st.success("✅ Bonne réponse !")
            else:
                correct_labels = " / ".join(f"**{q['choices'][i]}**" for i in q["answers"])
                st.error(f"❌ Incorrect — Bonne(s) réponse(s) : {correct_labels}")

            with st.expander("📚 Explication officielle", expanded=True):
                st.write(q["explanation"])
                st.caption(f"📖 {q['ref']}")

            # Explication enrichie Mistral
            if not res["correct"]:
                if st.button("🧠 Explication approfondie Mistral", key=f"explain_btn_{idx}"):
                    if st.session_state.ai_explanation_idx != idx:
                        with st.spinner("Mistral prépare une explication…"):
                            correct_ans = [q["choices"][i] for i in q["answers"]]
                            prompt = f"""Question AI-900 : "{q['question']}"
Bonne réponse : {correct_ans}
Explication officielle : {q['explanation']}
Enrichis avec : 1) une analogie concrète 2) un exemple Azure réel 3) un moyen mnémotechnique.
Réponds en français, de façon engageante."""
                            st.session_state.ai_explanation = mistral_chat(prompt, system="Tu es un expert Azure certifié et formateur passionné.")
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
                    save_result(st.session_state.username, st.session_state.score, total, st.session_state.domain_scores, mode="practice")
                    get_leaderboard.clear()
                    st.rerun()

    with st.sidebar:
        st.markdown(f"👤 **{st.session_state.username}**")
        mode_label = "⏱ Examen" if is_exam else "📝 Pratique"
        st.markdown(f"🎮 {mode_label}")
        st.markdown(f"🎯 `{st.session_state.domain}`")
        if not is_exam:
            st.markdown(f"📊 **{st.session_state.score}/{idx}**")
        st.divider()
        if st.button("🏠 Quitter", use_container_width=True):
            reset_quiz(keep_settings=False)
            st.rerun()

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE : RÉSULTATS
# ═══════════════════════════════════════════════════════════════════════════════
else:
    total = len(st.session_state.questions)
    score = st.session_state.score
    pct = round(score / total * 100)
    is_exam = st.session_state.mode == "exam"

    if is_exam:
        st.markdown("## ⏱ Résultats — Mode Examen")
    else:
        st.markdown("## 📊 Résultats")

    if pct >= 80:
        st.balloons()
        st.success(f"🎉 **Excellent ! {score}/{total} — {pct}%** — Tu es prêt(e) pour l'examen !")
    elif pct >= 60:
        st.warning(f"💪 **Pas mal ! {score}/{total} — {pct}%** — Encore un peu de révision.")
    else:
        st.error(f"📚 **{score}/{total} — {pct}%** — Continue, tu vas y arriver !")

    st.divider()

    # ── RADAR CHART ───────────────────────────────────────────────────────────
    if st.session_state.domain_scores:
        render_radar(st.session_state.domain_scores,
                     title=f"Radar de performance — {st.session_state.username}")
        st.caption("La zone verte indique l'objectif de 80% recommandé pour chaque domaine.")

    st.divider()

    # Détail par domaine
    st.subheader("Performance par domaine")
    domain_summary = []
    for dom, data in sorted(st.session_state.domain_scores.items()):
        p = round(data["correct"] / data["total"] * 100)
        domain_summary.append({"domain": dom, "pct": p, "correct": data["correct"], "total": data["total"]})
        icon = "✅" if p >= 70 else "⚠️" if p >= 50 else "❌"
        col_b, col_stat = st.columns([3, 1])
        with col_b:
            st.markdown(f"{icon} {badge(dom)}", unsafe_allow_html=True)
            st.progress(p / 100)
        with col_stat:
            st.metric("", f"{data['correct']}/{data['total']}", f"{p}%")

    st.divider()

    # ── COACH MISTRAL ─────────────────────────────────────────────────────────
    st.subheader("🎓 Coach IA personnalisé")
    if st.button("✨ Générer mon plan de révision Mistral", type="primary", use_container_width=True):
        with st.spinner("Mistral analyse tes résultats…"):
            results_str = "\n".join([f"- {d['domain']} : {d['correct']}/{d['total']} ({d['pct']}%)" for d in domain_summary])
            mode_ctx = "en mode examen simulé (sans feedback)" if is_exam else "en mode pratique"
            prompt = f"""Étudiant : {st.session_state.username}
Mode : {mode_ctx}
Score global : {pct}% ({score}/{total})
Résultats par domaine :
{results_str}

Génère un plan de révision personnalisé et motivant en français avec :
1. Diagnostic rapide (2-3 phrases)
2. Les 2-3 domaines prioritaires avec ressources Microsoft Learn spécifiques
3. Planning concret sur 2 jours pour atteindre 80%+
4. Message de motivation personnalisé pour {st.session_state.username}"""
            st.session_state.coach_report = mistral_chat(prompt, system="Tu es un coach expert certifications Microsoft Azure, bienveillant et précis.")

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
        if domain_summary:
            worst = min(domain_summary, key=lambda d: d["pct"])["domain"]
            if st.button(f"🎯 Cibler : {worst}", use_container_width=True):
                st.session_state.domain = worst
                st.session_state.mode = "practice"
                st.session_state.nb = 15
                start_quiz()
                st.rerun()
    with c3:
        if st.button("🏠 Accueil", use_container_width=True):
            reset_quiz(keep_settings=False)
            st.rerun()