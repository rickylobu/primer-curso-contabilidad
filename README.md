# 📖 PDF to LLM Context

> Transform a scanned PDF book into structured, accessible Markdown — readable by humans, browsers, and AI models alike.

**What this does:** Takes any image-based (scanned) PDF and converts it into clean Markdown files using Gemini's multimodal AI. The output is rendered as an accessible web app on GitHub Pages with text-to-speech, searchable pages, and interactive math visualizations.

```
Scanned PDF  →  Gemini OCR  →  Markdown pages  →  GitHub Pages viewer
                                      ↓
                              Consumable by any LLM
```

---

## ✨ Features

- **Accurate OCR** for scanned books using Google Gemini 1.5 Flash
- **Accounting-aware**: T-accounts and tables reconstructed as proper Markdown tables
- **Math support**: Formula links to GeoGebra interactive graphs; optional Wolfram Alpha validation
- **Text-to-speech**: Full Web Speech API integration with voice, speed, and pitch controls
- **Dynamic theming**: Colors automatically extracted from the book cover
- **Resume-safe**: If extraction is interrupted, it picks up exactly where it left off
- **Quota-aware**: Pre-flight check warns you before you hit the free tier limit
- **Copyright-friendly**: Source citations embedded in every page; PDF never committed to git
- **Zero hosting cost**: GitHub Pages + Gemini free tier

---

## 📋 Requirements

