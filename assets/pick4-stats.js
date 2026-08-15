/* pick4-stats.js
 * Stats module for Pick 4 pages. Direct adaptation of pick3-stats.js
 * for 4-digit draws instead of 3:
 *   - each draw is 4 digits (0-9) in thousands/hundreds/tens/ones position
 *   - front pair = positions 0-1 (thousands+hundreds), back pair =
 *     positions 2-3 (tens+ones) - real Pick 4 bet types, same
 *     reasoning as Pick 3's front/back pair, just shifted one digit
 *   - everything else (windowed stats, heatmap, explorer, lookup)
 *     mirrors pick3-stats.js structure exactly - see that file's
 *     header comment for the design reasoning, not repeated here
 *
 * Draw record shape (one per drawing, not per day):
 *   { draw_date: "2026-08-09", draw_time: "midday"|"evening",
 *     digits: [th, h, t, o], fireball: 6 | null }
 */

async function fetchPick4History(historyPath) {
  const res = await fetch(historyPath);
  if (!res.ok) throw new Error('Failed to load ' + historyPath);
  return res.json();
}

function windowedDraws(draws, windowSize) {
  return windowSize === 'all' ? draws : draws.slice(-windowSize);
}

const WINDOW_OPTIONS_FULL = [
  { label: 'Last 10', value: 10 },
  { label: 'Last 25', value: 25 },
  { label: 'Last 100', value: 100 },
  { label: 'All time', value: 'all' },
];

const WINDOW_OPTIONS_HEATMAP = [
  { label: 'Last 10', value: 10 },
  { label: 'Last 25', value: 25 },
  { label: 'Last 100', value: 100 },
];

function windowTabsHTML(current, groupId, options) {
  return `
    <div class="stat-tabs" data-tab-group="${groupId}">
      ${options.map(w => `<button class="stat-tab${w.value === current ? ' active' : ''}" data-window="${w.value}">${w.label}</button>`).join('')}
    </div>
  `;
}

/* ---------- State selector ---------- */

function stateSelectHTML(states, currentId) {
  return `
    <select class="explorer-select" id="pick4-state-select">
      ${states.map(s => `<option value="${s.id}"${s.id === currentId ? ' selected' : ''}>${s.label}</option>`).join('')}
    </select>
  `;
}

/* ---------- Hot & cold digits (overall, any position) ---------- */

function computeHotColdDigits(draws, windowSize) {
  const relevant = windowedDraws(draws, windowSize);
  const counts = {};
  for (let n = 0; n <= 9; n++) counts[n] = 0;
  relevant.forEach(d => d.digits.forEach(n => { counts[n] += 1; }));
  const entries = Object.entries(counts).map(([n, c]) => ({ number: Number(n), count: c }));
  const hot = [...entries].sort((a, b) => b.count - a.count || a.number - b.number).slice(0, 6);
  const cold = [...entries].sort((a, b) => a.count - b.count || a.number - b.number).slice(0, 6);
  return { hot, cold, drawCount: relevant.length };
}

function renderHotCold(containerId, draws, windowSize) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const { hot, cold, drawCount } = computeHotColdDigits(draws, windowSize);
  el.innerHTML = `
    <p class="section-label">Hot &amp; cold digits</p>
    ${windowTabsHTML(windowSize, 'shared', WINDOW_OPTIONS_FULL)}
    <p class="section-sub">Based on the last ${drawCount} draw${drawCount === 1 ? '' : 's'}</p>
    <div class="stats-grid">
      <div>
        <p class="stat-subhead hot">Hot</p>
        <div class="chip-row">${hot.map(h => `<span class="count-chip"><span class="num hot-num">${h.number}</span><span class="count">${h.count}x</span></span>`).join('')}</div>
      </div>
      <div>
        <p class="stat-subhead cold">Cold</p>
        <div class="chip-row">${cold.map(h => `<span class="count-chip"><span class="num cold-num">${h.number}</span><span class="count">${h.count}x</span></span>`).join('')}</div>
      </div>
    </div>
  `;
}

/* ---------- Digit heatmap by position ---------- */

const POSITIONS = [
  { key: 0, label: 'Thousands' },
  { key: 1, label: 'Hundreds' },
  { key: 2, label: 'Tens' },
  { key: 3, label: 'Ones' },
];

