from __future__ import annotations

import json
import random
import re
import sqlite3
import sys
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
REVIEWED_QUESTIONS_PATH = DATA_DIR / "reviewed_questions.tsv"
MAIN_QUESTIONS_FILE = "main.pdf"
REVIEWED_BLOCK_STARTS = {
    "Cuál es el derivado embrionario de las vértebras?": "Bloque 1. Embriología",
    "Qué tipo de articulación es la ATM?": "Bloque 2. ATM y masticación",
    "Cuál es un músculo prevertebral típico?": "Bloque 3. Cuello y columna",
    "Cuál es la afirmación correcta sobre la carótida común en el cuello?": "Bloque 4. Carótidas",
    "Qué tipo de articulación son los discos intervertebrales?": "Bloque 5. Diafragma y tronco",
    "Cuál es el contenido principal del conducto inguinal en el varón?": "Bloque 6. Conducto inguinal y abdomen",
    "Qué nervio pasa por el cuadrilátero de Velpeau?": "Bloque 7. Hombro, axila y plexo braquial",
    "Cuál es la función principal del braquiorradial?": "Bloque 8. Codo y antebrazo",
    "Qué nervio atraviesa el canal de Guyon?": "Bloque 9. Mano",
    "Cuál es el límite medial de la tabaquera anatómica?": "Bloque 10. Tabaquera anatómica",
    "Qué ligamento intracapsular pertenece a la articulación de la cadera?": "Bloque 11. Pelvis, cadera y muslo",
    "Qué músculos forman la pata de ganso superficial?": "Bloque 12. Rodilla, pierna y pie",
}
ANSWER_LETTER_RE = re.compile(r"RESPUESTA\s*[:：]?\s*([A-D1-4])", re.IGNORECASE)
OPTION_RE = re.compile(r"([a-d])\)\s*(.*?)(?=(?:[a-d]\)\s*)|$)", re.IGNORECASE | re.DOTALL)

ARROW_SEPARATORS = ("→", "->", "=>", "⇒")

# Matches trailing exam annotations like "MÁS REPETIDAS:", "MÁS REPETIDA:", etc.
TRAILING_ANNOTATION_RE = re.compile(r"\s*MÁS\s+REPET\w*[:\s].*$", re.IGNORECASE)
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
    "embrionario": "embryology",
    "somito": "embryology",
    "esclerotomo": "embryology",
    "miotomo": "embryology",
    "dermatomo": "embryology",
    "fisarias": "embryology",
    "atm": "tmj",
    "mandíbula": "tmj",
    "mandibula": "tmj",
    "mastic": "tmj",
    "bucinador": "tmj",
    "cigomático": "tmj",
    "cigomatico": "tmj",
    "cuello": "neck",
    "escaleno": "neck",
    "frénico": "neck",
    "frenico": "neck",
    "subclavia": "neck",
    "nucal": "neck",
    "carótida": "carotid",
    "carotida": "carotid",
    "salfopms": "carotid",
    "tiroidea": "carotid",
    "cervical ascendente": "carotid",
    "diafragma": "diaphragm",
    "hiato": "diaphragm",
    "vago": "diaphragm",
    "aórtico": "diaphragm",
    "aortico": "diaphragm",
    "esofágico": "diaphragm",
    "esofagico": "diaphragm",
    "inguinal": "inguinal",
    "recto": "inguinal",
    "epigástricos": "inguinal",
    "epigastricos": "inguinal",
    "glenohumeral": "shoulder",
    "manguito": "shoulder",
    "axila": "shoulder",
    "axilar": "shoulder",
    "supraescapular": "shoulder",
    "coracobraquial": "shoulder",
    "serrato": "shoulder",
    "romboides": "shoulder",
    "braquiorradial": "elbow",
    "pronador": "elbow",
    "supinador": "elbow",
    "fosa cubital": "elbow",
    "carpiano": "elbow",
    "epicóndilo": "elbow",
    "epicondilo": "elbow",
    "guyon": "hand",
    "lumbrical": "hand",
    "interóseo": "hand",
    "interoseo": "hand",
    "tenar": "hand",
    "hipotenar": "hand",
    "pisiforme": "hand",
    "tabaquera": "snuffbox",
    "escafoides": "snuffbox",
    "cadera": "hip",
    "obturador": "hip",
    "glúteo": "hip",
    "gluteo": "hip",
    "femoral": "hip",
    "rodilla": "leg",
    "peron": "leg",
    "safeno": "leg",
    "sural": "leg",
    "aquiles": "leg",
    "cuádriceps": "leg",
    "cuadriceps": "leg",
    "pata de ganso": "leg",
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


