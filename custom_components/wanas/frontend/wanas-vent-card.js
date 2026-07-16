import { LitElement, html, css, nothing } from "https://unpkg.com/lit@3?module";

const DOMAIN = "wanas"

const UiTileType = Object.freeze({
  STATE_HIDDEN: 0,
  STATE_HIDDEN_ERROR: 1,
  STATE_SHOWN: 2,
  SWITCH: 3,
  NUMBER: 4
});

class UiTileEntity extends LitElement {
  static properties = {
    hass: { attribute: false },
    entity: { type: String },
    tile_type: { type: Number },
    name: { type: String },
    narrow_tile_show_name: { type: Boolean },
    state: { type: String },
    wide_tile: { type: Boolean },
  };

  constructor() {
    super();
    this.wide_tile = false;
    this.narrow_tile_show_name = true;
  }

  get _stateObj() {
    return this.entity ? this.hass?.states[this.entity] : null;
  }

  async _toggleEntity() {
    if (!this.entity || !this.hass) return;
    await this.hass.callService("homeassistant", "toggle", { entity_id: this.entity });
  }

  render() {
    const obj = this._stateObj;
    if(!obj)
      return html`unavailable`//can happen when user changes entity id
    const name = this.name ?? obj.attributes.friendly_name ?? this.entity;
    const state = this.state ?? this.hass.formatEntityState(obj);
    const color = obj.state === "unavailable"
      ? "var(--state-unavailable-color)"
      : this.tile_type === UiTileType.STATE_HIDDEN_ERROR && obj.state === "on"
        ? "var(--state-icon-error-color)"
        : obj.state === "on"
          ? "var(--state-active-color)"
          : obj.state === "off"
            ? "var(--state-inactive-color)"
            : "var(--state-icon-color)";

    if (this.wide_tile) {
      switch (this.tile_type) {
        case UiTileType.STATE_SHOWN:
        case UiTileType.STATE_HIDDEN:
        case UiTileType.STATE_HIDDEN_ERROR:
          return html`
            <div class="tile tile-wide">
              <div class="background button" @click=${this._show_more_info}>
                <ha-ripple .recenters=${true}></ha-ripple>
              </div>
              <div class="container">
                <div class="content">
                  <ha-tile-icon style="--tile-icon-color: ${color};">
                    <ha-state-icon slot="icon" icon="${obj.attributes.icon}"></ha-state-icon>
                  </ha-tile-icon>
                  <div class="info">
                    ${this.tile_type === UiTileType.STATE_SHOWN
                      ? html`<div class="primary">${name}</div><div class="secondary">${state}</div>`
                      : html`<div class="primary-only">${name}</div>`}
                  </div>
                </div>
              </div>
            </div>
          `;
        case UiTileType.SWITCH:
          return html`
            <div class="tile tile-wide">
              <div class="background button" @click=${this._show_more_info}>
                <ha-ripple .recenters=${true}></ha-ripple>
              </div>
              <div class="container">
                <div class="content">
                  <ha-tile-icon .interactive=${obj.state !== "unavailable"} class="button" style="--tile-icon-color: ${color};" @click=${obj.state !== "unavailable" ? this._toggleEntity : undefined}>
                    <ha-state-icon slot="icon" icon="${obj.attributes.icon}"></ha-state-icon>
                  </ha-tile-icon>
                  <div class="info">
                    <div class="primary">${name}</div>
                    <div class="secondary">${state}</div>
                  </div>
                </div>
              </div>
            </div>
          `;
        case UiTileType.NUMBER:
          return html`
            <div class="tile tile-wide button">
              <div class="background button" @click=${this._show_more_info}>
                <ha-ripple .recenters=${true}></ha-ripple>
              </div>
              <div class="container">
                <div class="content">
                  <ha-tile-icon style="--tile-icon-color: ${color};">
                    <ha-state-icon slot="icon" icon="${obj.attributes.icon}"></ha-state-icon>
                  </ha-tile-icon>
                  <div class="info">
                    <div class="primary">${name}</div>
                    <div class="secondary">${state}</div>
                  </div>
                </div>
                <div class="container-additional-item">
                  <!--
                  <ha-control-number-buttons
                    .value=${obj.state === "unavailable" ? 0 : Number(obj.state)}
                    .min=${obj.attributes.min ?? 0}
                    .max=${obj.attributes.max ?? 100}
                    .step=${obj.attributes.step ?? 1}
                    .unit=${obj.attributes.unit_of_measurement ?? ""}
                    .disabled=${obj.state === "unavailable"}
                    @value-changed=${async (e) => {
                      if (!this.entity || !this.hass)
                        return
                      await this.hass.callService("number", "set_value", {
                        entity_id: this.entity,
                        value: Number(e.target.value),
                      })
                      e.stopPropagation()
                    }}
                    @click=${(e) => e.stopPropagation()}
                    style="pointer-events: auto;"
                  ></ha-control-number-buttons>
                  -->
                  <ha-control-slider
                    .value=${obj.state === "unavailable" ? 0 : Number(obj.state)}
                    .min=${obj.attributes.min ?? 0}
                    .max=${obj.attributes.max ?? 100}
                    .step=${obj.attributes.step ?? 1}
                    .label=${name}
                    .showHandle=${obj.state !== "unavailable"}
                    .unit=${obj.attributes.unit_of_measurement ?? ""}
                    .disabled=${obj.state === "unavailable"}
                    @value-changed=${async (e) => {
                      if (!this.entity || !this.hass)
                        return;
                      await this.hass.callService("number", "set_value", {
                        entity_id: this.entity,
                        value: Number(e.target.value),
                      });
                      e.stopPropagation();
                    }}
                    @click=${(e) => e.stopPropagation()}
                    style="pointer-events: auto;"
                  ></ha-control-slider>
                </div>
              </div>
            </div>
          `;
        default:
          return html`unimplemented type`;
      }
    } else {
      if (this.tile_type === UiTileType.STATE_SHOWN) {
        if (this.narrow_tile_show_name){
          return html`
          <div class="tile tile-narrow">
            <div class="background button" @click=${this._show_more_info}>
              <ha-ripple .recenters=${true}></ha-ripple>
            </div>
            <div class="container">
              <div class="content">
                <div class="icon-primary">
                  <ha-state-icon .hass=${this.hass} .stateObj=${obj} class="icon"></ha-state-icon>
                  <div class="primary">${name}</div>
                </div>
                <div class="secondary">${state}</div>
              </div>
            </div>
          </div>
        `;
        }
        else {
          return html`
          <div class="tile tile-narrow tile-xsmall">
            <div class="background button" @click=${this._show_more_info}>
              <ha-ripple .recenters=${true}></ha-ripple>
            </div>
            <div class="container">
              <div class="content">
                <div class="icon-primary">
                  <ha-state-icon .hass=${this.hass} .stateObj=${obj} class="icon"></ha-state-icon>
                </div>
                <div class="secondary">${state}</div>
              </div>
            </div>
          </div>
        `;
        }
      } else {
        return html`unimplemented type`;
      }
    }
  }

