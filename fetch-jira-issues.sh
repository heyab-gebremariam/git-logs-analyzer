#!/bin/bash
set -e
set -o pipefail

# ==== CONFIG ====
JIRA_EMAIL="heyab.gebremariam@gmail.com"
JIRA_API_TOKEN="ATATT3xFfGF03PIYGM86qHfMII961xEhemHG7xU167Z2kpF5AiGLhQJnm-HVVGF8U4SBRwuz6lPPwrpVlq2vY87xEydYmYYNYskn9fAsht_xUf5YPgDWLaZukSePmaBZtFiLtRAGr1wHM6k82KSoqi7q9JDQ5P-nA-eLW7DEpNRI8ZYnfAeMv5I=569DE168"
JIRA_BASE_URL="https://bmtechnology.atlassian.net"
OUTPUT_FILE="data/jira-issues.json"
MAX_RESULTS=50
TMP_DIR="data/tmp"

mkdir -p "$TMP_DIR"

# ==== Fetch all project keys dynamically ====
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Fetching all projects..."
projects=($(curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
    -X GET "$JIRA_BASE_URL/rest/api/3/project/search" \
    -H "Accept: application/json" \
    | jq -r '.values[].key'))

echo "[$(date +'%Y-%m-%d %H:%M:%S')] Found projects: ${projects[*]}"

API_URL="$JIRA_BASE_URL/rest/api/3/search"

for project in "${projects[@]}"; do
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Fetching issues for project: $project"

    # Sanitize project name for filenames
    safe_project=$(echo "$project" | tr -cd '[:alnum:]_-')

    startAt=0
    total=1 # dummy to enter the loop

    while [ $startAt -lt $total ]; do
        payload=$(jq -n \
            --arg jql "project=$project ORDER BY updated DESC" \
            --argjson startAt $startAt \
            --argjson maxResults $MAX_RESULTS \
            '{jql: $jql, startAt: $startAt, maxResults: $maxResults, fields:["key","summary","status","assignee","reporter","updated"]}')

        echo "[$(date +'%Y-%m-%d %H:%M:%S')] Request payload for $project startAt=$startAt:"
        echo "$payload"

        resp_file="$TMP_DIR/${safe_project}_${startAt}.json"

        # Run curl and log raw response
        curl -s -u "$JIRA_EMAIL:$JIRA_API_TOKEN" \
            -X POST "$API_URL" \
            -H "Content-Type: application/json" \
            -H "Accept: application/json" \
            --data "$payload" \
            | tee "$resp_file"

        # Check for API error
        if grep -q '"errorMessages"' "$resp_file"; then
            echo "[$(date +'%Y-%m-%d %H:%M:%S')] ERROR fetching $project startAt=$startAt"
        fi

        # Update pagination
        total=$(jq '.total' "$resp_file")
        startAt=$((startAt + MAX_RESULTS))
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] Next startAt=$startAt / total=$total"
    done

    # Merge all pages for project
    jq -s '[.[][]]' "$TMP_DIR/${safe_project}"_*.json > "$TMP_DIR/${safe_project}.json"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Saved project $project JSON"

    # Optional: remove temp pages
    rm -f "$TMP_DIR/${safe_project}"_*.json
done

# Merge all projects into final output
jq -s '[.[][]]' "$TMP_DIR"/*.json > "$OUTPUT_FILE"
echo "[$(date +'%Y-%m-%d %H:%M:%S')] Done! All Jira issues saved to $OUTPUT_FILE"

# Optional: remove temp folder
rm -rf "$TMP_DIR"
