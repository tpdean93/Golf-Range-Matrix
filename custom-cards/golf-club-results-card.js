class GolfClubResultsCard extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    this.profileBagsEntity = this.config.profile_bags_entity || 'input_text.golf_profile_bags_json';
    this.metadataEntity = this.config.metadata_entity || 'input_text.golf_club_metadata_json';
    this.summaryPrefix = this.config.summary_entity_prefix || 'sensor.golf_summary';
    this.chunkCount = Number(this.config.metadata_chunks || 8);
  }

  set hass(hass) {
    this._hass = hass;
    const signature = this.renderSignature();
    if (signature === this._signature) return;
    this._signature = signature;
    this.render();
  }

  getCardSize() { return 8; }
  state(entity) { return this._hass?.states?.[entity]; }
  esc(value) { return String(value ?? '').replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[c])); }
  parseJson(text, fallback) { try { return JSON.parse(text || ''); } catch { return fallback; } }
  slug(value) { return String(value || '').trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'unknown'; }

  chunkEntities(entity, count = 4) {
    return Array.from({ length: count }, (_, index) => index === 0 ? entity : `${entity}_${index + 1}`);
  }

  chunkText(entity, count = 4) {
    return this.chunkEntities(entity, count).map(e => this.state(e)?.state || '').join('');
  }

  saveChunked(entity, text, count = 4) {
    this.chunkEntities(entity, count).forEach((chunkEntity, index) => {
      this._hass.callService('input_text', 'set_value', {
        entity_id: chunkEntity,
        value: text.slice(index * 240, (index + 1) * 240),
      });
    });
  }

  player() {
    return this.state(this.config.player_entity)?.state || 'Tyler';
  }

  renderSignature() {
    if (!this._hass) return '';
    const player = this.player();
    const bag = this.chunkText(this.profileBagsEntity, 4);
    const metadata = this.chunkText(this.metadataEntity, this.chunkCount);
    const playerSlug = this.slug(player);
    const summary = this.state(`${this.summaryPrefix}_${playerSlug}_bag`) || this.state(`sensor.nova_shot_logger_golf_summary_${playerSlug}_bag`);
    return JSON.stringify({
      player,
      bag,
      metadata,
      summaryState: summary?.state || '',
      summaryUpdated: summary?.attributes?.updated_at || '',
      summaryShotCount: summary?.attributes?.shot_count || 0,
      clubs: summary?.attributes?.clubs || [],
    });
  }

  bagMap() {
    return this.parseJson(this.chunkText(this.profileBagsEntity, 4), {}) || {};
  }

  savedBag() {
    const fromMap = String(this.bagMap()[this.player()] || '').split(',').map(s => s.trim()).filter(Boolean);
    return fromMap.length ? fromMap.slice(0, 14) : (this.config.clubs || []);
  }

  summaryEntity() {
    return `${this.summaryPrefix}_${this.slug(this.player())}_bag`;
  }

  summaryState() {
    const playerSlug = this.slug(this.player());
    return this.state(this.summaryEntity()) || this.state(`sensor.nova_shot_logger_golf_summary_${playerSlug}_bag`);
  }

  summaryClubs() {
    const attrs = this.summaryState()?.attributes || {};
    return Array.isArray(attrs.clubs) ? attrs.clubs : [];
  }

  metadataMap() {
    return this.parseJson(this.chunkText(this.metadataEntity, this.chunkCount), {}) || {};
  }

  clubMetadata(club) {
    return this.metadataMap()?.[this.player()]?.[club] || {};
  }

  clubSummary(club) {
    return this.summaryClubs().find(item => String(item.club || '').toLowerCase() === String(club).toLowerCase()) || null;
  }

  number(value, suffix = '', digits = 1) {
    const num = Number(value);
    if (!Number.isFinite(num)) return '--';
    return `${num.toFixed(digits)}${suffix}`;
  }

  rangeText(range, suffix = ' yd') {
    if (!range || range.low == null || range.high == null) return '--';
    return `${this.number(range.low, '', 1)}-${this.number(range.high, suffix, 1)}`;
  }

  saveClub(club) {
    const key = this.slug(club);
    const map = this.metadataMap();
    const player = this.player();
    map[player] = map[player] || {};
    map[player][club] = {
      brand: this.querySelector(`[data-brand="${key}"]`)?.value?.trim() || '',
      model: this.querySelector(`[data-model="${key}"]`)?.value?.trim() || '',
      image_url: this.querySelector(`[data-image="${key}"]`)?.value?.trim() || '',
    };
    this.saveChunked(this.metadataEntity, JSON.stringify(map), this.chunkCount);
  }

  heroMeta(summary) {
    const avg = summary?.averages || {};
    const playable = summary?.playable_yardage || {};
    return [
      ['Carry', this.number(avg.carry, ' yd')],
      ['Total', this.number(avg.total, ' yd')],
      ['Playable', this.rangeText(playable.carry)],
      ['Offline', this.number(avg.offline, ' yd')],
    ];
  }

  detailMeta(summary) {
    const avg = summary?.averages || {};
    return [
      ['Launch', this.number(avg.launch_angle, ' deg')],
      ['Spin', this.number(avg.total_spin, ' rpm', 0)],
      ['Ball', this.number(avg.ball_speed, ' mph')],
      ['Smash', this.number(avg.smash_factor, '', 2)],
    ];
  }

  fallbackArt(club) {
    return `<div class="fallback"><ha-icon icon="mdi:golf-tee"></ha-icon><strong>${this.esc(club)}</strong></div>`;
  }

  renderClub(club) {
    const summary = this.clubSummary(club);
    const meta = this.clubMetadata(club);
    const key = this.slug(club);
    const shotCount = Number(summary?.shot_count || 0);
    const title = [meta.brand, meta.model].filter(Boolean).join(' ');
    const confidence = summary?.confidence?.rating || 'unmapped';
    const tendency = summary?.tendencies?.direction || 'Ready to map';
    const dispersion = summary?.tendencies?.dispersion || 'No saved shots yet';
    const image = String(meta.image_url || '').trim();
    const hero = this.heroMeta(summary).map(([label, value]) => `<div><span>${label}</span><b>${this.esc(value)}</b></div>`).join('');
    const details = this.detailMeta(summary).map(([label, value]) => `<div><span>${label}</span><b>${this.esc(value)}</b></div>`).join('');

    return `<article class="clubCard">
      <div class="top">
        <div>
          <div class="club">${this.esc(club)}</div>
          <div class="model">${this.esc(title || 'Add brand + model')}</div>
        </div>
        <div class="badge ${shotCount >= 5 ? 'mapped' : ''}">${shotCount ? `${shotCount} shots` : 'unmapped'}</div>
      </div>
      <div class="body">
        <div class="photo">${image ? `<img src="${this.esc(image)}" alt="${this.esc(club)}" loading="lazy">` : this.fallbackArt(club)}</div>
        <div class="numbers">${hero}</div>
      </div>
      <div class="insight">
        <strong>${this.esc(confidence)} confidence</strong>
        <span>${this.esc(tendency)} | ${this.esc(dispersion)}</span>
        <small>${this.esc(summary?.ai_notes || 'Map this club to unlock averages, playable yardage, and shot tendencies.')}</small>
      </div>
      <div class="details">${details}</div>
      <details class="editor">
        <summary>Club details</summary>
        <label>Brand<input data-brand="${key}" value="${this.esc(meta.brand || '')}" placeholder="Titleist"></label>
        <label>Model<input data-model="${key}" value="${this.esc(meta.model || '')}" placeholder="Vokey SM10"></label>
        <label>Image URL<input data-image="${key}" value="${this.esc(image)}" placeholder="https://..."></label>
        <button data-save="${this.esc(club)}">Save Club Details</button>
      </details>
    </article>`;
  }

  render() {
    if (!this._hass) return;
    const clubs = this.savedBag();
    const summary = this.summaryState();
    const summaryAttrs = summary?.attributes || {};
    const mapped = this.summaryClubs().length;
    const totalShots = Number(summaryAttrs.shot_count || summary?.state || 0);
    const subtitle = summary
      ? `${mapped} mapped clubs | ${totalShots} saved shots | updates when you re-map`
      : `Waiting for ${this.summaryEntity()} from the shot logger`;

    this.innerHTML = `<ha-card>
      <section class="panel">
        <div class="head">
          <div>
            <div class="kicker">Mapped Bag Results</div>
            <h2>${this.esc(this.player())}'s Club Cards</h2>
            <p>${this.esc(subtitle)}</p>
          </div>
          <div class="summaryBadge"><span>${clubs.length}</span><small>clubs</small></div>
        </div>
        <div class="grid">${clubs.length ? clubs.map(club => this.renderClub(club)).join('') : '<div class="empty">Save clubs in the Practice tab to build this results wall.</div>'}</div>
      </section>
    </ha-card><style>
      ha-card{border:0;border-radius:30px;background:linear-gradient(145deg,rgba(18,25,45,.94),rgba(8,12,24,.86));color:white;overflow:hidden;box-shadow:0 24px 70px rgba(0,0,0,.36)}
      .panel{position:relative;isolation:isolate;padding:20px}.panel:before{content:'';position:absolute;inset:-160px -120px auto auto;width:520px;height:420px;border-radius:50%;background:radial-gradient(circle,rgba(56,248,255,.20),transparent 64%);z-index:-1}.panel:after{content:'';position:absolute;left:-140px;bottom:-180px;width:460px;height:360px;border-radius:50%;background:radial-gradient(circle,rgba(168,85,247,.22),transparent 65%);z-index:-1}
      .head{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:18px}.kicker{color:#8ffcff;font-size:11px;font-weight:950;text-transform:uppercase;letter-spacing:.18em}h2{margin:4px 0 0;font-size:30px;line-height:1;font-weight:950;letter-spacing:-.05em}p{margin:8px 0 0;color:rgba(255,255,255,.66);font-weight:750}.summaryBadge{min-width:82px;min-height:82px;border-radius:26px;display:grid;place-items:center;background:rgba(247,255,92,.12);border:1px solid rgba(247,255,92,.35);box-shadow:inset 0 0 28px rgba(247,255,92,.08)}.summaryBadge span{font-size:30px;font-weight:950;color:#f7ff8a}.summaryBadge small{margin-top:-18px;color:rgba(255,255,255,.72);font-weight:900;text-transform:uppercase;letter-spacing:.12em}
      .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(310px,1fr));gap:16px}.clubCard{border:1px solid rgba(255,255,255,.12);border-radius:26px;background:linear-gradient(145deg,rgba(255,255,255,.08),rgba(255,255,255,.035));padding:14px;box-shadow:inset 0 1px 0 rgba(255,255,255,.08);overflow:hidden}.top{display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.club{font-size:26px;font-weight:950;letter-spacing:-.05em}.model{margin-top:3px;color:rgba(255,255,255,.62);font-size:13px;font-weight:850}.badge{white-space:nowrap;border-radius:999px;padding:7px 10px;background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.12);font-size:12px;font-weight:950;color:rgba(255,255,255,.72)}.badge.mapped{background:rgba(114,255,125,.13);border-color:rgba(114,255,125,.34);color:#b8ffbf}
      .body{display:grid;grid-template-columns:130px minmax(0,1fr);gap:13px;margin-top:14px}.photo{height:154px;border-radius:22px;overflow:hidden;background:radial-gradient(circle at 50% 22%,rgba(56,248,255,.22),rgba(0,0,0,.25));border:1px solid rgba(255,255,255,.10);display:grid;place-items:center}.photo img{width:100%;height:100%;object-fit:cover}.fallback{display:grid;place-items:center;gap:8px;color:#8ffcff;text-align:center}.fallback ha-icon{--mdc-icon-size:44px}.fallback strong{max-width:100px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:white}.numbers,.details{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.numbers div,.details div{border-radius:16px;padding:10px;background:rgba(0,0,0,.22);border:1px solid rgba(255,255,255,.09)}.numbers span,.details span{display:block;color:rgba(255,255,255,.52);font-size:10px;font-weight:950;letter-spacing:.12em;text-transform:uppercase}.numbers b{display:block;margin-top:5px;font-size:19px;font-weight:950;color:#f7ff8a}.details{margin-top:10px}.details b{display:block;margin-top:4px;font-size:14px;font-weight:900}
      .insight{display:grid;gap:4px;margin-top:12px;padding:12px;border-radius:18px;background:rgba(56,248,255,.08);border:1px solid rgba(56,248,255,.16)}.insight strong{color:#8ffcff;text-transform:capitalize}.insight span{color:rgba(255,255,255,.82);font-weight:850}.insight small{color:rgba(255,255,255,.58);font-weight:700;line-height:1.35}
      .editor{margin-top:12px;border-radius:18px;background:rgba(0,0,0,.16);border:1px solid rgba(255,255,255,.10);padding:9px 11px}.editor summary{cursor:pointer;font-weight:950;color:#8ffcff}.editor label{display:block;margin-top:10px;color:rgba(255,255,255,.58);font-size:10px;font-weight:950;text-transform:uppercase;letter-spacing:.12em}.editor input{box-sizing:border-box;width:100%;margin-top:5px;border:1px solid rgba(255,255,255,.14);border-radius:12px;background:rgba(0,0,0,.28);color:white;padding:10px;font-weight:800;outline:none}.editor button{margin-top:11px;width:100%;border:1px solid rgba(247,255,92,.36);border-radius:14px;background:rgba(247,255,92,.12);color:#f7ff8a;padding:10px;font-weight:950}.empty{grid-column:1/-1;padding:24px;border-radius:24px;background:rgba(255,255,255,.07);color:rgba(255,255,255,.72);font-weight:850}
      @media(max-width:720px){.head{align-items:flex-start}.summaryBadge{display:none}.body{grid-template-columns:1fr}.photo{height:190px}}
    </style>`;
    this.querySelectorAll('[data-save]').forEach(button => {
      button.addEventListener('click', () => this.saveClub(button.dataset.save));
    });
    this.querySelectorAll('.photo img').forEach(img => {
      img.addEventListener('error', () => {
        img.parentElement.innerHTML = this.fallbackArt(img.alt);
      });
    });
  }
}

if (!customElements.get('golf-club-results-card')) customElements.define('golf-club-results-card', GolfClubResultsCard);
window.customCards = window.customCards || [];
window.customCards.push({ type: 'golf-club-results-card', name: 'Golf Club Results', description: 'Mapped club analytics with brand, model, and image metadata' });
