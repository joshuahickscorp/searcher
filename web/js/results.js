import { $, announce, clear, el, outboundLink, remoteImg, show, text } from "./dom.js";
import {
  NO_CANDIDATES,
  NO_REAL,
  POSSIBLE_SUBTITLE,
  REAL_SUBTITLE,
  STAGES,
  availabilityLine,
  interval,
  missingOr,
  priceLine,
  sizeLine,
  stageFromState,
} from "./format.js";

function scoreLine(label, block) {
  const value = block && block.label ? block.label : "Not provided";
  const line = el("p", { className: "score-line" }, [
    el("span", { className: "score-k", text: `${label}: ` }),
    el("span", { text: value }),
  ]);
  const nums = interval(block);
  if (nums) {
    line.appendChild(document.createTextNode(" "));
    line.appendChild(el("span", { className: "dev-num", text: nums }));
  }
  return line;
}

function whySection(result) {
  const why = result.why || {};
  const body = el("div", { className: "why-body" });

  function addList(title, items, emptyText) {
    body.appendChild(el("h4", { text: title }));
    const values = Array.isArray(items) && items.length ? items : [emptyText];
    body.appendChild(el("ul", {}, values.map((item) => el("li", { text: item }))));
  }

  body.appendChild(el("h4", { text: why.heading || "Why this result" }));
  addList("Why does Searcher think this is the same item?", why.points, missingOr(null));
  addList("Why is it in this tab?", why.tab_reason ? [why.tab_reason] : [], missingOr(null));
  addList("Which evidence supports the decision?", why.supporting, missingOr(null));
  addList("Which evidence conflicts?", why.contradictions, ["None stated."]);
  addList("What evidence is missing?", why.missing, missingOr(null));
  addList("Still unverified", why.still_unverified, missingOr(null));

  const live = why.live == null ? result.availability === "LIVE" : why.live;
  body.appendChild(el("h4", { text: "Is the listing currently live?" }));
  body.appendChild(el("p", { text: live ? "Yes, when last checked." : "No, or not confirmed." }));
  body.appendChild(el("h4", { text: "When was it checked?" }));
  body.appendChild(el("p", { text: why.checked_at || result.last_checked_at || missingOr(null) }));

  const images = Array.isArray(why.images_compared) ? why.images_compared : [];
  body.appendChild(el("h4", { text: "Which images were compared?" }));
  if (!images.length) {
    body.appendChild(el("p", { text: missingOr(null) }));
  } else {
    body.appendChild(el("ul", {}, images.map((img) => (
      el("li", { text: `${img.role || "image"}: ${img.alt || "untitled"}` })
    ))));
  }

  const dupes = why.duplicate_image_family_count;
  body.appendChild(el("h4", { text: "Did multiple result pages reuse the same images?" }));
  body.appendChild(el("p", {
    text: dupes == null
      ? missingOr(null)
      : (dupes > 0 ? `Yes — ${dupes} shared image families.` : "No shared image families were reported."),
  }));

  const reported = Array.isArray(why.seller_reported) ? why.seller_reported : [];
  body.appendChild(el("h4", { text: "What is reported by the seller rather than independently observed?" }));
  if (!reported.length) {
    body.appendChild(el("p", { text: missingOr(null) }));
  } else {
    body.appendChild(el("ul", {}, reported.map((row) => (
      el("li", { text: `${row.field || "Field"}: ${row.value ?? "—"} (${row.origin || "REPORTED_BY_SELLER"})` })
    ))));
  }

  return el("details", { className: "why" }, [
    el("summary", { text: "Why this result" }),
    body,
  ]);
}

