/*
 * Labs Experience Controller — Spaces sidebar panel.
 *
 * Self-contained web component (no build step): lists every space grouped
 * by area with live phase, experience, daypart, and authority, plus quick
 * actions (set experience, resume automatic, pause automation).
 */

const PHASE_OPTIONS = "vacant,waking,occupied,cooldown";

const PHASE_COLORS = {
  vacant: "var(--disabled-text-color, #9e9e9e)",
  waking: "var(--warning-color, #ffa726)",
  occupied: "var(--success-color, #66bb6a)",
  cooldown: "var(--info-color, #29b6f6)",
};

const PHASES = ["vacant", "waking", "occupied", "cooldown"];

class LabsExperiencePanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._areaByEntity = null;
    this._signature = "";
    this._expanded = new Set();
  }

  set hass(hass) {
    this._hass = hass;
    if (this._areaByEntity === null) {
      this._areaByEntity = {};
      this._loadRegistry();
    }
    this._maybeRender();
  }

  async _loadRegistry() {
    try {
      const [areas, devices, entities] = await Promise.all([
        this._hass.callWS({ type: "config/area_registry/list" }),
        this._hass.callWS({ type: "config/device_registry/list" }),
        this._hass.callWS({ type: "config/entity_registry/list" }),
      ]);
      const areaNames = {};
      for (const area of areas) areaNames[area.area_id] = area.name;
      const deviceArea = {};
      for (const device of devices) deviceArea[device.id] = device.area_id;
      const map = {};
      for (const entity of entities) {
        const areaId = entity.area_id || deviceArea[entity.device_id];
        if (areaId) map[entity.entity_id] = areaNames[areaId] || "Other";
      }
      this._areaByEntity = map;
      this._signature = "";
      this._maybeRender();
    } catch (err) {
      // Registry access failed (rare); grouping falls back to "Spaces".
      this._areaByEntity = {};
    }
  }

  _spaces() {
    const states = this._hass.states;
    const spaces = [];
    for (const entityId of Object.keys(states)) {
      if (!entityId.startsWith("sensor.") || !entityId.endsWith("_phase")) {
        continue;
      }
      const phase = states[entityId];
      const options = phase.attributes.options || [];
      if (options.join(",") !== PHASE_OPTIONS) continue;
      const base = entityId.slice("sensor.".length, -"_phase".length);
      const select = states[`select.${base}_experience`];
      if (!select) continue;
      spaces.push({
        base,
        name: phase.attributes.friendly_name
          ? phase.attributes.friendly_name.replace(/ Phase$/i, "")
          : base,
        phase,
        select,
        daypart: states[`sensor.${base}_daypart`],
        automation: states[`switch.${base}_automation`],
        area: this._areaByEntity[entityId] || "Spaces",
      });
    }
    spaces.sort((a, b) =>
      a.area === b.area
        ? a.name.localeCompare(b.name)
        : a.area.localeCompare(b.area)
    );
    return spaces;
  }

  _maybeRender() {
    if (!this._hass) return;
    const spaces = this._spaces();
    const signature = spaces
      .map((space) => {
        let sig =
          `${space.base}|${space.phase.state}|${space.select.state}|` +
          `${space.select.attributes.override}|` +
          `${space.phase.attributes.lighting}|` +
          `${space.daypart ? space.daypart.state : ""}|` +
          `${space.automation ? space.automation.state : ""}|${space.area}|` +
          `${this._expanded.has(space.base) ? 1 : 0}`;
        if (this._expanded.has(space.base)) {
          for (const def of space.select.attributes.states || []) {
            for (const entityId of def.evidence || []) {
              const st = this._hass.states[entityId];
              sig += `|${entityId}=${st ? st.state : "?"}`;
            }
          }
        }
        return sig;
      })
      .join(";");
    if (signature === this._signature) return;
    this._signature = signature;
    this._render(spaces);
  }

  _render(spaces) {
    const groups = {};
    for (const space of spaces) {
      (groups[space.area] = groups[space.area] || []).push(space);
    }
    const root = this.shadowRoot;
    root.innerHTML = `
      <style>
        :host { display: block; padding: 16px; max-width: 960px; margin: 0 auto;
          font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
          color: var(--primary-text-color); }
        h1 { font-size: 22px; font-weight: 400; margin: 8px 0 16px; }
        h2 { font-size: 14px; text-transform: uppercase; letter-spacing: 0.1em;
          color: var(--secondary-text-color); margin: 20px 0 8px; }
        .space { display: flex; align-items: center; gap: 12px; padding: 12px 16px;
          background: var(--card-background-color, #fff); border-radius: 12px;
          margin-bottom: 8px; box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.2)); }
        .name { flex: 1; min-width: 120px; font-weight: 500; }
        .phase { font-size: 12px; padding: 3px 10px; border-radius: 10px;
          color: #fff; text-transform: capitalize; }
        .meta { font-size: 12px; color: var(--secondary-text-color); min-width: 60px; }
        select { padding: 6px 8px; border-radius: 8px;
          border: 1px solid var(--divider-color, #ccc);
          background: var(--card-background-color, #fff);
          color: var(--primary-text-color); }
        select:disabled { opacity: 0.5; }
        button { border: none; background: none; cursor: pointer; font-size: 16px;
          padding: 6px; border-radius: 8px; color: var(--primary-color); }
        button:hover { background: var(--secondary-background-color); }
        .paused { opacity: 0.55; }
        .empty { color: var(--secondary-text-color); padding: 24px; text-align: center; }
        .card { background: var(--card-background-color, #fff); border-radius: 12px;
          margin-bottom: 8px; box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0,0,0,.2)); }
        .card .space { box-shadow: none; margin: 0; background: none; }
        .detail { padding: 4px 16px 14px; border-top: 1px solid var(--divider-color, #eee); }
        .flow { display: flex; align-items: center; gap: 6px; margin: 10px 0 14px;
          font-size: 12px; text-transform: capitalize; }
        .flow .step { padding: 3px 10px; border-radius: 10px;
          background: var(--secondary-background-color); color: var(--secondary-text-color); }
        .flow .step.now { color: #fff; font-weight: 600; }
        .flow .arrow { color: var(--secondary-text-color); }
        .ladder { display: flex; flex-direction: column; gap: 6px; }
        .rung { display: flex; align-items: center; gap: 8px; padding: 8px 10px;
          border-radius: 10px; border: 1px solid var(--divider-color, #e0e0e0); }
        .rung.live { border-color: var(--success-color, #66bb6a);
          background: color-mix(in srgb, var(--success-color, #66bb6a) 8%, transparent); }
        .rung .prio { font-size: 11px; min-width: 26px; text-align: center;
          border-radius: 8px; background: var(--secondary-background-color);
          color: var(--secondary-text-color); padding: 2px 4px; }
        .rung .sname { font-weight: 500; min-width: 110px; }
        .chip { font-size: 11px; padding: 2px 8px; border-radius: 8px;
          background: var(--secondary-background-color);
          color: var(--secondary-text-color); }
        .chip.match { background: var(--success-color, #66bb6a); color: #fff; }
        .chips { flex: 1; display: flex; flex-wrap: wrap; gap: 4px; }
        .try { font-size: 12px; border: 1px solid var(--primary-color);
          padding: 3px 10px; border-radius: 8px; }
        .detail .toolbar { display: flex; justify-content: flex-end; gap: 8px; margin-top: 10px; }
        .linkish { font-size: 12px; color: var(--primary-color); }
      </style>
      <h1>Spaces</h1>
      <div id="content"></div>
    `;
    const content = root.getElementById("content");
    if (!spaces.length) {
      content.innerHTML =
        '<div class="empty">No spaces yet — add one via Settings → Devices & services → Labs Experience Controller.</div>';
      return;
    }
    for (const [area, group] of Object.entries(groups)) {
      const heading = document.createElement("h2");
      heading.textContent = area;
      content.appendChild(heading);
      for (const space of group) {
        const card = document.createElement("div");
        card.className = "card";
        card.appendChild(this._renderSpace(space));
        if (this._expanded.has(space.base)) {
          card.appendChild(this._renderDetail(space));
        }
        content.appendChild(card);
      }
    }
  }

  _navigate(path) {
    history.pushState(null, "", path);
    window.dispatchEvent(new CustomEvent("location-changed"));
  }

  _renderDetail(space) {
    const detail = document.createElement("div");
    detail.className = "detail";

    // Occupancy lifecycle: where the space is on its path right now.
    const flow = document.createElement("div");
    flow.className = "flow";
    PHASES.forEach((phase, index) => {
      if (index) {
        const arrow = document.createElement("span");
        arrow.className = "arrow";
        arrow.textContent = "→";
        flow.appendChild(arrow);
      }
      const step = document.createElement("span");
      step.className = "step" + (space.phase.state === phase ? " now" : "");
      if (space.phase.state === phase) {
        step.style.background = PHASE_COLORS[phase] || "#888";
      }
      step.textContent = phase;
      flow.appendChild(step);
    });
    detail.appendChild(flow);

    // The state ladder: priority-ranked, live evidence, one-tap testing.
    const ladder = document.createElement("div");
    ladder.className = "ladder";
    const activeId = space.select.attributes.state_id;
    for (const def of space.select.attributes.states || []) {
      const rung = document.createElement("div");
      rung.className = "rung" + (def.id === activeId ? " live" : "");

      const prio = document.createElement("span");
      prio.className = "prio";
      prio.textContent = def.priority;
      rung.appendChild(prio);

      const sname = document.createElement("span");
      sname.className = "sname";
      sname.textContent = def.name + (def.hold ? " ⏳" : "");
      rung.appendChild(sname);

      const chips = document.createElement("span");
      chips.className = "chips";
      for (const entityId of def.evidence || []) {
        const chip = document.createElement("span");
        const st = this._hass.states[entityId];
        const matched =
          st && (def.active || []).includes(st.state.toLowerCase());
        chip.className = "chip" + (matched ? " match" : "");
        chip.title = entityId;
        chip.textContent = st
          ? `${st.attributes.friendly_name || entityId}: ${st.state}`
          : entityId;
        chips.appendChild(chip);
      }
      if (!(def.evidence || []).length) {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = "baseline";
        chips.appendChild(chip);
      }
      for (const daypart of def.dayparts || []) {
        const chip = document.createElement("span");
        chip.className = "chip";
        chip.textContent = daypart;
        chips.appendChild(chip);
      }
      rung.appendChild(chips);

      const tryBtn = document.createElement("button");
      tryBtn.className = "try";
      tryBtn.textContent = def.id === activeId ? "active" : "try";
      tryBtn.disabled = def.id === activeId;
      tryBtn.addEventListener("click", () =>
        this._hass.callService("labs_experience", "set_state", {
          entity_id: space.select.entity_id,
          state: def.id,
        })
      );
      rung.appendChild(tryBtn);
      ladder.appendChild(rung);
    }
    detail.appendChild(ladder);

    const toolbar = document.createElement("div");
    toolbar.className = "toolbar";
    const edit = document.createElement("button");
    edit.className = "linkish";
    edit.textContent = "Edit states, profile & controls →";
    edit.addEventListener("click", () =>
      this._navigate("/config/integrations/integration/labs_experience")
    );
    toolbar.appendChild(edit);
    detail.appendChild(toolbar);
    return detail;
  }

  _renderSpace(space) {
    const row = document.createElement("div");
    const paused = space.automation && space.automation.state === "off";
    row.className = "space" + (paused ? " paused" : "");

    const name = document.createElement("span");
    name.className = "name";
    name.textContent = space.name;
    name.style.cursor = "pointer";
    name.addEventListener("click", () => {
      if (this._expanded.has(space.base)) {
        this._expanded.delete(space.base);
      } else {
        this._expanded.add(space.base);
      }
      this._signature = "";
      this._maybeRender();
    });
    row.appendChild(name);

    const phase = document.createElement("span");
    phase.className = "phase";
    phase.style.background = PHASE_COLORS[space.phase.state] || "#888";
    phase.textContent = space.phase.state;
    row.appendChild(phase);

    const daypart = document.createElement("span");
    daypart.className = "meta";
    daypart.textContent = space.daypart ? space.daypart.state : "";
    row.appendChild(daypart);

    const lighting = document.createElement("span");
    lighting.className = "meta";
    lighting.textContent =
      space.phase.attributes.lighting === "manual" ? "🖐 manual" : "";
    row.appendChild(lighting);

    const picker = document.createElement("select");
    const available = space.select.state !== "unavailable";
    picker.disabled = !available;
    const options = space.select.attributes.options || [];
    for (const option of options) {
      const el = document.createElement("option");
      el.value = option;
      el.textContent = option;
      el.selected = option === space.select.state;
      picker.appendChild(el);
    }
    picker.addEventListener("change", () =>
      this._hass.callService("select", "select_option", {
        entity_id: space.select.entity_id,
        option: picker.value,
      })
    );
    row.appendChild(picker);

    const resume = document.createElement("button");
    resume.title = "Resume automatic";
    resume.textContent = "▶";
    resume.addEventListener("click", () =>
      this._hass.callService("button", "press", {
        entity_id: `button.${space.base}_resume_automatic`,
      })
    );
    row.appendChild(resume);

    if (space.automation) {
      const pause = document.createElement("button");
      pause.title = paused ? "Enable automation" : "Pause automation";
      pause.textContent = paused ? "⏻" : "⏸";
      pause.addEventListener("click", () =>
        this._hass.callService("switch", "toggle", {
          entity_id: space.automation.entity_id,
        })
      );
      row.appendChild(pause);
    }
    return row;
  }
}

customElements.define("labs-experience-panel", LabsExperiencePanel);
