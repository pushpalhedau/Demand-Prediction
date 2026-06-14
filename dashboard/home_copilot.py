import streamlit as st
import plotly.graph_objects as go
import os
import json

from database.queries import (
    get_copilot_context_summary,
    get_revenue_collections_trend,
    get_inventory_breakdown,
    get_lead_funnel_summary,
    get_project_health_scores,
)
from utils.helpers import get_re_colors, plotly_dark_layout, section_header


# ── Example questions ──────────────────────────────────────
EXAMPLE_CHIPS = [
    "Which project generated highest revenue this month?",
    "Why are sales declining? What should we do?",
    "Show me high-risk construction projects",
    "Which emirate should we prioritize for next launch?",
]


def _call_groq(context_json: str, user_query: str) -> dict:
    try:
        from groq import Groq
        api_key = os.getenv("XAI_API_KEY")
        if not api_key:
            raise ValueError("XAI_API_KEY not set")

        client = Groq(api_key=api_key)
        system_msg = (
            "You are the AI Business Copilot for a UAE real estate CEO. "
            "Answer questions using the live business data provided. Be concise and actionable. "
            f"Current business data:\n{context_json}\n\n"
            "Respond ONLY in valid JSON with this exact structure (no markdown, no explanation outside JSON):\n"
            '{"answer": "...", "chart_type": "bar|line|pie|none", '
            '"data_key": "revenue|inventory|leads|projects|none", "recommendation": "..."}'
        )
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_query},
            ],
            temperature=0.3,
            max_tokens=800,
        )
        raw = resp.choices[0].message.content.strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        return {
            "answer": f"AI service unavailable ({e}). Showing data-driven answer below.",
            "chart_type": "none",
            "data_key": "none",
            "recommendation": "Check XAI_API_KEY in .env or retry.",
            "_fallback": True,
        }


def _render_chart(data_key: str, session, colors: dict):
    if data_key == "revenue":
        df = get_revenue_collections_trend(session, months=12)
        if df.empty:
            return
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df["period_date"], y=df["revenue_booked_aed"] / 1e6,
            name="Revenue", line=dict(color=colors["primary"], width=2.5),
            fill="tozeroy", fillcolor="rgba(16,185,129,0.07)",
        ))
        fig.add_trace(go.Scatter(
            x=df["period_date"], y=df["collections_received_aed"] / 1e6,
            name="Collections", line=dict(color=colors["gold"], width=2, dash="dot"),
        ))
        fig.update_layout(**plotly_dark_layout("Revenue & Collections (AED M)", 300))
        st.plotly_chart(fig, use_container_width=True)

    elif data_key == "inventory":
        df = get_inventory_breakdown(session)
        if df.empty:
            return
        fig = go.Figure()
        for col, color, label in [
            ("available_units", colors["primary"], "Available"),
            ("booked_units", colors["gold"], "Booked"),
            ("registered_units", colors["indigo"], "Registered"),
        ]:
            fig.add_trace(go.Bar(y=df["emirate"], x=df[col], name=label,
                                 orientation="h", marker_color=color))
        layout = plotly_dark_layout("Inventory by Emirate", 300)
        layout["barmode"] = "stack"
        fig.update_layout(**layout)
        st.plotly_chart(fig, use_container_width=True)

    elif data_key == "leads":
        df = get_lead_funnel_summary(session)
        if df.empty:
            return
        fig = go.Figure(go.Bar(
            x=df["lead_stage"], y=df["count"],
            marker_color=colors["colors_seq"][:len(df)],
        ))
        fig.update_layout(**plotly_dark_layout("Lead Funnel by Stage", 300))
        st.plotly_chart(fig, use_container_width=True)

    elif data_key == "projects":
        df = get_project_health_scores(session)
        if df.empty:
            return
        df = df.sort_values("health_score")

        def _c(s):
            if s >= 80:
                return colors["primary"]
            if s >= 60:
                return colors["gold"]
            return colors["rose"]

        fig = go.Figure(go.Bar(
            y=df["project_name"], x=df["health_score"],
            orientation="h",
            marker_color=[_c(s) for s in df["health_score"]],
            text=[f"{s:.0f}" for s in df["health_score"]],
            textposition="auto",
        ))
        layout = plotly_dark_layout("Project Health Scores", 300)
        layout["xaxis"]["range"] = [0, 100]
        fig.update_layout(**layout)
        st.plotly_chart(fig, use_container_width=True)