function computePositionFrequency(draws, posIndex) {
  const counts = {};
  for (let n = 0; n <= 9; n++) counts[n] = 0;
  draws.forEach(d => { counts[d.digits[posIndex]] += 1; });
  return counts;
}

function heatClass(count, max) {
  const ratio = max > 0 ? count / max : 0;
  if (ratio > 0.8) return 'heat-5';
  if (ratio > 0.6) return 'heat-4';
  if (ratio > 0.4) return 'heat-3';
  if (ratio > 0.2) return 'heat-2';
  return 'heat-1';
}

function renderHeatmap(containerId, draws, windowSize, onCellClick) {
  const el = document.getElementById(containerId);
  if (!el) return;

  const relevant = windowedDraws(draws, windowSize === 'all' ? 100 : windowSize);

  const rows = POSITIONS.map(pos => {
    const counts = computePositionFrequency(relevant, pos.key);
    const max = Math.max(...Object.values(counts));
    const cells = [];
    for (let n = 0; n <= 9; n++) {
      cells.push(`<button type="button" class="heat-cell pos-heat-cell ${heatClass(counts[n], max)}" data-num="${n}" data-pos="${pos.key}" title="${pos.label} ${n}: drawn ${counts[n]} times">${n}</button>`);
    }
    return `
      <div class="pos-heat-row">
        <span class="pos-heat-label">${pos.label}</span>
        <div class="pos-heat-cells">${cells.join('')}</div>
      </div>
    `;
  }).join('');

  el.innerHTML = `
    <p class="section-label">Digit heatmap by position <span class="muted-suffix">(0-9)</span></p>
    ${windowTabsHTML(windowSize === 'all' ? 100 : windowSize, 'heatmap', WINDOW_OPTIONS_HEATMAP)}
    <p class="section-sub">Based on the last ${relevant.length} draw${relevant.length === 1 ? '' : 's'}</p>
    <div class="heat-legend">
      <span>Cold</span>
      <span class="heat-legend-swatch heat-1"></span>
      <span class="heat-legend-swatch heat-2"></span>
      <span class="heat-legend-swatch heat-3"></span>
      <span class="heat-legend-swatch heat-4"></span>
      <span class="heat-legend-swatch heat-5"></span>
      <span>Hot</span>
    </div>
    <div class="pos-heat-grid">${rows}</div>
  `;

  el.querySelectorAll('.pos-heat-cell').forEach(cell => {
    cell.addEventListener('click', () => {
      if (onCellClick) onCellClick(Number(cell.dataset.num), Number(cell.dataset.pos));
    });
  });
}

/* ---------- Front pair / back pair frequency ---------- */

function computeFrontBackPairs(draws) {
  const frontCounts = {};
  const backCounts = {};
  draws.forEach(d => {
    const front = `${d.digits[0]}${d.digits[1]}`;
    const back = `${d.digits[2]}${d.digits[3]}`;
    frontCounts[front] = (frontCounts[front] || 0) + 1;
    backCounts[back] = (backCounts[back] || 0) + 1;
  });

  const topFront = Object.entries(frontCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);
  const topBack = Object.entries(backCounts).sort((a, b) => b[1] - a[1]).slice(0, 5);
  return { topFront, topBack };
}

function renderPairs(containerId, draws, windowSize) {
  const el = document.getElementById(containerId);
  if (!el) return;

  const relevant = windowedDraws(draws, windowSize);
  const { topFront, topBack } = computeFrontBackPairs(relevant);

  function chip([pair, count]) {
    return `<span class="pair-chip">${pair} <span class="pair-chip-count">${count}x</span></span>`;
  }

  el.innerHTML = `
    <p class="section-label">Pair frequency</p>
    ${windowTabsHTML(windowSize, 'shared', WINDOW_OPTIONS_FULL)}
    <p class="section-sub">Based on the last ${relevant.length} draw${relevant.length === 1 ? '' : 's'}</p>
    <div class="pairs-columns">
      <div>
        <p class="section-sub">Front pair (top 5)</p>
        <div class="chip-row">${topFront.map(chip).join('') || '<p class="fine-print">Not enough draws yet.</p>'}</div>
      </div>
      <div>
        <p class="section-sub">Back pair (top 5)</p>
        <div class="chip-row">${topBack.map(chip).join('') || '<p class="fine-print">Not enough draws yet.</p>'}</div>
      </div>
    </div>
  `;
}

