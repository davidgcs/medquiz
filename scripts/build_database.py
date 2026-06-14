from __future__ import annotations

import json
import random
import re
import sqlite3
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from docx import Document
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "documents"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "medquiz.db"
QUESTIONS_JSON_PATH = DATA_DIR / "questions.json"
MAIN_QUESTIONS_FILE = "main.pdf"

ARROW_SEPARATORS = ("→", "->", "=>", "⇒")
QUESTION_MARKERS = {
    "que",
    "cuál",
    "cual",
    "tipo",
    "función",
    "funcion",
    "nervio",
    "músculo",
    "musculo",
    "arteria",
    "vena",
    "ligamento",
    "articulación",
    "articulacion",
    "estructura",
    "inervado",
    "inserción",
    "insercion",
    "derivado",
    "pared",
    "suelo",
    "contenido",
}

TOPIC_KEYWORDS = {
    "nervio": "nerve",
    "músculo": "muscle",
    "musculo": "muscle",
    "arteria": "artery",
    "vena": "vein",
    "ligamento": "ligament",
    "articulación": "joint",
    "articulacion": "joint",
    "hueso": "bone",
    "foramen": "foramen",
    "conducto": "canal",
    "canal": "canal",
    "hiato": "hiatus",
    "derivado": "embryology",
    "origen": "origin",
    "inserción": "insertion",
    "insercion": "insertion",
    "inervado": "innervation",
    "inervación": "innervation",
    "inervacion": "innervation",
    "espacio": "space",
    "cara": "surface",
}


def normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def normalize_key(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = re.sub(r"[^a-zA-Z0-9]+", " ", text.lower())
    return normalize_space(text)


@dataclass(frozen=True)
class QAPair:
    number: int
    question: str
    answer: str
    source: str


def extract_text(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    if suffix == ".docx":
        doc = Document(str(path))
        return "\n".join(p.text for p in doc.paragraphs)
    return ""


def split_qa_line(text: str) -> tuple[str, str] | None:
    line = normalize_space(text)
    for sep in ARROW_SEPARATORS:
        if sep not in line:
            continue
        left, right = line.split(sep, 1)
        question = normalize_space(left)
        answer = normalize_space(right)
        if len(question) >= 5 and len(answer) >= 2:
            return question, answer
    return None


def looks_like_question(text: str) -> bool:
    tokens = set(re.findall(r"[a-záéíóúñ]+", text.lower()))
    return bool(tokens & QUESTION_MARKERS)


def sanitize_answer(answer: str) -> str:
    clean = normalize_space(answer)
    clean = re.sub(r"\((?:[^)]*según[^)]*|[^)]*opcion[^)]*|[^)]*a veces[^)]*)\)", "", clean, flags=re.IGNORECASE)
    clean = normalize_space(clean).strip(".;, ")
    return clean


def parse_main_pdf_pairs(text: str, source: str) -> list[QAPair]:
    entry_pattern = re.compile(r"(?ms)^\s*(\d+)\.\s*(.+?)(?=^\s*\d+\.\s|\Z)")
    entries = [(int(m.group(1)), normalize_space(m.group(2))) for m in entry_pattern.finditer(text)]
    if not entries:
        return []

    runs: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []

    for number, block in entries:
        if not current or number == current[-1][0] + 1:
            current.append((number, block))
        else:
            runs.append(current)
            current = [(number, block)]
    if current:
        runs.append(current)

    best_run = max(runs, key=lambda r: (1 if r[0][0] == 1 else 0, len(r)))

    pairs: list[QAPair] = []
    used_numbers: set[int] = set()

    for number, block in best_run:
        maybe = split_qa_line(block)
        if not maybe:
            continue
        left, right = maybe

        question, answer = left, sanitize_answer(right)
        if not looks_like_question(question) and looks_like_question(answer):
            question, answer = answer, sanitize_answer(left)

        if number in used_numbers or not answer:
            continue
        used_numbers.add(number)

        pairs.append(QAPair(number=number, question=question, answer=answer, source=source))

    return pairs


def load_documents() -> list[tuple[Path, str]]:
    docs: list[tuple[Path, str]] = []
    for path in sorted(DOCS_DIR.iterdir()):
        if path.suffix.lower() not in {".pdf", ".docx"}:
            continue
        text = extract_text(path)
        docs.append((path, text))
    return docs


def classify_topic(question: str, answer: str) -> str:
    joined = f"{question} {answer}".lower()
    for keyword, topic in TOPIC_KEYWORDS.items():
        if keyword in joined:
            return topic
    return "general"


def token_set(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-záéíóúñ]+", text.lower()) if len(t) > 2}


def similarity_score(base_q: str, base_a: str, other_q: str, other_a: str) -> int:
    q_overlap = len(token_set(base_q) & token_set(other_q))
    a_overlap = len(token_set(base_a) & token_set(other_a))
    return (q_overlap * 2) + a_overlap


def build_options(current: QAPair, qa_pairs: list[QAPair], pool_by_topic: dict[str, list[QAPair]], rng: random.Random) -> list[str]:
    used = {normalize_key(current.answer)}
    distractors: list[str] = []
    current_topic = classify_topic(current.question, current.answer)

    def choose_from_pool(pool: list[QAPair]) -> None:
        ranked = sorted(
            pool,
            key=lambda p: similarity_score(current.question, current.answer, p.question, p.answer),
            reverse=True,
        )
        for pair in ranked:
            key = normalize_key(pair.answer)
            if key in used:
                continue
            used.add(key)
            distractors.append(pair.answer)
            if len(distractors) == 3:
                return

    choose_from_pool([p for p in pool_by_topic.get(current_topic, []) if p.number != current.number])

    if len(distractors) < 3:
        choose_from_pool([p for p in qa_pairs if p.number != current.number])

    while len(distractors) < 3:
        filler = f"Opción anatómica alternativa {len(distractors) + 1}"
        if normalize_key(filler) not in used:
            distractors.append(filler)
            used.add(normalize_key(filler))

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
                question_number INTEGER NOT NULL,
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
            INSERT INTO qa_pairs (question_number, question, correct_answer, source_document)
            VALUES (?, ?, ?, ?)
            """,
            [(pair.number, pair.question, pair.answer, pair.source) for pair in qa_pairs],
        )

        conn.commit()


def create_quiz_json(qa_pairs: list[QAPair]) -> None:
    rng = random.Random(42)
    pool_by_topic: dict[str, list[QAPair]] = {}

    for pair in qa_pairs:
        topic = classify_topic(pair.question, pair.answer)
        pool_by_topic.setdefault(topic, []).append(pair)

    output = []
    for pair in qa_pairs:
        options = build_options(pair, qa_pairs, pool_by_topic, rng)
        output.append(
            {
                "id": pair.number,
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


def main() -> None:
    documents = load_documents()
    main_doc = next((doc for doc in documents if doc[0].name == MAIN_QUESTIONS_FILE), None)
    if not main_doc:
        raise SystemExit(f"Missing {MAIN_QUESTIONS_FILE} in documents directory")

    qa_pairs = parse_main_pdf_pairs(main_doc[1], MAIN_QUESTIONS_FILE)
    if not qa_pairs:
        raise SystemExit("No question-answer pairs were found in main.pdf")

    create_database(documents, qa_pairs)
    create_quiz_json(qa_pairs)

    print(f"Loaded {len(documents)} documents")
    print(f"Stored {len(qa_pairs)} question-answer pairs from {MAIN_QUESTIONS_FILE}")
    print(f"Database: {DB_PATH}")
    print(f"Quiz data: {QUESTIONS_JSON_PATH}")


if __name__ == "__main__":
    main()
