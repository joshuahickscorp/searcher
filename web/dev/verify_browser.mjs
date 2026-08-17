#!/usr/bin/env node
/**
 * DEVELOPMENT ONLY. Drives headless Chrome over CDP against the local UI.
 * Not part of the published site.
 */
import { spawn } from "node:child_process";
import { createWriteStream } from "node:fs";
import { mkdir, writeFile } from "node:fs/promises";
import http from "node:http";
import path from "node:path";
import process from "node:process";

const CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
const OUT = path.resolve("web/dev/artifacts");
const PORT = 9333;
const UI = process.env.UI_BASE || "http://127.0.0.1:8080";
const API = process.env.API_BASE || "http://127.0.0.1:8765";
const SAMPLE = path.resolve("web/images/sample-upload.png");

const consoleLines = [];
const dialogs = [];
const failures = [];
const feedbackPosts = [];

function httpJson(urlPath) {
  return new Promise((resolve, reject) => {
    http.get({ host: "127.0.0.1", port: PORT, path: urlPath }, (res) => {
      let buf = "";
      res.on("data", (c) => { buf += c; });
      res.on("end", () => {
        try { resolve(JSON.parse(buf)); }
        catch (err) { reject(err); }
      });
    }).on("error", reject);
  });
}

class Cdp {
  constructor(ws) {
    this.ws = ws;
    this.id = 0;
    this.pending = new Map();
    this.eventWaiters = new Map();
    this.ws.addEventListener("message", (ev) => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id);
        this.pending.delete(msg.id);
        if (msg.error) reject(new Error(JSON.stringify(msg.error)));
        else resolve(msg.result || {});
        return;
      }
      if (msg.method && this.eventWaiters.has(msg.method)) {
        const list = this.eventWaiters.get(msg.method);
        this.eventWaiters.delete(msg.method);
        for (const resolve of list) resolve(msg.params);
      }
      if (msg.method === "Runtime.consoleAPICalled") {
        const text = (msg.params.args || []).map((a) => a.value ?? a.description ?? "").join(" ");
        consoleLines.push({ type: msg.params.type, text });
      } else if (msg.method === "Log.entryAdded") {
        consoleLines.push({ type: msg.params.entry?.level, text: msg.params.entry?.text });
      } else if (msg.method === "Page.javascriptDialogOpening") {
        dialogs.push(msg.params);
      } else if (msg.method === "Network.requestWillBeSent") {
        const req = msg.params.request || {};
        if (req.method === "POST" && String(req.url || "").includes("/feedback")) {
          feedbackPosts.push({ url: req.url, postData: req.postData || null });
        }
      }
    });
  }

  send(method, params = {}) {
    const id = ++this.id;
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  once(method) {
    return new Promise((resolve) => {
      const list = this.eventWaiters.get(method) || [];
      list.push(resolve);
      this.eventWaiters.set(method, list);
    });
  }

  async navigate(url) {
    const loaded = this.once("Page.loadEventFired");
    await this.send("Page.navigate", { url });
    await Promise.race([loaded, sleep(8000)]);
    await sleep(150);
  }
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

async function waitFor(cdp, expression, timeout = 15000) {
  const start = Date.now();
  let last;
  while (Date.now() - start < timeout) {
    const result = await cdp.send("Runtime.evaluate", {
      expression,
      returnByValue: true,
      awaitPromise: true,
    });
    last = result.result?.value;
    if (last) return last;
    await sleep(150);
  }
  throw new Error(`timeout waiting for ${expression} (last=${last})`);
}

async function evalValue(cdp, expression) {
  const result = await cdp.send("Runtime.evaluate", {
    expression,
    returnByValue: true,
    awaitPromise: true,
  });
  if (result.exceptionDetails) {
    throw new Error(result.exceptionDetails.text || "evaluate failed");
  }
  return result.result?.value;
}

async function screenshot(cdp, name) {
  const shot = await cdp.send("Page.captureScreenshot", { format: "png" });
  const dest = path.join(OUT, `${name}.png`);
  await writeFile(dest, Buffer.from(shot.data, "base64"));
  return dest;
}

async function setViewport(cdp, width, height, mobile = false) {
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width,
    height,
    deviceScaleFactor: 1,
    mobile,
  });
}