/* ---------- Historical draw explorer ---------- */

function initExplorer(containerId, draws) {
  const el = document.getElementById(containerId);
  if (!el) return;

  const DEFAULT_ROWS = 10;
  const MAX_FILTERED_ROWS = 50;

  const years = Array.from(new Set(draws.map(d => d.draw_date.slice(0, 4)))).sort().reverse();
  const descending = [...draws].reverse();

  el.innerHTML = `
    <p class="section-label">Historical draw explorer</p>
    <div class="explorer-controls">
      <input type="text" class="explorer-input" id="p4-explorer-search" placeholder="Search date (YYYY-MM-DD) or digits">
      <select class="explorer-select" id="p4-explorer-year">
        <option value="">Year: any</option>
        ${years.map(y => `<option value="${y}">${y}</option>`).join('')}
      </select>
    </div>
    <div class="explorer-table-wrap">
      <table class="explorer-table">
        <thead><tr><th>Date</th><th>Draw</th><th>Digits</th><th>Fireball</th></tr></thead>
        <tbody id="p4-explorer-rows"></tbody>
      </table>
    </div>
    <p class="fine-print" id="p4-explorer-count"></p>
  `;

  const searchInput = el.querySelector('#p4-explorer-search');
  const yearSelect = el.querySelector('#p4-explorer-year');
  const rowsEl = el.querySelector('#p4-explorer-rows');
  const countEl = el.querySelector('#p4-explorer-count');

  function renderRows() {
    const query = searchInput.value.trim().toLowerCase();
    const year = yearSelect.value;
    const filtering = Boolean(query) || Boolean(year);

    let filtered = descending;
    if (year) filtered = filtered.filter(d => d.draw_date.startsWith(year));
    if (query) {
      filtered = filtered.filter(d => {
        if (d.draw_date.includes(query)) return true;
        if (d.digits.join('').includes(query.replace(/\D/g, ''))) return true;
        return false;
      });
    }

    const limit = filtering ? MAX_FILTERED_ROWS : DEFAULT_ROWS;
    const shown = filtered.slice(0, limit);

    rowsEl.innerHTML = shown.map(d => `
      <tr>
        <td>${d.draw_date}</td>
        <td style="text-transform:capitalize;">${d.draw_time}</td>
        <td>${d.digits.join('-')}</td>
        <td>${d.fireball ?? '-'}</td>
      </tr>
    `).join('') || '<tr><td colspan="4" class="fine-print">No draws match that search.</td></tr>';

    if (!filtering) {
      countEl.textContent = `Showing the last ${shown.length} draws - search above for anything further back.`;
    } else if (filtered.length > limit) {
      countEl.textContent = `Showing ${limit} of ${filtered.length} matching draws - narrow your search to see more.`;
    } else {
      countEl.textContent = `${filtered.length} matching draw${filtered.length === 1 ? '' : 's'}.`;
    }
  }

  searchInput.addEventListener('input', renderRows);
  yearSelect.addEventListener('change', renderRows);
  renderRows();
}

/* ---------- Number lookup (4-digit combo) ---------- */

function computeComboStats(draws, digits) {
  const straightIndices = [];
  const boxIndices = [];
  const sortedTarget = [...digits].sort().join('');

  draws.forEach((d, i) => {
    if (d.digits.join('') === digits.join('')) straightIndices.push(i);
    if ([...d.digits].sort().join('') === sortedTarget) boxIndices.push(i);
  });

  if (boxIndices.length === 0) return { straightCount: 0, boxCount: 0 };

  const lastBoxDrawn = draws[boxIndices[boxIndices.length - 1]].draw_date;

  return {
    straightCount: straightIndices.length,
    boxCount: boxIndices.length,
    lastBoxDrawn,
  };
}

