/* powerball-stats.js
 * Reads /data/powerball-history.json (every draw since the 2015-10-07
 * matrix change) and computes hot/cold numbers, a frequency heatmap,
 * pair/triple analysis, a historical draw explorer, and a per-number
 * lookup - all client-side. ~1,700 draws is small enough that every
 * computation here runs in a few milliseconds, so nothing is
 * precomputed server-side.
 *
 * Hot & cold, the heatmap, and pair/triple analysis share ONE window
 * selector (Last 10 / 25 / 100 / All time) so switching it updates
 * all three sections together, rather than each having its own
 * separate control.
 */

async function fetchPowerballHistory() {
  const res = await fetch('/data/powerball-history.json');
  if (!res.ok) throw new Error('Failed to load /data/powerball-history.json');
  return res.json();
}

function statBallHTML(num) {
  return `<span class="stat-ball">${num}</span>`;
}

function windowedDraws(draws, windowSize) {
  return windowSize === 'all' ? draws : draws.slice(-windowSize);
}

const WINDOW_OPTIONS = [
  { label: 'Last 10', value: 10 },
  { label: 'Last 25', value: 25 },
  { label: 'Last 100', value: 100 },
  { label: 'All time', value: 'all' },
];

function windowTabsHTML(current, groupId) {
  return `
    <div class="stat-tabs" data-tab-group="${groupId}">
      ${WINDOW_OPTIONS.map(w => `<button class="stat-tab${w.value === current ? ' active' : ''}" data-window="${w.value}">${w.label}</button>`).join('')}
    </div>
  `;
}

/* ---------- Hot & cold ---------- */

function computeHotCold(draws, windowSize) {
  const relevant = windowedDraws(draws, windowSize);
  const counts = {};
  for (let n = 1; n <= 69; n++) counts[n] = 0;
  relevant.forEach(d => d.white_balls.forEach(n => { counts[n] += 1; }));
  const entries = Object.entries(counts).map(([n, c]) => ({ number: Number(n), count: c }));
  const hot = [...entries].sort((a, b) => b.count - a.count || a.number - b.number).slice(0, 6);
  const cold = [...entries].sort((a, b) => a.count - b.count || a.number - b.number).slice(0, 6);
  return { hot, cold, drawCount: relevant.length };
}

