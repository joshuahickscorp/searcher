import { $, announce, clear, el, outboundLink, remoteImg, show, text } from "./dom.js";
import { feedbackControls, paintFeedback } from "./feedback.js";
import {
  NO_CANDIDATES,
  NO_REAL,
  POSSIBLE_SUBTITLE,
  REAL_SUBTITLE,
  REPLICA_SUBTITLE,
  STAGES,
  availabilityLine,
  coverageStatsLine,
  interval,
  missingOr,
  nextInputFromMissing,
  priceLine,
  sizeLine,
  sourcesInProgress,
  stageFromState,
  stageStepLabel,
  terminalStatusLabel,
  whyHeadingText,
  whyLeadText,
  formatElapsed,
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
    const emptyReason = why.images_compared_reason
      || (result.compare && result.compare.reason)
      || "comparison stage did not run";
    body.appendChild(el("p", { text: emptyReason }));
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
    el("summary", { text: "Full evidence" }),
    body,
  ]);
}

function whyLeadBlock(result) {
  const heading = whyHeadingText(result);
  const lead = whyLeadText(result);
  if (!heading && !lead) return null;
  const block = el("div", { className: "why-lead" });
  if (heading) block.appendChild(el("p", { className: "why-kicker", text: heading }));
  if (lead) block.appendChild(el("p", { className: "why-sentence", text: lead }));
  return block;
}

function nextInputBlock(search) {
  const next = nextInputFromMissing(search);
  if (!next) return null;
  const box = el("div", { className: "next-input" }, [
    el("p", { className: "next-input-k", text: "What to add next" }),
    el("p", { className: "next-input-action", text: next.action }),
  ]);
  if (next.why) {
    box.appendChild(el("p", { className: "next-input-why", text: next.why }));
  }
  if (next.rest.length) {
    box.appendChild(el("ul", { className: "next-input-rest" }, next.rest.map((row) => (
      el("li", { text: row })
    ))));
  }
  return box;
}

function card(result, { apiBase, onCompare, onFeedback, feedbackState }) {
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

  const lead = whyLeadBlock(result);
  if (lead) li.appendChild(lead);

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
  // The listing always opens. Withholding the URL protected nobody - the page is
  // public and the source published it - while telling a reader the listing was
  // "not live" when availability is merely unknown claimed more than the
  // evidence supports. Liveness is stated on its own line, from last_checked_at.
  const link = outboundLink(result.listing_url, "Open listing ↗");
  if (link) {
    actions.appendChild(link);
  } else {
    actions.appendChild(el("span", { text: "No usable listing link was recorded." }));
  }
  if (result.availability === "SOLD" || result.availability === "REMOVED") {
    actions.appendChild(el("span", {
      className: "card-meta",
      text: "This listing is no longer offered; the link opens the original page.",
    }));
  } else if (result.availability !== "LIVE") {
    actions.appendChild(el("span", {
      className: "card-meta",
      text: "Availability could not be confirmed, so the link may be stale.",
    }));
  }
  const compareBtn = el("button", { type: "button", className: "compare-btn", text: "Compare" });
  compareBtn.addEventListener("click", () => onCompare(result, compareBtn));
  actions.appendChild(compareBtn);
  li.appendChild(actions);
  li.appendChild(whySection(result));
  if (typeof onFeedback === "function") {
    li.appendChild(feedbackControls(result, {
      onFeedback,
      state: feedbackState ? feedbackState.get(result.result_id) : null,
    }));
  }
  return li;
}