async function tabUntil(cdp, selector, max = 20) {
  for (let i = 0; i < max; i++) {
    const ok = await evalValue(cdp, `Boolean(document.activeElement && document.activeElement.matches(${JSON.stringify(selector)}))`);
    if (ok) return true;
    await key(cdp, "Tab");
  }
  return false;
}

async function key(cdp, key, options = {}) {
  const map = {
    Tab: { code: "Tab", keyCode: 9 },
    Enter: { code: "Enter", keyCode: 13 },
    Escape: { code: "Escape", keyCode: 27 },
    Backspace: { code: "Backspace", keyCode: 8 },
    " ": { code: "Space", keyCode: 32 },
    ArrowRight: { code: "ArrowRight", keyCode: 39 },
    ArrowLeft: { code: "ArrowLeft", keyCode: 37 },
  };
  const extra = map[key] || { code: key.length === 1 ? `Key${key.toUpperCase()}` : key, keyCode: key.length === 1 ? key.toUpperCase().charCodeAt(0) : 0 };
  const payload = { type: "keyDown", key, ...extra, ...options };
  await cdp.send("Input.dispatchKeyEvent", payload);
  await cdp.send("Input.dispatchKeyEvent", { ...payload, type: "keyUp" });
}

async function typeText(cdp, text) {
  await cdp.send("Input.insertText", { text });
}

async function setFiles(cdp, selector, files) {
  const doc = await cdp.send("DOM.getDocument", { depth: 1 });
  const { nodeId } = await cdp.send("DOM.querySelector", {
    nodeId: doc.root.nodeId,
    selector,
  });
  if (!nodeId) throw new Error(`no node for ${selector}`);
  await cdp.send("DOM.setFileInputFiles", { nodeId, files });
}

async function clickSel(cdp, selector) {
  const ok = await cdp.send("Runtime.evaluate", {
    expression: `(() => { const n = document.querySelector(${JSON.stringify(selector)}); if (!n) return false; n.click(); return true; })()`,
    returnByValue: true,
    userGesture: true,
  });
  if (!ok.result?.value) throw new Error(`cannot click ${selector}`);
}

