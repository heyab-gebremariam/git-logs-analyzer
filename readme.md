# Git Logs Analyzer

Git Logs Analyzer is a tool to **collect, analyze, persist, and distribute commit reports by developer**.
It combines **Git commit history** and **Jira tickets** into structured reports, summarizes them with **Gemini**, and distributes via **Gmail** using MCP tools.

---

## 🚀 Features

* Track developer contributions for a configurable time window.
* Distinguish between **regular** vs **overtime** commits.
* Fetch and analyze **Jira issues** alongside commits.
* Persist structured reports in `data/reports.json`.
* Send reports via **Gmail**.

---

## 🛠️ Current Design

### `server.py`

Provides MCP tools:

* `get_authors()` → fetch all authors and their emails from `/data/commits.json`.
* `get_commits_by_author(author)` → fetch commits for a developer.
* `get_tickets_and_commits_by_email(email)` → fetch Jira tickets and commits merged by email.
* `save_reports_batch(reports)` → save multiple reports in `/data/reports.json`.
* `send_reports_batch_gmail(reports)` → send multiple reports via Gmail.

### `client.py`

Implements workflow:

1. Retrieve all authors via MCP.
2. Retrieve merged Jira tickets + commits per author email.
3. Ask Gemini to **summarize** commits + tickets.
4. Build `Report` objects and collect them in a batch.
5. Save batch locally and send via **Gmail**.

### `models.py`

Defines structured dataclasses:

* `Commit`
* `JiraIssue`
* `MergedInput` → combines an author's tickets and commits.
* `Report` → contains Gemini AI summary and sending metadata.

---

## 📂 Project Directory

```
git-logs-analyzer/
├── server.py
├── client.py
├── test.py
├── models.py
├── data/
│   ├── commits.json
│   ├── formatted-jira-issues.json
│   ├── jira-commits-merged.json
│   ├── jira-issues.json
│   └── reports.json
├── 01_commits-by-author.sh
├── 02_fetch-jira-issues.sh
├── 03_format-jira-tickets.sh
├── 04_merge-tickets-and-commits.sh
├── schema.sql
├── requirements.txt
├── .env.example
├── .env
└── readme.md
```

---

## ⚡ Usage

### 1. Initial Scripts

```bash
chmod +x 01_commits-by-author.sh
chmod +x 02_fetch-jira-issues.sh
chmod +x 03_format-jira-tickets.sh
chmod +x 04_merge-tickets-and-commits.sh

./01_commits-by-author.sh
./02_fetch-jira-issues.sh
./03_format-jira-tickets.sh
./04_merge-tickets-and-commits.sh
```

### 2. Setup environment

```bash
uv venv
uv pip install -r requirements.txt
```

### 3. Configure environment variables

Copy `.env.example` → `.env` and fill values:

```
GEMINI_API_KEY=your_gemini_key
SLACK_BOT_TOKEN=your_slack_token
GMAIL_CLIENT_ID=your_gmail_id
GMAIL_CLIENT_SECRET=your_gmail_secret
JIRA_API_TOKEN=your_jira_token
JIRA_BASE_URL=https://yourcompany.atlassian.net
```

### 4. Run MCP server

```bash
mcp dev server.py
```

### 5. Run client

```bash
uv run client.py
```
