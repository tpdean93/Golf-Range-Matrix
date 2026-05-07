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
  state(entity) { return novaState(this._hass, entity); }
  select(entity, option) { this._hass.callService('select', 'select_option', { entity_id: entity, option }); }
  setShots(entity, value) { this._hass.callService('number', 'set_value', { entity_id: entity, value }); }
  pill(label, value, icon) {
    return `<div class="stat"><ha-icon icon="${icon}"></ha-icon><div><span>${novaEsc(label)}</span><b>${novaEsc(value ?? '--')}</b></div></div>`;
  }
  render() {
    const workflowEntity = this.config.workflow_entity || 'sensor.golf_range_matrix_range_matrix_workflow';
    const playerEntity = this.config.player_entity || 'select.golf_range_matrix_range_matrix_active_player';
    const clubEntity = this.config.club_entity || 'select.golf_range_matrix_range_matrix_active_club';
    const shotsEntity = this.config.shots_per_club_entity || 'number.golf_range_matrix_range_matrix_shots_per_club';
    const workflow = novaAttrs(this._hass, workflowEntity);
    const player = novaValue(this._hass, playerEntity);
    const club = novaValue(this._hass, clubEntity);
    const recording = novaValue(this._hass, 'switch.golf_range_matrix_range_matrix_recording') === 'on';
    const players = novaAttrs(this._hass, playerEntity).options || [player].filter(Boolean);
    const clubs = novaAttrs(this._hass, clubEntity).options || [club].filter(Boolean);
    const count = Number(workflow.bag_test_shot_count || 0);
    const target = Number(workflow.shots_per_club || novaValue(this._hass, shotsEntity) || 5);
    this.innerHTML = `<ha-card><div class="panel">
      <div class="head"><div><div class="kicker">Practice Control</div><div class="title">Session Controls</div></div><div class="live ${recording ? 'on' : ''}"><span></span>${recording ? 'Recording' : 'Not Recording'}</div></div>
      <div class="stats">
        ${this.pill('Player', player, 'mdi:account')}
        ${this.pill('Club', club, 'mdi:golf-tee')}
        ${this.pill('Mode', novaValue(this._hass, workflowEntity) || 'Casual', 'mdi:golf')}
        ${this.pill('Bag Test', workflow.bag_test_active ? 'Active' : 'Off', 'mdi:format-list-numbered')}
        ${this.pill('Progress', `${Math.min(count, target)}/${target} valid`, 'mdi:counter')}
        ${this.pill('Session', workflow.session_id || 'none', 'mdi:identifier')}
      </div>
      <div class="sectionLabel">Player</div><div class="chips">${players.map(p => `<button class="chip ${p === player ? 'on' : ''}" data-player="${novaEsc(p)}">${novaEsc(p)}</button>`).join('')}</div>
      <div class="sectionLabel">Saved Bag Quick Select</div><div class="chips">${clubs.map(c => `<button class="chip ${c === club ? 'on' : ''}" data-club="${novaEsc(c)}">${novaEsc(c)}</button>`).join('')}</div>
      <div class="actions">
        <button class="action primary" data-action="map"><ha-icon icon="mdi:target"></ha-icon>Map Club</button>
        <button class="action primary" data-action="bag"><ha-icon icon="mdi:playlist-play"></ha-icon>Bag Test</button>
        <button class="action danger" data-action="discard"><ha-icon icon="mdi:delete-restore"></ha-icon>Discard</button>
        <button class="action" data-action="stop"><ha-icon icon="mdi:stop-circle"></ha-icon>Stop</button>
      </div>
      <div class="stepper"><button data-step="-1">-</button><span>${target} shots per club</span><button data-step="1">+</button></div>
    </div></ha-card><style>
      ha-card{border:0;border-radius:26px;background:linear-gradient(145deg,rgba(18,25,45,.94),rgba(8,12,24,.86));color:white;overflow:hidden;box-shadow:0 22px 60px rgba(0,0,0,.34)}.panel{padding:18px;position:relative;isolation:isolate}.panel:before{content:'';position:absolute;inset:-30% auto auto 30%;width:360px;height:260px;border-radius:50%;background:radial-gradient(circle,rgba(56,248,255,.22),transparent 64%);z-index:-1}.head{display:flex;align-items:center;justify-content:space-between;gap:12px}.kicker,.sectionLabel{color:#8ffcff;font-size:10px;font-weight:900;letter-spacing:.18em;text-transform:uppercase}.title{font-size:24px;font-weight:950;letter-spacing:-.05em}.live{display:flex;align-items:center;gap:8px;padding:9px 12px;border-radius:999px;background:rgba(255,255,255,.08);font-weight:900;color:rgba(255,255,255,.7)}.live span{width:9px;height:9px;border-radius:50%;background:#ff5d7a;box-shadow:0 0 12px #ff5d7a}.live.on span{background:#72ff7d;box-shadow:0 0 12px #72ff7d}.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:16px 0}.stat{display:grid;grid-template-columns:30px minmax(0,1fr);gap:9px;align-items:center;padding:12px;border-radius:18px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.11)}.stat ha-icon{color:#8ffcff}.stat span{display:block;color:rgba(255,255,255,.55);font-size:10px;text-transform:uppercase;letter-spacing:.1em;font-weight:900}.stat b{display:block;margin-top:4px;font-size:16px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.chips{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 14px}.chip,.action,.stepper button{border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.08);color:white;border-radius:999px;font-weight:900}.chip{padding:8px 11px}.chip.on{background:rgba(247,255,92,.16);border-color:rgba(247,255,92,.42);color:#f7ff8a}.actions{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px;margin-top:12px}.action{display:flex;flex-direction:column;align-items:center;gap:6px;padding:12px 8px;border-radius:18px}.action ha-icon{color:#8ffcff}.action.primary{background:rgba(56,248,255,.12);border-color:rgba(56,248,255,.35)}.action.danger ha-icon{color:#ff8aa1}.stepper{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:14px;padding:10px 12px;border-radius:18px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.11);font-weight:900}.stepper button{width:34px;height:30px;color:#f7ff8a}@media(max-width:760px){.stats{grid-template-columns:1fr}.actions{grid-template-columns:repeat(2,minmax(0,1fr))}}
    </style>`;
    this.querySelectorAll('[data-player]').forEach(b => b.addEventListener('click', () => this.select(playerEntity, b.dataset.player)));
    this.querySelectorAll('[data-club]').forEach(b => b.addEventListener('click', () => this.select(clubEntity, b.dataset.club)));
    this.querySelector('[data-action="map"]')?.addEventListener('click', () => novaCall(this._hass, 'start_mapping'));
    this.querySelector('[data-action="bag"]')?.addEventListener('click', () => novaCall(this._hass, 'start_bag_test'));
    this.querySelector('[data-action="discard"]')?.addEventListener('click', () => novaCall(this._hass, 'discard_last_shot'));
    this.querySelector('[data-action="stop"]')?.addEventListener('click', () => novaCall(this._hass, 'stop_session'));
    this.querySelectorAll('[data-step]').forEach(b => b.addEventListener('click', () => this.setShots(shotsEntity, Math.max(1, Math.min(20, target + Number(b.dataset.step))))));
  }
}

