const statusEl = document.getElementById("status");
const questionCard = document.getElementById("questionCard");
const questionText = document.getElementById("questionText");
const answersEl = document.getElementById("answers");
const feedbackEl = document.getElementById("feedback");
const sourceInfoEl = document.getElementById("sourceInfo");
const questionNumberEl = document.getElementById("questionNumber");

const correctCountEl = document.getElementById("correctCount");
const incorrectCountEl = document.getElementById("incorrectCount");
const totalCountEl = document.getElementById("totalCount");

const toggleReviewBtn = document.getElementById("toggleReview");
const reviewPanel = document.getElementById("reviewPanel");
const reviewListEl = document.getElementById("reviewList");

const modeRandomBtn = document.getElementById("modeRandom");
const modeOrderedBtn = document.getElementById("modeOrdered");

let questions = [];
let mode = "random";
let queue = [];
let pointer = 0;
let history = [];
let pendingQuestion = null;
let nextQuestionTimeout = null;

const score = {
  correct: 0,
  incorrect: 0,
  total: 0,
};

function shuffle(arr) {
  const copy = [...arr];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function startCycle() {
  const ids = questions.map((_, index) => index);
  queue = mode === "random" ? shuffle(ids) : ids;
  pointer = 0;
}

function nextQuestion() {
  if (!questions.length) return null;

  if (pendingQuestion) {
    const q = pendingQuestion;
    pendingQuestion = null;
    return q;
  }

  if (pointer >= queue.length) {
    startCycle();
  }

  const index = queue[pointer];
  pointer += 1;
  return questions[index];
}

function updateScore() {
  correctCountEl.textContent = String(score.correct);
  incorrectCountEl.textContent = String(score.incorrect);
  totalCountEl.textContent = String(score.total);
}

function updateToggleReviewBtn() {
  if (reviewPanel.hidden) {
    toggleReviewBtn.textContent = `All questions (${questions.length})`;
  } else {
    toggleReviewBtn.textContent = `Hide questions (${questions.length})`;
  }
}

function getLastAnswerForQuestion(questionId) {
  for (let i = history.length - 1; i >= 0; i -= 1) {
    if (history[i].id === questionId) return history[i];
  }
  return null;
}

function renderReview() {
  reviewListEl.innerHTML = "";

  questions.forEach((question) => {
    const entry = getLastAnswerForQuestion(question.id);

    const item = document.createElement("div");
    let statusClass = "review-unanswered";
    if (entry) {
      statusClass = entry.isCorrect ? "review-correct" : "review-incorrect";
    }
    item.className = `review-item ${statusClass}`;
    item.title = "Go to this question";
    item.style.cursor = "pointer";
    item.addEventListener("click", () => jumpToQuestion(question));

    const num = document.createElement("p");
    num.className = "review-meta";
    num.textContent = `Question #${question.id} — ${question.source}`;

    const q = document.createElement("p");
    q.className = "review-question";
    q.textContent = question.question;

    item.appendChild(num);
    item.appendChild(q);

    const optionsList = document.createElement("ul");
    optionsList.className = "review-options";

    question.options.forEach((optionText) => {
      const li = document.createElement("li");
      li.textContent = optionText;
      li.className = "review-option";

      if (optionText === question.correctAnswer) {
        li.classList.add("review-option-correct");
      }
      if (entry && optionText === entry.selected && !entry.isCorrect) {
        li.classList.add("review-option-selected-wrong");
      }

      optionsList.appendChild(li);
    });

    item.appendChild(optionsList);

    reviewListEl.appendChild(item);
  });
}

function jumpToQuestion(question) {
  if (nextQuestionTimeout !== null) {
    clearTimeout(nextQuestionTimeout);
    nextQuestionTimeout = null;
  }
  pendingQuestion = question;
  const q = nextQuestion();
  if (q) renderQuestion(q);
}

function renderQuestion(question) {
  questionCard.hidden = false;
  questionNumberEl.textContent = `Question #${question.id}`;
  sourceInfoEl.textContent = `Source: ${question.source}`;
  questionText.textContent = question.question;
  feedbackEl.textContent = "";
  answersEl.innerHTML = "";

  question.options.forEach((optionText) => {
    const button = document.createElement("button");
    button.className = "answer-btn";
    button.textContent = optionText;
    button.addEventListener("click", () => handleAnswer(question, optionText, button));
    answersEl.appendChild(button);
  });
}

function lockAnswers() {
  [...answersEl.querySelectorAll("button")].forEach((btn) => {
    btn.disabled = true;
  });
}

function handleAnswer(question, selectedAnswer, clickedButton) {
  lockAnswers();

  score.total += 1;
  const isCorrect = selectedAnswer === question.correctAnswer;

  if (isCorrect) {
    score.correct += 1;
    clickedButton.classList.add("correct");
    feedbackEl.textContent = "Correct!";
  } else {
    score.incorrect += 1;
    clickedButton.classList.add("incorrect");
    feedbackEl.textContent = `Incorrect. Correct answer: ${question.correctAnswer}`;

    [...answersEl.querySelectorAll("button")].forEach((btn) => {
      if (btn.textContent === question.correctAnswer) {
        btn.classList.add("correct");
      }
    });
  }

  history.push({
    id: question.id,
    source: question.source,
    question: question.question,
    selected: selectedAnswer,
    correctAnswer: question.correctAnswer,
    isCorrect,
  });

  updateScore();
  if (!reviewPanel.hidden) renderReview();

  nextQuestionTimeout = setTimeout(() => {
    nextQuestionTimeout = null;
    const following = nextQuestion();
    if (!following) return;
    renderQuestion(following);
  }, 900);
}

async function fetchQuestionsFrom(path) {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Unable to load question database from ${path}`);
  }

  const data = await response.json();
  if (!Array.isArray(data)) {
    throw new Error(`Question database at ${path} is not a list`);
  }

  return data;
}

async function loadQuestions() {
  const paths = ["./data/questions.json", "../data/questions.json"];
  const errors = [];

  for (const path of paths) {
    try {
      questions = await fetchQuestionsFrom(path);
      statusEl.textContent = `Loaded ${questions.length} questions.`;
      toggleReviewBtn.hidden = false;
      updateToggleReviewBtn();
      return;
    } catch (error) {
      errors.push(error.message);
    }
  }

  statusEl.textContent = `Error: Unable to load question database. Tried ${paths.join(" and ")}.`;
  console.error("Question database loading failed:", errors);
}

function startGame(selectedMode) {
  if (!questions.length) {
    statusEl.textContent = "No questions available.";
    return;
  }
  mode = selectedMode;
  startCycle();
  renderQuestion(nextQuestion());
  statusEl.textContent = `Mode: ${mode}. Questions will repeat only after all are shown.`;
}

modeRandomBtn.addEventListener("click", () => startGame("random"));
modeOrderedBtn.addEventListener("click", () => startGame("ordered"));

toggleReviewBtn.addEventListener("click", () => {
  reviewPanel.hidden = !reviewPanel.hidden;
  updateToggleReviewBtn();
  if (!reviewPanel.hidden) renderReview();
});

loadQuestions();
updateScore();
