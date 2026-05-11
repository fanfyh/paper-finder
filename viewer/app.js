// Paper-Finder — Academic Redesign (v2)
// Client-side renderer with collapsible sections

const FAV_KEY = "pf_favorites_v2";

// ── Journal abbreviation map ─────────────────────────────────────────────────
const JOURNAL_ABBR = {
  "American Economic Review": "AER",
  "American Economic Review: Papers and Proceedings": "AER P&P",
  "American Economic Journal: Applied Economics": "AEJ: Appl",
  "American Economic Journal: Economic Policy": "AEJ: Pol",
  "American Economic Journal: Microeconomics": "AEJ: Micro",
  "American Economic Journal: Macroeconomics": "AEJ: Macro",
  "The Quarterly Journal of Economics": "QJE",
  "Journal of Political Economy": "JPE",
  "Journal of Economic Growth": "JEG",
  "Review of Economic Studies": "REStud",
  "Review of Economics and Statistics": "Restat",
  "Econometrica": "Em",
  "Journal of Econometrics": "JEconomet",
  "Journal of the European Economic Association": "JEEA",
  "European Economic Review": "EER",
  "Journal of Labor Economics": "JLE",
  "Journal of Human Resources": "JHR",
  "Journal of Public Economics": "J. Public Econ.",
  "Journal of Urban Economics": "JUE",
  "Journal of Development Economics": "JDE",
  "World Bank Economic Review": "WBER",
  "Journal of Environmental Economics and Management": "JEEM",
  "Energy Economics": "Energy Econ.",
  "Resource and Energy Economics": "Res. Energy Econ.",
  "Journal of Health Economics": "JHE",
  "Health Economics": "Health Econ.",
  "Journal of Economic Perspectives": "JEP",
  "Journal of Economic Literature": "JEL",
  "Economic Journal": "Econ. J.",
  "Games and Economic Behavior": "GEB",
  "International Economic Review": "IER",
  "Journal of Economic Theory": "JET",
  "Theoretical Economics": "Theor. Econ.",
  "Rand Journal of Economics": "RJE",
  "Journal of Economic Behavior & Organization": "JEBO",
  "Journal of Economic Inequality": "JEI",
  "Oxford Bulletin of Economics and Statistics": "OBES",
  "Oxford Economic Papers": "OEP",
  "Review of Economic Dynamics": "Rev. Econ. Dyn.",
  "Journal of Macroeconomics": "JMacro",
  "Journal of Monetary Economics": "JME",
  "Journal of Money, Credit and Banking": "JMCB",
  "Journal of Financial Economics": "JFE",
  "Review of Financial Studies": "RFS",
  "American Economic Review: Papers & Proceedings": "AER P&P",
  "Proceedings of the National Academy of Sciences": "PNAS",
  "Nature Climate Change": "Nat. Clim. Change",
  "Science": "Science",
  "Nature": "Nature",
  "PNAS": "PNAS",
  "Social Science & Medicine": "SSM",
  "Regional Science and Urban Economics": "RSUE",
  "Urban Studies": "Urban Stud.",
  "Housing Policy Debate": "Hous. Policy Debate",
  "Land Economics": "Land Econ.",
  "Real Estate Economics": "Real Est. Econ.",
  "Journal of Housing Economics": "J. Housing Econ.",
  "Social Policy & Administration": "Soc. Policy Admin.",
  "Policy Studies Journal": "Policy Stud. J.",
  "China Economic Review": "China Econ. Rev.",
  "China Quarterly": "China Q.",
  "Journal of Comparative Economics": "J. Comp. Econ.",
  "World Development": "World Dev.",
  "Journal of Economic Geography": "JEG",
  "Review of Income and Wealth": "Rev. Income Wealth",
  "Scandinavian Journal of Economics": "Scand. J. Econ.",
  "Economica": "Economica",
  "Fiscal Studies": "Fiscal Stud.",
  "Contemporary Economic Policy": "Contemp. Econ. Pol.",
  "Contemporary Economic Policy": "Contemp. Econ. Pol.",
  "Applied Economics": "Appl. Econ.",
  "Applied Economics Letters": "Appl. Econ. Lett.",
  "Journal of Policy Modeling": "J. Policy Model.",
  "Environmental and Resource Economics": "Env. Resour. Econ.",
  "Ecological Economics": "Ecol. Econ.",
  "Transportation Research Part A": "Transport Res. A",
  "Transportation Research Part B": "Transport Res. B",
  "Transportation Research Part D": "Transport Res. D",
  "Journal of Transport Geography": "J. Transp. Geog.",
  "Energy Policy": "Energy Policy",
  "Technological Forecasting and Social Change": "Tech. Forecast. Soc. Change",
};

