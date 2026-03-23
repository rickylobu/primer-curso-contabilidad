"""
extractor.py
Main pipeline: PDF → images → Gemini OCR → enriched Markdown → index.json

Run from the PROJECT ROOT (recommended):
    python extractor/extractor.py

Or from inside /extractor/:
    cd extractor && python extractor.py
"""

import os
import sys
import json
import time
import shutil
import yaml
import fitz  # PyMuPDF
from pathlib import Path
from dotenv import load_dotenv
from google.genai import types as genai_types

# Local modules — works whether run from root or from /extractor/
sys.path.insert(0, str(Path(__file__).parent))
from gemini_client import GeminiClientManager   # ← singleton, single source of truth
from quota_analyzer import run_preflight
from state_manager import StateManager
from cover_analyzer import run_cover_analysis
from math_enricher import enrich_markdown_with_math

load_dotenv()

# ──────────────────────────────────────────────
# Gemini OCR prompt  (language-aware, structured)
# ──────────────────────────────────────────────
OCR_PROMPT = """
You are an expert document digitizer specializing in accounting and financial texts written in Spanish.

Analyze this book page image and extract ALL content with the following rules:

1. TEXT: Transcribe all text verbatim, preserving paragraph breaks.

2. HEADINGS: Use Markdown heading levels (# ## ###) that match the visual hierarchy.

3. STANDARD TABLES: Render as GitHub-Flavored Markdown tables with | delimiters.

4. T-ACCOUNTS (Cuentas T / Esquemas de Mayor): Render as a Markdown table with three columns:
   | **Debe** | **Cuenta: [Name]** | **Haber** |
   |---|---|---|
   | [left entries] | | [right entries] |

5. FORMULAS & EQUATIONS: Wrap inline math in backticks. E.g. `Activo = Pasivo + Capital`.

6. NUMBERED LISTS & BULLETS: Preserve using Markdown list syntax.

7. FOOTNOTES: Append at the bottom prefixed with > **Nota:**.

8. IF THE PAGE IS BLANK or ONLY contains a page number: respond with exactly: [BLANK_PAGE]

9. DO NOT add any commentary, preamble, or explanation outside the extracted content.

Output: pure Markdown only.
"""

CLAUDE_ENRICHMENT_PROMPT = """
You receive raw Markdown extracted from a scanned accounting textbook page.
Your job is to improve structure and clarity WITHOUT changing the content:
- Fix obvious OCR errors in Spanish words.
- Ensure heading hierarchy is consistent.
- Fix broken table rows.
- Do not add or remove factual content.
- Return only the improved Markdown.
"""


# ──────────────────────────────────────────────
# Configuration loader
# ──────────────────────────────────────────────

def find_project_root() -> Path:
    """
    Locate the project root by searching upward for config.yaml.
    Works whether the script is run from root or from /extractor/.
    """
    candidate = Path(__file__).parent          # /extractor/
    for _ in range(3):
        if (candidate / "config.yaml").exists():
            return candidate
        candidate = candidate.parent
    raise FileNotFoundError(
        "config.yaml not found. Run from the project root or from /extractor/."
    )


