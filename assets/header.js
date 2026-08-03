/**
 * Shared header for LottoPickHub. Injects into any element with
 * id="site-header". Logo/wordmark click returns to homepage.
 */
const HEADER_HTML = `
<header class="site-header">
  <a href="/" class="brand">
    <img src="/assets/lottopickhub-icon.png" alt="LottoPickHub" class="brand-icon">
    <span class="brand-name">Lotto<span class="accent">Pick</span>Hub</span>
  </a>
  <nav class="site-nav">
  </nav>
  <div id="tip-jar-widget"></div>
</header>
<div class="gold-rule"></div>
`;

function initHeader() {
  const mount = document.getElementById('site-header');
  if (!mount) return;
  mount.innerHTML = HEADER_HTML;
  if (typeof renderTipJar === 'function') {
    renderTipJar('tip-jar-widget');
  }
}

document.addEventListener('DOMContentLoaded', initHeader);
