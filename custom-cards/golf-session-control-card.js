class GolfSessionControlCard extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    this.bagEntities = this.config.bag_entities || {};
    this.profileEntity = this.config.profiles_entity || 'input_text.golf_profiles_json';
    this.profileBagsEntity = this.config.profile_bags_entity || 'input_text.golf_profile_bags_json';
  }
  set hass(hass) { this._hass = hass; this.render(); }
  getCardSize() { return 6; }
  state(e) { return this._hass?.states?.[e]; }
  esc(v) { return String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
  parseJson(text, fallback) { try { return JSON.parse(text || ''); } catch { return fallback; } }
  call(domain, service, data) { this._hass.callService(domain, service, data); }
  press(entity) { this.call('input_button', 'press', { entity_id: entity }); }
  setSelect(entity, option) { this.call('input_select', 'select_option', { entity_id: entity, option }); }
  setNumber(entity, value) { this.call('input_number', 'set_value', { entity_id: entity, value }); }
  player() { return this.state(this.config.player_entity)?.state || this.players()[0] || 'Tyler'; }
  players() {
    const parsed = this.parseJson(this.state(this.profileEntity)?.state, null);
    const players = Array.isArray(parsed) ? parsed : Array.isArray(parsed?.players) ? parsed.players : this.config.players;
    return (players || ['Tyler', 'Kids', 'Guest']).map(p => String(p).trim()).filter(Boolean);
  }
  chunkEntities(entity) { return [entity, `${entity}_2`, `${entity}_3`, `${entity}_4`]; }
  chunkText(entity) { return this.chunkEntities(entity).map(e => this.state(e)?.state || '').join(''); }
  saveChunked(entity, text) {
    this.chunkEntities(entity).forEach((e, idx) => this.call('input_text', 'set_value', { entity_id: e, value: text.slice(idx * 240, (idx + 1) * 240) }));
  }
  bagMap() { return this.parseJson(this.chunkText(this.profileBagsEntity), {}) || {}; }
  savePlayers(players, nextPlayer = null) {
    const clean = players.map(p => String(p).trim()).filter(Boolean);
    this.call('input_text', 'set_value', { entity_id: this.profileEntity, value: JSON.stringify({ players: clean }) });
    this.call('input_select', 'set_options', { entity_id: this.config.player_entity, options: clean });
    if (nextPlayer) this.setSelect(this.config.player_entity, nextPlayer);
  }
  saveBagMap(map) {
    this.saveChunked(this.profileBagsEntity, JSON.stringify(map));
  }
  addProfile() {
    const input = this.querySelector('.profileName');
    const clean = String(input?.value || '').trim().replace(/\s+/g, ' ');
    if (!clean) return;
    const players = this.players();
    if (players.some(p => p.toLowerCase() === clean.toLowerCase())) return;
    const map = this.bagMap();
    map[clean] = map[clean] || '';
    this.saveBagMap(map);
    this.savePlayers([...players, clean], clean);
  }
  removeProfile() {
    const current = this.player();
    const players = this.players();
    if (players.length <= 1) return;
    const next = players.find(p => p !== current) || players[0];
    const map = this.bagMap();
    delete map[current];
    this.saveBagMap(map);
    this.savePlayers(players.filter(p => p !== current), next);
  }
  bagEntity() { return this.bagEntities[this.player()] || this.bagEntities.Tyler; }
  savedBag() {
    const fromMap = String(this.bagMap()[this.player()] || '').split(',').map(s => s.trim()).filter(Boolean).slice(0, 14);
    if (fromMap.length) return fromMap;
    const entity = this.bagEntity();
    const saved = entity ? (this.state(entity)?.state || '').split(',').map(s => s.trim()).filter(Boolean).slice(0, 14) : [];
    return saved.length ? saved : (this.config.quick_clubs || ['Driver']);
  }

  pill(label, value, icon) { return `<div class="stat"><ha-icon icon="${icon}"></ha-icon><div><span>${label}</span><b>${this.esc(value)}</b></div></div>`; }
  playerButtons() { const current = this.player(); return this.players().map(p => `<button class="chip ${p === current ? 'on' : ''}" data-player="${this.esc(p)}">${this.esc(p)}</button>`).join(''); }
  clubButtons() { const current = this.state(this.config.club_entity)?.state; return this.savedBag().map(c => `<button class="chip ${c === current ? 'on' : ''}" data-club="${this.esc(c)}">${this.esc(c)}</button>`).join(''); }

  render() {
    if (!this._hass) return;
    const recording = this.state(this.config.recording_entity)?.state === 'on';
    const bagTest = this.state(this.config.bag_test_entity)?.state === 'on';
    const mapping = this.state(this.config.mapping_entity)?.state === 'on';
    const shotsPer = Number(this.state(this.config.shots_per_club_entity)?.state || 5);
    const shotCount = Number(this.state(this.config.shot_count_entity)?.state || 0);
    const progress = recording ? `${Math.min(shotCount, shotsPer).toFixed(0)}/${shotsPer.toFixed(0)} valid` : '--';
    this.innerHTML = `<ha-card><div class="panel">
      <div class="head"><div><div class="kicker">Practice Control</div><div class="title">Session Controls</div></div><div class="live ${recording ? 'on' : ''}"><span></span>${recording ? 'Recording' : 'Not Recording'}</div></div>
      <div class="stats">
        ${this.pill('Player', this.player(), 'mdi:account')}
        ${this.pill('Club', this.state(this.config.club_entity)?.state || '--', 'mdi:golf-tee')}
        ${this.pill('Mode', mapping ? 'Club Map' : this.state(this.config.mode_entity)?.state || '--', 'mdi:golf')}
        ${this.pill('Bag Test', bagTest ? 'Active' : 'Off', 'mdi:format-list-numbered')}
        ${this.pill('Progress', progress, 'mdi:counter')}
        ${this.pill('Session', this.state(this.config.session_entity)?.state || 'none', 'mdi:identifier')}
      </div>
      <div class="sectionLabel">Player</div><div class="chips">${this.playerButtons()}</div>
      <div class="profileTools"><input class="profileName" placeholder="Add player profile"><button class="addProfile">Add</button><button class="removeProfile" ${this.players().length <= 1 ? 'disabled' : ''}>Remove Current</button></div>
      <div class="sectionLabel">Saved Bag Quick Select</div><div class="chips">${this.clubButtons()}</div>
      <div class="actions">
        <button class="action primary" data-press="${this.config.start_button}"><ha-icon icon="mdi:target"></ha-icon>Map Club</button>
        <button class="action" data-press="${this.config.stop_button}"><ha-icon icon="mdi:stop-circle"></ha-icon>Stop</button>
        <button class="action primary" data-press="${this.config.bag_test_button}"><ha-icon icon="mdi:playlist-play"></ha-icon>Bag Test</button>
        <button class="action" data-press="${this.config.next_button}"><ha-icon icon="mdi:skip-next-circle"></ha-icon>Next Club</button>
        <button class="action danger" data-press="${this.config.discard_button}"><ha-icon icon="mdi:delete-restore"></ha-icon>Discard</button>
      </div>
      <div class="stepper"><button data-step="-1">-</button><span>${shotsPer.toFixed(0)} shots per club</span><button data-step="1">+</button></div>
      <div class="context"><div class="sectionLabel">Context MQTT</div><code>${this.esc(this.state(this.config.context_entity)?.state || '')}</code></div>
    </div></ha-card><style>
      ha-card{border:0;border-radius:26px;background:linear-gradient(145deg,rgba(18,25,45,.94),rgba(8,12,24,.86));color:white;overflow:hidden;box-shadow:0 22px 60px rgba(0,0,0,.34)}.panel{padding:18px;position:relative;isolation:isolate}.panel:before{content:'';position:absolute;inset:-30% auto auto 30%;width:360px;height:260px;border-radius:50%;background:radial-gradient(circle,rgba(56,248,255,.22),transparent 64%);z-index:-1}.head{display:flex;align-items:center;justify-content:space-between;gap:12px}.kicker,.sectionLabel{color:#8ffcff;font-size:10px;font-weight:900;letter-spacing:.18em;text-transform:uppercase}.title{font-size:24px;font-weight:950;letter-spacing:-.05em}.live{display:flex;align-items:center;gap:8px;padding:9px 12px;border-radius:999px;background:rgba(255,255,255,.08);font-weight:900;color:rgba(255,255,255,.7)}.live span{width:9px;height:9px;border-radius:50%;background:#ff5d7a;box-shadow:0 0 12px #ff5d7a}.live.on span{background:#72ff7d;box-shadow:0 0 12px #72ff7d}.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:16px 0}.stat{display:grid;grid-template-columns:30px minmax(0,1fr);gap:9px;align-items:center;padding:12px;border-radius:18px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.11)}.stat ha-icon{color:#8ffcff}.stat span{display:block;color:rgba(255,255,255,.55);font-size:10px;text-transform:uppercase;letter-spacing:.1em;font-weight:900}.stat b{display:block;margin-top:4px;font-size:16px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.chips{display:flex;gap:8px;flex-wrap:wrap;margin:8px 0 14px}.chip,.action,.stepper button,.addProfile,.removeProfile{border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.08);color:white;border-radius:999px;font-weight:900}.chip{padding:8px 11px}.chip.on{background:rgba(247,255,92,.16);border-color:rgba(247,255,92,.42);color:#f7ff8a}.profileTools{display:grid;grid-template-columns:minmax(0,1fr) auto auto;gap:8px;margin:-4px 0 14px}.profileTools input{min-width:0;border:1px solid rgba(255,255,255,.14);border-radius:16px;background:rgba(0,0,0,.22);color:white;padding:11px;font-weight:850;outline:none}.addProfile,.removeProfile{border-radius:16px;padding:0 12px;color:#8ffcff}.removeProfile{color:#ff9aad}.removeProfile:disabled{opacity:.45}.actions{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:9px;margin-top:12px}.action{display:flex;flex-direction:column;align-items:center;gap:6px;padding:12px 8px;border-radius:18px}.action ha-icon{color:#8ffcff}.action.primary{background:rgba(56,248,255,.12);border-color:rgba(56,248,255,.35)}.action.danger ha-icon{color:#ff8aa1}.stepper{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:14px;padding:10px 12px;border-radius:18px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.11);font-weight:900}.stepper button{width:34px;height:30px;color:#f7ff8a}.context{margin-top:14px}.context code{display:block;margin-top:8px;max-height:58px;overflow:auto;padding:10px;border-radius:14px;background:rgba(0,0,0,.28);color:rgba(255,255,255,.72);font-size:11px;white-space:pre-wrap}@media(max-width:760px){.stats,.profileTools{grid-template-columns:1fr}.actions{grid-template-columns:repeat(2,minmax(0,1fr))}}
    </style>`;
    this.querySelectorAll('[data-player]').forEach(b => b.addEventListener('click', () => this.setSelect(this.config.player_entity, b.dataset.player)));
    this.querySelectorAll('[data-club]').forEach(b => b.addEventListener('click', () => this.setSelect(this.config.club_entity, b.dataset.club)));
    this.querySelectorAll('[data-press]').forEach(b => b.addEventListener('click', () => this.press(b.dataset.press)));
    this.querySelectorAll('[data-step]').forEach(b => b.addEventListener('click', () => this.setNumber(this.config.shots_per_club_entity, Math.max(1, Math.min(10, shotsPer + Number(b.dataset.step))))));
    this.querySelector('.addProfile')?.addEventListener('click', () => this.addProfile());
    this.querySelector('.removeProfile')?.addEventListener('click', () => this.removeProfile());
    this.querySelector('.profileName')?.addEventListener('keydown', ev => { if (ev.key === 'Enter') this.addProfile(); });
  }
}

if (!customElements.get('golf-session-control-card')) customElements.define('golf-session-control-card', GolfSessionControlCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: 'golf-session-control-card', name: 'Golf Session Control', description: 'Practice session controls for golf shot logging' });
