#!/usr/bin/env bash
#
# Scan ALL of git history - not just the current tree - for content that should
# never have been committed.
#
# Run this before:
#   - flipping a repo from private to public
#   - submitting a manuscript that cites the repo
#   - sharing the repo with a collaborating institution
#
# Adding a path to .gitignore does NOT remove what is already committed. Two
# Huang Lab repos deleted 122,000 and 29,000 lines of cluster job output
# respectively, and every line is still reachable in history, complete with
# absolute Minerva paths.
#
# If this finds something real, the fix is `git filter-repo` followed by a force
# push - which means doing it while the repo has no external forks or clones.
#
# Usage: ./scripts/scan_history.sh [--full]
#   default  scan deleted files and blob names across history (fast)
#   --full   also grep every blob's content (slow: minutes on a large repo)

set -uo pipefail

FULL=0
[ "${1:-}" = "--full" ] && FULL=1

FOUND=0
red()  { printf '\033[31m%s\033[0m\n' "$1"; }
warn() { printf '\033[33m%s\033[0m\n' "$1"; }
ok()   { printf '\033[32m%s\033[0m\n' "$1"; }
hdr()  { printf '\n\033[1m== %s\033[0m\n' "$1"; }

# Patterns worth finding. Tune per project - a genomics repo has different
# identifiers than an EHR repo.
#
# These are POSIX ERE, because `git grep -E` compiles them with the system
# regcomp and NOT with PCRE. `\s` is a PCRE/GNU-grep extension: POSIX ERE reads
# it as a literal `s`, silently and without an error. Use `[[:space:]]`.
#
# This is not a style point. The rule below used to read
# `password\s*[=:]\s*["'"'"'][^"'"'"']`, which POSIX expands to "password",
# then zero or more literal `s`, then `[=:]` - so it matched `password:"x"` and
# missed `password: "x"` and `password = "x"`. Those are the two ways anyone
# actually writes it. A real database password sat in a public lab repo for 665
# days and this scanner, run over full history, reported nothing.
PATTERNS=(
    '/sc/arion/'                      # Minerva project and scratch paths
    '/hpc/users/'                     # Minerva home paths
    '/Users/[a-z]'                    # macOS home paths
    'MRN'                             # medical record number, by name
    '[^0-9]1[0-9]{7}[^0-9]'           # 8-digit MRN-shaped strings
    'ghp_[A-Za-z0-9]{20,}'            # GitHub personal access token
    'github_pat_[A-Za-z0-9_]{20,}'
    'AKIA[0-9A-Z]{16}'                # AWS access key
    'sk-[A-Za-z0-9]{20,}'             # OpenAI-style key
    'sk-ant-[A-Za-z0-9-]{20,}'        # Anthropic key
    'BEGIN (RSA|OPENSSH|DSA|EC) PRIVATE KEY'
    # An assignment of a quoted literal to a secret-ish name. The trailing
    # [^"'"'"'] rejects the empty string, so `password: ""` in a .env.example
    # does not fire.
    '(password|passwd|secret|api[_-]?key|access[_-]?token|auth[_-]?token|private[_-]?key)[[:space:]]*[=:][[:space:]]*["'"'"'][^"'"'"']'
    # A .env-style line with a literal value. Anchored and upper-case on
    # purpose: `PASSWORD = args.password` in code is a false positive, a line
    # that starts `DB_PASSWORD=hunter2` is not. `$` and `{` exclude
    # `PASSWORD=${PASSWORD}` and `PASSWORD=$(...)`; requiring one character
    # after `=` excludes the empty `password=` of a .env.example.
    '^[A-Z_]*(PASSWORD|PASSWD|SECRET|TOKEN|API_?KEY)[A-Z_]*=[^[:space:]$#{]'
    # Credentials inside a URL: postgres://user:hunter2@host.
    '://[^/[:space:]:@]+:[^/[:space:]@]+@'
)

