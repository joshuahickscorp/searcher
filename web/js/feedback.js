import { el } from "./dom.js";
import { FEEDBACK_THIS_IS_NOT_IT, FEEDBACK_THIS_IS_THE_ONE } from "./format.js";

function statusCopy(state) {
  if (!state) return "";
  if (state.status === "sending") return "Recording…";
  if (state.status === "recorded") {
    const which = state.verdict === FEEDBACK_THIS_IS_THE_ONE.verdict
      ? FEEDBACK_THIS_IS_THE_ONE.label
      : state.verdict === FEEDBACK_THIS_IS_NOT_IT.verdict
        ? FEEDBACK_THIS_IS_NOT_IT.label
        : "Feedback";
    return `${which} recorded. Rankings are unchanged.`;
  }
  if (state.status === "error") return state.message || "Feedback could not be recorded.";
  return "";
}

export function paintFeedback(root, state) {
  if (!root) return;
  const status = root.querySelector(".feedback-status");
  const buttons = root.querySelectorAll("button[data-verdict]");
  const copy = statusCopy(state);
  if (status) status.textContent = copy;
  const busy = Boolean(state && (state.status === "sending" || state.status === "recorded"));
  for (const button of buttons) {
    button.disabled = busy;
    const on = Boolean(state && state.status === "recorded" && button.dataset.verdict === state.verdict);
    button.setAttribute("aria-pressed", on ? "true" : "false");
  }
}

export function feedbackControls(result, { onFeedback, state } = {}) {
  const one = el("button", {
    type: "button",
    className: "feedback-yes",
    text: FEEDBACK_THIS_IS_THE_ONE.label,
    "data-verdict": FEEDBACK_THIS_IS_THE_ONE.verdict,
    "aria-pressed": "false",
  });
  const not = el("button", {
    type: "button",
    className: "feedback-no",
    text: FEEDBACK_THIS_IS_NOT_IT.label,
    "data-verdict": FEEDBACK_THIS_IS_NOT_IT.verdict,
    "aria-pressed": "false",
  });
  one.addEventListener("click", () => {
    if (typeof onFeedback === "function") onFeedback(result, FEEDBACK_THIS_IS_THE_ONE.verdict, one);
  });
  not.addEventListener("click", () => {
    if (typeof onFeedback === "function") onFeedback(result, FEEDBACK_THIS_IS_NOT_IT.verdict, not);
  });
  const root = el("div", {
    className: "feedback",
    dataset: { resultId: result.result_id || "" },
  }, [
    el("p", { className: "feedback-k", text: "Is this the item?" }),
    el("div", { className: "feedback-actions" }, [one, not]),
    el("p", { className: "feedback-status", role: "status" }),
  ]);
  paintFeedback(root, state);
  return root;
}
