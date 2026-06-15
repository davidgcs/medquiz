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

const modeRandomBtn = document.getElementById("modeRandom");
const modeOrderedBtn = document.getElementById("modeOrdered");

let questions = [];
let mode = "random";
let queue = [];
let pointer = 0;

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

  updateScore();

  setTimeout(() => {
    const following = nextQuestion();
    if (!following) return;
    renderQuestion(following);
  }, 900);
}

async function loadQuestions() {
  try {
    const response = await fetch("./data/questions.json");
    if (!response.ok) {
      throw new Error("Unable to load question database");
    }
    questions = await response.json();
    statusEl.textContent = `Loaded ${questions.length} questions.`;
  } catch (error) {
    statusEl.textContent = `Error: ${error.message}`;
  }
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

loadQuestions();
updateScore();
