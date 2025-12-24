const el = (tag, attrs = {}, children = []) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2).toLowerCase(), v);
    else if (v !== undefined && v !== null) node.setAttribute(k, String(v));
  }
  for (const child of children) {
    if (child === null || child === undefined) continue;
    node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
  }
  return node;
};

const getTheme = () => {
  try {
    const t = localStorage.getItem("lb_theme");
    return t === "light" ? "light" : "dark";
  } catch {
    return "dark";
  }
};

const applyTheme = (theme) => {
  document.documentElement.classList.toggle("dark", theme === "dark");
};

const setTheme = (theme) => {
  try {
    localStorage.setItem("lb_theme", theme);
  } catch {}
  applyTheme(theme);
};

const WEATHER_ZIP_STORAGE_KEY = "lb_weather_zip";
const LAST_SELECTED_LOAD_STORAGE_KEY = "lb_last_selected_load_id";
const GREENLIGHT_DEFAULTS_STORAGE_KEY = "lb_greenlight_defaults";
const FILTER_DEFAULTS_STORAGE_KEY = "lb_filter_defaults";
const UI_PREFS_STORAGE_KEY = "lb_ui_prefs";

const DEFAULT_UI_PREFS = {
  show_greenlight_ticker: true,
  show_news_ticker: true,
  show_sidebar: true,
  greenlight_full_row: false,
};

