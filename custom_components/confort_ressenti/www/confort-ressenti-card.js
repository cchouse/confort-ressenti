/* Carte « Confort ressenti » — chargée automatiquement par l'intégration.
 * Montre ce que l'intégration comprend et apprend : ressenti, murs estimés, tendance,
 * courbe 24 h, progression de l'apprentissage par plage, « Pourquoi ? » et derniers appuis. */
const VERSION = "0.3.0";

const fmt = (x, n = 1) => (x === null || x === undefined || Number.isNaN(x)) ? "–" : Number(x).toFixed(n).replace(".", ",");
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const MOTS = { froid: "Froid", frais: "Un peu frais", bien: "Bien", doux: "Un peu chaud", chaud: "Chaud" };
const ICONES = { froid: "❄", frais: "❄", bien: "✓", doux: "☀", chaud: "☀" };
const PLAGE_COURT = { nuit: "Nuit", matin: "Matin", apres_midi: "Après-midi", soir: "Soir" };

const STYLE = `
:host { display:block; }
ha-card { padding:16px; font-family: var(--ha-card-font-family, inherit); }
* { box-sizing:border-box; }
.tete { display:flex; align-items:center; justify-content:space-between; gap:8px; margin-bottom:8px; }
.piece { font-size:1.1rem; font-weight:600; color:var(--primary-text-color); }
.chip { font-size:.8rem; padding:4px 10px; border-radius:999px; border:1px solid var(--divider-color); color:var(--secondary-text-color); white-space:nowrap; }
.alerte { margin:8px 0; padding:10px 12px; border-radius:12px; border:2px solid var(--warning-color,#b26a00); color:var(--primary-text-color); font-size:.9rem; }
.verdict { display:flex; align-items:baseline; gap:10px; flex-wrap:wrap; margin:4px 0 2px; }
.mot { font-size:1.9rem; font-weight:600; line-height:1.15; color:var(--primary-text-color); }
.mot .ic { margin-right:6px; }
.detail { color:var(--secondary-text-color); font-size:.9rem; line-height:1.45; }
.detail b { color:var(--primary-text-color); font-weight:600; }
.echelle { position:relative; height:44px; margin:14px 4px 4px; }
.rail { position:absolute; left:0; right:0; top:18px; height:8px; border-radius:4px; background:var(--divider-color); }
.zone { position:absolute; top:12px; height:20px; border-radius:6px; background:color-mix(in srgb, var(--primary-color) 22%, transparent); border:2px solid var(--primary-color); }
.repere { position:absolute; top:4px; width:4px; height:36px; margin-left:-2px; border-radius:2px; background:var(--primary-text-color); }
.repere::after { content:""; position:absolute; left:50%; top:-6px; width:12px; height:12px; margin-left:-6px; border-radius:50%; background:var(--primary-text-color); }
.legende { display:flex; justify-content:space-between; font-size:.75rem; color:var(--secondary-text-color); margin:0 4px 10px; }
.tendance { display:flex; align-items:center; gap:8px; margin:6px 0 12px; font-size:.95rem; color:var(--primary-text-color); }
.tendance .fl { font-size:1.4rem; width:28px; text-align:center; }
.boutons { display:grid; grid-template-columns:1fr 1fr 1fr; gap:8px; margin:8px 0 6px; }
button.b.bien { background:color-mix(in srgb, var(--primary-color) 14%, transparent); }
button.b { min-height:52px; border-radius:12px; border:2px solid var(--primary-color); background:transparent; color:var(--primary-text-color); font:inherit; font-size:1rem; font-weight:600; cursor:pointer; }
button.b:hover { background:color-mix(in srgb, var(--primary-color) 12%, transparent); }
button.b:focus-visible { outline:3px solid var(--primary-color); outline-offset:2px; }
button.b:disabled { opacity:.5; cursor:not-allowed; }
.sec { margin-top:16px; }
.sec h3 { margin:0 0 6px; font-size:.95rem; font-weight:600; color:var(--primary-text-color); }
.petit { font-size:.8rem; color:var(--secondary-text-color); }
svg.courbe { width:100%; height:110px; display:block; }
.lg { display:flex; gap:14px; flex-wrap:wrap; font-size:.75rem; color:var(--secondary-text-color); margin-top:4px; }
.lg i { display:inline-block; width:18px; height:0; border-top:3px solid var(--primary-text-color); vertical-align:middle; margin-right:4px; }
.lg i.t { border-top:3px dashed var(--secondary-text-color); }
.lg i.z { height:10px; border:0; background:color-mix(in srgb, var(--primary-color) 25%, transparent); }
.plage { color:var(--primary-text-color); display:grid; grid-template-columns: 92px 1fr 64px; align-items:center; gap:8px; padding:8px 8px; border-radius:10px; font-size:.9rem; }
.plage.act { border:2px solid var(--primary-color); }
.plage:not(.act) { border:2px solid transparent; }
.barre { height:10px; border-radius:5px; background:var(--divider-color); overflow:hidden; }
.barre > span { display:block; height:100%; background:var(--primary-color); }
.val { text-align:right; font-weight:600; color:var(--primary-text-color); }
.sous { grid-column:1 / -1; font-size:.78rem; color:var(--secondary-text-color); }
details { margin-top:14px; border:1px solid var(--divider-color); border-radius:12px; padding:0 12px; }
summary { min-height:48px; display:flex; align-items:center; cursor:pointer; font-weight:600; color:var(--primary-text-color); }
summary:focus-visible { outline:3px solid var(--primary-color); outline-offset:2px; }
details p { margin:0 0 12px; line-height:1.5; color:var(--primary-text-color); font-size:.92rem; }
ul.ap { list-style:none; margin:0; padding:0; }
ul.ap li { display:flex; justify-content:space-between; gap:8px; padding:6px 0; border-bottom:1px solid var(--divider-color); font-size:.88rem; color:var(--primary-text-color); }
ul.ap li:last-child { border-bottom:0; }
.vide { color:var(--secondary-text-color); font-size:.88rem; padding:4px 0; }
.pilote { margin-top:16px; border:2px solid var(--divider-color); border-radius:12px; padding:12px; }
.pilote.on { border-color:var(--primary-color); }
.pilote .ligne { display:flex; align-items:center; justify-content:space-between; gap:10px; }
.pilote h3 { margin:0; }
.etat { font-size:.8rem; font-weight:600; padding:4px 10px; border-radius:999px; border:1px solid currentColor; white-space:nowrap; color:var(--secondary-text-color); }
.pilote.on .etat { color:var(--primary-text-color); border-width:2px; }
.cons { font-size:1.5rem; font-weight:600; color:var(--primary-text-color); margin:8px 0 2px; }
button.bp { min-height:48px; padding:0 14px; border-radius:12px; border:2px solid var(--primary-color); background:transparent; color:var(--primary-text-color); font:inherit; font-weight:600; cursor:pointer; }
button.bp[aria-pressed="true"] { background:var(--primary-color); color:var(--text-primary-color,#fff); }
button.bp:focus-visible { outline:3px solid var(--primary-color); outline-offset:2px; }
.lien { background:none; border:0; padding:0; min-height:44px; font:inherit; color:var(--primary-color); cursor:pointer; text-decoration:underline; }
@media (forced-colors: active) {
  .zone, .repere, .barre > span { forced-color-adjust:none; background:Highlight; border-color:Highlight; }
  button.b { border-color:ButtonText; }
}
@media (prefers-reduced-motion: reduce) { * { transition:none !important; animation:none !important; } }
`;

