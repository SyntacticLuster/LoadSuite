#!/usr/bin/env bash
set -euo pipefail

# Sequentially run RouteCast package tests (monorepo-friendly).

root_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

(cd "$root_dir/packages/routecast-core" && poetry run pytest)
(cd "$root_dir/packages/routecast-routing" && poetry run pytest)
(cd "$root_dir/packages/routecast-sources" && poetry run pytest)
(cd "$root_dir/apps/routecast-api" && poetry run pytest)