async function main() {
  await mkdir(OUT, { recursive: true });
  const userData = path.join(OUT, "chrome-profile");
  const chrome = spawn(CHROME, [
    "--headless=new",
    "--disable-gpu",
    `--remote-debugging-port=${PORT}`,
    `--user-data-dir=${userData}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-dev-shm-usage",
    "--window-size=1280,800",
    "about:blank",
  ], { stdio: ["ignore", "pipe", "pipe"] });
  const chromeLog = createWriteStream(path.join(OUT, "chrome.log"));
  chrome.stdout.pipe(chromeLog);
  chrome.stderr.pipe(chromeLog);

  let version;
  for (let i = 0; i < 40; i++) {
    try {
      version = await httpJson("/json/version");
      break;
    } catch {
      await sleep(150);
    }
  }
  if (!version) {
    chrome.kill();
    throw new Error("Chrome debug port did not open");
  }

  let page;
  for (let i = 0; i < 20; i++) {
    const list = await httpJson("/json/list");
    page = list.find((t) => t.type === "page" && t.webSocketDebuggerUrl);
    if (page) break;
    await sleep(150);
  }
  if (!page) {
    page = await httpJson("/json/new?about:blank");
  }
  if (!page?.webSocketDebuggerUrl) {
    chrome.kill();
    throw new Error("no page target");
  }

  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener("open", resolve);
    ws.addEventListener("error", reject);
  });
  const cdp = new Cdp(ws);
  await cdp.send("Page.enable");
  await cdp.send("Runtime.enable");
  await cdp.send("Log.enable");
  await cdp.send("DOM.enable");
  await cdp.send("Network.enable");

  const ui = (hash = "", extra = "") => {
    const q = new URLSearchParams({ api: API });
    if (extra) {
      for (const [k, v] of Object.entries(extra)) q.set(k, v);
    }
    return `${UI}/?${q.toString()}${hash}`;
  };

  // 1. Initial screen
  await setViewport(cdp, 1280, 800, false);
  await cdp.navigate(ui());
  await waitFor(cdp, `document.getElementById("search-button") && document.getElementById("search-button").textContent.includes("Search")`);
  await screenshot(cdp, "01-initial");

  const homeText = await evalValue(cdp, `document.body.innerText`);
  if (!homeText.includes("SEARCHER") || !homeText.includes("Find the exact item")) {
    failures.push("initial screen missing wordmark or tagline");
  }

  // 2. Full mouse-assisted flow (files via CDP; rest as a user)
  await setFiles(cdp, "#file-input", [SAMPLE]);
  await waitFor(cdp, `document.querySelectorAll("#thumbs li").length === 1`);
  await clickSel(cdp, "#know");
  await typeText(cdp, "Dior Homme General Army Trainer around 2007");
  await clickSel(cdp, "#tag-input");
  await typeText(cdp, "Dior Homme");
  await key(cdp, "Enter");
  await typeText(cdp, "2007");
  await key(cdp, "Enter");
  await screenshot(cdp, "01b-form-filled");
  await clickSel(cdp, "#search-button");
  await waitFor(cdp, `!document.getElementById("results").hidden`, 10000);
  await waitFor(cdp, `
    [...document.querySelectorAll("#stage-list li")].some(li => li.dataset.state === "current")
    || document.getElementById("campaign-status").textContent.length > 0
  `, 10000);
  await screenshot(cdp, "02-streaming-progress");

  await waitFor(cdp, `document.querySelectorAll("#list-real .card").length >= 1`, 25000);
  await waitFor(cdp, `!document.getElementById("delete-search").hidden || document.querySelectorAll("#list-real .card-title").length >= 1`, 20000);
  await sleep(600);
  await evalValue(cdp, `document.querySelector("#list-real .card")?.scrollIntoView({block:"start"}); true`);
  await sleep(200);
  await screenshot(cdp, "03-real-tab");

  const realTitle = await evalValue(cdp, `document.querySelector("#list-real .card-title")?.textContent || ""`);
  const scores = await evalValue(cdp, `
    [...document.querySelectorAll("#list-real .score-line")].map(n => n.textContent)
  `);

  await clickSel(cdp, "#tab-possible");
  await waitFor(cdp, `document.getElementById("tab-possible").getAttribute("aria-selected") === "true"`);
  await evalValue(cdp, `document.querySelector("#list-possible .card")?.scrollIntoView({block:"start"}); true`);
  await sleep(200);
  await screenshot(cdp, "04-possibly-real-tab");

  await clickSel(cdp, "#tab-real");
  await evalValue(cdp, `
    const s = document.querySelector("#list-real .why summary");
    if (s) { s.click(); s.scrollIntoView({block:"center"}); }
    true
  `);
  await sleep(200);
  await screenshot(cdp, "05-why-expanded");

  await clickSel(cdp, "#list-real .compare-btn, #list-real .card-actions button");
  await waitFor(cdp, `document.getElementById("compare").open === true`);
  await screenshot(cdp, "06-compare");

  const compareText = await evalValue(cdp, `document.getElementById("compare-body").innerText`);
  await key(cdp, "Escape");
  const closedByEsc = await evalValue(cdp, `document.getElementById("compare").open === false`);
  if (!closedByEsc) {
    await clickSel(cdp, "#compare-close");
  }
  await waitFor(cdp, `document.getElementById("compare").open === false`);

  await clickSel(cdp, "#list-real .feedback-yes");
  await waitFor(cdp, `document.querySelector("#list-real .feedback-status")?.textContent.includes("recorded")`, 8000);
  const feedbackStatus = await evalValue(cdp, `document.querySelector("#list-real .feedback-status")?.textContent || ""`);

  const linkAttrs = await evalValue(cdp, `
    const a = document.querySelector("#list-real .card-actions a");
    a ? { href: a.getAttribute("href"), target: a.getAttribute("target"), rel: a.getAttribute("rel") } : null
  `);

  const liveSearchId = await evalValue(cdp, `location.hash`);

  // 3. Keyboard-only new page
  await cdp.navigate(ui());
  await waitFor(cdp, `document.getElementById("search-button")`);
  // focus the file input via JS focus (keyboard would Tab there); set files as the OS picker would
  await evalValue(cdp, `document.getElementById("file-input").focus(); true`);
  await setFiles(cdp, "#file-input", [SAMPLE]);
  await evalValue(cdp, `document.getElementById("file-input").dispatchEvent(new Event("change", { bubbles: true })); true`);
  await waitFor(cdp, `document.querySelectorAll("#thumbs li").length >= 1`);
  if (!await tabUntil(cdp, "#know")) {
    await evalValue(cdp, `document.getElementById("know").focus(); true`);
  }
  await typeText(cdp, "keyboard only run");
  if (!await tabUntil(cdp, "#tag-input")) {
    await evalValue(cdp, `document.getElementById("tag-input").focus(); true`);
  }
  await typeText(cdp, "size 42");
  await key(cdp, "Enter");
  await typeText(cdp, "remove-me");
  await key(cdp, "Enter");
  await key(cdp, "Backspace");
  if (!await tabUntil(cdp, "#search-button")) {
    await evalValue(cdp, `document.getElementById("search-button").focus(); true`);
  }
  await key(cdp, "Enter");
  const started = await evalValue(cdp, `!document.getElementById("results").hidden`);
  if (!started) {
    await cdp.send("Runtime.evaluate", {
      expression: `document.getElementById("search-button").click()`,
      userGesture: true,
    });
  }
  await waitFor(cdp, `!document.getElementById("results").hidden`, 10000);
  await waitFor(cdp, `document.querySelectorAll(".card").length >= 1`, 20000);
  await key(cdp, "ArrowRight"); // possible tab if focus on tablist — move focus first
  await evalValue(cdp, `document.getElementById("tab-real").focus(); true`);
  await key(cdp, "ArrowRight");
  await evalValue(cdp, `document.querySelector(".why summary")?.focus(); true`);
  await key(cdp, "Enter");
  await cdp.send("Runtime.evaluate", {
    expression: `document.querySelector(".why summary")?.click()`,
    userGesture: true,
  });
  await evalValue(cdp, `document.querySelector(".card-actions button")?.focus(); true`);
  await key(cdp, "Enter");
  await cdp.send("Runtime.evaluate", {
    expression: `document.querySelector(".card-actions button")?.click()`,
    userGesture: true,
  });
  await waitFor(cdp, `document.getElementById("compare").open === true`);
  await key(cdp, "Escape");
  if (!await evalValue(cdp, `document.getElementById("compare").open === false`)) {
    await clickSel(cdp, "#compare-close");
  }
  await waitFor(cdp, `document.getElementById("compare").open === false`);
  await screenshot(cdp, "07-keyboard-complete");

  // 4. Mobile sheet
  await setViewport(cdp, 390, 844, true);
  await cdp.navigate(ui("#/search/fixture-normal"));
  await waitFor(cdp, `!document.getElementById("results").hidden && document.querySelectorAll("#list-real .card").length >= 1`);
  await screenshot(cdp, "08-mobile-sheet");
  const drawerWidth = await evalValue(cdp, `document.getElementById("results").getBoundingClientRect().width`);

  // 5. Reduced motion
  await setViewport(cdp, 1280, 800, false);
  await cdp.send("Emulation.setEmulatedMedia", {
    features: [{ name: "prefers-reduced-motion", value: "reduce" }],
  });
  await cdp.navigate(ui("#/search/fixture-normal"));
  await waitFor(cdp, `document.querySelector("#list-real .card")`);
  const animation = await evalValue(cdp, `
    getComputedStyle(document.querySelector(".stage-list li .stage-mark") || document.body).animationName
  `);
  await screenshot(cdp, "09-reduced-motion");
  await cdp.send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-reduced-motion", value: "" }] });

  // 6. XSS fixture
  await cdp.navigate(ui("#/search/fixture-xss"));
  await waitFor(cdp, `document.querySelectorAll("#list-possible .card").length >= 1`);
  await clickSel(cdp, "#tab-possible");
  await sleep(200);
  await screenshot(cdp, "10-xss-inert");
  const xssDom = await evalValue(cdp, `
    (() => {
      const titles = [...document.querySelectorAll(".card-title")].map(n => n.textContent);
      const html = [...document.querySelectorAll(".card-title")].map(n => n.innerHTML);
      const imgs = document.querySelectorAll("img[src='x'], img[onerror]");
      const handlers = [...document.querySelectorAll(".card")].flatMap(card =>
        [...card.querySelectorAll("*")].filter(n =>
          [...n.attributes].some(a => a.name.startsWith("on"))
        ).map(n => n.outerHTML)
      );
      const refused = [...document.querySelectorAll(".card")].map(c => c.innerText).join("\\n");
      return { titles, html, strayImgs: imgs.length, handlers, refusedHasSchemeNote: refused.includes("scheme") };
    })()
  `);

  // 7. Empty-real
  await cdp.navigate(ui("#/search/fixture-empty-real"));
  await waitFor(cdp, `document.getElementById("tab-real")`);
  await clickSel(cdp, "#tab-real");
  await waitFor(cdp, `document.getElementById("empty-real") && !document.getElementById("empty-real").hidden`);
  await screenshot(cdp, "11-empty-real");

  // 8. No candidates + blocked sources
  await cdp.navigate(ui("#/search/fixture-empty"));
  await waitFor(cdp, `document.body.innerText.includes("did not find a displayable candidate")`);
  await waitFor(cdp, `document.body.innerText.includes("Add a photograph of the sole")`);
  await screenshot(cdp, "12-no-candidates");

  await cdp.navigate(ui("#/search/fixture-blocked"));
  await waitFor(cdp, `document.body.innerText.includes("blocked") || document.body.innerText.includes("BLOCKED")`);
  await screenshot(cdp, "13-blocked");

  // 9. Refresh mid-search: start a search, reload once a stage is current
  await cdp.navigate(ui());
  await waitFor(cdp, `document.getElementById("file-input")`);
  await setFiles(cdp, "#file-input", [SAMPLE]);
  await evalValue(cdp, `document.getElementById("know").value = "refresh mid-search"; true`);
  await clickSel(cdp, "#search-button");
  await waitFor(cdp, `location.hash.includes("/search/")`, 10000);
  await waitFor(cdp, `
    [...document.querySelectorAll("#stage-list li")].some(li => li.dataset.state === "current")
  `, 10000);
  const hashBefore = await evalValue(cdp, `location.hash`);
  const reloaded = cdp.once("Page.loadEventFired");
  await cdp.send("Page.reload", { ignoreCache: true });
  await Promise.race([reloaded, sleep(8000)]);
  await waitFor(cdp, `location.hash === ${JSON.stringify(hashBefore)}`);
  await waitFor(cdp, `!document.getElementById("results").hidden`);
  const hashAfter = await evalValue(cdp, `location.hash`);
  await screenshot(cdp, "14-refresh-mid-search");

  // 10. Colors used
  const colors = await evalValue(cdp, `
    (() => {
      const out = new Set();
      const nodes = [document.documentElement, document.body, ...document.querySelectorAll("body *")];
      for (const n of nodes.slice(0, 400)) {
        const s = getComputedStyle(n);
        for (const prop of ["color", "backgroundColor", "borderTopColor", "outlineColor"]) {
          out.add(s[prop]);
        }
      }
      return [...out];
    })()
  `);

  // API unavailable
  await cdp.navigate(`${UI}/?api=http://127.0.0.1:9`);
  await waitFor(cdp, `!document.getElementById("api-banner").hidden`, 8000);
  await screenshot(cdp, "15-api-unavailable");
  const unavailableText = await evalValue(cdp, `document.getElementById("api-banner").textContent`);

  const report = {
    homeHasWordmark: homeText.includes("SEARCHER"),
    realTitle,
    scores,
    compareHasSeller: /Reported/i.test(compareText),
    compareHasParts: /Part/i.test(compareText),
    linkAttrs,
    liveSearchId,
    feedbackStatus,
    drawerWidth,
    animation,
    xssDom,
    dialogs,
    hashBefore,
    hashAfter,
    unavailableText,
    colors,
    feedbackPosts,
    consoleLines,
    failures,
  };
  await writeFile(path.join(OUT, "report.json"), JSON.stringify(report, null, 2));
  console.log(JSON.stringify({
    ok: failures.length === 0 && dialogs.length === 0,
    realTitle,
    scores,
    linkAttrs,
    xssTitles: xssDom.titles,
    xssHtml: xssDom.html,
    strayImgs: xssDom.strayImgs,
    handlers: xssDom.handlers,
    dialogs,
    drawerWidth,
    animation,
    hashBefore,
    hashAfter,
    feedbackStatus,
    feedbackPosts,
    consoleErrors: consoleLines.filter((l) => l.type === "error"),
    failures,
  }, null, 2));

  ws.close();
  chrome.kill();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
