const EVENT_NAMES = [
  "search.state",
  "search.progress",
  "search.coverage",
  "candidate.discovered",
  "candidate.normalized",
  "candidate.promoted",
  "candidate.updated",
  "result.real",
  "result.possibly_real",
  "result.replica",
  "result.removed",
  "search.warning",
  "search.complete",
];

export function createApi(getBase) {
  function root() {
    return String(getBase() || "").replace(/\/$/, "");
  }

  async function request(path, options = {}) {
    const url = `${root()}${path}`;
    let response;
    try {
      response = await fetch(url, {
        ...options,
        headers: options.headers,
      });
    } catch (err) {
      const error = new Error("The search service is unavailable.");
      error.code = "unavailable";
      error.cause = err;
      throw error;
    }
    if (response.status === 204) return null;
    const text = await response.text();
    let body = null;
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = { raw: text };
      }
    }
    if (!response.ok) {
      const error = new Error(
        (body && (body.detail || body.error)) || `Request failed (${response.status})`,
      );
      error.status = response.status;
      error.body = body;
      if (response.status === 404) error.code = "not_found";
      throw error;
    }
    return body;
  }

  return {
    root,
    health() {
      return request("/v1/health");
    },
    capabilities() {
      return request("/v1/capabilities");
    },
    createSearch(formData) {
      return request("/v1/searches", { method: "POST", body: formData });
    },
    getSearch(id) {
      return request(`/v1/searches/${encodeURIComponent(id)}`);
    },
    getResults(id, bucket) {
      const q = bucket ? `?bucket=${encodeURIComponent(bucket)}` : "";
      return request(`/v1/searches/${encodeURIComponent(id)}/results${q}`);
    },
    getResult(id) {
      return request(`/v1/results/${encodeURIComponent(id)}`);
    },
    cancel(id) {
      return request(`/v1/searches/${encodeURIComponent(id)}/cancel`, { method: "POST" });
    },
    deleteSearch(id) {
      return request(`/v1/searches/${encodeURIComponent(id)}`, { method: "DELETE" });
    },
    openEvents(id, handlers) {
      const url = `${root()}/v1/searches/${encodeURIComponent(id)}/events`;
      const source = new EventSource(url);
      const listeners = [];
      for (const name of EVENT_NAMES) {
        const fn = (ev) => {
          let data = {};
          try {
            data = ev.data ? JSON.parse(ev.data) : {};
          } catch {
            data = { raw: ev.data };
          }
          if (typeof handlers.onEvent === "function") handlers.onEvent(name, data, ev);
        };
        source.addEventListener(name, fn);
        listeners.push([name, fn]);
      }
      source.addEventListener("open", () => {
        if (handlers.onOpen) handlers.onOpen();
      });
      source.addEventListener("error", () => {
        if (handlers.onError) handlers.onError();
      });
      return {
        close() {
          for (const [name, fn] of listeners) source.removeEventListener(name, fn);
          source.close();
        },
      };
    },
  };
}
