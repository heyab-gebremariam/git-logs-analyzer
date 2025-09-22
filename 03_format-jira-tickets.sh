#!/bin/bash

JIRA_INPUT="data/jira-issues.json"
JIRA_OUTPUT="data/formatted-jira-issues.json"

echo "Processing Jira issues..."

# Extract every 4th element, map to a simplified JiraIssue format
jq '[.[] | select(type == "array") | .[] | {
    key: .key,
    summary: .fields.summary,
    assignee: .fields.assignee.displayName,
    status: .fields.status.name,
    reporter: .fields.reporter.displayName,
    updated: .fields.updated
}]' "$JIRA_INPUT" > "$JIRA_OUTPUT"

echo "Formatted Jira issues saved to $JIRA_OUTPUT"