def normalize_key_relaxed(text: str) -> str:
    """Like normalize_key but also strips parenthetical notes and list separators.

    Used for near-duplicate detection so that e.g. "Gínglimo" and
    "Gínglimo (tróclea)" or "Sartorio + Grácil + Semitendinoso" and
    "Sartorio, grácil y semitendinoso" are treated as the same option.
    """
    # Drop parenthetical notes
    clean = re.sub(r"\([^)]*\)", " ", text)
    # Normalise list separators (+, comma, slash) to space
    clean = re.sub(r"[+,/]", " ", clean)
    # Remove Spanish/English conjunctions used as list connectors ("y", "e", "and")
    clean = re.sub(r"\b(y|e|and)\b", " ", clean, flags=re.IGNORECASE)
    return normalize_key(clean)


def option_token_set(text: str) -> set[str]:
    return {token for token in normalize_key(text).split() if len(token) > 2}


def answers_are_equivalent(left: str, right: str) -> bool:
    if normalize_key(left) == normalize_key(right):
        return True
    if normalize_key_relaxed(left) == normalize_key_relaxed(right):
        return True
    left_tokens = option_token_set(left)
    right_tokens = option_token_set(right)
    if left_tokens and right_tokens and (left_tokens <= right_tokens or right_tokens <= left_tokens):
        return True
    return False


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
    # Strip trailing exam annotations like "MÁS REPETIDAS:", "MÁS REPETIDA:", etc.
    clean = TRAILING_ANNOTATION_RE.sub("", clean)
    clean = normalize_space(clean).strip(".;, ")
    return clean


def sanitize_question(question: str) -> str:
    clean = normalize_space(question)
    clean = re.sub(r"^\W+", "", clean)
    return clean.strip(".;, ")


def split_numbered_blocks(text: str) -> list[tuple[int, str]]:
    entry_pattern = re.compile(r"(?is)(?<![A-Za-zÁÉÍÓÚÑáéíóúñ])(\d+)[\.\)]\s*(.+?)(?=(?<![A-Za-zÁÉÍÓÚÑáéíóúñ])\d+[\.\)]\s*|$)")
    return [(int(m.group(1)), normalize_space(m.group(2))) for m in entry_pattern.finditer(text)]


def split_mcq_block(block: str) -> tuple[str, dict[str, str]] | None:
    matches = list(OPTION_RE.finditer(block))
    if len(matches) < 2:
        return None

    question = sanitize_question(block[: matches[0].start()])
    if len(question) < 5:
        return None

    options: dict[str, str] = {}
    for match in matches:
        label = match.group(1).lower()
        option_text = sanitize_answer(re.sub(r"\s*[—-]+>\s*.*$", "", match.group(2), flags=re.DOTALL))
        option_text = normalize_space(option_text.replace("THIS", ""))
        if option_text:
            options[label] = option_text

    if len(options) < 2:
        return None

    return question, options


def parse_main_pdf_pairs(text: str, source: str) -> list[QAPair]:
    entries = split_numbered_blocks(text)
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


def parse_explicit_answer_pairs(text: str, source: str) -> list[QAPair]:
    pairs: list[QAPair] = []

    for number, block in split_numbered_blocks(text):
        answer_match = ANSWER_LETTER_RE.search(block)
        if not answer_match:
            continue

        parsed = split_mcq_block(block[: answer_match.start()])
        if not parsed:
            continue

        question, options = parsed
        answer_label = answer_match.group(1).lower()
        answer_label = {"1": "a", "2": "b", "3": "c", "4": "d"}.get(answer_label, answer_label)
        correct_answer = options.get(answer_label)
        if not correct_answer:
            continue

        pairs.append(QAPair(number=number, question=question, answer=correct_answer, source=source))

    return pairs