function initLookup(containerId, draws) {
  const el = document.getElementById(containerId);
  if (!el) return;

  el.innerHTML = `
    <p class="section-label">Number lookup</p>
    <div class="explorer-controls">
      <input type="text" inputmode="numeric" class="explorer-input" id="p4-lookup-input" placeholder="Enter 4 digits, e.g. 4721" maxlength="4" style="max-width:160px;">
      <button class="btn-gold" id="p4-lookup-btn" type="button">Look up</button>
    </div>
    <div id="p4-lookup-result"></div>
  `;

  const input = el.querySelector('#p4-lookup-input');
  const btn = el.querySelector('#p4-lookup-btn');
  const resultEl = el.querySelector('#p4-lookup-result');

  function renderCombo(raw) {
    const clean = raw.replace(/\D/g, '');
    if (clean.length !== 4) {
      resultEl.innerHTML = '<p class="fine-print">Enter exactly 4 digits, 0-9 each.</p>';
      return;
    }
    const digits = clean.split('').map(Number);
    const stats = computeComboStats(draws, digits);
    if (stats.boxCount === 0) {
      resultEl.innerHTML = `<p class="section-sub">Number lookup - ${clean}</p><p class="fine-print">This combination (any order) hasn't been drawn in the stored history.</p>`;
      return;
    }
    resultEl.innerHTML = `
      <p class="section-sub">Number lookup - ${clean}</p>
      <div class="lookup-grid">
        <div class="lookup-stat"><span class="lookup-label">Straight hits</span><span class="lookup-value">${stats.straightCount}</span></div>
        <div class="lookup-stat"><span class="lookup-label">Box hits (any order)</span><span class="lookup-value">${stats.boxCount}</span></div>
        <div class="lookup-stat"><span class="lookup-label">Last box match</span><span class="lookup-value">${stats.lastBoxDrawn}</span></div>
      </div>
      <p class="stats-disclaimer">Every drawing is independent - this reflects history only, not odds of a future draw.</p>
    `;
  }

  btn.addEventListener('click', () => renderCombo(input.value));
  input.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); renderCombo(input.value); } });

  window.pick4JumpToDigit = function jumpToDigit(digit, posIndex) {
    const current = (input.value.replace(/\D/g, '') + '____').slice(0, 4).split('');
    current[posIndex] = String(digit);
    input.value = current.join('').replace(/_/g, '');
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  resultEl.innerHTML = '<p class="fine-print">Enter a 4-digit combination above to see its history.</p>';
}

/* ---------- Entry point ---------- */

async function initPick4Stats(ids, states, defaultStateId) {
  let currentState = states.find(s => s.id === defaultStateId) || states[0];
  let draws = [];
  let windowSize = 100;

  async function loadState(stateId) {
    currentState = states.find(s => s.id === stateId) || states[0];
    const history = await fetchPick4History(currentState.historyPath);
    draws = history.draws;
    renderAll();
    if (ids.lookup) initLookup(ids.lookup, draws);
    if (ids.explorer) initExplorer(ids.explorer, draws);
  }

  function renderAll() {
    if (ids.hotcold) renderHotCold(ids.hotcold, draws, windowSize);
    if (ids.heatmap) renderHeatmap(ids.heatmap, draws, windowSize, (digit, pos) => {
      if (window.pick4JumpToDigit) window.pick4JumpToDigit(digit, pos);
    });
    if (ids.pairs) renderPairs(ids.pairs, draws, windowSize);
    bindTabs();
  }

  function bindTabs() {
    document.querySelectorAll('[data-tab-group="shared"] .stat-tab').forEach(b => {
      b.addEventListener('click', () => {
        const v = b.dataset.window;
        windowSize = v === 'all' ? 'all' : Number(v);
        renderAll();
      });
    });
    bindHeatmapTabs();
  }

  function bindHeatmapTabs() {
    document.querySelectorAll('[data-tab-group="heatmap"] .stat-tab').forEach(b => {
      b.addEventListener('click', () => {
        renderHeatmap(ids.heatmap, draws, Number(b.dataset.window), (digit, pos) => {
          if (window.pick4JumpToDigit) window.pick4JumpToDigit(digit, pos);
        });
        bindHeatmapTabs();
      });
    });
  }

  const stateSelect = document.getElementById('pick4-state-select');
  if (stateSelect) {
    stateSelect.addEventListener('change', () => loadState(stateSelect.value));
  }

  await loadState(currentState.id);
}
