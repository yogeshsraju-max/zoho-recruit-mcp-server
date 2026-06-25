# zoho-recruit-mcp-server

An MCP (Model Context Protocol) server that bridges **Claude** and the **Zoho
Recruit ATS**. It lets Claude search candidates, manage jobs and interviews,
run recruitment analytics, send candidate email, and use AI-assist tools —
all through natural language.

```
Claude  ⇄  Model Context Protocol  ⇄  this server  ⇄  Zoho Recruit API v2  ⇄  Recruitment data
```

Example prompts once connected:

- "Show me all candidates interviewed for the TPM role this week"
- "Find candidates with React.js experience"
- "Move candidate to the Technical Interview stage"
- "Create a new job opening for a Senior Backend Engineer"
- "Schedule an interview for candidate 12345 with alice@acme.com on 2026-07-01 at 14:30"
- "Generate a hiring funnel report for Q2"
- "Find candidates rejected in the last 30 days"
- "Send the interview invitation email to candidate 12345"

---

## 1. Architecture

```
zoho-recruit-mcp-server/
├── src/
│   ├── server.py              # FastMCP entrypoint, transport selection
│   ├── config.py              # pydantic settings + region/URL resolution
│   ├── services.py            # wires client + domain APIs together
│   ├── auth/
│   │   └── zoho_auth.py        # OAuth2 refresh-token -> access-token manager
│   ├── zoho/
│   │   ├── client.py           # async httpx client: retry, rate limit, 401 recovery
│   │   ├── common.py           # search-criteria builders, response helpers
│   │   ├── candidates.py       # Candidates module operations
│   │   ├── jobs.py             # Job_Openings module operations
│   │   ├── interviews.py       # Interviews module operations
│   │   ├── reports.py          # analytics (funnel, recruiter, source)
│   │   ├── email.py            # candidate email automation
│   │   └── ai_helpers.py       # resume parsing, match scoring, summaries
│   ├── tools/
│   │   ├── candidate_tools.py  # MCP tool registration (candidates)
│   │   ├── job_tools.py        # MCP tool registration (jobs)
│   │   ├── interview_tools.py  # MCP tool registration (interviews)
│   │   ├── analytics_tools.py  # MCP tool registration (analytics)
│   │   ├── email_tools.py      # MCP tool registration (email)
│   │   └── ai_tools.py         # MCP tool registration (AI assist)
│   ├── models/
│   │   ├── candidate.py        # pydantic input models + Zoho field mapping
│   │   └── job.py
│   └── utils/
│       ├── logger.py           # structured logging + secret/PII redaction
│       └── error_handler.py    # error taxonomy + MCP error formatting
├── tests/                      # pytest unit + integration tests
├── requirements.txt
├── pyproject.toml
├── Dockerfile
├── docker-compose.yml
├── claude_config.json
├── .env.example
└── README.md
```

**Transports**

- **STDIO** — for Claude Desktop (default).
- **Streamable HTTP** — for cloud deployment and the MCP Inspector (endpoint `/mcp`).

---

## 2. Setup

### Prerequisites

- Python 3.12+
- A Zoho Recruit account with API access

### Install

```bash
git clone <your-repo-url> zoho-recruit-mcp-server
cd zoho-recruit-mcp-server

python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env                # then fill in your Zoho credentials
```

---

## 3. Zoho setup (OAuth)

1. **Register a client** at the Zoho API console: <https://api-console.zoho.com/>
   - Choose **Server-based Applications**.
   - Note the **Client ID** and **Client Secret**.
   - Set an authorized redirect URI (e.g. `https://www.zoho.com/recruit` or your
     own callback).

2. **Pick scopes.** A broad working scope is:
   ```
   ZohoRecruit.modules.ALL,ZohoRecruit.settings.ALL
   ```
   For least privilege you can narrow to specific module scopes
   (e.g. `ZohoRecruit.modules.candidates.ALL`).

3. **Get an authorization code.** In a browser (use the accounts host for your
   region, e.g. `accounts.zoho.in` for India):
   ```
   https://accounts.zoho.com/oauth/v2/auth?response_type=code
     &client_id=YOUR_CLIENT_ID
     &scope=ZohoRecruit.modules.ALL,ZohoRecruit.settings.ALL
     &redirect_uri=YOUR_REDIRECT_URI
     &access_type=offline
     &prompt=consent
   ```
   `access_type=offline` is required to receive a refresh token. Copy the
   `code` value from the redirect URL (it expires within minutes).