def render_ai_copilot(session):
    colors = get_re_colors()

    # ── Page Header ───────────────────────────────────────
    st.markdown("""
    <div style="margin-bottom:24px; padding-bottom:14px;
                border-bottom:1px solid rgba(255,255,255,0.06);">
        <h2 style="margin:0; font-size:24px; font-weight:800; color:#f0f4f8;
                   font-family:'Outfit',sans-serif;">
            AI Executive Copilot
        </h2>
        <p style="margin:4px 0 0 0; font-size:12px; color:#6b7280;">
            Ask anything about your business — powered by Groq LLaMA 3.3 70B
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Session state for query
    if "copilot_query" not in st.session_state:
        st.session_state["copilot_query"] = ""
    if "copilot_result" not in st.session_state:
        st.session_state["copilot_result"] = None

    left_col, right_col = st.columns([35, 65])

    # ── Left: Search Interface ────────────────────────────
    with left_col:
        section_header("Ask Your Business")

        query_input = st.text_area(
            label="Your question",
            value=st.session_state["copilot_query"],
            placeholder="e.g. Which project is most at risk of delay?",
            height=100,
            label_visibility="collapsed",
        )

        st.markdown(
            "<p style='font-size:11px; color:#4b5563; font-weight:600; "
            "text-transform:uppercase; letter-spacing:0.08em; margin:12px 0 8px 0;'>"
            "Try an example</p>",
            unsafe_allow_html=True,
        )

        for chip in EXAMPLE_CHIPS:
            if st.button(chip, key=f"chip_{chip[:20]}", use_container_width=True):
                st.session_state["copilot_query"] = chip
                st.rerun()

        st.markdown("<div style='margin-top:14px'></div>", unsafe_allow_html=True)

        submitted = st.button(
            "Get AI Answer",
            type="primary",
            use_container_width=True,
        )

        if submitted and query_input.strip():
            st.session_state["copilot_query"] = query_input
            with st.spinner("Analyzing your business data..."):
                try:
                    context = get_copilot_context_summary(session)
                except Exception:
                    context = "{}"
                result = _call_groq(context, query_input.strip())
            st.session_state["copilot_result"] = result
            st.rerun()

        # API status indicator
        api_key_present = bool(os.getenv("XAI_API_KEY"))
        if api_key_present:
            st.markdown(
                "<div style='margin-top:16px; font-size:11px; color:#10b981;'>"
                "● Groq API connected</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                "<div style='margin-top:16px; font-size:11px; color:#f59e0b;'>"
                "[!] XAI_API_KEY not set — fallback mode active</div>",
                unsafe_allow_html=True,
            )

    # ── Right: Response Area ──────────────────────────────
    with right_col:
        result = st.session_state.get("copilot_result")

        if result is None:
            st.markdown("""
            <div style="border:1px dashed rgba(255,255,255,0.08);
                        border-radius:12px; padding:48px 32px;
                        text-align:center; margin-top:12px;">
                <div style="font-size:16px; font-weight:700; color:#f0f4f8; margin-bottom:8px;">
                    AI Copilot Ready
                </div>
                <div style="font-size:13px; color:#4b5563; line-height:1.6; max-width:380px; margin:0 auto;">
                    Ask any question about your UAE real estate portfolio — revenue, projects,
                    leads, inventory, or market trends. Live data analysis, instant response.
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            # Show the query
            q = st.session_state.get("copilot_query", "")
            if q:
                st.markdown(f"""
                <div style="background:rgba(99,102,241,0.08); border:1px solid rgba(99,102,241,0.2);
                            border-radius:8px; padding:10px 14px; margin-bottom:16px;">
                    <span style="font-size:11px; color:#6366f1; font-weight:700; text-transform:uppercase;">
                        Your Question
                    </span>
                    <div style="font-size:14px; color:#e2e8f0; margin-top:4px;">{q}</div>
                </div>
                """, unsafe_allow_html=True)

            # Answer
            answer = result.get("answer", "")
            if answer:
                st.markdown(f"""
                <div class="insight-box" style="padding:16px; margin-bottom:16px;">
                    <div style="font-size:11px; color:#10b981; font-weight:700;
                                text-transform:uppercase; margin-bottom:8px;">
                        AI Analysis
                    </div>
                    <div style="font-size:14px; color:#e2e8f0; line-height:1.7;">{answer}</div>
                </div>
                """, unsafe_allow_html=True)

            # Chart (if requested)
            data_key = result.get("data_key", "none")
            chart_type = result.get("chart_type", "none")
            if data_key != "none" and chart_type != "none":
                try:
                    _render_chart(data_key, session, colors)
                except Exception as e:
                    st.warning(f"Chart could not load: {e}")

            # Recommendation
            rec = result.get("recommendation", "")
            if rec:
                st.markdown(f"""
                <div class="warning-box" style="padding:14px; margin-top:12px;">
                    <div style="font-size:11px; color:#f59e0b; font-weight:700;
                                text-transform:uppercase; margin-bottom:6px;">
                        CEO Recommendation
                    </div>
                    <div style="font-size:13px; color:#e2e8f0; line-height:1.6;">{rec}</div>
                </div>
                """, unsafe_allow_html=True)

            # Clear button
            st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
            if st.button("Clear & Ask Again", key="clear_copilot"):
                st.session_state["copilot_query"] = ""
                st.session_state["copilot_result"] = None
                st.rerun()
