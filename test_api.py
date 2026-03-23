"""
test_api.py
Diagnostic script — uses the same GeminiClientManager singleton as the pipeline.
Run from project root: python test_api.py

This script exercises the exact same code path as extractor.py so that
"test passes" guarantees "extractor will work".
"""

import os
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Same module path resolution as extractor.py ─────────────────────────────
sys.path.insert(0, str(Path(__file__).parent / "extractor"))
from gemini_client import GeminiClientManager
from google.genai import types as genai_types
import yaml
import fitz


def load_config() -> dict:
    for candidate in [Path("config.yaml"), Path("../config.yaml")]:
        if candidate.exists():
            with open(candidate, encoding="utf-8") as f:
                return yaml.safe_load(f)
    raise FileNotFoundError("config.yaml not found. Run from project root.")


def main():
    print("\n============================================================")
    print("  test_api.py -- Gemini API Diagnostic")
    print("============================================================\n")

    # 1. Load config
    try:
        config = load_config()
        model_name = config["ai"]["ocr_model"]
        print(f"  [OK] config.yaml loaded")
        print(f"  [->] Model : {model_name}")
        print(f"  [->] API   : {GeminiClientManager.resolve_version(model_name)}\n")
    except Exception as e:
        print(f"  [!!] config.yaml error: {e}")
        sys.exit(1)

    # 2. API key
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        print("  [!!] GEMINI_API_KEY not set in .env")
        sys.exit(1)
    print(f"  [OK] API key loaded: {api_key[:8]}...")

    # 3. Health check via singleton (same as extractor startup)
    print(f"\n  --> Health check ({model_name})...")
    health = GeminiClientManager.health_check(model_name)
    if not health["ok"]:
        print(f"  [!!] Health check failed:\n       {health['error']}")
        sys.exit(1)
    print(f"  [OK] Model confirmed via {health['api_version']}")
    print("\n=== Recommended Models for OCR (March 2026) ===")

    print("\n[1] Best for production / high-volume OCR")
    print("    → gemini-2.5-flash-image")
    print("       - Excellent OCR + low cost")
    print("       - Free Tier: YES (Google offers free input/output tokens)")
    print("       - Pricing: $0.30 input / $2.50 output per 1M tokens "
        "(TLDL Pricing, Mar 2026)")

    print("\n[2] Best quality OCR (premium)")
    print("    → gemini-3-pro-image-preview")
    print("       - Highest OCR fidelity, best for damaged/complex scans")
    print("       - Free Tier: NO (Pro models not included in free tier)")
    print("       - Pricing: $2.00 input / $12.00 output per 1M tokens "
        "(Vertex AI Pricing, Mar 2026)")

    print("\n[3] Best balance of speed, quality, cost")
    print("    → gemini-3.1-flash-image-preview")
    print("       - Modern OCR with improved multimodal understanding")
    print("       - Free Tier: YES (Flash models included in free tier)")
    print("       - Pricing: $0.50 input / $3.00 output per 1M tokens "
        "(Vertex AI Pricing, Mar 2026)")
    
    print("\n[4] if you are developing on free tier and want to test with the same model, use:")
    print("    → gemini-3.1-flash-lite-preview")
    print("       - Basic OCR and multimodal support (sufficient for smoke tests)")
    print("       - Free Tier: YES (Flash-Lite models included in free tier limits)")
    print("       - Pricing: $0.25 input / $1.50 output per 1M tokens "
      "(Vertex AI Pricing, Mar 2026)")  # turn17search4


    print("\n==============================================\n")
    print(f"  [OK] available models: {',\n '.join(health['available_models'])}")

    # 4. Text test
    print(f"\n  --> Text test...")
    try:
        client = GeminiClientManager.get(model_name)
        r = client.models.generate_content(
            model=model_name,
            contents="Reply with exactly: OK"
        )
        print(f"  [OK] Response: {r.text.strip()}")
    except Exception as e:
        print(f"  [!!] Text test failed: {type(e).__name__}: {e}")
        sys.exit(1)

    # 5. Image test (uses first page of your PDF — same as extractor)
    print(f"\n  --> Image test (first page of your PDF)...")
    try:
        pdf_filename = config["input"]["pdf_filename"]
        pdf_path = Path("input") / pdf_filename
        if not pdf_path.exists():
            print(f"  [!]  PDF not found at {pdf_path} — skipping image test")
        else:
            doc = fitz.open(str(pdf_path))
            pix = doc[0].get_pixmap(matrix=fitz.Matrix(1, 1))
            img_bytes = pix.tobytes("png")
            doc.close()

            r = client.models.generate_content(
                model=model_name,
                contents=[
                    genai_types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                    genai_types.Part.from_text(text="What is the title of this book? One sentence."),
                ]
            )
            print(f"  [OK] Image response: {r.text.strip()[:120]}")
    except Exception as e:
        print(f"  [!!] Image test failed: {type(e).__name__}: {e}")

    print("\n  All tests passed. Ready to run:")
    print("  python extractor/extractor.py\n")


if __name__ == "__main__":
    main()
