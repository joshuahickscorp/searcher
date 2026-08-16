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
  "No displayable candidate within this search’s current source and budget coverage.";
