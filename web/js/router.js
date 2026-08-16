function pathFromLocation() {
  const hash = location.hash.replace(/^#/, "");
  if (hash && hash !== "/") {
    return hash.startsWith("/") ? hash : `/${hash}`;
  }
  const path = location.pathname.replace(/\/+$/, "") || "/";
  if (path.endsWith("/privacy")) return "/privacy";
  if (path.endsWith("/limitations")) return "/limitations";
  const searchAt = path.lastIndexOf("/search/");
  if (searchAt !== -1) return path.slice(searchAt);
  const params = new URLSearchParams(location.search);
  if (params.get("search")) {
    const result = params.get("result");
    return result ? `/search/${params.get("search")}/result/${result}` : `/search/${params.get("search")}`;
  }
  return "/";
}

export function parseRoute(path) {
  const clean = path.replace(/\/+$/, "") || "/";
  if (clean === "/" || clean === "/index.html") return { name: "home" };
  if (clean === "/privacy") return { name: "privacy" };
  if (clean === "/limitations") return { name: "limitations" };
  const parts = clean.split("/").filter(Boolean);
  if (parts[0] === "search" && parts[1]) {
    if (parts[2] === "result" && parts[3]) {
      return { name: "result", searchId: parts[1], resultId: parts[3] };
    }
    return { name: "search", searchId: parts[1] };
  }
  return { name: "home" };
}

export function currentRoute() {
  return parseRoute(pathFromLocation());
}

export function searchHash(searchId, resultId) {
  return resultId ? `#/search/${searchId}/result/${resultId}` : `#/search/${searchId}`;
}

export function go(searchId, resultId) {
  const next = searchHash(searchId, resultId);
  if (location.hash !== next) location.hash = next;
}

export function goHome() {
  if (location.hash !== "#/" && location.hash !== "") location.hash = "#/";
}

export function onRoute(handler) {
  const fire = () => handler(currentRoute());
  window.addEventListener("hashchange", fire);
  window.addEventListener("popstate", fire);
  return fire;
}