class NovaBagBuilderCard extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    this.catalog = this.config.catalog || ['Driver','3 Wood','5 Wood','7 Wood','3 Hybrid','4 Hybrid','5 Hybrid','4 Iron','5 Iron','6 Iron','7 Iron','8 Iron','9 Iron','PW','GW','52 Wedge','56 Wedge','60 Wedge','Putter'];
    this.maxClubs = this.config.max_clubs || 14;
    this._draft = null;
    this._draftPlayer = null;
  }
  set hass(hass) { this._hass = hass; this.render(); }
  playerEntity() { return this.config.player_entity || 'select.golf_range_matrix_range_matrix_active_player'; }
  clubEntity() { return this.config.club_entity || 'select.golf_range_matrix_range_matrix_active_club'; }
  player() { return novaValue(this._hass, this.playerEntity()) || 'Tyler'; }
  savedBag() { return novaAttrs(this._hass, this.clubEntity()).options || []; }
  selected() {
    if (this._draftPlayer !== this.player() || !this._draft) {
      this._draftPlayer = this.player();
      this._draft = [...this.savedBag()];
    }
    return this._draft;
  }
  allClubs() {
    const clubs = [];
    [...this.catalog, ...this.savedBag(), ...this.selected()].forEach(club => {
      if (club && !clubs.some(c => c.toLowerCase() === club.toLowerCase())) clubs.push(club);
    });
    return clubs;
  }
  selectPlayer(player) { this._hass.callService('select', 'select_option', { entity_id: this.playerEntity(), option: player }); this._draft = null; }
  selectClub(club) { this._hass.callService('select', 'select_option', { entity_id: this.clubEntity(), option: club }); }
  addClub(club) {
    const clean = String(club || '').trim().replace(/\s+/g, ' ');
    if (!clean || this.selected().some(c => c.toLowerCase() === clean.toLowerCase()) || this.selected().length >= this.maxClubs) return;
    this._draft = [...this.selected(), clean];
    this.render();
  }
  toggleClub(club) {
    const selected = [...this.selected()];
    const idx = selected.findIndex(c => c.toLowerCase() === String(club).toLowerCase());
    if (idx >= 0) selected.splice(idx, 1);
    else if (selected.length < this.maxClubs) selected.push(club);
    this._draft = selected;
    this.render();
  }
  saveBag() { novaCall(this._hass, 'save_bag', { player: this.player(), clubs: this.selected().slice(0, this.maxClubs) }); }
  changeLabel(selected, saved) {
    const added = selected.filter(c => !saved.some(s => s.toLowerCase() === c.toLowerCase())).length;
    const removed = saved.filter(c => !selected.some(s => s.toLowerCase() === c.toLowerCase())).length;
    return added || removed ? [`+${added}`, `-${removed}`].filter(p => !p.endsWith('0')).join(' / ') : 'Saved';
  }
  render() {
    const player = this.player();
    const players = novaAttrs(this._hass, this.playerEntity()).options || [player];
    const selected = this.selected();
    const saved = this.savedBag();
    const active = novaValue(this._hass, this.clubEntity());
    const dirty = selected.join('|') !== saved.join('|');
    this.innerHTML = `<ha-card><div class="panel">
      <div class="head"><div><div class="kicker">Player Bag</div><div class="title">Bag Builder</div></div><button class="save ${dirty ? 'dirty' : ''}">${dirty ? 'Save Changes' : 'Saved'}</button></div>
      <div class="note">Click clubs below to add or remove them from this player bag. Add a custom club if it is not in the list. Maximum ${this.maxClubs} clubs.</div>
      <div class="players">${players.map(p => `<button class="pill ${p === player ? 'on' : ''}" data-player="${novaEsc(p)}">${novaEsc(p)}</button>`).join('')}</div>
      <div class="summary"><div><span>Player</span><b>${novaEsc(player)}</b></div><div><span>Saved Clubs</span><b>${saved.length}/${this.maxClubs}</b></div><div><span>Status</span><b>${dirty ? this.changeLabel(selected, saved) : 'Saved'}</b></div><div><span>Active</span><b>${novaEsc(active || '--')}</b></div></div>
      <div class="stripLabel">Saved bag. Click one to make it active.</div>
      <div class="bagStrip">${saved.map((club, idx) => `<button class="bagClub ${active === club ? 'active' : ''}" data-active-club="${novaEsc(club)}"><b>${idx + 1}</b>${novaEsc(club)}</button>`).join('') || '<div class="empty">Save clubs below to build this player bag.</div>'}</div>
      <div class="customClub"><input placeholder="Add custom club, ex. Mini Driver" ${selected.length >= this.maxClubs ? 'disabled' : ''}><button class="addCustom" ${selected.length >= this.maxClubs ? 'disabled' : ''}>Add Custom</button></div>
      <div class="clubGrid">${this.allClubs().map(club => {
        const inDraft = selected.some(c => c.toLowerCase() === club.toLowerCase());
        const inSaved = saved.some(c => c.toLowerCase() === club.toLowerCase());
        const disabled = selected.length >= this.maxClubs && !inDraft;
        const label = active === club ? 'Active' : inDraft && inSaved ? 'In bag' : inDraft ? 'Pending add' : inSaved ? 'Pending remove' : disabled ? 'Max 14' : 'Add';
        return `<button class="club ${inDraft ? 'inBag' : ''} ${inSaved ? 'savedClub' : ''} ${active === club ? 'active' : ''} ${disabled ? 'disabled' : ''}" data-club="${novaEsc(club)}" ${disabled ? 'disabled' : ''}><span>${novaEsc(club)}</span><small>${label}</small></button>`;
      }).join('')}</div>
    </div></ha-card><style>
      ha-card{border:0;border-radius:26px;background:linear-gradient(145deg,rgba(18,25,45,.94),rgba(8,12,24,.86));color:white;overflow:hidden;box-shadow:0 22px 60px rgba(0,0,0,.34)}.panel{padding:18px;position:relative;isolation:isolate}.panel:before{content:'';position:absolute;inset:-35% -20% auto auto;width:300px;height:260px;border-radius:50%;background:radial-gradient(circle,rgba(56,248,255,.22),transparent 64%);z-index:-1}.head{display:flex;justify-content:space-between;gap:12px;align-items:center}.kicker{color:#8ffcff;font-size:10px;font-weight:900;letter-spacing:.18em;text-transform:uppercase}.title{font-size:24px;font-weight:950;letter-spacing:-.05em}.note{margin-top:12px;color:rgba(255,255,255,.7);font-size:13px;font-weight:750;line-height:1.35}.save,.pill,.club,.bagClub,.addCustom{border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.08);color:white;border-radius:999px;font-weight:850}.save{padding:9px 12px;color:#b8ffbf}.save.dirty{color:#f7ff8a;border-color:rgba(247,255,92,.4);background:rgba(247,255,92,.12)}.players{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}.pill{padding:9px 12px}.pill.on{background:rgba(247,255,92,.16);border-color:rgba(247,255,92,.45);color:#f7ff8a}.summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:14px}.summary div{padding:12px;border-radius:18px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.11)}.summary span,.stripLabel{display:block;color:rgba(255,255,255,.55);font-size:10px;text-transform:uppercase;letter-spacing:.12em;font-weight:900}.summary b{display:block;margin-top:5px;font-size:18px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.stripLabel{margin:4px 0 8px}.bagStrip{display:flex;gap:8px;overflow:auto;padding:4px 0 12px}.bagClub{padding:8px 10px;white-space:nowrap;color:rgba(255,255,255,.78)}.bagClub b{color:#8ffcff;margin-right:6px}.bagClub.active{background:rgba(56,248,255,.16);border-color:rgba(56,248,255,.45);color:#8ffcff}.customClub{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;margin:0 0 12px}.customClub input{min-width:0;border:1px solid rgba(255,255,255,.14);border-radius:16px;background:rgba(0,0,0,.22);color:white;padding:12px;font-weight:800;outline:none}.addCustom{border-radius:16px;padding:0 13px;color:#8ffcff}.addCustom:disabled,.customClub input:disabled{opacity:.45}.clubGrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}.club{border-radius:16px;padding:12px;text-align:left;min-height:62px}.club span{display:block;font-size:15px;font-weight:900}.club small{display:block;margin-top:5px;color:rgba(255,255,255,.48);font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.1em}.club.inBag{background:rgba(255,255,255,.115);border-color:rgba(255,255,255,.18)}.club.savedClub small{color:#b8ffbf}.club.active{box-shadow:inset 0 0 0 1px rgba(247,255,92,.48);color:#f7ff8a}.club.disabled{opacity:.42}.empty{color:rgba(255,255,255,.55);font-weight:800;padding:9px 0}@media(max-width:760px){.clubGrid{grid-template-columns:repeat(2,minmax(0,1fr))}.summary{grid-template-columns:repeat(2,minmax(0,1fr))}}
    </style>`;
    this.querySelectorAll('[data-player]').forEach(b => b.addEventListener('click', () => this.selectPlayer(b.dataset.player)));
    this.querySelectorAll('[data-club]').forEach(b => b.addEventListener('click', () => this.toggleClub(b.dataset.club)));
    this.querySelectorAll('[data-active-club]').forEach(b => b.addEventListener('click', () => this.selectClub(b.dataset.activeClub)));
    this.querySelector('.save')?.addEventListener('click', () => this.saveBag());
    const input = this.querySelector('.customClub input');
    this.querySelector('.addCustom')?.addEventListener('click', () => this.addClub(input?.value));
    input?.addEventListener('keydown', ev => { if (ev.key === 'Enter') this.addClub(input.value); });
  }
}
novaDefine('range-bag-builder-card', NovaBagBuilderCard);