function coverageBlock(search) {
  const wrap = el("div");
  const cov = search.coverage || {};
  const groups = [
    ["Completed", cov.sources_completed],
    ["Blocked", cov.sources_blocked],
  ];
  for (const [title, rows] of groups) {
    wrap.appendChild(el("h4", { text: title }));
    const list = Array.isArray(rows) ? rows : [];
    if (!list.length) {
      wrap.appendChild(el("p", { text: "None." }));
    } else {
      wrap.appendChild(el("ul", {}, list.map((row) => {
        const bits = [row.name || row.id || "Source", row.status, row.detail].filter(Boolean);
        return el("li", { text: bits.join(" — ") });
      })));
    }
  }
  const missing = Array.isArray(search.missing_reference_views) ? search.missing_reference_views : [];
  wrap.appendChild(el("h4", { text: "Missing views" }));
  if (!missing.length) {
    wrap.appendChild(el("p", { text: "None." }));
  } else {
    wrap.appendChild(el("ul", {}, missing.map((row) => (
      el("li", { text: row.view ? `${row.view} — ${row.why || ""}`.trim() : String(row) })
    ))));
  }
  wrap.appendChild(el("h4", { text: "Deeper refresh" }));
  wrap.appendChild(el("p", {
    text: search.deeper_refresh_available
      ? "Deeper refresh is available."
      : "Deeper refresh is not available.",
  }));
  if (cov.pages_fetched != null) {
    wrap.appendChild(el("p", { text: `Pages fetched: ${cov.pages_fetched}. Candidates normalized: ${cov.candidates_normalized ?? "not provided"}.` }));
  }
  return wrap;
}

