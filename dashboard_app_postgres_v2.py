import streamlit as st
import psycopg2
import pandas as pd
import os
from datetime import datetime

# ============================================================
# IBOP Live Dashboard — Postgres version (Neon / Supabase)
# ============================================================
# Same dashboard as the original, pointed at a free Postgres
# database instead of Azure SQL. Deploy this on Streamlit
# Community Cloud so it's viewable from any browser, including
# an office laptop with no Python installed.
# ============================================================

st.set_page_config(page_title="IBOP - Live Ops Dashboard", layout="wide")

# ---- Midnight Executive theme (navy/amber) ----
st.markdown("""
<style>
    .stApp { background-color: #0B1220; color: #E8E8E8; }
    [data-testid="stMetricValue"] { color: #F5A623; }
    [data-testid="stMetricLabel"] { color: #9BA5B5; }
    h1, h2, h3 { color: #F5A623 !important; }
    .stDataFrame { background-color: #131B2E; }
    div[data-testid="stSidebar"] { background-color: #0B1220; }
</style>
""", unsafe_allow_html=True)


def get_credential(key):
    """Works both locally (environment variables) and on Streamlit
    Community Cloud (st.secrets), without needing two versions of this file."""
    if key in st.secrets:
        return st.secrets[key]
    return os.environ[key]


@st.cache_resource
def get_connection():
    # DATABASE_URL looks like: postgresql://user:password@host/dbname?sslmode=require
    return psycopg2.connect(get_credential("DATABASE_URL"))


def run_query(query):
    conn = get_connection()
    return pd.read_sql(query, conn)


st.title("IBOP — Intelligent Backup Operations Platform")
st.caption(f"Live view — last loaded {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

if st.button("Refresh now"):
    st.cache_resource.clear()
    st.rerun()

# ---- Top metrics row ----
jobs_df = run_query('SELECT * FROM "jobs"')
tickets_df = run_query('SELECT * FROM "tickets"')
risk_df = run_query('SELECT * FROM "riskscores"')

# Postgres lowercases unquoted identifiers, so normalize column names for display
jobs_df.columns = [c.capitalize() if c != "jobid" else "JobId" for c in jobs_df.columns]
tickets_df.columns = [c.capitalize() if c != "jobid" and c != "ticketid" and c != "jirakey"
                       else {"jobid": "JobId", "ticketid": "TicketId", "jirakey": "JiraKey"}.get(c, c)
                       for c in tickets_df.columns]
risk_df.columns = [c.capitalize() if c != "jobid" else "JobId" for c in risk_df.columns]

total_jobs = len(jobs_df)
success_rate = (jobs_df["Exitcode"].eq(0).sum() / total_jobs * 100) if total_jobs else 0
open_tickets = len(tickets_df[tickets_df["Status"] == "Open"]) if len(tickets_df) else 0
resolved_tickets = len(tickets_df[tickets_df["Status"] == "Resolved"]) if len(tickets_df) else 0
escalated_tickets = len(tickets_df[tickets_df["Status"] == "Escalated"]) if len(tickets_df) else 0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Total Jobs", total_jobs)
col2.metric("Success Rate", f"{success_rate:.1f}%")
col3.metric("Open Tickets", open_tickets)
col4.metric("Resolved", resolved_tickets)
col5.metric("Escalated", escalated_tickets)

st.divider()

# ---- Tickets table (the centerpiece - shows AI diagnosis + action taken) ----
st.subheader("Tickets — AI Diagnosis & Actions")
if len(tickets_df):
    cols = [c for c in ["JiraKey", "Assignedteam", "Rootcause", "Confidence", "Fixablebyback", "Status"]
            if c in tickets_df.columns]
    display_tickets = tickets_df.sort_values("TicketId", ascending=False) if "TicketId" in tickets_df.columns else tickets_df
    st.dataframe(display_tickets, use_container_width=True, hide_index=True)
else:
    st.info("No tickets yet. Run create_tickets() in your Colab notebook to generate some.")

st.divider()

# ---- Two columns: recent jobs + top risk scores ----
left, right = st.columns(2)

with left:
    st.subheader("Recent Jobs")
    if len(jobs_df):
        recent_jobs = jobs_df.sort_values("JobId", ascending=False).head(20)
        st.dataframe(recent_jobs, use_container_width=True, hide_index=True)
    else:
        st.info("No jobs yet. Run run_backup_now() in your Colab notebook.")

with right:
    st.subheader("Top Risk Scores")
    if len(risk_df):
        top_risk = risk_df.sort_values("Anomalyscore", ascending=False).head(20)
        st.dataframe(top_risk, use_container_width=True, hide_index=True)
    else:
        st.info("No risk scores yet. Run run_anomaly_scoring() in your Colab notebook.")

st.divider()

# ---- Audit log - the full timeline of automated actions ----
st.subheader("Audit Log — Every Automated Action")
audit_df = run_query('SELECT * FROM "auditlog" ORDER BY "logid" DESC')
if len(audit_df):
    audit_df.columns = [c.capitalize() for c in audit_df.columns]
    st.dataframe(
        audit_df[["Actionat", "Actiontype", "Details"]],
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No audit log entries yet.")
