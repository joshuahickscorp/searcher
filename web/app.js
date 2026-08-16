import { API_BASE as CONFIG_API_BASE } from "./config.js";
import { createApi } from "./js/api.js";
import { createCompare } from "./js/compare.js";
import { $, announce, show, text } from "./js/dom.js";
import { createForm } from "./js/form.js";
import { createResults } from "./js/results.js";
import { currentRoute, go, goHome, onRoute } from "./js/router.js";
import { createScopeControl } from "./js/scopes.js";
import { forgetSearch, loadDevMode, loadTab, rememberSearch, saveDevMode, saveTab } from "./js/storage.js";

const params = new URLSearchParams(location.search);
const apiOverride = params.get("api");
let apiBase = (apiOverride || CONFIG_API_BASE || "").replace(/\/$/, "");
const initialDev = params.get("dev") === "1" || loadDevMode();

const api = createApi(() => apiBase);
const banner = $("api-banner");
const viewHome = $("view-home");
const viewPrivacy = $("view-privacy");
const viewLimitations = $("view-limitations");
const devToggle = $("dev-mode");

let currentSearchId = null;
let currentSearch = null;
let stream = null;
let healthFails = 0;
let compareOpener = null;

function setApiBase(next) {
  apiBase = String(next || "").replace(/\/$/, "");
}

function setBanner(message) {
  if (message) {
    text(banner, message);
    show(banner, true);
  } else {
    show(banner, false);
    text(banner, "");
  }
}

function setView(name) {
  show(viewHome, name === "home" || name === "search" || name === "result");
  show(viewPrivacy, name === "privacy");
  show(viewLimitations, name === "limitations");
}

function applyDev(on) {
  document.body.classList.toggle("dev-on", on);
  devToggle.checked = on;
  saveDevMode(on);
}

devToggle.addEventListener("change", () => applyDev(devToggle.checked));
applyDev(initialDev);

