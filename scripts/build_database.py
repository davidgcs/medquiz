from __future__ import annotations

import json
import random
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from docx import Document
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "documents"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "medquiz.db"
QUESTIONS_JSON_PATH = DATA_DIR / "questions.json"

ARROW_SEPARATORS = ("→", "->", "=>", "⇒")
LEADING_NUMBER_RE = re.compile(r"^\s*\d+[\.)]\s*")

STOPWORDS = {
    "de",
    "del",
    "la",
    "el",
    "los",
    "las",
    "en",
    "y",
    "que",
    "con",
    "por",
    "para",
    "al",
    "se",
    "no",
    "es",
    "un",
    "una",
}


@dataclass(frozen=True)
class QAPair:
    question: str
    answer: str
    source: str


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if suffix == ".docx":
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    return ""


def split_qa_line(line: str) -> tuple[str, str] | None:
    line = normalize_space(LEADING_NUMBER_RE.sub("", line))
    if len(line) < 8:
        return None

    for sep in ARROW_SEPARATORS:
        if sep in line:
            left, right = line.split(sep, 1)
            question = normalize_space(left)
            answer = normalize_space(right)
            if len(question) >= 5 and len(answer) >= 1:
                return question, answer
    return None


def parse_qa_pairs(text: str, source: str) -> list[QAPair]:
    pairs: list[QAPair] = []
    seen: set[tuple[str, str]] = set()

    for raw in text.splitlines():
        maybe = split_qa_line(raw)
        if not maybe:
            continue
        question, answer = maybe
        key = (question.lower(), answer.lower())
        if key in seen:
            continue
        seen.add(key)
        pairs.append(QAPair(question=question, answer=answer, source=source))

    return pairs


def load_documents() -> list[tuple[Path, str]]:
    docs: list[tuple[Path, str]] = []
    for path in sorted(DOCS_DIR.iterdir()):
        if path.suffix.lower() not in {".pdf", ".docx"}:
            continue
        text = extract_text(path)
        docs.append((path, text))
    return docs


def score_related(question: str, other_question: str) -> int:
    q_tokens = {
        t
        for t in re.findall(r"[a-záéíóúñ]+", question.lower())
        if len(t) > 2 and t not in STOPWORDS
    }
    o_tokens = {
        t
        for t in re.findall(r"[a-záéíóúñ]+", other_question.lower())
        if len(t) > 2 and t not in STOPWORDS
    }
    return len(q_tokens & o_tokens)


def build_options(current: QAPair, all_pairs: list[QAPair], rng: random.Random) -> list[str]:
    candidates: list[tuple[int, str]] = []
    for pair in all_pairs:
        if pair.answer.lower() == current.answer.lower():
            continue
        similarity = score_related(current.question, pair.question)
        candidates.append((similarity, pair.answer))

    candidates.sort(key=lambda item: item[0], reverse=True)

    distractors: list[str] = []
    used = {current.answer.lower()}

    for similarity, answer in candidates:
        key = answer.lower()
        if key in used:
            continue
        if similarity == 0 and len(distractors) >= 2:
            break
        distractors.append(answer)
        used.add(key)
        if len(distractors) == 3:
            break

    if len(distractors) < 3:
        fallback_answers = [pair.answer for pair in all_pairs if pair.answer.lower() not in used]
        rng.shuffle(fallback_answers)
        for answer in fallback_answers:
            key = answer.lower()
            if key in used:
                continue
            distractors.append(answer)
            used.add(key)
            if len(distractors) == 3:
                break

    options = [current.answer, *distractors[:3]]
    rng.shuffle(options)
    return options


def create_database(documents: list[tuple[Path, str]], qa_pairs: list[QAPair]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if DB_PATH.exists():
        DB_PATH.unlink()

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                content TEXT NOT NULL,
                char_count INTEGER NOT NULL
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE qa_pairs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                question TEXT NOT NULL,
                correct_answer TEXT NOT NULL,
                source_document TEXT NOT NULL
            )
            """
        )

        cur.executemany(
            """
            INSERT INTO documents (file_name, file_path, file_type, content, char_count)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                (
                    path.name,
                    str(path.relative_to(ROOT)),
                    path.suffix.lower().lstrip("."),
                    text,
                    len(text),
                )
                for path, text in documents
            ],
        )

        cur.executemany(
            """
            INSERT INTO qa_pairs (question, correct_answer, source_document)
            VALUES (?, ?, ?)
            """,
            [(pair.question, pair.answer, pair.source) for pair in qa_pairs],
        )

        conn.commit()


def create_quiz_json(qa_pairs: list[QAPair]) -> None:
    rng = random.Random(42)

    output = []
    for idx, pair in enumerate(qa_pairs, start=1):
        options = build_options(pair, qa_pairs, rng)
        output.append(
            {
                "id": idx,
                "question": pair.question,
                "correctAnswer": pair.answer,
                "options": options,
                "source": pair.source,
            }
        )

    QUESTIONS_JSON_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def prioritize_pairs(pairs: Iterable[QAPair]) -> list[QAPair]:
    unique: dict[tuple[str, str], QAPair] = {}

    for pair in pairs:
        key = (pair.question.lower(), pair.answer.lower())
        if key not in unique:
            unique[key] = pair

    ordered = sorted(
        unique.values(),
        key=lambda p: (0 if p.source == "main.pdf" else 1, p.source.lower(), p.question.lower()),
    )
    return ordered


def main() -> None:
    documents = load_documents()
    all_pairs: list[QAPair] = []

    for path, text in documents:
        all_pairs.extend(parse_qa_pairs(text, source=path.name))

    prioritized = prioritize_pairs(all_pairs)

    if not prioritized:
        raise SystemExit("No question-answer pairs were found in documents.")

    create_database(documents, prioritized)
    create_quiz_json(prioritized)

    print(f"Loaded {len(documents)} documents")
    print(f"Stored {len(prioritized)} unique question-answer pairs")
    print(f"Database: {DB_PATH}")
    print(f"Quiz data: {QUESTIONS_JSON_PATH}")


if __name__ == "__main__":
    main()
