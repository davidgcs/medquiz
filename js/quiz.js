/**
 * MedQuiz — Quiz Game Logic
 *
 * Play modes:
 *  - "random"  : questions shuffled; every question is shown exactly once
 *                before the deck is reshuffled for the next round.
 *  - "ordered" : questions shown in database order; every question is shown
 *                exactly once before restarting from question 1.
 *
 * In both modes the player must answer all questions before any repeats.
 */

/* ── State ───────────────────────────────────────────────────── */
let allQuestions   = [];   // full question database
let queue          = [];   // indices into allQuestions for this round
let currentPos     = 0;    // position within queue
let currentAnswers = [];   // shuffled [correct, wrong, wrong, wrong]
let correctIndex   = -1;   // index in currentAnswers that is correct
let answered       = false;
let score          = 0;
let gameMode       = 'random';

/* ── Utility ─────────────────────────────────────────────────── */
/**
 * Fisher-Yates shuffle (in-place). Returns the array.
 * @param {Array} arr
 */
function shuffle(arr) {
  for (let i = arr.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [arr[i], arr[j]] = [arr[j], arr[i]];
  }
  return arr;
}

/* ── Screen Management ───────────────────────────────────────── */
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function showMenu() {
  showScreen('menu-screen');
}

/* ── Game Initialisation ─────────────────────────────────────── */
/**
 * Build a fresh queue of question indices for the current round.
 * In 'ordered' mode the queue is [0, 1, 2, …, n-1].
 * In 'random'  mode the queue is a shuffled copy of the same indices.
 */
function buildQueue() {
  queue = allQuestions.map((_, i) => i);
  if (gameMode === 'random') {
    shuffle(queue);
  }
}

/**
 * Entry point called from the mode selection buttons.
 * @param {'random'|'ordered'} mode
 */
function startGame(mode) {
  gameMode  = mode;
  score     = 0;
  currentPos = 0;
  buildQueue();
  showScreen('quiz-screen');
  renderQuestion();
}

/**
 * Restart the same game mode from scratch.
 */
function restartGame() {
  startGame(gameMode);
}

/* ── Question Rendering ──────────────────────────────────────── */
function renderQuestion() {
  if (currentPos >= queue.length) {
    showResults();
    return;
  }

  answered = false;

  const q = allQuestions[queue[currentPos]];

  // Build and shuffle the four options
  currentAnswers = shuffle([q.correct, ...q.wrong]);
  correctIndex   = currentAnswers.indexOf(q.correct);

  // Update question text and topic
  document.getElementById('question-text').textContent = q.question;
  document.getElementById('topic-badge').textContent   = q.topic;

  // Reset and populate answer buttons
  for (let i = 0; i < 4; i++) {
    const btn = document.getElementById(`answer-${i}`);
    btn.textContent = currentAnswers[i];
    btn.className   = 'answer-btn';
    btn.disabled    = false;
  }

  // Hide feedback and next button
  const feedback = document.getElementById('feedback');
  feedback.className = 'feedback hidden';
  document.getElementById('next-btn').classList.add('hidden');

  // Update header counters
  const total = queue.length;
  document.getElementById('question-counter').textContent =
    `${currentPos + 1} / ${total}`;
  document.getElementById('score-display').textContent =
    `Score: ${score}`;

  // Update progress bar (percentage of questions completed so far)
  const pct = (currentPos / total) * 100;
  document.getElementById('progress-bar').style.width = `${pct}%`;
}

/* ── Answer Selection ────────────────────────────────────────── */
/**
 * Called when the player clicks one of the four answer buttons.
 * @param {number} idx  0-3
 */
function selectAnswer(idx) {
  if (answered) return;
  answered = true;

  // Disable all buttons
  for (let i = 0; i < 4; i++) {
    document.getElementById(`answer-${i}`).disabled = true;
  }

  const isCorrect = idx === correctIndex;
  if (isCorrect) score++;

  // Highlight correct / wrong
  document.getElementById(`answer-${correctIndex}`).classList.add('correct');
  if (!isCorrect) {
    document.getElementById(`answer-${idx}`).classList.add('wrong');
  }

  // Show feedback
  const feedback = document.getElementById('feedback');
  feedback.textContent = isCorrect ? '✓ Correct!' : '✗ Incorrect!';
  feedback.className   = `feedback ${isCorrect ? 'correct' : 'wrong'}`;

  // Update score display
  document.getElementById('score-display').textContent = `Score: ${score}`;

  // Reveal next button
  document.getElementById('next-btn').classList.remove('hidden');
}

/* ── Navigation ──────────────────────────────────────────────── */
function nextQuestion() {
  currentPos++;
  renderQuestion();
}

/* ── Results ─────────────────────────────────────────────────── */
function showResults() {
  const total = queue.length;
  const pct   = total > 0 ? Math.round((score / total) * 100) : 0;

  document.getElementById('final-score').textContent  = score;
  document.getElementById('result-total').textContent = total;
  document.getElementById('result-pct').textContent   = `${pct}%`;

  let msg;
  if      (pct >= 90) msg = '🏆 Excellent! Outstanding medical knowledge!';
  else if (pct >= 75) msg = '🎉 Great job! You have solid medical knowledge!';
  else if (pct >= 60) msg = '👍 Good effort! Keep studying to improve!';
  else                msg = '📚 Keep practicing — medicine takes dedication!';

  document.getElementById('result-message').textContent = msg;
  showScreen('results-screen');
}

/* ── Load Questions & Bootstrap ──────────────────────────────── */
fetch('data/questions.json')
  .then(response => {
    if (!response.ok) throw new Error(`Failed to load questions: ${response.status}`);
    return response.json();
  })
  .then(data => {
    allQuestions = data;
    document.getElementById('total-count').textContent =
      `${allQuestions.length} questions across 6 medical topics`;
  })
  .catch(err => {
    console.error(err);
    document.getElementById('total-count').textContent =
      'Error loading questions. Please refresh the page.';
  });