  _show_more_info() {
    this.dispatchEvent(new CustomEvent("hass-more-info", {
      detail: { entityId: this.entity },
      bubbles: true,
      composed: true,
    }));
  }

  static styles = css`
    :host {
      display: flex;
    }
    .tile {
      border-radius: var(--ha-card-border-radius, 12px);
      border-width: 1px;
      border-style: solid;
      border-color: var(--ha-card-border-color, var(--divider-color, #e0e0e0));
      box-shadow: var(--ha-card-box-shadow, 0 1px 3px rgba(0, 0, 0, 0.1));
      user-select: none;
      transition: box-shadow 0.3s ease;
      width: 100%;
      position: relative;
      display: flex;
    }
    .tile:hover {
      box-shadow: var(--ha-card-box-shadow, 0 4px 8px rgba(0, 0, 0, 0.15));
    }
    .tile-xsmall {
      height: 50px !important;
    }
    .tile-narrow {
      height: 80px;
      justify-content: center;
    }
    .tile-wide {
    }
    .background {
      position: absolute;
      top: 0;
      left: 0;
      bottom: 0;
      right: 0;
      border-radius: var(--ha-card-border-radius, 12px);
      margin: -1px;
      overflow: hidden;
    }
    .container {
      margin: -1px;
      display: flex;
    }
    .tile-wide .container {
      flex-direction: column;
      flex: 1;
    }
    .container-additional-item {
      --feature-color: var(--state-icon-color);
      --feature-height: 42px;
      --feature-border-radius: var(--ha-card-features-border-radius, var(--ha-border-radius-lg));
      --feature-button-spacing: 12px;
      pointer-events: none;
      position: relative;
      width: 100%;
      display: flex;
      flex-direction: column;
      gap: var(--ha-card-feature-gap, 12px);
      box-sizing: border-box;
      justify-content: space-evenly;
      padding: 0 12px 12px 12px;
    }
    .tile-narrow .container .content {
      padding: 4px 2px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      pointer-events: none;
    }
    .tile-wide .container .content {
      padding: 10px;
      display: flex;
      flex-direction: row;
      gap: 10px;
      pointer-events: none;
    }
    .button {
      cursor: pointer;
      pointer-events: auto;
    }
    .icon {
      color: var(--state-icon-color);
      transition: color 180ms ease-in-out;
      flex-shrink: 0;
      --mdc-icon-size: 24px;
    }
    .button.icon {
      color: var(--state-active-color);
    }
    .tile-wide .container .content .icon {
      padding: 6px;
      margin: -6px;
    }
    .info {
      display: flex;
      flex-direction: column;
      width: 100%;
    }
    .tile-wide .info {
      align-items: flex-start;
    }
    .icon-primary {
      display: flex;
      flex-direction: column;
      width: 100%;
      align-items: center;
      gap: 2px;
    }
    .primary-only {
      color: var(--tile-info-primary-color);
      font-size: var(--tile-info-primary-font-size);
      font-weight: var(--tile-info-primary-font-weight);
      letter-spacing: var(--tile-info-primary-letter-spacing);
      width: 100%;
      white-space: normal;
      overflow-wrap: break-word;
      word-break: break-word;
    }
    .tile-narrow .primary-only {
      text-align: center;
      line-height: 1.0;
    }
    .tile-wide .primary-only {
      text-align: left;
      line-height: 1.1;
    }
    .primary {
      color: var(--tile-info-primary-color);
      font-size: var(--tile-info-primary-font-size);
      font-weight: var(--tile-info-primary-font-weight);
      letter-spacing: var(--tile-info-primary-letter-spacing);
      width: 100%;
    }
    .tile-narrow .primary {
      text-align: center;
      line-height: 1.0;
      white-space: normal;
      overflow-wrap: break-word;
      word-break: break-word;
    }
    .tile-wide .primary {
      text-align: left;
      line-height: 1.1;
      white-space: normal;
      overflow-wrap: break-word;
      word-break: break-word;
    /* optionally
      text-overflow: ellipsis;
      overflow: hidden;
      white-space: nowrap;
    */
    }
    .secondary {
      color: var(--secondary-text-color);
      font-size: var(--tile-info-secondary-font-size);
      font-weight: var(--tile-info-secondary-font-weight);
      letter-spacing: var(--tile-info-secondary-letter-spacing);
      width: 100%;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .tile-narrow .secondary {
      text-align: center;
    }
    .tile-wide .secondary {
      text-align: left;
    }
  `;
}

