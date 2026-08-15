async function fetchPowerballData(path) {
  const res = await fetch(path || '/data/powerball.json');
  if (!res.ok) throw new Error('Failed to load ' + (path || '/data/powerball.json'));
  return res.json();
}

function ballHTML(num, opts) {
  opts = opts || {};
  const classes = ['ball'];
  if (opts.small) classes.push('small');
  if (opts.special) classes.push('special');
  if (opts.placeholder) classes.push('placeholder');
  return `<span class="${classes.join(' ')}">${num}</span>`;
}

function renderLatestDraw(containerId, dateId, data) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const draw = data.latest_draw;
  el.innerHTML = draw.white_balls.map(n => ballHTML(n)).join('') + ballHTML(draw.powerball, { special: true });

  const dateEl = document.getElementById(dateId);
  if (dateEl) {
    const d = new Date(draw.draw_date + 'T00:00:00');
    dateEl.textContent = 'Latest draw — ' + d.toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' });
  }
}

function randomInt(max) {
  return Math.floor(Math.random() * max) + 1;
}
function randomDigit() {
  return Math.floor(Math.random() * 10);
}

// Shared by Pick 3 and Pick 4 - unlike generateQuickPick() above,
// digits can repeat within a single pick (e.g. 0,0,5,2 is valid), so
// this doesn't need generateQuickPick's Set-based duplicate avoidance.
// No Fireball digit included, matching the ticket checker's scope on
// both pages, which also only asks for the base digits.
function generateDigitQuickPick(digitCount) {
  const digits = [];
  for (let i = 0; i < digitCount; i++) digits.push(randomDigit());
  return digits;
}

function initDigitQuickPick(containerId, btnId, digitCount) {
  const el = document.getElementById(containerId);
  const btn = document.getElementById(btnId);
  if (!el || !btn) return;

  el.innerHTML = Array(digitCount).fill(0).map(() => ballHTML('-', { placeholder: true })).join('');

  btn.addEventListener('click', () => {
    const digits = generateDigitQuickPick(digitCount);
    el.innerHTML = digits.map(n => ballHTML(n)).join('');
  });
}

function generateQuickPick(game) {
  const whites = new Set();
  while (whites.size < game.white_ball_count) {
    whites.add(randomInt(game.white_ball_max));
  }
  const sorted = Array.from(whites).sort((a, b) => a - b);
  const special = randomInt(game.red_ball_max);
  return { white_balls: sorted, powerball: special };
}

function initQuickPick(containerId, btnId, data) {
  const el = document.getElementById(containerId);
  const btn = document.getElementById(btnId);
  if (!el || !btn) return;

  // Show placeholders until the user generates a pick.
  el.innerHTML = Array(data.game.white_ball_count).fill(0)
    .map(() => ballHTML('-', { placeholder: true })).join('') + ballHTML('-', { placeholder: true, special: true });

  btn.addEventListener('click', () => {
    const pick = generateQuickPick(data.game);
    el.innerHTML = pick.white_balls.map(n => ballHTML(n)).join('') + ballHTML(pick.powerball, { special: true });
  });
}

function initTicketChecker(rowId, btnId, resultId, data) {
  const row = document.getElementById(rowId);
  const btn = document.getElementById(btnId);
  const result = document.getElementById(resultId);
  if (!row || !btn || !result) return;

  const total = data.game.white_ball_count + 1;
  row.innerHTML = '';
  for (let i = 0; i < total; i++) {
    const input = document.createElement('input');
    input.type = 'text';
    input.inputMode = 'numeric';
    input.maxLength = 2;
    input.className = 'checker-ball' + (i === total - 1 ? ' checker-ball-special' : '');
    row.appendChild(input);
  }
  const inputs = Array.from(row.querySelectorAll('.checker-ball'));

  inputs.forEach((input, i) => {
    input.addEventListener('input', () => {
      input.value = input.value.replace(/\D/g, '').slice(0, 2);
      if (input.value.length === 2 && i < inputs.length - 1) inputs[i + 1].focus();
    });
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Backspace' && input.value === '' && i > 0) inputs[i - 1].focus();
      if (e.key === 'Enter') { e.preventDefault(); btn.click(); }
    });
    input.addEventListener('paste', (e) => {
      const text = (e.clipboardData || window.clipboardData).getData('text');
      const nums = text.match(/\d+/g);
      if (!nums) return;
      e.preventDefault();
      nums.slice(0, inputs.length - i).forEach((n, j) => { inputs[i + j].value = n.slice(0, 2); });
      inputs[Math.min(i + nums.length, inputs.length - 1)].focus();
    });
  });

  btn.addEventListener('click', () => {
    const values = inputs.map(inp => inp.value.trim());
    if (values.some(v => v === '')) {
      result.innerHTML = 'Enter all ' + data.game.white_ball_count + ' numbers plus the Powerball.';
      return;
    }
    const userNums = values.slice(0, data.game.white_ball_count).map(Number);
    const userSpecial = Number(values[values.length - 1]);
    const draw = data.latest_draw;
    const whiteMatches = userNums.filter(n => draw.white_balls.includes(n)).length;
    const specialMatch = userSpecial === draw.powerball;

    let msg = `Against the latest draw (${draw.draw_date}): <strong>${whiteMatches} of ${data.game.white_ball_count}</strong> white ball number${whiteMatches === 1 ? '' : 's'} matched`;
    msg += specialMatch ? ', and the Powerball matched.' : ', and the Powerball did not match.';
    result.innerHTML = msg;
  });
}

function renderStats(containerId, data) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const stats = data.stats_since_jackpot;
  const jackpot = data.last_jackpot;

  const jackpotDate = new Date(jackpot.date + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });

  const mostDrawnHTML = stats.most_drawn.slice(0, 3).map(m => `
    <span class="count-chip">
      <span class="num">${m.number}</span>
      <span class="count">${m.count}x</span>
    </span>
  `).join('');

  const notDrawnHTML = stats.not_drawn.slice(0, 12).map(n => `<span class="not-drawn-num">${n}</span>`).join('');

  el.innerHTML = `
    <div class="jackpot-banner">
      <span class="label">Since last jackpot win: </span>
      <span class="value">${stats.draws_since_jackpot} draws — ${jackpot.amount} won ${jackpotDate}</span>
    </div>
    <div class="stats-grid">
      <div>
        <p class="section-label">Most drawn since</p>
        <div class="chip-row">${mostDrawnHTML || '<span class="fine-print">No repeats yet.</span>'}</div>
      </div>
      <div>
        <p class="section-label">Not drawn since (${stats.draws_since_jackpot} draws)</p>
        <div class="chip-row">${notDrawnHTML || '<span class="fine-print">Every number has come up.</span>'}</div>
      </div>
    </div>
    <p class="stats-disclaimer">Every drawing is independent — this reflects history only, not odds of a future draw.</p>
  `;
}
