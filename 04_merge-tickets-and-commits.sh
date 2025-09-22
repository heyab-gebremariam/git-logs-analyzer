#!/usr/bin/env bash
set -euo pipefail

COMMITS_JSON="data/commits.json"
JIRA_ISSUES_JSON="data/formatted-jira-issues.json"
OUTPUT_JSON="data/jira-commits-merged.json"

# --- Normalize line endings (remove hidden \r) -------------------
sed -i 's/\r$//' "$COMMITS_JSON"
sed -i 's/\r$//' "$JIRA_ISSUES_JSON"
[ -f "$OUTPUT_JSON" ] && sed -i 's/\r$//' "$OUTPUT_JSON"

# ---------------------------------------------------------------
# 1. Prepare base object keyed by primary email
# ---------------------------------------------------------------
echo "Initializing output structure from $COMMITS_JSON ..."
BASE_JSON=$(jq '
  reduce .contributors[] as $c
    ({}; .[$c.emails[0]] = {
         name: $c.name,
         tickets: [],
         commits: $c.commits
    })
' "$COMMITS_JSON")

TMP_FILE=$(mktemp)
echo "$BASE_JSON" > "$TMP_FILE"

# ---------------------------------------------------------------
# 2. Show all unique Jira assignees for manual mapping
# ---------------------------------------------------------------
echo
echo "Unique Jira assignees (from $JIRA_ISSUES_JSON):"
mapfile -t ASSIGNEES < <(
  jq -r '.[].assignee' "$JIRA_ISSUES_JSON" | sed 's/\r$//' | sort -u
)
for i in "${!ASSIGNEES[@]}"; do
  printf "%2d) %s\n" "$((i+1))" "${ASSIGNEES[$i]}"
done
echo

# ---------------------------------------------------------------
# 3. Show contributor emails we can map to
# ---------------------------------------------------------------
echo "Contributor emails available:"
mapfile -t EMAILS < <(
  jq -r 'keys[]' "$TMP_FILE" | sed 's/\r$//'
)
for i in "${!EMAILS[@]}"; do
  printf "%2d) %s\n" "$((i+1))" "${EMAILS[$i]}"
done
echo

# ---------------------------------------------------------------
# 4. Interactive mapping
# ---------------------------------------------------------------
while true; do
  read -rp "Enter Jira assignee number to map (or press Enter to finish): " ANUM || true
  [[ -z "$ANUM" ]] && break
  ASSIGNEE="${ASSIGNEES[$((ANUM-1))]}"

  read -rp "Pick email number for \"$ASSIGNEE\": " ENUM
  EMAIL="${EMAILS[$((ENUM-1))]}"

  echo "Mapping all Jira tickets assigned to \"$ASSIGNEE\" -> $EMAIL"

  TMP_FILE2=$(mktemp)
  jq --arg assignee "$ASSIGNEE" --arg email "$EMAIL" \
   --slurpfile jira "$JIRA_ISSUES_JSON" '
    . as $out
    | ($jira[0]
       | map(
           select(
             (.assignee | type == "string")
             and ((.assignee | gsub("\\s+$"; "")) == ($assignee | gsub("\\s+$"; "")))
           )
         )
      ) as $tickets
    | $out[$email].tickets += $tickets
   ' "$TMP_FILE" > "$TMP_FILE2"
  mv "$TMP_FILE2" "$TMP_FILE"
done

# ---------------------------------------------------------------
# 5. Save final merged JSON
# ---------------------------------------------------------------
mv "$TMP_FILE" "$OUTPUT_JSON"
echo "Merged file saved to $OUTPUT_JSON"
jq . "$OUTPUT_JSON"
