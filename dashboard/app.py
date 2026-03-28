import os
import time
import psycopg2
import psycopg2.extras
import streamlit as st
import pandas as pd
from datetime import datetime

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Suporty — Dashboard",
    page_icon="🎫",
    layout="wide",
    initial_sidebar_state="expanded",
)

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://supporty:supporty@db:5432/supporty",
).replace("+asyncpg", "")

# ── DB helpers ─────────────────────────────────────────────────────────────────

@st.cache_resource
def get_conn():
    return psycopg2.connect(DATABASE_URL)


def query(sql: str, params=None) -> pd.DataFrame:
    conn = get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        return pd.DataFrame(rows)
    except Exception:
        conn.rollback()
        # Reconnect on stale connection
        st.cache_resource.clear()
        raise


# ── Styling helpers ────────────────────────────────────────────────────────────

URGENCY_COLOR = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "🟢",
}

STATUS_COLOR = {
    "resolved":  "✅",
    "escalated": "🚨",
}

INTENT_ICON = {
    "billing":         "💳",
    "technical":       "🔧",
    "account":         "👤",
    "onboarding":      "🚀",
    "feature_request": "💡",
    "complaint":       "😤",
    "other":           "📝",
}


def fmt_urgency(u):  return f"{URGENCY_COLOR.get(u, '⚪')} {u or '—'}"
def fmt_status(s):   return f"{STATUS_COLOR.get(s, '❓')} {s or '—'}"
def fmt_intent(i):   return f"{INTENT_ICON.get(i, '📝')} {i or '—'}"
def fmt_conf(c):
    if c is None: return "—"
    bar = "█" * int(c * 10) + "░" * (10 - int(c * 10))
    return f"{bar} {c:.0%}"


# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("🎫 Suporty")
    st.caption("Autonomous Support Architect")
    st.divider()
    page = st.radio("Navigation", ["Overview", "Escalation Queue", "Ticket Detail"])
    st.divider()
    auto_refresh = st.toggle("Auto-refresh (30s)", value=True)
    if st.button("Refresh now"):
        st.cache_data.clear()
        st.rerun()


# ── Data loaders (cached 30s) ──────────────────────────────────────────────────

@st.cache_data(ttl=30)
def load_stats():
    return query(
        """
        SELECT
            COUNT(*)                                          AS total,
            COUNT(*) FILTER (WHERE status = 'resolved')      AS resolved,
            COUNT(*) FILTER (WHERE status = 'escalated')     AS escalated,
            ROUND(AVG(confidence)::numeric, 2)               AS avg_confidence,
            COUNT(*) FILTER (WHERE sensitive = TRUE)         AS sensitive_count,
            COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') AS last_hour
        FROM tickets
        """
    )


@st.cache_data(ttl=30)
def load_recent(limit=50):
    return query(
        """
        SELECT ticket_id, user_id, intent, urgency, confidence, status,
               sensitive, created_at, processed_at
        FROM   tickets
        ORDER  BY created_at DESC
        LIMIT  %s
        """,
        (limit,),
    )


@st.cache_data(ttl=30)
def load_escalations():
    return query(
        """
        SELECT ticket_id, user_id, intent, urgency, confidence,
               escalation_reason, created_at
        FROM   tickets
        WHERE  status = 'escalated'
        ORDER  BY
            CASE urgency
                WHEN 'critical' THEN 1
                WHEN 'high'     THEN 2
                WHEN 'medium'   THEN 3
                ELSE 4
            END,
            created_at DESC
        """
    )


@st.cache_data(ttl=30)
def load_ticket(ticket_id: str):
    df = query(
        "SELECT * FROM tickets WHERE ticket_id = %s",
        (ticket_id,),
    )
    return df.iloc[0] if not df.empty else None


@st.cache_data(ttl=30)
def load_hourly_trend():
    return query(
        """
        SELECT
            DATE_TRUNC('hour', created_at) AS hour,
            COUNT(*)                        AS total,
            COUNT(*) FILTER (WHERE status = 'escalated') AS escalated
        FROM tickets
        WHERE created_at > NOW() - INTERVAL '24 hours'
        GROUP BY 1
        ORDER BY 1
        """
    )


# ── Pages ──────────────────────────────────────────────────────────────────────

