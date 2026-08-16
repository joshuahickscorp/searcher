#!/usr/bin/env bash
# Install the audited VisionMCP donor at its pinned SHA.
#
# The donor is not on PyPI, and `uv pip install git+…@<sha>` fails on this commit:
# it carries a gitlink at artifacts/world-engine/step-28/hostile-pack-fixture with
# no matching .gitmodules entry, so git aborts the checkout. Cloning without
# submodule recursion works, so that is what this does.
#
# Override the clone location with SEARCHER_DONOR_DIR.
set -euo pipefail

REPO="${SEARCHER_DONOR_REPO:-https://github.com/joshuahickscorp/visionmcp.git}"
SHA="18ee3c06d27f04937d1681dea5fa2650131e4b2a"
DIR="${SEARCHER_DONOR_DIR:-$HOME/.searcher-donors/visionmcp}"

if [ ! -d "$DIR/.git" ]; then
  mkdir -p "$(dirname "$DIR")"
  git clone --no-recurse-submodules "$REPO" "$DIR"
fi

git -C "$DIR" fetch --no-recurse-submodules origin "$SHA" 2>/dev/null || git -C "$DIR" fetch --no-recurse-submodules
git -C "$DIR" checkout --no-recurse-submodules --quiet "$SHA"

ACTUAL="$(git -C "$DIR" rev-parse HEAD)"
if [ "$ACTUAL" != "$SHA" ]; then
  echo "donor SHA mismatch: wanted $SHA, got $ACTUAL" >&2
  exit 1
fi

uv pip install "$DIR"
uv run python -c "
import visionmcp
from searcher.integrations.visionmcp.compatibility import PINNED_VERSION
assert visionmcp.__version__ == PINNED_VERSION, (visionmcp.__version__, PINNED_VERSION)
print('donor installed:', visionmcp.__version__, 'at', '$ACTUAL')
"
