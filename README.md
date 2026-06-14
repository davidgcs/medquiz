# medquiz
A quiz game for medicine.

## Build the database from `documents`

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/build_database.py
```

This creates:
- `/home/runner/work/medquiz/medquiz/davidgcs/medquiz/data/medquiz.db` with all extracted document content and parsed question-answer pairs.
- `/home/runner/work/medquiz/medquiz/davidgcs/medquiz/data/questions.json` used by the web quiz.

## Run the quiz UI

```bash
python -m http.server 8000
```

Then open:
- `http://localhost:8000/web/`

## Game behavior

- Two modes: **Random** and **In-order**.
- Questions are not repeated until all questions have appeared once in the current cycle.
- Every question has 4 answers: 1 correct + 3 wrong related distractors.
- Scores tracked: correct / incorrect / total answered.
