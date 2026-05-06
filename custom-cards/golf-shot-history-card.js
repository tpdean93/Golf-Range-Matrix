class GolfShotHistoryCard extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    this.limit = this.config.limit || 50;
    this.entities = this.config.entities || ['sensor.golf_carry', 'sensor.golf_total', 'sensor.golf_offline', 'sensor.golf_ball_speed'];
    this.basis = this.config.basis_entity || this.entities[0];
    this._liveShots = [];
  }

  set hass(hass) {
    this._hass = hass;
    const signature = this.entities.map(e => `${e}:${hass.states?.[e]?.state ?? ''}`).join('|');
    if (signature !== this._liveSignature) {
      this._liveSignature = signature;
      this.addLiveShot();
      this._lastFetch = 0;
    }
    if (!this._lastFetch || Date.now() - this._lastFetch > 45000) this.fetchData();
    this.render();
  }

  getCardSize() { return 4; }
  esc(v) { return String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
  num(v) { const n = Number(v); return Number.isFinite(n) ? n : null; }

  currentShot() {
    if (!this._hass) return null;
    const shot = { idx: 0, t: Date.now() };
    let hasValue = false;
    for (const entity of this.entities) {
      const value = this.num(this._hass.states?.[entity]?.state);
      shot[entity] = value;
      if (value !== null) hasValue = true;
    }
    return hasValue ? shot : null;
  }

  addLiveShot() {
    const shot = this.currentShot();
    if (!shot || shot[this.basis] === null) return;
    const last = this._liveShots[this._liveShots.length - 1];
    if (last && Math.abs((last[this.basis] ?? 0) - shot[this.basis]) < 0.05 && Math.abs((last['sensor.golf_ball_speed'] ?? 0) - (shot['sensor.golf_ball_speed'] ?? 0)) < 0.05) return;
    this._liveShots.push(shot);
    this._liveShots = this._liveShots.slice(-this.limit);
  }

  mergeShots(historyShots) {
    const combined = [...(historyShots || [])];
    for (const live of this._liveShots || []) {
      const duplicate = combined.some(s => Math.abs((s[this.basis] ?? 99999) - (live[this.basis] ?? -99999)) < 0.05 && Math.abs((s['sensor.golf_ball_speed'] ?? 99999) - (live['sensor.golf_ball_speed'] ?? -99999)) < 0.05);
      if (!duplicate) combined.push(live);
    }
    return combined.slice(-this.limit).map((shot, idx) => ({ ...shot, idx: idx + 1 }));
  }

  async fetchData() {
    if (!this._hass || this._fetching) return;
    this._fetching = true;
    this._lastFetch = Date.now();
    try {
      const start = new Date(Date.now() - (this.config.hours_back || 168) * 3600000).toISOString();
      const ids = this.entities.join(',');
      const rows = await this._hass.callApi('GET', `history/period/${start}?filter_entity_id=${encodeURIComponent(ids)}&minimal_response`);
      const byEntity = {};
      for (const list of rows || []) {
        for (const item of list || []) {
          if (!byEntity[item.entity_id]) byEntity[item.entity_id] = [];
          const value = this.num(item.state);
          if (value !== null) byEntity[item.entity_id].push({ t: new Date(item.last_changed || item.last_updated).getTime(), v: value });
        }
      }
      const basisRows = byEntity[this.basis] || [];
      const historyShots = basisRows.slice(-this.limit).map((point, idx) => {
        const shot = { idx: idx + 1, t: point.t };
        for (const entity of this.entities) {
          const series = byEntity[entity] || [];
          let match = null;
          for (const p of series) {
            if (p.t <= point.t + 10000) match = p;
            else break;
          }
          shot[entity] = match?.v ?? null;
        }
        return shot;
      });
      this._historyShots = historyShots;
      this._shots = this.mergeShots(historyShots);
    } catch (err) {
      this._error = err?.message || String(err);
      this._shots = this.mergeShots(this._historyShots || []);
    } finally {
      this._fetching = false;
      this.render();
    }
  }

  points(values, x0, y0, w, h) {
    const nums = values.filter(v => v !== null);
    if (!nums.length) return { path: '', dots: '', min: 0, max: 0 };
    let min = Math.min(...nums), max = Math.max(...nums);
    if (min === max) { min -= 1; max += 1; }
    const coords = values.map((v, i) => {
      if (v === null) return null;
      return { x: x0 + (values.length <= 1 ? w : i * w / (values.length - 1)), y: y0 + h - ((v - min) / (max - min)) * h };
    });
    const path = coords.filter(Boolean).map((p, i) => `${i === 0 ? 'M' : 'L'} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(' ');
    const dots = coords.filter(Boolean).map(p => `<circle cx="${p.x.toFixed(1)}" cy="${p.y.toFixed(1)}" r="3"/>`).join('');
    return { path, dots, min, max };
  }

  chart(title, series) {
    const shots = this._shots || this.mergeShots(this._historyShots || []);
    const w = 360, h = 172, x0 = 30, y0 = 28, cw = 302, ch = 92;
    const grid = [0, 1, 2, 3].map(i => `<line x1="${x0}" y1="${y0 + i * ch / 3}" x2="${x0 + cw}" y2="${y0 + i * ch / 3}"/>`).join('');
    const paths = series.map(s => {
      const data = this.points(shots.map(p => p[s.entity]), x0, y0, cw, ch);
      return `<g class="series" style="--c:${s.color}"><path class="line" d="${data.path}"/>${data.dots}</g>`;
    }).join('');
    const latest = series.map(s => {
      const vals = shots.map(p => p[s.entity]).filter(v => v !== null);
      const last = vals[vals.length - 1];
      return `<span style="--c:${s.color}"><b></b>${this.esc(s.name)} ${last == null ? '--' : last.toFixed(s.decimals ?? 1)}</span>`;
    }).join('');
    return `<div class="chart"><div class="chartHead"><div>${this.esc(title)}</div><small>Last ${shots.length || 0} shots</small></div><svg viewBox="0 0 ${w} ${h}"><g class="grid">${grid}</g>${paths}</svg><div class="legend">${latest}</div></div>`;
  }

  render() {
    const title = this.config.title || 'Last 50 Shots';
    this.innerHTML = `<ha-card><div class="panel"><div class="head"><div><div class="kicker">Shot History</div><div class="title">${this.esc(title)}</div></div><button>${this._fetching ? 'Loading' : 'Refresh'}</button></div>${this._error ? `<div class="error">${this.esc(this._error)}</div>` : ''}<div class="charts">${this.chart('Distance', [{entity:'sensor.golf_carry', name:'Carry', color:'#f7ff5c'}, {entity:'sensor.golf_total', name:'Total', color:'#38f8ff'}])}${this.chart('Direction + Speed', [{entity:'sensor.golf_offline', name:'Offline', color:'#ff5d7a'}, {entity:'sensor.golf_ball_speed', name:'Speed', color:'#72ff7d'}])}</div></div></ha-card><style>
      ha-card{border:0;border-radius:24px;background:linear-gradient(145deg,rgba(20,26,44,.92),rgba(8,12,24,.84));color:white;overflow:hidden;box-shadow:0 22px 60px rgba(0,0,0,.34)}.panel{padding:18px;position:relative;isolation:isolate}.panel:before{content:'';position:absolute;inset:-40% auto auto 35%;width:360px;height:260px;border-radius:50%;background:radial-gradient(circle,rgba(56,248,255,.18),transparent 64%);z-index:-1}.head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:14px}.kicker{color:#8ffcff;font-size:10px;font-weight:900;letter-spacing:.18em;text-transform:uppercase}.title{font-size:20px;font-weight:900;letter-spacing:-.04em}button{border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.08);color:rgba(255,255,255,.78);border-radius:999px;padding:7px 10px;font-weight:800;text-transform:uppercase;font-size:10px}.charts{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.chart{border:1px solid rgba(255,255,255,.12);border-radius:18px;background:rgba(255,255,255,.055);padding:12px}.chartHead{display:flex;justify-content:space-between;gap:8px;align-items:center;font-size:14px;font-weight:850}.chartHead small{color:rgba(255,255,255,.48);font-size:10px;font-weight:800;text-transform:uppercase;letter-spacing:.08em}svg{width:100%;height:160px}.grid line{stroke:rgba(255,255,255,.1);stroke-width:1}.line{fill:none;stroke:var(--c);stroke-width:4;stroke-linecap:round;stroke-linejoin:round;filter:drop-shadow(0 0 8px color-mix(in srgb,var(--c),transparent 40%))}.series circle{fill:var(--c);filter:drop-shadow(0 0 8px var(--c))}.legend{display:flex;gap:10px;flex-wrap:wrap;color:rgba(255,255,255,.7);font-size:12px;font-weight:800}.legend span{display:flex;align-items:center;gap:5px}.legend b{display:block;width:9px;height:9px;border-radius:50%;background:var(--c);box-shadow:0 0 10px var(--c)}.error{color:#ff9aad;margin-bottom:10px}@media(max-width:760px){.charts{grid-template-columns:1fr}}
    </style>`;
    this.querySelector('button')?.addEventListener('click', () => { this._lastFetch = 0; this.fetchData(); });
  }
}

if (!customElements.get('golf-shot-history-card')) customElements.define('golf-shot-history-card', GolfShotHistoryCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: 'golf-shot-history-card', name: 'Golf Shot History', description: 'Last 50 golf shots side-by-side charts' });
