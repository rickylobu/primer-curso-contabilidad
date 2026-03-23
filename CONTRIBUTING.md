# Contributing to pdf-to-llm-context

## Repository roles

```
pdf-to-llm-context          TEMPLATE — development and contributions live here
primer-curso-contabilidad   INSTANCE — production only, created via "Use this template"
```

**Development always happens in the template repo.**
The instance is a clean production copy with no development history.

---

## Internal development (maintainer workflow)

This is the day-to-day workflow for developing and improving the template itself.

```bash
# 1. Clone the template repo (only done once)
git clone https://github.com/rickylobu/pdf-to-llm-context.git
cd pdf-to-llm-context

# 2. Create a feature or fix branch
git checkout -b feat/your-feature-name
# or
git checkout -b fix/your-fix-name

# 3. Develop and test
#    - Run: python test_api.py
#    - Run: python extractor/extractor.py
#    - Verify the viewer: cd viewer && npm run dev

# 4. Before merging to main — clean all extraction artifacts
powershell -ExecutionPolicy Bypass -File .\cer.ps1 full
# or on macOS/Linux:
bash cer.sh full

# 5. Commit and push your branch
git add extractor/ viewer/ README.md  # infrastructure only, never output/ or input/
git commit -m "feat: describe your change"
git push origin feat/your-feature-name

# 6. Open a Pull Request on GitHub:
#    feat/your-feature-name -> main
#    PR requires a title and description.

# 7. After PR is merged, update your local main
git checkout main
git pull origin main
```

**main is always production-ready.** Never commit directly to main.

---

## Creating a book instance

Once main is stable, create a new instance for any book:

1. Go to `github.com/rickylobu/pdf-to-llm-context`
2. Click **"Use this template"** → **"Create a new repository"**
3. Name it after your book: `primer-curso-contabilidad`
4. Clone it locally and configure:

```bash
git clone https://github.com/rickylobu/primer-curso-contabilidad.git
cd primer-curso-contabilidad

# Configure your book (the only files you edit)
cp .env.example .env               # add your GEMINI_API_KEY
# Edit config.yaml with your book metadata

# Place your PDF
# Copy your file to /input/your_book.pdf

# Install Python dependencies
cd extractor
python -m venv .venv
source .venv/Scripts/activate      # Git Bash on Windows
# .\.venv\Scripts\Activate.ps1     # PowerShell
python -m pip install --upgrade pip
pip install -r requirements.txt
cd ..

# Verify API connection
python test_api.py

# Run extraction
python extractor/extractor.py
```

The instance has **only a main branch**. It is not connected to the template repo.
If you need to update the instance with improvements from the template,
re-create it from "Use this template" after the template's main is updated.

---

## External contributions (third-party contributors)

If you are not the maintainer and want to contribute an improvement:

```bash
# 1. Fork pdf-to-llm-context on GitHub (Fork button, top right)
# 2. Clone your fork
git clone https://github.com/your-username/pdf-to-llm-context.git
cd pdf-to-llm-context
git remote add upstream https://github.com/rickylobu/pdf-to-llm-context.git

# 3. Create a feature branch
git checkout -b feat/your-improvement

# 4. Make changes to infrastructure files only:
#    extractor/*.py, viewer/src/*, README.md, cer.ps1, cer.sh

# 5. Clean before committing
bash cer.sh full

# 6. Commit and push to your fork
git add extractor/ viewer/ README.md
git commit -m "feat: describe your improvement"
git push origin feat/your-improvement

# 7. Open PR: your-fork:feat/your-improvement -> rickylobu/pdf-to-llm-context:main
```

---

## What to clean before any commit or PR

```powershell
# Windows — reset state only (keep .md files for review if needed):
powershell -ExecutionPolicy Bypass -File .\cer.ps1

# Windows — full clean (recommended before merging to main):
powershell -ExecutionPolicy Bypass -File .\cer.ps1 full

# macOS/Linux:
bash cer.sh full
```

**Never commit to any branch:**
- `output/pages/*.md` (generated content — belongs in instance, not template)
- `input/*.pdf` (copyrighted material)
- `.env` (API keys)
- `output/.extraction_state.json` (local state)

---

## File ownership by repo

| File | Template (dev) | Instance (production) |
|---|---|---|
| `extractor/*.py` | ✅ develop here | ✅ inherited |
| `viewer/src/` | ✅ develop here | ✅ inherited |
| `config.yaml` | ✅ defaults only | ✅ your book data |
| `output/pages/*.md` | ❌ clean before PR | ✅ your extracted book |
| `input/*.pdf` | ❌ never | local only |
| `.env` | local only | local only |