# Paths excluded from the content scan: the scanner itself, plus anything listed
# one pathspec per line in .scanignore (documentation that quotes paths as
# examples, test fixtures with synthetic identifiers).
EXCLUDES=(':!scripts/scan_history.sh' ':!scripts/check_hygiene.sh')
if [ -f .scanignore ]; then
    while IFS= read -r line; do
        case "$line" in ''|'#'*) continue ;; esac
        EXCLUDES+=(":!$line")
    done < .scanignore
fi

hdr "1. Files ever deleted from history"
echo "These are gone from the tree but still in every clone."
DELETED=$(git log --all --diff-filter=D --name-only --format='' | sort -u | grep -v '^$' || true)
if [ -n "$DELETED" ]; then
    printf '%s\n' "$DELETED" | head -50
    COUNT=$(printf '%s\n' "$DELETED" | wc -l | tr -d ' ')
    [ "$COUNT" -gt 50 ] && echo "... and $((COUNT - 50)) more"
else
    ok "None."
fi

hdr "2. Suspicious filenames anywhere in history"
SUSPECT=$(git log --all --pretty=format: --name-only | sort -u \
    | grep -iE '(\.stdout$|\.stderr$|\.out$|\.err$|(^|/)logs?/|(^|/)tmp\.|\.env$|\.pem$|\.key$|id_rsa|\.DS_Store$|\.RData$|credentials|\.vcf(\.gz)?$|\.bam$|\.cram$|\.fastq(\.gz)?$)' || true)
if [ -n "$SUSPECT" ]; then
    red "Found file names that suggest data, logs, or secrets:"
    printf '%s\n' "$SUSPECT" | head -50
    FOUND=1
else
    ok "None."
fi

hdr "3. Sensitive patterns in the current tree"
for p in "${PATTERNS[@]}"; do
    hits=$(git grep -nIE "$p" -- ':!scripts/scan_history.sh' ':!scripts/check_hygiene.sh' 2>/dev/null | head -5 || true)
    if [ -n "$hits" ]; then
        red "pattern: $p"
        printf '%s\n' "$hits"
        FOUND=1
    fi
done
[ "$FOUND" -eq 0 ] && ok "None in the current tree."

if [ "$FULL" -eq 1 ]; then
    hdr "4. Sensitive patterns across ALL history (slow)"
    REVS=$(git rev-list --all)
    if [ -z "$REVS" ]; then
        ok "No commits."
    else
        for p in "${PATTERNS[@]}"; do
            # shellcheck disable=SC2086
            hits=$(git grep -nIE "$p" $REVS -- ':!scripts/scan_history.sh' ':!scripts/check_hygiene.sh' 2>/dev/null | head -5 || true)
            if [ -n "$hits" ]; then
                red "pattern: $p"
                printf '%s\n' "$hits"
                FOUND=1
            fi
        done
        [ "$FOUND" -eq 0 ] && ok "None anywhere in history."
    fi
else
    hdr "4. Full-history content scan"
    warn "Skipped. Re-run with --full before making this repo public."
fi

hdr "5. Ten largest blobs ever committed"
git rev-list --objects --all \
    | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' 2>/dev/null \
    | awk '$1 == "blob" {print $3, $4}' | sort -rn | head -10 \
    | awk '{printf "  %8.2f MB  %s\n", $1/1048576, $2}'

hdr "Next steps if anything above is real"
cat <<'TXT'
  1. Confirm the hit is genuine, not a false positive on an 8-digit number.
  2. Remove it from history:
       pip install git-filter-repo
       git filter-repo --invert-paths --path <file>            # a whole file
       git filter-repo --replace-text <(echo 'literal:SECRET==>REDACTED')
  3. Force-push, and have every collaborator re-clone. Old clones keep the data.
  4. If a credential was exposed, rotate it. Removing it from git is not enough -
     assume it was scraped.
  5. If the repo was ever public, treat the content as public permanently.
TXT

exit 0
