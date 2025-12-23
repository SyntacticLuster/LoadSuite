#!/usr/bin/env bash
set -euo pipefail

# LoadSuite cPanel/Passenger deploy helper.
#
# What it does (opinionated, minimal):
# 1) Creates a deploy branch from your current HEAD.
# 2) Stages *everything* (including untracked) and commits it.
# 3) Pushes deploy branch.
# 4) Fast-forwards main to that deploy branch and pushes main.
# 5) SSHes to the server, clones/pulls the repo into REMOTE_DIR, resets to origin/main.
# 6) Restarts Passenger by touching tmp/restart.txt.
#
# You must set:
#   DEPLOY_SSH_HOST   e.g. orbitsuite.cloud
#   DEPLOY_SSH_USER   e.g. username
#
# Optional overrides:
#   DEPLOY_REMOTE_DIR e.g. ~/apps/LoadSuite
#   DEPLOY_BRANCH     e.g. deploy-2025-12-23
#   DEPLOY_BASE_BRANCH default: main
#   DEPLOY_REMOTE      default: origin
#   DEPLOY_REPO_URL    default: git remote url for DEPLOY_REMOTE
#   DEPLOY_COMMIT_MSG  default: "Deploy"
#
# Example:
#   DEPLOY_SSH_HOST=orbitsuite.cloud DEPLOY_SSH_USER=username ./scripts/deploy_cpanel.sh

require_env() {
  local name="$1"
  if [[ -z "${!name:-}" ]]; then
    echo "Missing required env var: $name" >&2
    exit 2
  fi
}

confirm() {
  local prompt="$1"
  if [[ "${DEPLOY_YES:-}" == "1" || "${DEPLOY_YES:-}" == "true" || "${DEPLOY_YES:-}" == "yes" ]]; then
    return 0
  fi
  read -r -p "$prompt [y/N] " ans
  case "$ans" in
    y|Y|yes|YES) return 0 ;;
    *) return 1 ;;
  esac
}

main() {
  # SSH target can be provided as a full target (user@host or ssh-config alias)
  # or as host + (optional) user.
  local ssh_target_override="${DEPLOY_SSH_TARGET:-}"
  local ssh_host="${DEPLOY_SSH_HOST:-}"
  local ssh_user="${DEPLOY_SSH_USER:-}"

  if [[ -z "$ssh_target_override" && -z "$ssh_host" ]]; then
    echo "Missing required env var: DEPLOY_SSH_TARGET or DEPLOY_SSH_HOST" >&2
    exit 2
  fi

  local remote="${DEPLOY_REMOTE:-origin}"
  local base_branch="${DEPLOY_BASE_BRANCH:-main}"
  local deploy_branch="${DEPLOY_BRANCH:-deploy-$(date +%F-%H%M)}"
  local commit_msg="${DEPLOY_COMMIT_MSG:-Deploy}"
  # Remote path semantics:
  # - If DEPLOY_REMOTE_DIR is absolute, use it.
  # - If it starts with "~/", expand on the remote side.
  # - Otherwise treat as relative to remote $HOME.
  local remote_dir="${DEPLOY_REMOTE_DIR:-apps/LoadSuite}"
  local repo_url="${DEPLOY_REPO_URL:-}" 

  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Not in a git repo." >&2
    exit 2
  fi

  if [[ -z "$repo_url" ]]; then
    repo_url="$(git remote get-url "$remote")"
  fi

  echo "Repo:       $repo_url"
  echo "Remote:     $remote"
  echo "Base:       $base_branch"
  echo "Deploy:     $deploy_branch"
  local ssh_target=""
  if [[ -n "$ssh_target_override" ]]; then
    ssh_target="$ssh_target_override"
  elif [[ -n "$ssh_user" ]]; then
    ssh_target="${ssh_user}@${ssh_host}"
  else
    # Rely on ~/.ssh/config for User if not provided.
    ssh_target="$ssh_host"
  fi

  echo "Server:     $ssh_target"
  echo "Remote dir: $remote_dir"
  echo

  if ! confirm "This will stage+commit ALL changes and push to $base_branch. Continue?"; then
    echo "Aborted." >&2
    exit 1
  fi

  git fetch "$remote" --prune

  git checkout -B "$deploy_branch"
  git add -A

  if git diff --cached --quiet; then
    echo "No changes to commit. Skipping commit." >&2
  else
    git commit -m "$commit_msg"
  fi

  git push -u "$remote" "$deploy_branch"

  git checkout "$base_branch"
  git merge --ff-only "$deploy_branch"
  git push "$remote" "$base_branch"

  echo
  echo "Updating server checkout and restarting Passenger…"

  ssh "$ssh_target" \
    "REMOTE_DIR=$(printf %q "$remote_dir") REMOTE=$(printf %q "$remote") BASE_BRANCH=$(printf %q "$base_branch") REPO_URL=$(printf %q "$repo_url") bash -s" <<'REMOTE_SCRIPT'
set -euo pipefail

dir="$REMOTE_DIR"
if [[ "$dir" == "~/"* ]]; then
  dir="$HOME/${dir#~/}"
elif [[ "$dir" != /* ]]; then
  dir="$HOME/$dir"
fi

mkdir -p "$(dirname "$dir")"

# Best-effort: avoid interactive host key prompt when using GitHub SSH.
if [[ "$REPO_URL" == git@github.com:* || "$REPO_URL" == ssh://git@github.com/* ]]; then
  mkdir -p "$HOME/.ssh"
  chmod 700 "$HOME/.ssh" || true
  touch "$HOME/.ssh/known_hosts"
  chmod 600 "$HOME/.ssh/known_hosts" || true

  if command -v ssh-keygen >/dev/null 2>&1 && command -v ssh-keyscan >/dev/null 2>&1; then
    if ! ssh-keygen -F github.com -f "$HOME/.ssh/known_hosts" >/dev/null 2>&1; then
      ssh-keyscan -H github.com >> "$HOME/.ssh/known_hosts" 2>/dev/null || true
    fi
  fi
fi

if [[ ! -d "$dir/.git" ]]; then
  rm -rf "$dir"
  git clone "$REPO_URL" "$dir"
fi

cd "$dir"
git fetch --prune "$REMOTE"
git checkout -f "$BASE_BRANCH"
git reset --hard "$REMOTE/$BASE_BRANCH"

mkdir -p tmp
touch tmp/restart.txt
echo "Passenger restart triggered via tmp/restart.txt"
REMOTE_SCRIPT

  echo "Done. If the app doesn't restart, use the cPanel Python App 'Restart' button." 
}

main "$@"
