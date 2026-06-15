# medquiz
A quiz game for medicine.

## Live site (GitHub Pages)

Once enabled (see below), the quiz is available at:

```
https://davidgcs.github.io/medquiz/
```

### Enable GitHub Pages (one-time setup)
1. Go to the repository on GitHub.
2. Open **Settings → Pages**.
3. Under *Source*, select **GitHub Actions**.
4. Save — the next push to `main` will deploy automatically.

The quiz is then accessible from any device (iPad, phone, desktop) with no login required.

---

## Rebuild the question database

Run this locally when you add or update documents:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/build_database.py
```

Then commit and push — the GitHub Action will redeploy automatically.

Question generation currently includes:
- extracted pairs from `documents/main.pdf`
- curated reviewed questions from `data/reviewed_questions.tsv`

## Run locally

```bash
python -m http.server 8000
```

Open `http://localhost:8000/web/` in your browser.

## Game behavior

- Two modes: **Random** and **In-order**.
- Questions are not repeated until all questions have appeared once in the current cycle.
- Every question has 4 answers: 1 correct + 3 wrong related distractors.
- Scores tracked: correct / incorrect / total answered.