function card(result, { apiBase, onCompare }) {
  const li = el("li", {
    className: "card",
    dataset: { resultId: result.result_id },
  });

  const figure = el("div", { className: "card-image" });
  const image = result.primary_image || {};
  const imageNode = remoteImg(image.url, image.alt || result.title || "Listing image", apiBase());
  if (imageNode.classList.contains("img-failed")) figure.classList.add("img-failed");
  imageNode.addEventListener("error", () => figure.classList.add("img-failed"));
  figure.appendChild(imageNode);
  li.appendChild(figure);

  li.appendChild(el("h3", { className: "card-title", text: result.title || "Untitled listing" }));
  li.appendChild(el("p", { className: "card-meta", text: `Source: ${(result.source && result.source.name) || "Source not provided"}` }));
  li.appendChild(el("p", { className: "card-meta", text: priceLine(result.price) }));
  li.appendChild(el("p", { className: "card-meta", text: sizeLine(result.size) }));
  li.appendChild(el("p", { className: "card-meta", text: availabilityLine(result) }));

  const scores = el("div", { className: "score-block" }, [
    scoreLine("Item match", result.item_match),
    scoreLine("Authenticity evidence", result.authenticity),
    scoreLine("Listing utility", result.listing_utility),
  ]);
  li.appendChild(scores);

  const chips = Array.isArray(result.evidence_chips) ? result.evidence_chips.slice(0, 3) : [];
  if (chips.length) {
    li.appendChild(el("ul", { className: "chips-inline" }, chips.map((chip) => (
      el("li", { className: "evidence", dataset: { kind: chip.kind || "support" }, text: chip.text || "" })
    ))));
  }
  if (result.primary_gap && result.primary_gap.text) {
    const mark = result.primary_gap.kind === "contradiction" ? "!" : "?";
    li.appendChild(el("p", { className: "gap-line", text: `${mark} ${result.primary_gap.text}` }));
  }

  const actions = el("div", { className: "card-actions" });
  if (result.availability === "LIVE") {
    const link = outboundLink(result.listing_url, "Open listing ↗");
    if (link) actions.appendChild(link);
    else actions.appendChild(el("span", { text: "Listing link refused (scheme is not http or https)." }));
  } else {
    actions.appendChild(el("span", { text: "Listing is not live, so it is not offered as a purchase link." }));
  }
  const compareBtn = el("button", { type: "button", text: "Compare" });
  compareBtn.addEventListener("click", () => onCompare(result, compareBtn));
  actions.appendChild(compareBtn);
  li.appendChild(actions);
  li.appendChild(whySection(result));
  return li;
}

function coverageBlock(search) {
  const wrap = el("div");
  const cov = search.coverage || {};
  const groups = [
    ["Sources completed", cov.sources_completed],
    ["Sources blocked", cov.sources_blocked],
  ];
  for (const [title, rows] of groups) {
    wrap.appendChild(el("h4", { text: title }));
    const list = Array.isArray(rows) ? rows : [];
    if (!list.length) {
      wrap.appendChild(el("p", { text: "None reported." }));
    } else {
      wrap.appendChild(el("ul", {}, list.map((row) => {
        const bits = [row.name || row.id || "Source", row.status, row.detail].filter(Boolean);
        return el("li", { text: bits.join(" — ") });
      })));
    }
  }
  const missing = Array.isArray(search.missing_reference_views) ? search.missing_reference_views : [];
  wrap.appendChild(el("h4", { text: "Most valuable missing reference views" }));
  if (!missing.length) {
    wrap.appendChild(el("p", { text: "None reported." }));
  } else {
    wrap.appendChild(el("ul", {}, missing.map((row) => (
      el("li", { text: row.view ? `${row.view} — ${row.why || ""}`.trim() : String(row) })
    ))));
  }
  wrap.appendChild(el("h4", { text: "Deeper refresh" }));
  wrap.appendChild(el("p", {
    text: search.deeper_refresh_available
      ? "A deeper refresh is available from the search service."
      : "A deeper refresh is not available for this search.",
  }));
  if (cov.pages_fetched != null) {
    wrap.appendChild(el("p", { text: `Pages fetched: ${cov.pages_fetched}. Candidates normalized: ${cov.candidates_normalized ?? "not provided"}.` }));
  }
  return wrap;
}

