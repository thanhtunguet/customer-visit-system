#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")"/../.. && pwd)
cd "$ROOT_DIR/apps/web"

if command -v pnpm >/dev/null 2>&1; then
  PKG=pnpm
else
  PKG=npm
fi

$PKG install
exec $PKG run dev
