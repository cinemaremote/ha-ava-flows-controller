/*
 * AVA Flows card for AVA Flows Controller (Unofficial).
 * Run flows, give them friendly names, copy their run URLs, and export the list.
 * Names are saved in Home Assistant only; nothing is changed on the AVA Brain.
 */

const DOMAIN = "ava_flows_controller";

const STYLE = `
  :host { display: block; }
  ha-card { padding-bottom: 8px; overflow: hidden; }
  .header {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    padding: 12px 8px 0 16px; min-height: 44px;
  }
  .title {
    font-size: var(--ha-card-header-font-size, 24px); line-height: 1.2;
    color: var(--ha-card-header-color, var(--primary-text-color));
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }
  .brain {
    padding: 16px 16px 0; font-size: 15px; font-weight: 500;
    color: var(--primary-text-color);
  }
  .section {
    padding: 14px 16px 4px; font-size: 12px; font-weight: 500;
    letter-spacing: 0.06em; text-transform: uppercase;
    color: var(--secondary-text-color);
  }
  .row { display: flex; align-items: center; gap: 2px; padding: 0 8px 0 4px; }
  .row.off { opacity: 0.45; }
  button { font: inherit; color: inherit; }
  .run {
    flex: 1; min-width: 0; display: flex; align-items: center; gap: 14px;
    min-height: 48px; padding: 4px 8px 4px 12px; background: none; border: 0;
    border-radius: 8px; color: var(--primary-text-color); text-align: left; cursor: pointer;
  }
  .run:hover:not(:disabled) { background: var(--secondary-background-color); }
  .run:disabled { cursor: default; }
  .run ha-icon { flex: none; --mdc-icon-size: 24px; }
  .launch .run ha-icon { color: var(--primary-color); }
  .power .run ha-icon { color: var(--warning-color, #ff9800); }
  .text { display: flex; flex-direction: column; min-width: 0; }
  .name { font-size: 15px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .sub {
    font-size: 12px; color: var(--secondary-text-color);
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
  }
  .icon-btn {
    flex: none; width: 44px; height: 44px; display: flex; align-items: center;
    justify-content: center; background: none; border: 0; border-radius: 50%;
    color: var(--secondary-text-color); cursor: pointer; --mdc-icon-size: 20px;
  }
  .icon-btn:hover { background: var(--secondary-background-color); color: var(--primary-text-color); }
  .icon-btn.done { color: var(--success-color, #43a047); }
  .url { padding: 0 16px 8px 54px; }
  .url input {
    width: 100%; box-sizing: border-box; height: 36px; padding: 0 10px; font: inherit;
    font-size: 12px; color: var(--primary-text-color); background: var(--secondary-background-color);
    border: 1px solid var(--divider-color); border-radius: 6px;
  }
  .edit {
    margin: 4px 12px; padding: 10px; border-radius: 10px;
    background: var(--secondary-background-color); border: 1px solid var(--primary-color);
  }
  .edit label { display: block; font-size: 12px; color: var(--secondary-text-color); margin: 0 0 6px 2px; }
  .edit-row { display: flex; align-items: center; gap: 6px; }
  .edit input {
    flex: 1; min-width: 0; height: 44px; box-sizing: border-box; padding: 0 12px;
    font: inherit; font-size: 15px; color: var(--primary-text-color);
    background: var(--card-background-color, var(--primary-background-color));
    border: 1px solid var(--divider-color); border-radius: 8px;
  }
  .edit input:focus { outline: 2px solid var(--primary-color); outline-offset: -1px; }
  .square {
    flex: none; width: 44px; height: 44px; display: flex; align-items: center; justify-content: center;
    border-radius: 8px; cursor: pointer; --mdc-icon-size: 20px;
  }
  .save { background: var(--primary-color); color: var(--text-primary-color, #fff); border: 0; }
  .cancel { background: none; border: 1px solid var(--divider-color); color: var(--primary-text-color); }
  .edit-foot {
    display: flex; align-items: center; justify-content: space-between; gap: 8px;
    margin-top: 6px; font-size: 12px; color: var(--secondary-text-color);
  }
  .edit-foot span { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .reset {
    flex: none; min-height: 32px; padding: 0 4px; background: none; border: 0;
    color: var(--primary-color); font-size: 12px; font-weight: 500; cursor: pointer;
  }
  .empty { padding: 16px; color: var(--secondary-text-color); }
`;

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[c]);
}