def parse_this_marker_pairs(text: str, source: str) -> list[QAPair]:
    pairs: list[QAPair] = []
    number = 0
    current_question: str | None = None
    options: list[tuple[str, bool]] = []

    def flush() -> None:
        nonlocal number, current_question, options
        if not current_question or not options:
            current_question = None
            options = []
            return

        correct = next((option for option, is_correct in options if is_correct), None)
        if correct:
            number += 1
            pairs.append(
                QAPair(
                    number=number,
                    question=sanitize_question(current_question),
                    answer=sanitize_answer(correct),
                    source=source,
                )
            )
        current_question = None
        options = []

    for raw_line in text.splitlines():
        line = normalize_space(raw_line.replace("\x00", " "))
        if not line or line.startswith("08/04/17") or re.fullmatch(r"\d+", line):
            continue
        if line.startswith("-"):
            flush()
            current_question = line.lstrip("-").strip()
            continue
        if line.startswith("•"):
            option = line.lstrip("•").strip()
            options.append((option.replace("THIS", "").strip(), "THIS" in option))

    flush()
    return pairs


def dedupe_pairs(qa_pairs: list[QAPair]) -> list[QAPair]:
    seen: set[tuple[str, str]] = set()
    deduped: list[QAPair] = []

    for pair in qa_pairs:
        key = (normalize_key(pair.question), normalize_key(pair.answer))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(pair)

    return deduped


def parse_document_pairs(path: Path, text: str) -> list[QAPair]:
    pairs: list[QAPair] = []
    if path.name == MAIN_QUESTIONS_FILE:
        pairs.extend(parse_main_pdf_pairs(text, path.name))
    pairs.extend(parse_explicit_answer_pairs(text, path.name))
    if "THIS" in text:
        pairs.extend(parse_this_marker_pairs(text, path.name))
    return dedupe_pairs(pairs)


def load_documents() -> list[tuple[Path, str]]:
    docs: list[tuple[Path, str]] = []
    for path in sorted(DOCS_DIR.iterdir()):
        if path.suffix.lower() not in {".pdf", ".docx"}:
            continue
        text = extract_text(path)
        docs.append((path, text))
    return docs


