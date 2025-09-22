from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Commit:
    hash: str
    date: str
    time: str
    day: str
    message: str


@dataclass
class JiraIssue:
    key: str
    summary: str
    assignee: str
    status: str
    reporter: str
    updated: str


@dataclass
class MergedInput:
    email: str
    name: str
    tickets: List[JiraIssue]
    regular_commits: List[Commit]
    overtime_commits: List[Commit]


@dataclass
class Report:
    developer_email: str
    ai_summary: str
    tickets_and_commits: MergedInput
    sent_to_slack_at: Optional[str] = None
    sent_to_email_at: Optional[str] = None