function abbrJournal(name) {
  if (!name) return "";
  // Try exact match first
  if (JOURNAL_ABBR[name]) return JOURNAL_ABBR[name];
  // Try case-insensitive partial
  const lower = name.toLowerCase();
  for (const [key, val] of Object.entries(JOURNAL_ABBR)) {
    if (lower === key.toLowerCase()) return val;
    if (lower.includes(key.toLowerCase())) return val;
  }
  // Fallback: truncate long names, take first 15 chars
  if (name.length > 18) {
    const words = name.split(" ");
    if (words.length >= 3) {
      return words.slice(0, 3).map(w => w[0]).join(".") + ".";
    }
    return name.slice(0, 15).trim() + "…";
  }
  return name;
}

// ── State ────────────────────────────────────────────────────────────────────
let allPapers = [];
let favorites = new Set(JSON.parse(localStorage.getItem(FAV_KEY) || "[]"));

// ── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  restoreFavs();
  bindFilters();
  loadData();
});

function loadData() {
  const meta = document.getElementById("metaText");
  meta.textContent = "Loading…";
  fetch("papers_data.json")
    .then(r => { if (!r.ok) throw new Error(); return r.json(); })
    .then(data => {
      allPapers = data.papers || [];
      const dMin = data.crawled_date_min, dMax = data.crawled_date_max;
      meta.textContent =
        `共 ${data.count || allPapers.length} 篇论文` +
        (dMin && dMax ? ` · 抓取 ${dMin} ~ ${dMax}` : "");
      render();
    })
    .catch(() => {
      fetch("../papers_data.json")
        .then(r => r.json())
        .then(data => {
          allPapers = data.papers || [];
          meta.textContent = `共 ${allPapers.length} 篇论文`;
          render();
        })
        .catch(() => { meta.textContent = "未找到 papers_data.json"; });
    });
}

// ── Render ────────────────────────────────────────────────────────────────────
function render() {
  const subset = filterPapers();
  const summary = document.getElementById("summary");
  const container = document.getElementById("cards");
  const tpl = document.getElementById("paperTpl");

  summary.textContent =
    subset.length === allPapers.length
      ? `显示全部 ${subset.length} 篇`
      : `显示 ${subset.length} 篇 / 共 ${allPapers.length} 篇`;

  container.innerHTML = "";

  if (subset.length === 0) {
    container.innerHTML = "<p class='no-results'>没有匹配的论文。</p>";
    return;
  }

  for (const p of subset) {
    const article = tpl.content.cloneNode(true);
    const card = article.querySelector(".card");

    // ── Header: journal badge, year, interest, fav button ──
    const badge = article.querySelector(".journal-badge");
    const fullName = p.source_title || p.venue || "";
    badge.dataset.full = fullName;
    badge.dataset.abbr = abbrJournal(fullName) || fullName;
    if (!fullName) badge.style.display = "none";

    const yearPill = article.querySelector(".year-pill");
    yearPill.textContent = p.year && p.year !== "None" ? p.year : "";
    if (!yearPill.textContent) yearPill.style.display = "none";

    const interestBadge = article.querySelector(".interest-badge");
    if (p.interest_name) {
      interestBadge.textContent = p.interest_name;
    } else {
      interestBadge.style.display = "none";
    }

    const favBtn = article.querySelector(".favorite-btn");
    updateFavBtn(favBtn, p);
    favBtn.addEventListener("click", () => toggleFav(p, favBtn));

    // ── Title ──
    const titleEl = article.querySelector(".title");
    titleEl.textContent = p.title;
    if (p.url) titleEl.href = p.url;

    // ── Meta bar: authors, date, cited, relevance ──
    const authorsText = article.querySelector(".meta-authors-text");
    const authorLine = p.author_line || (p.authors && p.authors.length > 0 ? p.authors.join(", ") : "");
    if (authorLine) {
      authorsText.textContent = authorLine.length > 60 ? authorLine.slice(0, 58) + "…" : authorLine;
      authorsText.title = authorLine; // full text on hover
    } else {
      authorsText.textContent = "未知作者";
    }

    const dateText = article.querySelector(".meta-date-text");
    const pubDate = p.published_date || p.published_at;
    if (pubDate && pubDate !== "None") {
      dateText.textContent = pubDate.slice(0, 10);
    } else {
      article.querySelector(".meta-date").style.display = "none";
      article.querySelector(".meta-dot:nth-child(4)").style.display = "none";
    }

    const citedText = article.querySelector(".meta-cited-text");
    if (p.cited_by_count && p.cited_by_count > 0) {
      citedText.textContent = `引用 ${p.cited_by_count}`;
    } else {
      article.querySelector(".meta-cited").style.display = "none";
      article.querySelector(".meta-dot:nth-child(6)").style.display = "none";
    }

    if (p.relevance && p.relevance > 0) {
      article.querySelector(".meta-rel").style.display = "flex";
      article.querySelector(".meta-rel-dot").style.display = "block";
      article.querySelector(".meta-rel-text").textContent = `相关 ${(p.relevance * 100).toFixed(0)}%`;
    }

    // ── Tags row (crawled date) ──
    const tagsEl = article.querySelector(".card-tags");
    if (p.crawled_date) {
      const tag = document.createElement("span");
      tag.className = "tag";
      tag.textContent = `抓取 ${p.crawled_date}`;
      tagsEl.appendChild(tag);
    }

    // ── Collapsible sections ──
    setupSection(article, "affiliations", p.affiliations);
    setupSection(article, "summary-cn", p.summary_cn);
    setupSection(article, "abstract", p.abstract || "无摘要");

    container.appendChild(article);
  }
}

