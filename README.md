# EdgeDash: Autonomous Career-Intelligence System

EdgeDash is an autonomous AI career-intelligence agent designed to fetch job listings, extract factual job requirements using LLMs, score listings deterministically against candidate profiles, identify high-value skill gaps, verify outputs, store data behind an isolated storage interface, and present insights via a read-only web dashboard and natural-language query interface.

- **Public Dashboard**: [Streamlit App](https://edgedash.streamlit.app) *(or your deployed URL)*


---

## Production & System Architecture

```text
Trigger / GitHub Actions Scheduler
  → Orchestrator
  → Sub-agents (Fetcher, Scorer, GapAnalyzer)
  → Verifier
  → Storage (PostgreSQL / SQLite fallback)
  → Streamlit Read-Only Dashboard & Ask Pipeline
```

### Key Architectural Decisions

1. **Storage Isolation (`edgedash/storage.py`)**: All database interaction goes strictly through `edgedash/storage.py`. No other module imports database drivers or executes raw queries.
2. **PostgreSQL & Ephemeral System Safety**: Hosted filesystems are ephemeral. All persistent data is stored in PostgreSQL when `DATABASE_URL` is set, with an automatic fallback to local SQLite for offline development.
3. **Zero Text-to-SQL**: The language model is never allowed to generate SQL, compose queries, or access database tables directly. Natural language routing selects only from a pre-tested registry of 8 parameterised, read-only Python tools with strict parameter clamping.
4. **Deterministic Scoring & Calculations**: Models extract factual raw strings from job descriptions; models do not compute fit scores, rank gaps, or calculate aggregate metrics. All scoring and gap math is pure, deterministic Python code.
5. **Independent Dashboard & Scheduler**: The Streamlit dashboard and GitHub Actions scheduler run as separate processes that share only the database. The dashboard is strictly read-only and never runs a cycle or performs database writes.
6. **Verifier Autonomy**: The Verifier evaluates output plausible metrics and returns a verdict. It never rewrites or repairs data automatically.

---

## Production Deployment & Operational Commands

### Environment Variables & Secrets

- `DATABASE_URL`: Hosted PostgreSQL connection string (e.g. `postgresql://user:pass@host:5432/dbname`). When absent, EdgeDash falls back to local SQLite (`edgedash.db`).
- `GEMINI_API_KEY`: API key for Google Gemini LLM API (used for extraction, scoring, routing, and phrasing).

### Storage Migration & Health Commands

- Run idempotent database migrations:
  ```bash
  python -m edgedash.storage --migrate
  ```
- Run database health and schema check:
  ```bash
  python -m edgedash.storage --check
  ```
- Execute full autonomous cycle:
  ```bash
  python run_cycle.py
  ```
- Run read-only system health check:
  ```bash
  python -m edgedash.health
  ```
- Launch Streamlit dashboard locally:
  ```bash
  streamlit run app.py
  ```
- Run full pytest test suite:
  ```bash
  python -m pytest -q
  ```

---

## GitHub Actions Automated Scheduler

The scheduled data-collection job runs automatically via [.github/workflows/cycle.yml](file:///.github/workflows/cycle.yml) daily at 06:00 IST (00:30 UTC), and supports manual invocation via `workflow_dispatch`.

### Configuring Secrets in GitHub
1. Navigate to your GitHub repository.
2. Go to **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions**.
3. Add Repository Secrets:
   - `DATABASE_URL`: Your hosted PostgreSQL connection string.
   - `GEMINI_API_KEY`: Your Gemini API Key.

### Manually Running the Workflow
1. Navigate to your GitHub repository.
2. Click the **Actions** tab.
3. Select **EdgeDash Scheduled Cycle & Health Check** workflow from the left sidebar.
4. Click **Run workflow** $\rightarrow$ select branch $\rightarrow$ click **Run workflow**.

---

## Known System Limitations

- **Cross-Source Duplicates**: Listings with different URLs from different job boards are currently treated as distinct entries.
- **Extraction Misses**: LLM fact extraction may miss implicit requirements not stated explicitly in job descriptions.
- **Thin Trend History**: Trend comparisons require at least two separate snapshot runs to compute directional movement.
- **Scheduled Update Delays**: Data updates occur according to the 6-hour fetch interval or daily scheduled workflow execution.
- **Free-Tier Database Pauses**: Cloud PostgreSQL instances on free tiers may pause after periods of inactivity, causing initial query delay during cold starts.
- **Unsupported Questions**: Natural-language questions outside the 8 registered tool scopes (such as salary negotiation advice or promotion predictions) are cleanly refused with supported options listed.