function clientSearchId() {
  if (crypto && crypto.randomUUID) return crypto.randomUUID();
  return `c-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

let pollTimer = null;

function closeStream() {
  if (stream) {
    stream.close();
    stream = null;
  }
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

async function checkHealth() {
  try {
    await api.health();
    healthFails = 0;
    setBanner("");
    return true;
  } catch {
    healthFails += 1;
    return false;
  }
}

function markUnavailable() {
  setBanner("The search service is unavailable. Searcher cannot start or update a search until the service responds.");
  results.setStream("The search service is unavailable.");
  announce("The search service is unavailable.");
}

function attachStream(searchId) {
  closeStream();
  pollTimer = setInterval(async () => {
    if (searchId !== currentSearchId) return;
    try {
      const search = await api.getSearch(searchId);
      currentSearch = { ...currentSearch, ...search };
      results.setSearch(search);
      if (search.terminal_status) {
        form.setBusy(false);
        try {
          const payload = await api.getResults(searchId);
          results.loadResults(payload);
        } catch {
          /* already have stream cards */
        }
        closeStream();
      }
    } catch (err) {
      if (err.code === "unavailable") markUnavailable();
    }
  }, 1500);
  stream = api.openEvents(searchId, {
    onOpen() {
      healthFails = 0;
      results.setStream("");
    },
    async onError() {
      if (currentSearch && currentSearch.terminal_status) {
        // The server closes the stream once the campaign stops. That is the end
        // of the search, not a lost connection.
        closeStream();
        results.setStream("");
        return;
      }
      results.setStream("The live update connection dropped. Reconnecting…");
      const ok = await checkHealth();
      if (!ok && healthFails >= 2) markUnavailable();
    },
    onEvent(name, data) {
      handleEvent(name, data);
    },
  });
}

function handleEvent(name, data) {
  if (!currentSearch) currentSearch = { search_id: currentSearchId, counts: { real: 0, possibly_real: 0, hidden: 0 } };

  if (name === "search.state") {
    currentSearch.state = data.state;
    currentSearch.state_version = data.version;
    results.setSearch(currentSearch);
  } else if (name === "search.progress") {
    currentSearch.progress = { stage: data.stage, detail: data.detail };
    results.setSearch(currentSearch);
    results.announceStage(data.stage);
  } else if (name === "search.coverage") {
    currentSearch.coverage = data;
    results.setSearch(currentSearch);
  } else if (name === "result.real" || name === "result.possibly_real" || name === "result.replica") {
    const bucket = name === "result.real"
      ? "real"
      : name === "result.replica"
        ? "replica"
        : "possibly_real";
    results.upsertResult(data, bucket);
    const counts = currentSearch.counts || { real: 0, possibly_real: 0, hidden: 0 };
    const other = bucket === "real" ? "possibly_real" : "real";
    counts[bucket] = (counts[bucket] || 0);
    if (data.result_id) {
      /* counts refreshed from paint via upsert; keep a running lower bound */
      counts[bucket] = Math.max(counts[bucket], 0);
    }
    currentSearch.counts = counts;
    void other;
  } else if (name === "result.removed") {
    results.removeResult(data.result_id);
    if (currentSearch.counts) {
      currentSearch.counts.hidden = (currentSearch.counts.hidden || 0) + 1;
      currentSearch.hidden_policy_note = currentSearch.hidden_policy_note || "Some candidates did not meet policy.";
    }
    results.setSearch(currentSearch);
    if (compare.isOpen() && lastCompared === data.result_id) compare.close();
  } else if (name === "search.warning") {
    results.setWarning(data.message || "The search reported a warning.");
  } else if (name === "search.complete") {
    currentSearch.terminal_status = data.terminal_status;
    currentSearch.terminal_reason = data.reason;
    currentSearch.state = data.terminal_status || currentSearch.state;
    results.setSearch(currentSearch);
    form.setBusy(false);
    announce("Search finished.");
  }
}

let lastCompared = null;

async function openCompare(result, opener) {
  compareOpener = opener || null;
  lastCompared = result.result_id;
  let full = result;
  if (!result.compare || !result.why) {
    try {
      full = await api.getResult(result.result_id);
    } catch {
      full = result;
    }
  }
  compare.open(full);
  go(currentSearchId, result.result_id);
}

const compare = createCompare({
  apiBase: () => apiBase,
  onClose() {
    const route = currentRoute();
    if (route.name === "result" && currentSearchId) go(currentSearchId);
    if (compareOpener) {
      compareOpener.focus();
      compareOpener = null;
    }
  },
});

let scopes;
const results = createResults({
  apiBase: () => apiBase,
  replicaScope: () => Boolean(scopes && scopes.replicaOn()),
  onCompare: openCompare,
  async onCancel() {
    if (!currentSearchId) return;
    try {
      const next = await api.cancel(currentSearchId);
      currentSearch = next;
      results.setSearch(next);
      announce("Search cancelled.");
    } catch (err) {
      if (err.code === "unavailable") markUnavailable();
    }
  },
  async onDelete() {
    if (!currentSearchId) return;
    try {
      await api.deleteSearch(currentSearchId);
      forgetSearch(currentSearchId);
      form.renderRecent();
      closeStream();
      results.reset();
      results.close();
      currentSearchId = null;
      currentSearch = null;
      goHome();
      announce("Search deleted.");
    } catch (err) {
      if (err.code === "unavailable") markUnavailable();
      else if (err.code === "not_found") {
        results.reset();
        results.close();
        goHome();
      }
    }
  },
  onClose() {
    results.close();
  },
  onTab(tab) {
    saveTab(tab);
  },
});

scopes = createScopeControl({
  onChange() {
    results.syncReplicaScope();
  },
});

function buildSearchForm({ files, text, tags, clientId, includeScopes }) {
  const fd = new FormData();
  for (const file of files) fd.append("images", file, file.name);
  fd.append("text", text);
  for (const tag of tags) fd.append("tags", tag);
  fd.append("client_search_id", clientId);
  if (includeScopes) {
    for (const scope of scopes.list()) fd.append("source_scopes", scope);
  }
  return fd;
}

async function createSearchSafe({ files, text, tags }) {
  const clientId = clientSearchId();
  try {
    return await api.createSearch(buildSearchForm({
      files,
      text,
      tags,
      clientId,
      includeScopes: true,
    }));
  } catch (err) {
    if (err.code === "unavailable") throw err;
    return api.createSearch(buildSearchForm({
      files,
      text,
      tags,
      clientId,
      includeScopes: false,
    }));
  }
}

const form = createForm({
  async onSubmit({ files, text: known, tags }) {
    setBanner("");
    form.setBusy(true);
    try {
      const created = await createSearchSafe({ files, text: known, tags });
      rememberSearch({
        id: created.search_id,
        text: known,
        tags,
        at: created.created_at,
      });
      form.renderRecent();
      go(created.search_id);
      await openSearch(created.search_id, { created });
    } catch (err) {
      form.setBusy(false);
      if (err.code === "unavailable") markUnavailable();
      else announce(err.message || "Search could not be started.");
      const imageError = $("image-error");
      imageError.hidden = false;
      imageError.textContent = err.message || "Search could not be started.";
    }
  },
});

async function openSearch(searchId, { created = null, resultId = null } = {}) {
  currentSearchId = searchId;
  results.reset();
  results.open();
  results.setTab(resultId ? loadTab() : "real");
  form.setBusy(true);
  try {
    const search = created || await api.getSearch(searchId);
    currentSearch = search;
    results.setSearch(search);
    try {
      const payload = await api.getResults(searchId);
      results.loadResults(payload);
    } catch {
      /* stream may still fill cards */
    }
    if (!search.terminal_status) attachStream(searchId);
    else form.setBusy(false);
    if (resultId) {
      let result = results.getResult(resultId);
      if (!result) {
        try {
          result = await api.getResult(resultId);
          results.upsertResult(result, result.bucket);
        } catch {
          result = null;
        }
      }
      if (result) await openCompare(result);
    }
  } catch (err) {
    form.setBusy(false);
    results.open();
    if (err.code === "not_found") {
      results.setStream("This search is no longer available. It may have been deleted.");
      announce("This search is no longer available.");
    } else {
      markUnavailable();
    }
  }
}

function syncRoute(route) {
  if (route.name === "privacy" || route.name === "limitations") {
    setView(route.name);
    results.close();
    if (compare.isOpen()) compare.close();
    document.title = route.name === "privacy" ? "Privacy — SEARCHER" : "Limitations — SEARCHER";
    return;
  }
  setView("home");
  document.title = "SEARCHER";
  if (route.name === "search" || route.name === "result") {
    if (route.searchId !== currentSearchId) {
      openSearch(route.searchId, { resultId: route.resultId || null });
    } else if (route.name === "result" && route.resultId) {
      const result = results.getResult(route.resultId);
      if (result && !compare.isOpen()) openCompare(result);
    } else if (route.name === "search" && compare.isOpen()) {
      compare.close();
    }
    if (!results.isOpen()) results.open();
  }
}

$("home-link").addEventListener("click", (ev) => {
  ev.preventDefault();
  goHome();
  setView("home");
});

const fireRoute = onRoute(syncRoute);

(async function boot() {
  if (apiOverride) setApiBase(apiOverride);
  const ok = await checkHealth();
  if (!ok) {
    setBanner("The search service is unavailable. Set a working ?api= address if this page is not served by the search service.");
  }
  fireRoute();
})();
