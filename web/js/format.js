export const STAGES = [
  "Understanding the item",
  "Reading visible labels",
  "Building possible identities",
  "Searching exact names",
  "Searching alternate names",
  "Searching international sources",
  "Comparing candidate images",
  "Checking detail consistency",
  "Checking listing authenticity evidence",
  "Verifying live links",
  "Ranking results",
];

const STATE_STAGE = {
  CREATED: "Understanding the item",
  VALIDATING_INPUT: "Understanding the item",
  INGESTING_REFERENCES: "Understanding the item",
  CALIBRATING_REFERENCES: "Understanding the item",
  DECOMPOSING_REFERENCES: "Reading visible labels",
  FORMING_HYPOTHESES: "Building possible identities",
  PLANNING_QUERIES: "Searching exact names",
  PLANNING_SOURCES: "Searching international sources",
  DISCOVERING: "Searching international sources",
  ACQUIRING: "Comparing candidate images",
  NORMALIZING: "Comparing candidate images",
  DEDUPLICATING: "Comparing candidate images",
  BROAD_RETRIEVAL: "Comparing candidate images",
  FINE_MATCHING: "Checking detail consistency",
  AUTHENTICITY_REVIEW: "Checking listing authenticity evidence",
  LIVE_CHECKING: "Verifying live links",
  RANKING: "Ranking results",
  PUBLISHING: "Ranking results",
  GAP_ANALYSIS: "Ranking results",
  REPLANNING: "Searching alternate names",
};

export function stageFromState(state, fallback) {
  if (fallback) return fallback;
  return STATE_STAGE[state] || null;
}

export function relativeTime(iso) {
  if (!iso) return "check time not provided";
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return String(iso);
  const delta = Date.now() - then;
  const sec = Math.round(delta / 1000);
  if (Math.abs(sec) < 45) return "just now";
  const min = Math.round(sec / 60);
  if (Math.abs(min) < 60) return min === 1 ? "1 minute ago" : `${min} minutes ago`;
  const hr = Math.round(min / 60);
  if (Math.abs(hr) < 36) return hr === 1 ? "1 hour ago" : `${hr} hours ago`;
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(then));
  } catch {
    return String(iso);
  }
}

export function availabilityLine(result) {
  const status = String(result.availability || "").toUpperCase();
  const words = {
    LIVE: "Live",
    SOLD: "Sold",
    RESERVED: "Reserved",
    REMOVED: "Removed",
    UNKNOWN: "Availability unknown",
  };
  const word = words[status] || "Availability unknown";
  if (!result.last_checked_at) return `${word} — never checked`;
  return `${word} — checked ${relativeTime(result.last_checked_at)}`;
}

export function priceLine(price) {
  if (!price) return "Price not provided";
  if (price.display) return String(price.display);
  if (price.original && price.currency) return `${price.currency} ${price.original}`;
  if (price.original) return String(price.original);
  return "Price not provided";
}

export function sizeLine(size) {
  if (!size) return "Size not provided";
  if (size.display) return String(size.display);
  if (size.marked) return `Size ${size.marked}`;
  return "Size not provided";
}

export function interval(block) {
  if (!block) return "";
  const lo = block.lower_bound;
  const hi = block.upper_bound;
  const mean = block.mean;
  const bits = [];
  if (mean != null) bits.push(`mean ${mean}`);
  if (lo != null && hi != null) bits.push(`${lo}–${hi}`);
  return bits.join(", ");
}

export function missingOr(value, fallback = "Not provided by the search service.") {
  if (value == null) return fallback;
  if (Array.isArray(value) && value.length === 0) return fallback;
  if (typeof value === "string" && !value.trim()) return fallback;
  return value;
}

export const REAL_SUBTITLE =
  "High confidence this is the same item under the current evidence — not a professional authentication guarantee.";

export const POSSIBLE_SUBTITLE =
  "May be the same item; evidence is missing or conflicting.";

export const REPLICA_SUBTITLE =
  "From replica sources. A replica listing can never be ranked Real.";

export const NO_REAL =
  "No candidate met the Real threshold yet.";

export const NO_CANDIDATES =
  "Searcher did not find a displayable candidate within this search’s current source and budget coverage.";