def load_config(config_path: str = None) -> dict:
    if config_path is None:
        config_path = find_project_root() / "config.yaml"
    with open(config_path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ──────────────────────────────────────────────
# PDF → image (per page)
# ──────────────────────────────────────────────

def pdf_page_to_image_bytes(doc: fitz.Document, page_index: int, dpi: int) -> bytes:
    page = doc[page_index]
    mat = fitz.Matrix(dpi / 72, dpi / 72)
    pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
    return pix.tobytes("png")


# ──────────────────────────────────────────────
# Gemini OCR call (with retry)
# ──────────────────────────────────────────────

def gemini_ocr(
    client,   # genai.Client — managed by GeminiClientManager singleton
    model_name: str,
    image_bytes: bytes,
    max_retries: int = 3,
    delay: float = 4.5,
    override_prompt: str = None,   # replaces OCR_PROMPT when set (blank-aware pass 2)
) -> tuple:
    """
    Sends a page image to Gemini for OCR using the new google.genai SDK.
    Returns (markdown_text, token_count).
    Raises RuntimeError if all retries are exhausted.
    """
    prompt = override_prompt if override_prompt else OCR_PROMPT
    contents = [
        genai_types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
        genai_types.Part.from_text(text=prompt),
    ]

    last_error: Exception = None

    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=contents,
                config=genai_types.GenerateContentConfig(
                    temperature=0.1,
                    safety_settings=[
                        genai_types.SafetySetting(
                            category="HARM_CATEGORY_HATE_SPEECH",
                            threshold="BLOCK_NONE",
                        ),
                        genai_types.SafetySetting(
                            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            threshold="BLOCK_NONE",
                        ),
                        genai_types.SafetySetting(
                            category="HARM_CATEGORY_DANGEROUS_CONTENT",
                            threshold="BLOCK_NONE",
                        ),
                        genai_types.SafetySetting(
                            category="HARM_CATEGORY_HARASSMENT",
                            threshold="BLOCK_NONE",
                        ),
                    ],
                ),
            )
            text = response.text or ""
            token_count = (
                response.usage_metadata.total_token_count
                if response.usage_metadata
                else 0
            )
            return text, token_count

        except Exception as e:
            last_error = e
            err = str(e)
            is_rate_limit = any(
                kw in err for kw in ("429", "RESOURCE_EXHAUSTED", "quota", "rate limit")
            )
            is_retryable = is_rate_limit or "500" in err or "503" in err or "timeout" in err.lower()

            if is_rate_limit:
                wait = delay * (2 ** (attempt - 1))
                print(f"\n  ⏳  Rate limit (429). Waiting {wait:.0f}s (attempt {attempt}/{max_retries})...")
                time.sleep(wait)
            elif is_retryable and attempt < max_retries:
                print(f"\n  ⚠️   Retryable error (attempt {attempt}/{max_retries}): {err[:120]}")
                time.sleep(delay)
            else:
                raise RuntimeError(
                    f"{type(e).__name__}: {err}"
                )

    raise RuntimeError(f"Exhausted all retries. Last error — {type(last_error).__name__}: {last_error}")


# ──────────────────────────────────────────────
# Optional: Claude enrichment pass
# ──────────────────────────────────────────────

def claude_enrich(markdown_text: str, model_name: str) -> str:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        msg = client.messages.create(
            model=model_name,
            max_tokens=4096,
            messages=[
                {"role": "user", "content": f"{CLAUDE_ENRICHMENT_PROMPT}\n\n---\n\n{markdown_text}"}
            ],
        )
        return msg.content[0].text
    except Exception as e:
        print(f"\n  ⚠️  Claude enrichment failed: {e}. Using raw Gemini output.")
        return markdown_text


# ──────────────────────────────────────────────
# Markdown page wrapper (adds frontmatter)
# ──────────────────────────────────────────────

def wrap_page_markdown(
    content: str,
    page_number: int,
    config: dict,
) -> str:
    book = config["input"]
    citation_lines = []
    citation_lines.append(f"**Source:** {book.get('title', 'Unknown Title')}")
    if book.get("author"):
        citation_lines.append(f"**Author:** {book['author']}")
    if book.get("year"):
        citation_lines.append(f"**Year:** {book['year']}")
    if book.get("isbn"):
        citation_lines.append(f"**ISBN:** {book['isbn']}")
    if book.get("original_url"):
        citation_lines.append(f"**Original source:** [{book['original_url']}]({book['original_url']})")

    citation_block = (
        "\n\n---\n\n> " + "  \n> ".join(citation_lines)
        if citation_lines else ""
    )

    return f"""---
page: {page_number}
source: "{book.get('title', '')}"
author: "{book.get('author', '')}"
---

{content}
{citation_block}
"""