4. **Exchange the code for a refresh token:**
   ```bash
   curl -X POST "https://accounts.zoho.com/oauth/v2/token" \
     -d "grant_type=authorization_code" \
     -d "client_id=YOUR_CLIENT_ID" \
     -d "client_secret=YOUR_CLIENT_SECRET" \
     -d "redirect_uri=YOUR_REDIRECT_URI" \
     -d "code=PASTE_THE_CODE"
   ```
   Save the `refresh_token` from the response. This server uses **only** the
   refresh token at runtime; access tokens are fetched and rotated automatically.

5. **Fill `.env`:**
   ```env
   ZOHO_CLIENT_ID=...
   ZOHO_CLIENT_SECRET=...
   ZOHO_REFRESH_TOKEN=...
   ZOHO_REGION=com        # com | eu | in | au | jp | ca
   ```
   The accounts and API base URLs are derived from `ZOHO_REGION`. Override with
   `ZOHO_ACCOUNTS_URL` / `ZOHO_BASE_URL` only for custom domains.

> **Region note:** use the accounts host matching the DC where your Zoho account
> lives (`.com`, `.eu`, `.in`, `.com.au`, `.jp`, `zohocloud.ca`). Using the wrong
> region produces `invalid_code` / auth errors.

---

## 4. Connecting to Claude

### Claude Desktop (STDIO)

Add the server to your Claude Desktop config (`claude_desktop_config.json`),
using the absolute path to your checkout:

```json
{
  "mcpServers": {
    "zoho-recruit": {
      "command": "python",
      "args": ["-m", "src.server"],
      "env": {
        "ZOHO_CLIENT_ID": "your-client-id",
        "ZOHO_CLIENT_SECRET": "your-client-secret",
        "ZOHO_REFRESH_TOKEN": "your-refresh-token",
        "ZOHO_REGION": "com"
      }
    }
  }
}
```

Run `python` from the project directory (or set `"cwd"` / use an absolute
interpreter path from your venv). A ready-to-edit `claude_config.json` ships in
this repo. Restart Claude Desktop and the **zoho-recruit** tools appear.

### Test the connection

With the **MCP Inspector** (HTTP transport):

```bash
MCP_TRANSPORT=http python -m src.server --transport http --port 8000
# Inspector connects to: http://localhost:8000/mcp
```

Or directly over stdio:

```bash
python -m src.server          # waits for an MCP client on stdin/stdout
```

---

## 5. Docker

```bash
cp .env.example .env          # fill in credentials
docker compose up --build
```

The container runs the **HTTP** transport on port `8000`; the MCP endpoint is
`http://localhost:8000/mcp`.

---

## 6. Available MCP tools

### Candidate management

| Tool | Purpose | Key inputs | Example prompt |
|------|---------|-----------|----------------|
| `search_candidates` | Search candidates | `keyword, skills, location, experience, status, job_id` | "Find Python developers with 5+ years" |
| `get_candidate_details` | Full profile + interview history | `candidate_id` | "Show me candidate 12345" |
| `create_candidate` | Create a candidate | `last_name, email, …` | "Add a candidate named Rahul Sharma" |
| `update_candidate_status` | Change candidate status | `candidate_id, status` | "Mark candidate 12345 as Rejected" |
| `bulk_candidate_update` | Update many candidates | `updates[]` (each needs `id`) | "Reject all who failed assessment" |

### Job management

| Tool | Purpose | Key inputs | Example prompt |
|------|---------|-----------|----------------|
| `create_job_opening` | Create a job | `job_title, department, skills, …` | "Open a Senior Backend Engineer role" |
| `search_jobs` | Find job openings | `keyword, status, department, location, recruiter` | "List all open jobs in Engineering" |
| `get_job_pipeline` | Candidates on a job | `job_id` | "Who's in the pipeline for job J-1?" |
| `update_job_status` | Change job status | `job_id, status` | "Put job J-1 on Hold" |
| `move_candidate_in_pipeline` | Move candidate within a job's pipeline | `job_id, candidate_id, status, comments` | "Move candidate to Technical Interview" |

