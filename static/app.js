// Configurator UI. Prices come from the server; the client never computes one,
// so a tampered page cannot change what a watch costs.

const state = {
  catalogue: null,
  selection: {},
  engraving: "",
  cart: [],
  spin: false,
  // Monotonic guard. Two rapid changes issue two requests; if the older one
  // resolves last it would overwrite the newer price on screen. Only the newest
  // request is allowed to write to the DOM.
  seq: 0,
};

const el = (id) => document.getElementById(id);
const gbp = (s) => "£" + Number(s).toFixed(2).replace(/\B(?=(\d{3})+(?!\d))/g, ",");

/* ------------------------------------------------------------------ render */
function renderGroups() {
  const host = el("groups");
  host.innerHTML = "";
  for (const g of state.catalogue.groups) {
    const fs = document.createElement("fieldset");
    fs.className = "group";
    const legend = document.createElement("legend");
    legend.textContent = g.label;
    if (!g.required) {
      const opt = document.createElement("span");
      opt.className = "opt";
      opt.textContent = "optional";
      legend.append(opt);
    }
    fs.append(legend);

    const row = document.createElement("div");
    row.className = "swatches";
    row.setAttribute("role", "radiogroup");
    row.setAttribute("aria-label", g.label);

    for (const o of g.options) {
      const label = document.createElement("label");
      label.className = "swatch";
      const input = document.createElement("input");
      input.type = "radio";
      input.name = g.id;
      input.value = o.id;
      input.checked = state.selection[g.id] === o.id;
      input.addEventListener("change", () => choose(g.id, o.id));
      const dot = document.createElement("span");
      dot.className = "dot";
      if (o.colour) dot.style.background = o.colour;
      else dot.classList.add("no-colour");
      const name = document.createElement("span");
      name.className = "swatch-label";
      name.textContent = o.label;
      label.append(input, dot, name);
      if (o.price && Number(o.price) > 0) {
        const p = document.createElement("span");
        p.className = "swatch-price";
        p.textContent = "+" + gbp(o.price);
        label.append(p);
      }
      if (o.note) label.title = o.note;
      row.append(label);
    }
    fs.append(row);
    host.append(fs);
  }
}

function syncedSelections() {
  return document.querySelectorAll(".swatch input:checked").length;
}

/* --------------------------------------------------------------- behaviour */
async function choose(groupId, optionId) {
  const next = { ...state.selection, [groupId]: optionId };
  const token = ++state.seq;
  const result = await requestQuote(next);
  if (token !== state.seq) return;          // superseded by a newer change
  if (!result.ok) {
    // Refused by the rules. Put the radio back where it was and say why.
    flash(result.error, result.field);
    const previous = document.querySelector(`input[name="${groupId}"][value="${state.selection[groupId]}"]`);
    if (previous) previous.checked = true;
    return;
  }
  state.selection = result.selection;
  renderQuote(result.quote);
  syncScene();
  updateRef();
}

function flash(message, field) {
  const note = el("price-note");
  note.textContent = message;
  note.classList.add("err");
  clearTimeout(flash._t);
  flash._t = setTimeout(() => {
    note.textContent = "incl. VAT";
    note.classList.remove("err");
  }, 4200);
  if (field) {
    const legend = [...document.querySelectorAll(".group legend")]
      .find((l) => l.textContent.toLowerCase().startsWith(field));
    if (legend) legend.parentElement.classList.add("shake"), setTimeout(() => legend.parentElement.classList.remove("shake"), 420);
  }
}

async function requestQuote(selection) {
  try {
    const res = await fetch("/api/quote", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selection }),
    });
    const data = await res.json();
    if (!res.ok) return { ok: false, error: data.error || "refused", field: data.field };
    return { ok: true, selection: data.selection, quote: data.quote };
  } catch {
    return { ok: false, error: "Cannot reach the server" };
  }
}

function renderQuote(q) {
  el("price").textContent = gbp(q.total);
  el("price-note").textContent = `incl. VAT · ${gbp(q.vat)} tax`;
  el("price-note").classList.remove("err");
}

function updateRef() {
  const initials = (id, n) => (id || "").split(".").pop().slice(0, n).toUpperCase().padEnd(n, "·");
  const parts = [
    "HEL",
    (state.selection.case || "").split(".").pop(),
    initials(state.selection.shell, 3),
    initials(state.selection.face, 3),
    initials(state.selection.strap, 3),
  ];
  el("ref").textContent = parts.join("-");
}

