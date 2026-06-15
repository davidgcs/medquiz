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

const revealAnswersBtn = document.getElementById("revealAnswers");
const toggleReviewBtn = document.getElementById("toggleReview");
const reviewModal = document.getElementById("reviewModal");
const reviewBackdrop = document.getElementById("reviewBackdrop");
const reviewPanel = document.getElementById("reviewPanel");
const reviewListEl = document.getElementById("reviewList");
const closeReviewBtn = document.getElementById("closeReview");

const modeRandomBtn = document.getElementById("modeRandom");
const modeOrderedBtn = document.getElementById("modeOrdered");

let questions = [];
let mode = "random";
let queue = [];
let currentQuestion = null;
let history = [];
let nextQuestionTimeout = null;
let revealAllCorrectAnswers = false;

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
  queue = questions.map((_, index) => index);
  if (mode === "random") {
    queue = shuffle(queue);
  }
}

function nextQuestion() {
  if (!questions.length) return null;
  if (!queue.length) {
    startCycle();
  }
  const index = queue.shift();
  currentQuestion = questions[index] ?? null;
  return currentQuestion;
}

function updateScore() {
  correctCountEl.textContent = String(score.correct);
  incorrectCountEl.textContent = String(score.incorrect);
  totalCountEl.textContent = String(score.total);
}

function updateToggleReviewBtn() {
  if (reviewModal.hidden) {
    toggleReviewBtn.textContent = `All questions (${questions.length})`;
  } else {
    toggleReviewBtn.textContent = `Hide questions (${questions.length})`;
  }
}

function updateRevealAnswersBtn() {
  revealAnswersBtn.disabled = revealAllCorrectAnswers;
  revealAnswersBtn.textContent = revealAllCorrectAnswers
    ? "Correct answers revealed"
    : "Reveal correct answers";
}

function getLastAnswerForQuestion(questionId) {
  for (let i = history.length - 1; i >= 0; i -= 1) {
    if (history[i].id === questionId) return history[i];
  }
  return null;
}

function getQuestionNumber(question) {
  return question.number ?? question.id;
}

function getQuestionIndex(questionId) {
  return questions.findIndex((question) => question.id === questionId);
}

function closeReview() {
  reviewModal.hidden = true;
  document.body.classList.remove("modal-open");
  updateToggleReviewBtn();
}

function openReview() {
  renderReview();
  reviewModal.hidden = false;
  document.body.classList.add("modal-open");
  updateToggleReviewBtn();
}

function reorderQueueFromQuestion(question) {
  const currentIndex = getQuestionIndex(question.id);
  if (currentIndex < 0) return;

  queue = queue.filter((index) => index !== currentIndex);

  if (mode === "random") {
    queue = shuffle(queue);
    return;
  }

  const remainingLater = [];
  const remainingEarlier = [];
  queue.forEach((index) => {
    if (index > currentIndex) {
      remainingLater.push(index);
    } else {
      remainingEarlier.push(index);
    }
  });
  queue = [...remainingLater, ...remainingEarlier];
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
    const isUnanswered = !entry;
    item.className = `review-item ${statusClass}`;
    if (currentQuestion && currentQuestion.id === question.id) {
      item.classList.add("review-current");
    }
    if (isUnanswered) {
      item.classList.add("review-clickable");
      item.title = "Go to this question";
      item.addEventListener("click", () => jumpToQuestion(question));
    }

    const num = document.createElement("p");
    num.className = "review-meta";
    num.textContent = `Question #${getQuestionNumber(question)} — ${question.source}`;

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
      const shouldRevealCorrectAnswer = revealAllCorrectAnswers || Boolean(entry);

      if (shouldRevealCorrectAnswer && optionText === question.correctAnswer) {
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
  reorderQueueFromQuestion(question);
  closeReview();
  renderQuestion(question);
}

function renderQuestion(question) {
  currentQuestion = question;
  questionCard.hidden = false;
  questionNumberEl.textContent = `Question #${getQuestionNumber(question)}`;
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
    number: getQuestionNumber(question),
    source: question.source,
    question: question.question,
    selected: selectedAnswer,
    correctAnswer: question.correctAnswer,
    isCorrect,
  });

  updateScore();
  if (!reviewModal.hidden) renderReview();

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
  const paths = ["../data/questions.json", "./data/questions.json"];
  const errors = [];

  for (const path of paths) {
    try {
      questions = await fetchQuestionsFrom(path);
      statusEl.textContent = `Loaded ${questions.length} questions.`;
      revealAnswersBtn.hidden = false;
      toggleReviewBtn.hidden = false;
      updateRevealAnswersBtn();
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
  if (nextQuestionTimeout !== null) {
    clearTimeout(nextQuestionTimeout);
    nextQuestionTimeout = null;
  }
  closeReview();
  mode = selectedMode;
  startCycle();
  renderQuestion(nextQuestion());
  statusEl.textContent = `Mode: ${mode}. Questions will repeat only after all are shown.`;
}

modeRandomBtn.addEventListener("click", () => startGame("random"));
modeOrderedBtn.addEventListener("click", () => startGame("ordered"));

revealAnswersBtn.addEventListener("click", () => {
  if (revealAllCorrectAnswers) return;
  revealAllCorrectAnswers = true;
  updateRevealAnswersBtn();
  if (!reviewModal.hidden) renderReview();
});

toggleReviewBtn.addEventListener("click", () => {
  if (reviewModal.hidden) {
    openReview();
  } else {
    closeReview();
  }
});

reviewBackdrop.addEventListener("click", closeReview);
closeReviewBtn.addEventListener("click", closeReview);
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !reviewModal.hidden) {
    closeReview();
  }
});

loadQuestions();
updateScore();
