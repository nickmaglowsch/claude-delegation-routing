#!/usr/bin/env bash
set -euo pipefail

CLAUDE_DIR="${CLAUDE_DIR:-$HOME/.claude}"
PASEO_DIR="${PASEO_DIR:-$HOME/.paseo}"
SRC="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$CLAUDE_DIR/skills" "$PASEO_DIR"

cp "$SRC/DELEGATION.md" "$CLAUDE_DIR/DELEGATION.md"
rm -rf "$CLAUDE_DIR/skills/delegation-audit"
cp -R "$SRC/skills/delegation-audit" "$CLAUDE_DIR/skills/"

if [ -f "$PASEO_DIR/orchestration-preferences.json" ]; then
  echo "kept existing $PASEO_DIR/orchestration-preferences.json (compare with $SRC/orchestration-preferences.json)"
else
  cp "$SRC/orchestration-preferences.json" "$PASEO_DIR/orchestration-preferences.json"
fi

touch "$CLAUDE_DIR/CLAUDE.md"
grep -qx '@DELEGATION.md' "$CLAUDE_DIR/CLAUDE.md" || printf '@DELEGATION.md\n' >> "$CLAUDE_DIR/CLAUDE.md"

echo "Installed. Open a NEW Claude Code session (the @include loads at startup)."
echo "Verify the scanner: python3 $CLAUDE_DIR/skills/delegation-audit/scripts/scan.py --days 30"