# ──────────────────────────────────────────────
# Progress bar
# ──────────────────────────────────────────────

def print_progress(current: int, total: int, page_num: int, status: str = "") -> None:
    pct = current / total if total else 0
    bar_len = 35
    filled = int(bar_len * pct)
    bar = "█" * filled + "░" * (bar_len - filled)
    pct_str = f"{pct * 100:5.1f}%"
    suffix = f" {status}" if status else ""
    print(f"\r  [{bar}] {pct_str}  Page {page_num}/{total}{suffix}   ", end="", flush=True)


# ──────────────────────────────────────────────
# Index builder
# ──────────────────────────────────────────────

def build_index(pages_dir: Path, config: dict, theme: dict) -> dict:
    """Scans generated .md files and builds index.json for the viewer."""
    entries = []
    for md_file in sorted(pages_dir.glob("page_*.md")):
        page_num = int(md_file.stem.replace("page_", ""))
        text_preview = md_file.read_text(encoding="utf-8")[:200].replace("\n", " ").strip()
        entries.append({
            "page": page_num,
            "file": f"pages/{md_file.name}",
            "preview": text_preview,
        })

    index = {
        "title": config["input"].get("title", "Untitled"),
        "author": config["input"].get("author", ""),
        "year": config["input"].get("year", ""),
        "isbn": config["input"].get("isbn", ""),
        "original_url": config["input"].get("original_url", ""),
        "total_pages": len(entries),
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "theme": theme,
        "pages": entries,
    }
    return index


# ──────────────────────────────────────────────
# Main pipeline
# ──────────────────────────────────────────────