export const FEEDBACK_THIS_IS_THE_ONE = {
  verdict: "correct_item",
  label: "This is the one",
};

export const FEEDBACK_THIS_IS_NOT_IT = {
  verdict: "wrong_model",
  label: "This is not it",
};

export function firstMissingView(search) {
  const rows = Array.isArray(search && search.missing_reference_views)
    ? search.missing_reference_views
    : [];
  for (const row of rows) {
    if (!row) continue;
    if (typeof row === "string" && row.trim()) return { view: row.trim(), why: "" };
    if (row.view || row.why) return row;
  }
  return null;
}

export function nextInputFromMissing(search) {
  const first = firstMissingView(search);
  if (!first) return null;
  const view = String(first.view || "").trim();
  const why = String(first.why || "").trim();
  const action = view
    ? `Add a photograph of the ${view}.`
    : "Add the missing photograph the search named.";
  const rest = (Array.isArray(search.missing_reference_views) ? search.missing_reference_views : [])
    .slice(1)
    .map((row) => {
      if (!row) return "";
      if (typeof row === "string") return row;
      const name = String(row.view || "").trim();
      const reason = String(row.why || "").trim();
      if (name && reason) return `${name} — ${reason}`;
      return name || reason;
    })
    .filter(Boolean);
  return { view, why, action, rest };
}

export function whyLeadText(result) {
  const why = result && result.why;
  if (!why) return "";
  if (why.tab_reason && String(why.tab_reason).trim()) return String(why.tab_reason).trim();
  if (Array.isArray(why.points) && why.points.length && String(why.points[0]).trim()) {
    return String(why.points[0]).trim();
  }
  return "";
}

export function whyHeadingText(result) {
  const heading = result && result.why && result.why.heading;
  return heading ? String(heading).trim() : "";
}

export function formatElapsed(ms) {
  if (ms == null || !Number.isFinite(ms) || ms < 0) return "";
  const sec = Math.floor(ms / 1000);
  const minutes = Math.floor(sec / 60);
  const seconds = sec % 60;
  if (minutes <= 0) return `${seconds}s`;
  return `${minutes}m ${String(seconds).padStart(2, "0")}s`;
}

export function stageStepLabel(stage) {
  const idx = STAGES.indexOf(stage);
  if (idx === -1) return "";
  return `Stage ${idx + 1} of ${STAGES.length}`;
}

export function coverageStatsLine(coverage, activity) {
  const cov = coverage || {};
  const completed = Array.isArray(cov.sources_completed) ? cov.sources_completed.length : 0;
  const blocked = Array.isArray(cov.sources_blocked) ? cov.sources_blocked.length : 0;
  const running = Array.isArray(cov.sources_in_progress) ? cov.sources_in_progress.length : 0;
  const pages = cov.pages_fetched;
  const normalized = cov.candidates_normalized;
  const seen = Math.max(
    Number(normalized) || 0,
    (activity && activity.normalized) || 0,
    (activity && activity.discovered) || 0,
  );
  const parts = [];
  if (completed) parts.push(`${completed} source${completed === 1 ? "" : "s"} searched`);
  if (running) parts.push(`${running} in progress`);
  if (blocked) parts.push(`${blocked} blocked`);
  if (pages != null && pages > 0) parts.push(`${pages} page${pages === 1 ? "" : "s"}`);
  if (seen > 0) parts.push(`${seen} listing${seen === 1 ? "" : "s"} seen`);
  return parts.join(" · ");
}

export function sourcesInProgress(coverage) {
  const rows = coverage && Array.isArray(coverage.sources_in_progress)
    ? coverage.sources_in_progress
    : [];
  return rows
    .map((row) => (row && (row.name || row.id || row.detail)) || "")
    .map((name) => String(name).trim())
    .filter(Boolean);
}

export function terminalStatusLabel(status) {
  const words = {
    COMPLETE: "Finished",
    PARTIAL: "Finished with incomplete coverage",
    BLOCKED: "Blocked",
    FAILED: "Failed",
    CANCELLED: "Cancelled",
  };
  return words[status] || status || "";
}
