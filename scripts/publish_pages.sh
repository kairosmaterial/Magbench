#!/usr/bin/env bash
# Prepare the static Pages branch locally; publishing is a separate maintainer action.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
page_worktree="${1:-$(dirname "$repo_dir")/Magbench_pages}"
python "$repo_dir/scripts/build_site.py"
if [ -e "$page_worktree" ]; then
  if [ "$(git -C "$page_worktree" rev-parse --show-toplevel 2>/dev/null)" != "$page_worktree" ] || [ "$(git -C "$page_worktree" branch --show-current)" != gh-pages ]; then
    printf '%s\n' 'Destination must be the separate gh-pages worktree.' >&2
    exit 1
  fi
  if [ -n "$(git -C "$page_worktree" status --porcelain)" ]; then
    printf '%s\n' 'The Pages worktree has uncommitted changes; review them before rebuilding.' >&2
    exit 1
  fi
elif git -C "$repo_dir" show-ref --verify --quiet refs/heads/gh-pages; then
  git -C "$repo_dir" worktree add "$page_worktree" gh-pages
else
  git -C "$repo_dir" worktree add --detach "$page_worktree" HEAD
  git -C "$page_worktree" checkout --orphan gh-pages
fi
publication_stage="$(mktemp -d "$(dirname "$page_worktree")/.magbench-pages-XXXXXXXX")"
trap 'rm -rf -- "$publication_stage"' EXIT
python "$repo_dir/scripts/prepare_pages.py" "$repo_dir/site/dist" "$publication_stage/site"
git -C "$page_worktree" rm -rf -- .
python - "$publication_stage/site" "$page_worktree" <<'PY'
from pathlib import Path
import shutil
import sys
source,target=map(Path,sys.argv[1:])
for path in source.iterdir():
    destination=target/path.name
    if path.is_dir():shutil.copytree(path,destination)
    else:shutil.copyfile(path,destination)
PY
initial_commit="$(git -C "$repo_dir" rev-list --max-parents=0 HEAD | tail -n 1)"
commit_name="$(git -C "$repo_dir" show -s --format=%an "$initial_commit")"
commit_email="$(git -C "$repo_dir" show -s --format=%ae "$initial_commit")"
git -C "$page_worktree" add --all
if ! git -C "$page_worktree" diff --cached --quiet; then
  git -C "$page_worktree" -c user.name="$commit_name" -c user.email="$commit_email" commit -m 'Build MagBench Pages site'
fi
printf 'Prepared local gh-pages commit in %s. No remote update was made.\n' "$page_worktree"
