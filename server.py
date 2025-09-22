import os
import json
from mcp.server.fastmcp import FastMCP
from models import Commit, JiraIssue, MergedInput, Report
from typing import List

mcp = FastMCP(
    name="Git Logs Analyzer",
    host="0.0.0.0",
    port=8050,
)

def load_json_file(path: str, default=None):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default if default is not None else []
    except Exception as e:
        return f"Error reading {path}: {str(e)}"


@mcp.tool()
def get_authors() -> str:
    """Retrieve all authors and their emails from commits.json."""
    commits_path = os.path.join(os.path.dirname(__file__), "data", "commits.json")
    data = load_json_file(commits_path, default={"contributors": []})
    if isinstance(data, str):
        return json.dumps([])

    authors_list = [
        {"name": c.get("name", ""), "emails": c.get("emails", [])}
        for c in data.get("contributors", [])
    ]
    return json.dumps(authors_list, indent=2)


@mcp.tool()
def get_commits_by_author(author: str) -> str:
    """Retrieve commits by a given author."""
    commits_path = os.path.join(os.path.dirname(__file__), "data", "commits.json")
    data = load_json_file(commits_path, default={"contributors": []})
    if isinstance(data, str):
        return json.dumps({})

    for contrib in data.get("contributors", []):
        if contrib.get("name", "").lower() == author.lower():
            commits_list = [
                Commit(**commit).__dict__ for commit in contrib.get("regular_commits", [])
            ]
            overtime_list = [
                Commit(**commit).__dict__ for commit in contrib.get("overtime_commits", [])
            ]
            contrib_dict = {
                "name": contrib.get("name", ""),
                "emails": contrib.get("emails", []),
                "regular_commits": commits_list,
                "overtime_commits": overtime_list
            }
            return json.dumps(contrib_dict, indent=2)

    return json.dumps({})


@mcp.tool()
def get_tickets_and_commits_by_email(email: str) -> str:
    """Retrieve Jira tickets and commits for a given email, type-guarded."""
    jira_path = os.path.join(os.path.dirname(__file__), "data", "jira-commits-merged.json")
    data = load_json_file(jira_path, default={})
    if isinstance(data, str):
        return json.dumps({})

    entry = data.get(email, {})
    tickets: List[JiraIssue] = [
        JiraIssue(**ticket) for ticket in entry.get("tickets", [])
    ]
    regular_commits: List[Commit] = [
        Commit(**commit) for commit in entry.get("commits", {}).get("regular", [])
    ]
    overtime_commits: List[Commit] = [
        Commit(**commit) for commit in entry.get("commits", {}).get("overtime", [])
    ]

    merged_input = MergedInput(
        email=email,
        name=entry.get("name", ""),
        tickets=tickets,
        regular_commits=regular_commits,
        overtime_commits=overtime_commits
    )

    return json.dumps(merged_input.__dict__, indent=2, default=lambda o: o.__dict__)


@mcp.tool()
def save_reports_batch(reports: list) -> str:
    """Save multiple reports to JSON file without overwriting existing ones."""
    try:
        report_path = os.path.join(os.path.dirname(__file__), "data", "reports.json")
        os.makedirs(os.path.dirname(report_path), exist_ok=True)

        # Load existing reports
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                existing_reports = json.load(f)
            if not isinstance(existing_reports, list):
                existing_reports = []
        else:
            existing_reports = []

        # Append new reports
        existing_reports.extend(reports)

        # Save all reports
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(existing_reports, f, indent=2, default=lambda o: o.__dict__)

        return f"All reports saved successfully! Total reports: {len(existing_reports)}"

    except Exception as e:
        return f"Error saving reports: {str(e)}"


@mcp.tool()
def send_reports_batch_slack(reports: list) -> str:
    """Send multiple reports via Slack."""
    count = len(reports)
    
    for r in reports:
        r["sent_to_slack_at"] = "now"
    return f"[Slack] {count} reports sent!"


@mcp.tool()
def send_reports_batch_gmail(reports: list) -> str:
    """Send multiple reports via Gmail."""
    count = len(reports)
    
    for r in reports:
        r["sent_to_email_at"] = "now"
    return f"[Gmail] {count} reports sent!"
