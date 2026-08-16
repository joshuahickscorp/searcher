import { $, announce, clear, el, show, text } from "./dom.js";
import { loadRecent } from "./storage.js";

const ACCEPT = new Set(["image/jpeg", "image/png", "image/webp", "image/gif"]);
const ACCEPT_EXT = /\.(jpe?g|png|webp|gif)$/i;
const MAX_IMAGES = 10;
const MAX_BYTES = 20 * 1024 * 1024;

// Name is prefixed into the existing text field. There is no separate API field.
export function composeSearchText(name, known) {
  const titled = String(name || "").trim();
  const rest = String(known || "").trim();
  if (titled && rest) return `Name: ${titled}\n\n${rest}`;
  if (titled) return `Name: ${titled}`;
  return rest;
}

function looksLikeImage(file) {
  if (ACCEPT.has(file.type)) return true;
  if (!file.type && ACCEPT_EXT.test(file.name || "")) return true;
  return false;
}

export function createForm({ onSubmit }) {
  const form = $("search-form");
  const dropzone = $("dropzone");
  const fileInput = $("file-input");
  const thumbs = $("thumbs");
  const imageError = $("image-error");
  const itemName = $("item-name");
  const know = $("know");
  const tagInput = $("tag-input");
  const chips = $("chips");
  const searchButton = $("search-button");
  const recentList = $("recent-list");

  const files = [];
  const tags = [];

  function setError(message) {
    if (message) {
      text(imageError, message);
      show(imageError, true);
      announce(message);
    } else {
      show(imageError, false);
      text(imageError, "");
    }
  }

  function renderThumbs() {
    clear(thumbs);
    files.forEach((entry, index) => {
      const img = el("img", { alt: entry.file.name || `Selected image ${index + 1}` });
      img.src = entry.url;
      const remove = el("button", {
        type: "button",
        text: "Remove",
        "aria-label": `Remove ${entry.file.name || `image ${index + 1}`}`,
      });
      remove.addEventListener("click", (ev) => {
        ev.preventDefault();
        ev.stopPropagation();
        removeAt(index);
      });
      thumbs.appendChild(el("li", { className: "thumb" }, [img, remove]));
    });
    searchButton.disabled = files.length === 0;
  }

  function removeAt(index) {
    const [gone] = files.splice(index, 1);
    if (gone) URL.revokeObjectURL(gone.url);
    renderThumbs();
  }

  function addFiles(list) {
    const incoming = Array.from(list || []);
    if (!incoming.length) return;
    const messages = [];
    for (const file of incoming) {
      if (!looksLikeImage(file)) {
        messages.push(`${file.name || "A file"} is not a supported raster image. Use JPEG, PNG, WebP, or GIF. The server is the final validator.`);
        continue;
      }
      if (file.size > MAX_BYTES) {
        messages.push(`${file.name || "A file"} is larger than 20 MB. The server is the final validator.`);
        continue;
      }
      if (files.length >= MAX_IMAGES) {
        messages.push("A search can include at most 10 images. The server is the final validator.");
        break;
      }
      const already = files.some((held) => held.file.name === file.name && held.file.size === file.size);
      if (already) {
        messages.push(`${file.name || "That image"} is already attached.`);
        continue;
      }
      files.push({ file, url: URL.createObjectURL(file) });
    }
    setError(messages[0] || "");
    renderThumbs();
  }

  function renderTags() {
    clear(chips);
    tags.forEach((tag, index) => {
      const remove = el("button", {
        type: "button",
        text: "×",
        "aria-label": `Remove tag ${tag}`,
      });
      remove.addEventListener("click", () => {
        tags.splice(index, 1);
        renderTags();
        tagInput.focus();
      });
      chips.appendChild(el("li", { className: "chip" }, [
        el("span", { text: tag }),
        remove,
      ]));
    });
  }

  function addTag(raw) {
    const value = String(raw || "").replace(/,/g, "").trim();
    if (!value) return;
    if (!tags.includes(value)) tags.push(value);
    tagInput.value = "";
    renderTags();
  }

  function renderRecent() {
    clear(recentList);
    const rows = loadRecent();
    if (!rows.length) {
      recentList.appendChild(el("li", { text: "None yet on this device." }));
      return;
    }
    for (const row of rows) {
      const label = row.text || (row.tags && row.tags.join(", ")) || row.id;
      const link = el("a", { href: `#/search/${row.id}`, text: label });
      recentList.appendChild(el("li", {}, [link]));
    }
  }

  dropzone.addEventListener("click", (ev) => {
    if (ev.target.closest("button") || ev.target === fileInput) return;
    if (ev.target.closest("label")) return;
    fileInput.click();
  });
  fileInput.addEventListener("change", () => {
    addFiles(fileInput.files);
    fileInput.value = "";
  });
  dropzone.addEventListener("dragover", (ev) => {
    ev.preventDefault();
    dropzone.classList.add("is-dragover");
  });
  dropzone.addEventListener("dragleave", () => dropzone.classList.remove("is-dragover"));
  dropzone.addEventListener("drop", (ev) => {
    ev.preventDefault();
    dropzone.classList.remove("is-dragover");
    addFiles(ev.dataTransfer && ev.dataTransfer.files);
  });

  document.addEventListener("paste", (ev) => {
    const clip = ev.clipboardData;
    if (!clip) return;
    const pasted = Array.from(clip.files || []).filter(looksLikeImage);
    if (!pasted.length) return;
    ev.preventDefault();
    addFiles(pasted);
  });

  tagInput.addEventListener("keydown", (ev) => {
    if (ev.key === "Enter" || ev.key === ",") {
      ev.preventDefault();
      addTag(tagInput.value);
    } else if (ev.key === "Backspace" && !tagInput.value && tags.length) {
      tags.pop();
      renderTags();
    }
  });
  tagInput.addEventListener("blur", () => addTag(tagInput.value));

  form.addEventListener("submit", (ev) => {
    ev.preventDefault();
    if (!files.length) {
      setError("Add at least one image to search. The server is the final validator.");
      return;
    }
    onSubmit({
      files: files.map((row) => row.file),
      text: composeSearchText(itemName.value, know.value),
      tags: tags.slice(),
    });
  });

  renderThumbs();
  renderTags();
  renderRecent();

  return {
    renderRecent,
    getDraft() {
      return {
        name: itemName.value.trim(),
        text: know.value.trim(),
        tags: tags.slice(),
      };
    },
    setBusy(busy) {
      searchButton.disabled = busy || files.length === 0;
      searchButton.textContent = busy ? "Searching" : "Search";
    },
  };
}