class NovaWedgeMatrixCard extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    this.defaultSwings = this.config.swings || ['Half', 'Waist', 'Shoulder', 'Full'];
    this.captureTarget = this.config.capture_shots || 5;
    this._draft = null;
    this._draftPlayer = null;
    this._selected = null;
    this._capture = null;
  }
  set hass(hass) { this._hass = hass; this.captureShotIfNeeded(hass); this.render(); }
  playerEntity() { return this.config.player_entity || 'select.golf_range_matrix_range_matrix_active_player'; }
  clubEntity() { return this.config.club_entity || 'select.golf_range_matrix_range_matrix_active_club'; }
  summaryEntity() { return this.config.summary_entity || 'sensor.golf_range_matrix_range_matrix_player_bag_summary'; }
  carryEntity() { return this.config.carry_entity || 'sensor.golf_range_matrix_range_matrix_carry'; }
  player() { return novaValue(this._hass, this.playerEntity()) || 'Tyler'; }
  attrs() { return novaAttrs(this._hass, this.summaryEntity()); }
  savedBag() { return this.attrs().bag || novaAttrs(this._hass, this.clubEntity()).options || []; }
  swingTypes() { return this.config.swings || this.defaultSwings; }
  isWedge(club) {
    const normalized = String(club || '').trim().toLowerCase();
    if (!normalized) return false;
    if (['pw','gw','sw','lw','aw','uw'].includes(normalized)) return true;
    if (normalized.includes('wedge')) return true;
    return /^(4[6-9]|5[0-9]|6[0-4])\s*(deg|degree)?$/.test(normalized);
  }
  matrix() {
    if (this._draftPlayer !== this.player() || !this._draft) {
      this._draftPlayer = this.player();
      this._draft = JSON.parse(JSON.stringify(this.attrs().wedge_matrix || {}));
    }
    return this._draft;
  }
  wedges() { return this.savedBag().filter(club => this.isWedge(club)); }
  dirty() { return JSON.stringify(this.matrix()) !== JSON.stringify(this.attrs().wedge_matrix || {}); }
  selectCell(club, swing) { this._selected = { club, swing }; this.render(); }
  updateSelected(value) {
    if (!this._selected) return;
    const matrix = this.matrix();
    matrix[this._selected.club] = matrix[this._selected.club] || {};
    const clean = String(value || '').trim();
    if (clean) matrix[this._selected.club][this._selected.swing] = clean;
    else delete matrix[this._selected.club][this._selected.swing];
    this._draft = matrix;
    this.render();
  }
  save() { novaCall(this._hass, 'save_wedge_matrix', { player: this.player(), matrix: this.matrix() }); }
  carryState(hass = this._hass) { return hass?.states?.[this.carryEntity()]; }
  carrySignature(hass = this._hass) { const state = this.carryState(hass); return state ? `${state.state}:${state.last_changed || state.last_updated || ''}` : ''; }
  carryValue(hass = this._hass) { const value = Number(this.carryState(hass)?.state); return Number.isFinite(value) && value > 0 ? value : null; }
  startCapture() {
    if (!this._selected) return;
    this._hass.callService('select', 'select_option', { entity_id: this.clubEntity(), option: this._selected.club });
    this._capture = { club: this._selected.club, swing: this._selected.swing, shots: [], signature: this.carrySignature() };
    this.render();
  }
  stopCapture() { this._capture = null; this.render(); }
  throwOutCaptureShot() { if (this._capture?.shots?.length) this._capture.shots.pop(); this.render(); }
  captureShotIfNeeded(hass) {
    if (!this._capture) return;
    const signature = this.carrySignature(hass);
    if (!signature || signature === this._capture.signature) return;
    this._capture.signature = signature;
    const carry = this.carryValue(hass);
    if (carry === null) return;
    this._capture.shots.push(carry);
    if (this._capture.shots.length >= this.captureTarget) {
      const avg = this._capture.shots.reduce((sum, value) => sum + value, 0) / this._capture.shots.length;
      this._selected = { club: this._capture.club, swing: this._capture.swing };
      this.updateSelected(avg.toFixed(1).replace(/\.0$/, ''));
      this._capture = null;
    }
  }
  renderTable() {
    const wedges = this.wedges();
    if (!wedges.length) return '<div class="empty">No wedges are saved in this player bag yet. Add wedges in the Bag Builder first.</div>';
    const matrix = this.matrix();
    return `<table><thead><tr><th>Swing</th>${wedges.map(club => `<th>${novaEsc(club)}</th>`).join('')}</tr></thead><tbody>${this.swingTypes().map(swing => `<tr><th>${novaEsc(swing)}</th>${wedges.map(club => {
      const value = matrix?.[club]?.[swing] || '';
      const selected = this._selected?.club === club && this._selected?.swing === swing;
      return `<td><button class="cell ${selected ? 'selected' : ''} ${value ? 'filled' : ''}" data-club="${novaEsc(club)}" data-swing="${novaEsc(swing)}">${value ? novaEsc(value) : '--'}</button></td>`;
    }).join('')}</tr>`).join('')}</tbody></table>`;
  }
  render() {
    const dirty = this.dirty();
    const selected = this._selected;
    const value = selected ? this.matrix()?.[selected.club]?.[selected.swing] || '' : '';
    const capture = this._capture;
    const avg = capture?.shots?.length ? (capture.shots.reduce((sum, shot) => sum + shot, 0) / capture.shots.length).toFixed(1) : '--';
    this.innerHTML = `<ha-card><div class="panel">
      <div class="head"><div><div class="kicker">Short Game</div><div class="title">Wedge Matrix</div></div><button class="save ${dirty ? 'dirty' : ''}">${dirty ? 'Save Matrix' : 'Saved'}</button></div>
      <div class="note">Build confidence inside scoring range. This matrix only shows wedges saved in the selected player bag.</div>
      <div class="tableWrap">${this.renderTable()}</div>
      <div class="editor"><div><span>Selected</span><b>${selected ? `${novaEsc(selected.club)} / ${novaEsc(selected.swing)}` : 'Pick a cell'}</b></div><input class="yardInput" placeholder="Yards or range, ex. 74/80" value="${novaEsc(value)}" ${selected ? '' : 'disabled'}><button class="apply" ${selected ? '' : 'disabled'}>Set</button></div>
      <div class="capturePanel"><div><span>5-shot capture</span><b>${capture ? `${capture.club} / ${capture.swing}: ${capture.shots.length}/${this.captureTarget} shots` : 'Pick a cell, start capture, then hit shots.'}</b><small>Running avg: ${novaEsc(avg)}</small></div><button class="captureStart" ${selected && !capture ? '' : 'disabled'}>Start</button><button class="captureThrow" ${capture?.shots?.length ? '' : 'disabled'}>Throw Out Last</button><button class="captureStop" ${capture ? '' : 'disabled'}>Reset</button></div>
      <div class="manageNote">Need another wedge here? Add it to the player bag first.</div>
    </div></ha-card><style>
      ha-card{border:0;border-radius:26px;background:linear-gradient(145deg,rgba(18,25,45,.94),rgba(8,12,24,.86));color:white;overflow:hidden;box-shadow:0 22px 60px rgba(0,0,0,.34)}.panel{padding:18px;position:relative;isolation:isolate}.panel:before{content:'';position:absolute;inset:-30% -20% auto auto;width:300px;height:250px;border-radius:50%;background:radial-gradient(circle,rgba(247,255,92,.18),transparent 64%);z-index:-1}.head{display:flex;align-items:center;justify-content:space-between;gap:12px}.kicker{color:#8ffcff;font-size:10px;font-weight:900;letter-spacing:.18em;text-transform:uppercase}.title{font-size:24px;font-weight:950;letter-spacing:-.05em}.note,.manageNote{margin-top:12px;color:rgba(255,255,255,.68);font-size:13px;font-weight:750;line-height:1.35}.manageNote{color:rgba(255,255,255,.48);font-size:12px}.save,.cell,.apply,.captureStart,.captureThrow,.captureStop{border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.08);color:white;border-radius:999px;font-weight:900}.save{padding:9px 12px;color:#b8ffbf}.save.dirty{color:#f7ff8a;border-color:rgba(247,255,92,.4);background:rgba(247,255,92,.12)}.tableWrap{margin-top:16px;overflow:visible;border-radius:18px;border:1px solid rgba(255,255,255,.12);background:rgba(0,0,0,.18)}table{width:100%;table-layout:fixed;border-collapse:collapse;min-width:0}th,td{border-bottom:1px solid rgba(255,255,255,.1);border-right:1px solid rgba(255,255,255,.08);padding:8px;text-align:center}th{color:rgba(255,255,255,.58);font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.12em}thead th:first-child,tbody th{width:86px}tbody th{text-align:left;color:#8ffcff}.cell{width:100%;min-height:42px;border-radius:13px;font-size:clamp(13px,1.8vw,16px);padding:0 6px}.cell.filled{background:rgba(56,248,255,.12);border-color:rgba(56,248,255,.28);color:#d8fdff}.cell.selected{box-shadow:inset 0 0 0 1px rgba(247,255,92,.75);color:#f7ff8a}.editor,.capturePanel{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) auto;gap:9px;align-items:center;margin-top:12px}.capturePanel{grid-template-columns:minmax(0,1fr) auto auto auto}.editor div,.capturePanel div{padding:10px;border-radius:16px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.11)}.editor span,.capturePanel span{display:block;color:rgba(255,255,255,.5);font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.12em}.editor b,.capturePanel b{display:block;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.capturePanel small{display:block;margin-top:4px;color:#8ffcff;font-weight:850}.yardInput{min-width:0;border:1px solid rgba(255,255,255,.14);border-radius:16px;background:rgba(0,0,0,.22);color:white;padding:12px;font-weight:850;outline:none}.apply,.captureStart,.captureThrow,.captureStop{border-radius:16px;padding:0 13px;height:42px;color:#8ffcff}.captureStart{color:#f7ff8a}.captureThrow,.captureStop{color:#ff9aad}.apply:disabled,.yardInput:disabled,.captureStart:disabled,.captureThrow:disabled,.captureStop:disabled{opacity:.45}.empty{padding:18px;color:rgba(255,255,255,.62);font-weight:850;text-align:center}@media(max-width:760px){.tableWrap{overflow:auto}table{min-width:520px}.editor,.capturePanel{grid-template-columns:1fr}.apply,.captureStart,.captureThrow,.captureStop{width:100%}}
    </style>`;
    this.querySelectorAll('[data-club]').forEach(button => button.addEventListener('click', () => this.selectCell(button.dataset.club, button.dataset.swing)));
    this.querySelector('.save')?.addEventListener('click', () => this.save());
    this.querySelector('.apply')?.addEventListener('click', () => this.updateSelected(this.querySelector('.yardInput')?.value));
    this.querySelector('.yardInput')?.addEventListener('keydown', ev => { if (ev.key === 'Enter') this.updateSelected(ev.currentTarget.value); });
    this.querySelector('.captureStart')?.addEventListener('click', () => this.startCapture());
    this.querySelector('.captureThrow')?.addEventListener('click', () => this.throwOutCaptureShot());
    this.querySelector('.captureStop')?.addEventListener('click', () => this.stopCapture());
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
    const attrs = novaAttrs(this._hass, this.config.summary_entity || 'sensor.golf_range_matrix_range_matrix_player_bag_summary');
    const clubs = attrs.clubs || [];
    const mapped = clubs.filter(club => Number(club.shot_count || 0) > 0).length;
    const totalShots = attrs.shot_count || 0;
    this.innerHTML = `<ha-card><section class="panel">
      <div class="head"><div><div class="kicker">Mapped Bag Results</div><h2>${novaEsc(player)}'s Club Cards</h2><p>${mapped} mapped clubs | ${totalShots} saved shots | updates when you re-map</p></div><div class="summaryBadge"><span>${clubs.length}</span><small>clubs</small></div></div>
      <div class="grid">${clubs.length ? clubs.map((club, index) => this.club(player, club, index)).join('') : '<div class="empty">Map or save clubs to build this results wall.</div>'}</div>
    </section></ha-card><style>
      ha-card{border:0;border-radius:30px;background:linear-gradient(145deg,rgba(18,25,45,.94),rgba(8,12,24,.86));color:white;overflow:hidden;box-shadow:0 24px 70px rgba(0,0,0,.36)}
      .panel{position:relative;isolation:isolate;padding:20px}.panel:before{content:'';position:absolute;inset:-160px -120px auto auto;width:520px;height:420px;border-radius:50%;background:radial-gradient(circle,rgba(56,248,255,.20),transparent 64%);z-index:-1}.panel:after{content:'';position:absolute;left:-140px;bottom:-180px;width:460px;height:360px;border-radius:50%;background:radial-gradient(circle,rgba(168,85,247,.22),transparent 65%);z-index:-1}
      .head{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:18px}.kicker{color:#8ffcff;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.18em}h2{margin:4px 0 0;font-size:30px;line-height:1;font-weight:950;letter-spacing:-.05em}p{margin:8px 0 0;color:rgba(255,255,255,.66);font-weight:750}.summaryBadge{min-width:82px;min-height:82px;border-radius:26px;display:grid;place-items:center;background:rgba(247,255,92,.12);border:1px solid rgba(247,255,92,.35);box-shadow:inset 0 0 28px rgba(247,255,92,.08)}.summaryBadge span{font-size:30px;font-weight:950;color:#f7ff8a}.summaryBadge small{margin-top:-18px;color:rgba(255,255,255,.72);font-weight:900;text-transform:uppercase;letter-spacing:.12em}
      .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:16px}.clubCard{border:1px solid rgba(255,255,255,.12);border-radius:26px;background:linear-gradient(145deg,rgba(255,255,255,.08),rgba(255,255,255,.035));padding:14px;box-shadow:inset 0 1px 0 rgba(255,255,255,.08);overflow:hidden}.top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.club{font-size:26px;font-weight:950;letter-spacing:-.05em}.model{margin-top:3px;color:rgba(255,255,255,.62);font-size:13px;font-weight:850}.badge{white-space:nowrap;border-radius:999px;padding:7px 10px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);font-size:12px;font-weight:950;color:rgba(255,255,255,.72)}.badge.mapped{background:rgba(114,255,125,.13);border-color:rgba(114,255,125,.34);color:#b8ffbf}
      .body{display:grid;grid-template-columns:130px minmax(0,1fr);gap:13px;margin-top:14px}.photo{height:154px;border-radius:22px;overflow:hidden;background:radial-gradient(circle at 50% 22%,rgba(56,248,255,.22),rgba(0,0,0,.25));border:1px solid rgba(255,255,255,.10);display:grid;place-items:center}.photo img{width:100%;height:100%;object-fit:cover}.fallback{display:grid;place-items:center;gap:8px;color:#8ffcff;text-align:center}.fallback ha-icon{--mdc-icon-size:44px}.fallback strong{max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:white}.numbers,.details{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.numbers div,.details div{border-radius:16px;padding:10px;background:rgba(0,0,0,.22);border:1px solid rgba(255,255,255,.09)}.numbers span,.details span{display:block;color:rgba(255,255,255,.52);font-size:10px;font-weight:950;letter-spacing:.12em;text-transform:uppercase}.numbers b{display:block;margin-top:5px;font-size:19px;font-weight:950;color:#f7ff8a}.details{margin-top:10px}.details b{display:block;margin-top:4px;font-size:14px;font-weight:900}
      .insight{display:grid;gap:4px;margin-top:12px;padding:12px;border-radius:18px;background:rgba(56,248,255,.08);border:1px solid rgba(56,248,255,.16)}.insight strong{color:#8ffcff;text-transform:capitalize}.insight span{color:rgba(255,255,255,.82);font-weight:850}.insight small{color:rgba(255,255,255,.58);font-weight:700;line-height:1.35}
      .editor{margin-top:12px;border-radius:18px;background:rgba(0,0,0,.16);border:1px solid rgba(255,255,255,.10);padding:9px 11px}.editor summary{cursor:pointer;font-weight:950;color:#8ffcff}.editor label{display:block;margin-top:10px;color:rgba(255,255,255,.58);font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.12em}.editor input{box-sizing:border-box;width:100%;margin-top:5px;border:1px solid rgba(255,255,255,.14);border-radius:12px;background:rgba(0,0,0,.28);color:white;padding:10px;font-weight:800;outline:none}.editor button{margin-top:11px;width:100%;border:1px solid rgba(247,255,92,.36);border-radius:14px;background:rgba(247,255,92,.12);color:#f7ff8a;padding:10px;font-weight:950}.empty{grid-column:1/-1;padding:24px;border-radius:24px;background:rgba(255,255,255,.07);color:rgba(255,255,255,.72);font-weight:850}
      @media(max-width:720px){.head{align-items:flex-start}.summaryBadge{display:none}.body{grid-template-columns:1fr}.photo{height:190px}}
    </style>`;
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
    const shotCount = Number(club.shot_count || 0);
    const title = [meta.brand, meta.model].filter(Boolean).join(' ');
    const confidence = club.confidence?.rating || 'unmapped';
    const tendency = club.tendencies?.direction || 'Ready to map';
    const dispersion = club.tendencies?.dispersion || 'No saved shots yet';
    const image = String(meta.image_url || '').trim();
    const hero = [['Carry', avg.carry ? `${avg.carry} yd` : '--'], ['Total', avg.total ? `${avg.total} yd` : '--'], ['Playable', playable.low != null && playable.high != null ? `${playable.low}-${playable.high} yd` : '--'], ['Offline', avg.offline != null ? `${avg.offline} yd` : '--']]
      .map(([label, value]) => `<div><span>${label}</span><b>${novaEsc(value)}</b></div>`).join('');
    const details = [['Launch', avg.launch_angle ? `${avg.launch_angle} deg` : '--'], ['Spin', avg.total_spin ? `${avg.total_spin} rpm` : '--'], ['Ball', avg.ball_speed ? `${avg.ball_speed} mph` : '--'], ['Smash', avg.smash_factor ?? '--']]
      .map(([label, value]) => `<div><span>${label}</span><b>${novaEsc(value)}</b></div>`).join('');
    return `<article class="clubCard" data-club="${novaEsc(club.club)}">
      <div class="top"><div><div class="club">${novaEsc(club.club)}</div><div class="model">${novaEsc(title || 'Add brand + model')}</div></div><div class="badge ${shotCount >= 5 ? 'mapped' : ''}">${shotCount ? `${shotCount} shots` : 'unmapped'}</div></div>
      <div class="body"><div class="photo">${image ? `<img src="${novaEsc(image)}" alt="${novaEsc(club.club)}" loading="lazy">` : `<div class="fallback"><ha-icon icon="mdi:golf-tee"></ha-icon><strong>${novaEsc(club.club)}</strong></div>`}</div><div class="numbers">${hero}</div></div>
      <div class="insight"><strong>${novaEsc(confidence)} confidence</strong><span>${novaEsc(tendency)} | ${novaEsc(dispersion)}</span><small>${novaEsc(club.ai_notes || 'Map this club to unlock averages, playable yardage, and shot tendencies.')}</small></div>
      <div class="details">${details}</div>
      <details class="editor"><summary>Club details</summary><label>Brand<input name="brand" value="${novaEsc(meta.brand || '')}" placeholder="Titleist"></label><label>Model<input name="model" value="${novaEsc(meta.model || '')}" placeholder="Vokey SM10"></label><label>Image URL<input name="image_url" value="${novaEsc(image)}" placeholder="https://..."></label><button data-save="${index}">Save Club Details</button></details>
    </article>`;
  }
}

novaDefine('range-shot-tracer-card', NovaShotTracerCard);
novaDefine('range-metric-panel-card', GolfMetricPanelCard);
novaDefine('range-shot-history-card', GolfShotHistoryCard);
novaDefine('range-session-control-card', GolfSessionControlCard);
novaDefine('range-bag-builder-card', NovaBagBuilderCard);
novaDefine('range-wedge-matrix-card', NovaWedgeMatrixCard);
novaDefine('range-club-results-card', GolfClubResultsCard);
