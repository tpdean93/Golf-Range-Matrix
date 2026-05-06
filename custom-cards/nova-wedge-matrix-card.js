class NovaWedgeMatrixCard extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    this.players = this.config.players || ['Tyler', 'Kids', 'Guest'];
    this.matrixEntities = this.config.matrix_entities || {};
    this.bagEntities = this.config.bag_entities || {};
    this.profileEntity = this.config.profiles_entity || 'input_text.golf_profiles_json';
    this.profileBagsEntity = this.config.profile_bags_entity || 'input_text.golf_profile_bags_json';
    this.profileMatricesEntity = this.config.profile_matrices_entity || 'input_text.golf_profile_wedge_matrices_json';
    this.defaultSwings = this.config.swings || ['Half', 'Waist', 'Shoulder', 'Full'];
    this.captureTarget = this.config.capture_shots || 5;
    this.carryEntity = this.config.carry_entity || 'sensor.golf_carry';
    this._draft = null;
    this._draftPlayer = null;
    this._selected = null;
    this._capture = null;
  }

  set hass(hass) {
    this._hass = hass;
    this.captureShotIfNeeded(hass);
    this.render();
  }

  getCardSize() { return 5; }
  esc(value) { return String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c])); }
  parseJson(text, fallback) { try { return JSON.parse(text || ''); } catch { return fallback; } }
  state(entity) { return this._hass?.states?.[entity]; }
  playerList() {
    const parsed = this.parseJson(this.state(this.profileEntity)?.state, null);
    const players = Array.isArray(parsed) ? parsed : Array.isArray(parsed?.players) ? parsed.players : this.players;
    return (players || ['Tyler', 'Kids', 'Guest']).map(p => String(p).trim()).filter(Boolean);
  }
  profileData() { return this.parseJson(this.state(this.profileEntity)?.state, {}) || {}; }
  swingTypes() {
    const data = this.profileData();
    const swings = Array.isArray(data.swings) ? data.swings : this.defaultSwings;
    return swings.map(swing => String(swing).trim()).filter(Boolean);
  }
  saveSwingTypes(swings) {
    const data = this.profileData();
    data.players = this.playerList();
    data.swings = swings.map(swing => String(swing).trim()).filter(Boolean);
    this.call('input_text', 'set_value', { entity_id: this.profileEntity, value: JSON.stringify(data) });
  }
  addSwingType() {
    const input = this.querySelector('.swingName');
    const clean = String(input?.value || '').trim().replace(/\s+/g, ' ');
    if (!clean) return;
    const swings = this.swingTypes();
    if (swings.some(swing => swing.toLowerCase() === clean.toLowerCase())) return;
    this.saveSwingTypes([...swings, clean]);
  }
  removeSwingType(swing) {
    const swings = this.swingTypes().filter(existing => existing !== swing);
    if (!swings.length) return;
    if (this._selected?.swing === swing) this._selected = null;
    const matrix = this.matrix();
    Object.keys(matrix).forEach(club => { delete matrix[club][swing]; });
    this._draft = matrix;
    this.saveSwingTypes(swings);
  }
  player() { return this.state(this.config.player_entity)?.state || this.playerList()[0] || 'Tyler'; }
  matrixEntity() { return this.matrixEntities[this.player()] || this.matrixEntities.Tyler || 'input_text.golf_tyler_wedge_matrix'; }
  bagEntity() { return this.bagEntities[this.player()] || this.bagEntities.Tyler || 'input_text.golf_tyler_bag'; }
  chunkEntities(entity) { return [entity, `${entity}_2`, `${entity}_3`, `${entity}_4`]; }
  chunkText(entity) { return this.chunkEntities(entity).map(e => this.state(e)?.state || '').join(''); }
  saveChunked(entity, text) {
    this.chunkEntities(entity).forEach((e, idx) => this.call('input_text', 'set_value', { entity_id: e, value: text.slice(idx * 240, (idx + 1) * 240) }));
  }
  bagMap() { return this.parseJson(this.chunkText(this.profileBagsEntity), {}) || {}; }
  matrixMap() { return this.parseJson(this.chunkText(this.profileMatricesEntity), {}) || {}; }
  carryState(hass = this._hass) { return hass?.states?.[this.carryEntity]; }
  carryValue(hass = this._hass) {
    const value = Number(this.carryState(hass)?.state);
    return Number.isFinite(value) && value > 0 ? value : null;
  }
  carrySignature(hass = this._hass) {
    const state = this.carryState(hass);
    return state ? `${state.state}:${state.last_changed || state.last_updated || ''}` : '';
  }

  call(domain, service, data) { this._hass.callService(domain, service, data); }
  setPlayer(player) {
    this.call('input_select', 'select_option', { entity_id: this.config.player_entity, option: player });
    this._draft = null;
    this._draftPlayer = null;
    this._selected = null;
  }

  savedText() { return this.matrixMap()[this.player()] || this.state(this.matrixEntity())?.state || ''; }
  savedBag() {
    const fromMap = String(this.bagMap()[this.player()] || '').split(',').map(s => s.trim()).filter(Boolean);
    if (fromMap.length) return fromMap;
    return String(this.state(this.bagEntity())?.state || '').split(',').map(s => s.trim()).filter(Boolean);
  }
  isWedge(club) {
    const normalized = String(club || '').trim().toLowerCase();
    if (!normalized) return false;
    if (['pw', 'gw', 'sw', 'lw', 'aw', 'uw'].includes(normalized)) return true;
    if (normalized.includes('wedge')) return true;
    return /^(4[6-9]|5[0-9]|6[0-4])\s*(deg|degree|°)?$/.test(normalized);
  }

  parse(text) {
    const matrix = {};
    String(text || '').split(';').map(s => s.trim()).filter(Boolean).forEach(block => {
      const [club, rest] = block.split(':');
      if (!club || !rest) return;
      matrix[club] = matrix[club] || {};
      rest.split(',').map(s => s.trim()).filter(Boolean).forEach(pair => {
        const [swing, value] = pair.split('=');
        if (swing && value) matrix[club][swing] = value;
      });
    });
    return matrix;
  }

  serialize(matrix) {
    return this.wedges(matrix).map(club => {
      const values = this.swingTypes()
        .map(swing => {
          const value = matrix?.[club]?.[swing];
          return value ? `${swing}=${String(value).trim()}` : '';
        })
        .filter(Boolean)
        .join(',');
      return values ? `${club}:${values}` : '';
    }).filter(Boolean).join(';');
  }

  matrix() {
    const player = this.player();
    if (this._draftPlayer !== player || !this._draft) {
      this._draftPlayer = player;
      this._draft = this.parse(this.savedText());
    }
    return this._draft;
  }

  wedges(matrix = this.matrix()) {
    const bagWedges = this.savedBag().filter(club => this.isWedge(club));
    return bagWedges.filter((club, idx, clubs) => clubs.findIndex(c => c.toLowerCase() === club.toLowerCase()) === idx);
  }

  dirty() { return this.serialize(this.matrix()) !== this.savedText(); }

  selectCell(club, swing) {
    this._selected = { club, swing };
    this.render();
    const input = this.querySelector('.yardInput');
    if (input) input.focus();
  }

  updateSelected(value) {
    if (!this._selected) return;
    const clean = String(value || '').trim();
    const matrix = this.matrix();
    matrix[this._selected.club] = matrix[this._selected.club] || {};
    if (clean) matrix[this._selected.club][this._selected.swing] = clean;
    else delete matrix[this._selected.club][this._selected.swing];
    this._draft = matrix;
    this.render();
  }

  startCapture() {
    if (!this._selected) return;
    if (this.config.club_entity) {
      this.call('input_select', 'select_option', { entity_id: this.config.club_entity, option: this._selected.club });
    }
    this._capture = {
      club: this._selected.club,
      swing: this._selected.swing,
      shots: [],
      signature: this.carrySignature(),
    };
    this.render();
  }

  stopCapture() {
    this._capture = null;
    this.render();
  }

  throwOutCaptureShot() {
    if (!this._capture?.shots?.length) return;
    this._capture.shots.pop();
    this.render();
  }

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
      const value = avg.toFixed(1).replace(/\.0$/, '');
      this._selected = { club: this._capture.club, swing: this._capture.swing };
      this.updateSelected(value);
      this._capture = null;
    }
  }

  save() {
    const value = this.serialize(this.matrix());
    const map = this.matrixMap();
    if (value) map[this.player()] = value;
    else delete map[this.player()];
    this.saveChunked(this.profileMatricesEntity, JSON.stringify(map));
    const legacy = this.matrixEntities[this.player()];
    if (legacy) this.call('input_text', 'set_value', { entity_id: legacy, value });
  }

  renderPlayers() {
    const current = this.player();
    return this.playerList().map(player => `<button class="pill ${player === current ? 'on' : ''}" data-player="${this.esc(player)}">${this.esc(player)}</button>`).join('');
  }

  renderTable() {
    const matrix = this.matrix();
    const wedges = this.wedges(matrix);
    if (!wedges.length) {
      return '<div class="empty">No wedges are saved in this player bag yet. Add wedges in the Bag Builder first.</div>';
    }
    const header = wedges.map(club => `<th>${this.esc(club)}</th>`).join('');
    const rows = this.swingTypes().map(swing => {
      const cells = wedges.map(club => {
        const value = matrix?.[club]?.[swing] || '';
        const selected = this._selected?.club === club && this._selected?.swing === swing;
        return `<td><button class="cell ${selected ? 'selected' : ''} ${value ? 'filled' : ''}" data-club="${this.esc(club)}" data-swing="${this.esc(swing)}">${value ? this.esc(value) : '--'}</button></td>`;
      }).join('');
      return `<tr><th>${this.esc(swing)}</th>${cells}</tr>`;
    }).join('');
    return `<table style="--wedge-count:${wedges.length}"><thead><tr><th>Swing</th>${header}</tr></thead><tbody>${rows}</tbody></table>`;
  }

  renderEditor() {
    const selected = this._selected;
    const value = selected ? this.matrix()?.[selected.club]?.[selected.swing] || '' : '';
    const capture = this._capture;
    const captureText = capture
      ? `${capture.club} / ${capture.swing}: ${capture.shots.length}/${this.captureTarget} shots`
      : 'Pick a cell, start capture, then hit 5 shots.';
    const avg = capture && capture.shots.length
      ? (capture.shots.reduce((sum, shot) => sum + shot, 0) / capture.shots.length).toFixed(1)
      : '--';
    return `<div class="editor">
      <div><span>Selected</span><b>${selected ? `${this.esc(selected.club)} / ${this.esc(selected.swing)}` : 'Pick a cell'}</b></div>
      <input class="yardInput" placeholder="Yards or range, ex. 74/80" value="${this.esc(value)}" ${selected ? '' : 'disabled'}>
      <button class="apply" ${selected ? '' : 'disabled'}>Set</button>
    </div><div class="capturePanel"><div><span>5-shot capture</span><b>${this.esc(captureText)}</b><small>Running avg: ${this.esc(avg)}</small></div><button class="captureStart" ${selected && !capture ? '' : 'disabled'}>Start</button><button class="captureThrow" ${capture?.shots?.length ? '' : 'disabled'}>Throw Out Last</button><button class="captureStop" ${capture ? '' : 'disabled'}>Reset</button></div>`;
  }

  renderSwingManager() {
    return `<div class="swingManager"><div class="swingChips">${this.swingTypes().map(swing => `<button class="swingChip" data-remove-swing="${this.esc(swing)}"><span>${this.esc(swing)}</span><b>x</b></button>`).join('')}</div><div class="swingAdd"><input class="swingName" placeholder="Add swing type, ex. Pocket to Pocket"><button class="addSwing">Add Swing</button></div></div>`;
  }

  render() {
    if (!this._hass) return;
    const dirty = this.dirty();
    this.innerHTML = `<ha-card><div class="panel">
      <div class="head"><div><div class="kicker">Short Game</div><div class="title">Wedge Matrix</div></div><button class="save ${dirty ? 'dirty' : ''}">${dirty ? 'Save Matrix' : 'Saved'}</button></div>
      <div class="note">Build confidence inside scoring range. This matrix only shows wedges saved in the selected player bag.</div>
      <div class="players">${this.renderPlayers()}</div>
      ${this.renderSwingManager()}
      <div class="tableWrap">${this.renderTable()}</div>
      ${this.renderEditor()}
      <div class="manageNote">Need another wedge here? Add it to the player bag first.</div>
    </div></ha-card><style>
      ha-card{border:0;border-radius:26px;background:linear-gradient(145deg,rgba(18,25,45,.94),rgba(8,12,24,.86));color:white;overflow:hidden;box-shadow:0 22px 60px rgba(0,0,0,.34)}.panel{padding:18px;position:relative;isolation:isolate}.panel:before{content:'';position:absolute;inset:-30% -20% auto auto;width:300px;height:250px;border-radius:50%;background:radial-gradient(circle,rgba(247,255,92,.18),transparent 64%);z-index:-1}.head{display:flex;align-items:center;justify-content:space-between;gap:12px}.kicker{color:#8ffcff;font-size:10px;font-weight:900;letter-spacing:.18em;text-transform:uppercase}.title{font-size:24px;font-weight:950;letter-spacing:-.05em}.note,.manageNote{margin-top:12px;color:rgba(255,255,255,.68);font-size:13px;font-weight:750;line-height:1.35}.manageNote{color:rgba(255,255,255,.48);font-size:12px}.save,.pill,.cell,.apply,.captureStart,.captureThrow,.captureStop,.swingChip,.addSwing{border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.08);color:white;border-radius:999px;font-weight:900}.save{padding:9px 12px;color:#b8ffbf}.save.dirty{color:#f7ff8a;border-color:rgba(247,255,92,.4);background:rgba(247,255,92,.12)}.players{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}.pill{padding:9px 12px}.pill.on{background:rgba(247,255,92,.16);border-color:rgba(247,255,92,.45);color:#f7ff8a}.swingManager{display:grid;gap:9px;margin:-4px 0 14px}.swingChips{display:flex;flex-wrap:wrap;gap:8px}.swingChip{display:flex;align-items:center;gap:7px;padding:8px 10px;color:#8ffcff}.swingChip b{color:#ff9aad}.swingAdd{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:8px}.swingAdd input{min-width:0;border:1px solid rgba(255,255,255,.14);border-radius:16px;background:rgba(0,0,0,.22);color:white;padding:11px;font-weight:850;outline:none}.addSwing{border-radius:16px;padding:0 12px;color:#f7ff8a}.tableWrap{overflow:visible;border-radius:18px;border:1px solid rgba(255,255,255,.12);background:rgba(0,0,0,.18)}table{width:100%;table-layout:fixed;border-collapse:collapse;min-width:0}th,td{border-bottom:1px solid rgba(255,255,255,.1);border-right:1px solid rgba(255,255,255,.08);padding:8px;text-align:center}th{color:rgba(255,255,255,.58);font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.12em}thead th:first-child,tbody th{width:86px}tbody th{text-align:left;color:#8ffcff}.cell{width:100%;min-height:42px;border-radius:13px;font-size:clamp(13px,1.8vw,16px);padding:0 6px}.cell.filled{background:rgba(56,248,255,.12);border-color:rgba(56,248,255,.28);color:#d8fdff}.cell.selected{box-shadow:inset 0 0 0 1px rgba(247,255,92,.75);color:#f7ff8a}.editor,.capturePanel{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) auto;gap:9px;align-items:center;margin-top:12px}.capturePanel{grid-template-columns:minmax(0,1fr) auto auto auto}.editor div,.capturePanel div{padding:10px;border-radius:16px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.11)}.editor span,.capturePanel span{display:block;color:rgba(255,255,255,.5);font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.12em}.editor b,.capturePanel b{display:block;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.capturePanel small{display:block;margin-top:4px;color:#8ffcff;font-weight:850}.yardInput{min-width:0;border:1px solid rgba(255,255,255,.14);border-radius:16px;background:rgba(0,0,0,.22);color:white;padding:12px;font-weight:850;outline:none}.apply,.captureStart,.captureThrow,.captureStop{border-radius:16px;padding:0 13px;height:42px;color:#8ffcff}.captureStart{color:#f7ff8a}.captureThrow,.captureStop{color:#ff9aad}.apply:disabled,.yardInput:disabled,.captureStart:disabled,.captureThrow:disabled,.captureStop:disabled{opacity:.45}.empty{padding:18px;color:rgba(255,255,255,.62);font-weight:850;text-align:center}@media(max-width:760px){.tableWrap{overflow:auto}table{min-width:520px}.editor,.capturePanel,.swingAdd{grid-template-columns:1fr}.apply,.captureStart,.captureThrow,.captureStop,.addSwing{width:100%}}
    </style>`;
    this.querySelectorAll('[data-player]').forEach(button => button.addEventListener('click', () => this.setPlayer(button.dataset.player)));
    this.querySelectorAll('[data-club]').forEach(button => button.addEventListener('click', () => this.selectCell(button.dataset.club, button.dataset.swing)));
    this.querySelector('.save')?.addEventListener('click', () => this.save());
    this.querySelectorAll('[data-remove-swing]').forEach(button => button.addEventListener('click', () => this.removeSwingType(button.dataset.removeSwing)));
    this.querySelector('.addSwing')?.addEventListener('click', () => this.addSwingType());
    this.querySelector('.swingName')?.addEventListener('keydown', ev => { if (ev.key === 'Enter') this.addSwingType(); });
    this.querySelector('.apply')?.addEventListener('click', () => this.updateSelected(this.querySelector('.yardInput')?.value));
    this.querySelector('.yardInput')?.addEventListener('keydown', ev => { if (ev.key === 'Enter') this.updateSelected(ev.currentTarget.value); });
    this.querySelector('.captureStart')?.addEventListener('click', () => this.startCapture());
    this.querySelector('.captureThrow')?.addEventListener('click', () => this.throwOutCaptureShot());
    this.querySelector('.captureStop')?.addEventListener('click', () => this.stopCapture());
  }
}

if (!customElements.get('nova-wedge-matrix-card')) customElements.define('nova-wedge-matrix-card', NovaWedgeMatrixCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: 'nova-wedge-matrix-card', name: 'NOVA Wedge Matrix', description: 'Short-game wedge yardage matrix builder' });