| Tool | Version | Install |
|---|---|---|
| Python | ≥ 3.11 | [python.org](https://python.org) |
| Node.js | ≥ 20 | [nodejs.org](https://nodejs.org) |
| Git | any | [git-scm.com](https://git-scm.com) |
| Google account | — | For Gemini API key (free) |

---

## 🚀 Quick Start

### Step 1 — Fork and clone the repository

```bash
# Fork this repo on GitHub first, then clone your fork:
git clone https://github.com/YOUR_USERNAME/pdf-to-llm-context.git

# Rename the folder to your book title (optional but recommended):
mv pdf-to-llm-context primer_curso_de_contabilidad_22va_edicion
cd primer_curso_de_contabilidad_22va_edicion
```

### Step 2 — Get your free Gemini API key

1. Go to [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Sign in with your Google account
3. Click **Create API key**
4. Copy the key — you will need it in Step 6

> The free tier includes **1,500 requests/day** and **15 requests/minute** for Gemini 1.5 Flash.
> A 300-page book takes approximately 22 minutes and costs $0.

### Step 3 — Place your PDF in the `/input/` folder

```
your-project-folder/
└── input/
    └── your_book.pdf    ← put it here
```

> The `/input/` folder is excluded from git. Your PDF will never be committed to the repository.

### Step 4 — Configure the project

Open `config.yaml` in any text editor. **This is the only file you need to edit.**

```yaml
input:
  pdf_filename: "primer_curso_de_contabilidad_22va_edicion-elias_lara_flores.pdf"
  title: "Primer Curso de Contabilidad - 22va Edición"
  author: "Elias Lara Flores"
  year: 2008
  isbn: "978-968-24-8207-6"
  original_url: "https://ceves.edu.mx/v2/books/primer-curso-de-contabilidad/"
```

The rest of the defaults work out of the box. See [Configuration Reference](#%EF%B8%8F-configuration-reference) for all options.

### Step 5 — Set up Python environment

```bash
# From the /extractor/ folder:
cd extractor

# Create a virtual environment
python -m venv .venv

# Activate it:
# Git Bash / macOS / Linux:
source .venv/Scripts/activate
# PowerShell (Windows):
# .\.venv\Scripts\Activate.ps1

# Upgrade pip first — important on Windows to get pre-built wheels
python -m pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

> **Windows long path issue:** If pip fails with `OSError: No such file or directory`,
> enable Windows Long Paths or create the venv in a short path:
> ```bash
> python -m venv C:\venvs\pdfenv
> C:\venvs\pdfenv\Scripts\activate
> pip install -r requirements.txt
> ```

### Step 6 — Add your API key

```bash
# In the project root:
cp .env.example .env
```

Open `.env` and replace the placeholder:

```env
GEMINI_API_KEY=AIza...your_actual_key_here
```

> Never commit `.env` to git. It is already in `.gitignore`.

### Step 7 — Run the extractor

Run from the **project root** (recommended — avoids path issues on all platforms):

```bash
# From project root, with your venv active:
python extractor/extractor.py
```

You will see a **pre-flight quota analysis** before processing starts:

```
============================================================
  📊  QUOTA ANALYSIS — Pre-flight Check
============================================================
  Book pages       : 425
  Pages to process : 425
  AI model         : Gemini 1.5 Flash
  Est. time        : ~39.0 minutes
  Est. tokens      : ~340,000

  Free tier usage  : [███████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░] 425/1500 req/day

  ✅  Fits within the free tier. Good to go!
```

Then extraction begins with a live progress bar:

```
  [███████████████░░░░░░░░░░░░░░░░░░░░░░░░]  44.1%  Page 151/425 ✅ done
```

**If interrupted**, just run the command again — already-processed pages are skipped automatically.

### Step 8 — Preview the viewer locally

```bash
cd viewer
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🌐 Deploy to GitHub Pages

### One-time GitHub setup

1. **Make sure you have at least one commit before pushing:**
   ```bash
   git add .
   git commit -m "init: project setup"
   git push -u origin main
   ```
   > If you get `error: src refspec main does not match any`, you have no local commits yet. Run the above.

2. Go to your repository → **Settings → Pages → Source**: select **GitHub Actions**

3. **Settings → Secrets and variables → Actions → New repository secret**:
   - Name: `VITE_BASE_PATH`
   - Value: `/your-repository-name/` *(with leading and trailing slash)*

### Deploy

```bash
git add output/ viewer/
git commit -m "feat: add extracted book pages"
git push origin main
```

GitHub Actions will build and deploy automatically. Live URL:

```
https://YOUR_USERNAME.github.io/your-repository-name/
```

---

## ⚙️ Configuration Reference

```yaml
input:
  pdf_filename: "my_book.pdf"     # Filename inside /input/
  title: "Book Title"
  author: "Author Name"
  year: 2024
  isbn: ""                        # Optional
  original_url: ""                # Optional — URL for attribution

ai:
  ocr_model: "gemini-1.5-flash"   # "gemini-1.5-flash" (free) or "gemini-1.5-pro"
  enable_claude_enrichment: false # Second pass with Claude (requires ANTHROPIC_API_KEY)
  claude_model: "claude-sonnet-4-20250514"
  enable_wolfram_math: false      # Math validation (requires WOLFRAM_APP_ID)

processing:
  dpi: 300                        # 200=fast, 300=balanced, 400=quality
  page_range: null                # null=all, or [start, end] e.g. [1, 50]
  rate_limit_delay: 4.5           # Seconds between API calls (min 4.0 for free tier)
  max_retries: 3                  # Retries per page before marking failed
  skip_existing: true             # Skip already-processed pages (resume support)

output:
  pages_dir: "output/pages"
  sync_to_viewer: true            # Copy output to viewer/public/ after extraction
  viewer_public_dir: "viewer/public/pages"

theme:
  primary_color: ""               # Leave empty to auto-detect from cover
  secondary_color: ""
  accent_color: ""
  background_color: ""
  text_color: ""
```

---

## 🔑 Optional API Keys

### Claude enrichment pass (Anthropic)

1. Get your key at [console.anthropic.com](https://console.anthropic.com)
2. Add to `.env`: `ANTHROPIC_API_KEY=sk-ant-...`
3. Enable in `config.yaml`: `enable_claude_enrichment: true`
4. Uncomment `# anthropic>=0.34.0` in `requirements.txt` and reinstall

> Note: Claude API is paid. A 300-page book costs approximately $0.50–$2.00.

### Wolfram Alpha math validation

1. Get a free App ID at [products.wolframalpha.com/api](https://products.wolframalpha.com/api) *(2,000 free/month)*
2. Add to `.env`: `WOLFRAM_APP_ID=XXXX-XXXX`
3. Enable in `config.yaml`: `enable_wolfram_math: true`

---

## 📁 Project Structure

```
your-project/
├── config.yaml                   ← ⭐ Edit this file only
├── .env.example                  ← Copy to .env and add your keys
├── .gitignore
│
├── input/                        ← Place your PDF here (never committed)
│
├── output/                       ← Auto-generated by extractor
│   ├── pages/
│   │   ├── page_0001.md
│   │   └── ...
│   ├── index.json
│   ├── theme.json
│   └── cover.png
│
├── extractor/                    ← Python pipeline
│   ├── extractor.py              ← Main script
│   ├── quota_analyzer.py
│   ├── state_manager.py
│   ├── cover_analyzer.py
│   ├── math_enricher.py
│   └── requirements.txt
│
├── viewer/                       ← React web app
│   ├── src/
│   │   ├── App.jsx
│   │   ├── components/
│   │   │   ├── Sidebar.jsx
│   │   │   ├── Reader.jsx
│   │   │   └── TTSControls.jsx
│   │   └── hooks/
│   │       └── useTTS.js
│   ├── package.json
│   └── vite.config.js
│
└── .github/
    └── workflows/
        └── deploy.yml
```

---

## 🔧 Troubleshooting

**`ModuleNotFoundError: No module named 'yaml'` / `'fitz'` / `'dotenv'` / `'google'`**
→ Virtual environment is not active, or install was incomplete.
```bash
source .venv/Scripts/activate   # Git Bash
pip install -r requirements.txt
# If a specific package keeps failing, install manually:
pip install pyyaml pymupdf python-dotenv google-genai Pillow
```

**`PyMuPDF` fails to compile on Windows**
→ Upgrade pip first to get the pre-built wheel:
```bash
python -m pip install --upgrade pip
pip install pymupdf
```
If it still requires Visual Studio Build Tools, switch to Python 3.11 or 3.12.

**`OSError: No such file or directory` when installing packages**
→ Windows path length limit. Move the project to a shorter path (e.g. `C:\projects\pdf-to-llm-context`), or create the venv outside the project:
```bash
python -m venv C:\venvs\pdfenv
C:\venvs\pdfenv\Scripts\activate
```

**`FileNotFoundError: config.yaml`**
→ Run from the project root, not from inside `/extractor/`:
```bash
# Correct (from project root):
python extractor/extractor.py
```

**`error: src refspec main does not match any`**
→ You need a commit before pushing:
```bash
git add .
git commit -m "init"
git push -u origin main
```

**Rate limit (429 / RESOURCE_EXHAUSTED) on every page from the start**
→ Your `GEMINI_API_KEY` in `.env` may be invalid or expired. Verify it at [aistudio.google.com](https://aistudio.google.com/app/apikey). If the key is valid, increase `processing.rate_limit_delay` to `6.0` in `config.yaml`.

**`FutureWarning: All support for google.generativeai has ended`**
→ Make sure you have the latest code and reinstall:
```bash
pip install google-genai --upgrade
```
The old `google-generativeai` package is no longer used in this project.

**Cover extracted but theme colors show `n/a`**
→ Pillow is not installed:
```bash
pip install Pillow
```

**GitHub Pages shows a blank page**
→ Verify `VITE_BASE_PATH` secret is set to `/your-repo-name/` (with both slashes) in **Settings → Secrets → Actions**.

**Some pages marked as failed**
→ Run the extractor again — failed pages are retried automatically. No page is ever double-processed.

---

## ❓ FAQ

**Does the PDF get uploaded to the repository?**
No. `/input/` is in `.gitignore`. The PDF is never committed.

**Can I pause and resume extraction?**
Yes. Run the extractor again and it continues from where it left off.

**How much does it cost?**
With Gemini 1.5 Flash on the free tier: **$0**. The pre-flight check shows your estimated usage before processing starts.

**Can I process only a range of pages?**
Yes. Set `processing.page_range: [1, 50]` in `config.yaml`.

---

## 🛡️ Security

| What | Status |
|---|---|
| Your PDF | ✅ Never committed — `.gitignore` |
| API keys | ✅ Never committed — `.env` in `.gitignore` |
| Extracted Markdown | Committed by you — this is the shareable output |

---

## 📄 License

MIT — free to use, modify, and distribute. See [LICENSE](LICENSE).

---

## 🙏 Acknowledgments

- [Google Gemini](https://ai.google.dev/) — multimodal OCR
- [PyMuPDF](https://pymupdf.readthedocs.io/) — PDF rendering
- [React](https://react.dev/) + [Vite](https://vitejs.dev/) — viewer
- [react-markdown](https://github.com/remarkjs/react-markdown) — Markdown rendering
- [GeoGebra](https://www.geogebra.org/) — interactive math visualization
- [Wolfram Alpha](https://www.wolframalpha.com/) — math validation (optional)

---

## 🗂️ Repository Architecture

```
pdf-to-llm-context          ← Template repo — development lives here
├── main                       Protected, production-ready at all times
├── feat/xxx                   Feature branches — your development workflow
└── fix/xxx                    Fix branches
         ↓ "Use this template"
primer-curso-contabilidad   ← Instance repo — your book in production
└── main                       Only branch, no development history
```

**Development rule:** never develop in an instance. All improvements go through
a feature branch in the template, get reviewed via PR, merged to main, then
the instance is updated by re-creating from "Use this template" or pulling manually.

**External contributors** fork the template and PR back to it — the instance
is never involved.
