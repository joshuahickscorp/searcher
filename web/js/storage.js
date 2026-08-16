const RECENT_KEY = "searcher.recent";
const DEV_KEY = "searcher.devMode";
const TAB_KEY = "searcher.tab";

function readJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch {
    return fallback;
  }
}

export function loadRecent() {
  const rows = readJson(RECENT_KEY, []);
  return Array.isArray(rows) ? rows.slice(0, 12) : [];
}

export function rememberSearch(entry) {
  const next = [
    {
      id: entry.id,
      text: String(entry.text || "").slice(0, 120),
      tags: Array.isArray(entry.tags) ? entry.tags.slice(0, 8) : [],
      at: entry.at || new Date().toISOString(),
    },
    ...loadRecent().filter((row) => row.id !== entry.id),
  ].slice(0, 12);
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    /* ignore quota */
  }
  return next;
}

export function forgetSearch(id) {
  const next = loadRecent().filter((row) => row.id !== id);
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(next));
  } catch {
    /* ignore */
  }
  return next;
}

export function loadDevMode() {
  return localStorage.getItem(DEV_KEY) === "1";
}

export function saveDevMode(on) {
  localStorage.setItem(DEV_KEY, on ? "1" : "0");
}

export function loadTab() {
  return localStorage.getItem(TAB_KEY) === "possibly_real" ? "possibly_real" : "real";
}

export function saveTab(tab) {
  localStorage.setItem(TAB_KEY, tab);
}