def page_overview():
    st.header("Overview")

    try:
        stats = load_stats()
    except Exception as e:
        st.error(f"Cannot reach database: {e}")
        return

    if stats.empty or stats.iloc[0]["total"] == 0:
        st.info("No tickets yet. Send one via `POST /api/v1/webhook/ticket` to get started.")
        return

    row = stats.iloc[0]
    total      = int(row["total"])
    resolved   = int(row["resolved"])
    escalated  = int(row["escalated"])
    avg_conf   = float(row["avg_confidence"] or 0)
    last_hour  = int(row["last_hour"])
    sensitive  = int(row["sensitive_count"])

    # ── Metric cards
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Tickets",     total)
    c2.metric("Resolved",          resolved,  f"{resolved/total:.0%}")
    c3.metric("Escalated",         escalated, f"{escalated/total:.0%}", delta_color="inverse")
    c4.metric("Avg Confidence",    f"{avg_conf:.0%}")
    c5.metric("Last Hour",         last_hour)

    st.divider()

    # ── Trend chart
    trend = load_hourly_trend()
    if not trend.empty:
        trend["hour"] = pd.to_datetime(trend["hour"])
        st.subheader("Ticket volume — last 24 h")
        st.bar_chart(trend.set_index("hour")[["total", "escalated"]])

    st.divider()

    # ── Recent tickets table
    st.subheader("Recent tickets")
    df = load_recent()
    if df.empty:
        st.write("No tickets yet.")
        return

    df["urgency"]    = df["urgency"].apply(fmt_urgency)
    df["status"]     = df["status"].apply(fmt_status)
    df["intent"]     = df["intent"].apply(fmt_intent)
    df["confidence"] = df["confidence"].apply(fmt_conf)
    df["sensitive"]  = df["sensitive"].apply(lambda x: "🔒" if x else "")
    df["created_at"] = pd.to_datetime(df["created_at"]).dt.strftime("%Y-%m-%d %H:%M")

    st.dataframe(
        df[["ticket_id", "user_id", "intent", "urgency", "confidence", "status", "sensitive", "created_at"]],
        use_container_width=True,
        hide_index=True,
    )


def page_escalations():
    st.header("🚨 Escalation Queue")

    try:
        df = load_escalations()
    except Exception as e:
        st.error(f"Cannot reach database: {e}")
        return

    if df.empty:
        st.success("No escalated tickets. All clear!")
        return

    st.caption(f"{len(df)} ticket(s) awaiting human review — sorted by urgency")

    for _, row in df.iterrows():
        urgency_icon = URGENCY_COLOR.get(row.get("urgency"), "⚪")
        with st.expander(
            f"{urgency_icon} [{row['urgency'].upper()}] {row['ticket_id']}  —  {fmt_intent(row['intent'])}",
            expanded=row.get("urgency") in ("critical", "high"),
        ):
            col1, col2 = st.columns(2)
            col1.write(f"**User:** {row['user_id']}")
            col1.write(f"**Confidence:** {row['confidence']:.0%}")
            col2.write(f"**Created:** {row['created_at']}")
            st.error(f"**Escalation reason:** {row['escalation_reason'] or '—'}")


def page_ticket_detail():
    st.header("Ticket Detail")

    try:
        recent = load_recent(limit=200)
    except Exception as e:
        st.error(f"Cannot reach database: {e}")
        return

    if recent.empty:
        st.info("No tickets yet.")
        return

    ticket_ids = recent["ticket_id"].tolist()
    selected = st.selectbox("Select ticket", ticket_ids)

    if not selected:
        return

    ticket = load_ticket(selected)
    if ticket is None:
        st.warning("Ticket not found.")
        return

    st.divider()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Status",     fmt_status(ticket["status"]))
    c2.metric("Intent",     fmt_intent(ticket["intent"]))
    c3.metric("Urgency",    fmt_urgency(ticket["urgency"]))
    c4.metric("Confidence", f"{ticket['confidence']:.0%}" if ticket["confidence"] else "—")

    st.divider()
    st.subheader("Customer message")
    st.text_area("", value=ticket["raw_text"] or "", height=120, disabled=True, label_visibility="collapsed")

    if ticket["status"] == "resolved":
        st.subheader("Resolution")
        st.success(ticket["resolution"] or "—")
    else:
        st.subheader("Escalation reason")
        st.error(ticket["escalation_reason"] or "—")

    st.caption(
        f"Ticket ID: `{ticket['ticket_id']}` · "
        f"User: `{ticket['user_id']}` · "
        f"{'🔒 Sensitive' if ticket['sensitive'] else '🔓 Non-sensitive'} · "
        f"Processed: {ticket['processed_at']}"
    )


# ── Router ─────────────────────────────────────────────────────────────────────

if page == "Overview":
    page_overview()
elif page == "Escalation Queue":
    page_escalations()
elif page == "Ticket Detail":
    page_ticket_detail()

# ── Auto-refresh ───────────────────────────────────────────────────────────────
if auto_refresh:
    time.sleep(30)
    st.rerun()
