#!/usr/bin/env bash
# Create the team-pipeline GitHub issues from the markdown files in this folder.
#
# Prints what it would do unless --create is passed. Set ASSIGNEE_L,
# ASSIGNEE_A, ASSIGNEE_B, ASSIGNEE_C and ASSIGNEE_D to GitHub handles to
# assign each workstream, for example:
#
#   ASSIGNEE_L=EBOD13 ASSIGNEE_A=ibll ./create-issues.sh            # dry run
#   ASSIGNEE_L=EBOD13 ASSIGNEE_A=ibll ./create-issues.sh --create   # for real
set -euo pipefail

REPO="ibll/home-assistant-core"
cd "$(dirname "$0")"

create=false
if [[ "${1:-}" == "--create" ]]; then
  create=true
fi

run() {
  if $create; then
    "$@"
  else
    printf 'would run:'
    printf ' %q' "$@"
    printf '\n'
  fi
}

run gh label create team-pipeline --repo "$REPO" --force --color 1d76db --description "Course CI/CD pipeline work"
run gh label create ai --repo "$REPO" --force --color 8250df --description "Uses AI inside the pipeline"
for ws in L A B C D; do
  run gh label create "workstream:$ws" --repo "$REPO" --force --color 0e8a16
done
for week in 1 2 3 4; do
  run gh label create "week:$week" --repo "$REPO" --force --color fbca04
done

# Lead issues first so L0 gets the lowest issue number.
for file in L[0-9].md A[0-9].md B[0-9].md C[0-9].md D[0-9].md; do
  title=$(sed -n 's/^<!-- title: \(.*\) -->$/\1/p' "$file")
  labels=$(sed -n 's/^<!-- labels: \(.*\) -->$/\1/p' "$file" | tr -d ' ')
  ws=${file:0:1}
  assignee_var="ASSIGNEE_$ws"
  assignee=${!assignee_var:-}

  args=(gh issue create --repo "$REPO" --title "$title" --label "$labels"
    --body "$(tail -n +4 "$file")")
  if [[ -n "$assignee" ]]; then
    args+=(--assignee "$assignee")
  fi

  if $create; then
    "${args[@]}"
  else
    echo "would create: $title  [labels: $labels] [assignee: ${assignee:-none}]"
  fi
done
