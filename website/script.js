// RepoLens landing — tiny vanilla interactions, no dependencies.

(() => {
  "use strict";

  // Current year in the footer.
  const year = document.getElementById("year");
  if (year) year.textContent = String(new Date().getFullYear());

  // Mobile nav toggle.
  const header = document.querySelector(".site-header");
  const toggle = document.querySelector(".nav-toggle");
  if (toggle && header) {
    toggle.addEventListener("click", () => {
      const open = header.classList.toggle("open");
      toggle.setAttribute("aria-expanded", String(open));
    });
    // Close the menu after tapping a link.
    header.querySelectorAll(".nav a").forEach((a) =>
      a.addEventListener("click", () => {
        header.classList.remove("open");
        toggle.setAttribute("aria-expanded", "false");
      })
    );
  }

  // Copy-to-clipboard on install commands.
  document.querySelectorAll(".copy").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const text = btn.getAttribute("data-copy-text") || "";
      try {
        await navigator.clipboard.writeText(text);
      } catch {
        // Fallback for older browsers / non-secure contexts.
        const ta = document.createElement("textarea");
        ta.value = text;
        ta.style.position = "fixed";
        ta.style.opacity = "0";
        document.body.appendChild(ta);
        ta.select();
        try { document.execCommand("copy"); } catch { /* ignore */ }
        ta.remove();
      }
      const original = btn.textContent;
      btn.textContent = "Copied ✓";
      btn.classList.add("done");
      setTimeout(() => {
        btn.textContent = original;
        btn.classList.remove("done");
      }, 1600);
    });
  });

  // Scroll-reveal: tag headings and cards, then fade them in on view.
  const revealTargets = document.querySelectorAll(
    ".section-title, .problem-grid article, .pillar, .feature, .flow li, .use-grid article, .faq details, .backends, .steps li, .stat-strip div"
  );
  revealTargets.forEach((el) => el.classList.add("reveal"));

  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add("in");
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: "0px 0px -40px 0px" }
    );
    revealTargets.forEach((el) => io.observe(el));
  } else {
    revealTargets.forEach((el) => el.classList.add("in"));
  }

  // Scrollspy: highlight the nav link for the section in view.
  const navLinks = Array.from(document.querySelectorAll(".nav a"));
  const sections = navLinks
    .map((a) => document.querySelector(a.getAttribute("href")))
    .filter(Boolean);

  if ("IntersectionObserver" in window && sections.length) {
    const spy = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            const id = e.target.id;
            navLinks.forEach((a) =>
              a.classList.toggle("active", a.getAttribute("href") === "#" + id)
            );
          }
        });
      },
      { rootMargin: "-45% 0px -50% 0px" }
    );
    sections.forEach((s) => spy.observe(s));
  }
})();
