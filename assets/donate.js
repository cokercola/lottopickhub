/**
 * Tip jar button + popover for the header. Edit STRIPE_LINKS below
 * once you've created the Stripe products/Payment Links (Dashboard ->
 * Payment Links), same pattern as before - one link per amount tier.
 */
const STRIPE_LINKS = {
  5: "https://buy.stripe.com/fZu6oJ5PE6MO9dS3bcebu04",
  10: "https://buy.stripe.com/3cI00l1zoefgdu8h22ebu05",
  25: "https://buy.stripe.com/00w3cxb9Y5IK3Ty278ebu06",
  custom: "https://buy.stripe.com/fZu4gB91Q6MO0HmbHIebu07",
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
