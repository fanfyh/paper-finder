// Paper-Finder Static Viewer — client-side JS
// Reads papers_data.json and renders filterable paper cards.

const FAV_KEY = "pf_favorites_v1";

// ── State ────────────────────────────────────────────────────────────────────
let allPapers = [];
let favorites = new Set(JSON.parse(localStorage.getItem(FAV_KEY) || "[]"));

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  restoreFavButtons();
  bindFilters();
  loadData();
});

function loadData() {
  const status = document.getElementById("metaText");
  status.textContent = "Loading...";
  fetch("papers_data.json")
    .then(r => {
      if (!r.ok) throw new Error("Not found");
      return r.json();
    })
    .then(data => {
      allPapers = data.papers || [];
      const dMin = data.crawled_date_min;
      const dMax = data.crawled_date_max;
      document.getElementById("metaText").textContent =
        `共 ${data.count || allPapers.length} 篇论文` +
        (dMin && dMax ? ` · 抓取 ${dMin} ~ ${dMax}` : "");
      render();
    })
    .catch(() => {
      // Fallback: try parent directory
      fetch("../papers_data.json")
        .then(r => r.json())
        .then(data => {
          allPapers = data.papers || [];
          document.getElementById("metaText").textContent =
            `共 ${data.count || allPapers.length} 篇论文`;
          render();
        })
        .catch(() => {
          document.getElementById("metaText").textContent = "未找到 papers_data.json";
          document.getElementById("summary").textContent = "";
        });
    });
}

// ── Render ───────────────────────────────────────────────────────────────────
function render() {
  const subset = filterPapers();
  const summary = document.getElementById("summary");
  const container = document.getElementById("cards");
  const tpl = document.getElementById("paperTpl");

  const n = subset.length;
  const total = allPapers.length;
  summary.textContent =
    n === total
      ? `显示全部 ${n} 篇`
      : `显示 ${n} 篇 / 共 ${total} 篇`;

  container.innerHTML = "";

  if (n === 0) {
    container.innerHTML = "<p style='color:#8a7465;font-size:14px;padding:20px'>没有匹配的论文。</p>";
    return;
  }

  for (const p of subset) {
    const article = tpl.content.cloneNode(true);

    // Pill: source + year
    const pill = article.querySelector(".pill");
    pill.textContent = [p.source_title, p.year].filter(Boolean).join(" · ");

    // Title
    const titleEl = article.querySelector(".title");
    titleEl.textContent = p.title;
    if (p.url) titleEl.href = p.url;

    // Favorite button
    const favBtn = article.querySelector(".favorite-btn");
    updateFavBtn(favBtn, p);
    favBtn.addEventListener("click", () => toggleFav(p, favBtn));

    // Meta
    const metaEl = article.querySelector(".meta");
    metaEl.innerHTML = [
      p.author_line,
      p.published_date ? `发表: ${p.published_date}` : "",
      p.cited_by_count ? `引用: ${p.cited_by_count}` : "",
      p.relevance ? `相关性: ${(p.relevance * 100).toFixed(0)}%` : "",
    ].filter(Boolean).join(" · ");

    // Tags
    const tagsEl = article.querySelector(".tags");
    if (p.source_title) {
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = p.source_title;
      tagsEl.appendChild(tag);
    }
    if (p.crawled_date) {
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = `抓取 ${p.crawled_date}`;
      tagsEl.appendChild(tag);
    }

    // Affiliations
    const affEl = article.querySelector(".affiliations");
    if (p.affiliations) {
      affEl.textContent = p.affiliations;
    } else {
      article.querySelector(".section").style.display = "none";
    }

    // Chinese summary
    const cnEl = article.querySelector(".summary-cn");
    if (p.summary_cn) {
      cnEl.textContent = p.summary_cn;
    } else {
      article.querySelector(".cn-section").style.display = "none";
    }

    // Abstract
    const absEl = article.querySelector(".abstract");
    absEl.textContent = p.abstract || "无摘要";

    container.appendChild(article);
  }
}

// ── Filter ────────────────────────────────────────────────────────────────────
function filterPapers() {
  const kwd = document.getElementById("keyword").value.trim().toLowerCase();
  const dateMode = document.getElementById("dateMode").value;
  const start = document.getElementById("startDate").value;
  const end = document.getElementById("endDate").value;
  const favOnly = document.getElementById("favoriteOnly").checked;
  const minRel = parseFloat(document.getElementById("minRelevance").value) || 0;

  return allPapers.filter(p => {
    if (favOnly && !favorites.has(titleKey(p))) return false;
    if (p.relevance < minRel) return false;

    const date = dateMode === "published_date"
      ? (p.published_date || "").slice(0, 10)
      : (p.crawled_date || "").slice(0, 10);
    if (start && date < start) return false;
    if (end && date > end) return false;

    if (!kwd) return true;
    const haystack = [
      p.title, p.author_line, p.affiliations,
      p.summary_cn, p.abstract, p.source_title,
      (p.authors || []).join(" "),
    ].join(" ").toLowerCase();
    return haystack.includes(kwd);
  });
}

// ── Favorites ────────────────────────────────────────────────────────────────
function titleKey(p) {
  return `${p.title}|${p.year}`;
}

function toggleFav(p, btn) {
  const k = titleKey(p);
  if (favorites.has(k)) {
    favorites.delete(k);
  } else {
    favorites.add(k);
  }
  localStorage.setItem(FAV_KEY, JSON.stringify([...favorites]));
  updateFavBtn(btn, p);
  render(); // re-render to update fav-only filter
}

function updateFavBtn(btn, p) {
  if (favorites.has(titleKey(p))) {
    btn.textContent = "★ 已收藏";
    btn.classList.add("active");
  } else {
    btn.textContent = "☆ 收藏";
    btn.classList.remove("active");
  }
}

function restoreFavButtons() {
  // Already handled in render(); this is for persistence check
}

// ── Filters binding ────────────────────────────────────────────────────────────
function bindFilters() {
  document.getElementById("applyBtn").addEventListener("click", render);
  document.getElementById("resetBtn").addEventListener("click", () => {
    document.getElementById("keyword").value = "";
    document.getElementById("startDate").value = "";
    document.getElementById("endDate").value = "";
    document.getElementById("favoriteOnly").checked = false;
    document.getElementById("minRelevance").value = "0";
    document.getElementById("dateMode").value = "crawled_date";
    render();
  });

  // Quick range buttons
  document.getElementById("quickRange").addEventListener("click", e => {
    const btn = e.target.closest("[data-range]");
    if (!btn) return;
    const range = btn.dataset.range;
    const today = new Date().toISOString().slice(0, 10);
    const mode = document.getElementById("dateMode").value;
    if (range === "today") {
      document.getElementById("startDate").value = today;
      document.getElementById("endDate").value = today;
    } else if (range === "3d") {
      const d = n => new Date(Date.now() - n * 86400e3).toISOString().slice(0, 10);
      document.getElementById("startDate").value = d(2);
      document.getElementById("endDate").value = today;
    } else if (range === "7d") {
      const d = n => new Date(Date.now() - n * 86400e3).toISOString().slice(0, 10);
      document.getElementById("startDate").value = d(6);
      document.getElementById("endDate").value = today;
    } else {
      document.getElementById("startDate").value = "";
      document.getElementById("endDate").value = "";
    }
    render();
  });

  // Enter in keyword input triggers filter
  document.getElementById("keyword").addEventListener("keydown", e => {
    if (e.key === "Enter") render();
  });
}