function matches(wanted, values) {
  const w = String(wanted).trim().toLowerCase();
  return values.some((v) => v != null && String(v).toLowerCase() === w);
}

function byName(a, b) {
  return a.name.localeCompare(b.name, undefined, { sensitivity: "base", numeric: true });
}

async function copyText(text) {
  if (navigator.clipboard && window.isSecureContext) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (err) {
      /* fall back below */
    }
  }
  // Plain http:// pages can't use the clipboard API; this older method still works.
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.top = "-1000px";
  document.body.appendChild(area);
  area.select();
  let ok = false;
  try {
    ok = document.execCommand("copy");
  } catch (err) {
    ok = false;
  }
  document.body.removeChild(area);
  return ok;
}

function download(filename, text) {
  const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  setTimeout(() => {
    URL.revokeObjectURL(link.href);
    link.remove();
  }, 1000);
}

class AvaFlowsCard extends HTMLElement {
  static getStubConfig() {
    return {};
  }

  setConfig(config) {
    this._config = { show_power_off: true, ...(config || {}) };
    this._sig = undefined;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    const sig = JSON.stringify(this._flows());
    if (sig === this._sig) return;
    this._sig = sig;
    if (this._editing) {
      this._stale = true; // re-render after editing so the text box isn't reset
      return;
    }
    this._render();
  }

  getCardSize() {
    return Math.max(2, Math.ceil(this._flows().length * 0.9) + 1);
  }

  getGridOptions() {
    return { columns: 6, min_columns: 4 };
  }

  _flows() {
    if (!this._hass || !this._config) return [];
    const c = this._config;
    const exclude = new Set(c.exclude || []);
    const out = [];
    for (const state of Object.values(this._hass.states)) {
      if (!state.entity_id.startsWith("button.")) continue;
      const a = state.attributes || {};
      if (a.recipe_key === undefined || !("run_url" in a)) continue;
      if (exclude.has(state.entity_id)) continue;
      if (c.brain && !matches(c.brain, [a.brain, a.brain_id])) continue;
      if (c.room && !matches(c.room, [a.room])) continue;
      const power = a.flow_type === "poweroff";
      if (power && c.show_power_off === false) continue;
      out.push({
        id: state.entity_id,
        name: a.custom_name || a.default_name || a.friendly_name || state.entity_id,
        defaultName: a.default_name || "",
        custom: Boolean(a.custom_name),
        ava: a.ava_name || "",
        power,
        url: a.run_url || "",
        brain: a.brain || "AVA",
        room: a.room || "",
        off: state.state === "unavailable",
      });
    }
    return out;
  }

  _toast(message) {
    this.dispatchEvent(
      new CustomEvent("hass-notification", { detail: { message }, bubbles: true, composed: true })
    );
  }

  _setup() {
    if (this.shadowRoot) return;
    this.attachShadow({ mode: "open" });
    this.shadowRoot.addEventListener("click", (ev) => this._onClick(ev));
    this.shadowRoot.addEventListener("keydown", (ev) => this._onKey(ev));
    this.shadowRoot.addEventListener("input", (ev) => {
      if (ev.target.classList && ev.target.classList.contains("name-input")) {
        this._draft = ev.target.value;
      }
    });
  }

