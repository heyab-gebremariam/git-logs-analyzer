import os
import json
import base64
import time
from typing import List, Dict, Any, Optional

import requests
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

JIRA_BASE = os.getenv("JIRA_BASE_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_TOKEN = os.getenv("JIRA_API_TOKEN")
DEFAULT_COMMITS_PATH = os.getenv("COMMITS_JSON_PATH", os.path.join(os.path.dirname(__file__), "data", "commits.json"))

if not (JIRA_BASE and JIRA_EMAIL and JIRA_TOKEN):
    # We still allow server to start for local tests, but the tool will return an error if these are missing.
    pass

mcp = FastMCP(
        name="Git Logs Analyzer", 
        host="0.0.0.0", 
        port=8050
    )


def jira_auth_header() -> Dict[str, str]:
    token = f"{JIRA_EMAIL}:{JIRA_TOKEN}"
    encoded = base64.b64encode(token.encode()).decode()
    return {
        "Authorization": f"Basic {encoded}", 
        "Accept": "application/json", "Content-Type": 
        "application/json"
    }


def extract_emails_from_commits(json_path: str) -> List[str]:
    """Load JSON and extract unique emails from the contributors list."""
    if not os.path.exists(json_path):
        raise FileNotFoundError(f"Commits JSON not found at {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    emails = set()
    contributors = data.get("contributors", [])
    for c in contributors:
        for e in c.get("emails", []):
            emails.add(e)
    return sorted(emails)


def get_account_ids_for_email(email: str) -> List[str]:
    """
    Use Jira Cloud user search to get accountId(s) for an email.
    Endpoint: GET /rest/api/3/user/search?query={email}
    Returns list of accountIds (could be multiple matches).
    """
    if not JIRA_BASE or not JIRA_EMAIL or not JIRA_TOKEN:
        raise RuntimeError("Jira configuration missing (JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN).")

    url = f"{JIRA_BASE.rstrip('/')}/rest/api/3/user/search"
    params = {"query": email}
    headers = jira_auth_header()

    resp = requests.get(url, headers=headers, params=params, timeout=15)
    resp.raise_for_status()
    users = resp.json()
    # Each user may have accountId (Jira Cloud). Return those.
    account_ids = []
    for u in users:
        acct = u.get("accountId")
        if acct:
            account_ids.append(acct)
    return account_ids


def search_issues_for_account(account_id: str, max_results: int = 50) -> List[Dict[str, Any]]:
    """
    Query Jira for issues where assignee = accountId OR reporter = accountId
    using Search API (POST).
    Endpoint: POST /rest/api/3/search  (safer for long JQL)
    """
    url = f"{JIRA_BASE.rstrip('/')}/rest/api/3/search"
    headers = jira_auth_header()
    jql = f"(assignee = {account_id} OR reporter = {account_id}) ORDER BY updated DESC"
    payload = {"jql": jql, "maxResults": max_results, "fields": ["key", "summary", "status", "assignee", "reporter", "updated"]}
    resp = requests.post(url, headers=headers, json=payload, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    return data.get("issues", [])


@mcp.tool()
def get_jira_tickets_for_commits(commits_path: Optional[str] = None, max_issues_per_user: int = 30) -> str:
    """
    Tool: read commits json, extract emails, fetch Jira accountIds, and search issues.
    Returns: formatted text with found issues.
    """
    try:
        path = commits_path or DEFAULT_COMMITS_PATH
        emails = extract_emails_from_commits(path)
        if not emails:
            return "No contributor emails found in commits JSON."

        results = {}
        for email in emails:
            try:
                account_ids = get_account_ids_for_email(email)
            except requests.HTTPError as e:
                results[email] = {"error": f"Jira user search failed: {str(e)}"}
                continue

            if not account_ids:
                results[email] = {"accountIds": [], "issues": []}
                continue

            user_issues = []
            # For each accountId (usually 1), fetch issues
            for acct in account_ids:
                try:
                    issues = search_issues_for_account(acct, max_results=max_issues_per_user)
                except requests.HTTPError as e:
                    # if search fails for this account, attach error and continue
                    user_issues.append({"accountId": acct, "error": str(e)})
                    continue

                # simplify issues to a small dict
                simplified = []
                for it in issues:
                    simplified.append({
                        "key": it.get("key"),
                        "summary": (it.get("fields") or {}).get("summary"),
                        "status": ((it.get("fields") or {}).get("status") or {}).get("name"),
                        "assignee": ((it.get("fields") or {}).get("assignee") or {}).get("displayName"),
                        "reporter": ((it.get("fields") or {}).get("reporter") or {}).get("displayName"),
                        "updated": (it.get("fields") or {}).get("updated"),
                    })
                user_issues.append({"accountId": acct, "issues": simplified})

                # small sleep between account queries to be polite with rate limits
                time.sleep(0.2)

            results[email] = {"accountIds": account_ids, "issues": user_issues}

        # Format a human readable summary
        out_lines = []
        out_lines.append("Jira tickets found for contributor emails:\n")
        for email, info in results.items():
            out_lines.append(f"Email: {email}")
            if "error" in info:
                out_lines.append(f"  ERROR: {info['error']}\n")
                continue
            out_lines.append(f"  accountIds: {info.get('accountIds')}")
            for acct_block in info.get("issues", []):
                acct = acct_block.get("accountId")
                if "error" in acct_block:
                    out_lines.append(f"   - accountId {acct} -> ERROR: {acct_block['error']}")
                    continue
                issues = acct_block.get("issues", [])
                out_lines.append(f"   - accountId {acct} -> {len(issues)} issue(s)")
                for it in issues[:10]:
                    out_lines.append(f"      * {it['key']}: {it['summary']} ({it['status']}) - updated {it['updated']}")
            out_lines.append("")  # blank line

        return "\n".join(out_lines)
    except FileNotFoundError as e:
        return f"File error: {str(e)}"
    except Exception as e:
        return f"Unexpected error: {str(e)}"


@mcp.tool()
def echo(x: str) -> str:
    return f"echo: {x}"


if __name__ == "__main__":
    mcp.run(transport="stdio")