def main():
    print("\n" + "=" * 60)
    print("  📖  PDF → LLM Context Extractor")
    print("=" * 60)

    # 1. Locate project root and load config
    project_root = find_project_root()
    os.chdir(project_root)   # normalize cwd so all relative paths work
    config = load_config()
    pdf_filename = config["input"]["pdf_filename"]
    pdf_path = project_root / "input" / pdf_filename
    output_dir = project_root / config["output"]["pages_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)

    # 2. Pre-flight quota check
    proceed, quota_report = run_preflight(str(project_root / "config.yaml"))
    if not proceed:
        sys.exit(0)

    # 3. Cover analysis & theme extraction
    root_output = project_root / "output"
    theme = run_cover_analysis(pdf_path, root_output, config.get("theme", {}))

    # 4. Initialize Gemini via singleton (single source of truth)
    model_name = config["ai"]["ocr_model"]   # e.g. "gemini-2.5-flash"

    print(f"\n  🔌  Connecting to Gemini ({model_name})...")
    health = GeminiClientManager.health_check(model_name)
    if not health["ok"]:
        print(f"\n  ❌  Gemini health check failed:\n      {health['error']}\n")
        sys.exit(1)
    print(f"  ✅  Model confirmed: {model_name} via {health['api_version']}\n")

    gemini_client = GeminiClientManager.get(model_name)

    # 5. Open PDF
    doc = fitz.open(str(pdf_path))
    total_pages = len(doc)
    dpi = config["processing"]["dpi"]
    delay = config["processing"]["rate_limit_delay"]
    max_retries = config["processing"]["max_retries"]
    skip_existing = config["processing"]["skip_existing"]

    # 6. Determine page range
    page_range = config["processing"].get("page_range")
    if page_range:
        start_page, end_page = max(1, page_range[0]), min(total_pages, page_range[1])
    else:
        start_page, end_page = 1, total_pages
    pages_to_process = list(range(start_page, end_page + 1))

    # 7. State manager (resume + idempotency)
    state = StateManager(pdf_filename=pdf_filename, total_pages=total_pages)

    # 8. Process pages
    print(f"\n  🔄  Pass 1/2 — Processing pages {start_page}–{end_page} of {total_pages}...\n")
    processed = 0

    enable_claude  = config["ai"].get("enable_claude_enrichment", False)
    claude_model   = config["ai"].get("claude_model", "claude-sonnet-4-20250514")
    enable_wolfram = config["ai"].get("enable_wolfram_math", False)

    # ── Pass 1: full extraction ─────────────────────────────────────────────
    for i, page_num in enumerate(pages_to_process):
        output_file = output_dir / f"page_{page_num:04d}.md"

        # Skip terminal pages (done / confirmed_blank / skipped)
        if skip_existing and state.is_terminal(page_num):
            print_progress(i + 1, len(pages_to_process), page_num, "⏭ skipped")
            continue

        # Skip suspect_blank — handled in Pass 2
        entry_status = state._state.pages.get(str(page_num), {}).get("status", "pending")
        if entry_status == "suspect_blank":
            print_progress(i + 1, len(pages_to_process), page_num, "🔍 queued→pass2")
            continue

        # Max retries guard
        if state.get_attempts(page_num) >= max_retries:
            print_progress(i + 1, len(pages_to_process), page_num, "❌ max retries")
            continue

        attempt_id = state.mark_in_progress(page_num)
        print_progress(i + 1, len(pages_to_process), page_num, "🔍 extracting")

        try:
            img_bytes = pdf_page_to_image_bytes(doc, page_num - 1, dpi)
            raw_md, tokens = gemini_ocr(
                gemini_client, model_name, img_bytes,
                max_retries=max_retries, delay=delay,
            )

            is_explicit_blank = raw_md.strip() == "[BLANK_PAGE]"
            is_empty          = len(raw_md.strip()) < 20

            if is_explicit_blank or is_empty:
                # Write placeholder and queue for second pass — do NOT mark DONE yet
                placeholder = wrap_page_markdown(
                    f"*[Page {page_num} — pending blank verification (pass 2)]*",
                    page_num, config,
                )
                output_file.write_text(placeholder, encoding="utf-8")
                state.mark_suspect_blank(page_num, str(output_file), tokens)
                print_progress(i + 1, len(pages_to_process), page_num, "❓ suspect-blank")
                time.sleep(delay)
                continue

            # Enrichment passes
            if enable_claude:
                raw_md = claude_enrich(raw_md, claude_model)
            if enable_wolfram:
                raw_md = enrich_markdown_with_math(raw_md, enable_wolfram=True)

            final_md = wrap_page_markdown(raw_md, page_num, config)
            output_file.write_text(final_md, encoding="utf-8")
            state.mark_done(page_num, str(output_file), tokens)
            processed += 1
            print_progress(i + 1, len(pages_to_process), page_num, "✅ done")

        except Exception as e:
            state.mark_failed(page_num, str(e))
            print_progress(i + 1, len(pages_to_process), page_num, "⚠️  error")

        time.sleep(delay)

    doc.close()

    # ── Pass 2: blank verification ──────────────────────────────────────────
    suspect_queue = state.get_suspect_blank_queue()
    if suspect_queue:
        hi_res_dpi   = min(dpi + 150, 450)
        wait_between = max(delay, 5.0)   # slightly more generous between blank retries

        print(f"\n\n  🔎  Pass 2/2 — Blank verification for {len(suspect_queue)} page(s)...")
        print(f"      DPI: {hi_res_dpi}  |  Prompt: blank-aware aggressive  |  Delay: {wait_between}s\n")

        # Re-open PDF for hi-res rendering
        doc2 = fitz.open(str(pdf_path))

        for i, page_num in enumerate(suspect_queue):
            output_file = output_dir / f"page_{page_num:04d}.md"
            attempt_id  = state.mark_blank_retry_in_progress(page_num)
            print_progress(i + 1, len(suspect_queue), page_num, "🔬 hi-res scan")

            try:
                img_bytes_hires = pdf_page_to_image_bytes(doc2, page_num - 1, hi_res_dpi)

                # Aggressive blank-aware prompt with unique attempt marker
                blank_prompt = (
                    f"[attempt:{attempt_id[:8]}] "
                    "This page may have been misread as empty. "
                    "Look VERY carefully — even faint, watermarked, or light-gray text counts. "
                    "If you find ANY text, transcribe it completely in Markdown. "
                    "Only respond with exactly [BLANK_PAGE] if the page is truly, "
                    "completely empty or contains only decorative elements with zero text."
                )

                raw_md, tokens = gemini_ocr(
                    gemini_client, model_name, img_bytes_hires,
                    max_retries=2, delay=wait_between,
                    override_prompt=blank_prompt,
                )

                is_still_blank = (
                    raw_md.strip() == "[BLANK_PAGE]" or len(raw_md.strip()) < 20
                )

                if is_still_blank:
                    confirmed = wrap_page_markdown(
                        f"*[Page {page_num} — confirmed blank after hi-res verification]*",
                        page_num, config,
                    )
                    output_file.write_text(confirmed, encoding="utf-8")
                    state.mark_confirmed_blank(page_num, str(output_file))
                    print_progress(i + 1, len(suspect_queue), page_num, "⬜ confirmed blank")
                else:
                    if enable_claude:
                        raw_md = claude_enrich(raw_md, claude_model)
                    if enable_wolfram:
                        raw_md = enrich_markdown_with_math(raw_md, enable_wolfram=True)
                    final_md = wrap_page_markdown(raw_md, page_num, config)
                    output_file.write_text(final_md, encoding="utf-8")
                    state.mark_done(page_num, str(output_file), tokens)
                    processed += 1
                    print_progress(i + 1, len(suspect_queue), page_num, "✅ recovered!")

            except Exception as e:
                state.mark_failed(page_num, str(e))
                print_progress(i + 1, len(suspect_queue), page_num, "⚠️  error")

            time.sleep(wait_between)

        doc2.close()
    else:
        print("\n\n  ✅  No suspect-blank pages — skipping pass 2.")

    # ── Build index ─────────────────────────────────────────────────────────
    print(f"\n\n  📋  Building index.json...")
    index = build_index(output_dir, config, theme)
    index_path = output_dir.parent / "index.json"
    index_path.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  ✅  index.json → {index_path}")

    # ── Sync to viewer ──────────────────────────────────────────────────────
    if config["output"].get("sync_to_viewer"):
        viewer_dir = Path(config["output"]["viewer_public_dir"])
        viewer_dir.mkdir(parents=True, exist_ok=True)
        for md_file in output_dir.glob("*.md"):
            shutil.copy(md_file, viewer_dir / md_file.name)
        shutil.copy(index_path, viewer_dir.parent / "index.json")
        for extra in ["theme.json", "cover.png"]:
            src = output_dir.parent / extra
            if src.exists():
                shutil.copy(src, viewer_dir.parent / extra)
        print(f"  🚀  Output synced → {viewer_dir.parent}")

    # ── Final summary ───────────────────────────────────────────────────────
    summary = state.summary()
    failed_queue = state.get_failed_queue()
    print("\n" + "=" * 60)
    print("  📊  EXTRACTION COMPLETE")
    print("=" * 60)
    print(f"  ✅  Done             : {summary['done']}")
    print(f"  ⬜  Confirmed blank  : {summary['confirmed_blank']}")
    print(f"  ⏭️   Skipped          : {summary['skipped']}")
    print(f"  ❌  Failed           : {summary['failed']}")
    print(f"  🔢  Tokens used      : ~{summary['total_tokens_used']:,}")
    if failed_queue:
        print(f"\n  Failed pages: {failed_queue}")
        print("  Run the extractor again — failed pages retry automatically.")
    print()


if __name__ == "__main__":
    main()