  _rowHtml(f) {
    if (this._editing === f.id) {
      return `
        <div class="edit">
          <label for="name-input">Name on this card</label>
          <div class="edit-row">
            <input id="name-input" class="name-input" type="text" value="${esc(this._draft)}"
              aria-label="New name for ${esc(f.name)}" autocomplete="off">
            <button class="square save" data-action="save" data-id="${esc(f.id)}" aria-label="Save name" title="Save">
              <ha-icon icon="mdi:check"></ha-icon></button>
            <button class="square cancel" data-action="cancel" aria-label="Cancel" title="Cancel">
              <ha-icon icon="mdi:close"></ha-icon></button>
          </div>
          <div class="edit-foot">
            <span>AVA name: ${esc(f.ava)}</span>
            ${f.custom ? `<button class="reset" data-action="reset" data-id="${esc(f.id)}">Use default name</button>` : ""}
          </div>
        </div>`;
    }
    const copied = this._copied === f.id;
    return `
      <div class="row ${f.power ? "power" : "launch"} ${f.off ? "off" : ""}">
        <button class="run" data-action="run" data-id="${esc(f.id)}" ${f.off ? "disabled" : ""}
          title="Run ${esc(f.name)}">
          <ha-icon icon="${f.power ? "mdi:power" : "mdi:play-circle-outline"}"></ha-icon>
          <span class="text">
            <span class="name">${esc(f.name)}</span>
            ${f.custom ? `<span class="sub">AVA: ${esc(f.ava)}</span>` : ""}
          </span>
        </button>
        <button class="icon-btn ${copied ? "done" : ""}" data-action="copy" data-id="${esc(f.id)}"
          aria-label="Copy run URL for ${esc(f.name)}" title="Copy run URL" ${f.url ? "" : "disabled"}>
          <ha-icon icon="${copied ? "mdi:check" : "mdi:content-copy"}"></ha-icon></button>
        <button class="icon-btn" data-action="edit" data-id="${esc(f.id)}"
          aria-label="Rename ${esc(f.name)}" title="Rename">
          <ha-icon icon="mdi:pencil"></ha-icon></button>
      </div>
      ${this._showUrl === f.id ? `<div class="url"><input readonly value="${esc(f.url)}" aria-label="Run URL"></div>` : ""}`;
  }

  _render() {
    if (!this._config || !this._hass) return;
    this._setup();
    this._stale = false;
    const flows = this._flows();
    const c = this._config;

    const brains = [...new Set(flows.map((f) => f.brain))].sort((a, b) => a.localeCompare(b));
    const title = c.title !== undefined ? c.title : brains.length === 1 ? brains[0] : "AVA Flows";
    const multiBrain = brains.length > 1;

    let body = "";
    if (!flows.length) {
      body = `<div class="empty">No AVA flows found. Add the AVA Flows Controller integration, or check the card's brain and room settings.</div>`;
    }
    for (const brain of brains) {
      const inBrain = flows.filter((f) => f.brain === brain);
      if (multiBrain) body += `<div class="brain">${esc(brain)}</div>`;
      const rooms = [...new Set(inBrain.map((f) => f.room))].sort((a, b) => a.localeCompare(b));
      const multiRoom = rooms.length > 1;
      for (const room of rooms) {
        for (const power of [false, true]) {
          const group = inBrain.filter((f) => f.room === room && f.power === power).sort(byName);
          if (!group.length) continue;
          const label = power ? "Power off" : "Launch";
          body += `<div class="section">${multiRoom && room ? `${esc(room)} · ` : ""}${label}</div>`;
          body += group.map((f) => this._rowHtml(f)).join("");
        }
      }
    }

    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <ha-card>
        <div class="header">
          <div class="title">${esc(title || "")}</div>
          <button class="icon-btn" data-action="export" aria-label="Export flows to a text file"
            title="Export flows" ${flows.length ? "" : "disabled"}>
            <ha-icon icon="mdi:file-export-outline"></ha-icon></button>
        </div>
        ${body}
      </ha-card>`;

    if (this._focusInput) {
      this._focusInput = false;
      const input = this.shadowRoot.querySelector(".name-input");
      if (input) {
        input.focus();
        input.select();
      }
    }
    if (this._showUrl) {
      const urlInput = this.shadowRoot.querySelector(".url input");
      if (urlInput) urlInput.select();
    }
  }

  _flow(id) {
    return this._flows().find((f) => f.id === id);
  }

  async _onClick(ev) {
    const el = ev.target.closest("[data-action]");
    if (!el || el.disabled) return;
    const id = el.dataset.id;
    switch (el.dataset.action) {
      case "run":
        return this._run(id);
      case "copy":
        return this._copy(id);
      case "edit": {
        const f = this._flow(id);
        if (!f) return;
        this._editing = id;
        this._draft = f.name;
        this._showUrl = null;
        this._focusInput = true;
        return this._render();
      }
      case "save":
        return this._save(id, this._draft);
      case "cancel":
        return this._stopEditing();
      case "reset":
        return this._save(id, "");
      case "export":
        return this._export();
      default:
        return undefined;
    }
  }

  _onKey(ev) {
    if (!ev.target.classList || !ev.target.classList.contains("name-input")) return;
    if (ev.key === "Enter") {
      ev.preventDefault();
      this._save(this._editing, ev.target.value);
    } else if (ev.key === "Escape") {
      ev.preventDefault();
      this._stopEditing();
    }
  }

  _stopEditing() {
    this._editing = null;
    this._draft = "";
    this._render();
  }

  async _run(id) {
    const f = this._flow(id);
    if (!f) return;
    try {
      await this._hass.callService("button", "press", { entity_id: id });
      this._toast(`Ran ${f.name}`);
    } catch (err) {
      this._toast(`Couldn't run ${f.name}: ${err.message || err}`);
    }
  }

  async _copy(id) {
    const f = this._flow(id);
    if (!f || !f.url) return;
    if (await copyText(f.url)) {
      this._copied = id;
      this._showUrl = null;
      this._toast(`Copied the run URL for ${f.name}`);
      this._render();
      clearTimeout(this._copiedTimer);
      this._copiedTimer = setTimeout(() => {
        this._copied = null;
        if (!this._editing) this._render();
      }, 1500);
    } else {
      // Couldn't reach the clipboard: show the URL, selected, to copy by hand.
      this._showUrl = id;
      this._toast("Select the URL and copy it");
      this._render();
    }
  }

  async _save(id, name) {
    if (!id) return;
    try {
      await this._hass.callService(DOMAIN, "rename_flow", { entity_id: id, name: (name || "").trim() });
    } catch (err) {
      this._toast(`Couldn't rename: ${err.message || err}`);
      return;
    }
    this._editing = null;
    this._draft = "";
    this._render();
  }

  async _export() {
    const data = { save_file: false };
    if (this._config.brain) data.brain = this._config.brain;
    try {
      const result = await this._hass.connection.sendMessagePromise({
        type: "call_service",
        domain: DOMAIN,
        service: "export_flows",
        service_data: data,
        return_response: true,
      });
      const response = (result && result.response) || {};
      download(response.filename || "ava_flows_export.txt", response.text || "");
    } catch (err) {
      this._toast(`Couldn't export: ${err.message || err}`);
    }
  }
}

