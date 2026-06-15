#!/bin/bash
# Composition layer: hand the .pptx decks that readings.js downloaded to the
# standalone slides/ tool, which converts them to markdown in the vault.
#
# canvas-grabber and slides stay INDEPENDENT tools — neither imports the other
# (CLAUDE.md: "no cross-tool runtime coupling"). They communicate only through a
# queue file on disk: readings.js writes <pptx>\t<md-out> lines, this reads them.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
QUEUE="${OUTPUT_DIR:-$SCRIPT_DIR/output}/slides-convert-queue.tsv"
SLIDES_DIR="$SCRIPT_DIR/../slides"
CONVERT="$SLIDES_DIR/convert-slides"

if [ ! -f "$QUEUE" ]; then
  echo "no slide queue ($QUEUE) — run \`npm run readings\` with DOWNLOAD_READINGS=1 first. Nothing to do."
  exit 0
fi
if [ ! -x "$SLIDES_DIR/.venv/bin/python" ]; then
  echo "slides tool isn't set up ($SLIDES_DIR/.venv missing) — skipping conversion." >&2
  echo "Set it up once: cd ../slides && python3 -m venv .venv && .venv/bin/pip install -e ." >&2
  exit 0
fi

n=0; fail=0
while IFS=$'\t' read -r pptx out chapter; do
  [ -z "${pptx:-}" ] && continue
  if [ ! -f "$pptx" ]; then echo "  missing pptx (skipped): $pptx" >&2; continue; fi
  mkdir -p "$(dirname "$out")"
  # readings.js already resolved the chapter (incl. spelled-out numbers); pass it
  # through so the slides tool's heading matches the ch<NN> filename.
  args=( "$pptx" --out "$out" )
  [ -n "${chapter:-}" ] && args+=( --chapter "$chapter" )
  echo "converting: $(basename "$pptx")  ->  $out"
  if bash "$CONVERT" "${args[@]}"; then n=$((n+1)); else fail=$((fail+1)); echo "  convert failed: $pptx" >&2; fi
done < "$QUEUE"

echo "converted $n deck(s)${fail:+, $fail failed}."
