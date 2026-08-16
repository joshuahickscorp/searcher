import { $ } from "./dom.js";

const KEY = "searcher.sourceScopes";
export const SCOPE_LEGITIMATE = "legitimate";
export const SCOPE_REPLICA = "replica";

export function defaultScopes() {
  return { legitimate: true, replica: false };
}

export function parseScopesParam(raw) {
  const parts = String(raw ?? "")
    .split(",")
    .map((part) => part.trim().toLowerCase())
    .filter(Boolean);
  return {
    legitimate: parts.includes(SCOPE_LEGITIMATE),
    replica: parts.includes(SCOPE_REPLICA),
  };
}

export function scopesToParam(scopes) {
  const parts = [];
  if (scopes.legitimate) parts.push(SCOPE_LEGITIMATE);
  if (scopes.replica) parts.push(SCOPE_REPLICA);
  return parts.join(",");
}

export function selectedScopeList(scopes) {
  const list = [];
  if (scopes.legitimate) list.push(SCOPE_LEGITIMATE);
  if (scopes.replica) list.push(SCOPE_REPLICA);
  return list;
}

function readStored() {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const data = JSON.parse(raw);
    if (!data || typeof data !== "object") return null;
    return {
      legitimate: data.legitimate !== false,
      replica: data.replica === true,
    };
  } catch {
    return null;
  }
}

function writeStored(scopes) {
  try {
    localStorage.setItem(
      KEY,
      JSON.stringify({
        legitimate: Boolean(scopes.legitimate),
        replica: Boolean(scopes.replica),
      }),
    );
  } catch {
    /* quota */
  }
}

function scopesFromUrl() {
  const params = new URLSearchParams(location.search);
  if (!params.has("scopes")) return null;
  return parseScopesParam(params.get("scopes"));
}

function writeScopesUrl(scopes) {
  const url = new URL(location.href);
  url.searchParams.set("scopes", scopesToParam(scopes));
  const next = `${url.pathname}${url.search}${url.hash}`;
  const current = `${location.pathname}${location.search}${location.hash}`;
  if (current !== next) history.replaceState(null, "", next);
}

function resolveInitial() {
  return scopesFromUrl() || readStored() || defaultScopes();
}

export function createScopeControl({ onChange } = {}) {
  const legitimate = $("scope-legitimate");
  const replica = $("scope-replica");
  let state = resolveInitial();

  function apply(next) {
    state = {
      legitimate: Boolean(next.legitimate),
      replica: Boolean(next.replica),
    };
    legitimate.checked = state.legitimate;
    replica.checked = state.replica;
    writeStored(state);
    writeScopesUrl(state);
    if (typeof onChange === "function") onChange(state);
  }

  legitimate.addEventListener("change", () => {
    apply({ legitimate: legitimate.checked, replica: replica.checked });
  });
  replica.addEventListener("change", () => {
    apply({ legitimate: legitimate.checked, replica: replica.checked });
  });

  apply(state);
  return {
    get() {
      return { ...state };
    },
    list() {
      return selectedScopeList(state);
    },
    replicaOn() {
      return state.replica;
    },
  };
}
