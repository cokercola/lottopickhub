/**
 * Tip jar button + popover for the header. Edit STRIPE_LINKS below
 * once you've created the Stripe products/Payment Links (Dashboard ->
 * Payment Links), same pattern as before - one link per amount tier.
 */
const STRIPE_LINKS = {
  5: "REPLACE_WITH_5_DOLLAR_LINK",
  10: "REPLACE_WITH_10_DOLLAR_LINK",
  25: "REPLACE_WITH_25_DOLLAR_LINK",
  custom: "REPLACE_WITH_CUSTOM_AMOUNT_LINK",
};

function renderTipJar(containerId) {
  const el = document.getElementById(containerId);
  if (!el) return;

  const isReady = (url) => url && !url.includes("REPLACE_WITH");
  const amountButtons = [5, 10, 25]
    .filter((amt) => isReady(STRIPE_LINKS[amt]))
    .map((amt) => `<a class="tip-amount-btn" href="${STRIPE_LINKS[amt]}" target="_blank" rel="noopener">$${amt}</a>`)
    .join("");
  const customButton = isReady(STRIPE_LINKS.custom)
    ? `<a class="tip-custom-btn" href="${STRIPE_LINKS.custom}" target="_blank" rel="noopener">Custom amount</a>`
    : "";

  el.innerHTML = `
    <div class="tip-wrap">
      <button class="tip-jar-btn" id="tip-toggle" type="button">Tip jar</button>
      <div class="tip-popover" id="tip-popover">
        <div class="tip-popover-label">Support LottoPickHub</div>
        <div class="tip-popover-text">Keeps the site free and ad-light — thank you!</div>
        <div class="tip-amounts">${amountButtons}</div>
        ${customButton}
      </div>
    </div>
  `;

  const toggle = document.getElementById("tip-toggle");
  const popover = document.getElementById("tip-popover");
  toggle.addEventListener("click", (e) => {
    e.stopPropagation();
    popover.classList.toggle("open");
  });
  document.addEventListener("click", () => {
    popover.classList.remove("open");
  });
}
