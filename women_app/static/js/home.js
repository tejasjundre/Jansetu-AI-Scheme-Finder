document.addEventListener("DOMContentLoaded", () => {
  const corner = document.querySelector("[data-news-corner]");
  if (!corner) {
    return;
  }

  const items = Array.from(corner.querySelectorAll("[data-news-corner-item]"));
  const dots = Array.from(corner.querySelectorAll("[data-news-corner-dot]"));
  if (items.length < 2) {
    return;
  }

  let currentIndex = items.findIndex((item) => item.classList.contains("is-active"));
  if (currentIndex < 0) {
    currentIndex = 0;
  }
  let timerId = null;

  function activate(index) {
    currentIndex = (index + items.length) % items.length;
    items.forEach((item, itemIndex) => {
      item.classList.toggle("is-active", itemIndex === currentIndex);
    });
    updateDots();
  }

  function updateDots() {
    dots.forEach((dot, index) => {
      dot.classList.toggle("active", index === currentIndex);
    });
  }

  function startAutoScroll() {
    stopAutoScroll();
    timerId = window.setInterval(() => {
      activate(currentIndex + 1);
    }, 2000);
  }

  function stopAutoScroll() {
    if (timerId) {
      window.clearInterval(timerId);
      timerId = null;
    }
  }

  dots.forEach((dot) => {
    dot.addEventListener("click", () => {
      const nextIndex = Number.parseInt(dot.dataset.newsCornerDot || "0", 10);
      if (!Number.isNaN(nextIndex)) {
        activate(nextIndex);
      }
    });
  });

  corner.addEventListener("mouseenter", stopAutoScroll);
  corner.addEventListener("mouseleave", startAutoScroll);
  corner.addEventListener("focusin", stopAutoScroll);
  corner.addEventListener("focusout", startAutoScroll);

  activate(currentIndex);
  updateDots();
  startAutoScroll();
});
