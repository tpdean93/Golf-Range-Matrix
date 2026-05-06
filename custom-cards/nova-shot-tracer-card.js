class NovaShotTracerCard extends HTMLElement {
  setConfig(config) { this.config = config || {}; if (!this.config.speed_entity) throw new Error('speed_entity is required'); }
  set hass(hass) {
    this._hass = hass;
    const watched = [this.config.speed_entity, this.config.carry_entity, this.config.total_entity, this.config.offline_entity, this.config.vertical_entity, this.config.horizontal_entity, this.config.spin_entity, this.config.spin_axis_entity, this.config.shot_name_entity, this.config.shot_rank_entity, this.config.count_entity, this.config.last_shot_entity, this.config.connection_entity];
    const signature = watched.map(e => `${e}:${hass.states?.[e]?.state ?? ''}`).join('|');
    if (this._signature === signature && this._rendered) return;
    this._signature = signature;
    this.render();
  }
  getCardSize() { return 8; }
  state(e) { return this._hass?.states?.[e]; }
  value(e) { const s = this.state(e); if (!s || s.state === 'unknown' || s.state === 'unavailable') return null; const n = Number(s.state); return Number.isFinite(n) ? n : s.state; }
  unit(e) { const u = this.state(e)?.attributes?.unit_of_measurement || ''; return u === 'yds' ? 'yd' : u; }
  esc(v) { return String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
  clamp(v, min, max) { return Math.min(max, Math.max(min, v)); }
  fmt(e, d = 1) { const v = this.value(e); if (v === null) return '--'; return typeof v === 'number' ? `${v.toFixed(d)}${this.unit(e) ? ` ${this.unit(e)}` : ''}` : this.esc(v); }
  ago(e) { const raw = this.value(e); if (!raw || typeof raw !== 'string') return '--'; const then = new Date(raw); if (Number.isNaN(then.getTime())) return this.esc(raw); const m = Math.max(0, Math.round((Date.now() - then.getTime()) / 60000)); return m < 1 ? 'just now' : m < 60 ? `${m} min ago` : `${Math.round(m / 60)} hr ago`; }
  metric(label, value, tone = '') { return `<div class="metric ${tone}"><div class="label">${label}</div><div class="value">${value}</div></div>`; }

  render() {
    if (!this._hass || !this.config) return;
    this._rendered = true;
    const c = this.config;
    const speed = Number(this.value(c.speed_entity) || 0);
    const carry = Number(this.value(c.carry_entity) || 0);
    const launch = Number(this.value(c.vertical_entity) || 0);
    const side = Number(this.value(c.horizontal_entity) || 0);
    const spin = Number(this.value(c.spin_entity) || 0);
    const axis = Number(this.value(c.spin_axis_entity) || 0);
    const offline = Number(this.value(c.offline_entity) || 0);
    const shotName = this.value(c.shot_name_entity) || '';
    const shotRank = this.value(c.shot_rank_entity) || '';
    const connected = this.state(c.connection_entity)?.state === 'on';
    const img = this.state(c.camera_entity)?.attributes?.entity_picture || '';

    const startX = 195, startY = 222;
    const distanceLift = carry ? this.clamp((carry - 110) * 0.18, -12, 34) : 0;
    const direction = side + axis * 0.22 + offline * 0.08;
    const endX = this.clamp(startX + direction * 9.4, 24, 366);
    const apexX = this.clamp(startX + direction * 4.8, 40, 350);
    const apexY = this.clamp(176 - launch * 3.25 - speed * 0.29 - distanceLift, 24, 150);
    const landY = this.clamp(156 - speed * 0.08 - distanceLift * 0.45, 100, 166);
    const curve = `M ${startX} ${startY} C ${startX} ${startY - 64}, ${apexX} ${apexY}, ${endX} ${landY}`;
    const shadow = `M ${startX} ${startY + 5} C ${startX} ${startY - 24}, ${apexX} ${apexY + 38}, ${this.clamp(endX * .86 + startX * .14, 48, 342)} ${this.clamp(landY + 36, 152, 204)}`;
    const directionText = offline < -1 ? 'Left' : offline > 1 ? 'Right' : side < -0.75 ? 'Started Left' : side > 0.75 ? 'Started Right' : 'Center Cut';
    const offlineLabel = Math.abs(offline) >= 1 ? `${directionText} ${Math.abs(offline).toFixed(1)} yd` : 'Center Cut';
    const resultRest = [shotName, offlineLabel].filter(Boolean).join(' | ');

    this.innerHTML = `<ha-card><div class="shell">
      ${img ? `<img class="bg" src="${this.esc(img)}" alt="Garage camera">` : ''}<div class="wash"></div>
      <div class="topline"><div><div class="eyebrow">LIVE OPEN GOLF COACH</div><h1>${this.esc(c.title || 'NOVA Shot Lab')}</h1></div><div class="status ${connected ? 'on' : 'off'}"><span></span>${connected ? 'Connected' : 'Offline'}</div></div>
      <div class="heroStrip"><div class="primaryStat carryStat"><div class="statLabel">Carry</div><div class="statValue">${this.fmt(c.carry_entity, 1)}</div></div><div class="primaryStat"><div class="statLabel">Ball Speed</div><div class="statValue small">${this.fmt(c.speed_entity, 1)}</div></div><div class="resultWrap">${shotRank ? `<div class="gradeBig">${this.esc(shotRank)}</div>` : ''}<div class="resultText">${this.esc(resultRest)}</div></div></div>
      <div class="stage"><svg viewBox="0 0 390 252" preserveAspectRatio="none" aria-label="Animated shot tracer driving range grid"><defs><linearGradient id="nova-tracer" x1="0" x2="1" y1="1" y2="0"><stop offset="0" stop-color="#f7ff5c"/><stop offset="0.44" stop-color="#38f8ff"/><stop offset="1" stop-color="#b36bff"/></linearGradient><radialGradient id="impact-glow"><stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#38f8ff" stop-opacity="0"/></radialGradient><filter id="glow"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>
        <path class="fairway" d="M52 242 L195 24 L338 242 Z"/><path class="target" d="M195 24 V236"/><path class="roughBoundary" d="M104 236 L195 24 M286 236 L195 24"/><path class="grid" d="M22 214 H368 M34 178 H356 M48 142 H342 M66 106 H324 M88 70 H302 M112 36 H278 M52 242 L195 24 L338 242"/>
        <g class="rangeLabels"><text x="30" y="210">50 YD</text><text x="42" y="174">100 YD</text><text x="56" y="138">150 YD</text><text x="76" y="102">200 YD</text><text x="98" y="66">250 YD</text><text x="122" y="31">300 YD</text><text x="315" y="210">50</text><text x="306" y="174">100</text><text x="292" y="138">150</text><text x="266" y="102">200</text><text x="242" y="66">250</text><text x="218" y="31">300</text></g>
        <g class="sideLabels"><text x="70" y="247">LEFT ROUGH</text><text x="246" y="247">RIGHT ROUGH</text></g>
        <path class="ghost" d="${shadow}"/><path id="flightPath" class="pathTemplate" d="${curve}"/><path class="curve halo" d="${curve}"/><path class="curve animated" d="${curve}"/><circle class="impactGlow" cx="${startX}" cy="${startY}" r="30"/><circle class="tee" cx="${startX}" cy="${startY}" r="5"/><circle class="movingBall" r="5"><animateMotion dur="3s" repeatCount="indefinite" rotate="auto" calcMode="spline" keyTimes="0;0.8;1" keyPoints="0;1;1" keySplines=".2 0 .2 1;0 0 1 1"><mpath href="#flightPath"/></animateMotion><animate attributeName="opacity" values="0;1;1;0" keyTimes="0;0.06;0.8;1" dur="3s" repeatCount="indefinite"/></circle><circle class="landPulse" cx="${endX}" cy="${landY}" r="5"/><text class="impactLabel" x="151" y="248">IMPACT</text><text class="flightLabel" x="${this.clamp(endX - 54, 18, 292)}" y="${this.clamp(landY - 12, 24, 168)}">${this.esc(offlineLabel)}</text>
      </svg></div>
      <div class="metrics">${this.metric('Total', this.fmt(c.total_entity, 1), 'cyan')}${this.metric('Offline', this.fmt(c.offline_entity, 1), 'violet')}${this.metric('Spin', this.fmt(c.spin_entity, 0), 'lime')}${this.metric('Launch', this.fmt(c.vertical_entity, 1), 'amber')}${this.metric('Shots', this.fmt(c.count_entity, 0), 'blue')}${this.metric('Last Shot', this.ago(c.last_shot_entity), 'pink')}</div>
    </div></ha-card><style>
      ha-card{overflow:hidden;border:0;border-radius:28px;background:#050814;color:white;box-shadow:0 24px 70px rgba(0,0,0,.42)}.shell{position:relative;min-height:840px;padding:26px;isolation:isolate}.bg{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;opacity:.21;filter:saturate(1.3) contrast(1.08);z-index:-3}.wash{position:absolute;inset:0;background:radial-gradient(circle at 70% 15%,rgba(56,248,255,.25),transparent 34%),radial-gradient(circle at 12% 88%,rgba(168,85,247,.28),transparent 42%),linear-gradient(135deg,rgba(4,7,19,.98),rgba(7,15,36,.86));z-index:-2}.topline{display:flex;justify-content:space-between;gap:18px;align-items:flex-start}.eyebrow{color:#8ffcff;font-weight:900;letter-spacing:.2em;font-size:13px;text-shadow:0 0 14px rgba(56,248,255,.45)}h1{margin:7px 0 0;font-size:clamp(36px,6vw,64px);line-height:.92;letter-spacing:-.06em}.status{display:flex;align-items:center;gap:8px;padding:10px 14px;border-radius:999px;background:rgba(255,255,255,.11);font-weight:800;white-space:nowrap}.status span{width:10px;height:10px;border-radius:50%;background:#ff4d6d;box-shadow:0 0 18px #ff4d6d}.status.on span{background:#72ff7d;box-shadow:0 0 18px #72ff7d}.heroStrip{display:grid;grid-template-columns:minmax(0,1fr) minmax(150px,.72fr) minmax(240px,1fr);align-items:center;gap:14px;margin-top:24px;padding:16px 18px;border:1px solid rgba(255,255,255,.14);border-radius:22px;background:rgba(255,255,255,.08);backdrop-filter:blur(16px)}.statLabel{color:rgba(255,255,255,.68);text-transform:uppercase;letter-spacing:.17em;font-size:12px;font-weight:900}.statValue{margin-top:3px;font-size:clamp(44px,7vw,72px);line-height:.95;font-weight:950;letter-spacing:-.07em;text-shadow:0 0 28px rgba(56,248,255,.35)}.statValue.small{font-size:clamp(30px,4.5vw,50px)}.carryStat .statValue{color:#f7ff8a}.resultWrap{display:flex;align-items:center;justify-content:flex-end;gap:10px}.gradeBig{font-size:38px;line-height:1;font-weight:950;color:#f7ff8a;text-shadow:0 0 20px rgba(247,255,92,.35)}.resultText{padding:9px 12px;border-radius:999px;background:rgba(255,255,255,.1);border:1px solid rgba(247,255,92,.32);color:#f7ff8a;font-size:12px;font-weight:900;text-transform:uppercase;letter-spacing:.08em}.stage{position:relative;margin-top:16px;min-height:490px;border:1px solid rgba(255,255,255,.15);border-radius:25px;background:linear-gradient(180deg,rgba(255,255,255,.09),rgba(255,255,255,.03));overflow:hidden}svg{position:absolute;inset:0;width:100%;height:100%}.fairway{fill:rgba(56,248,255,.045);stroke:rgba(255,255,255,.08);stroke-width:1}.grid{stroke:rgba(255,255,255,.17);stroke-width:1;fill:none}.target{stroke:rgba(247,255,92,.45);stroke-width:1.8;fill:none;stroke-dasharray:5 8}.roughBoundary{stroke:rgba(255,255,255,.18);stroke-width:1.25;fill:none;stroke-dasharray:4 8}.ghost{stroke:rgba(255,255,255,.16);stroke-width:5;fill:none;stroke-linecap:round;stroke-dasharray:2 13}.pathTemplate{fill:none;stroke:none}.curve{stroke:url(#nova-tracer);stroke-width:7;fill:none;stroke-linecap:round;filter:url(#glow)}.curve.halo{stroke:rgba(56,248,255,.25);stroke-width:18;opacity:.45}.curve.animated{stroke-dasharray:520;stroke-dashoffset:520;animation:draw-flight 3s ease-out infinite}.movingBall{fill:white;filter:url(#glow)}.landPulse{fill:white;filter:url(#glow);opacity:0;animation:land-pulse 3s ease-out infinite}.tee{fill:white;filter:url(#glow)}.impactGlow{fill:url(#impact-glow);opacity:.76;animation:impact-pulse 3s ease-out infinite}text{fill:rgba(255,255,255,.64);font-size:12px;text-transform:uppercase;letter-spacing:.16em}.rangeLabels text{fill:rgba(247,255,92,.86);font-size:10.5px;font-weight:950;letter-spacing:.12em;text-shadow:0 0 10px rgba(247,255,92,.35)}.sideLabels text{fill:rgba(255,255,255,.42);font-size:8.5px;font-weight:950;letter-spacing:.15em}.flightLabel,.impactLabel{font-size:13px;font-weight:950;fill:rgba(255,255,255,.78);text-shadow:0 0 12px rgba(255,255,255,.28)}.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin-top:14px}.metric{padding:16px;border-radius:20px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);backdrop-filter:blur(16px)}.metric .label{color:rgba(255,255,255,.66);text-transform:uppercase;font-size:11px;letter-spacing:.14em;font-weight:900}.metric .value{margin-top:8px;font-size:25px;font-weight:900;letter-spacing:-.03em}.cyan{box-shadow:inset 0 0 0 1px rgba(56,248,255,.12)}.violet{box-shadow:inset 0 0 0 1px rgba(168,85,247,.16)}.lime{box-shadow:inset 0 0 0 1px rgba(230,255,88,.14)}.amber{box-shadow:inset 0 0 0 1px rgba(255,184,77,.14)}.blue{box-shadow:inset 0 0 0 1px rgba(80,140,255,.16)}.pink{box-shadow:inset 0 0 0 1px rgba(255,77,190,.16)}@keyframes draw-flight{0%{stroke-dashoffset:520;opacity:0}7%{opacity:1}78%{stroke-dashoffset:0;opacity:1}100%{stroke-dashoffset:0;opacity:.25}}@keyframes impact-pulse{0%,100%{opacity:.28;transform:scale(.88)}7%,18%{opacity:.82;transform:scale(1)}}@keyframes land-pulse{0%,76%{opacity:0;r:4}83%{opacity:1;r:7}100%{opacity:0;r:13}}@media(max-width:760px){.shell{min-height:980px;padding:18px}.topline{flex-direction:column}.heroStrip{grid-template-columns:1fr;align-items:flex-start}.resultWrap{justify-content:flex-start}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}.stage{min-height:430px}}
    </style>`;
  }
}
if (!customElements.get('nova-shot-tracer-card')) customElements.define('nova-shot-tracer-card', NovaShotTracerCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: 'nova-shot-tracer-card', name: 'NOVA Shot Tracer', description: 'Live golf launch monitor shot tracer card' });