customElements.define("ui-tile-entity", UiTileEntity);

class WanasCard extends LitElement {
  static properties = {
    hass: { attribute: false },
    _config: { attribute: false },
    _deviceId: { attribute: false },
    _entityRegistry: { attribute: false },
    _settingsOpen: { type: Boolean },
    _wirelessSensorsOpen: { type: Boolean },
    _trDB: { state: false },
    _loadedLang: { state: false },
    readOnlySensors: { attribute: false },
    readWriteSwitches: { attribute: false },
    readWriteNumbers: { attribute: false },
    readOnlyBinarySensors: { attribute: false },
    errors: { attribute: false },
    funcEnabled: { attribute: false },
    dateTime: { attribute: false },
  };

  constructor() {
    super();
    this._settingsOpen = false;
    this._wirelessSensorsOpen = true;
    this._trDB = {};
    this._loadedLang = "";
  }

  get _settingsStorageKey() {
    return this._config?.device ? `${this._config.device}_settingsOpen` : null;
  }

  get _wirelessSensorsStorageKey() {
    return this._config?.device ? `${this._config.device}_wirelessSensorsOpen` : null;
  }

  setConfig(config) {
    if (!config || !config.device) {
      // show red error card if device not specified
      throw new Error("Please select a Wanas device.");
    }
    this._config = config;
  }

  getCardSize() {
    return 3;
  }

  static getConfigForm() {
    return {
      schema: [
        {
          name: "device",
          required: true,
          selector: {
            device: {
              filter: {
                integration: DOMAIN,
              },
            },
          },
        },
        {
          name: "name",
          required: false,
          default: "Wanas",
          selector: {
            text: {},
          },
        },
      ],
    };
  }

