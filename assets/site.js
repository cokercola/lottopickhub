async function fetchPowerballData() {
  const res = await fetch('/data/powerball.json');
  if (!res.ok) throw new Error('Failed to load /data/powerball.json');
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

function initTicketChecker(formId, inputId, resultId, data) {
  const form = document.getElementById(formId);
  const input = document.getElementById(inputId);
  const result = document.getElementById(resultId);
  if (!form || !input || !result) return;

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    const nums = input.value.match(/\d+/g);
    if (!nums || nums.length < data.game.white_ball_count) {
      result.innerHTML = 'Enter your ' + data.game.white_ball_count + ' numbers (and optionally the Powerball) separated by spaces or commas.';
      return;
    }
    const userNums = nums.slice(0, data.game.white_ball_count).map(Number);
    const userSpecial = nums.length > data.game.white_ball_count ? Number(nums[data.game.white_ball_count]) : null;

    const draw = data.latest_draw;
    const whiteMatches = userNums.filter(n => draw.white_balls.includes(n)).length;
    const specialMatch = userSpecial !== null && userSpecial === draw.powerball;

    let msg = `Against the latest draw (${draw.draw_date}): <strong>${whiteMatches} of ${data.game.white_ball_count}</strong> white ball number${whiteMatches === 1 ? '' : 's'} matched`;
    if (userSpecial !== null) {
      msg += specialMatch ? ', and the Powerball matched.' : ', and the Powerball did not match.';
    } else {
      msg += '. (No Powerball number entered.)';
    }
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