function setupSection(article, sectionName, value) {
  const section = article.querySelector(`[data-section="${sectionName}"]`);
  if (!value || value === "None" || (Array.isArray(value) && value.length === 0)) {
    section.style.display = "none";
    return;
  }
  const toggle = section.querySelector(".section-toggle");
  const content = section.querySelector(".section-text");
  content.textContent = value;
  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
    if (!expanded) content.classList.add("expanded");
    else content.classList.remove("expanded");
  });
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

    const date = (dateMode === "published_date"
      ? (p.published_date || p.published_at || "")
      : (p.crawled_date || "")
    ).slice(0, 10);
    if (start && date < start) return false;
    if (end && date > end) return false;

    if (!kwd) return true;
    const haystack = [
      p.title, p.author_line,
      (p.authors || []).join(" "),
      p.affiliations, p.summary_cn, p.abstract,
      p.source_title, p.interest_name,
    ].join(" ").toLowerCase();
    return haystack.includes(kwd);
  });
}

// ── Favorites ─────────────────────────────────────────────────────────────────
function titleKey(p) { return `${p.title}|${p.year}`; }

function toggleFav(p, btn) {
  const k = titleKey(p);
  if (favorites.has(k)) favorites.delete(k);
  else favorites.add(k);
  localStorage.setItem(FAV_KEY, JSON.stringify([...favorites]));
  updateFavBtn(btn, p);
  render();
}

function updateFavBtn(btn, p) {
  const active = favorites.has(titleKey(p));
  btn.textContent = active ? "★" : "☆";
  btn.classList.toggle("active", active);
  btn.setAttribute("aria-label", active ? "取消收藏" : "收藏");
}

function restoreFavs() {
  // localStorage is restored at init
}

// ── Filter bindings ───────────────────────────────────────────────────────────
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

  document.getElementById("quickRange").addEventListener("click", e => {
    const btn = e.target.closest("[data-range]");
    if (!btn) return;
    const range = btn.dataset.range;
    const today = new Date().toISOString().slice(0, 10);
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

  document.getElementById("keyword").addEventListener("keydown", e => {
    if (e.key === "Enter") render();
  });

  // Favorites export modal
  document.getElementById("exportFavBtn").addEventListener("click", () => {
    const favData = [...favorites].map(k => {
      const [title, year] = k.split("|");
      return { title, year: year || null };
    });
    document.getElementById("favJson").value = JSON.stringify({ updated: new Date().toISOString().slice(0, 10), favorites: favData }, null, 2);
    document.getElementById("favModal").style.display = "flex";
  });

  document.getElementById("copyFavBtn").addEventListener("click", () => {
    navigator.clipboard.writeText(document.getElementById("favJson").value)
      .then(() => {
        const btn = document.getElementById("copyFavBtn");
        btn.textContent = "已复制 ✓";
        setTimeout(() => { btn.textContent = "复制到剪贴板"; }, 2000);
      });
  });

  document.getElementById("closeFavBtn").addEventListener("click", () => {
    document.getElementById("favModal").style.display = "none";
  });
}
