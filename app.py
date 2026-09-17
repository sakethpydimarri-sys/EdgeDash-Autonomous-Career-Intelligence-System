"""EdgeDash Read-Only Streamlit Dashboard (Class 6: Trust Nothing)."""

import json
import logging
from datetime import datetime, timezone
import streamlit as st

from edgedash.config import load_config
from edgedash import storage
from edgedash import health

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="EdgeDash Intelligence Dashboard",
    page_icon="⚡",
    layout="wide",
)


def get_health_indicator(db_path: str) -> tuple[str, str, str]:
    """Compute top health status indicator (badge, status_text, color_type)."""
    try:
        db_ok, _ = health.check_database_connectivity(db_path)
        if not db_ok:
            return "⚪", "Health Status: Database Unavailable", "off"

        cycle_ok, _ = health.check_cycle_recency(db_path, max_age_hours=24.0)
        health_ok, _ = health.check_cycle_health(db_path)

        if not health_ok:
            return "🔴", "System Status: Verification Failures Detected", "error"
        elif not cycle_ok:
            return "🟠", "System Status: Data Stale (>24h since last cycle)", "warning"
        else:
            return "🟢", "System Status: Healthy & Verified", "success"
    except Exception as exc:
        logger.error("Health check computation failed: %s", storage.sanitize_db_error(exc))
        return "⚪", "System Status: Health Status Unavailable", "off"


@st.cache_data(ttl=10)
def fetch_dashboard_data(db_path: str):
    """Fetch read-only database metrics with short TTL cache."""
    try:
        last_passing = storage.get_last_passing_cycle(db_path)
        recent_cycles = storage.get_recent_cycles(db_path, limit=30)
        top_listings = storage.get_listings(db_path, limit=10, min_score=1)
        top_gaps = storage.get_latest_gap_snapshot(db_path)[:10]
        diagnostics = storage.get_score_diagnostics(db_path)

        return {
            "success": True,
            "last_passing": last_passing,
            "recent_cycles": recent_cycles,
            "top_listings": top_listings,
            "top_gaps": top_gaps,
            "diagnostics": diagnostics,
            "error": None,
        }
    except Exception as exc:
        safe_err = storage.sanitize_db_error(exc)
        logger.error("Database fetch failed: %s", safe_err)
        return {
            "success": False,
            "last_passing": None,
            "recent_cycles": [],
            "top_listings": [],
            "top_gaps": [],
            "diagnostics": {},
            "error": safe_err,
        }