export function createResults({ apiBase, onCompare, onFeedback, onCancel, onDelete, onClose, onTab, replicaScope }) {
  const drawer = $("results");
  const heading = $("results-heading");
  const intentLine = $("campaign-intent");
  const status = $("campaign-status");
  const cancelBtn = $("cancel-search");
  const deleteBtn = $("delete-search");
  const closeBtn = $("close-drawer");
  const progress = $("progress");
  const progressNow = $("progress-now");
  const progressMeta = $("progress-meta");
  const progressDetail = $("progress-detail");
  const progressStats = $("progress-stats");
  const progressSources = $("progress-sources");
  const stageDetails = $("stage-details");
  const stageList = $("stage-list");
  const streamNote = $("stream-note");
  const warningNote = $("warning-note");
  const terminalNote = $("terminal-note");
  const countReal = $("count-real");
  const countPossible = $("count-possible");
  const countReplica = $("count-replica");
  const subtitle = $("tab-subtitle");
  const hiddenNote = $("hidden-note");
  const panelReal = $("panel-real");
  const panelPossible = $("panel-possible");
  const panelReplica = $("panel-replica");
  const listReal = $("list-real");
  const listPossible = $("list-possible");
  const listReplica = $("list-replica");
  const emptyReal = $("empty-real");
  const emptyPossible = $("empty-possible");
  const tabReal = $("tab-real");
  const tabPossible = $("tab-possible");
  const tabReplica = $("tab-replica");
  const coverage = $("coverage");
  const coverageBody = $("coverage-body");

  const results = new Map();
  const cards = new Map();
  const signatures = new Map();
  const feedbackState = new Map();
  const activity = { discovered: new Set(), normalized: new Set(), promoted: new Set() };
  let tab = "real";
  let search = null;
  let lastStage = null;
  let startedAt = null;
  let tick = null;

  function currentStage() {
    if (!search) return null;
    return (search.progress && search.progress.stage) || stageFromState(search.state);
  }

  function activityCounts() {
    return {
      discovered: activity.discovered.size,
      normalized: activity.normalized.size,
      promoted: activity.promoted.size,
    };
  }

  function stopTick() {
    if (tick) {
      clearInterval(tick);
      tick = null;
    }
  }

  function ensureTick() {
    if (tick || !search || search.terminal_status) return;
    tick = setInterval(() => {
      if (!search || search.terminal_status) {
        stopTick();
        return;
      }
      renderStages();
    }, 1000);
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
    const nowLabel = terminal ? "Search finished" : (stage || "Starting");
    text(progressNow, nowLabel);

    const metaBits = [];
    if (!terminal && stage) {
      const step = stageStepLabel(stage);
      if (step) metaBits.push(step);
    }
    if (!terminal && startedAt) {
      const elapsed = formatElapsed(Date.now() - startedAt);
      if (elapsed) metaBits.push(elapsed);
    }
    if (progressMeta) {
      text(progressMeta, metaBits.join(" · "));
      show(progressMeta, metaBits.length > 0);
    }

    const apiDetail = search && search.progress && search.progress.detail;
    const detailText = apiDetail && String(apiDetail).trim() ? String(apiDetail).trim() : "";
    if (progressDetail) {
      text(progressDetail, detailText);
      show(progressDetail, Boolean(detailText));
    }
    const runningNames = sourcesInProgress(search && search.coverage);

    const stats = coverageStatsLine(search && search.coverage, activityCounts());
    if (progressStats) {
      text(progressStats, stats);
      show(progressStats, Boolean(stats));
    }
    if (progressSources) {
      clear(progressSources);
      if (runningNames.length && !terminal) {
        for (const name of runningNames) {
          progressSources.appendChild(el("li", { text: name }));
        }
        show(progressSources, true);
      } else {
        show(progressSources, false);
      }
    }
    if (stageDetails) {
      const summary = stageDetails.querySelector("summary");
      if (summary) {
        text(summary, terminal ? "All stages" : (stage ? `Now: ${stage}` : "All stages"));
      }
    }
    show(progress, Boolean(stage || (search && !search.terminal_status) || stats));
    if (busy) ensureTick();
    else stopTick();
  }

  function fillEmpty(node, lines) {
    clear(node);
    for (const line of lines) {
      node.appendChild(el("p", { text: line }));
    }
    const next = nextInputBlock(search);
    if (next) node.appendChild(next);
    else if (search && search.terminal_status && search.terminal_status !== "BLOCKED" && search.terminal_status !== "FAILED") {
      node.appendChild(el("p", {
        className: "next-input-fallback",
        text: "Close results, add another photograph or a more specific name, and search again.",
      }));
    }
    if (search && search.deeper_refresh_available) {
      node.appendChild(el("p", {
        className: "next-input-note",
        text: "Deeper refresh is available.",
      }));
    }
  }

  function emptyCopy() {
    if (!search) return;
    const realN = Number((search.counts && search.counts.real) || 0);
    const posN = Number((search.counts && search.counts.possibly_real) || 0);
    const terminal = search.terminal_status;
    const blockedLike = terminal === "BLOCKED" || terminal === "FAILED";

    if (realN === 0 && posN === 0) {
      if (blockedLike) {
        show(emptyReal, false);
        show(emptyPossible, false);
      } else if (terminal) {
        fillEmpty(emptyReal, [NO_CANDIDATES]);
        fillEmpty(emptyPossible, [NO_CANDIDATES]);
        show(emptyReal, tab === "real");
        show(emptyPossible, tab === "possibly_real");
      } else {
        show(emptyReal, false);
        show(emptyPossible, false);
      }
      return;
    }
    if (realN === 0) {
      const lines = [NO_REAL];
      if (posN > 0) lines.push("See Possibly Real.");
      fillEmpty(emptyReal, lines);
      show(emptyReal, tab === "real");
    } else {
      show(emptyReal, false);
    }
    if (posN === 0 && tab === "possibly_real") {
      fillEmpty(emptyPossible, ["No Possibly Real candidates yet."]);
      show(emptyPossible, true);
    } else {
      show(emptyPossible, false);
    }
  }

  function renderTerminal() {
    if (!search) return;
    const terminal = search.terminal_status;
    const reason = search.terminal_reason || "";
    let message = "";
    if (terminal === "CANCELLED") {
      message = reason || "Search cancelled. Evidence gathered before cancellation is kept.";
    } else if (terminal === "BLOCKED") {
      message = reason || "Search blocked. Access, policy, or missing reference evidence stopped the goal. This is not the same as finding no matching item.";
    } else if (terminal === "FAILED") {
      message = reason || "Search failed from an internal error. It is not a “no results” outcome.";
    } else if (terminal === "PARTIAL") {
      message = reason || "Search finished with incomplete coverage. Some sources were blocked or the budget ended first.";
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

  function replicaVisible() {
    if (typeof replicaScope === "function" && !replicaScope()) return false;
    for (const result of results.values()) {
      if (result.bucket === "replica") return true;
    }
    return false;
  }

  function visibleTabIds() {
    const ids = ["real", "possibly_real"];
    if (replicaVisible()) ids.push("replica");
    return ids;
  }

  function tabButton(id) {
    if (id === "replica") return tabReplica;
    if (id === "possibly_real") return tabPossible;
    return tabReal;
  }

  function paintLists() {
    const real = [];
    const possible = [];
    const replica = [];
    for (const result of results.values()) {
      if (result.bucket === "real") real.push(result);
      else if (result.bucket === "possibly_real") possible.push(result);
      else if (result.bucket === "replica") replica.push(result);
    }
    real.sort((a, b) => (a.rank || 0) - (b.rank || 0));
    possible.sort((a, b) => (a.rank || 0) - (b.rank || 0));
    replica.sort((a, b) => (a.rank || 0) - (b.rank || 0));

    function signatureOf(result) {
      return JSON.stringify({
        bucket: result.bucket,
        rank: result.rank,
        title: result.title,
        avail: result.availability,
        checked: result.last_checked_at,
        heading: whyHeadingText(result),
        lead: whyLeadText(result),
        chips: result.evidence_chips,
        gap: result.primary_gap,
        price: result.price && result.price.display,
        size: result.size && result.size.display,
      });
    }

    function order(list, parent) {
      for (const result of list) {
        const nextSig = signatureOf(result);
        let node = cards.get(result.result_id);
        const focused = node && node.contains(document.activeElement);
        if (!node || (signatures.get(result.result_id) !== nextSig && !focused)) {
          const next = card(result, { apiBase, onCompare, onFeedback, feedbackState });
          if (node) node.replaceWith(next);
          node = next;
          cards.set(result.result_id, node);
          signatures.set(result.result_id, nextSig);
        }
        parent.appendChild(node);
      }
    }
    order(real, listReal);
    order(possible, listPossible);
    order(replica, listReplica);
    text(countReal, String(real.length));
    text(countPossible, String(possible.length));
    text(countReplica, String(replica.length));
    if (search) {
      search.counts = search.counts || {};
      search.counts.real = real.length;
      search.counts.possibly_real = possible.length;
    }
    syncReplicaScope();
    emptyCopy();
  }

  function setTab(next, { announceChange = false } = {}) {
    const allowed = visibleTabIds();
    if (!allowed.includes(next)) next = "real";
    tab = next;
    const defs = [
      ["real", tabReal, panelReal, REAL_SUBTITLE, "Real tab"],
      ["possibly_real", tabPossible, panelPossible, POSSIBLE_SUBTITLE, "Possibly Real tab"],
      ["replica", tabReplica, panelReplica, REPLICA_SUBTITLE, "Replica tab"],
    ];
    for (const [id, btn, panel, sub, spoken] of defs) {
      const selected = tab === id;
      const present = id !== "replica" || replicaVisible();
      btn.setAttribute("aria-selected", selected ? "true" : "false");
      btn.tabIndex = selected ? 0 : -1;
      show(btn, present);
      show(panel, selected && present);
      if (selected) text(subtitle, sub);
      if (selected && announceChange) announce(spoken);
    }
    emptyCopy();
    onTab(tab);
  }

  function syncReplicaScope() {
    const on = replicaVisible();
    show(tabReplica, on);
    if (!on && tab === "replica") {
      setTab("real");
      return;
    }
    if (tab === "replica") show(panelReplica, on);
    else show(panelReplica, false);
  }

  tabReal.addEventListener("click", () => setTab("real", { announceChange: true }));
  tabPossible.addEventListener("click", () => setTab("possibly_real", { announceChange: true }));
  tabReplica.addEventListener("click", () => setTab("replica", { announceChange: true }));
  document.querySelector(".tabs").addEventListener("keydown", (ev) => {
    if (ev.key !== "ArrowRight" && ev.key !== "ArrowLeft") return;
    ev.preventDefault();
    const ids = visibleTabIds();
    const idx = Math.max(0, ids.indexOf(tab));
    const step = ev.key === "ArrowRight" ? 1 : -1;
    const next = ids[(idx + step + ids.length) % ids.length];
    setTab(next, { announceChange: true });
    tabButton(next).focus();
  });
  cancelBtn.addEventListener("click", () => onCancel());
  deleteBtn.addEventListener("click", () => onDelete());
  closeBtn.addEventListener("click", () => onClose());

  return {
    open() {
      show(drawer, true);
      document.body.classList.add("drawer-open");
      if (heading && typeof heading.focus === "function") heading.focus();
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
      signatures.clear();
      feedbackState.clear();
      activity.discovered.clear();
      activity.normalized.clear();
      activity.promoted.clear();
      clear(listReal);
      clear(listPossible);
      clear(listReplica);
      search = null;
      lastStage = null;
      startedAt = null;
      stopTick();
      show(streamNote, false);
      show(warningNote, false);
      show(terminalNote, false);
      show(hiddenNote, false);
      show(coverage, false);
      show(cancelBtn, false);
      show(deleteBtn, false);
      show(tabReplica, false);
      show(panelReplica, false);
      text(status, "");
      if (intentLine) {
        text(intentLine, "");
        show(intentLine, false);
      }
      text(countReal, "0");
      text(countPossible, "0");
      text(countReplica, "0");
      if (progressDetail) {
        text(progressDetail, "");
        show(progressDetail, false);
      }
      if (progressStats) {
        text(progressStats, "");
        show(progressStats, false);
      }
      if (progressMeta) {
        text(progressMeta, "");
        show(progressMeta, false);
      }
    },
    setSearch(next) {
      search = next;
      const stage = currentStage();
      const label = search.terminal_status
        ? terminalStatusLabel(search.terminal_status)
        : (stage || search.state || "");
      text(status, label);
      if (intentLine) {
        const intent = search.intent && search.intent.text ? String(search.intent.text).trim() : "";
        text(intentLine, intent);
        show(intentLine, Boolean(intent));
      }
      show(cancelBtn, !search.terminal_status);
      show(deleteBtn, Boolean(search.terminal_status));
      if (!search.terminal_status && !startedAt) startedAt = Date.now();
      if (search.terminal_status) stopTick();
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
      if (payload.real || payload.possibly_real || payload.replica) {
        for (const row of payload.real || []) this.upsertResult(row, "real");
        for (const row of payload.possibly_real || []) this.upsertResult(row, "possibly_real");
        for (const row of payload.replica || []) this.upsertResult(row, "replica");
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
    syncReplicaScope,
    announceStage(stage) {
      if (stage && stage !== lastStage) announce(stage);
      lastStage = stage;
    },
    noteCandidate(kind, candidateId) {
      const key = candidateId || `${kind}:${activity.discovered.size + activity.normalized.size + 1}`;
      if (kind === "discovered") activity.discovered.add(key);
      else if (kind === "normalized") activity.normalized.add(key);
      else if (kind === "promoted") activity.promoted.add(key);
      renderStages();
    },
    setFeedback(resultId, state) {
      if (!resultId) return;
      feedbackState.set(resultId, state);
      const node = cards.get(resultId);
      if (node) paintFeedback(node.querySelector(".feedback"), state);
    },
    getFeedback(resultId) {
      return feedbackState.get(resultId) || null;
    },
  };
}
