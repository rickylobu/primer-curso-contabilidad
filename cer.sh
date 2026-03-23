#!/usr/bin/env bash
# cer.sh -- Clean Extractor Results (macOS / Linux / Git Bash)
# Usage: bash cer.sh [mode]
# Modes: (default) | full | viewer | all

set -euo pipefail
MODE="${1:-default}"
GREEN='\033[0;32m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; NC='\033[0m'

ok()   { echo -e "  ${GREEN}[OK]  $1${NC}"; }
warn() { echo -e "  ${YELLOW}[!]   $1${NC}"; }
info() { echo -e "  ${CYAN}-->   $1${NC}"; }

echo ""
echo "============================================================"
info "CER -- Clean Extractor Results  |  mode: $MODE"
echo "============================================================"
echo ""

for f in "output/.extraction_state.json" "output/.extraction_state.tmp"; do
    if [ -f "$f" ]; then rm -f "$f"; ok "Deleted: $f"
    else warn "Not found (already clean): $f"; fi
done

if [[ "$MODE" == "full" || "$MODE" == "all" ]]; then
    if [ -d "output/pages" ]; then
        COUNT=$(find output/pages -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
        rm -f output/pages/*.md 2>/dev/null || true
        ok "Deleted $COUNT .md files from output/pages"
    fi
    for f in output/index.json output/theme.json output/cover.png; do
        [ -f "$f" ] && rm -f "$f" && ok "Deleted: $f"
    done
fi

if [[ "$MODE" == "viewer" || "$MODE" == "all" ]]; then
    if [ -d "viewer/public/pages" ]; then
        COUNT=$(find viewer/public/pages -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
        rm -f viewer/public/pages/*.md 2>/dev/null || true
        ok "Deleted $COUNT .md files from viewer/public/pages"
    fi
    for f in viewer/public/index.json viewer/public/theme.json viewer/public/cover.png; do
        [ -f "$f" ] && rm -f "$f" && ok "Deleted: $f"
    done
fi

echo ""
info "Done. Run the extractor:"
echo "  python extractor/extractor.py"
echo ""