class ConfortRessentiCard extends HTMLElement {
  setConfig(config) {
    if (!config || !config.entity) throw new Error("Choisissez l'entité « Ressenti » de la pièce.");
    this._config = { pourquoi_ouvert: true, ...config };
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
    this._rendu = null;
  }

  set hass(hass) {
    this._hass = hass;
    const st = hass.states[this._config.entity];
    const cle = st ? st.last_updated + "|" + st.state : "absent";
    if (cle === this._rendu) return;
    this._rendu = cle;
    this._dessiner(st);
  }

  getCardSize() { return 8; }

  static getConfigElement() { return document.createElement("confort-ressenti-card-editor"); }

  static getStubConfig(hass) {
    const e = Object.keys(hass.states).find((k) => k.startsWith("sensor.") && hass.states[k].attributes && hass.states[k].attributes.plages && hass.states[k].attributes.boutons);
    return { entity: e || "" };
  }

  _presser(entityId) {
    if (!entityId) return;
    this._hass.callService("button", "press", { entity_id: entityId });
  }

  _courbe(a) {
    const h = a.historique || [];
    if (h.length < 2) return `<div class="vide">La courbe apparaîtra après quelques mesures (un point toutes les 15 minutes).</div>`;
    const W = 320, H = 110, pad = 6;
    const ts = h.map((p) => p[0]);
    const vals = h.flatMap((p) => [p[1], p[2]]).concat([a.confort - 0.7, a.confort + 0.7]);
    let lo = Math.min(...vals) - 0.3, hi = Math.max(...vals) + 0.3;
    if (hi - lo < 2) { const m = (hi + lo) / 2; lo = m - 1; hi = m + 1; }
    const t0 = ts[0], t1 = ts[ts.length - 1] || t0 + 1;
    const X = (t) => pad + ((t - t0) / Math.max(1, t1 - t0)) * (W - 2 * pad);
    const Y = (v) => H - pad - ((v - lo) / (hi - lo)) * (H - 2 * pad);
    const ligne = (i) => h.map((p, k) => `${k ? "L" : "M"}${X(p[0]).toFixed(1)},${Y(p[i]).toFixed(1)}`).join(" ");
    const yh = Y(a.confort + 0.7), yb = Y(a.confort - 0.7);
    return `<svg class="courbe" viewBox="0 0 ${W} ${H}" role="img" aria-label="Courbe de la température de l'air et des murs estimés sur 24 heures, avec la zone de confort">
      <rect x="${pad}" y="${yh.toFixed(1)}" width="${W - 2 * pad}" height="${Math.max(2, yb - yh).toFixed(1)}" fill="var(--primary-color)" opacity=".22"/>
      <path d="${ligne(2)}" fill="none" stroke="var(--secondary-text-color)" stroke-width="2" stroke-dasharray="5 4"/>
      <path d="${ligne(1)}" fill="none" stroke="var(--primary-text-color)" stroke-width="2.5"/>
      <text x="${pad}" y="10" font-size="9" fill="var(--secondary-text-color)">${fmt(hi, 0)} °C</text>
      <text x="${pad}" y="${H - 1}" font-size="9" fill="var(--secondary-text-color)">${fmt(lo, 0)} °C</text>
    </svg>
    <div class="lg"><span><i></i>Air (mesuré)</span><span><i class="t"></i>Murs (estimés)</span><span><i class="z"></i>Votre zone de confort</span></div>`;
  }

