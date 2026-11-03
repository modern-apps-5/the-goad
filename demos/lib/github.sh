# Shared by the demos that change main and run a workflow: open a pull
# request with an edit, merge it, start a workflow, and wait for a run.
# The demos' scripts source it. It is not run on its own.
#
# Every change goes through the GitHub API, so the presenter's own checkout
# is never touched. Needs gh, logged in with write access to the
# repository, jq and perl.

REPO=${REPO:-modern-apps-5/the-goad}

DEMO_TMP=$(mktemp -d)
trap 'rm -rf "$DEMO_TMP"' EXIT

# Print a file as it is on main.
main_file() {
  gh api "repos/$REPO/contents/$1?ref=main" --jq .content | base64 -d
}

# Make a branch from main.
new_branch() {
  local sha
  sha=$(gh api "repos/$REPO/git/ref/heads/main" --jq .object.sha)
  gh api -X POST "repos/$REPO/git/refs" -f "ref=refs/heads/$1" -f "sha=$sha" >/dev/null
}

delete_branch() {
  gh api -X DELETE "repos/$REPO/git/refs/heads/$1" >/dev/null
}

# Commit an edit of one file to a branch. The edit is a perl -0pe
# expression. Returns 3 and commits nothing when the edit changes nothing.
edit_file() {
  local branch=$1 path=$2 expr=$3 message=$4
  # A caller's && turns off set -e in here, so each step is checked.
  gh api "repos/$REPO/contents/$path?ref=$branch" > "$DEMO_TMP/doc.json" || return 1
  jq -r .content "$DEMO_TMP/doc.json" | base64 -d > "$DEMO_TMP/old" || return 1
  [[ -s $DEMO_TMP/old ]] || { echo "$path is empty on $branch" >&2; return 1; }
  perl -0pe "$expr" "$DEMO_TMP/old" > "$DEMO_TMP/new" || return 1
  cmp -s "$DEMO_TMP/old" "$DEMO_TMP/new" && return 3
  base64 < "$DEMO_TMP/new" | tr -d '\n' > "$DEMO_TMP/new.b64"
  jq -n --arg message "$message" --arg branch "$branch" \
    --arg sha "$(jq -r .sha "$DEMO_TMP/doc.json")" --rawfile content "$DEMO_TMP/new.b64" \
    '{message: $message, branch: $branch, sha: $sha, content: $content}' |
    gh api -X PUT "repos/$REPO/contents/$path" --input - >/dev/null
}

# Open a pull request from a branch to main, merge it, and delete the
# branch. Sets MERGE_SHA to the merge commit.
merge_branch() {
  local branch=$1 title=$2 body=$3 url
  url=$(gh pr create -R "$REPO" --base main --head "$branch" --title "$title" --body "$body")
  echo "Pull request: $url"
  gh pr merge -R "$REPO" "$url" --merge >/dev/null
  delete_branch "$branch"
  MERGE_SHA=$(gh pr view -R "$REPO" "$url" --json mergeCommit --jq .mergeCommit.oid)
}

latest_run() {
  gh run list -R "$REPO" -w "$1" -e workflow_dispatch -L 1 --json databaseId --jq '.[0].databaseId // ""'
}

# Wait for a run to end. Fails if the run failed.
wait_run() {
  echo "Run: $(gh run view -R "$REPO" "$1" --json url --jq .url)"
  gh run watch -R "$REPO" "$1" --exit-status --interval 10 >/dev/null
}

# Start a workflow on main and wait for it. The other arguments are gh
# workflow run's, such as -f apply=true. Sets RUN_ID.
run_workflow() {
  local workflow=$1 before
  shift
  before=$(latest_run "$workflow")
  gh workflow run "$workflow" -R "$REPO" --ref main "$@"
  RUN_ID=$before
  for _ in $(seq 60); do
    RUN_ID=$(latest_run "$workflow")
    [[ -n $RUN_ID && $RUN_ID != "$before" ]] && break
    sleep 2
  done
  [[ $RUN_ID != "$before" ]] || { echo "$workflow: the run did not start" >&2; return 1; }
  wait_run "$RUN_ID"
}

# Wait for the run of a workflow that a push of a commit started. Sets
# RUN_ID.
wait_push_run() {
  local workflow=$1 commit=$2
  RUN_ID=
  for _ in $(seq 60); do
    RUN_ID=$(gh run list -R "$REPO" -w "$workflow" -c "$commit" -L 1 --json databaseId --jq '.[0].databaseId // ""')
    [[ -n $RUN_ID ]] && break
    sleep 2
  done
  [[ -n $RUN_ID ]] || { echo "$workflow: no run started for $commit" >&2; return 1; }
  wait_run "$RUN_ID"
}

# Print what each Terraform job of a run planned: "No changes.", the
# "Plan:" line, or each resource and its action for a job that hides its
# plan. Returns 1 if any job planned a change, and 2 if the log has no
# plan. "Plan: 0 to add, 0 to change, 0 to destroy." is no change: it is
# what a removed block that only forgets a resource plans. Prints no value.
plan_summary() {
  gh run view -R "$REPO" "$1" --log |
    awk -F'\t' '{ sub(/^[^ ]+ /, "", $3); print $1 "\t" $3 }' |
    grep -E $'\t(No changes\\.|Plan: [0-9]+ to add|(create|update|delete|replace)[a-z,]* [a-z_]+\\.)' |
    sort -u > "$DEMO_TMP/plan"
  [[ -s $DEMO_TMP/plan ]] || { echo "No plan in the run's log." >&2; return 2; }
  sed $'s/\t/: /' "$DEMO_TMP/plan"
  ! grep -qvE $'\t(No changes\\.|Plan: 0 to add, 0 to change, 0 to destroy\\.)' "$DEMO_TMP/plan"
}

# The namespace a vcf context points at.
context_namespace() {
  kubectl config view -o jsonpath="{.contexts[?(@.name==\"$1\")].context.namespace}"
}

# Print a dot every 5 seconds until a command succeeds, for at most the
# given number of seconds.
wait_for() {
  local what=$1 timeout=$2 start=$SECONDS
  shift 2
  printf '%s' "$what"
  until "$@" >/dev/null 2>&1; do
    ((SECONDS - start < timeout)) || { echo " gave up after ${timeout}s" >&2; return 1; }
    printf .
    sleep 5
  done
  echo " done ($((SECONDS - start))s)"
}