export function createResults({ apiBase, onCompare, onCancel, onDelete, onClose, onTab }) {
  const drawer = $("results");
  const status = $("campaign-status");
  const cancelBtn = $("cancel-search");
  const deleteBtn = $("delete-search");
  const closeBtn = $("close-drawer");
  const progress = $("progress");
  const progressNow = $("progress-now");
  const stageList = $("stage-list");
  const streamNote = $("stream-note");
  const warningNote = $("warning-note");
  const terminalNote = $("terminal-note");
  const countReal = $("count-real");
  const countPossible = $("count-possible");
  const subtitle = $("tab-subtitle");
  const hiddenNote = $("hidden-note");
  const panelReal = $("panel-real");
  const panelPossible = $("panel-possible");
  const listReal = $("list-real");
  const listPossible = $("list-possible");
  const emptyReal = $("empty-real");
  const emptyPossible = $("empty-possible");
  const tabReal = $("tab-real");
  const tabPossible = $("tab-possible");
  const coverage = $("coverage");
  const coverageBody = $("coverage-body");

  const results = new Map();
  const cards = new Map();
  let tab = "real";
  let search = null;
  let lastStage = null;

  function currentStage() {
    if (!search) return null;
    return (search.progress && search.progress.stage) || stageFromState(search.state);
  }

  function renderStages() {
    const stage = currentStage();
    lastStage = stage;
    clear(stageList);
    const idx = STAGES.indexOf(stage);
    const terminal = Boolean(search && search.terminal_status);
    STAGES.forEach((name, i) => {
      let state = "todo";
      if (terminal || (idx !== -1 && i < idx)) state = "done";
      else if (idx === i) state = "current";
      const mark = state === "todo" ? "○" : state === "current" ? "●" : "■";
      stageList.appendChild(el("li", { dataset: { state } }, [
        el("span", { className: "stage-mark", text: mark, "aria-hidden": "true" }),
        el("span", { text: name }),
      ]));
    });
    const busy = Boolean(search && !search.terminal_status && stage);
    progress.classList.toggle("is-busy", busy);
    text(progressNow, stage || (search && search.terminal_status ? "Search finished" : "Starting"));
    show(progress, Boolean(stage || (search && !search.terminal_status)));
  }

  function emptyCopy() {
    if (!search) return;
    const realN = Number((search.counts && search.counts.real) || 0);
    const posN = Number((search.counts && search.counts.possibly_real) || 0);
    const terminal = search.terminal_status;
    const blockedLike = terminal === "BLOCKED" || terminal === "FAILED";

    clear(emptyReal);
    clear(emptyPossible);

    if (realN === 0 && posN === 0) {
      if (blockedLike) {
        show(emptyReal, false);
        show(emptyPossible, false);
      } else if (terminal) {
        emptyReal.appendChild(el("p", { text: NO_CANDIDATES }));
        show(emptyReal, tab === "real");
        emptyPossible.appendChild(el("p", { text: NO_CANDIDATES }));
        show(emptyPossible, tab === "possibly_real");
      } else {
        show(emptyReal, false);
        show(emptyPossible, false);
      }
      return;
    }
    if (realN === 0) {
      emptyReal.appendChild(el("p", { text: NO_REAL }));
      if (posN > 0) {
        emptyReal.appendChild(el("p", { text: "Possibly Real results are available in the other tab." }));
      }
      show(emptyReal, tab === "real");
    } else {
      show(emptyReal, false);
    }
    show(emptyPossible, tab === "possibly_real" && posN === 0);
    if (posN === 0 && tab === "possibly_real") {
      emptyPossible.appendChild(el("p", { text: "No Possibly Real candidates yet." }));
    }
  }

  function renderTerminal() {
    if (!search) return;
    const terminal = search.terminal_status;
    const reason = search.terminal_reason || "";
    let message = "";
    if (terminal === "CANCELLED") {
      message = reason || "This search was cancelled. Evidence gathered before cancellation is kept.";
    } else if (terminal === "BLOCKED") {
      message = reason || "This search is blocked. Searcher could not complete the declared goal because of access, policy, or missing reference evidence. This is not the same as finding no matching item.";
    } else if (terminal === "FAILED") {
      message = reason || "This search failed because of an internal error. It is not a “no results” outcome.";
    } else if (terminal === "PARTIAL") {
      message = reason || "This search finished with incomplete coverage. Some sources were blocked or the budget ended before the search was exhausted.";
    } else if (terminal === "COMPLETE") {
      message = "";
    }
    if (message) {
      text(terminalNote, message);
      show(terminalNote, true);
    } else {
      show(terminalNote, false);
      text(terminalNote, "");
    }
    const hidden = search.hidden_policy_note || (
      search.counts && search.counts.hidden ? "Some candidates did not meet policy." : ""
    );
    if (hidden) {
      text(hiddenNote, hidden);
      show(hiddenNote, true);
    } else {
      show(hiddenNote, false);
    }
    const cov = search.coverage || {};
    const hasCoverage = Boolean(
      (cov.sources_completed && cov.sources_completed.length)
      || (cov.sources_blocked && cov.sources_blocked.length)
      || search.terminal_status,
    );
    if (hasCoverage) {
      clear(coverageBody);
      coverageBody.appendChild(coverageBlock(search));
      show(coverage, true);
    } else {
      show(coverage, false);
    }
  }

  function paintLists() {
    const real = [];
    const possible = [];
    for (const result of results.values()) {
      if (result.bucket === "real") real.push(result);
      else possible.push(result);
    }
    real.sort((a, b) => (a.rank || 0) - (b.rank || 0));
    possible.sort((a, b) => (a.rank || 0) - (b.rank || 0));

    function order(list, parent) {
      for (const result of list) {
        let node = cards.get(result.result_id);
        if (!node) {
          node = card(result, { apiBase, onCompare });
          cards.set(result.result_id, node);
        }
        parent.appendChild(node);
      }
    }
    order(real, listReal);
    order(possible, listPossible);
    text(countReal, String(real.length));
    text(countPossible, String(possible.length));
    if (search) {
      search.counts = search.counts || {};
      search.counts.real = real.length;
      search.counts.possibly_real = possible.length;
    }
    emptyCopy();
  }

  function setTab(next, { announceChange = false } = {}) {
    tab = next === "possibly_real" ? "possibly_real" : "real";
    const isReal = tab === "real";
    tabReal.setAttribute("aria-selected", isReal ? "true" : "false");
    tabPossible.setAttribute("aria-selected", isReal ? "false" : "true");
    tabReal.tabIndex = isReal ? 0 : -1;
    tabPossible.tabIndex = isReal ? -1 : 0;
    show(panelReal, isReal);
    show(panelPossible, !isReal);
    text(subtitle, isReal ? REAL_SUBTITLE : POSSIBLE_SUBTITLE);
    emptyCopy();
    if (announceChange) announce(isReal ? "Real tab" : "Possibly Real tab");
    onTab(tab);
  }

  tabReal.addEventListener("click", () => setTab("real", { announceChange: true }));
  tabPossible.addEventListener("click", () => setTab("possibly_real", { announceChange: true }));
  document.querySelector(".tabs").addEventListener("keydown", (ev) => {
    if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
    ev.preventDefault();
    const next = tab === "real" ? "possibly_real" : "real";
    setTab(next, { announceChange: true });
    (next === "real" ? tabReal : tabPossible).focus();
  });
  cancelBtn.addEventListener("click", () => onCancel());
  deleteBtn.addEventListener("click", () => onDelete());
  closeBtn.addEventListener("click", () => onClose());

  return {
    open() {
      show(drawer, true);
      document.body.classList.add("drawer-open");
    },
    close() {
      show(drawer, false);
      document.body.classList.remove("drawer-open");
    },
    isOpen() {
      return !drawer.hidden;
    },
    reset() {
      results.clear();
      cards.clear();
      clear(listReal);
      clear(listPossible);
      search = null;
      lastStage = null;
      show(streamNote, false);
      show(warningNote, false);
      show(terminalNote, false);
      show(hiddenNote, false);
      show(coverage, false);
      show(cancelBtn, false);
      show(deleteBtn, false);
      text(status, "");
      text(countReal, "0");
      text(countPossible, "0");
    },
    setSearch(next) {
      search = next;
      const stage = currentStage();
      text(status, stage || (search.terminal_status ? search.terminal_status : search.state || ""));
      show(cancelBtn, !search.terminal_status);
      show(deleteBtn, Boolean(search.terminal_status));
      renderStages();
      renderTerminal();
      if (search.counts) {
        text(countReal, String(search.counts.real || 0));
        text(countPossible, String(search.counts.possibly_real || 0));
      }
      emptyCopy();
    },
    setStream(message) {
      if (message) {
        text(streamNote, message);
        show(streamNote, true);
      } else {
        show(streamNote, false);
        text(streamNote, "");
      }
    },
    setWarning(message) {
      if (message) {
        text(warningNote, message);
        show(warningNote, true);
        announce(message);
      }
    },
    upsertResult(result, bucket) {
      const copy = { ...result, bucket: bucket || result.bucket };
      const prev = results.get(copy.result_id);
      results.set(copy.result_id, copy);
      if (prev && prev.bucket !== copy.bucket) {
        const node = cards.get(copy.result_id);
        if (node) {
          node.remove();
          cards.delete(copy.result_id);
        }
      }
      paintLists();
    },
    removeResult(resultId) {
      results.delete(resultId);
      const node = cards.get(resultId);
      if (node) node.remove();
      cards.delete(resultId);
      paintLists();
    },
    loadResults(payload) {
      if (payload.real || payload.possibly_real) {
        for (const row of payload.real || []) this.upsertResult(row, "real");
        for (const row of payload.possibly_real || []) this.upsertResult(row, "possibly_real");
      } else if (Array.isArray(payload.results)) {
        const bucket = payload.bucket;
        for (const row of payload.results) this.upsertResult(row, bucket);
      }
    },
    getResult(id) {
      return results.get(id) || null;
    },
    setTab,
    getTab() {
      return tab;
    },
    announceStage(stage) {
      if (stage && stage !== lastStage) announce(stage);
      lastStage = stage;
    },
  };
}