  _pilotage(a, b) {
    const pi = a.pilotage || {};
    const on = !!pi.actif;
    const d = pi.derniere;
    const quand = d ? new Date(d.ts * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : null;
    return `<div class="pilote ${on ? "on" : ""}">
      <div class="ligne"><h3>Pilotage des têtes</h3><span class="etat">${on ? "● Actif" : "○ Désactivé"}</span></div>
      <div class="cons">${fmt(pi.consigne)} °C <span class="petit">consigne d'air recommandée</span></div>
      <div class="detail">${esc(pi.raison || "")}</div>
      <div class="petit">${pi.nb_tetes ? `${pi.nb_tetes} tête${pi.nb_tetes > 1 ? "s" : ""}` : "Aucune tête choisie"} · limites ${fmt(pi.min)} à ${fmt(pi.max)} °C${quand ? ` · dernier envoi ${esc(quand)} (${fmt(d.cible)} °C)` : ""}</div>
      <div style="margin-top:10px"><button class="bp" id="pilotage" aria-pressed="${on}" ${b.pilotage ? "" : "disabled"}>${on ? "Désactiver le pilotage" : "Activer le pilotage"}</button></div>
    </div>`;
  }

  _dessiner(st) {
    const r = this.shadowRoot;
    if (!st) { r.innerHTML = `<style>${STYLE}</style><ha-card><div class="alerte">Entité introuvable : ${esc(this._config.entity)}</div></ha-card>`; return; }
    const a = st.attributes || {};
    const mot = st.state;
    const libelle = MOTS[mot] || (mot === "unknown" || mot === "unavailable" ? "En attente de mesure" : mot);
    const ressentie = a.temperature_ressentie, confort = a.confort;
    // échelle : confort ± 3 °C
    const lo = (confort ?? 20) - 3, hi = (confort ?? 20) + 3;
    const pos = (v) => Math.max(0, Math.min(100, ((v - lo) / (hi - lo)) * 100));
    const zg = pos(confort - 0.7), zd = pos(confort + 0.7);
    // tendance
    let fl = "→", txt = "Je n'ai pas encore assez de mesures pour dire si ça monte ou si ça descend.";
    if (a.tendance !== null && a.tendance !== undefined) {
      if (a.tendance > a.tendance_seuil) { fl = "↗"; txt = `La pièce <b>se réchauffe</b> (+${fmt(a.tendance)} °C par heure).`; }
      else if (a.tendance < -a.tendance_seuil) { fl = "↘"; txt = `La pièce <b>se refroidit</b> (${fmt(a.tendance)} °C par heure).`; }
      else { fl = "→"; txt = "La température est <b>stable</b>."; }
    }
    const b = a.boutons || {};
    const pause = a.apprentissage_actif === false;
    const plages = (a.plages || []).map((p) => {
      const pct = Math.round((p.confiance || 0) * 100);
      const sous = p.appuis === 0
        ? "Pas encore appris — j'utilise la moyenne des autres plages."
        : `${p.appuis} appui${p.appuis > 1 ? "s" : ""}` + (p.bien != null ? ` · « bien » vers ${fmt(p.bien)}` : "") + (p.froid != null ? ` · « trop froid » à ${fmt(p.froid)}` : "") + (p.chaud != null ? ` · « trop chaud » à ${fmt(p.chaud)}` : "");
      return `<div class="plage ${p.actuelle ? "act" : ""}" ${p.actuelle ? 'aria-current="true"' : ""}>
        <span>${esc(PLAGE_COURT[p.plage] || p.plage)}${p.actuelle ? " ●" : ""}</span>
        <span class="barre" role="progressbar" aria-valuenow="${pct}" aria-valuemin="0" aria-valuemax="100" aria-label="Fiabilité ${pct} %"><span style="width:${pct}%"></span></span>
        <span class="val">${fmt(p.confort)} °C</span><span class="sous">${sous}</span></div>`;
    }).join("");
    const appuis = (a.appuis || []).map((p) => {
      const d = new Date(p.ts * 1000);
      const quand = d.toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
      return `<li><span>${esc(quand)} · ${p.sens === "froid" ? "❄ Trop froid" : p.sens === "bien" ? "✓ Bien" : "☀ Trop chaud"} à ${fmt(p.ressentie)} °C</span><span>confort ${fmt(p.confort_avant)} → <b>${fmt(p.confort_apres)}</b></span></li>`;
    }).join("");

    r.innerHTML = `<style>${STYLE}</style>
    <ha-card>
      <div class="tete"><span class="piece">${esc(a.piece || a.friendly_name || "Pièce")}</span><span class="chip">${esc(PLAGE_COURT[a.plage] || "")}</span></div>
      ${a.capteur_ok === false ? `<div class="alerte" role="alert">⚠ Le capteur de température ne répond pas. Les valeurs ci-dessous sont les dernières connues.</div>` : ""}
      ${pause ? `<div class="alerte" role="status">⏸ Apprentissage en pause : les appuis sont ignorés. <button class="lien" id="reprendre">Reprendre</button></div>` : ""}
      <div class="verdict"><span class="mot"><span class="ic" aria-hidden="true">${ICONES[mot] || "…"}</span>${esc(libelle)}</span></div>
      <div class="detail">Ressenti <b>${fmt(ressentie)} °C</b> · air <b>${fmt(a.temperature_air)} °C</b> · murs ≈ <b>${fmt(a.murs_estimes)} °C</b> (estimé) · confort appris <b>${fmt(confort)} °C</b></div>
      <div class="echelle" aria-hidden="true">
        <div class="rail"></div><div class="zone" style="left:${zg}%;width:${Math.max(2, zd - zg)}%"></div>
        ${ressentie != null ? `<div class="repere" style="left:${pos(ressentie)}%"></div>` : ""}
      </div>
      <div class="legende" aria-hidden="true"><span>Froid</span><span>Zone de confort</span><span>Chaud</span></div>
      <div class="tendance"><span class="fl" aria-hidden="true">${fl}</span><span>${txt}</span></div>
      <div class="boutons">
        <button class="b" id="froid" ${!b.trop_froid || pause ? "disabled" : ""}>❄ Trop froid</button>
        <button class="b bien" id="bien" ${!b.bien || pause ? "disabled" : ""}>✓ Je suis bien</button>
        <button class="b" id="chaud" ${!b.trop_chaud || pause ? "disabled" : ""}>☀ Trop chaud</button>
      </div>
      ${a.peut_annuler ? `<button class="lien" id="annuler">Annuler mon dernier appui</button>` : ""}
      ${this._pilotage(a, b)}
      <div class="sec"><h3>Les dernières 24 heures</h3>${this._courbe(a)}</div>
      <div class="sec"><h3>Ce que j'ai appris (${Math.round((a.confiance || 0) * 100)} % de fiabilité)</h3>${plages}
        <div class="petit">Plus vous appuyez dans une plage, plus elle devient fiable. Appuyez sur « Je suis bien » quand c'est parfait : c'est la confirmation la plus utile. « Trop froid » et « trop chaud » encadrent ensuite précisément votre confort.</div></div>
      <details ${this._config.pourquoi_ouvert ? "open" : ""}><summary>Pourquoi ce ressenti ?</summary><p>${esc(a.explication)}</p>
        <p class="petit">Les murs sont une estimation calculée à partir de l'air (ils réagissent lentement), pas une mesure.</p></details>
      <div class="sec"><h3>Derniers appuis</h3>${appuis ? `<ul class="ap">${appuis}</ul>` : `<div class="vide">Aucun appui pour l'instant.</div>`}</div>
    </ha-card>`;
    r.getElementById("froid")?.addEventListener("click", () => this._presser(b.trop_froid));
    r.getElementById("bien")?.addEventListener("click", () => this._presser(b.bien));
    r.getElementById("chaud")?.addEventListener("click", () => this._presser(b.trop_chaud));
    r.getElementById("annuler")?.addEventListener("click", () => this._presser(b.annuler));
    r.getElementById("pilotage")?.addEventListener("click", () => this._hass.callService("switch", (a.pilotage || {}).actif ? "turn_off" : "turn_on", { entity_id: b.pilotage }));
    r.getElementById("reprendre")?.addEventListener("click", () => this._hass.callService("switch", "turn_on", { entity_id: b.apprentissage }));
  }
}

class ConfortRessentiCardEditor extends HTMLElement {
  setConfig(config) { this._config = config; this._rendre(); }
  set hass(h) { this._hass = h; this._rendre(); }
  _rendre() {
    if (!this._hass || !this._config) return;
    if (!this._form) {
      this._form = document.createElement("ha-form");
      this._form.computeLabel = (s) => ({ entity: "Pièce (entité « Ressenti »)", pourquoi_ouvert: "Afficher « Pourquoi ce ressenti ? » ouvert" }[s.name] || s.name);
      this._form.addEventListener("value-changed", (ev) => {
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: ev.detail.value }, bubbles: true, composed: true }));
      });
      this.appendChild(this._form);
    }
    this._form.hass = this._hass;
    this._form.data = this._config;
    this._form.schema = [
      { name: "entity", required: true, selector: { entity: { domain: "sensor", integration: "confort_ressenti", device_class: "enum" } } },
      { name: "pourquoi_ouvert", selector: { boolean: {} } },
    ];
  }
}

customElements.get("confort-ressenti-card") || customElements.define("confort-ressenti-card", ConfortRessentiCard);
customElements.get("confort-ressenti-card-editor") || customElements.define("confort-ressenti-card-editor", ConfortRessentiCardEditor);
window.customCards = window.customCards || [];
if (!window.customCards.some((c) => c.type === "confort-ressenti-card")) {
  window.customCards.push({
    type: "confort-ressenti-card",
    name: "Confort ressenti",
    description: "Ressenti de la pièce, murs estimés, tendance, courbe 24 h et progression de l'apprentissage.",
    preview: false,
  });
}
console.info(`%c CONFORT-RESSENTI %c ${VERSION}`, "background:#1F5A4A;color:#fff", "");
