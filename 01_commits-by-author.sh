#!/bin/bash
# commits-by-author-json.sh
# Collect commits grouped by unique contributor (via email) into JSON
# Handles all branches + timezone offset

# ==== CONFIG ====
TOKEN="[REDACTED]"
REPO_NAME="finance-frontend"
START_DATE="2025-08-01"
END_DATE="2025-10-01"
ORG_NAME="BM-Technology-Et"
OUTPUT_FILE="data/commits.json"
# OUTPUT_FILE="data/${REPO_NAME}-${START_DATE}-${END_DATE}.json"
TZ_OFFSET="+3"   # adjust timezone hours (+3 = Ethiopia)
# =================

mkdir -p data

# Clone or fetch repo
if [ -d "$REPO_NAME" ]; then
    echo "[INFO] Fetching updates for $REPO_NAME..."
    cd "$REPO_NAME"
    git fetch --all
else
    echo "[INFO] Cloning $REPO_NAME..."
    repo_url_with_token="https://$TOKEN@github.com/$ORG_NAME/$REPO_NAME.git"
    git clone "$repo_url_with_token"
    cd "$REPO_NAME"
fi

echo "[INFO] Collecting commits between $START_DATE and $END_DATE..."

# Collect all unique emails + names
declare -A EMAIL_TO_NAME
while IFS= read -r line; do
    name=$(echo "$line" | sed -E 's/^(.*) <.*>$/\1/' | xargs)
    email=$(echo "$line" | sed -E 's/^.*<(.*)>$/\1/' | tr '[:upper:]' '[:lower:]' | xargs)
    EMAIL_TO_NAME["$email"]="$name"
done < <(git log --all --since="$START_DATE" --until="$END_DATE 23:59:59" \
            --format='%an <%ae>' | sort -u)

UNIQUE_EMAILS=$(printf "%s\n" "${!EMAIL_TO_NAME[@]}" | sort -u)

# Function to collect commits for an email
collect_commits() {
    local email="$1"
    local mode="$2"  # "regular" or "overtime"

    git log --all --since="$START_DATE" --until="$END_DATE 23:59:59" --author="$email" \
      --pretty=format:'%h|%ct|%s' | awk -F'|' -v mode="$mode" -v offset="$TZ_OFFSET" '
      BEGIN { first=1 }
      {
          hash=$1; ts=$2; msg=$3;

          # Apply timezone offset
          split(offset, parts, /[+-]/)
          sign=substr(offset,1,1)
          hours=substr(offset,2)
          if (sign == "-") {
              ts = ts - (hours * 3600)
          } else {
              ts = ts + (hours * 3600)
          }

          day=strftime("%u", ts)+0   # 1=Mon..7=Sun
          hour=strftime("%H", ts)+0  # 0-23

          isRegular=(day>=1 && day<=5 && hour>=9 && hour<17)

          if ((mode=="regular" && isRegular) || (mode=="overtime" && !isRegular)) {
              if (!first) { print "," } first=0;
              printf("{\"hash\":\"%s\",\"date\":\"%s\",\"time\":\"%s\",\"day\":\"%s\",\"message\":\"%s\"}",
                  hash,
                  strftime("%Y-%m-%d", ts),
                  strftime("%I:%M %p", ts),
                  strftime("%a", ts),
                  msg);
          }
      }'
}

# Start JSON
echo "{" > "../$OUTPUT_FILE"
echo "  \"contributors\": [" >> "../$OUTPUT_FILE"

first=1
for email in $UNIQUE_EMAILS; do
    name="${EMAIL_TO_NAME[$email]}"
    echo "[INFO] Processing contributor: $name <$email>"

    if [ $first -ne 1 ]; then
        echo "    }," >> "../$OUTPUT_FILE"
    fi
    first=0

    echo "    {" >> "../$OUTPUT_FILE"
    echo "      \"name\": \"${name}\"," >> "../$OUTPUT_FILE"
    echo "      \"emails\": [\"${email}\"]," >> "../$OUTPUT_FILE"
    echo "      \"commits\": {" >> "../$OUTPUT_FILE"

    # Regular commits
    echo "        \"regular\": [" >> "../$OUTPUT_FILE"
    collect_commits "$email" "regular" >> "../$OUTPUT_FILE"
    echo "        ]," >> "../$OUTPUT_FILE"

    # Overtime commits
    echo "        \"overtime\": [" >> "../$OUTPUT_FILE"
    collect_commits "$email" "overtime" >> "../$OUTPUT_FILE"
    echo "        ]" >> "../$OUTPUT_FILE"

    echo "      }" >> "../$OUTPUT_FILE"
done

echo "    }" >> "../$OUTPUT_FILE"
echo "  ]" >> "../$OUTPUT_FILE"
echo "}" >> "../$OUTPUT_FILE"

echo "[INFO] Commits saved to $OUTPUT_FILE"
