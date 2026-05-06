class NovaWedgeMatrixCard extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    this.players = this.config.players || ['Tyler', 'Kids', 'Guest'];
    this.matrixEntities = this.config.matrix_entities || {};
    this.defaultWedges = this.config.wedges || ['LW', 'SW', 'GW', 'PW'];
    this.swings = this.config.swings || ['Half', 'Waist', 'Shoulder', 'Full'];
    this._draft = null;
    this._draftPlayer = null;
    this._selected = null;
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() { return 5; }
  esc(value) { return String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c])); }
  state(entity) { return this._hass?.states?.[entity]; }
  player() { return this.state(this.config.player_entity)?.state || this.players[0] || 'Tyler'; }
  matrixEntity() { return this.matrixEntities[this.player()] || this.matrixEntities.Tyler || 'input_text.golf_tyler_wedge_matrix'; }

  call(domain, service, data) { this._hass.callService(domain, service, data); }
  setPlayer(player) {
    this.call('input_select', 'select_option', { entity_id: this.config.player_entity, option: player });
    this._draft = null;
    this._draftPlayer = null;
    this._selected = null;
  }

  savedText() { return this.state(this.matrixEntity())?.state || ''; }

  parse(text) {
    const matrix = {};
    for (const wedge of this.defaultWedges) matrix[wedge] = {};
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
      const values = this.swings
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
    const clubs = [...this.defaultWedges];
    Object.keys(matrix || {}).forEach(club => {
      if (!clubs.some(c => c.toLowerCase() === club.toLowerCase())) clubs.push(club);
    });
    return clubs;
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

  addWedge(name) {
    const clean = String(name || '').trim().replace(/\s+/g, ' ');
    if (!clean) return;
    const matrix = this.matrix();
    if (!matrix[clean]) matrix[clean] = {};
    this._draft = matrix;
    this._selected = { club: clean, swing: this.swings[0] };
    this.render();
  }

  save() {
    this.call('input_text', 'set_value', { entity_id: this.matrixEntity(), value: this.serialize(this.matrix()) });
  }

  renderPlayers() {
    const current = this.player();
    return this.players.map(player => `<button class="pill ${player === current ? 'on' : ''}" data-player="${this.esc(player)}">${this.esc(player)}</button>`).join('');
  }

  renderTable() {
    const matrix = this.matrix();
    const header = this.wedges(matrix).map(club => `<th>${this.esc(club)}</th>`).join('');
    const rows = this.swings.map(swing => {
      const cells = this.wedges(matrix).map(club => {
        const value = matrix?.[club]?.[swing] || '';
        const selected = this._selected?.club === club && this._selected?.swing === swing;
        return `<td><button class="cell ${selected ? 'selected' : ''} ${value ? 'filled' : ''}" data-club="${this.esc(club)}" data-swing="${this.esc(swing)}">${value ? this.esc(value) : '--'}</button></td>`;
      }).join('');
      return `<tr><th>${this.esc(swing)}</th>${cells}</tr>`;
    }).join('');
    return `<table><thead><tr><th>Swing</th>${header}</tr></thead><tbody>${rows}</tbody></table>`;
  }

  renderEditor() {
    const selected = this._selected;
    const value = selected ? this.matrix()?.[selected.club]?.[selected.swing] || '' : '';
    return `<div class="editor">
      <div><span>Selected</span><b>${selected ? `${this.esc(selected.club)} / ${this.esc(selected.swing)}` : 'Pick a cell'}</b></div>
      <input class="yardInput" placeholder="Yards or range, ex. 74/80" value="${this.esc(value)}" ${selected ? '' : 'disabled'}>
      <button class="apply" ${selected ? '' : 'disabled'}>Set</button>
    </div>`;
  }

  render() {
    if (!this._hass) return;
    const dirty = this.dirty();
    this.innerHTML = `<ha-card><div class="panel">
      <div class="head"><div><div class="kicker">Short Game</div><div class="title">Wedge Matrix</div></div><button class="save ${dirty ? 'dirty' : ''}">${dirty ? 'Save Matrix' : 'Saved'}</button></div>
      <div class="note">Build confidence inside scoring range. Pick a wedge and swing type, then enter the expected yardage or range.</div>
      <div class="players">${this.renderPlayers()}</div>
      <div class="tableWrap">${this.renderTable()}</div>
      ${this.renderEditor()}
      <div class="custom"><input class="customWedge" placeholder="Add wedge, ex. 50 Wedge"><button class="addWedge">Add Wedge</button></div>
    </div></ha-card><style>
      ha-card{border:0;border-radius:26px;background:linear-gradient(145deg,rgba(18,25,45,.94),rgba(8,12,24,.86));color:white;overflow:hidden;box-shadow:0 22px 60px rgba(0,0,0,.34)}.panel{padding:18px;position:relative;isolation:isolate}.panel:before{content:'';position:absolute;inset:-30% -20% auto auto;width:300px;height:250px;border-radius:50%;background:radial-gradient(circle,rgba(247,255,92,.18),transparent 64%);z-index:-1}.head{display:flex;align-items:center;justify-content:space-between;gap:12px}.kicker{color:#8ffcff;font-size:10px;font-weight:900;letter-spacing:.18em;text-transform:uppercase}.title{font-size:24px;font-weight:950;letter-spacing:-.05em}.note{margin-top:12px;color:rgba(255,255,255,.68);font-size:13px;font-weight:750;line-height:1.35}.save,.pill,.cell,.apply,.addWedge{border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.08);color:white;border-radius:999px;font-weight:900}.save{padding:9px 12px;color:#b8ffbf}.save.dirty{color:#f7ff8a;border-color:rgba(247,255,92,.4);background:rgba(247,255,92,.12)}.players{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}.pill{padding:9px 12px}.pill.on{background:rgba(247,255,92,.16);border-color:rgba(247,255,92,.45);color:#f7ff8a}.tableWrap{overflow:auto;border-radius:18px;border:1px solid rgba(255,255,255,.12);background:rgba(0,0,0,.18)}table{width:100%;border-collapse:collapse;min-width:520px}th,td{border-bottom:1px solid rgba(255,255,255,.1);border-right:1px solid rgba(255,255,255,.08);padding:8px;text-align:center}th{color:rgba(255,255,255,.58);font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.12em}tbody th{text-align:left;color:#8ffcff}.cell{width:100%;min-height:42px;border-radius:13px;font-size:16px}.cell.filled{background:rgba(56,248,255,.12);border-color:rgba(56,248,255,.28);color:#d8fdff}.cell.selected{box-shadow:inset 0 0 0 1px rgba(247,255,92,.75);color:#f7ff8a}.editor,.custom{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) auto;gap:9px;align-items:center;margin-top:12px}.editor div{padding:10px;border-radius:16px;background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.11)}.editor span{display:block;color:rgba(255,255,255,.5);font-size:10px;font-weight:900;text-transform:uppercase;letter-spacing:.12em}.editor b{display:block;margin-top:4px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.yardInput,.customWedge{min-width:0;border:1px solid rgba(255,255,255,.14);border-radius:16px;background:rgba(0,0,0,.22);color:white;padding:12px;font-weight:850;outline:none}.apply,.addWedge{border-radius:16px;padding:0 13px;height:42px;color:#8ffcff}.apply:disabled,.yardInput:disabled{opacity:.45}@media(max-width:760px){.editor,.custom{grid-template-columns:1fr}.apply,.addWedge{width:100%}}
    </style>`;
    this.querySelectorAll('[data-player]').forEach(button => button.addEventListener('click', () => this.setPlayer(button.dataset.player)));
    this.querySelectorAll('[data-club]').forEach(button => button.addEventListener('click', () => this.selectCell(button.dataset.club, button.dataset.swing)));
    this.querySelector('.save')?.addEventListener('click', () => this.save());
    this.querySelector('.apply')?.addEventListener('click', () => this.updateSelected(this.querySelector('.yardInput')?.value));
    this.querySelector('.yardInput')?.addEventListener('keydown', ev => { if (ev.key === 'Enter') this.updateSelected(ev.currentTarget.value); });
    this.querySelector('.addWedge')?.addEventListener('click', () => this.addWedge(this.querySelector('.customWedge')?.value));
  }
}

if (!customElements.get('nova-wedge-matrix-card')) customElements.define('nova-wedge-matrix-card', NovaWedgeMatrixCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: 'nova-wedge-matrix-card', name: 'NOVA Wedge Matrix', description: 'Short-game wedge yardage matrix builder' });
