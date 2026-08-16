import { $, clear, el, remoteImg } from "./dom.js";
import { missingOr } from "./format.js";

function listBlock(title, items) {
  const values = Array.isArray(items) && items.length
    ? items
    : [missingOr(items)];
  return el("section", {}, [
    el("h3", { text: title }),
    el("ul", {}, values.map((item) => el("li", { text: item }))),
  ]);
}

function originMark(origin) {
  if (!origin) return null;
  const labels = {
    REPORTED_BY_SELLER: "Reported by seller",
    REPORTED_BY_SOURCE: "Reported by source",
    USER_SUPPLIED: "User supplied",
    OBSERVED: "Observed",
    EXTRACTED: "Extracted",
    INFERRED: "Inferred",
    UNRESOLVED: "Unresolved",
  };
  return el("span", {
    className: "origin",
    text: labels[origin] || origin,
  });
}

export function createCompare({ apiBase, onClose }) {
  const dialog = $("compare");
  const body = $("compare-body");
  const closeBtn = $("compare-close");

  function close() {
    if (dialog.open) dialog.close();
    onClose();
  }

  closeBtn.addEventListener("click", close);
  dialog.addEventListener("cancel", (ev) => {
    ev.preventDefault();
    close();
  });
  document.addEventListener("keydown", (ev) => {
    if (ev.key === "Escape" && dialog.open) {
      ev.preventDefault();
      close();
    }
  });

  function render(result) {
    clear(body);
    const compare = result.compare || {};
    const why = result.why || {};
    const emptyReason = compare.reason
      || why.images_compared_reason
      || (
        Array.isArray(why.images_compared) && why.images_compared.length
          ? ""
          : "comparison stage did not run"
      );
    if (emptyReason && !((compare.reference_crop && compare.reference_crop.url)
      || (compare.candidate_crop && compare.candidate_crop.url)
      || (Array.isArray(compare.parts) && compare.parts.length)
      || (Array.isArray(why.images_compared) && why.images_compared.length))) {
      body.appendChild(el("p", { text: emptyReason }));
      return;
    }
    const ref = compare.reference_crop || {};
    const cand = compare.candidate_crop || {};

    const pair = el("div", { className: "compare-pair" }, [
      el("figure", {}, [
        remoteImg(ref.url, ref.alt || "User reference crop", apiBase()),
        el("figcaption", { text: `Your reference${ref.part ? ` · ${ref.part}` : ""}` }),
      ]),
      el("figure", {}, [
        remoteImg(cand.url, cand.alt || "Candidate crop", apiBase()),
        el("figcaption", { text: `Candidate${cand.part ? ` · ${cand.part}` : ""}` }),
      ]),
    ]);

    const table = el("table", { className: "compare-table" }, [
      el("thead", {}, [
        el("tr", {}, [
          el("th", { text: "Part" }),
          el("th", { text: "Note" }),
          el("th", { text: "Status" }),
          el("th", { text: "Origin" }),
        ]),
      ]),
    ]);
    const tb = el("tbody");
    const parts = Array.isArray(compare.parts) ? compare.parts : [];
    if (!parts.length) {
      tb.appendChild(el("tr", {}, [
        el("td", { attrs: { colspan: "4" }, text: "Not provided by the search service." }),
      ]));
    } else {
      for (const row of parts) {
        tb.appendChild(el("tr", {}, [
          el("td", { text: row.part || "—" }),
          el("td", { text: row.note || "—" }),
          el("td", { text: row.status || "—" }),
          el("td", {}, [originMark(row.origin) || el("span", { text: "—" })]),
        ]));
      }
    }
    table.appendChild(tb);

    const seller = el("section", {}, [
      el("h3", { text: "Seller-reported fields" }),
    ]);
    const sellerFields = Array.isArray(compare.seller_reported_fields)
      ? compare.seller_reported_fields
      : [];
    if (!sellerFields.length) {
      seller.appendChild(el("p", { text: "Not provided by the search service." }));
    } else {
      const slist = el("ul");
      for (const field of sellerFields) {
        slist.appendChild(el("li", {}, [
          el("strong", { text: `${field.field || "Field"}: ` }),
          document.createTextNode(String(field.value ?? "—")),
          document.createTextNode(" "),
          originMark(field.origin || "REPORTED_BY_SELLER"),
        ]));
      }
      seller.appendChild(slist);
    }

    body.appendChild(pair);
    body.appendChild(table);
    body.appendChild(listBlock("Supporting details", compare.supporting));
    body.appendChild(listBlock("Contradictions", compare.contradictions));
    body.appendChild(listBlock("Missing views", compare.missing_views));
    body.appendChild(seller);
  }

  return {
    open(result) {
      render(result);
      if (!dialog.open) dialog.showModal();
      closeBtn.focus();
    },
    close,
    isOpen() {
      return dialog.open;
    },
  };
}
