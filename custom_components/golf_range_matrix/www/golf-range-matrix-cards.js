const novaEsc = (value) => String(value ?? '').replace(/[&<>'"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c]));
const novaState = (hass, entity) => hass?.states?.[entity];
const novaAttrs = (hass, entity) => novaState(hass, entity)?.attributes || {};
const novaValue = (hass, entity) => novaState(hass, entity)?.state;
const novaCall = (hass, service, data = {}) => hass.callService('golf_range_matrix', service, data);
const novaDefine = (name, klass) => { if (!customElements.get(name)) customElements.define(name, klass); };
const novaConfiguredEntity = (config, key, fallback) => (config?.entities?.[key] || config?.[`${key}_entity`] || fallback);

const novaStyles = `
  <style>
    .nova-card{position:relative;overflow:hidden;border-radius:28px;padding:22px;background:linear-gradient(145deg,rgba(8,15,30,.82),rgba(18,34,62,.66));border:1px solid rgba(148,214,255,.22);box-shadow:0 24px 70px rgba(0,0,0,.36);color:#eef8ff;font-family:Inter,Roboto,Arial,sans-serif}
    .nova-card:before{content:"";position:absolute;inset:-40%;background:radial-gradient(circle at 10% 10%,rgba(65,220,255,.18),transparent 28%),radial-gradient(circle at 85% 10%,rgba(137,90,255,.18),transparent 32%);pointer-events:none}
    .nova-card>*{position:relative}.nova-title{font-size:13px;text-transform:uppercase;letter-spacing:.16em;color:#8fdcff;margin:0 0 8px}.nova-hero{font-size:30px;font-weight:900;line-height:1.05;margin:0}.nova-muted{color:#9bb7c9}.nova-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}.nova-tile{border:1px solid rgba(255,255,255,.12);border-radius:18px;padding:14px;background:rgba(255,255,255,.07);backdrop-filter:blur(14px)}.nova-label{font-size:11px;text-transform:uppercase;letter-spacing:.12em;color:#8faec0}.nova-value{font-size:24px;font-weight:800;margin-top:4px}.nova-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}.nova-btn{border:0;border-radius:999px;padding:10px 14px;background:linear-gradient(135deg,#2ee6a6,#3bb7ff);color:#04101f;font-weight:850;cursor:pointer}.nova-btn.secondary{background:rgba(255,255,255,.12);color:#eaf7ff;border:1px solid rgba(255,255,255,.16)}.nova-input,.nova-select{width:100%;box-sizing:border-box;border-radius:14px;border:1px solid rgba(255,255,255,.16);background:rgba(0,0,0,.24);color:#fff;padding:10px;margin-top:6px}.nova-row{display:grid;grid-template-columns:1fr 1fr;gap:10px}.nova-club{display:grid;grid-template-columns:120px 1fr;gap:18px;align-items:start}.nova-img{width:120px;height:120px;border-radius:22px;object-fit:cover;background:linear-gradient(135deg,rgba(255,255,255,.18),rgba(255,255,255,.04));border:1px solid rgba(255,255,255,.12)}.nova-fallback{display:grid;place-items:center;font-size:46px;color:#9ee7ff}.nova-divider{height:1px;background:rgba(255,255,255,.11);margin:14px 0}@media(max-width:700px){.nova-club,.nova-row{grid-template-columns:1fr}.nova-img{width:100%;height:180px}}
  </style>
`;

class NovaShotTracerCard extends HTMLElement {
  setConfig(config) { this.config = config || {}; }
  set hass(hass) { this._hass = hass; this.render(); }
  metric(key) {
    const entity = novaConfiguredEntity(this.config, key, `sensor.golf_range_matrix_range_matrix_${key}`);
    return Number(novaValue(this._hass, entity) || 0);
  }
  render() {
    const carry = this.metric('carry');
    const offline = this.metric('offline');
    const total = this.metric('total');
    const x = Math.max(20, Math.min(280, 150 + offline * 2));
    const y = Math.max(28, 265 - carry * .8);
    this.innerHTML = `${novaStyles}<div class="nova-card">
      <p class="nova-title">Live Shot Tracer</p><h2 class="nova-hero">${carry ? carry.toFixed(1) : '--'} yd carry</h2>
      <svg viewBox="0 0 300 300" style="width:100%;height:360px;margin-top:10px;border-radius:24px;background:linear-gradient(#10233d,#14351f)">
        ${[75,150,225].map((v,i)=>`<line x1="0" y1="${v}" x2="300" y2="${v}" stroke="rgba(255,255,255,.18)"/><text x="12" y="${v-6}" fill="rgba(255,255,255,.55)" font-size="10">${(3-i)*75} yd</text>`).join('')}
        <path d="M150 285 C150 210 ${x} 170 ${x} ${y}" fill="none" stroke="#55f7ff" stroke-width="5" stroke-linecap="round" filter="drop-shadow(0 0 10px #55f7ff)"/>
        <circle cx="${x}" cy="${y}" r="7" fill="#fff"/>
      </svg>
      <div class="nova-grid"><div class="nova-tile"><div class="nova-label">Total</div><div class="nova-value">${total ? total.toFixed(1) : '--'} yd</div></div><div class="nova-tile"><div class="nova-label">Offline</div><div class="nova-value">${offline ? offline.toFixed(1) : '0.0'} yd</div></div></div>
    </div>`;
  }
}

class GolfMetricPanelCard extends HTMLElement {
  setConfig(config) { this.config = config || {}; }
  set hass(hass) { this._hass = hass; this.render(); }
  render() {
    const metrics = this.config.metrics || [
      ['carry', 'Carry', 'yd'], ['total', 'Total', 'yd'], ['ball_speed', 'Ball Speed', 'mph'], ['club_speed', 'Club Speed', 'mph'], ['smash_factor', 'Smash', ''], ['total_spin', 'Spin', 'rpm']
    ];
    this.innerHTML = `${novaStyles}<div class="nova-card"><p class="nova-title">${novaEsc(this.config.title || 'Range Matrix Metrics')}</p><div class="nova-grid">${metrics.map((metric) => {
      const key = Array.isArray(metric) ? metric[0] : metric.key;
      const label = Array.isArray(metric) ? metric[1] : (metric.name || metric.label || key);
      const unit = Array.isArray(metric) ? metric[2] : (metric.unit || '');
      const entity = Array.isArray(metric) ? novaConfiguredEntity(this.config, key, `sensor.golf_range_matrix_range_matrix_${key}`) : metric.entity;
      const v = novaValue(this._hass, entity);
      return `<div class="nova-tile"><div class="nova-label">${novaEsc(label)}</div><div class="nova-value">${v && v !== 'unknown' ? novaEsc(v) : '--'} <span class="nova-muted" style="font-size:13px">${novaEsc(unit)}</span></div></div>`;
    }).join('')}</div></div>`;
  }
}

class GolfShotHistoryCard extends HTMLElement {
  setConfig(config) { this.config = config || {}; }
  set hass(hass) { this._hass = hass; this.render(); }
  render() {
    const attrs = novaAttrs(this._hass, this.config.entity || this.config.latest_shot_entity || 'sensor.golf_range_matrix_range_matrix_latest_shot');
    this.innerHTML = `${novaStyles}<div class="nova-card"><p class="nova-title">Latest Shot</p><div class="nova-grid">
      ${['player','club','carry','total','offline','ball_speed','launch_angle','shot_rank'].map((key) => `<div class="nova-tile"><div class="nova-label">${novaEsc(key.replaceAll('_',' '))}</div><div class="nova-value">${novaEsc(attrs[key] ?? '--')}</div></div>`).join('')}
    </div></div>`;
  }
}

class GolfSessionControlCard extends HTMLElement {
  setConfig(config) { this.config = config || {}; }
  set hass(hass) { this._hass = hass; this.render(); }
  render() {
    const workflowEntity = this.config.workflow_entity || 'sensor.golf_range_matrix_range_matrix_workflow';
    const playerEntity = this.config.player_entity || 'select.golf_range_matrix_range_matrix_active_player';
    const clubEntity = this.config.club_entity || 'select.golf_range_matrix_range_matrix_active_club';
    const shotsEntity = this.config.shots_per_club_entity || 'number.golf_range_matrix_range_matrix_shots_per_club';
    const workflow = novaAttrs(this._hass, workflowEntity);
    const player = novaValue(this._hass, playerEntity);
    const club = novaValue(this._hass, clubEntity);
    const count = workflow.bag_test_shot_count || 0;
    const target = workflow.shots_per_club || novaValue(this._hass, shotsEntity) || 5;
    this.innerHTML = `${novaStyles}<div class="nova-card">
      <p class="nova-title">Session Controls</p><h2 class="nova-hero">${novaEsc(player)} / ${novaEsc(club)}</h2>
      <p class="nova-muted">${novaEsc(novaValue(this._hass, workflowEntity) || 'Casual')} &middot; Progress ${count}/${target}</p>
      <div class="nova-actions">
        <button class="nova-btn" data-action="map">Map Club</button><button class="nova-btn" data-action="bag">Bag Test</button><button class="nova-btn secondary" data-action="discard">Discard</button><button class="nova-btn secondary" data-action="stop">Stop</button>
      </div>
    </div>`;
    this.querySelector('[data-action="map"]')?.addEventListener('click', () => novaCall(this._hass, 'start_mapping'));
    this.querySelector('[data-action="bag"]')?.addEventListener('click', () => novaCall(this._hass, 'start_bag_test'));
    this.querySelector('[data-action="discard"]')?.addEventListener('click', () => novaCall(this._hass, 'discard_last_shot'));
    this.querySelector('[data-action="stop"]')?.addEventListener('click', () => novaCall(this._hass, 'stop_session'));
  }
}

class NovaBagBuilderCard extends HTMLElement {
  setConfig(config) { this.config = config || {}; }
  set hass(hass) { this._hass = hass; this.render(); }
  render() {
    const playerEntity = this.config.player_entity || 'select.golf_range_matrix_range_matrix_active_player';
    const clubEntity = this.config.club_entity || 'select.golf_range_matrix_range_matrix_active_club';
    const player = novaValue(this._hass, playerEntity) || 'Tyler';
    const options = novaAttrs(this._hass, clubEntity).options || [];
    this.innerHTML = `${novaStyles}<div class="nova-card"><p class="nova-title">Bag Builder</p><h2 class="nova-hero">${novaEsc(player)} Bag</h2>
      <textarea class="nova-input" rows="4" placeholder="One club per line">${novaEsc(options.join('\n'))}</textarea>
      <div class="nova-actions"><button class="nova-btn">Save Bag</button></div></div>`;
    this.querySelector('button')?.addEventListener('click', () => {
      const clubs = this.querySelector('textarea').value.split('\n').map((v) => v.trim()).filter(Boolean).slice(0, 14);
      novaCall(this._hass, 'save_bag', { player, clubs });
    });
  }
}
novaDefine('range-bag-builder-card', NovaBagBuilderCard);

class NovaWedgeMatrixCard extends HTMLElement {
  setConfig(config) { this.config = config || {}; }
  set hass(hass) { this._hass = hass; this.render(); }
  render() {
    const player = novaValue(this._hass, this.config.player_entity || 'select.golf_range_matrix_range_matrix_active_player') || 'Tyler';
    this.innerHTML = `${novaStyles}<div class="nova-card"><p class="nova-title">Wedge Matrix</p><h2 class="nova-hero">Saved in Range Matrix SQLite</h2>
      <textarea class="nova-input" rows="8" placeholder='{"PW":{"Half":80,"Full":120}}'></textarea>
      <div class="nova-actions"><button class="nova-btn">Save Matrix JSON</button></div></div>`;
    this.querySelector('button')?.addEventListener('click', () => {
      let matrix = {};
      try { matrix = JSON.parse(this.querySelector('textarea').value || '{}'); } catch { alert('Matrix must be valid JSON'); return; }
      novaCall(this._hass, 'save_wedge_matrix', { player, matrix });
    });
  }
}

class GolfClubResultsCard extends HTMLElement {
  setConfig(config) { this.config = config || {}; }
  set hass(hass) {
    this._hass = hass;
    const playerEntity = this.config.player_entity || 'select.golf_range_matrix_range_matrix_active_player';
    const summaryEntity = this.config.summary_entity || 'sensor.golf_range_matrix_range_matrix_player_bag_summary';
    const sig = JSON.stringify([novaValue(hass, playerEntity), novaAttrs(hass, summaryEntity)]);
    if (sig === this._sig) return;
    this._sig = sig;
    this.render();
  }
  render() {
    const player = novaValue(this._hass, this.config.player_entity || 'select.golf_range_matrix_range_matrix_active_player') || 'Tyler';
    const clubs = novaAttrs(this._hass, this.config.summary_entity || 'sensor.golf_range_matrix_range_matrix_player_bag_summary').clubs || [];
    this.innerHTML = `${novaStyles}<div class="nova-card"><p class="nova-title">Results</p><h2 class="nova-hero">${novaEsc(player)} Club Results</h2><div class="nova-divider"></div>
      ${clubs.map((club, index) => this.club(player, club, index)).join('') || '<p class="nova-muted">Map a club to populate results.</p>'}</div>`;
    this.querySelectorAll('[data-save]').forEach((button) => button.addEventListener('click', (ev) => {
      const root = ev.target.closest('[data-club]');
      novaCall(this._hass, 'save_club_metadata', {
        player, club: root.dataset.club,
        brand: root.querySelector('[name="brand"]').value,
        model: root.querySelector('[name="model"]').value,
        image_url: root.querySelector('[name="image_url"]').value,
      });
    }));
  }
  club(player, club, index) {
    const avg = club.averages || {};
    const playable = club.playable_yardage?.carry || {};
    const meta = (novaAttrs(this._hass, this.config.summary_entity || 'sensor.golf_range_matrix_range_matrix_player_bag_summary').metadata || {})[club.club] || {};
    return `<div class="nova-tile nova-club" data-club="${novaEsc(club.club)}" style="margin:14px 0">
      ${meta.image_url ? `<img class="nova-img" src="${novaEsc(meta.image_url)}">` : `<div class="nova-img nova-fallback">GOLF</div>`}
      <div><h3 style="margin:0;font-size:24px">${novaEsc(club.club)}</h3><p class="nova-muted">${club.shot_count || 0} shots &middot; ${novaEsc(club.confidence?.rating || 'building')} confidence</p>
      <div class="nova-grid"><div><div class="nova-label">Avg Carry</div><div class="nova-value">${avg.carry ?? '--'} yd</div></div><div><div class="nova-label">Playable</div><div class="nova-value">${playable.low ?? '--'}-${playable.high ?? '--'}</div></div><div><div class="nova-label">Tendency</div><div class="nova-value" style="font-size:18px">${novaEsc(club.tendencies?.direction || '--')}</div></div></div>
      <details style="margin-top:12px"><summary>Club details</summary><div class="nova-row"><label>Brand<input class="nova-input" name="brand" value="${novaEsc(meta.brand || '')}"></label><label>Model<input class="nova-input" name="model" value="${novaEsc(meta.model || '')}"></label></div><label>Image URL<input class="nova-input" name="image_url" value="${novaEsc(meta.image_url || '')}"></label><button class="nova-btn" data-save="${index}">Save Club</button></details></div>
    </div>`;
  }
}

novaDefine('range-shot-tracer-card', NovaShotTracerCard);
novaDefine('range-metric-panel-card', GolfMetricPanelCard);
novaDefine('range-shot-history-card', GolfShotHistoryCard);
novaDefine('range-session-control-card', GolfSessionControlCard);
novaDefine('range-bag-builder-card', NovaBagBuilderCard);
novaDefine('range-wedge-matrix-card', NovaWedgeMatrixCard);
novaDefine('range-club-results-card', GolfClubResultsCard);
