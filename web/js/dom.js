export function $(id) {
  const node = document.getElementById(id);
  if (!node) throw new Error(`Missing #${id}`);
  return node;
}

export function el(tag, attrs = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value == null || value === false) continue;
    if (key === "className") node.className = value;
    else if (key === "text") node.textContent = String(value);
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key === "attrs") {
      for (const [name, attr] of Object.entries(value)) {
        if (attr != null && attr !== false) node.setAttribute(name, String(attr));
      }
    } else if (key.startsWith("on") || key === "html" || key === "innerHTML") {
      throw new Error("Forbidden DOM binding");
    } else {
      node.setAttribute(key, value === true ? "" : String(value));
    }
  }
  const list = Array.isArray(children) ? children : [children];
  for (const child of list) {
    if (child == null || child === false) continue;
    if (typeof child === "string" || typeof child === "number") {
      node.appendChild(document.createTextNode(String(child)));
    } else {
      node.appendChild(child);
    }
  }
  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

export function announce(text) {
  const live = document.getElementById("live");
  if (!live) return;
  live.textContent = "";
  live.textContent = text;
}

export function show(node, on = true) {
  node.hidden = !on;
}

export function text(node, value) {
  node.textContent = value == null ? "" : String(value);
}

const BLOCKED_SCHEMES = /^(javascript|data|file|about|blob):/i;

export function safeHttpUrl(raw) {
  if (raw == null) return null;
  const value = String(raw).trim();
  if (!value || BLOCKED_SCHEMES.test(value)) return null;
  try {
    const url = new URL(value);
    if (url.protocol !== "http:" && url.protocol !== "https:") return null;
    return url.href;
  } catch {
    return null;
  }
}

export function resolveMediaUrl(raw, apiBase, { trusted = false } = {}) {
  if (raw == null) return null;
  const value = String(raw).trim();
  if (!value) return null;
  if (trusted && (value.startsWith("blob:") || value.startsWith("data:image/"))) return value;
  if (value.startsWith("/") && !value.startsWith("//")) {
    const base = (apiBase || "").replace(/\/$/, "");
    return `${base}${value}`;
  }
  return safeHttpUrl(value);
}

export function remoteImg(raw, alt, apiBase) {
  const img = el("img", {
    alt: alt == null ? "" : String(alt),
    referrerpolicy: "no-referrer",
    decoding: "async",
  });
  const src = resolveMediaUrl(raw, apiBase);
  if (!src) {
    img.classList.add("img-failed");
    img.alt = "Image unavailable";
    return img;
  }
  img.src = src;
  img.addEventListener("error", () => {
    img.removeAttribute("src");
    img.alt = "Image unavailable";
    img.classList.add("img-failed");
  });
  return img;
}

export function outboundLink(href, label) {
  const safe = safeHttpUrl(href);
  if (!safe) return null;
  return el(
    "a",
    {
      href: safe,
      target: "_blank",
      rel: "noopener noreferrer nofollow",
      referrerpolicy: "no-referrer",
      text: label,
    },
  );
}