/* ------------------------------------------------------------------- scene */
function syncScene() {
  const find = (id) => {
    for (const g of state.catalogue.groups) for (const o of g.options) if (o.id === id) return o;
    return null;
  };
  const shell = find(state.selection.shell);
  const face = find(state.selection.face);
  const strap = find(state.selection.strap);
  const kase = find(state.selection.case);

  if (shell && shell.colour) WATCH.model.caseMat.color.set(shell.colour);
  if (shell) WATCH.model.caseMat.roughness = state.selection.shell === "shell.brass" ? 0.22 : 0.28;
  if (face && face.colour) WATCH.model.dialMat.color.set(face.colour);
  if (strap && strap.colour) WATCH.model.strapMat.color.set(strap.colour);
  if (strap) {
    WATCH.model.strapMat.metalness = state.selection.strap === "strap.steel" ? 0.9 : 0.02;
    WATCH.model.strapMat.roughness = state.selection.strap === "strap.steel" ? 0.25 : 0.85;
  }
  if (kase) {
    const scale = state.selection.case === "case.38" ? 0.94 : state.selection.case === "case.40" ? 1.0 : 1.06;
    WATCH.model.group.scale.setScalar(scale);
  }
}

/* -------------------------------------------------------------------- cart */
async function addToBag() {
  const line = {
    sku: "helio-watch",
    selection: state.selection,
    engraving: state.engraving,
    qty: 1,
  };
  const res = await fetch("/api/cart", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lines: [...state.cart, line] }),
  });
  const data = await res.json();
  if (!res.ok) {
    el("cart-note").textContent = data.error;
    el("cart-note").classList.add("err");
    return;
  }
  state.cart.push(line);
  el("cart-note").classList.remove("err");
  el("cart-note").textContent = `${state.cart.length} item(s) · ${gbp(data.total.total)}`;
}

/* -------------------------------------------------------------------- init */
async function boot() {
  WATCH.model = WATCH.makeWatch(window.__scene);

  const res = await fetch("/api/catalogue");
  state.catalogue = await res.json();

  // Defaults: first option of every group, which is the no-cost specification.
  for (const g of state.catalogue.groups) state.selection[g.id] = g.options[0].id;
  renderGroups();
  syncScene();
  updateRef();

  // The initial quote goes through the same guard as a click: on a slow link it
  // can resolve *after* the customer has already changed an option, and an
  // unguarded write would repaint the base price over their choice.
  const bootToken = ++state.seq;
  const q = await requestQuote(state.selection);
  if (bootToken === state.seq && q.ok) renderQuote(q.quote);

  el("add").addEventListener("click", addToBag);

  const engraving = el("engraving");
  engraving.addEventListener("input", async () => {
    el("eng-count").textContent = String(engraving.value.length);
    state.engraving = engraving.value.trim();
    // Entering text implies the paid engraving option.
    if (state.engraving && state.selection.engraving !== "engraving.text") {
      const token = ++state.seq;
      const r = await requestQuote({ ...state.selection, engraving: "engraving.text" });
      if (token !== state.seq) return;
      if (r.ok) {
        state.selection = r.selection;
        renderQuote(r.quote);
        updateRef();
        document.querySelector('input[name="engraving"][value="engraving.text"]').checked = true;
      } else {
        engraving.value = "";
        state.engraving = "";
        flash(r.error, "engraving");
      }
    } else if (!state.engraving && state.selection.engraving === "engraving.text") {
      const token = ++state.seq;
      const r = await requestQuote({ ...state.selection, engraving: "engraving.none" });
      if (token !== state.seq) return;
      if (r.ok) {
        state.selection = r.selection;
        renderQuote(r.quote);
        document.querySelector('input[name="engraving"][value="engraving.none"]').checked = true;
      }
    }
  });

  el("spin").addEventListener("click", (e) => {
    state.spin = !state.spin;
    window.__spin = state.spin;   // published for the render loop
    e.currentTarget.setAttribute("aria-pressed", String(state.spin));
    e.currentTarget.classList.toggle("on", state.spin);
  });

  document.documentElement.dataset.ready = "true";
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