### Interview management

| Tool | Purpose | Key inputs | Example prompt |
|------|---------|-----------|----------------|
| `schedule_interview` | Schedule an interview | `candidate_id, interviewer, date, time, duration_minutes, meeting_link` | "Schedule an interview…" |
| `get_interview_schedule` | Upcoming / pending evaluations | `from_date, to_date, interviewer, pending_feedback_only` | "Show pending interview evaluations" |
| `submit_interview_feedback` | Record feedback | `candidate_id, interviewer, rating, feedback, recommendation` | "Submit feedback for candidate 12345" |

### Recruitment analytics

| Tool | Purpose | Key inputs |
|------|---------|-----------|
| `hiring_funnel_report` | Applicants → joiners + conversion % | `date_from, date_to, role, recruiter, department` |
| `recruiter_performance_report` | Sourced / interviews / offers / closures per recruiter | `date_from, date_to` |
| `source_analysis` | Source breakdown + join rates | `date_from, date_to` |

### Email automation

| Tool | Purpose | Key inputs |
|------|---------|-----------|
| `send_candidate_email` | Send rejection / invite / follow-up / offer | `candidate_id, template, message, subject, template_id` |

### Advanced AI assist

| Tool | Purpose | Key inputs | Output |
|------|---------|-----------|--------|
| `resume_parser` | Structure a resume | `resume_base64` or `resume_text` | `{skills, experience, companies, education, projects}` |
| `candidate_match_score` | Candidate vs JD fit | `candidate_skills, job_description` | `{match_percentage, strengths, gaps, recommendation}` |
| `interview_summary_generator` | Structure a transcript | `transcript` | `{summary, strengths, concerns, questions_asked}` |

---

## 7. Errors

Every tool returns either a result or a stable error object:

```json
{ "error_code": "ZOHO_TOKEN_EXPIRED", "message": "Refresh token is invalid or revoked. ..." }
```

Common codes: `ZOHO_TOKEN_EXPIRED`, `ZOHO_AUTH_FAILED`, `ZOHO_RATE_LIMITED`,
`ZOHO_RECORD_NOT_FOUND`, `INVALID_INPUT`, `NETWORK_ERROR`, `ZOHO_API_ERROR`,
`ENDPOINT_NOT_CONFIGURED`.

The client retries transient failures (429/5xx/network) with exponential
backoff and transparently refreshes the access token on a 401.

---

## 8. Security & logging

- Only the refresh token is stored; access tokens live in memory and rotate.
- Structured logs capture request id, tool name, execution time, and status.
- Logs **never** contain tokens, secrets, candidate emails/phones, or resume
  text — these are redacted by the logger.
- A client-side rate limiter caps requests per minute (`RATE_LIMIT_PER_MINUTE`).
- All tool inputs are validated (pydantic models / explicit checks).

---

## 9. Testing

```bash
pip install -r requirements.txt
pytest -q
```

Tests cover authentication, the HTTP client (retry / 401 / error mapping),
domain logic, the AI helpers, and end-to-end flows against a mocked Zoho API
(`respx`). No real Zoho calls are made.

---

## 10. Endpoints that may need confirmation for your account

Zoho field/module API names and a few action endpoints vary by edition and by
any customisations in your org. These are centralised and clearly commented in
the code so you can adjust them in one place:

- **Module names** — `src/zoho/common.py` (`Candidates`, `Job_Openings`, `Interviews`).
- **Candidate ↔ job association / stage change** — `JobsAPI.get_pipeline` and
  `JobsAPI.change_candidate_stage` (`/Job_Openings/{id}/associate`).
- **Candidate email send action** — `src/zoho/email.py` (`_SEND_MAIL_PATH`).
- **Zoho Resume Parser** — `AIHelpers.resume_parse(use_zoho_parser=True)`
  (the local heuristic parser works out of the box without it).
- **Custom field names** (e.g. `Hiring_Manager`, `Start_DateTime`, `Duration`)
  — adjust in the relevant domain module if your template differs.

The local heuristics (match scoring, transcript summarisation, resume text
parsing) work without any Zoho-specific configuration.
