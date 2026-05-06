class NovaBagBuilderCard extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    this.catalog = this.config.catalog || [
      'Driver', '3 Wood', '5 Wood', '7 Wood',
      '3 Hybrid', '4 Hybrid', '5 Hybrid',
      '4 Iron', '5 Iron', '6 Iron', '7 Iron', '8 Iron', '9 Iron',
      'PW', 'GW', '52 Wedge', '56 Wedge', '60 Wedge', 'Putter',
    ];
    this.bagEntities = this.config.bag_entities || {};
    this.maxClubs = this.config.max_clubs || 14;
    this._draft = null;
    this._draftPlayer = null;
    this._optimisticSaved = null;
  }

  set hass(hass) {
    this._hass = hass;
    if (this._optimisticSaved) {
      const state = hass.states?.[this._optimisticSaved.entity]?.state;
      const actual = this.parseBag(state).join('|');
      const expected = this._optimisticSaved.clubs.join('|');
      if (actual === expected || Date.now() - this._optimisticSaved.at > 3000) {
        this._optimisticSaved = null;
      }
    }
    this.render();
  }

  getCardSize() { return 6; }
  esc(v) { return String(v ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c])); }
  state(e) { return this._hass?.states?.[e]; }
  player() { return this.state(this.config.player_entity)?.state || 'Tyler'; }
  bagEntity() { return this.bagEntities[this.player()] || this.bagEntities.Tyler || 'input_text.golf_tyler_bag'; }
  parseBag(value) { return String(value || '').split(',').map(s => s.trim()).filter(Boolean); }

  savedBag() {
    const entity = this.bagEntity();
    if (this._optimisticSaved && this._optimisticSaved.entity === entity) return this._optimisticSaved.clubs;
    return this.parseBag(this.state(entity)?.state);
  }

  selected() {
    const player = this.player();
    if (this._draftPlayer !== player || !this._draft) {
      this._draftPlayer = player;
      this._draft = this.savedBag();
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

  changeLabel(selected, saved) {
    const added = selected.filter(c => !saved.some(s => s.toLowerCase() === c.toLowerCase())).length;
    const removed = saved.filter(c => !selected.some(s => s.toLowerCase() === c.toLowerCase())).length;
    const parts = [];
    if (added) parts.push(`+${added}`);
    if (removed) parts.push(`-${removed}`);
    return parts.length ? parts.join(' / ') : 'Pending';
  }

  call(domain, service, data) { this._hass.callService(domain, service, data); }
  setPlayer(player) {
    this.call('input_select', 'select_option', { entity_id: this.config.player_entity, option: player });
    this._draft = null;
    this._optimisticSaved = null;
  }
  setActiveClub(club) { this.call('input_select', 'select_option', { entity_id: this.config.club_entity, option: club }); }
  normalizeClub(club) { return String(club || '').trim().replace(/\s+/g, ' '); }

  addClub(club) {
    const clean = this.normalizeClub(club);
    if (!clean) return;
    const selected = [...this.selected()];
    if (selected.some(c => c.toLowerCase() === clean.toLowerCase())) return;
    if (selected.length >= this.maxClubs) return;
    selected.push(clean);
    this._draft = selected;
    this.render();
  }

  toggleClub(club) {
    const selected = [...this.selected()];
    const idx = selected.findIndex(c => c.toLowerCase() === club.toLowerCase());
    if (idx >= 0) selected.splice(idx, 1);
    else {
      if (selected.length >= this.maxClubs) return;
      selected.push(club);
    }
    this._draft = selected;
    this.render();
  }

  saveBag() {
    const clubs = this.selected().slice(0, this.maxClubs);
    const entity = this.bagEntity();
    this._optimisticSaved = { entity, clubs, at: Date.now() };
    this.call('input_text', 'set_value', { entity_id: entity, value: clubs.join(',') });
    if (!clubs.includes(this.state(this.config.club_entity)?.state) && clubs[0]) this.setActiveClub(clubs[0]);
    this.render();
  }

  renderPlayers() {
    const current = this.player();
    return (this.config.players || ['Tyler', 'Kids', 'Guest'])
      .map(p => `<button class="pill ${p === current ? 'on' : ''}" data-player="${this.esc(p)}">${this.esc(p)}</button>`)
      .join('');
  }

  renderCustomClub() {
    const atMax = this.selected().length >= this.maxClubs;
    return `<div class="customClub"><input placeholder="Add custom club, ex. Mini Driver" ${atMax ? 'disabled' : ''}><button class="addCustom" ${atMax ? 'disabled' : ''}>Add Custom</button></div>`;
  }

  renderClubs() {
    const selected = this.selected();
    const saved = this.savedBag();
    const active = this.state(this.config.club_entity)?.state;
    const atMax = selected.length >= this.maxClubs;
    return this.allClubs().map(club => {
      const inDraft = selected.some(c => c.toLowerCase() === club.toLowerCase());
      const inSaved = saved.some(c => c.toLowerCase() === club.toLowerCase());
      const disabled = atMax && !inDraft;
      const label = active === club ? 'Active' : inDraft && inSaved ? 'In bag' : inDraft ? 'Pending add' : inSaved ? 'Pending remove' : disabled ? 'Max 14' : 'Add';
      return `<button class="club ${inDraft ? 'inBag' : ''} ${inSaved ? 'savedClub' : ''} ${active === club ? 'active' : ''} ${disabled ? 'disabled' : ''}" data-club="${this.esc(club)}" ${disabled ? 'disabled' : ''}><span>${this.esc(club)}</span><small>${label}</small></button>`;
    }).join('');
  }

  renderSavedBagStrip() {
    const active = this.state(this.config.club_entity)?.state;
    return this.savedBag()
      .map((club, idx) => `<button class="bagClub ${active === club ? 'active' : ''}" data-active-club="${this.esc(club)}"><b>${idx + 1}</b>${this.esc(club)}</button>`)
      .join('') || '<div class="empty">Save clubs below to build this player bag.</div>';
  }

  render() {
    if (!this._hass) return;
    const selected = this.selected();
    const saved = this.savedBag();
    const dirty = selected.join('|') !== saved.join('|');
    this.innerHTML = `<ha-card><div class="panel">
      <div class="head"><div><div class="kicker">Player Bag</div><div class="title">Bag Builder</div></div><button class="save ${dirty ? 'dirty' : ''}">${dirty ? 'Save Changes' : 'Saved'}</button></div>
      <div class="note">Click clubs below to add or remove them from this player bag. Add a custom club if it is not in the list. Maximum ${this.maxClubs} clubs.</div>
      <div class="players">${this.renderPlayers()}</div>
      <div class="summary"><div><span>Player</span><b>${this.esc(this.player())}</b></div><div><span>Saved Clubs</span><b>${saved.length}/${this.maxClubs}</b></div><div><span>Status</span><b>${dirty ? this.changeLabel(selected, saved) : 'Saved'}</b></div><div><span>Active</span><b>${this.esc(this.state(this.config.club_entity)?.state || '--')}</b></div></div>
      <div class="stripLabel">Saved bag. Click one to make it active.</div>
      <div class="bagStrip">${this.renderSavedBagStrip()}</div>
      ${this.renderCustomClub()}
      <div class="clubGrid">${this.renderClubs()}</div>
    </div></ha-card><style>
      ha-card{border:0;border-radius:26px;background:linear-gradient(145deg,rgba(18,25,45,.94),rgba(8,12,24,.86));color:white;overflow:hidden;box-shadow:0 22px 60px rgba(0,0,0,.34)}.panel{padding:18px;position:relative;isolation:isolate}.panel:before{content:'';position:absolute;inset:-35% -20% auto auto;width:300px;height:260px;border-radius:50%;background:radial-gradient(circle,rgba(56,248,255,.22),transparent 64%);z-index:-1}.head{display:flex;justify-content:space-between;gap:12px;align-items:center}.kicker{color:#8ffcff;font-size:10px;font-weight:900;letter-spacing:.18em;text-transform:uppercase}.title{font-size:24px;font-weight:950;letter-spacing:-.05em}.note{margin-top:12px;color:rgba(255,255,255,.7);font-size:13px;font-weight:750;line-height:1.35}.save,.pill,.club,.bagClub,.addCustom{border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.08);color:white;border-radius:999px;font-weight:850}.save{padding:9px 12px;color:#b8ffbf}.save.dirty{color:#f7ff8a;border-color:rgba(247,255,92,.4);background:rgba(247,255,92,.12)}.players{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}.pill{padding:9px 12px}.pill.on{background:rgba(247,255,92,.16);border-color:rgba(247,255,92,.45);color:#f7ff8a}.summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-bottom:14px}.summary div{padding:12px;border-radius:18px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.11)}.summary span,.stripLabel{display:block;color:rgba(255,255,255,.55);font-size:10px;text-transform:uppercase;letter-spacing:.12em;font-weight:900}.summary b{display:block;margin-top:5px;font-size:18px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.stripLabel{margin:4px 0 8px}.bagStrip{display:flex;gap:8px;overflow:auto;padding:4px 0 12px}.bagClub{padding:8px 10px;white-space:nowrap;color:rgba(255,255,255,.78)}.bagClub b{color:#8ffcff;margin-right:6px}.bagClub.active{background:rgba(56,248,255,.16);border-color:rgba(56,248,255,.45);color:#8ffcff}.customClub{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px;margin:0 0 12px}.customClub input{min-width:0;border:1px solid rgba(255,255,255,.14);border-radius:16px;background:rgba(0,0,0,.22);color:white;padding:12px;font-weight:800;outline:none}.customClub input::placeholder{color:rgba(255,255,255,.42)}.addCustom{border-radius:16px;padding:0 13px;color:#8ffcff}.addCustom:disabled,.customClub input:disabled{opacity:.45}.clubGrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}.club{border-radius:16px;padding:12px;text-align:left;min-height:62px}.club span{display:block;font-size:15px;font-weight:900}.club small{display:block;margin-top:5px;color:rgba(255,255,255,.48);font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.1em}.club.inBag{background:rgba(255,255,255,.115);border-color:rgba(255,255,255,.18)}.club.savedClub small{color:#b8ffbf}.club.active{box-shadow:inset 0 0 0 1px rgba(247,255,92,.48);color:#f7ff8a}.club.disabled{opacity:.42}.empty{color:rgba(255,255,255,.55);font-weight:800;padding:9px 0}@media(max-width:760px){.clubGrid{grid-template-columns:repeat(2,minmax(0,1fr))}.summary{grid-template-columns:repeat(2,minmax(0,1fr))}}
    </style>`;
    this.querySelectorAll('[data-player]').forEach(b => b.addEventListener('click', () => this.setPlayer(b.dataset.player)));
    this.querySelectorAll('[data-club]').forEach(b => b.addEventListener('click', () => this.toggleClub(b.dataset.club)));
    this.querySelectorAll('[data-active-club]').forEach(b => b.addEventListener('click', () => this.setActiveClub(b.dataset.activeClub)));
    this.querySelector('.save')?.addEventListener('click', () => this.saveBag());
    const input = this.querySelector('.customClub input');
    this.querySelector('.addCustom')?.addEventListener('click', () => this.addClub(input?.value));
    input?.addEventListener('keydown', ev => { if (ev.key === 'Enter') this.addClub(input.value); });
  }
}

if (!customElements.get('nova-bag-builder-card')) customElements.define('nova-bag-builder-card', NovaBagBuilderCard);
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'nova-bag-builder-card',
  name: 'NOVA Bag Builder',
  description: 'Build per-player golf bags and select active club',
});
