#!/usr/bin/env bash
# Prepare the static Pages branch locally; publishing is a separate maintainer action.
set -euo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
page_worktree="${1:-$(dirname "$repo_dir")/Magbench_pages}"
python "$repo_dir/scripts/build_site.py"
if git -C "$repo_dir" show-ref --verify --quiet refs/heads/gh-pages; then
  printf '%s\n' 'Local gh-pages already exists. Review or remove that local branch and its worktree before preparing another build.' >&2
  exit 1
fi
if [ -e "$page_worktree" ]; then
  printf '%s\n' 'The Pages worktree destination already exists. Choose an empty destination.' >&2
  exit 1
fi
git -C "$repo_dir" worktree add --detach "$page_worktree" HEAD
git -C "$page_worktree" checkout --orphan gh-pages
git -C "$page_worktree" rm -rf -- .
python - "$repo_dir/site/dist" "$page_worktree" <<'PY'
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
git -C "$page_worktree" -c user.name="$commit_name" -c user.email="$commit_email" commit -m 'Build MagBench Pages site'
printf 'Prepared local gh-pages commit in %s. No remote update was made.\n' "$page_worktree"