  async connectedCallback() {
    super.connectedCallback();
    if (this.hass) {
      if (this._unsub) {
        this._unsub();
        this._unsub = null;
      }
      this._unsub = await this.hass.connection.subscribeEvents(this._handleRegistryUpdate.bind(this), "entity_registry_updated");
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    if (this._unsub) {
      this._unsub();
      this._unsub = null;
    }
  }

  async _handleRegistryUpdate() {
    await this._updateRegistryAndEntities();
    this.requestUpdate();
  }

  async firstUpdated(changedProps) {
    await this._loadTranslations();
  }

  async updated(changedProps) {
    if (changedProps.has("hass") && this.hass) {
      if (this._loadedLang !== this.hass.language)
        this._loadTranslations();
    }
    if (changedProps.has("_config") || changedProps.has("hass")) {
      if (this._config?.device && this.hass) {
        if (!this._entityRegistry) {
          await this._updateRegistryAndEntities();
        }
        const settingsKey = this._settingsStorageKey;
        if (settingsKey) {
          let result = localStorage.getItem(settingsKey)//returns null if not exists
          if(result) {
            this._settingsOpen = result === 'true';
          }
        }

        const wirelessSensorsKey = this._wirelessSensorsStorageKey;
        if (wirelessSensorsKey) {
          let result = localStorage.getItem(wirelessSensorsKey)//returns null if not exists
          if(result) {
            this._wirelessSensorsOpen = result === 'true';
          }
        }
      }
    }
  }

  //simple translator - uses english string as key + fallback
  tr(source, params = {}) {
    //translation exists? -> use it, else fall back to source string itself
    let text = this._trDB[source] ?? source;
    //replace placeholders only if we have any
    if(Object.keys(params).length > 0){
      for(const [key, value] of Object.entries(params))
        text = text.replace(`{${key}}`, value);
    }
    //console.log("tr: source: ", source, "   return: ", text)
    return text;
  }

  async _loadTranslations() {
  if (!this.hass) 
    return;

  let lang = this.hass.language || 'en';

  //build ordered fallback list
  const fallbacks = [lang];
  if (lang.includes('-')) {
    const parts = lang.split('-');
    if (parts.length >= 2)
      fallbacks.push(parts.slice(0, 2).join('-'));//ex. zh-Hans-CN -> zh-Hans
    fallbacks.push(parts[0]);//base language
  }
  if (!fallbacks.includes('en'))
    fallbacks.push('en');

  for (const tryLang of fallbacks) {
    if (this._loadedLang === tryLang)
      return; // skip if already loaded

    try {
      const response = await fetch(`/${DOMAIN}/translations/${tryLang}.json`);
      if (response.ok) {
        this._trDB = await response.json();
        this._loadedLang = tryLang;
        this.requestUpdate();
        return;
      }
    } catch {} //silent, next
  }

  //no match at all -> empty (tr() uses english source strings)
  this._trDB = {};
  this._loadedLang = 'en';
  this.requestUpdate();
}

  async _updateRegistryAndEntities() {
    this._entityRegistry = await this._getEntityRegistry(this.hass);
    this._deviceId = this._getDevIdFromConfDevId(this._config.device);
    const configDeviceId = this._config.device;

    this.readOnlySensors = this._fetchEntities(configDeviceId, [
      "supply_airflow", "extract_airflow", "supply_fan_speed", "extract_fan_speed",
      "outdoor_temp", "exhaust_temp", "supply_temp", "extract_temp", "extra_temp",
      "filter_wear_status", "extsen_th_humidity_livingroom",
      "extsen_th_humidity_bathroom1", "extsen_th_humidity_bathroom2",
      "extsen_co2th_co2_dayzone", "extsen_co2th_co2_nightzone",
      "extsen_co2th_humidity_dayzone", "extsen_co2th_humidity_nightzone",
      "extsen_th_temp_livingroom", "extsen_th_temp_bathroom1",
      "extsen_th_temp_bathroom2", "extsen_co2th_temp_dayzone",
      "extsen_co2th_temp_nightzone"
    ]);

    this.readWriteSwitches = this._fetchEntities(configDeviceId, [
      "ghe_mode", "summer_bypass_mode", "humidifier_mode", "zone_damper_mode"
    ]);

    this.readWriteNumbers = this._fetchEntities(configDeviceId, [
      "heater_mode", "cooler_mode", "vacation_mode", "fireplace_mode", "party_mode",
      "speed1_airflow", "speed2_airflow", "speed3_airflow", "manual_fan_speed", "manual_comfort_temp"
    ]);

    this.readOnlyBinarySensors = this._fetchEntities(configDeviceId, [
      "ghe", "summer_bypass", "humidifier", "heater", "cooler", "vacation",
      "frost_protection", "primary_heater", "zone_damper", "connection_status"
    ]);

    this.errors = this._fetchEntities(configDeviceId, [
      "extract_fan_error", "supply_fan_error", "outdoor_temp_sensor_error",
      "extract_temp_sensor_error", "supply_temp_sensor_error", "exhaust_temp_sensor_error",
      "humidifier_temp_sensor_error", "extra_outdoor_temp_sensor_error",
      "extra_supply_temp_sensor_error", "extract_air_pressure_sensor_error",
      "supply_air_pressure_sensor_error"
    ]);

    this.funcEnabled = this._fetchEntities(configDeviceId, [
      "humidifier_func_enabled", "xf_func_enabled", "ghe_func_enabled",
      "cooler_func_enabled", "heater_func_enabled", "zone_damper_func_enabled",
      "extra_supply_temp_enabled", "extra_outdoor_temp_enabled"
    ]);

    this.dateTime = this._fetchEntities(configDeviceId, ["device_date", "device_time"]);
  }

  async _getEntityRegistry(hass) {
    return await hass.callWS({ type: "config/entity_registry/list" });
  }

  _fetchEntities(configDeviceId, keys) {
    return Object.fromEntries(keys.map(key => [key, this._getEntityEntry(configDeviceId, this._deviceId, key)]));
  }

  _getEntityEntry(configDeviceId, deviceId, key) {
    const hassEntityPrefix = `${DOMAIN}_${deviceId}`;
    return this._entityRegistry.find(
      (e) =>
      e.device_id === configDeviceId &&
      e.unique_id === `${hassEntityPrefix}_${key}`
    );
  }

  _getDevIdFromConfDevId(configDeviceId) {
    const device = this.hass?.devices?.[configDeviceId];
    if (!device)
      return null;
    for (const ident of device.identifiers) {
      const [domain, deviceId] = ident;
      if (domain === DOMAIN)
        return deviceId;
    }
    return null;
  }

  _openMoreInfo(entityId) {
    this.dispatchEvent(new CustomEvent("hass-more-info", {
      bubbles: true,
      composed: true,
      detail: { entityId },
    }));
  }

  _tryGetShorterName(entry) {
    return entry?.name ?? entry?.original_name ?? null;
  }

  _getEntityStateSafe(entity) {
    if (!entity)
      return "";
    const stateObj = this.hass.states[entity.entity_id];
    return stateObj.state !== "unavailable" ? stateObj.state : this.hass.formatEntityState(stateObj);
  }

  _tile(entity, overrideLabelEntry = null) {
    if (!entity)
      return html``;
    const stateObj = this.hass.states[entity.entity_id];
    return html`
      <div class="entity-tile clickable" @click=${() => this._openMoreInfo(entity.entity_id)}>
        <div class="icon-value">
          <ha-state-icon .hass=${this.hass} .stateObj=${stateObj}></ha-state-icon>
          <div class="value">${this.hass.formatEntityState(stateObj)}</div>
        </div>
        <div class="label">
          ${overrideLabelEntry ? this._tryGetShorterName(overrideLabelEntry) : this._tryGetShorterName(entity)}
        </div>
      </div>
    `;
  }

  _renderHeader() {
    return this._config.name ? html`<div class="wanas-card-header">${this._config.name}</div>` : nothing;
  }

  _renderErrors() {
    const allErrors = Object.values(this.errors);
    const isAnyError = allErrors.some(
      (err) => err && this.hass.states[err.entity_id]?.state === "on"
    );
    if (!isAnyError)
      return nothing;
    return html`
      <div class="tiles-container-title">
        <ha-icon icon="mdi:alert-circle"></ha-icon>
        <div>${this.tr("Detected Errors")}</div>
      </div>
      <div class="section-padding"></div>
      <div class="wide-tile-container">
        ${allErrors.map(err => err && this.hass.states[err.entity_id]?.state === "on" ? html`
          <ui-tile-entity
            .hass=${this.hass}
            .entity=${err.entity_id}
            .name=${this._tryGetShorterName(err)}
            .wide_tile=${true}
            .tile_type=${UiTileType.STATE_HIDDEN_ERROR}
          ></ui-tile-entity>
        ` : nothing)}
      </div>
    `;
  }

  _renderStatusTitle() {
    //display section title if there are errors, otherwise hide - to save space
    const allErrors = Object.values(this.errors);
    const isAnyError = allErrors.some(err => err && this.hass.states[err.entity_id]?.state === "on");
    if (!isAnyError)
      return nothing;
    return html`
      <div class="tiles-container-title">
        <ha-icon icon="mdi:list-status"></ha-icon>
        <div>${this.tr("Status")}</div>
      </div>
      <div class="section-padding"></div>
    `;
  }

  _renderTopRow() {
    return html`
      <div class="top-row">
        <div class="icon-value clickable" @click=${() => this._openMoreInfo(this.readOnlyBinarySensors.connection_status.entity_id)}>
          <ha-state-icon .hass=${this.hass} .stateObj=${this.hass.states[this.readOnlyBinarySensors.connection_status.entity_id]}></ha-state-icon>
          <div class="value-top-row">${this.hass.formatEntityState(this.hass.states[this.readOnlyBinarySensors.connection_status.entity_id])}</div>
        </div>
        <div class="top-row-date-time">
          <div class="clickable" @click=${() => this._openMoreInfo(this.dateTime.device_date.entity_id)}>
            <ha-state-icon .hass=${this.hass} .stateObj=${this.hass.states[this.dateTime.device_date.entity_id]}></ha-state-icon>
            ${this.hass.formatEntityState(this.hass.states[this.dateTime.device_date.entity_id])}
          </div>
          <div class="clickable" @click=${() => this._openMoreInfo(this.dateTime.device_time.entity_id)}>
            <ha-state-icon .hass=${this.hass} .stateObj=${this.hass.states[this.dateTime.device_time.entity_id]}></ha-state-icon>
            ${this.hass.formatEntityState(this.hass.states[this.dateTime.device_time.entity_id])}
          </div>
        </div>
      </div>
    `;
  }

  _renderMainArea() {
    return html`
      <div class="main-area">
        <div class="side-column left-column">
          ${this.hass.states[this.funcEnabled.extra_outdoor_temp_enabled.entity_id].state === "on"
            ? this._tile(this.readOnlySensors.extra_temp, this.readOnlySensors.outdoor_temp)
            : this._tile(this.readOnlySensors.outdoor_temp)}
          ${this._tile(this.readOnlySensors.extract_temp)}
        </div>
        <div class="center-column">
          <div class="house-container">
            <svg width="245.8" height="243.6" version="1.1" viewBox="0 0 65.035 64.453" xml:space="preserve" xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"><defs><linearGradient id="linearGradient6518" x1="12.887" x2="58.033" y1="31.549" y2="31.549" gradientUnits="userSpaceOnUse"><stop stop-color="#e50414" offset=".1173"/><stop stop-color="#059ce1" offset=".31925"/></linearGradient><linearGradient id="linearGradient6534" x1=".087014" x2="42.133" y1="32.671" y2="32.671" gradientUnits="userSpaceOnUse"><stop stop-color="#059ce1" offset=".41692"/><stop stop-color="#e50414" offset=".70221"/></linearGradient></defs><g fill-rule="evenodd"><path d="m3.2106 29.557 29.307-26.44 29.36 26.438h-3.9103c-2.246 0-3.109 0.63973-3.1109 3.0672l-0.02243 28.641h-44.089v-28.606c0-2.4075-0.79118-3.0786-3.1396-3.0858zm-2.4108-1.9985 29.389-26.5c1.5426-1.391 3.1915-1.3436 4.6805 0l29.073 26.233c2.124 1.9165 0.58046 5.3307-1.7833 5.3307l-4.1919-1.08e-4 1e-5 27.93c1e-6 2.4176-1.0438 3.7627-3.6639 3.7627h-43.488c-2.4031 0-3.2001-1.8134-3.2001-3.2357l-0.010257-28.422-4.345 1.12e-4c-3.1734 8.2e-5 -3.9819-3.7262-2.4607-5.0978z" fill="#5ab9e7"/><path d="m23.176 24.455 6.4724 6.3893-6.3559 6.3265-6.4857-6.4054zm-0.68101-0.66822c0.58834-0.58736 0.68428-0.59467 1.288 0l6.4636 6.3663c0.67815 0.66795 0.67118 0.73349 0.0067 1.3966l-6.2705 6.2579c-0.595 0.59381-0.74634 0.59353-1.3496 0l-6.5349-6.4295c-0.52209-0.51368-0.52632-0.68002 0-1.2055z" fill="#746b6c"/><path d="m16.807 30.765 6.3692-6.3105 6.4724 6.3893-6.3559 6.3265z" fill="#c8c4c3"/><path d="m12.887 53.565v-16.924h1.5409c1.9613 0 3.6891-1.9189 5.8753-4.2444 4.2566-4.5277 9.2797-10.612 12.462-14.372 5.0407-5.9557 9.8598-7.2454 12.627-7.1686l7.768 0.21551v-1.537l4.8721 2.5151-4.89 2.3724v-1.5154l-7.3865-0.10894c-4.675-0.06895-8.2062 2.3818-11.7 6.6296-4.2265 5.1386-8.5839 10.146-13.055 15.04-2.3164 2.5487-4.3947 3.8436-6.2524 3.9757v15.105z" fill="url(#linearGradient6518)"/><path d="m0.087014 10.848c5.5061-0.14033 8.8838 1.3481 10.838 3.9262 5.7888 7.9733 10.893 13.526 17.587 20.145 2.3665 2.0527 2.5857 1.6385 6.8109 1.6385h5.3244v13.173h1.4859l-2.4406 4.7711-2.4396-4.7594h1.4999v-11.31l-5.4862-0.02094c-3.455-0.013187-4.1367-0.2288-7.2952-3.3839-7.0791-7.0716-11.504-12.22-16.621-19.195-0.44988-0.61332-2.7653-3.4754-9.2609-3.102z" fill="url(#linearGradient6534)"/><circle cx="23.228" cy="30.813" r="2.0402" fill="#f0ebeb"/></g></svg>
            <div class="overlay-tile extract-fan-overlay clickable" @click=${() => this._openMoreInfo(this.readOnlySensors.extract_airflow.entity_id)}>
              <div class="icon-value">
                <ha-state-icon class="large-icon" .hass=${this.hass} .stateObj=${this.hass.states[this.readOnlySensors.extract_fan_speed.entity_id]}></ha-state-icon>
                ${this.hass.states[this.funcEnabled.xf_func_enabled.entity_id].state === "on"
                  ? html`<div class="value">${this._getEntityStateSafe(this.readOnlySensors.extract_airflow)}</div>`
                  : nothing}
              </div>
            </div>
            <div class="overlay-tile supply-fan-overlay clickable" @click=${() => this._openMoreInfo(this.readOnlySensors.supply_airflow.entity_id)}>
              <div class="icon-value">
                <ha-state-icon class="large-icon" .hass=${this.hass} .stateObj=${this.hass.states[this.readOnlySensors.supply_fan_speed.entity_id]}></ha-state-icon>
                ${this.hass.states[this.funcEnabled.xf_func_enabled.entity_id].state === "on"
                  ? html`<div class="value">${this._getEntityStateSafe(this.readOnlySensors.supply_airflow)}</div>`
                  : nothing}
              </div>
            </div>
            ${this.hass.states[this.funcEnabled.extra_supply_temp_enabled.entity_id].state === "on" ? html`
              <div class="overlay-tile extra-temp-overlay clickable" @click=${() => this._openMoreInfo(this.readOnlySensors.supply_temp.entity_id)}>
                <div class="icon-value">
                  <ha-state-icon .hass=${this.hass} .stateObj=${this.hass.states[this.readOnlySensors.supply_temp.entity_id]}></ha-state-icon>
                  <div class="value">${this.hass.formatEntityState(this.hass.states[this.readOnlySensors.supply_temp.entity_id])}</div>
                </div>
              </div>
            ` : nothing}
            ${this.hass.states[this.funcEnabled.extra_outdoor_temp_enabled.entity_id].state === "on" ? html`
              <div class="overlay-tile extra-outdoor-overlay clickable" @click=${() => this._openMoreInfo(this.readOnlySensors.outdoor_temp.entity_id)}>
                <div class="icon-value">
                  <ha-state-icon .hass=${this.hass} .stateObj=${this.hass.states[this.readOnlySensors.outdoor_temp.entity_id]}></ha-state-icon>
                  <div class="value">${this.hass.formatEntityState(this.hass.states[this.readOnlySensors.outdoor_temp.entity_id])}</div>
                </div>
              </div>
            ` : nothing}
          </div>
        </div>
        <div class="side-column right-column">
          ${this._tile(this.readOnlySensors.exhaust_temp)}
          ${this.hass.states[this.funcEnabled.extra_supply_temp_enabled.entity_id].state === "on"
            ? this._tile(this.readOnlySensors.extra_temp, this.readOnlySensors.supply_temp)
            : this._tile(this.readOnlySensors.supply_temp)}
        </div>
      </div>
    `;
  }

  _renderStatusTiles() {
    const tiles = [
      { entityMap: this.readOnlySensors, key: 'filter_wear_status' },
      { entityMap: this.readOnlyBinarySensors, key: 'summer_bypass' },
      { entityMap: this.readOnlyBinarySensors, key: 'frost_protection' },
      { entityMap: this.readOnlyBinarySensors, key: 'primary_heater' },
      { entityMap: this.readOnlyBinarySensors, key: 'vacation' },
      { funcKey: 'ghe_func_enabled', entityMap: this.readOnlyBinarySensors, key: 'ghe' },
      { funcKey: 'humidifier_func_enabled', entityMap: this.readOnlyBinarySensors, key: 'humidifier' },
      { funcKey: 'heater_func_enabled', entityMap: this.readOnlyBinarySensors, key: 'heater' },
      { funcKey: 'cooler_func_enabled', entityMap: this.readOnlyBinarySensors, key: 'cooler' },
      { funcKey: 'zone_damper_func_enabled', entityMap: this.readOnlyBinarySensors, key: 'zone_damper' },
    ].filter(tile => !tile.funcKey || this.hass.states[this.funcEnabled[tile.funcKey].entity_id].state === "on");

    return html`
      <div class="status-tiles-container">
        ${tiles.map(({ entityMap, key }) => html`
          <ui-tile-entity
            .hass=${this.hass}
            .entity=${entityMap[key]?.entity_id}
            .name=${this._tryGetShorterName(entityMap[key])}
            .tile_type=${UiTileType.STATE_SHOWN}
          ></ui-tile-entity>
        `)}
      </div>
    `;
  }

  _renderWirelessSensors() {
    const renderTilesFunc = (name, tiles) => {
      return tiles?.length ? html`
      <div class="wireless-sensor-tiles-outer-row">
        <div class="tiles-container-title">
          <ha-icon icon="mdi:router-wireless"></ha-icon>
          <div>${name}</div>
        </div>
        <div class="wireless-sensor-tiles-inner-container">
          ${tiles.map(({ entityMap, key }) => html`
            <ui-tile-entity
              .hass=${this.hass}
              .entity=${entityMap[key]?.entity_id}
              .name=${this._tryGetShorterName(entityMap[key])}
              .narrow_tile_show_name=${false}
              .tile_type=${UiTileType.STATE_SHOWN}
            ></ui-tile-entity>
          `)}
        </div>
        </div>
      ` : nothing;
    }
    const filterFunc = (tile) => {
      const entityId = tile.entityMap[tile.key].entity_id;
      return this.hass.states[entityId]?.state !== "unknown" //sensor not connected
                && this.hass.states[entityId]?.state !== "unavailable"//hrv not connected;
    };

    const livingroom_tiles = [
      { entityMap: this.readOnlySensors, key: 'extsen_th_temp_livingroom' },
      { entityMap: this.readOnlySensors, key: 'extsen_th_humidity_livingroom' },
    ].filter(filterFunc);
    const bathroom1_tiles = [
      { entityMap: this.readOnlySensors, key: 'extsen_th_temp_bathroom1' },
      { entityMap: this.readOnlySensors, key: 'extsen_th_humidity_bathroom1' },
    ].filter(filterFunc);
    const bathroom2_tiles = [
      { entityMap: this.readOnlySensors, key: 'extsen_th_temp_bathroom2' },
      { entityMap: this.readOnlySensors, key: 'extsen_th_humidity_bathroom2' },
    ].filter(filterFunc);
    const dayzone_tiles = [
      { entityMap: this.readOnlySensors, key: 'extsen_co2th_temp_dayzone' },
      { entityMap: this.readOnlySensors, key: 'extsen_co2th_humidity_dayzone' },
      { entityMap: this.readOnlySensors, key: 'extsen_co2th_co2_dayzone' },
    ].filter(filterFunc);
    const nightzone_tiles = [
      { entityMap: this.readOnlySensors, key: 'extsen_co2th_temp_nightzone' },
      { entityMap: this.readOnlySensors, key: 'extsen_co2th_humidity_nightzone' },
      { entityMap: this.readOnlySensors, key: 'extsen_co2th_co2_nightzone' },
    ].filter(filterFunc);

    const any_connected = livingroom_tiles?.length || bathroom1_tiles?.length
        || bathroom2_tiles?.length || dayzone_tiles?.length
        || nightzone_tiles?.length

    return any_connected ? html`
      <div class="tiles-container-title">
        <ha-icon icon="mdi:router-wireless"></ha-icon>
        <div>${this.tr("Extra sensors")}</div>
        <ha-switch
          .disabled=${false}
          @change=${(e) => {
            this._wirelessSensorsOpen = e.target.checked;
            const key = this._wirelessSensorsStorageKey;
            if (key) {
              localStorage.setItem(key, this._wirelessSensorsOpen);
            }
          }}
          .checked=${this._wirelessSensorsOpen}
          .haptic=${true}
          class="dropdown-section-switch"
        ></ha-switch>
      </div>
      <div class="dropdown-section-wrapper ${this._wirelessSensorsOpen ? 'open' : ''}">
        <div class="dropdown-section-inner">
          <div class="wireless-sensor-tiles-outer-container">
            ${renderTilesFunc(this.tr("Living room"), livingroom_tiles)}
            ${renderTilesFunc(this.tr("Bathroom 1"), bathroom1_tiles)}
            ${renderTilesFunc(this.tr("Bathroom 2"), bathroom2_tiles)}
          </div>
          <div class="wireless-sensor-tiles-outer-container">
            ${renderTilesFunc(this.tr("Day zone"), dayzone_tiles)}
            ${renderTilesFunc(this.tr("Night zone"), nightzone_tiles)}
          </div>
        </div>
      </div>
    ` : nothing;
  }

  _renderSettings() {
    const tiles = [
      { funcKey: 'ghe_func_enabled', entityMap: this.readWriteSwitches, key: 'ghe_mode', type: UiTileType.SWITCH },
      { entityMap: this.readWriteSwitches, key: 'summer_bypass_mode', type: UiTileType.SWITCH },
      { funcKey: 'humidifier_func_enabled', entityMap: this.readWriteSwitches, key: 'humidifier_mode', type: UiTileType.SWITCH },
      { funcKey: 'zone_damper_func_enabled', entityMap: this.readWriteSwitches, key: 'zone_damper_mode', type: UiTileType.SWITCH },
      { entityMap: this.readWriteNumbers, key: 'party_mode', type: UiTileType.NUMBER },
      { entityMap: this.readWriteNumbers, key: 'fireplace_mode', type: UiTileType.NUMBER },
      { entityMap: this.readWriteNumbers, key: 'vacation_mode', type: UiTileType.NUMBER },
      { funcKey: 'heater_func_enabled', entityMap: this.readWriteNumbers, key: 'heater_mode', type: UiTileType.NUMBER },
      { funcKey: 'cooler_func_enabled', entityMap: this.readWriteNumbers, key: 'cooler_mode', type: UiTileType.NUMBER },
      { entityMap: this.readWriteNumbers, key: 'speed1_airflow', type: UiTileType.NUMBER },
      { entityMap: this.readWriteNumbers, key: 'speed2_airflow', type: UiTileType.NUMBER },
      { entityMap: this.readWriteNumbers, key: 'speed3_airflow', type: UiTileType.NUMBER },
      { entityMap: this.readWriteNumbers, key: 'manual_fan_speed', type: UiTileType.NUMBER },
      { entityMap: this.readWriteNumbers, key: 'manual_comfort_temp', type: UiTileType.NUMBER },
    ].filter(tile => !tile.funcKey || this.hass.states[this.funcEnabled[tile.funcKey].entity_id].state === "on");

    return html`
      <div class="tiles-container-title">
        <ha-icon icon="mdi:cog-outline"></ha-icon>
        <div>${this.tr("Settings")}</div>
        <ha-switch
          .disabled=${false}
          @change=${(e) => {
            this._settingsOpen = e.target.checked;
            const key = this._settingsStorageKey;
            if (key) {
              localStorage.setItem(key, this._settingsOpen);
            }
          }}
          .checked=${this._settingsOpen}
          .haptic=${true}
          class="dropdown-section-switch"
        ></ha-switch>
      </div>
      <div class="dropdown-section-wrapper ${this._settingsOpen ? 'open' : ''}">
        <div class="dropdown-section-inner">
          <div class="wide-tile-container">
            ${tiles.map(({ entityMap, key, type }) => html`
              <ui-tile-entity
                .hass=${this.hass}
                .entity=${entityMap[key]?.entity_id}
                .name=${this._tryGetShorterName(entityMap[key])}
                .tile_type=${type}
                .wide_tile=${true}
              ></ui-tile-entity>
            `)}
          </div>
        </div>
      </div>
    `;
  }

  render() {
    if (!this._deviceId || !this._entityRegistry || !this._config?.device) {
      return html`<ha-card><p>No device selected</p></ha-card>`;
    }

    return html`
      <ha-card>
        ${this._renderHeader()}
        ${this._renderErrors()}
        ${this._renderStatusTitle()}
        ${this._renderTopRow()}
        ${this._renderMainArea()}
        ${this._renderStatusTiles()}
        ${this._renderWirelessSensors()}
        ${this._renderSettings()}
      </ha-card>
    `;
  }

  static styles = css`
    ha-card {
      padding: 10px;
    }
    .wanas-card-header {
      color: var(--primary-text-color);
      font-size: 24px;
      letter-spacing: -.012em;
      font-weight: 400;
    }
    .wide-tile-container {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      row-gap: 8px;
      column-gap: 4px;
      max-width: 440px;
    }
    .status-tiles-container {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(75px, 1fr));
      row-gap: 8px;
      column-gap: 4px;
    }
    .wireless-sensor-tiles-outer-container {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(135px, 1fr));
      column-gap: 8px;
    }
    .wireless-sensor-tiles-outer-row {
      display: flex;
      flex-direction:
      column; row-gap: 6px;
    }
    .wireless-sensor-tiles-inner-container {
      display: grid;
      grid-template-columns: repeat(auto-fit, 65px);
      row-gap: 8px;
      column-gap: 8px;
    }
    .tiles-container-title {
      padding-top: 10px;
      font-size: 18px;
      font-weight: 400;
      color: var(--primary-text-color);
      display: flex;
      flex-direction: row;
      gap: 0px 5px;
      align-items: center;
    }
    .section-padding {
      padding-top: 10px;
    }
    .clickable {
      cursor: pointer;
    }
    .top-row {
      display: flex;
      justify-content: space-between;
      padding-bottom: 5px;
      border-bottom: 1px solid var(--ha-card-border-color, var(--divider-color, #e0e0e0));
    }
    .top-row-date-time {
      display: flex;
      gap: 8px;
    }
    .main-area {
      display: flex;
      flex-direction: row;
      align-items: stretch;
      padding-top: 8px;
      padding-bottom: 8px;
    }
    .side-column {
      flex: 1 1 auto;
      min-width: 0;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      z-index: 1;
    }
    .left-column {
      align-items: flex-start;
    }
    .right-column {
      align-items: flex-end;
    }
    .left-column .entity-tile {
      align-items: flex-start;
      text-align: left;
    }
    .right-column .entity-tile {
      align-items: flex-end;
      text-align: right;
    }
    .left-column .icon-value {
      justify-content: flex-start;
    }
    .right-column .icon-value {
      justify-content: flex-end;
    }
    .center-column {
      flex: 0 0 auto;
      width: 152px;
      display: flex;
      justify-content: center;
      align-items: center;
    }
    .house-container {
      position: relative;
      width: 100%;
      pointer-events: none;
      z-index: 0;
    }
    .house-container svg {
      width: 100%;
      height: auto;
      display: block;
    }
    .overlay-tile {
      position: absolute;
      pointer-events: auto;
      z-index: 1;
    }
    .extract-fan-overlay {
      top: 30px;
      left: 65px;
    }
    .supply-fan-overlay {
      bottom: 50px;
      left: 65px;
    }
    .extra-temp-overlay {
      bottom: 25px;
      left: 65px;
    }
    .extra-outdoor-overlay {
      top: 0px;
      left: -25px;
      width: auto;
    }
    .entity-tile {
      display: flex;
      flex-direction: column;
    }
    .icon-value {
      display: flex;
      align-items: center;
    }
    .label {
      font-size: 12px;
    }
    .value {
      font-size: 16px;
      font-weight: 600;
    }
    .value-top-row {
      font-size: 14px;
    }
    .large-icon {
      --mdc-icon-size: 24px;
    }
    .dropdown-section-wrapper {
      display: grid;
      grid-template-rows: 0fr;
      overflow: hidden;
      transition: grid-template-rows 0.35s ease;
    }
    .dropdown-section-wrapper.open {
      grid-template-rows: 1fr;
      padding-top: 10px;
    }
    .dropdown-section-inner {
      overflow: hidden;
    }
    .dropdown-section-switch {
      margin-left: 10px;
    }
  `;
}

// register elements and custom card
customElements.define("wanas-card", WanasCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "wanas-card",
  name: "Wanas Card",
  description: "",
  preview: true,
  documentationURL: "https://github.com/micpub/homeassistant-wanas",
});