function renderHotCold(containerId, draws, windowSize) {
  const el = document.getElementById(containerId);
  if (!el) return;
  const { hot, cold, drawCount } = computeHotCold(draws, windowSize);
  el.innerHTML = `
    <p class="section-label">Hot &amp; cold numbers</p>
    ${windowTabsHTML(windowSize, 'shared')}
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

/* ---------- Frequency heatmap ---------- */

function computeFrequency(draws) {
  const counts = {};
  for (let n = 1; n <= 69; n++) counts[n] = 0;
  draws.forEach(d => d.white_balls.forEach(n => { counts[n] += 1; }));
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

  const relevant = windowedDraws(draws, windowSize);
  const counts = computeFrequency(relevant);
  const max = Math.max(...Object.values(counts));

  const cells = [];
  for (let n = 1; n <= 69; n++) {
    cells.push(`<button type="button" class="heat-cell ${heatClass(counts[n], max)}" data-num="${n}" title="${n}: drawn ${counts[n]} times">${n}</button>`);
  }

  el.innerHTML = `
    <p class="section-label">Frequency heatmap <span class="muted-suffix">(1-69)</span></p>
    ${windowTabsHTML(windowSize, 'shared')}
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
    <div class="heat-grid">${cells.join('')}</div>
  `;

  el.querySelectorAll('.heat-cell').forEach(cell => {
    cell.addEventListener('click', () => {
      if (onCellClick) onCellClick(Number(cell.dataset.num));
    });
  });
}

/* ---------- Pair & triple analysis ---------- */

function computePairsAndTriples(draws) {
  const pairCounts = {};
  const tripleCounts = {};

  draws.forEach(d => {
    const b = d.white_balls;
    for (let i = 0; i < b.length; i++) {
      for (let j = i + 1; j < b.length; j++) {
        const pKey = `${b[i]},${b[j]}`;
        pairCounts[pKey] = (pairCounts[pKey] || 0) + 1;
        for (let k = j + 1; k < b.length; k++) {
          const tKey = `${b[i]},${b[j]},${b[k]}`;
          tripleCounts[tKey] = (tripleCounts[tKey] || 0) + 1;
        }
      }
    }
  });

  const topPairs = Object.entries(pairCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([key, count]) => ({ numbers: key.split(','), count }));

  const topTriples = Object.entries(tripleCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 5)
    .map(([key, count]) => ({ numbers: key.split(','), count }));

  return { topPairs, topTriples };
}

function renderPairs(containerId, draws, windowSize) {
  const el = document.getElementById(containerId);
  if (!el) return;

  const relevant = windowedDraws(draws, windowSize);
  const { topPairs, topTriples } = computePairsAndTriples(relevant);

  function row(item) {
    return `
      <div class="pair-row">
        <span class="pair-numbers">${item.numbers.map(n => statBallHTML(n)).join('<span class="pair-plus">+</span>')}</span>
        <span class="pair-count">${item.count} time${item.count === 1 ? '' : 's'}</span>
      </div>
    `;
  }

  const meaningfulPairs = topPairs.filter(p => p.count > 1);
  const meaningfulTriples = topTriples.filter(p => p.count > 1);

  const pairsHTML = meaningfulPairs.length
    ? meaningfulPairs.map(row).join('')
    : '<p class="fine-print">Not enough draws in this window for repeat pairs.</p>';

  const triplesHTML = meaningfulTriples.length
    ? meaningfulTriples.map(row).join('')
    : '<p class="fine-print">Not enough draws in this window for repeat triples.</p>';

  el.innerHTML = `
    <p class="section-label">Pair &amp; triple analysis</p>
    ${windowTabsHTML(windowSize, 'shared')}
    <p class="section-sub">Based on the last ${relevant.length} draw${relevant.length === 1 ? '' : 's'}</p>
    <p class="section-sub" style="margin-top:14px;">Top pairs</p>
    <div class="pair-list">${pairsHTML}</div>
    <p class="section-sub" style="margin-top:16px;">Top triples</p>
    <div class="pair-list">${triplesHTML}</div>
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
      <input type="text" class="explorer-input" id="explorer-search" placeholder="Search date (YYYY-MM-DD) or number">
      <select class="explorer-select" id="explorer-year">
        <option value="">Year: any</option>
        ${years.map(y => `<option value="${y}">${y}</option>`).join('')}
      </select>
    </div>
    <div class="explorer-table-wrap">
      <table class="explorer-table">
        <thead><tr><th>Date</th><th>Numbers</th></tr></thead>
        <tbody id="explorer-rows"></tbody>
      </table>
    </div>
    <p class="fine-print" id="explorer-count"></p>
  `;

  const searchInput = el.querySelector('#explorer-search');
  const yearSelect = el.querySelector('#explorer-year');
  const rowsEl = el.querySelector('#explorer-rows');
  const countEl = el.querySelector('#explorer-count');

  function renderRows() {
    const query = searchInput.value.trim().toLowerCase();
    const year = yearSelect.value;
    const filtering = Boolean(query) || Boolean(year);

    let filtered = descending;
    if (year) {
      filtered = filtered.filter(d => d.draw_date.startsWith(year));
    }
    if (query) {
      const asNum = Number(query);
      filtered = filtered.filter(d => {
        if (d.draw_date.includes(query)) return true;
        if (!Number.isNaN(asNum) && asNum >= 1) {
          return d.white_balls.includes(asNum) || d.powerball === asNum;
        }
        return false;
      });
    }

    const limit = filtering ? MAX_FILTERED_ROWS : DEFAULT_ROWS;
    const shown = filtered.slice(0, limit);

    rowsEl.innerHTML = shown.map(d => `
      <tr>
        <td>${d.draw_date}</td>
        <td>${[...d.white_balls].sort((a, b) => a - b).map(n => String(n).padStart(2, '0')).join(' ')} <span class="explorer-pb">${String(d.powerball).padStart(2, '0')}</span></td>
      </tr>
    `).join('') || '<tr><td colspan="2" class="fine-print">No draws match that search.</td></tr>';

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

/* ---------- Number lookup ---------- */

function computeNumberStats(draws, number) {
  const indices = [];
  draws.forEach((d, i) => { if (d.white_balls.includes(number)) indices.push(i); });

  if (indices.length === 0) {
    return { timesDrawn: 0 };
  }

  const timesDrawn = indices.length;
  const lastDrawn = draws[indices[indices.length - 1]].draw_date;

  const gaps = [];
  for (let i = 1; i < indices.length; i++) gaps.push(indices[i] - indices[i - 1]);
  const avgGap = gaps.length ? gaps.reduce((a, b) => a + b, 0) / gaps.length : 0;
  const longestGap = gaps.length ? Math.max(...gaps) : 0;

  const partnerCounts = {};
  const pbCounts = {};
  indices.forEach(i => {
    const d = draws[i];
    d.white_balls.forEach(n => { if (n !== number) partnerCounts[n] = (partnerCounts[n] || 0) + 1; });
    pbCounts[d.powerball] = (pbCounts[d.powerball] || 0) + 1;
  });

  const commonPartner = Object.entries(partnerCounts).sort((a, b) => b[1] - a[1])[0];
  const commonPB = Object.entries(pbCounts).sort((a, b) => b[1] - a[1])[0];

  return {
    timesDrawn,
    lastDrawn,
    avgGap,
    longestGap,
    commonPartner: commonPartner ? commonPartner[0] : null,
    commonPB: commonPB ? commonPB[0] : null,
  };
}

function initLookup(containerId, draws) {
  const el = document.getElementById(containerId);
  if (!el) return;

  el.innerHTML = `
    <p class="section-label">Number lookup</p>
    <div class="explorer-controls">
      <input type="text" inputmode="numeric" class="explorer-input" id="lookup-input" placeholder="Enter a number, 1-69" maxlength="2" style="max-width:160px;">
      <button class="btn-gold" id="lookup-btn" type="button">Look up</button>
    </div>
    <div id="lookup-result"></div>
  `;

  const input = el.querySelector('#lookup-input');
  const btn = el.querySelector('#lookup-btn');
  const resultEl = el.querySelector('#lookup-result');

  function renderNumber(number) {
    if (!Number.isInteger(number) || number < 1 || number > 69) {
      resultEl.innerHTML = '<p class="fine-print">Enter a number between 1 and 69.</p>';
      return;
    }
    const stats = computeNumberStats(draws, number);
    if (stats.timesDrawn === 0) {
      resultEl.innerHTML = `<p class="section-sub">Number lookup - ${number}</p><p class="fine-print">This number hasn't been drawn since ${draws[0] ? draws[0].draw_date : 'the matrix change'}.</p>`;
      return;
    }
    resultEl.innerHTML = `
      <p class="section-sub">Number lookup - ${number}</p>
      <div class="lookup-grid">
        <div class="lookup-stat"><span class="lookup-label">Times drawn</span><span class="lookup-value">${stats.timesDrawn}</span></div>
        <div class="lookup-stat"><span class="lookup-label">Last drawn</span><span class="lookup-value">${stats.lastDrawn}</span></div>
        <div class="lookup-stat"><span class="lookup-label">Avg gap</span><span class="lookup-value">${stats.avgGap.toFixed(1)} draws</span></div>
        <div class="lookup-stat"><span class="lookup-label">Longest gap</span><span class="lookup-value">${stats.longestGap} draws</span></div>
        <div class="lookup-stat"><span class="lookup-label">Common partner</span><span class="lookup-value">${stats.commonPartner ?? '-'}</span></div>
        <div class="lookup-stat"><span class="lookup-label">Common Powerball</span><span class="lookup-value">${stats.commonPB ?? '-'}</span></div>
      </div>
      <p class="stats-disclaimer">Every drawing is independent - this reflects history only, not odds of a future draw.</p>
    `;
  }

  btn.addEventListener('click', () => renderNumber(Number(input.value)));
  input.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); renderNumber(Number(input.value)); } });

  window.powerballJumpToNumber = function jumpToNumber(number) {
    input.value = number;
    renderNumber(number);
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  resultEl.innerHTML = '<p class="fine-print">Enter a number above, or click any cell in the heatmap, to see its history.</p>';
}

/* ---------- Entry point ---------- */

async function initPowerballStats(ids) {
  const history = await fetchPowerballHistory();
  const draws = history.draws;

  let windowSize = 100;

  function renderShared() {
    if (ids.hotcold) renderHotCold(ids.hotcold, draws, windowSize);
    if (ids.heatmap) renderHeatmap(ids.heatmap, draws, windowSize, num => {
      if (window.powerballJumpToNumber) window.powerballJumpToNumber(num);
    });
    if (ids.pairs) renderPairs(ids.pairs, draws, windowSize);
    bindSharedTabs();
  }

  function bindSharedTabs() {
    document.querySelectorAll('[data-tab-group="shared"] .stat-tab').forEach(btn => {
      btn.addEventListener('click', () => {
        const v = btn.dataset.window;
        windowSize = v === 'all' ? 'all' : Number(v);
        renderShared();
      });
    });
  }

  renderShared();
  if (ids.lookup) initLookup(ids.lookup, draws);
  if (ids.explorer) initExplorer(ids.explorer, draws);
}