const PANEL_STYLE = `
  :host {
    display: block; min-height: 100vh;
    background: var(--primary-background-color);
    color: var(--primary-text-color);
  }
  .toolbar {
    display: flex; align-items: center; gap: 4px; box-sizing: border-box;
    height: var(--header-height, 56px); padding: 0 12px 0 4px;
    background: var(--app-header-background-color, var(--primary-color));
    color: var(--app-header-text-color, var(--text-primary-color, #fff));
    border-bottom: var(--app-header-border-bottom, none);
    font-size: 20px;
  }
  .toolbar .main-title { margin-left: 12px; }
  .content { box-sizing: border-box; max-width: 720px; margin: 0 auto; padding: 16px; }
`;

/* Full page shown from the "AVA Flows" sidebar entry. */
class AvaFlowsPanel extends HTMLElement {
  set hass(hass) {
    this._hass = hass;
    this._build();
    this._menu.hass = hass;
    this._card.hass = hass;
  }

  set narrow(narrow) {
    this._narrow = narrow;
    if (this._menu) this._menu.narrow = narrow;
  }

  set panel(panel) {
    this._panel = panel;
  }

  _build() {
    if (this._card) return;
    this.attachShadow({ mode: "open" });
    this.shadowRoot.innerHTML = `
      <style>${PANEL_STYLE}</style>
      <div class="toolbar">
        <ha-menu-button></ha-menu-button>
        <div class="main-title">AVA Flows</div>
      </div>
      <div class="content"></div>`;
    this._menu = this.shadowRoot.querySelector("ha-menu-button");
    this._menu.narrow = this._narrow;
    this._card = document.createElement("ava-flows-card");
    this._card.setConfig({});
    this.shadowRoot.querySelector(".content").appendChild(this._card);
  }
}

if (!customElements.get("ava-flows-panel")) {
  customElements.define("ava-flows-panel", AvaFlowsPanel);
}

if (!customElements.get("ava-flows-card")) {
  customElements.define("ava-flows-card", AvaFlowsCard);
  window.customCards = window.customCards || [];
  window.customCards.push({
    type: "ava-flows-card",
    name: "AVA Flows",
    description: "Run AVA flows, rename them, copy their run URLs and export the list.",
    preview: false,
  });
}