def main():
    """Render read-only Streamlit dashboard UI."""
    st.title("⚡ EdgeDash Autonomous Career Intelligence")

    # Load configuration safely
    try:
        config = load_config()
        db_path = config.db_path
    except Exception as err:
        st.error("Failed to load configuration. The application is running in limited mode.")
        logger.error("Config load error: %s", err)
        return

    # Top Health Status Line
    badge, status_msg, color_type = get_health_indicator(db_path)
    if color_type == "success":
        st.success(f"{badge} **{status_msg}**")
    elif color_type == "warning":
        st.warning(f"{badge} **{status_msg}**")
    elif color_type == "error":
        st.error(f"{badge} **{status_msg}**")
    else:
        st.info(f"{badge} **{status_msg}**")

    data = fetch_dashboard_data(db_path)

    # 1. Graceful Unreachable Database Banner
    if not data["success"]:
        st.error("⚠️ **The database is temporarily unavailable. Please try again later.**")
        st.info("The EdgeDash dashboard is currently unable to reach the persistent storage backend.")
        return

    last_passing = data["last_passing"]
    recent_cycles = data["recent_cycles"]
    top_listings = data["top_listings"]
    top_gaps = data["top_gaps"]
    diagnostics = data["diagnostics"]

    # 2. Empty Database / No Completed Cycles Banner
    if not last_passing and not recent_cycles and diagnostics.get("scored_count", 0) == 0:
        st.info("ℹ️ **No completed cycles are available yet.**")
        st.caption("The database contains no verified job listings or cycle execution history. The scheduled data collection job will populate data on its next run.")

    # Header Strip & Stale Verified Data Warning Banner
    newest_cycle = recent_cycles[0] if recent_cycles else None
    newest_status = newest_cycle.get("status") if newest_cycle else "no_cycles"

    if newest_status in ("failed", "degraded"):
        passing_ts = last_passing.get("finished_at") if last_passing else "None"
        st.warning(
            f"⚠️ **STALE VERIFIED DATA WARNING**: The newest execution cycle status is **{newest_status.upper()}**. "
            f"Displaying data from the last verified passing cycle (**{passing_ts}**). "
            f"Fresh unverified or degraded data is strictly withheld from presentation."
        )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        pass_ts = last_passing.get("finished_at", "Never") if last_passing else "Never"
        st.metric("Last Verified Cycle", pass_ts.split("T")[0] if "T" in pass_ts else pass_ts)
    with col2:
        st.metric("Total Scored Listings", diagnostics.get("scored_count", 0))
    with col3:
        st.metric("Unscored Listings", diagnostics.get("unscored_count", 0))
    with col4:
        verdict_label = "PASSING" if newest_status == "complete" else newest_status.upper()
        st.metric("Current Verdict Status", verdict_label)

    st.markdown("---")

    # 3. Ask Your Data Section (Secure Natural Language Queries)
    st.subheader("💬 Ask Your Data")
    st.caption("Ask plain English questions over verified EdgeDash data (no SQL generation, direct DB access, or code execution).")

    example_col1, example_col2, example_col3 = st.columns(3)
    ex1_clicked = example_col1.button("Which companies are hiring for my role this week?", use_container_width=True)
    ex2_clicked = example_col2.button("What three skills would unlock the most listings?", use_container_width=True)
    ex3_clicked = example_col3.button("Have things gotten better or worse this month?", use_container_width=True)

    default_query = ""
    if ex1_clicked:
        default_query = "Which companies are hiring for my role this week?"
    elif ex2_clicked:
        default_query = "What three skills would unlock the most listings?"
    elif ex3_clicked:
        default_query = "Have things gotten better or worse this month?"

    query_input = st.text_input("Ask a question:", value=default_query, key="ask_input_field", placeholder="e.g. Which companies are hiring for my role this week?")
    submit_ask = st.button("Submit Question", type="primary")

    if (submit_ask or default_query) and query_input.strip():
        from edgedash.query.ask import ask

        try:
            answer_obj = ask(query_input.strip(), db_path=db_path)
            st.markdown("#### 💡 Answer")
            if answer_obj.was_answerable:
                st.success(answer_obj.text)
            else:
                st.warning(answer_obj.text)

            if answer_obj.tool_used:
                st.caption(f"🔧 **Tool Selected:** `{answer_obj.tool_used}` | **Parameters:** `{json.dumps(answer_obj.params)}`")

            st.markdown("#### 📊 Underlying Data Rows")
            if answer_obj.rows:
                st.dataframe(answer_obj.rows, use_container_width=True)
            else:
                st.info("No underlying rows returned for this query.")
        except Exception as query_err:
            st.error("Error processing query. Please try again.")
            logger.error("Ask query error: %s", storage.sanitize_db_error(query_err))

    st.markdown("---")

    # 4. Data Panels (Top Listings, Skill Gaps, Activity Log)
    tab1, tab2, tab3 = st.tabs(["📌 Top Scored Listings", "🎯 Skill Gap Analysis", "📜 Agent Activity Log"])

    with tab1:
        st.subheader("Top 10 Scored Job Listings (Verified Data)")
        try:
            if not top_listings:
                st.info("No verified scored listings available in database yet.")
            else:
                for l in top_listings:
                    score = l.get("fit_score", "N/A")
                    title = l.get("title", "Unknown Role")
                    company = l.get("company", "Unknown Company")
                    location = l.get("location", "Remote")
                    reason = l.get("fit_reason", "No reason recorded")

                    with st.expander(f"**[{score}/100]** {title} — *{company}* ({location})"):
                        st.write(f"**Fit Reason:** {reason}")
                        st.write(f"**URL:** {l.get('url')}")
                        st.write(f"**Source:** {l.get('source')} | **Fetched At:** {l.get('fetched_at')}")
        except Exception as panel_err:
            st.error("Failed to render job listings panel.")
            logger.error("Listings panel error: %s", storage.sanitize_db_error(panel_err))

    with tab2:
        st.subheader("Top 10 High-Cost Skill Gaps (Verified Snapshot)")
        try:
            if not top_gaps:
                st.info("No skill gap snapshot available in database yet.")
            else:
                for g in top_gaps:
                    skill = g.get("skill", "Unknown")
                    cost = g.get("opportunity_cost", 0.0)
                    blocked = g.get("listings_blocked", 0)
                    top_sc = g.get("top_score", 0)
                    low_conf = g.get("low_confidence", False)

                    conf_str = " (⚠️ Low Confidence)" if low_conf else ""
                    st.write(
                        f"- **{skill.title()}**: Blocked **{blocked}** listings | "
                        f"Opportunity Cost: **{cost:.2f}** | Top Fit Score: **{top_sc}**{conf_str}"
                    )
        except Exception as panel_err:
            st.error("Failed to render skill gap panel.")
            logger.error("Skill gap panel error: %s", storage.sanitize_db_error(panel_err))

    with tab3:
        st.subheader("Agent Activity Log (Last 30 Execution Cycles)")
        try:
            if not recent_cycles:
                st.info("No cycle execution history found in database.")
            else:
                log_data = []
                for c in recent_cycles:
                    notes = c.get("parsed_notes", {})
                    status = c.get("status", "unknown")
                    log_data.append(
                        {
                            "Cycle ID": c.get("id"),
                            "Finished At": c.get("finished_at"),
                            "Status": status.upper(),
                            "Verdict": notes.get("verdict", "N/A").upper(),
                            "Ran Agents": ", ".join(notes.get("ran", [])),
                            "Skipped": ", ".join(notes.get("skipped", [])),
                            "Failed Checks": ", ".join(notes.get("failed_checks", [])),
                            "Observed": str(notes.get("observed_values", {})),
                            "Retries": notes.get("retry_count", 0),
                        }
                    )
                st.dataframe(log_data, use_container_width=True)
        except Exception as panel_err:
            st.error("Failed to render agent activity log panel.")
            logger.error("Activity log panel error: %s", storage.sanitize_db_error(panel_err))

    # Footer
    st.markdown("---")
    last_pass_time = last_passing.get("finished_at", "No completed cycle") if last_passing else "No completed cycle"
    st.caption(
        f"⚡ **EdgeDash Autonomous Career Intelligence** | Last Successful Cycle: `{last_pass_time}` | "
        f"[GitHub Repository](https://github.com/saket/edgedash)"
    )


if __name__ == "__main__":
    main()
