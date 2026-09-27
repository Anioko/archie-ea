#!/usr/bin/env bash
# Copy production's local-only branches to the private backup remote.
#
#   ./deploy/mirror_prod_branches.sh [--dry-run]
#
# Run this from a workstation that can reach BOTH the app host over SSH and
# GitHub - the production box itself cannot. It has no credential helper, no
# stored credentials and no SSH key, and its only remote is the public repo. So
# every commit made there stays there: on 2026-08-03 that was 44 commits across
# six branches existing nowhere else in the world, including the SRI gate, the
# CRLF/vendored-asset fix and the tenancy corrections.
#
# The database dumps have the same problem in a quieter way - archie-backup.sh
# writes to /root/deploy-backups, which is the same disk it is protecting. Lose
# the droplet and you lose the backups with it. This script addresses the code
# half; the database half needs an off-box destination.
#
# Pushes to the PRIVATE remote only. Production history is unreviewed, and the
# other remote is a public repository.
set -euo pipefail

PROD_REMOTE=${PROD_REMOTE:-prodhost}          # ssh://root@<host>/root/archie-ea
BACKUP_REMOTE=${BACKUP_REMOTE:-sg}            # must be private
BASELINE=${BASELINE:-origin/main}             # what counts as "already safe"
STAMP=$(date +%Y-%m-%d)
NS="backup/prod-$STAMP"
DRY_RUN=${1:-}

say() { printf '\n== %s\n' "$*"; }

say "0. refusing to push production history to a public repository"
url=$(git remote get-url "$BACKUP_REMOTE")
if command -v gh >/dev/null 2>&1; then
    slug=$(printf '%s' "$url" | sed -E 's#.*github\.com[:/]([^/]+/[^/.]+)(\.git)?#\1#')
    private=$(gh repo view "$slug" --json isPrivate -q .isPrivate 2>/dev/null || echo unknown)
    echo "  $BACKUP_REMOTE -> $slug (private=$private)"
    [ "$private" = "true" ] || { echo "ABORT: backup remote is not known-private" >&2; exit 1; }
else
    echo "  gh not installed - cannot confirm $url is private; confirm manually" >&2
fi

say "1. fetching every branch from production"
git fetch "$PROD_REMOTE" "refs/heads/*:refs/remotes/$PROD_REMOTE/*"

say "2. branches carrying commits not in $BASELINE"
# Rank by how much unique work each carries, most first, so the branch that
# contains the others is considered before them and they drop out as contained.
ranked=$(git branch -r | grep "$PROD_REMOTE/" | grep -v HEAD | sed 's/^ *//' \
         | while read -r b; do
               c=$(git rev-list --count "$BASELINE..$b" 2>/dev/null || echo 0)
               # An `if` rather than `&&`: under `set -e`, a trailing `&&` that
               # fails on the last branch makes the whole subshell exit 1 and
               # the script dies here having silently backed up nothing.
               if [ "$c" -gt 0 ]; then printf '%s %s\n' "$c" "$b"; fi
           done | sort -rn)

tips=()
while read -r count branch; do
    [ -n "${branch:-}" ] || continue
    contained=no
    for chosen in ${tips[@]+"${tips[@]}"}; do
        if git merge-base --is-ancestor "$branch" "$chosen" 2>/dev/null; then
            contained=yes
            break
        fi
    done
    printf '  %-50s %4s commits  %s\n' "$branch" "$count" \
        "$([ "$contained" = yes ] && echo '(already inside a selected tip)' || echo 'SELECTED')"
    [ "$contained" = yes ] || tips+=("$branch")
done <<< "$ranked"

[ ${#tips[@]} -gt 0 ] || { echo "  nothing to back up - production is fully pushed"; exit 0; }

say "3. secret-scanning what is about to be pushed"
# Unreviewed history goes nowhere until gitleaks has seen it. Run on the app
# host, which has Docker; this workstation may not.
host=$(git remote get-url "$PROD_REMOTE" | sed -E 's#ssh://([^@]+@)?([^/]+).*#\1\2#')
for tip in "${tips[@]}"; do
    short=${tip#"$PROD_REMOTE"/}
    echo "  scanning $BASELINE..$short"
    ssh -o BatchMode=yes "$host" \
        "cd /root/archie-ea && docker run --rm --memory=512m -v /root/archie-ea:/repo \
         ghcr.io/gitleaks/gitleaks:latest detect --source=/repo --redact --no-banner \
         --exit-code 1 --log-opts='$BASELINE..$short'" 2>&1 | grep -aE "commits scanned|leaks" | sed 's/^/    /'
done

say "4. pushing to $BACKUP_REMOTE under $NS/"
refspecs=()
for tip in "${tips[@]}"; do
    name=$(printf '%s' "${tip#"$PROD_REMOTE"/}" | tr '/' '-')
    refspecs+=("refs/remotes/$tip:refs/heads/$NS/$name")
    echo "  $tip -> $NS/$name"
done
if [ "$DRY_RUN" = "--dry-run" ]; then
    echo "  (dry run - nothing pushed)"
    exit 0
fi
git push "$BACKUP_REMOTE" "${refspecs[@]}"

say "5. verifying the copy matches production"
mismatch=0
for tip in "${tips[@]}"; do
    name=$(printf '%s' "${tip#"$PROD_REMOTE"/}" | tr '/' '-')
    local_sha=$(git rev-parse "$tip")
    remote_sha=$(git ls-remote "$BACKUP_REMOTE" "refs/heads/$NS/$name" | cut -f1)
    if [ "$local_sha" = "$remote_sha" ]; then
        printf '  MATCH  %-46s %s\n' "$name" "${local_sha:0:10}"
    else
        printf '  DIFFER %-46s remote=%s prod=%s\n' "$name" "${remote_sha:0:10}" "${local_sha:0:10}"
        mismatch=$((mismatch+1))
    fi
done
[ "$mismatch" -eq 0 ] || { echo; echo "BACKUP FAILED - $mismatch branch(es) did not copy" >&2; exit 1; }

echo
echo "BACKUP VERIFIED - ${#tips[@]} branch tip(s) mirrored to $BACKUP_REMOTE under $NS/"
