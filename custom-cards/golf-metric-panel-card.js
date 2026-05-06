class GolfMetricPanelCard extends HTMLElement {
  setConfig(config) {
    this.config = config || {};
    this.metrics = this.config.metrics || [];
  }

  set hass(hass) {
    this._hass = hass;
    this.render();
  }

  getCardSize() { return Math.max(2, Math.ceil((this.metrics.length || 1) / 2)); }

  state(entity) { return this._hass?.states?.[entity]; }
  esc(value) { return String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }

  shortUnit(unit) {
    if (unit === 'yds') return 'yd';
    if (unit === 'degrees') return 'deg';
    return unit || '';
  }

  display(metric) {
    const state = this.state(metric.entity);
    if (!state || state.state === 'unknown' || state.state === 'unavailable') return '--';
    const n = Number(state.state);
    const unit = this.shortUnit(metric.unit ?? state.attributes?.unit_of_measurement ?? '');
    if (Number.isFinite(n)) {
      const decimals = metric.decimals ?? 1;
      return `${n.toFixed(decimals)}${unit ? ` ${unit}` : ''}`;
    }
    return this.esc(state.state);
  }

  renderMetric(metric) {
    const accent = metric.accent || '#38f8ff';
    return `<div class="metric" style="--accent:${accent}">
      <ha-icon icon="${this.esc(metric.icon || 'mdi:chart-box-outline')}"></ha-icon>
      <div class="text">
        <div class="label">${this.esc(metric.name || this.state(metric.entity)?.attributes?.friendly_name || metric.entity)}</div>
        <div class="value">${this.display(metric)}</div>
        ${metric.hint ? `<div class="hint">${this.esc(metric.hint)}</div>` : ''}
      </div>
    </div>`;
  }

  render() {
    if (!this._hass) return;
    this.innerHTML = `<ha-card>
      <div class="panel">
        <div class="head">
          <div>
            ${this.config.kicker ? `<div class="kicker">${this.esc(this.config.kicker)}</div>` : ''}
            <div class="title">${this.esc(this.config.title || 'Metrics')}</div>
          </div>
          ${this.config.badge ? `<div class="badge">${this.esc(this.config.badge)}</div>` : ''}
        </div>
        <div class="grid">${this.metrics.map(m => this.renderMetric(m)).join('')}</div>
      </div>
    </ha-card>
    <style>
      ha-card { overflow: hidden; border: 0; border-radius: 24px; background: linear-gradient(145deg, rgba(20,26,44,.92), rgba(8,12,24,.84)); color: white; box-shadow: 0 22px 60px rgba(0,0,0,.34); }
      .panel { position: relative; padding: 18px; isolation: isolate; }
      .panel:before { content: ''; position: absolute; inset: -35% -25% auto auto; width: 240px; height: 240px; border-radius: 50%; background: radial-gradient(circle, rgba(56,248,255,.22), transparent 62%); z-index: -1; }
      .head { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 14px; }
      .kicker { color: #8ffcff; font-size: 10px; font-weight: 900; letter-spacing: .18em; text-transform: uppercase; }
      .title { margin-top: 3px; font-size: 18px; font-weight: 850; letter-spacing: -.03em; }
      .badge { padding: 7px 10px; border-radius: 999px; background: rgba(255,255,255,.09); color: rgba(255,255,255,.75); font-size: 11px; font-weight: 800; text-transform: uppercase; letter-spacing: .08em; }
      .grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
      .metric { display: grid; grid-template-columns: 30px minmax(0, 1fr); align-items: center; gap: 9px; min-height: 74px; padding: 12px; border-radius: 18px; background: linear-gradient(145deg, rgba(255,255,255,.1), rgba(255,255,255,.045)); border: 1px solid rgba(255,255,255,.12); box-shadow: inset 0 0 0 1px color-mix(in srgb, var(--accent), transparent 84%); backdrop-filter: blur(14px); }
      ha-icon { width: 27px; height: 27px; color: var(--accent); filter: drop-shadow(0 0 12px color-mix(in srgb, var(--accent), transparent 45%)); }
      .label { color: rgba(255,255,255,.58); font-size: 9.5px; font-weight: 900; letter-spacing: .1em; text-transform: uppercase; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .value { margin-top: 5px; font-size: clamp(17px, 2.35vw, 23px); line-height: 1.05; font-weight: 930; letter-spacing: -.055em; white-space: normal; overflow: visible; }
      .hint { margin-top: 5px; color: rgba(255,255,255,.42); font-size: 10px; font-weight: 700; }
      @media (max-width: 760px) { .grid { grid-template-columns: 1fr; } }
    </style>`;
  }
}

if (!customElements.get('golf-metric-panel-card')) {
  customElements.define('golf-metric-panel-card', GolfMetricPanelCard);
}
window.customCards = window.customCards || [];
window.customCards.push({ type: 'golf-metric-panel-card', name: 'Golf Metric Panel', description: 'Glassy OpenGolfCoach metrics panel' });