const getUiPrefs = () => {
  try {
    const raw = localStorage.getItem(UI_PREFS_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
};

const setUiPrefs = (prefs) => {
  try {
    localStorage.setItem(UI_PREFS_STORAGE_KEY, JSON.stringify(prefs ?? {}));
  } catch {}
};

const applyUiPrefsToShell = () => {
  const greenlightTicker = document.getElementById("greenlight-ticker");
  if (greenlightTicker) {
    greenlightTicker.style.display = state.uiPrefs.show_greenlight_ticker ? "" : "none";
  }

  const newsTicker = document.getElementById("news-ticker");
  if (newsTicker) {
    newsTicker.style.display = state.uiPrefs.show_news_ticker ? "" : "none";
  }

  // The body reserves space for the bottom ticker. If it's hidden, drop the padding.
  if (document.body) {
    document.body.classList.toggle("pb-24", !!state.uiPrefs.show_news_ticker);
  }
};

const getWeatherZip = () => {
  try {
    const z = String(localStorage.getItem(WEATHER_ZIP_STORAGE_KEY) || "").trim();
    return z;
  } catch {
    return "";
  }
};

const setWeatherZip = (zip) => {
  const z = String(zip ?? "").trim();
  try {
    if (!z) localStorage.removeItem(WEATHER_ZIP_STORAGE_KEY);
    else localStorage.setItem(WEATHER_ZIP_STORAGE_KEY, z);
  } catch {}
};

const getLastSelectedLoadId = () => {
  try {
    const v = String(localStorage.getItem(LAST_SELECTED_LOAD_STORAGE_KEY) || "").trim();
    return v;
  } catch {
    return "";
  }
};

const setLastSelectedLoadId = (loadId) => {
  const v = String(loadId || "").trim();
  try {
    if (!v) localStorage.removeItem(LAST_SELECTED_LOAD_STORAGE_KEY);
    else localStorage.setItem(LAST_SELECTED_LOAD_STORAGE_KEY, v);
  } catch {}
  state.lastSelectedLoadId = v;
};

const getGreenLightDefaults = () => {
  try {
    const raw = localStorage.getItem(GREENLIGHT_DEFAULTS_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
};

const setGreenLightDefaults = (prefs) => {
  try {
    localStorage.setItem(GREENLIGHT_DEFAULTS_STORAGE_KEY, JSON.stringify(prefs ?? {}));
  } catch {}
};

const clearGreenLightDefaults = () => {
  try {
    localStorage.removeItem(GREENLIGHT_DEFAULTS_STORAGE_KEY);
  } catch {}
};

const getFilterDefaults = () => {
  try {
    const raw = localStorage.getItem(FILTER_DEFAULTS_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === "object" ? parsed : null;
  } catch {
    return null;
  }
};

const setFilterDefaults = (query) => {
  try {
    localStorage.setItem(FILTER_DEFAULTS_STORAGE_KEY, JSON.stringify(query ?? {}));
  } catch {}
};

const clearFilterDefaults = () => {
  try {
    localStorage.removeItem(FILTER_DEFAULTS_STORAGE_KEY);
  } catch {}
};

const appBasePath = (() => {
  // Compute a stable base like "/" or "/FreightLens/".
  // This lets the app run when mounted under a subpath (cPanel Passenger Application URL).
  let p = window.location.pathname || "/";
  if (!p.endsWith("/")) p = `${p}/`;
  return p;
})();

const toAppUrl = (path) => {
  const raw = String(path ?? "");
  if (!raw) return raw;
  if (/^https?:\/\//i.test(raw)) return raw;

  const normalized = raw.startsWith("/") ? raw.slice(1) : raw;
  const base = appBasePath.endsWith("/") ? appBasePath : `${appBasePath}/`;
  return `${base}${normalized}`;
};

const apiGet = async (path) => {
  const res = await fetch(toAppUrl(path));
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return await res.json();
};

const apiPostJson = async (path, body) => {
  const res = await fetch(toAppUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return await res.json();
};

const apiPostFileBytes = async (path, file) => {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const res = await fetch(toAppUrl(path), {
    method: "POST",
    headers: { "Content-Type": "application/octet-stream" },
    body: bytes,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `${res.status} ${res.statusText}`);
  }
  return await res.json();
};

const fmtMoney = (n) => `$${Number(n).toFixed(0)}`;
const fmtNum = (n, digits = 0) => Number(n).toFixed(digits);

const weatherEmojiForText = (text, { isDay } = {}) => {
  const t = String(text || "").toLowerCase();
  if (!t) return "";

  // Order matters: check more specific / severe conditions first.
  if (t.includes("tornado")) return "🌪️";
  if (t.includes("thunder") || t.includes("t-storm") || t.includes("tstorm") || t.includes("storm")) return "⛈️";
  if (t.includes("hail")) return "🌨️";
  if (t.includes("sleet") || t.includes("freezing rain") || t.includes("ice")) return "🧊";
  if (t.includes("snow") || t.includes("flurr")) return "🌨️";
  if (t.includes("rain") || t.includes("shower") || t.includes("drizzle")) return "🌧️";
  // Some clients (older Android/Windows fonts) render 🌫️ as a missing-glyph box.
  // Use ☁️ as the fallback so the UI stays readable.
  if (t.includes("fog") || t.includes("mist")) return "☁️";
  if (t.includes("smoke") || t.includes("haze") || t.includes("dust") || t.includes("sand")) return "☁️";
  if (t.includes("wind")) return "💨";

  // Cloud coverage
  if (t.includes("overcast")) return "☁️";
  if (t.includes("cloud")) return "⛅";

  // Clear / fair
  if (t.includes("clear") || t.includes("sunny") || t.includes("fair")) return isDay === false ? "🌙" : "☀️";

  return "";
};

// Day/night helper (no API calls): compute whether the sun is above the horizon.
// Used to render ☀️ vs 🌙 for moderate temperatures.
const isSunUpAt = (latDeg, lonDeg, when) => {
  const lat = Number(latDeg);
  const lon = Number(lonDeg);
  const date = when instanceof Date ? when : new Date(when);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return null;
  if (!(date instanceof Date) || Number.isNaN(date.valueOf())) return null;

  // Julian day (UTC)
  const jd = date.valueOf() / 86400000 + 2440587.5;
  const n = jd - 2451545.0;

  const deg2rad = (d) => (d * Math.PI) / 180;
  const rad2deg = (r) => (r * 180) / Math.PI;

  // Solar coordinates (approx)
  const L = (280.460 + 0.9856474 * n) % 360; // mean longitude
  const g = (357.528 + 0.9856003 * n) % 360; // mean anomaly
  const lambda = L + 1.915 * Math.sin(deg2rad(g)) + 0.020 * Math.sin(deg2rad(2 * g)); // ecliptic lon
  const epsilon = 23.439 - 0.0000004 * n; // obliquity

  const sinLambda = Math.sin(deg2rad(lambda));
  const cosLambda = Math.cos(deg2rad(lambda));
  const cosEps = Math.cos(deg2rad(epsilon));
  const sinEps = Math.sin(deg2rad(epsilon));

  const alpha = rad2deg(Math.atan2(cosEps * sinLambda, cosLambda)); // RA deg
  const delta = Math.asin(sinEps * sinLambda); // declination rad

  // Greenwich mean sidereal time (deg)
  const theta = (280.46061837 + 360.98564736629 * n) % 360;
  // Local hour angle (deg)
  const H = deg2rad(((theta + lon - alpha + 540) % 360) - 180);

  const latRad = deg2rad(lat);
  const altitude = Math.asin(
    Math.sin(latRad) * Math.sin(delta) + Math.cos(latRad) * Math.cos(delta) * Math.cos(H)
  );

  return altitude > 0;
};

const tempClassForF = (tempF) => {
  if (tempF === null || tempF === undefined) return "";
  const f = Number(tempF);
  if (!Number.isFinite(f)) return "";
  if (f <= 34) return "text-sky-600 dark:text-sky-400";
  if (f >= 80) return "text-red-600 dark:text-red-400";
  return "";
};

const renderTempLabel = (value, unit, opts = {}) => {
  if (value === null || value === undefined) return el("span", {}, [""]);
  const n = Number(value);
  if (!Number.isFinite(n)) return el("span", {}, [""]);

  const u = String(unit || "").toUpperCase();
  const fForColor = u === "C" ? (n * 9) / 5 + 32 : n;
  const cls = tempClassForF(fForColor);

  const showSnowflake = Number.isFinite(fForColor) && fForColor <= 34;
  const showThermometer = Number.isFinite(fForColor) && fForColor >= 80;

  return el("span", { class: cls }, [
    `${Math.round(n)}°${u || ""}`,
    showSnowflake ? " ❄️" : "",
    showThermometer ? " 🌡️" : "",
  ]);
};

const getHashRoute = () => {
  const h = window.location.hash || "#/";
  const parts = h.replace(/^#\//, "").split("/");
  return { page: parts[0] || "", id: parts[1] || null };
};

const DEFAULT_QUERY = {
  q: "",
  equipment: "",
  hazmat: "",
  weight_min: "",
  weight_max: "",
  deadhead_max: "",
  rpm_min: "",
  broker_rating_min: "",
  detention: "",
  multi_stop: "",
  lane_history: "",
  sort: "composite",
};

const SORT_OPTIONS = [
  { value: "composite", label: "Composite" },
  { value: "score_desc", label: "Score (desc)" },
  { value: "rpm_desc", label: "$ / mi (desc)" },
  { value: "pickup_soonest", label: "Pickup (soonest)" },
  { value: "deadhead_asc", label: "Deadhead (asc)" },
  { value: "broker_desc", label: "Broker rating (desc)" },
];

const DEFAULT_PREFS = {
  rpm_min: "",
  equipment: "",
  weight_max: "",
  weight_min: "",
  detention: "",
  broker_rating_min: "",
  deadhead_max: "",
  hazmat: "",
  multi_stop: "",
  greenlight_sort: "",
};

const state = {
  filtersOpen: false,
  terminalPanelOpen: false,
  ui: {
    collapseForecast: true,
    collapseAlerts: true,
    collapseRouteCast: false,
  },
  uiPrefs: { ...DEFAULT_UI_PREFS },
  query: { ...DEFAULT_QUERY },
  prefsDraft: { ...DEFAULT_PREFS },
  prefs: { ...DEFAULT_PREFS },
  latestLoads: [],
  scoredLoads: {},      // Map of load_id -> score data
  watchlist: new Set(), // Set of watched load IDs
  filterPresets: [],    // Saved filter presets

  watchlistSweep: {
    loading: false,
    error: "",
    items: [], // [{ load_id, score, route }]
  },

  lastSelectedLoadId: "",

  routecast: {
    loadId: "",
    data: null,
    error: "",
    fetching: false,
    fetchedAtMs: 0,
  },

  weather: {
    zip: "",
    zipDraft: "",
    forecast: null,
    alerts: null,
    forecastError: "",
    alertsError: "",
    fetchingForecast: false,
    fetchingAlerts: false,
    fetchedAtForecastMs: 0,
    fetchedAtAlertsMs: 0,
  },
  alertRules: [],
  triggeredAlerts: [],
};

const WEATHER_FORECAST_TTL_MS = 10 * 60 * 1000;
const WEATHER_ALERTS_TTL_MS = 2 * 60 * 1000;
const ROUTECAST_TTL_MS = 2 * 60 * 1000;

const _normalizeZip = (raw) => {
  const s = String(raw ?? "").trim();
  const digits = s.replace(/\D+/g, "");
  return digits.length >= 5 ? digits.slice(0, 5) : digits;
};

const fetchWeatherForecast = async () => {
  const zip = _normalizeZip(state.weather.zip);
  if (!zip || zip.length !== 5) return;
  if (state.weather.fetchingForecast) return;

  const now = Date.now();
  if (state.weather.forecast && state.weather.fetchedAtForecastMs && now - state.weather.fetchedAtForecastMs < WEATHER_FORECAST_TTL_MS) {
    return;
  }

  state.weather.fetchingForecast = true;
  state.weather.forecastError = "";
  try {
    const payload = await apiGet(`/api/weather/forecast?zip=${encodeURIComponent(zip)}`);
    // If ZIP changed while in-flight, ignore.
    if (_normalizeZip(state.weather.zip) !== zip) return;
    state.weather.forecast = payload;
    state.weather.fetchedAtForecastMs = Date.now();
  } catch (err) {
    state.weather.forecast = null;
    state.weather.forecastError = err?.message || String(err);
  } finally {
    state.weather.fetchingForecast = false;
    render();
  }
};

const fetchWeatherAlerts = async () => {
  const zip = _normalizeZip(state.weather.zip);
  if (!zip || zip.length !== 5) return;
  if (state.weather.fetchingAlerts) return;

  const now = Date.now();
  if (state.weather.alerts && state.weather.fetchedAtAlertsMs && now - state.weather.fetchedAtAlertsMs < WEATHER_ALERTS_TTL_MS) {
    return;
  }

  state.weather.fetchingAlerts = true;
  state.weather.alertsError = "";
  try {
    const payload = await apiGet(`/api/weather/alerts?zip=${encodeURIComponent(zip)}`);
    if (_normalizeZip(state.weather.zip) !== zip) return;
    state.weather.alerts = payload;
    state.weather.fetchedAtAlertsMs = Date.now();
  } catch (err) {
    state.weather.alerts = null;
    state.weather.alertsError = err?.message || String(err);
  } finally {
    state.weather.fetchingAlerts = false;
    render();
  }
};

const renderWeatherSidebar = () => {
  const zip = _normalizeZip(state.weather.zip);
  const zipOk = zip.length === 5;

  // Kick off refresh in the background when on list view.
  if (zipOk) {
    fetchWeatherForecast().catch((e) => console.error("weather forecast fetch failed", e));
    fetchWeatherAlerts().catch((e) => console.error("weather alerts fetch failed", e));
  }

  const applyZipFromPrompt = () => {
    const current = _normalizeZip(state.weather.zip);
    const raw = window.prompt("Enter 5-digit ZIP code", current || "");
    if (raw === null) return;
    const next = _normalizeZip(raw);
    if (next.length !== 5) return;

    setWeatherZip(next);
    state.weather.zip = next;
    state.weather.zipDraft = next;
    state.weather.forecast = null;
    state.weather.alerts = null;
    state.weather.forecastError = "";
    state.weather.alertsError = "";
    state.weather.fetchedAtForecastMs = 0;
    state.weather.fetchedAtAlertsMs = 0;

    fetchWeatherForecast().catch((e) => console.error("weather forecast fetch failed", e));
    fetchWeatherAlerts().catch((e) => console.error("weather alerts fetch failed", e));
    render();
  };

  const card = (
    title,
    bodyChildren,
    titleClass = "",
    collapseKey = null,
    { showZipChange, locationLabel, alwaysChildren } = {}
  ) => {
    const isCollapsed = collapseKey ? !!state.ui[collapseKey] : false;
    const toggleBtn = collapseKey
      ? el(
          "button",
          {
            class:
              "rounded-md border border-sky-500 bg-sky-50 px-2 py-1 text-xs font-medium text-sky-700 hover:bg-sky-100 dark:border-sky-600 dark:bg-sky-900/30 dark:text-sky-400 dark:hover:bg-sky-900/40",
            title: isCollapsed ? "Show" : "Hide",
            "aria-label": isCollapsed ? "Show" : "Hide",
            onclick: () => {
              state.ui[collapseKey] = !state.ui[collapseKey];
              render();
            },
          },
          [isCollapsed ? "Show" : "Hide"]
        )
      : null;

    const changeZipBtn = showZipChange
      ? el(
          "button",
          {
            class:
              "rounded-md border border-sky-500 bg-sky-50 px-2 py-1 text-xs font-medium text-sky-700 hover:bg-sky-100 dark:border-sky-600 dark:bg-sky-900/30 dark:text-sky-400 dark:hover:bg-sky-900/40",
            title: "Change ZIP code",
            "aria-label": "Change ZIP code",
            onclick: () => applyZipFromPrompt(),
          },
          ["Change"]
        )
      : null;

    const subRow =
      !isCollapsed && changeZipBtn
        ? el(
            "div",
            { class: "flex items-start justify-between gap-2 pt-2" },
            [
              locationLabel
                ? el("div", { class: "text-xs font-medium text-slate-700 dark:text-slate-300" }, [locationLabel])
                : el("div", { class: "text-xs" }, [""]),
              changeZipBtn,
            ]
          )
        : null;

    return el(
      "div",
      { class: "rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900" },
      [
        el("div", { class: "flex items-start justify-between gap-2" }, [
          el("div", { class: `text-sm font-semibold ${titleClass}`.trim() }, [title]),
          toggleBtn,
        ].filter(Boolean)),
        subRow,
        ...((alwaysChildren && Array.isArray(alwaysChildren)) ? alwaysChildren : []),
        ...(!isCollapsed ? bodyChildren : []),
      ]
    );
  };

  const settingsPrompt = el("div", { class: "pt-1 text-xs text-slate-600 dark:text-slate-400" }, [
    "Set a 5-digit ZIP in ",
    el("a", { href: "/#/settings", class: "underline" }, ["Settings"]),
    ".",
  ]);

  // Forecast widget
  const forecastBody = zipOk ? [] : [settingsPrompt];
  const forecastAlways = [];
  let forecastLocationLabel = "";
  if (zipOk && state.weather.fetchingForecast) {
    forecastAlways.push(el("div", { class: "pt-2 text-xs text-slate-600 dark:text-slate-400" }, ["Loading forecast…"]));
  } else if (zipOk && state.weather.forecastError) {
    forecastAlways.push(el("div", { class: "pt-2 text-xs text-red-600 dark:text-red-400" }, ["Forecast unavailable."]));
  } else if (zipOk && state.weather.forecast?.forecast?.periods?.length) {
    const label = state.weather.forecast.location;
    if (label) forecastLocationLabel = label;
    const periods = state.weather.forecast.forecast.periods.slice(0, 4);

    // Keep a compact "Current Conditions" block visible even when collapsed.
    const current = periods[0];
    if (current) {
      const emoji = weatherEmojiForText(current.shortForecast, { isDay: current.isDaytime === false ? false : true });
      forecastAlways.push(
        el("div", { class: "pt-2" }, [
          el("div", { class: "flex items-baseline justify-between gap-2 text-xs" }, [
            el("div", { class: "font-semibold text-slate-600 dark:text-slate-400" }, ["Current Conditions"]),
            el("div", { class: "text-slate-700 dark:text-slate-300" }, [
              renderTempLabel(current.temperature, current.temperatureUnit, { isDay: !!current.isDaytime }),
            ]),
          ]),
          el("div", { class: "pt-1 text-xs text-slate-600 dark:text-slate-400" }, [
            `${emoji}${emoji && current.shortForecast ? " " : ""}${current.shortForecast || ""}`,
          ]),
        ])
      );
    }

    for (const p of periods) {
      forecastBody.push(
        el("div", { class: "pt-2 text-xs" }, [
          el("div", { class: "flex items-baseline justify-between gap-2" }, [
            el("div", { class: "font-semibold text-slate-800 dark:text-slate-200" }, [p.name || ""]),
            el("div", { class: "text-slate-700 dark:text-slate-300" }, [
              renderTempLabel(p.temperature, p.temperatureUnit, { isDay: !!p.isDaytime }),
            ]),
          ]),
          el("div", { class: "text-slate-600 dark:text-slate-400" }, [
            `${weatherEmojiForText(p.shortForecast, { isDay: !!p.isDaytime })}${p.shortForecast ? " " : ""}${p.shortForecast || ""}`,
          ]),
        ])
      );
    }
  }

  if (!zipOk) {
    // Keep the settings prompt visible even when collapsed.
    forecastAlways.push(settingsPrompt.cloneNode(true));
  }

  // Alerts widget
  const alertsBody = zipOk ? [] : [settingsPrompt.cloneNode(true)];
  let alertsLocationLabel = "";
  let alertsTitle = "Severe Weather Alerts";
  let alertsTitleClass = "text-red-600 dark:text-red-400";
  if (zipOk && state.weather.fetchingAlerts) {
    alertsBody.push(el("div", { class: "pt-2 text-xs text-slate-600 dark:text-slate-400" }, ["Loading alerts…"]));
  } else if (zipOk && state.weather.alertsError) {
    alertsBody.push(el("div", { class: "pt-2 text-xs text-red-600 dark:text-red-400" }, ["Alerts unavailable."]));
  } else if (zipOk) {
    const alertsLabel = state.weather.alerts?.location;
    if (alertsLabel) alertsLocationLabel = alertsLabel;
    const items = state.weather.alerts?.alerts?.alerts || [];
    const hasAlerts = items.length > 0;
    if (hasAlerts) {
      alertsTitle = el(
        "span",
        { class: "alert-pill alert-flash-text" },
        ["Severe Weather Alerts"]
      );
      alertsTitleClass = "";
    }
    if (!items.length) {
      alertsBody.push(el("div", { class: "pt-2 text-xs text-slate-600 dark:text-slate-400" }, ["No active alerts."]));
    } else {
      for (const a of items.slice(0, 3)) {
        alertsBody.push(
          el("div", { class: "pt-2 text-xs" }, [
            el("div", { class: "font-semibold text-slate-800 dark:text-slate-200" }, [a.event || "Alert"]),
            el("div", { class: "text-slate-600 dark:text-slate-400" }, [a.headline || ""]),
          ])
        );
      }
    }
  }

  const forecastWidget = card(
    "Weather Forecast",
    forecastBody,
    "text-sky-600 dark:text-sky-400",
    "collapseForecast",
    { showZipChange: true, locationLabel: forecastLocationLabel, alwaysChildren: forecastAlways }
  );
  const alertsWidget = card(
    alertsTitle,
    alertsBody,
    alertsTitleClass,
    "collapseAlerts",
    { showZipChange: true, locationLabel: alertsLocationLabel }
  );

  // RouteCast (last selected load) lives under the weather widgets.
  const routecastWidget = renderRouteCastWidget(state.lastSelectedLoadId, { compact: true });

  return el("div", { class: "space-y-3 lg:w-80 lg:flex-shrink-0 lg:sticky lg:top-16 lg:self-start" }, [
    routecastWidget,
    alertsWidget,
    forecastWidget,
  ]);
};

const fetchRouteCast = async (loadId) => {
  const id = String(loadId || "").trim();
  if (!id) return;
  if (state.routecast.fetching && state.routecast.loadId === id) return;

  const now = Date.now();
  if (
    state.routecast.loadId === id &&
    state.routecast.data &&
    state.routecast.fetchedAtMs &&
    now - state.routecast.fetchedAtMs < ROUTECAST_TTL_MS
  ) {
    return;
  }

  state.routecast.fetching = true;
  state.routecast.error = "";
  state.routecast.loadId = id;
  try {
    const payload = await apiGet(`/api/loads/${encodeURIComponent(id)}/routecast`);
    if (state.routecast.loadId !== id) return;
    state.routecast.data = payload;
    state.routecast.fetchedAtMs = Date.now();
  } catch (err) {
    state.routecast.data = null;
    state.routecast.error = err?.message || String(err);
  } finally {
    state.routecast.fetching = false;
    render();
  }
};

const renderRouteCastWidget = (loadId, { compact, load } = { compact: false }) => {
  const id = String(loadId || "").trim();
  const isCollapsed = !!state.ui.collapseRouteCast;
  const rc = state.routecast.loadId === id ? state.routecast.data : null;
  const routeAlertCount =
    rc?.route_alerts?.count ?? rc?.route_alerts?.alerts?.length ?? 0;
  const hasRouteAlerts = routeAlertCount > 0;

  const jumpToLoadDetail = () => {
    if (!id) return;
    const route = getHashRoute();
    if (route.page === "load" && String(route.id || "") === id) return;
    setLastSelectedLoadId(id);
    window.location.hash = `#/load/${encodeURIComponent(id)}`;
  };

  const logoBlockChildren = [
    el("img", {
      src: toAppUrl("/static/images/rc_logo.png"),
      alt: "RouteCast",
      class: "h-14 w-auto object-contain",
    }),
    isCollapsed && hasRouteAlerts
      ? el(
          "div",
          { class: "pt-1 text-xs font-semibold text-red-600 dark:text-red-400" },
          ["Alerts exist on route"]
        )
      : null,
  ];

  const titleRow = el(
    "div",
    { class: "flex items-center justify-between gap-2" },
    [
      el(
        "div",
        {
          class: `flex flex-col items-start gap-1${id ? " cursor-pointer" : ""}`,
          title: id ? "Open load detail" : "RouteCast",
          onclick: () => {
            if (id) jumpToLoadDetail();
          },
        },
        logoBlockChildren
      ),
      el(
        "button",
        {
          class:
            "rounded-md border border-sky-500 bg-sky-50 px-2 py-1 text-xs font-medium text-sky-700 hover:bg-sky-100 dark:border-sky-600 dark:bg-sky-900/30 dark:text-sky-400 dark:hover:bg-sky-900/40",
          title: isCollapsed ? "Show" : "Hide",
          "aria-label": isCollapsed ? "Show" : "Hide",
          onclick: () => {
            state.ui.collapseRouteCast = !state.ui.collapseRouteCast;
            render();
          },
        },
        [isCollapsed ? "Show" : "Hide"]
      ),
    ]
  );

  const wrap = el(
    "div",
    {
      class:
        "rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900",
    },
    [titleRow]
  );

  if (isCollapsed) return wrap;

  const summaryLoad = load || state.latestLoads.find((l) => String(l?.id || "") === id) || null;
  if (id && summaryLoad) {
    const lane = `${summaryLoad.origin.city}, ${summaryLoad.origin.state} → ${summaryLoad.destination.city}, ${summaryLoad.destination.state}`;
    const rpm = summaryLoad.rpm !== null && summaryLoad.rpm !== undefined ? `$${fmtNum(summaryLoad.rpm, 2)}/mi` : "";
    const distance = summaryLoad.distance_miles !== null && summaryLoad.distance_miles !== undefined ? `${fmtNum(summaryLoad.distance_miles)} mi` : "";
    const deadhead = summaryLoad.deadhead_miles !== null && summaryLoad.deadhead_miles !== undefined ? `${fmtNum(summaryLoad.deadhead_miles)} dh` : "";
    const equipment = summaryLoad.equipment ? String(summaryLoad.equipment) : "";
    const metrics = [rpm, distance, deadhead, equipment].filter(Boolean).join(" • ");

    wrap.appendChild(
      el("div", { class: "pt-2" }, [
        el("div", { class: "text-xs font-semibold text-slate-800 dark:text-slate-200" }, [lane]),
        metrics
          ? el("div", { class: "pt-1 text-xs text-slate-600 dark:text-slate-400" }, [metrics])
          : null,
      ].filter(Boolean))
    );
  }

  if (!id) {
    wrap.appendChild(
      el("div", { class: "pt-2 text-xs text-slate-600 dark:text-slate-400" }, ["Select a load to see RouteCast."])
    );
    return wrap;
  }

  if (!state.routecast.fetching && (state.routecast.loadId !== id || (!state.routecast.data && !state.routecast.error))) {
    fetchRouteCast(id).catch((e) => console.error("routecast fetch failed", e));
  }

  if (state.routecast.fetching && state.routecast.loadId === id) {
    wrap.appendChild(el("div", { class: "pt-2 text-xs text-slate-600 dark:text-slate-400" }, ["Loading RouteCast…"]));
    return wrap;
  }

  if (state.routecast.error && state.routecast.loadId === id) {
    wrap.appendChild(
      el("div", { class: "pt-2 text-xs text-red-600 dark:text-red-400" }, ["Select a route to view RouteCast"])
    );
    return wrap;
  }

  if (!rc) {
    wrap.appendChild(el("div", { class: "pt-2 text-xs text-slate-600 dark:text-slate-400" }, ["RouteCast not available."]));
    return wrap;
  }

  const endpointBlock = (label, loc) => {
    const current = loc?.current;
    const line1 = `${loc.city}, ${loc.state}`;
    const when = current?.timestamp ? new Date(current.timestamp) : new Date();
    const isDay = isSunUpAt(loc?.lat, loc?.lon, when);
    let tempEl = null;
    if (current?.temperature_f !== null && current?.temperature_f !== undefined) {
      tempEl = renderTempLabel(current.temperature_f, "F", { isDay: isDay === null ? undefined : isDay });
    } else if (current?.temperature_c !== null && current?.temperature_c !== undefined) {
      tempEl = renderTempLabel(current.temperature_c, "C", { isDay: isDay === null ? undefined : isDay });
    }
    const text = current?.text || "";
    const emoji = weatherEmojiForText(text, { isDay: isDay === null ? undefined : isDay });
    return el("div", { class: compact ? "" : "pt-2" }, [
      el("div", { class: "text-xs font-semibold text-slate-600 dark:text-slate-400" }, [label]),
      el("div", { class: "pt-1 text-xs font-medium text-slate-800 dark:text-slate-200" }, [line1]),
      current
        ? el("div", { class: "pt-1 text-xs text-slate-600 dark:text-slate-400" }, [
            tempEl ? el("span", {}, [tempEl]) : null,
            tempEl && text ? " • " : "",
            `${emoji}${emoji && text ? " " : ""}${text}`,
          ].filter((x) => x !== null && x !== undefined && x !== ""))
        : el("div", { class: "pt-1 text-xs text-slate-600 dark:text-slate-400" }, ["Current conditions unavailable."]),
    ]);
  };

  wrap.appendChild(
    el(compact ? "div" : "div", { class: compact ? "pt-2 grid gap-2" : "pt-2 grid gap-2" }, [
      endpointBlock("Origin", rc.origin),
      endpointBlock("Destination", rc.destination),
    ])
  );

  const alerts = rc.route_alerts?.alerts || [];
  const alertCount = rc.route_alerts?.count ?? alerts.length;
  wrap.appendChild(el("div", { class: "pt-3 text-xs font-semibold text-slate-600 dark:text-slate-400" }, ["Route alerts"]));
  if (!alerts.length) {
    wrap.appendChild(el("div", { class: "pt-1 text-xs text-slate-600 dark:text-slate-400" }, ["No active alerts detected along the route."]));
  } else {
    wrap.appendChild(el("div", { class: "pt-1 text-xs text-slate-600 dark:text-slate-400" }, [`${alertCount} active alert(s)`]));
    for (const a of alerts.slice(0, compact ? 2 : 3)) {
      const label = a.event || "Alert";
      const sev = a.severity ? ` • ${a.severity}` : "";
      wrap.appendChild(el("div", { class: "pt-2 text-xs" }, [
        el("div", { class: "font-semibold text-slate-800 dark:text-slate-200" }, [`${label}${sev}`]),
        a.headline ? el("div", { class: "text-slate-600 dark:text-slate-400" }, [a.headline]) : null,
      ].filter(Boolean)));
    }
  }

  return wrap;
};

const NEWS_TICKER_REFRESH_MS = 5 * 60 * 1000;
const GREENLIGHT_TICKER_MAX = 6;
const newsTickerState = { items: [] };

// =============================================================================
// API Helpers for Terminal Workflows
// =============================================================================

const apiPut = async (path, body) => {
  const res = await fetch(toAppUrl(path), {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return await res.json();
};

const apiDelete = async (path) => {
  const res = await fetch(toAppUrl(path), { method: "DELETE" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return await res.json();
};

const fetchScoredLoads = async () => {
  try {
    const qs = buildQueryString();
    const res = await apiGet(`/api/loads/scored${qs}&limit=100`);
    state.scoredLoads = {};
    for (const item of res.loads || []) {
      state.scoredLoads[item.load.id] = {
        score: item.score,
        greenlight: item.greenlight,
        top_reasons: item.top_reasons || [],
        confidence: item.confidence,
      };
    }
  } catch (err) {
    console.error("Failed to fetch scored loads:", err);
  }
};

const fetchWatchlist = async () => {
  try {
    const res = await apiGet("/api/watchlist");
    state.watchlist = new Set((res.items || []).map((i) => i.load_id).filter(Boolean));
  } catch (err) {
    console.error("Failed to fetch watchlist:", err);
  }
};

const watchlistSummaryText = (count) =>
  count > 0
    ? `${count} load${count > 1 ? "s" : ""} watched. Toggle ☆ on any load card.`
    : "No loads watched yet. Click ☆ on a load card to add.";

const watchlistListBtnClass = (isWatched) =>
  `text-lg leading-none transition ${isWatched ? "text-amber-400" : "text-slate-400 hover:text-amber-400"}`;

const watchlistDetailBtnClass = (isWatched) =>
  `rounded-md px-3 py-2 text-sm font-medium ${
    isWatched
      ? "bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300"
      : "bg-slate-200 text-slate-700 dark:bg-slate-700 dark:text-slate-200"
  }`;

const updateWatchlistSummary = () => {
  const summary = document.querySelector("[data-watchlist-summary]");
  if (!summary) return;
  summary.textContent = watchlistSummaryText(state.watchlist.size);
};

const updateWatchlistButtons = (loadId) => {
  const isWatched = state.watchlist.has(loadId);
  const buttons = document.querySelectorAll(`button[data-watchlist-id="${loadId}"]`);
  buttons.forEach((btn) => {
    const variant = btn.getAttribute("data-watchlist-variant");
    if (variant === "detail") {
      btn.className = watchlistDetailBtnClass(isWatched);
      btn.textContent = isWatched ? "★ Watching" : "☆ Add to Watchlist";
      return;
    }
    btn.className = watchlistListBtnClass(isWatched);
    btn.setAttribute("title", isWatched ? "Remove from watchlist" : "Add to watchlist");
    btn.textContent = isWatched ? "★" : "☆";
  });
  updateWatchlistSummary();
};

const toggleWatchlist = async (loadId) => {
  try {
    if (state.watchlist.has(loadId)) {
      // Find and delete
      const res = await apiGet("/api/watchlist");
      const item = (res.items || []).find((i) => i.load_id === loadId);
      if (item) {
        await apiDelete(`/api/watchlist/${item.id}`);
        state.watchlist.delete(loadId);
      }
    } else {
      await apiPostJson("/api/watchlist", { item_type: "load", load_id: loadId });
      state.watchlist.add(loadId);
    }
    updateWatchlistButtons(loadId);
  } catch (err) {
    console.error("Failed to toggle watchlist:", err);
  }
};

const runWatchlistSweep = async () => {
  const ids = Array.from(state.watchlist || []).slice(0, 50);
  state.watchlistSweep.loading = true;
  state.watchlistSweep.error = "";
  state.watchlistSweep.items = [];
  render();

  if (ids.length === 0) {
    state.watchlistSweep.loading = false;
    render();
    return;
  }

  try {
    const scoreResults = await Promise.allSettled(
      ids.map(async (id) => {
        const scored = await apiGet(`/api/loads/${id}/score`);
        return { load_id: id, score: scored?.score };
      })
    );

    const scored = scoreResults
      .filter((r) => r.status === "fulfilled")
      .map((r) => r.value)
      .filter((x) => typeof x.score === "number" && Number.isFinite(x.score));

    const top = scored.sort((a, b) => b.score - a.score).slice(0, 5);

    const items = [];
    for (const t of top) {
      const existing = (state.latestLoads || []).find((l) => l.id === t.load_id) || null;
      let route = t.load_id;
      if (existing) {
        route = `${existing.origin.city}, ${existing.origin.state} → ${existing.destination.city}, ${existing.destination.state}`;
      } else {
        try {
          const load = await apiGet(`/api/loads/${t.load_id}`);
          route = `${load.origin.city}, ${load.origin.state} → ${load.destination.city}, ${load.destination.state}`;
        } catch {
          // Keep fallback route as the load ID.
        }
      }
      items.push({ load_id: t.load_id, score: t.score, route });
    }

    state.watchlistSweep.items = items;
  } catch (err) {
    console.error("Watchlist sweep failed:", err);
    state.watchlistSweep.error = err?.message || String(err);
  } finally {
    state.watchlistSweep.loading = false;
    render();
  }
};

const fetchFilterPresets = async () => {
  try {
    const res = await apiGet("/api/presets");
    state.filterPresets = res.presets || [];
  } catch (err) {
    console.error("Failed to fetch presets:", err);
  }
};
const fetchAlertRules = async () => {
  try {
    const res = await apiGet("/api/alerts");
    state.alertRules = res.rules || [];
  } catch (err) {
    console.error("Failed to fetch alert rules:", err);
    state.alertRules = [];
  }
};

const fetchTriggeredAlerts = async () => {
  try {
    const res = await apiGet("/api/alerts/triggered");
    state.triggeredAlerts = res.triggered || [];
  } catch (err) {
    console.error("Failed to fetch triggered alerts:", err);
    state.triggeredAlerts = [];
  }
};

const refreshAlerts = async () => {
  await fetchAlertRules();
  await fetchTriggeredAlerts();
};

const buildAlertConditionsFromFilters = () => {
  const conds = [];
  const q = state.query || {};

  const num = (v) => {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  };
  const boolFromStr = (v) => (v === "true" ? true : v === "false" ? false : null);

  if (String(q.q || "").trim()) conds.push({ field: "q", operator: "contains", value: String(q.q).trim() });
  if (String(q.equipment || "").trim()) conds.push({ field: "equipment", operator: "eq", value: String(q.equipment).trim() });

  const rpmMin = num(q.rpm_min);
  if (rpmMin !== null) conds.push({ field: "rpm", operator: "gte", value: rpmMin });

  const weightMin = num(q.weight_min);
  if (weightMin !== null) conds.push({ field: "weight_lbs", operator: "gte", value: weightMin });

  const weightMax = num(q.weight_max);
  if (weightMax !== null) conds.push({ field: "weight_lbs", operator: "lte", value: weightMax });

  const deadheadMax = num(q.deadhead_max);
  if (deadheadMax !== null) conds.push({ field: "deadhead_miles", operator: "lte", value: deadheadMax });

  const brokerMin = num(q.broker_rating_min);
  if (brokerMin !== null) conds.push({ field: "broker_rating", operator: "gte", value: brokerMin });

  const hazmat = boolFromStr(q.hazmat);
  if (hazmat !== null) conds.push({ field: "hazmat", operator: "eq", value: hazmat });

  const detention = boolFromStr(q.detention);
  if (detention !== null) conds.push({ field: "detention", operator: "eq", value: detention });

  const multiStop = boolFromStr(q.multi_stop);
  if (multiStop !== null) conds.push({ field: "multi_stop", operator: "eq", value: multiStop });

  const laneHistory = boolFromStr(q.lane_history);
  if (laneHistory !== null) conds.push({ field: "lane_history", operator: "eq", value: laneHistory });

  return conds;
};

const createAlertFromFilters = async (name) => {
  try {
    const conditions = buildAlertConditionsFromFilters();
    await apiPostJson("/api/alerts", { name, description: "From current filters", conditions, enabled: true });
    await refreshAlerts();
    render();
  } catch (err) {
    console.error("Failed to create alert:", err);
  }
};

const setAlertEnabled = async (ruleId, enabled) => {
  try {
    await apiPut(`/api/alerts/${ruleId}`, { enabled: !!enabled });
    await refreshAlerts();
    render();
  } catch (err) {
    console.error("Failed to update alert:", err);
  }
};

const deleteAlertRule = async (ruleId) => {
  try {
    await apiDelete(`/api/alerts/${ruleId}`);
    await refreshAlerts();
    render();
  } catch (err) {
    console.error("Failed to delete alert:", err);
  }
};

const saveFilterPreset = async (name) => {
  try {
    await apiPostJson("/api/presets", { name, filters: { ...state.query } });
    await fetchFilterPresets();
    render();
  } catch (err) {
    console.error("Failed to save preset:", err);
  }
};

const loadFilterPreset = (preset) => {
  state.query = { ...state.query, ...preset.filters };
  render();
};

const deleteFilterPreset = async (presetId) => {
  try {
    await apiDelete(`/api/presets/${presetId}`);
    await fetchFilterPresets();
    render();
  } catch (err) {
    console.error("Failed to delete preset:", err);
  }
};

const parseOptionalNumber = (raw) => {
  const s = String(raw ?? "").trim();
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
};

const _parseOptionalBool = (raw) => {
  if (raw === "true") return true;
  if (raw === "false") return false;
  return null;
};

const buildPreferencesPayload = (prefs) => ({
  min_rpm: parseOptionalNumber(prefs.rpm_min),
  max_deadhead_miles: parseOptionalNumber(prefs.deadhead_max),
  max_weight_lbs: parseOptionalNumber(prefs.weight_max),
  min_weight_lbs: parseOptionalNumber(prefs.weight_min),
  min_broker_rating: parseOptionalNumber(prefs.broker_rating_min),
  equipment_types: prefs.equipment ? [prefs.equipment] : null,
  detention: _parseOptionalBool(prefs.detention),
  hazmat: _parseOptionalBool(prefs.hazmat),
  multi_stop: _parseOptionalBool(prefs.multi_stop),
});

const syncPreferences = async (prefs) => {
  try {
    await apiPut("/api/preferences", buildPreferencesPayload(prefs));
  } catch (err) {
    console.error("Failed to sync preferences:", err);
  }
};

const prefStatus = (load) => {
  const rpmMin = parseOptionalNumber(state.prefs.rpm_min);
  const weightMax = parseOptionalNumber(state.prefs.weight_max);
  const weightMin = parseOptionalNumber(state.prefs.weight_min);
  const brokerRatingMin = parseOptionalNumber(state.prefs.broker_rating_min);
  const deadheadMax = parseOptionalNumber(state.prefs.deadhead_max);
  const hazmatPref = state.prefs.hazmat;
  const multiStopPref = state.prefs.multi_stop;

  const rpmOk = rpmMin === null ? null : load.rpm >= rpmMin;
  const equipmentOk = !state.prefs.equipment ? null : load.equipment === state.prefs.equipment;
  const weightOk = weightMax === null ? null : load.weight_lbs <= weightMax;
  const weightMinOk = weightMin === null ? null : load.weight_lbs >= weightMin;
  const brokerOk = brokerRatingMin === null ? null : load.broker.rating >= brokerRatingMin;
  const deadheadOk = deadheadMax === null ? null : load.deadhead_miles <= deadheadMax;

  let detentionOk = null;
  if (state.prefs.detention === "true") detentionOk = !!load.detention;
  else if (state.prefs.detention === "false") detentionOk = !load.detention;

  let hazmatOk = null;
  if (hazmatPref === "true") hazmatOk = !!load.hazmat;
  else if (hazmatPref === "false") hazmatOk = !load.hazmat;

  let multiStopOk = null;
  if (multiStopPref === "true") multiStopOk = !!load.multi_stop;
  else if (multiStopPref === "false") multiStopOk = !load.multi_stop;

  return {
    rpmOk,
    equipmentOk,
    weightOk,
    weightMinOk,
    detentionOk,
    brokerOk,
    deadheadOk,
    hazmatOk,
    multiStopOk,
  };
};

const greenlightGaps = (load) => {
  const gaps = [];
  const status = prefStatus(load);
  const prefs = state.prefs;

  if (parseOptionalNumber(prefs.rpm_min) !== null && status.rpmOk === false) gaps.push("$ / mi min");
  if (parseOptionalNumber(prefs.weight_max) !== null && status.weightOk === false) gaps.push("Weight max");
  if (parseOptionalNumber(prefs.weight_min) !== null && status.weightMinOk === false) gaps.push("Weight min");
  if (prefs.equipment && status.equipmentOk === false) gaps.push("Equipment");
  if (prefs.detention && status.detentionOk === false) gaps.push("Detention");
  if (parseOptionalNumber(prefs.broker_rating_min) !== null && status.brokerOk === false) gaps.push("Broker rating");
  if (parseOptionalNumber(prefs.deadhead_max) !== null && status.deadheadOk === false) gaps.push("Deadhead");
  if ((prefs.hazmat === "true" || prefs.hazmat === "false") && status.hazmatOk === false) gaps.push("Hazmat pref");
  if ((prefs.multi_stop === "true" || prefs.multi_stop === "false") && status.multiStopOk === false) gaps.push("Multi-stop pref");

  return gaps;
};

const buildScoreTooltip = (scoreValue, greenlightOk, load) => {
  const base = `Score: ${scoreValue.toFixed(1)}/100`;
  if (greenlightOk) return `${base} • GreenLight`;

  if (!hasActivePrefs()) return `${base} • Scored (set GreenLight prefs to enable endorsement)`;

  const gaps = greenlightGaps(load);
  if (gaps.length) return `${base} • Scored but not GreenLight: missing ${gaps.join(", ")}`;
  return `${base} • Scored but not GreenLight`;
};

const isGreenLight = (load) => {
  const prefs = state.prefs;
  const rpmMin = parseOptionalNumber(prefs.rpm_min);
  const weightMax = parseOptionalNumber(prefs.weight_max);
  const weightMin = parseOptionalNumber(prefs.weight_min);
  const brokerRatingMin = parseOptionalNumber(prefs.broker_rating_min);
  const deadheadMax = parseOptionalNumber(prefs.deadhead_max);
  const equipmentActive = !!prefs.equipment;
  const detentionActive = prefs.detention === "true" || prefs.detention === "false";
  const hazmatActive = prefs.hazmat === "true" || prefs.hazmat === "false";
  const brokerActive = brokerRatingMin !== null;
  const deadheadActive = deadheadMax !== null;
  const weightMinActive = weightMin !== null;
  const multiStopActive = prefs.multi_stop === "true" || prefs.multi_stop === "false";

  // When no preference is set we should not auto-signal a perfect green light.
  // Returning true here causes every load to appear greenlit even with an empty preference set.
  if (
    rpmMin === null &&
    weightMax === null &&
    !equipmentActive &&
    !detentionActive &&
    !brokerActive &&
    !deadheadActive &&
    !weightMinActive &&
    !hazmatActive &&
    !multiStopActive
  )
    return false;

  const {
    rpmOk,
    equipmentOk,
    weightOk,
    weightMinOk,
    detentionOk,
    brokerOk,
    deadheadOk,
    hazmatOk,
    multiStopOk,
  } = prefStatus(load);
  const checks = [
    rpmMin === null ? null : rpmOk,
    equipmentActive ? equipmentOk : null,
    weightMax === null ? null : weightOk,
    weightMinActive ? weightMinOk : null,
    detentionActive ? detentionOk : null,
    brokerActive ? brokerOk : null,
    deadheadActive ? deadheadOk : null,
    hazmatActive ? hazmatOk : null,
    multiStopActive ? multiStopOk : null,
  ];
  return checks.every((v) => v === null || v === true);
};

const hasActivePrefs = () => {
  const prefs = state.prefs;
  return (
    String(prefs.rpm_min ?? "").trim() !== "" ||
    String(prefs.weight_max ?? "").trim() !== "" ||
    String(prefs.weight_min ?? "").trim() !== "" ||
    String(prefs.equipment ?? "").trim() !== "" ||
    prefs.detention === "true" ||
    prefs.detention === "false" ||
    String(prefs.broker_rating_min ?? "").trim() !== "" ||
    String(prefs.deadhead_max ?? "").trim() !== "" ||
    prefs.hazmat === "true" ||
    prefs.hazmat === "false" ||
    prefs.multi_stop === "true" ||
    prefs.multi_stop === "false"
  );
};

const buildQueryString = () => {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(state.query)) {
    if (v === "" || v === null || v === undefined) continue;
    params.set(k, v);
  }
  return params.toString() ? `?${params.toString()}` : "";
};

const setMeta = async () => {
  try {
    const m = await apiGet("/api/meta");
    document.getElementById("meta").textContent = `${m.source} • ${m.count} loads`;
  } catch {
    document.getElementById("meta").textContent = "";
  }
};

const renderScoreLegend = () => {
  const pill = (label, cls) =>
    el("span", { class: `inline-flex items-center rounded-full px-2 py-0.5 text-[0.65rem] font-semibold ${cls}` }, [label]);

  const greenlightLegendCls =
    "border-emerald-400 bg-emerald-50/80 text-slate-900 shadow-[0_0_0_1px_rgba(16,185,129,0.45)] dark:border-emerald-500 dark:bg-emerald-900/30 dark:text-emerald-50";
  return el("div", { class: "flex flex-wrap items-center justify-end gap-2 text-[0.7rem]" }, [
    el("span", { class: "text-slate-500 dark:text-slate-400 font-semibold uppercase tracking-wide" }, ["Legend:"]),
    pill("GreenLight", greenlightLegendCls),
    pill("Scored", "bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-100"),
    pill("Warning", "border border-amber-300 bg-gradient-to-r from-yellow-200 via-amber-200 to-red-200 text-red-900"),
  ]);
};

const renderFatalError = (root, title, detail) => {
  const box = el(
    "div",
    {
      class:
        "mt-3 rounded-lg border border-slate-200 bg-white p-3 text-sm text-slate-800 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200",
    },
    [
      el("div", { class: "font-semibold" }, [title || "Something went wrong"]),
      detail ? el("div", { class: "pt-1 text-xs text-slate-600 dark:text-slate-400" }, [String(detail)]) : null,
      el("div", { class: "pt-3" }, [
        el("a", { href: "/#/", class: "text-sm font-medium underline" }, ["Back to loads"]),
      ]),
    ].filter(Boolean)
  );
  root.appendChild(box);
};

const render = async () => {
  const root = document.getElementById("app");
  root.innerHTML = "";

  try {
    // Keep shell-level UI (tickers/padding) in sync with settings.
    applyUiPrefsToShell();
    const route = getHashRoute();
    if (route.page === "settings") return await renderSettings(root);
    if (route.page === "load" && route.id) return await renderDetail(root, route.id);
    return await renderList(root);
  } catch (err) {
    console.error("Render failed:", err);
    renderFatalError(root, "Render failed", err?.message || err);
  }
};

const renderList = async (root) => {
  const layout = el("div", { class: "lg:flex lg:gap-4" });
  const sidebar = state.uiPrefs.show_sidebar ? renderWeatherSidebar() : null;
  const main = el("div", { class: "min-w-0 flex-1" });

  const top = el("div", { class: "space-y-3" });

  const searchRow = el("div", { class: "flex gap-2" }, [
    el("input", {
      class:
        "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400 dark:border-slate-800 dark:bg-slate-900",
      placeholder: "Search origin/destination/commodity",
      value: state.query.q,
      oninput: (e) => {
        state.query.q = e.target.value;
      },
    }),
    el(
      "button",
      {
        class:
          "shrink-0 rounded-md border border-sky-500 bg-sky-50 px-3 py-2 text-sm font-medium text-sky-700 dark:border-sky-600 dark:bg-sky-900/30 dark:text-sky-400",
        onclick: () => render(),
      },
      ["Search"]
    ),
  ]);

  const filtersBtn = el(
    "button",
    {
      class:
        "flex-1 rounded-md border border-sky-500 bg-sky-50 px-3 py-2 text-left text-sm font-medium text-sky-700 dark:border-sky-600 dark:bg-sky-900/30 dark:text-sky-400",
      onclick: () => {
        state.filtersOpen = !state.filtersOpen;
        render();
      },
    },
    [
      state.filtersOpen ? "Hide Filters & GreenLight" : "Show Filters & GreenLight",
    ]
  );

  const terminalBtn = el(
    "button",
    {
      class:
        "flex-1 rounded-md border border-sky-500 bg-sky-50 px-3 py-2 text-left text-sm font-medium text-sky-700 dark:border-sky-600 dark:bg-sky-900/30 dark:text-sky-400",
      onclick: async () => {
        state.terminalPanelOpen = !state.terminalPanelOpen;
        if (state.terminalPanelOpen) {
          await Promise.all([fetchWatchlist(), fetchFilterPresets(), refreshAlerts()]);
        }
        render();
      },
    },
    [state.terminalPanelOpen ? "Hide Terminal Workflows" : "Terminal Workflows"]
  );

  top.appendChild(searchRow);

  top.appendChild(el("div", { class: "flex flex-col gap-2 sm:flex-row" }, [filtersBtn, terminalBtn]));

  if (state.filtersOpen) {
    const panels = el(
      "div",
      {
        class: "space-y-3 pt-3 lg:grid lg:grid-cols-2 lg:gap-4 lg:space-y-0",
      },
      [renderFiltersPanel(), renderPrefsPanel()]
    );
    top.appendChild(panels);
  }

  if (state.terminalPanelOpen) {
    top.appendChild(renderTerminalPanel());
  }

  const sortSelect = (() => {
    const s = el(
      "select",
      {
        class:
          "rounded-md border border-sky-500 bg-sky-50 px-2 py-1 text-xs font-medium text-sky-700 dark:border-sky-600 dark:bg-sky-900/30 dark:text-sky-400",
        onchange: async (e) => {
          state.query.sort = e.target.value;
          await render();
        },
      },
      SORT_OPTIONS.map((o) =>
        el(
          "option",
          {
            value: o.value,
            class:
              "bg-slate-200 text-sky-800 dark:bg-slate-800 dark:text-sky-300",
          },
          [o.label]
        )
      )
    );
    s.value = state.query.sort || "composite";
    return s;
  })();

  const listWrap = el("div", { class: "pt-2" }, [
    el(
      "div",
      { class: "flex flex-col gap-2 text-xs text-slate-600 dark:text-slate-400 sm:flex-row sm:items-center sm:justify-between" },
      [
        el("div", {}, ["Results update on Search and Sort."]),
        el("div", { class: "flex items-center gap-2 sm:flex-1 sm:justify-center" }, [
          el("div", { class: "font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400" }, ["Sort:"]),
          sortSelect,
        ]),
        renderScoreLegend(),
      ]
    ),
  ]);
  top.appendChild(listWrap);
  main.appendChild(top);
  layout.appendChild(main);
  if (sidebar) layout.appendChild(sidebar);
  root.appendChild(layout);

  await fetchWatchlist();
  await fetchFilterPresets();

  const qs = buildQueryString();
  const limitParam = qs ? `${qs}&limit=200` : "?limit=200";
  const data = await apiGet(`/api/loads/scored${limitParam}`);
  listWrap.appendChild(el("div", { class: "text-xs text-slate-600 dark:text-slate-400 pt-2" }, [`${data.total} loads`]))

  const ul = el("div", { class: "grid grid-cols-1 gap-2 pt-2 lg:grid-cols-2" });
  const scoredItems = Array.isArray(data.loads) ? data.loads : [];
  state.scoredLoads = {};
  for (const item of scoredItems) {
    if (!item?.load?.id) continue;
    state.scoredLoads[item.load.id] = {
      score: item.score,
      greenlight: item.greenlight,
      top_reasons: item.top_reasons || [],
      confidence: item.confidence,
    };
  }
  const availableLoads = scoredItems.map((item) => item.load).filter(Boolean);
  state.latestLoads = availableLoads;
  _updateGreenlightTicker(state.latestLoads);
  const loads = availableLoads.slice(0, 200);
  const sortedLoads = state.prefs.greenlight_sort === "on"
    ? [...loads].sort((a, b) => {
        const ag = isGreenLight(a) ? 1 : 0;
        const bg = isGreenLight(b) ? 1 : 0;
        return bg - ag;
      })
    : loads;

  for (const load of sortedLoads) {
    const { rpmOk, equipmentOk, weightOk, detentionOk } = prefStatus(load);
    const greenlightActive = hasActivePrefs();

    // Get score data if available
    const scoreData = state.scoredLoads[load.id];
    const hasScore = !!scoreData;
    const greenlightOk = greenlightActive && isGreenLight(load);

    // Color semantics: reserve green for the GreenLight verdict.
    // Use a more blue-leaning accent for informational/pass indicators.
    const okTextClass = "text-sky-600 dark:text-sky-400";
    const scoreValue = hasScore ? scoreData.score : null;
    const isWatched = state.watchlist.has(load.id);

    const maybeClass = (ok, defaultClass) => {
      if (ok === null) return defaultClass;
      return ok ? okTextClass : "text-red-600 dark:text-red-400";
    };

    const rpmClass = "text-xs text-slate-700 dark:text-slate-300";
    const equipClass = maybeClass(equipmentOk, "");
    const weightClass = maybeClass(weightOk, "");
    const detentionClass = maybeClass(detentionOk, "");
    const payClass = "text-sm font-semibold text-slate-700 dark:text-slate-300";
    const routeClass = "text-sm font-semibold text-slate-900 dark:text-slate-100";

    // Build score + verdict badges (neutral pill; green tint only when endorsed)
    const scoreBadge = hasScore
      ? el(
          "span",
          {
            class: `inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${
              greenlightOk
                ? "border-emerald-400 bg-emerald-50/80 text-slate-900 shadow-[0_0_0_1px_rgba(16,185,129,0.45)] dark:border-emerald-500 dark:bg-emerald-900/30 dark:text-emerald-50"
                : "border-slate-300 bg-slate-100 text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
            }`,
            title: buildScoreTooltip(scoreValue, greenlightOk, load),
          },
          [`${scoreValue.toFixed(1)}`]
        )
      : null;

    const scoreCluster = hasScore
      ? (() => {
          const glyph = greenlightOk
            ? el(
                "span",
                { class: "mr-1 inline-flex items-center" },
                [
                  el("img", {
                    src: toAppUrl("/static/images/gl_glyph.png"),
                    alt: "GreenLight",
                    class: "inline-block align-middle h-4 w-4 transform scale-150",
                  }),
                ]
              )
            : null;

          const verdictBadge = greenlightOk
            ? null
            : el(
                "span",
                {
                  class:
                    "mr-1 inline-flex items-center rounded-full px-2 py-0.5 text-[0.7rem] font-semibold bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-100",
                  title: "Scored (not GreenLight)",
                },
                ["Scored"]
              );

          return el("div", { class: "flex items-center" }, [
            glyph,
            verdictBadge,
            scoreBadge,
          ].filter(Boolean));
        })()
      : null;

    // Build top reasons (inline, expandable)
    const topReasons = hasScore && scoreData.top_reasons.length > 0
      ? (() => {
          const reasons = scoreData.top_reasons.slice(0, 2);
          const children = [];
          reasons.forEach((r, idx) => {
            const icon = r.direction === "positive" ? "✓" : r.direction === "negative" ? "✗" : "○";
            const colorClass =
              r.direction === "positive"
                ? okTextClass
                : r.direction === "negative"
                ? "text-red-600 dark:text-red-400"
                : "text-slate-500 dark:text-slate-400";

            children.push(el("span", { class: colorClass }, [`${icon} ${r.display_name}`]));
            if (idx < reasons.length - 1) {
              children.push(el("span", { class: "px-1 text-slate-400 dark:text-slate-500" }, ["•"]));
            }
          });
          return el("div", { class: "text-xs truncate" }, children);
        })()
      : null;

    // Watchlist toggle button
    const watchlistBtn = el(
      "button",
      {
        class: watchlistListBtnClass(isWatched),
        title: isWatched ? "Remove from watchlist" : "Add to watchlist",
        "data-watchlist-id": load.id,
        "data-watchlist-variant": "list",
        onclick: (e) => {
          e.preventDefault();
          e.stopPropagation();
          toggleWatchlist(load.id);
        },
      },
      [isWatched ? "★" : "☆"]
    );

    const row = el(
      "a",
      {
        href: `${appBasePath}#/load/${load.id}`,
        onclick: () => setLastSelectedLoadId(load.id),
        class:
          [
            "block rounded-lg border border-slate-200 bg-white p-3 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:bg-slate-800 relative",
            "min-h-[130px]",
            state.uiPrefs.greenlight_full_row && greenlightOk ? "lg:col-span-2" : "",
          ]
            .filter(Boolean)
            .join(" "),
      },
      [
        // Header: left = route, right = vertical stack (score + price + $/mi) + watch star
        el("div", { class: "flex items-start justify-between gap-2" }, [
          // Left: route + load info stack
          el("div", { class: "min-w-0 flex-1" }, [
            el("div", { class: "flex items-center gap-2" }, [
              el("div", { class: routeClass }, [
                `${load.origin.city}, ${load.origin.state} → ${load.destination.city}, ${load.destination.state}`,
              ]),
            ]),
            topReasons ? el("div", { class: "pt-1" }, [topReasons]) : null,
            el("div", { class: "mt-2" }, [
              el("div", { class: "text-xs text-slate-700 dark:text-slate-300" }, [
                el("span", { class: equipClass }, [load.equipment]),
                " • ",
                `${fmtNum(load.distance_miles)} mi • deadhead ${fmtNum(load.deadhead_miles)} mi • `,
                el("span", { class: weightClass }, [`${load.weight_lbs} lbs`]),
              ]),
              el(
                "div",
                { class: "pt-1 text-xs text-slate-600 dark:text-slate-400" },
                [
                  el("div", { class: "min-w-0" }, [
                    `Broker: ${load.broker.name} (${fmtNum(load.broker.rating, 1)})`,
                    load.hazmat ? " • Hazmat" : "",
                    load.detention ? " • " : "",
                    load.detention ? el("span", { class: detentionClass }, ["Detention"]) : "",
                    load.multi_stop ? " • Multi-stop" : "",
                    load.lane_history ? " • Lane history" : "",
                  ]),
                ]
              ),
            ]),
          ].filter(Boolean)),

          // Right: score/price at top, watchlist star anchored bottom-right
          el("div", { class: "flex flex-col items-end justify-between self-stretch text-right" }, [
            el("div", { class: "flex flex-col items-end gap-1" }, [
              // Score cluster (if present) will appear at the top of this stack
              scoreCluster,
              // Price (preserve existing styling)
              el("div", {}, [
                el("div", { class: payClass }, [fmtMoney(load.rate_total_usd)]),
                el("div", { class: rpmClass }, [`$${fmtNum(load.rpm, 2)}/mi`]),
              ]),
            ].filter(Boolean)),
          ]),
        ]),
        el(
          "div",
          { class: "absolute bottom-3 right-3" },
          [watchlistBtn]
        ),
      ]
    );
    ul.appendChild(row);
  }
  listWrap.appendChild(ul);
};

const renderPrefsPanel = () => {
  const wrap = el("div", {
    class:
      "rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900",
  });

  const row = (label, inputEl) =>
    el("div", { class: "grid grid-cols-2 items-center gap-2" }, [
      el("div", { class: "text-xs font-medium text-slate-700 dark:text-slate-300" }, [label]),
      inputEl,
    ]);

  const num = (key, placeholder, step) =>
    el("input", {
      type: "number",
      step: step ?? "any",
      class:
        "w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-800 dark:bg-slate-950",
      placeholder,
      value: state.prefsDraft[key],
      oninput: (e) => (state.prefsDraft[key] = e.target.value),
    });

  const sel = (key, options) => {
    const s = el(
      "select",
      {
        class:
          "w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-800 dark:bg-slate-950",
        onchange: (e) => (state.prefsDraft[key] = e.target.value),
      },
      [
        el("option", { value: "" }, ["(any)"]),
        ...options.map((o) => el("option", { value: o.value }, [o.label])),
      ]
    );
    s.value = state.prefsDraft[key] || "";
    return s;
  };

  wrap.appendChild(
    el("div", { class: "text-sm font-semibold" }, [
      el("span", { class: "inline-flex items-center align-middle" }, [
        el("img", {
          src: toAppUrl("/static/images/gl_glyph.png"),
          alt: "GreenLight",
          class: "inline-block align-middle h-4 w-4 transform scale-150",
        }),
        el(
          "span",
          {
            class:
              "ml-1 inline-flex items-center rounded-full bg-green-100 px-2 py-0.5 text-xs font-semibold text-green-800 dark:bg-green-900 dark:text-green-200",
          },
          ["GreenLight"]
        ),
      ]),
    ])
  );

  wrap.appendChild(
    el("div", { class: "grid gap-2 pt-3" }, [
      row("$ / mi min", num("rpm_min", "e.g. 3.50", "0.01")),
      row(
        "Equipment",
        sel("equipment", [
          { value: "Dry Van", label: "Dry Van" },
          { value: "Reefer", label: "Reefer" },
          { value: "Flatbed", label: "Flatbed" },
          { value: "Power Only", label: "Power Only" },
        ])
      ),
      row("Weight max (lbs)", num("weight_max", "e.g. 45000", "1")),
      row("Weight min (lbs)", num("weight_min", "e.g. 12000", "1")),
      row("Broker rating min", num("broker_rating_min", "e.g. 3.5")),
      row("Deadhead max (mi)", num("deadhead_max", "e.g. 150")),
      row(
        "Detention",
        sel("detention", [
          { value: "true", label: "Required" },
          { value: "false", label: "No" },
        ])
      ),
      row(
        "Hazmat",
        sel("hazmat", [
          { value: "true", label: "Required" },
          { value: "false", label: "No" },
        ])
      ),
      row(
        "Multi-stop",
        sel("multi_stop", [
          { value: "true", label: "Required" },
          { value: "false", label: "No" },
        ])
      ),
      row(
        el("span", { class: "inline-flex items-center gap-2" }, [
          "Sort by",
          el("img", {
            src: toAppUrl("/static/images/gl_glyph.png"),
            alt: "GreenLight",
            class: "inline-block align-middle h-4 w-4 transform scale-150",
          }),
        ]),
        el("div", { class: "flex items-center justify-end gap-4" }, [
          el("label", { class: "flex items-center gap-2 text-sm" }, [
            el("input", {
              type: "radio",
              name: "greenlight_sort",
              value: "",
              checked: state.prefsDraft.greenlight_sort !== "on" ? "checked" : undefined,
              onchange: () => (state.prefsDraft.greenlight_sort = ""),
            }),
            "Off",
          ]),
          el("label", { class: "flex items-center gap-2 text-sm" }, [
            el("input", {
              type: "radio",
              name: "greenlight_sort",
              value: "on",
              checked: state.prefsDraft.greenlight_sort === "on" ? "checked" : undefined,
              onchange: () => (state.prefsDraft.greenlight_sort = "on"),
            }),
            "On",
          ]),
        ])
      ),
    ])
  );

  const applyBtn = el(
    "button",
    {
      class:
        "mt-3 w-full flex items-center justify-center gap-2 rounded-md border border-sky-500 bg-sky-50 px-3 py-2 text-sm font-medium text-sky-700 dark:border-sky-600 dark:bg-sky-900/30 dark:text-sky-400",
      onclick: async () => {
        state.prefs = { ...state.prefsDraft };
        await syncPreferences(state.prefs);
        render();
      },
    },
    ["Apply"]
  );
  wrap.appendChild(applyBtn);

  const saveDefaultBtn = el(
    "button",
    {
      class:
        "mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800",
      title: "Save these GreenLight parameters as the default on this device",
      onclick: async () => {
        state.prefs = { ...state.prefsDraft };
        setGreenLightDefaults(state.prefs);
        await syncPreferences(state.prefs);
        render();
      },
    },
    ["Save as Default"]
  );
  wrap.appendChild(saveDefaultBtn);

  const resetDefaultBtn = el(
    "button",
    {
      class:
        "mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800",
      title: "Clear saved GreenLight defaults and reset parameters",
      onclick: async () => {
        clearGreenLightDefaults();
        state.prefs = { ...DEFAULT_PREFS };
        state.prefsDraft = { ...DEFAULT_PREFS };
        await syncPreferences(state.prefs);
        render();
      },
    },
    ["Reset Defaults"]
  );
  wrap.appendChild(resetDefaultBtn);

  return wrap;
};

const renderTerminalPanel = () => {
  const wrap = el("div", {
    class:
      "rounded-lg border border-sky-500 bg-sky-50 p-3 dark:border-sky-600 dark:bg-sky-900/20 space-y-4",
  });

  // Section: Save Filter Preset
  const presetSection = el("div", { class: "space-y-2" });
  presetSection.appendChild(
    el("div", { class: "text-sm font-semibold text-sky-700 dark:text-sky-400" }, ["💾 Save Filter Preset"])
  );

  let presetNameInput;
  const presetRow = el("div", { class: "flex gap-2" }, [
    (presetNameInput = el("input", {
      class:
        "flex-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900",
      placeholder: "Preset name...",
    })),
    el(
      "button",
      {
        class:
          "shrink-0 rounded-md border border-sky-500 bg-sky-50 px-3 py-1 text-sm font-medium text-sky-700 dark:border-sky-600 dark:bg-sky-900/30 dark:text-sky-400",
        onclick: () => {
          const name = presetNameInput.value.trim();
          if (name) {
            saveFilterPreset(name);
            presetNameInput.value = "";
          }
        },
      },
      ["Save"]
    ),
  ]);
  presetSection.appendChild(presetRow);

  // Show saved presets
  if (state.filterPresets.length > 0) {
    const presetList = el("div", { class: "flex flex-wrap gap-2 pt-1" });
    for (const preset of state.filterPresets) {
      presetList.appendChild(
        el("div", { class: "flex items-center gap-1 rounded bg-slate-200 dark:bg-slate-700 px-2 py-1 text-xs" }, [
          el("span", { class: "text-slate-700 dark:text-slate-200" }, [preset.name]),
          el(
            "button",
            {
              class:
                "ml-1 rounded border border-sky-500 bg-sky-50 px-2 py-0.5 text-[0.7rem] font-medium text-sky-700 dark:border-sky-600 dark:bg-sky-900/30 dark:text-sky-400",
              title: "Apply preset and run Search",
              onclick: () => loadFilterPreset(preset),
            },
            ["Apply now"]
          ),
          el(
            "button",
            {
              class: "text-red-500 hover:text-red-700 ml-1",
              onclick: () => deleteFilterPreset(preset.id),
            },
            ["×"]
          ),
        ])
      );
    }
    presetSection.appendChild(presetList);
  }
  wrap.appendChild(presetSection);

  // Section: Watchlist summary
  const watchlistSection = el("div", { class: "space-y-2" });
  watchlistSection.appendChild(
    el("div", { class: "text-sm font-semibold text-sky-700 dark:text-sky-400" }, ["👁️ Watchlist"])
  );
  const watchCount = state.watchlist.size;
  watchlistSection.appendChild(
    el(
      "div",
      { class: "text-xs text-slate-600 dark:text-slate-400", "data-watchlist-summary": "true" },
      [watchlistSummaryText(watchCount)]
    )
  );

  watchlistSection.appendChild(
    el(
      "button",
      {
        class:
          "w-full rounded-md border border-sky-500 bg-sky-50 px-3 py-2 text-sm font-medium text-sky-700 dark:border-sky-600 dark:bg-sky-900/30 dark:text-sky-400",
        title: "Fetch scores for watched loads and show the top 5",
        onclick: async () => {
          await runWatchlistSweep();
        },
      },
      ["Watchlist sweep"]
    )
  );

  if (state.watchlistSweep?.loading) {
    watchlistSection.appendChild(
      el("div", { class: "text-xs text-slate-600 dark:text-slate-400" }, ["Sweeping…"])
    );
  } else if (state.watchlistSweep?.error) {
    watchlistSection.appendChild(
      el("div", { class: "text-xs text-red-600 dark:text-red-400" }, [state.watchlistSweep.error])
    );
  } else if ((state.watchlistSweep?.items || []).length > 0) {
    watchlistSection.appendChild(
      el("div", { class: "pt-1 text-xs font-semibold text-slate-700 dark:text-slate-300" }, ["Top 5 watched by score"])
    );
    const list = el("div", { class: "space-y-1" });
    for (const item of state.watchlistSweep.items) {
      list.appendChild(
        el(
          "a",
          {
            href: `${appBasePath}#/load/${item.load_id}`,
            class:
              "block rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-800 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800",
          },
          [`${item.score.toFixed(0)} • ${item.route}`]
        )
      );
    }
    watchlistSection.appendChild(list);
  }

  wrap.appendChild(watchlistSection);

  // Section: Alerts placeholder
  const alertsSection = el("div", { class: "space-y-2" });
  alertsSection.appendChild(
    el("div", { class: "text-sm font-semibold text-sky-700 dark:text-sky-400" }, ["🔔 Alerts"])
  );

  let alertNameInput;
  alertsSection.appendChild(
    el("div", { class: "flex gap-2" }, [
      (alertNameInput = el("input", {
        class:
          "flex-1 rounded-md border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-700 dark:bg-slate-900",
        placeholder: "Alert name (uses current filters)…",
      })),
      el(
      "button",
      {
        class:
          "shrink-0 rounded-md border border-sky-500 bg-sky-50 px-3 py-1 text-sm font-medium text-sky-700 dark:border-sky-600 dark:bg-sky-900/30 dark:text-sky-400",
        onclick: async () => {
          const name = alertNameInput.value.trim();
          if (!name) return;
            await createAlertFromFilters(name);
            alertNameInput.value = "";
          },
        },
        ["Create"]
      ),
      el(
        "button",
        {
          class:
            "shrink-0 rounded-md border border-slate-300 bg-white px-3 py-1 text-sm font-medium text-slate-800 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800",
          title: "Re-evaluate alerts",
          onclick: async () => {
            await refreshAlerts();
            render();
          },
        },
        ["Refresh"]
      ),
    ])
  );

  const byRuleId = {};
  for (const t of state.triggeredAlerts || []) byRuleId[t.rule_id] = t;

  if (!state.alertRules || state.alertRules.length === 0) {
    alertsSection.appendChild(
      el(
        "div",
        { class: "rounded border border-dashed border-slate-400 p-3 text-center text-xs text-slate-500 dark:border-slate-600" },
        [el("div", {}, ["No alert rules configured"])]
      )
    );
  } else {
    const list = el("div", { class: "space-y-2" });
    for (const rule of state.alertRules) {
      const trig = byRuleId[rule.id] || { matches_count: 0, last_triggered: null };
      const last = trig.last_triggered ? new Date(trig.last_triggered).toLocaleString() : "—";

      list.appendChild(
        el(
          "div",
          { class: "rounded border border-slate-200 bg-white p-2 text-xs dark:border-slate-800 dark:bg-slate-900" },
          [
            el("div", { class: "flex items-center justify-between gap-2" }, [
              el("div", { class: "min-w-0" }, [
                el("div", { class: "truncate font-semibold text-slate-800 dark:text-slate-200" }, [rule.name]),
                rule.description
                  ? el("div", { class: "truncate text-slate-600 dark:text-slate-400" }, [rule.description])
                  : null,
              ].filter(Boolean)),
              el("div", { class: "flex items-center gap-2" }, [
                el("div", { class: "text-slate-600 dark:text-slate-400" }, [`${trig.matches_count} match${trig.matches_count === 1 ? "" : "es"}`]),
                el("label", { class: "flex items-center gap-1 text-slate-700 dark:text-slate-300" }, [
                  el("input", {
                    type: "checkbox",
                    checked: rule.enabled ? "checked" : undefined,
                    onchange: (e) => setAlertEnabled(rule.id, e.target.checked),
                  }),
                  "On",
                ]),
                el(
                  "button",
                  {
                    class: "text-red-500 hover:text-red-700",
                    title: "Delete alert",
                    onclick: () => deleteAlertRule(rule.id),
                  },
                  ["×"]
                ),
              ]),
            ]),
            el("div", { class: "pt-1 text-[0.7rem] text-slate-600 dark:text-slate-400" }, [`Last triggered: ${last}`]),
          ].filter(Boolean)
        )
      );
    }
    alertsSection.appendChild(list);
  }

  wrap.appendChild(alertsSection);

  return wrap;
};

const renderFiltersPanel = () => {
  const wrap = el("div", { class: "rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900" });

  const row = (label, inputEl) =>
    el("div", { class: "grid grid-cols-2 items-center gap-2" }, [
      el("div", { class: "text-xs font-medium text-slate-700 dark:text-slate-300" }, [label]),
      inputEl,
    ]);

  const text = (key, placeholder) =>
    el("input", {
      class: "w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-800 dark:bg-slate-950",
      placeholder,
      value: state.query[key],
      oninput: (e) => (state.query[key] = e.target.value),
    });

  const num = (key, placeholder) =>
    el("input", {
      type: "number",
      class: "w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-800 dark:bg-slate-950",
      placeholder,
      value: state.query[key],
      oninput: (e) => (state.query[key] = e.target.value),
    });

  const sel = (key, options) => {
    const s = el(
      "select",
      {
        class: "w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-800 dark:bg-slate-950",
        onchange: (e) => (state.query[key] = e.target.value),
      },
      [
        el("option", { value: "" }, ["(any)"]),
        ...options.map((o) => el("option", { value: o.value }, [o.label])),
      ]
    );
    s.value = state.query[key] || "";
    return s;
  };

  wrap.appendChild(
    el("div", { class: "grid gap-2" }, [
      row(
        "Sort",
        sel("sort", SORT_OPTIONS)
      ),
      row("Equipment", sel("equipment", [
        { value: "Dry Van", label: "Dry Van" },
        { value: "Reefer", label: "Reefer" },
        { value: "Flatbed", label: "Flatbed" },
        { value: "Power Only", label: "Power Only" },
      ])),
      row("Weight min (lbs)", num("weight_min", "e.g. 10000")),
      row("Weight max (lbs)", num("weight_max", "e.g. 45000")),
      row("Hazmat", sel("hazmat", [
        { value: "true", label: "Yes" },
        { value: "false", label: "No" },
      ])),
      row("Deadhead max (mi)", num("deadhead_max", "e.g. 120")),
      row("$ / mi min", num("rpm_min", "e.g. 2.25")),
      row("Broker rating min", num("broker_rating_min", "e.g. 3.5")),
      row("Detention", sel("detention", [
        { value: "true", label: "Required" },
        { value: "false", label: "No" },
      ])),
      row("Multi-stop", sel("multi_stop", [
        { value: "true", label: "Yes" },
        { value: "false", label: "No" },
      ])),
      row("Lane history", sel("lane_history", [
        { value: "true", label: "Yes" },
        { value: "false", label: "No" },
      ])),
    ])
  );

  wrap.appendChild(
    el("div", { class: "pt-3" }, [
      el(
      "button",
      {
        class:
          "w-full rounded-md border border-sky-500 bg-sky-50 px-3 py-2 text-sm font-medium text-sky-700 dark:border-sky-600 dark:bg-sky-900/30 dark:text-sky-400",
        onclick: () => render(),
      },
      ["Apply"]
      ),
    ])
  );

  wrap.appendChild(
    el(
      "button",
      {
        class:
          "mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800",
        title: "Save these filters/sort as the default on this device",
        onclick: () => {
          // Persist only sort + filters; not the free-text search.
          setFilterDefaults({ ...state.query, q: "" });
          render();
        },
      },
      ["Save as Default"]
    )
  );

  wrap.appendChild(
    el(
      "button",
      {
        class:
          "mt-2 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-800 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-200 dark:hover:bg-slate-800",
        title: "Clear saved filter defaults and reset filters",
        onclick: () => {
          clearFilterDefaults();
          state.query = { ...DEFAULT_QUERY };
          render();
        },
      },
      ["Reset Defaults"]
    )
  );

  return wrap;
};

const renderDetail = async (root, id) => {
  let load;
  try {
    load = await apiGet(`/api/loads/${id}`);
  } catch (err) {
    console.error("Failed to fetch load:", err);
    const back = el("a", { href: "/#/", class: "text-sm font-medium underline" }, ["← Back"]);
    root.appendChild(back);
    renderFatalError(root, "Load not found", "That load ID is missing (try going back to the list).");
    return;
  }
  
  // Fetch score for this load
  let scoreData = null;
  try {
    const scored = await apiGet(`/api/loads/${id}/score`);
    scoreData = scored;
  } catch (err) {
    console.error("Failed to fetch score:", err);
  }

  // Check watchlist status
  await fetchWatchlist();
  const isWatched = state.watchlist.has(id);

  // GreenLight verdict for this load
  const greenlightOk = hasActivePrefs() && isGreenLight(load);

  // Persist last selected load for RouteCast on the main screen
  setLastSelectedLoadId(id);

  const back = el(
    "a",
    { href: "/#/", class: "text-sm font-medium underline" },
    ["← Back"]
  );

  // Score badge and GreenLight indicator (neutral pill, tint only when endorsed)
  const scoreBadge = scoreData
    ? el(
        "div",
        {
          class: `inline-flex items-center rounded-full border px-3 py-1 text-sm font-semibold ${
            greenlightOk
              ? "border-emerald-400 bg-emerald-50/80 text-slate-900 shadow-[0_0_0_1px_rgba(16,185,129,0.45)] dark:border-emerald-500 dark:bg-emerald-900/30 dark:text-emerald-50"
              : "border-slate-300 bg-slate-100 text-slate-900 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-100"
          }`,
          title: buildScoreTooltip(scoreData.score, greenlightOk, load),
        },
        [`${scoreData.score.toFixed(1)}`]
      )
    : null;

  const greenlightGlyph = scoreBadge && greenlightOk
    ? el("span", { class: "mr-1 inline-flex items-center" }, [
        el("img", {
          src: toAppUrl("/static/images/gl_glyph.png"),
          alt: "GreenLight",
          class: "inline-block align-middle h-4 w-4 transform scale-150",
        }),
      ])
    : null;

  const verdictBadge = scoreBadge && !greenlightOk
    ? el(
        "span",
        {
          class:
            "mr-1 inline-flex items-center rounded-full px-2 py-0.5 text-[0.75rem] font-semibold bg-slate-200 text-slate-800 dark:bg-slate-700 dark:text-slate-100",
          title: "Scored (not GreenLight)",
        },
        ["Scored"]
      )
    : null;

  const scoreCluster = scoreBadge
    ? el("div", { class: "flex items-center" }, [greenlightGlyph, verdictBadge, scoreBadge].filter(Boolean))
    : null;

  // Top reasons section
  const reasonsSection = scoreData && scoreData.top_reasons.length > 0
    ? el("div", { class: "pt-3" }, [
        el("div", { class: "text-xs font-semibold text-slate-600 dark:text-slate-400 pb-1" }, ["Score Factors"]),
        ...scoreData.top_reasons.map((r) => {
          const icon = r.direction === "positive" ? "✓" : r.direction === "negative" ? "✗" : "○";
          const colorClass =
            r.direction === "positive"
              ? "text-green-600 dark:text-green-400"
              : r.direction === "negative"
              ? "text-red-600 dark:text-red-400"
              : "text-slate-600 dark:text-slate-400";
          return el("div", { class: `text-xs ${colorClass} py-0.5` }, [
            `${icon} ${r.explanation}`,
          ]);
        }),
      ])
    : null;

  // Watchlist button
  const watchlistBtn = el(
    "button",
    {
      class: watchlistDetailBtnClass(isWatched),
      "data-watchlist-id": id,
      "data-watchlist-variant": "detail",
      onclick: () => toggleWatchlist(id),
    },
    [isWatched ? "★ Watching" : "☆ Add to Watchlist"]
  );

  const leftCol = el("div", { class: "min-w-0 flex-1" }, [
    el("div", { class: "flex items-center justify-between gap-2" }, [
      el("div", { class: "text-base font-semibold" }, [
        `${load.origin.city}, ${load.origin.state} → ${load.destination.city}, ${load.destination.state}`,
      ]),
      scoreCluster,
    ]),
    el("div", { class: "pt-2 text-sm" }, [
      el("div", { class: "flex justify-between" }, [
        el("div", { class: "text-slate-700 dark:text-slate-300" }, ["Rate total"]),
        el("div", { class: "font-semibold" }, [fmtMoney(load.rate_total_usd)]),
      ]),
      el("div", { class: "flex justify-between" }, [
        el("div", { class: "text-slate-700 dark:text-slate-300" }, ["$ / mi"]),
        el("div", { class: "font-semibold" }, [`$${fmtNum(load.rpm, 2)}`]),
      ]),
      el("div", { class: "flex justify-between" }, [
        el("div", { class: "text-slate-700 dark:text-slate-300" }, ["Distance"]),
        el("div", { class: "font-semibold" }, [`${fmtNum(load.distance_miles)} mi`]),
      ]),
      el("div", { class: "flex justify-between" }, [
        el("div", { class: "text-slate-700 dark:text-slate-300" }, ["Deadhead"]),
        el("div", { class: "font-semibold" }, [`${fmtNum(load.deadhead_miles)} mi`]),
      ]),
      el("div", { class: "flex justify-between" }, [
        el("div", { class: "text-slate-700 dark:text-slate-300" }, ["Equipment"]),
        el("div", { class: "font-semibold" }, [load.equipment]),
      ]),
      el("div", { class: "flex justify-between" }, [
        el("div", { class: "text-slate-700 dark:text-slate-300" }, ["Weight"]),
        el("div", { class: "font-semibold" }, [`${load.weight_lbs} lbs`]),
      ]),
    ]),
    el("div", { class: "pt-3 text-xs text-slate-600 dark:text-slate-400" }, [
      `Broker: ${load.broker.name} (${fmtNum(load.broker.rating, 1)})`,
      load.hazmat ? " • Hazmat" : "",
      load.detention ? " • Detention" : "",
      load.multi_stop ? " • Multi-stop" : "",
      load.lane_history ? " • Lane history" : "",
    ]),
    reasonsSection,
    el("div", { class: "pt-3" }, [watchlistBtn]),
  ]);

  const rightCol = el("div", { class: "pt-3 lg:pt-0 lg:w-[28rem] lg:flex-shrink-0" }, [
    renderRouteCastWidget(id, { compact: false, load }),
  ]);

  const card = el("div", { class: "mt-3 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900" }, [
    el("div", { class: "lg:flex lg:items-start lg:gap-4" }, [leftCol, rightCol]),
  ]);

  root.appendChild(back);
  root.appendChild(card);
};

const renderSettings = async (root) => {
  const back = el(
    "a",
    { href: "/#/", class: "text-sm font-medium underline" },
    ["← Back"]
  );
  root.appendChild(back);

  const box = el("div", { class: "mt-3 space-y-3 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900" });
  const meta = await apiGet("/api/meta");

  box.appendChild(el("div", { class: "text-sm" }, [
    el("div", { class: "font-semibold" }, ["Data source"]),
    el("div", { class: "text-slate-700 dark:text-slate-300" }, [`${meta.source} • ${meta.count} loads`]),
  ]));

  const themeRow = el("div", { class: "text-sm" }, [
    el("div", { class: "font-semibold" }, ["Theme"]),
  ]);
  const themeWrap = el("label", { class: "mt-2 flex items-center justify-between gap-3" }, [
    el("div", { class: "text-slate-700 dark:text-slate-300" }, ["Dark mode"]),
    el("input", {
      type: "checkbox",
      class: "h-5 w-5",
      checked: getTheme() === "dark" ? "checked" : undefined,
      onchange: (e) => {
        setTheme(e.target.checked ? "dark" : "light");
      },
    }),
  ]);
  themeRow.appendChild(themeWrap);
  box.appendChild(themeRow);

  // Terminal UI prefs
  const uiRow = el("div", { class: "text-sm" }, [
    el("div", { class: "font-semibold" }, ["Terminal UI"]),
  ]);

  const uiToggle = (label, key) =>
    el("label", { class: "mt-2 flex items-center justify-between gap-3" }, [
      el("div", { class: "text-slate-700 dark:text-slate-300" }, [label]),
      el("input", {
        type: "checkbox",
        class: "h-5 w-5",
        checked: state.uiPrefs[key] ? "checked" : undefined,
        onchange: (e) => {
          state.uiPrefs[key] = !!e.target.checked;
          setUiPrefs(state.uiPrefs);
          applyUiPrefsToShell();
          render();
        },
      }),
    ]);

  uiRow.appendChild(uiToggle("Show GreenLight ticker", "show_greenlight_ticker"));
  uiRow.appendChild(uiToggle("Show Freight Alerts ticker", "show_news_ticker"));
  uiRow.appendChild(uiToggle("Show sidebar", "show_sidebar"));
  uiRow.appendChild(uiToggle("GreenLight cards take full row", "greenlight_full_row"));
  box.appendChild(uiRow);

  // Weather ZIP override
  if (!state.weather.zipDraft) state.weather.zipDraft = state.weather.zip || "";
  const weatherRow = el("div", { class: "text-sm" }, [
    el("div", { class: "font-semibold" }, ["Weather location"]),
    el("div", { class: "mt-2 grid gap-2" }, [
      el("div", { class: "text-xs text-slate-600 dark:text-slate-400" }, [
        "Set a ZIP code to power the Weather Forecast and Severe Weather Alerts widgets.",
      ]),
      el("input", {
        type: "text",
        inputmode: "numeric",
        class: "w-full rounded-md border border-slate-300 bg-white px-2 py-1 text-sm dark:border-slate-800 dark:bg-slate-950",
        placeholder: "ZIP (e.g. 75201)",
        value: state.weather.zipDraft,
        oninput: (e) => (state.weather.zipDraft = e.target.value),
      }),
      el(
        "button",
        {
          class: "w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white dark:bg-slate-100 dark:text-slate-900",
          onclick: () => {
            const z = _normalizeZip(state.weather.zipDraft);
            state.weather.zip = z;
            state.weather.zipDraft = z;
            setWeatherZip(z);
            state.weather.forecast = null;
            state.weather.alerts = null;
            state.weather.forecastError = "";
            state.weather.alertsError = "";
            state.weather.fetchedAtForecastMs = 0;
            state.weather.fetchedAtAlertsMs = 0;
            render();
          },
        },
        ["Save ZIP"]
      ),
    ]),
  ]);
  box.appendChild(weatherRow);

  const refreshBtn = el(
    "button",
    {
      class: "w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white dark:bg-slate-100 dark:text-slate-900",
      onclick: async () => {
        refreshBtn.disabled = true;
        refreshBtn.textContent = "Refreshing…";
        try {
          await apiPostJson("/api/refresh", { count: 250 });
          await setMeta();
          await render();
        } finally {
          refreshBtn.disabled = false;
          refreshBtn.textContent = "Refresh (regenerate synthetic)";
        }
      },
    },
    ["Refresh (regenerate synthetic)"]
  );
  box.appendChild(refreshBtn);

  box.appendChild(el("div", { class: "pt-2 text-sm" }, [
    el("div", { class: "font-semibold" }, ["Import JSON/CSV"]),
    el("div", { class: "text-xs text-slate-600 dark:text-slate-400" }, [
      "Upload replaces the current dataset. See sample files in sample_data/.",
    ]),
  ]));

  const fileInput = el("input", { type: "file", class: "w-full text-sm" });
  const importBtn = el(
    "button",
    {
      class: "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm font-medium dark:border-slate-800 dark:bg-slate-950",
      onclick: async () => {
        const file = fileInput.files && fileInput.files[0];
        if (!file) return;
        importBtn.disabled = true;
        importBtn.textContent = "Importing…";
        try {
          await apiPostFileBytes(`/api/import?filename=${encodeURIComponent(file.name)}`, file);
          await setMeta();
          window.location.hash = "#/";
          await render();
        } catch (e) {
          alert(String(e));
        } finally {
          importBtn.disabled = false;
          importBtn.textContent = "Import";
        }
      },
    },
    ["Import"]
  );

  box.appendChild(fileInput);
  box.appendChild(importBtn);
  root.appendChild(box);
};

const _formatTickerTime = (value) => {
  if (!value) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) return null;
  return parsed.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

const _buildTickerEntry = (item) => {
  const timeLabel = _formatTickerTime(item.published);
  const badge = el(
    "span",
    { class: "flex-shrink-0 text-[0.55rem] font-semibold tracking-[0.35em] text-sky-200" },
    [item.source || "News"]
  );
  const title = el(
    "span",
    { class: "text-sm font-semibold text-white" },
    [item.title]
  );
  const divider = el("span", { class: "text-slate-200 opacity-70" }, ["—"]);
  const time = timeLabel
    ? el("span", { class: "text-[0.65rem] text-slate-200 opacity-80" }, [timeLabel])
    : null;

  const entry = el(
    "a",
    {
      class: "flex min-w-max items-center gap-2 opacity-90 hover:opacity-100 focus-visible:opacity-100",
      href: item.link || "#",
      target: "_blank",
      rel: "noreferrer",
    },
    [badge, divider, title, time].filter(Boolean)
  );
  return entry;
};

const _updateGreenlightTicker = (loads = []) => {
  const track = document.getElementById("greenlight-marquee-track");
  if (!track) return;
  track.innerHTML = "";
  const greenlightActive = hasActivePrefs();
  const entryBuilders = [];

  if (!greenlightActive) {
    entryBuilders.push(() =>
      el("span", { class: "text-[0.65rem] text-slate-500" }, [
        "Set preferred parameters to unlock ",
        el("img", {
          src: toAppUrl("/static/images/gl_logo.png"),
          alt: "GreenLight",
          class: "mx-1 h-5 w-auto object-contain inline-block align-middle",
        }),
        " alerts",
      ])
    );
  } else {
    const greenlightLoads = (loads ?? [])
      .filter((load) => isGreenLight(load))
      .slice(0, GREENLIGHT_TICKER_MAX);

    if (!greenlightLoads.length) {
      entryBuilders.push(() =>
        el("span", { class: "text-[0.65rem] text-slate-500" }, [
          "No ",
          el("img", {
            src: toAppUrl("/static/images/gl_logo.png"),
            alt: "GreenLight",
            class: "mx-1 h-5 w-auto object-contain inline-block align-middle",
          }),
          " lanes right now",
        ])
      );
    } else {
      for (const load of greenlightLoads) {
        entryBuilders.push(() => {
          const route = `${load.origin.city}, ${load.origin.state} → ${load.destination.city}, ${load.destination.state}`;
          return el(
            "a",
            {
              href: `${appBasePath}#/load/${load.id}`,
              class: "text-[0.75rem] font-semibold tracking-wide text-slate-400 transition hover:text-slate-200",
            },
            [`${route} • ${fmtMoney(load.rate_total_usd)}`]
          );
        });
      }
    }
  }

  const fragment = document.createDocumentFragment();
  const appendBatch = () => {
    for (const build of entryBuilders) {
      fragment.appendChild(build());
    }
  };
  appendBatch();
  appendBatch();
  track.appendChild(fragment);
};

const _updateNewsTicker = (items) => {
  const track = document.getElementById("news-marquee-track");
  if (!track) return;
  track.innerHTML = "";
  const entries = (items && items.length ? items : [{ title: "News temporarily unavailable", link: "#", source: "Freight" }]);
  const fragment = document.createDocumentFragment();
  const appendBatch = () => {
    for (const entry of entries) {
      fragment.appendChild(_buildTickerEntry(entry));
    }
  };
  appendBatch();
  appendBatch();
  track.appendChild(fragment);
};

const loadNewsTicker = async () => {
  try {
    const payload = await apiGet("/api/news");
    newsTickerState.items = payload.items ?? [];
  } catch (err) {
    console.error("failed to refresh news ticker", err);
  }
  _updateNewsTicker(newsTickerState.items);
};

const initNewsTicker = () => {
  loadNewsTicker();
  setInterval(loadNewsTicker, NEWS_TICKER_REFRESH_MS);
};

window.addEventListener("hashchange", render);
applyTheme(getTheme());
state.weather.zip = getWeatherZip();
state.lastSelectedLoadId = getLastSelectedLoadId();
{
  const defaults = getGreenLightDefaults();
  if (defaults) state.prefs = { ...state.prefs, ...defaults };
  state.prefsDraft = { ...state.prefs };
}
syncPreferences(state.prefs);
{
  const defaults = getFilterDefaults();
  if (defaults) state.query = { ...DEFAULT_QUERY, ...defaults, q: "" };
}
{
  const defaults = getUiPrefs();
  if (defaults) state.uiPrefs = { ...state.uiPrefs, ...defaults };
  applyUiPrefsToShell();
}
setMeta().then(render);
initNewsTicker();