def load_reviewed_questions() -> list[QAPair]:
    if not REVIEWED_QUESTIONS_PATH.exists():
        return []

    pairs: list[QAPair] = []
    current_block = "Bloque 1. Embriología"
    for number, raw_line in enumerate(REVIEWED_QUESTIONS_PATH.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        question, answer = line.split("\t", 1)
        clean_question = sanitize_question(question)
        current_block = REVIEWED_BLOCK_STARTS.get(clean_question, current_block)
        pairs.append(
            QAPair(
                number=number,
                question=clean_question,
                answer=sanitize_answer(answer),
                source=current_block,
            )
        )
    return dedupe_pairs(pairs)


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
    used_strict: set[str] = {normalize_key(current.answer)}
    used_relaxed: set[str] = {normalize_key_relaxed(current.answer)}
    used_answers: list[str] = [current.answer]
    distractors: list[str] = []
    current_topic = classify_topic(current.question, current.answer)

    def choose_from_pool(pool: list[QAPair]) -> None:
        ranked = sorted(
            pool,
            key=lambda p: similarity_score(current.question, current.answer, p.question, p.answer),
            reverse=True,
        )
        for pair in ranked:
            key_strict = normalize_key(pair.answer)
            key_relaxed = normalize_key_relaxed(pair.answer)
            if key_strict in used_strict or key_relaxed in used_relaxed:
                continue
            if any(answers_are_equivalent(pair.answer, kept) for kept in used_answers):
                continue
            used_strict.add(key_strict)
            used_relaxed.add(key_relaxed)
            used_answers.append(pair.answer)
            distractors.append(pair.answer)
            if len(distractors) == 3:
                return

    choose_from_pool([p for p in qa_pairs if p.source == current.source and p is not current])

    if len(distractors) < 3:
        choose_from_pool([p for p in pool_by_topic.get(current_topic, []) if p is not current])

    if len(distractors) < 3:
        choose_from_pool([p for p in qa_pairs if p is not current])

    while len(distractors) < 3:
        filler = f"Opción anatómica alternativa {len(distractors) + 1}"
        if normalize_key(filler) not in used_strict:
            distractors.append(filler)
            used_strict.add(normalize_key(filler))

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
    for index, pair in enumerate(qa_pairs, start=1):
        options = build_options(pair, qa_pairs, pool_by_topic, rng)
        output.append(
            {
                "id": index,
                "number": pair.number,
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


def repair_quiz_json() -> None:
    """Clean the existing questions.json in-place.

    Removes trailing annotations (e.g. "MÁS REPETIDAS:") from every answer
    string and eliminates near-duplicate options within each question (e.g.
    "Gínglimo" and "Gínglimo (tróclea)" cannot both be options for the same
    question).  The correct answer is always preserved even if a looser
    duplicate of it exists; that duplicate distractor is dropped instead.
    """
    if not QUESTIONS_JSON_PATH.exists():
        print(f"{QUESTIONS_JSON_PATH.name} not found — nothing to repair.", file=sys.stderr)
        return

    with QUESTIONS_JSON_PATH.open(encoding="utf-8") as f:
        questions = json.load(f)

    changed = False
    for q in questions:
        # --- clean the correct answer ---
        correct_clean = sanitize_answer(q["correctAnswer"])
        if correct_clean != q["correctAnswer"]:
            q["correctAnswer"] = correct_clean
            changed = True

        # Pre-seed dedup sets with the correct answer so near-duplicate
        # distractors are dropped instead of the correct answer.
        seen_strict: set[str] = {normalize_key(correct_clean)}
        seen_relaxed: set[str] = {normalize_key_relaxed(correct_clean)}
        seen_answers: list[str] = [correct_clean]
        new_options: list[str] = []
        correct_added = False

        for opt in q["options"]:
            clean_opt = sanitize_answer(opt)
            if not clean_opt:
                changed = True
                continue

            # If this option IS the correct answer, keep it (but only once).
            if normalize_key(clean_opt) == normalize_key(correct_clean):
                if not correct_added:
                    new_options.append(clean_opt)
                    correct_added = True
                else:
                    changed = True  # duplicate correct-answer entry — drop it
                continue

            k_strict = normalize_key(clean_opt)
            k_relaxed = normalize_key_relaxed(clean_opt)
            if k_strict in seen_strict or k_relaxed in seen_relaxed:
                # Near-duplicate of an already-kept option — skip it.
                changed = True
                continue
            if any(answers_are_equivalent(clean_opt, kept) for kept in seen_answers):
                # Near-duplicate of an already-kept option — skip it.
                changed = True
                continue

            seen_strict.add(k_strict)
            seen_relaxed.add(k_relaxed)
            seen_answers.append(clean_opt)
            new_options.append(clean_opt)

        # Guarantee the correct answer is present in options.
        if not any(normalize_key(o) == normalize_key(correct_clean) for o in new_options):
            new_options.insert(0, correct_clean)
            changed = True

        if new_options != q["options"]:
            q["options"] = new_options
            changed = True

    if changed:
        QUESTIONS_JSON_PATH.write_text(
            json.dumps(questions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Repaired {QUESTIONS_JSON_PATH.name}: annotations stripped and near-duplicate options removed.")
    else:
        print(f"{QUESTIONS_JSON_PATH.name}: no repairs needed.")


def main() -> None:
    if "--repair-only" in sys.argv:
        repair_quiz_json()
        return

    documents = load_documents()
    qa_pairs: list[QAPair] = []
    for path, text in documents:
        if path.name == MAIN_QUESTIONS_FILE:
            qa_pairs.extend(parse_document_pairs(path, text))
    qa_pairs.extend(load_reviewed_questions())
    qa_pairs = dedupe_pairs(qa_pairs)
    if not qa_pairs:
        raise SystemExit("No question-answer pairs were found in the supported documents")

    create_database(documents, qa_pairs)
    create_quiz_json(qa_pairs)
    repair_quiz_json()  # Final cleanup pass on the freshly generated JSON

    print(f"Loaded {len(documents)} documents")
    print(f"Stored {len(qa_pairs)} question-answer pairs")
    print(f"Database: {DB_PATH}")
    print(f"Quiz data: {QUESTIONS_JSON_PATH}")


if __name__ == "__main__":
    main()
