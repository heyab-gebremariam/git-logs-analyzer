# Git Logs Analyzer


Git Logs Analyzer is a tool to collect, analyze, persist, and distribute commit reports by developer.

- Track developer contributions for a time window
- Distinguish regular vs overtime activity
- Persist structured reports for later auditing
- Integrate with Slack/Gmail/Jira via MCP tools



### Integrations

#### Slack
- Use `slack_sdk` or `httpx` to call `chat.postMessage` with a nice message attachment.
- Store `SLACK_BOT_TOKEN` in env and the channel to post to.
- When sending, update `reports.sent_to_slack_at`.

#### Gmail
- Use OAuth2 or App Password (less recommended) to send via SMTP, or use Gmail API.
- Store `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, token storage.
- On send, update `reports.sent_to_email_at`.

#### Jira
- Use `JIRA_API_TOKEN`, `JIRA_BASE_URL`, and use `/rest/api/2/search?jql=assignee=<email>` to fetch tickets.
- Map tickets to developer by email.


---

### MCP tools (exposed from server.py)

A suggested toolset:

- `get_knowledge_base()` — returns knowledge base string (already implemented)
- `generate_report_for_developer(email, start_date, end_date)` — runs analyzer and persists report
- `get_report(report_id)` — returns report JSON
- `send_report_slack(report_id, slack_channel)` — posts to Slack (requires slack token in env)
- `send_report_email(report_id, to_email)` — send via Gmail (requires credentials)
- `get_jira_tickets_for_developer(email)` — lookup Jira issues assigned to `email`

Tool input/return JSON shapes should be declared in the MCP metadata (inputSchema) so Gemini can call them.


---
## Project directory tree

```
git-logs-analyzer/
├── server.py
├── client.py
├── scripts/
│   ├── sync-all-github.sh
│   ├── get-commits-by-author.sh
│   └── utilities.sh
├── mcp/
│   └── ... (mcp lib or package files)
├── data/
│   └── kb.json
├── docs/
│   ├── documentation.md  <-- (generated here)
│   └── README.md         <-- (generated here)
├── sql/
│   └── schema.sql
├── requirements.txt
├── .env.example
├── .env
├── tests/
│   └── test_db.py
└── README.md
```


---

### Deployment Steps

./commits-by-author.sh


1. Create and activate virtualenv, Install Requirements

```bash


uv venv
uv pip install -r requirements.txt
```

2. Enter Environment Variables

Copy `.env.example` to `.env` and fill values (GEMINI_API_KEY, DATABASE_URL, TOKEN, etc.)

3. Initialize database 

Execute schema.sql inside psql or pgAdmin


4. Run MCP server

```bash
mcp dev server.py
```

5. Run client

```bash
uv run client.py --query "Get commit report for heyab-gebremariam between 2025-08-01 and 2025-08-31"
```

