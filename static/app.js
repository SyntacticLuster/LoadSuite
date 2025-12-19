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

const apiGet = async (path) => {
  const res = await fetch(path);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return await res.json();
};

const apiPostJson = async (path, body) => {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body ?? {}),
  });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return await res.json();
};

const apiPostFileBytes = async (path, file) => {
  const bytes = new Uint8Array(await file.arrayBuffer());
  const res = await fetch(path, {
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

const getHashRoute = () => {
  const h = window.location.hash || "#/";
  const parts = h.replace(/^#\//, "").split("/");
  return { page: parts[0] || "", id: parts[1] || null };
};

const state = {
  filtersOpen: false,
  query: {
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
  },
  prefsDraft: {
    rpm_min: "",
    equipment: "",
    weight_max: "",
    detention: "",
    greenlight_sort: "",
  },
  prefs: {
    rpm_min: "",
    equipment: "",
    weight_max: "",
    detention: "",
    greenlight_sort: "",
  },
};

const parseOptionalNumber = (raw) => {
  const s = String(raw ?? "").trim();
  if (!s) return null;
  const n = Number(s);
  return Number.isFinite(n) ? n : null;
};

const prefStatus = (load) => {
  const rpmMin = parseOptionalNumber(state.prefs.rpm_min);
  const weightMax = parseOptionalNumber(state.prefs.weight_max);

  const rpmOk = rpmMin === null ? null : load.rpm >= rpmMin;
  const equipmentOk = !state.prefs.equipment ? null : load.equipment === state.prefs.equipment;
  const weightOk = weightMax === null ? null : load.weight_lbs <= weightMax;

  let detentionOk = null;
  if (state.prefs.detention === "true") detentionOk = !!load.detention;
  else if (state.prefs.detention === "false") detentionOk = !load.detention;

  return { rpmOk, equipmentOk, weightOk, detentionOk };
};

const isGreenLight = (load) => {
  const prefs = state.prefs;
  const rpmMin = parseOptionalNumber(prefs.rpm_min);
  const weightMax = parseOptionalNumber(prefs.weight_max);
  const equipmentActive = !!prefs.equipment;
  const detentionActive = prefs.detention === "true" || prefs.detention === "false";

  if (rpmMin === null && weightMax === null && !equipmentActive && !detentionActive) return true;

  const { rpmOk, equipmentOk, weightOk, detentionOk } = prefStatus(load);
  const checks = [
    rpmMin === null ? null : rpmOk,
    equipmentActive ? equipmentOk : null,
    weightMax === null ? null : weightOk,
    detentionActive ? detentionOk : null,
  ];
  return checks.every((v) => v === null || v === true);
};

const hasActivePrefs = () => {
  const prefs = state.prefs;
  return (
    String(prefs.rpm_min ?? "").trim() !== "" ||
    String(prefs.weight_max ?? "").trim() !== "" ||
    String(prefs.equipment ?? "").trim() !== "" ||
    prefs.detention === "true" ||
    prefs.detention === "false"
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

const render = async () => {
  const root = document.getElementById("app");
  root.innerHTML = "";

  const route = getHashRoute();
  if (route.page === "settings") return renderSettings(root);
  if (route.page === "load" && route.id) return renderDetail(root, route.id);
  return renderList(root);
};

const renderList = async (root) => {
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
          "shrink-0 rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white dark:bg-slate-100 dark:text-slate-900",
        onclick: () => render(),
      },
      ["Search"]
    ),
  ]);

  const filtersBtn = el(
    "button",
    {
      class:
        "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-left text-sm font-medium dark:border-slate-800 dark:bg-slate-900",
      onclick: () => {
        state.filtersOpen = !state.filtersOpen;
        render();
      },
    },
    [state.filtersOpen ? "Hide Filters & Sort" : "Show Filters & Sort"]
  );

  top.appendChild(searchRow);
  top.appendChild(filtersBtn);
  if (state.filtersOpen) {
    top.appendChild(renderFiltersPanel());
    top.appendChild(renderPrefsPanel());
  }

  const listWrap = el("div", { class: "pt-2" }, [
    el("div", { class: "text-xs text-slate-600 dark:text-slate-400" }, ["Results update on Search."]),
  ]);
  top.appendChild(listWrap);
  root.appendChild(top);

  const data = await apiGet(`/api/loads${buildQueryString()}`);
  listWrap.appendChild(el("div", { class: "text-xs text-slate-600 dark:text-slate-400 pt-2" }, [`${data.total} loads`]))

  const ul = el("div", { class: "grid grid-cols-1 gap-2 pt-2 lg:grid-cols-2" });
  const loads = data.loads.slice(0, 200);
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
    const greenlightOk = greenlightActive ? isGreenLight(load) : false;

    const maybeClass = (ok, defaultClass) => {
      if (ok === null) return defaultClass;
      return ok ? "text-green-600 dark:text-green-400" : "text-red-600 dark:text-red-400";
    };

    const rpmClass = `text-xs ${maybeClass(rpmOk, "text-slate-600 dark:text-slate-400")}`;
    const equipClass = maybeClass(equipmentOk, "");
    const weightClass = maybeClass(weightOk, "");
    const detentionClass = maybeClass(detentionOk, "");
    const payClass = greenlightOk ? "text-sm font-semibold text-green-600 dark:text-green-400" : "text-sm font-semibold";
    const routeClass = greenlightOk
      ? "text-sm font-semibold text-green-400 dark:text-green-300"
      : "text-sm font-semibold";
    const row = el(
      "a",
      {
        href: `/#/load/${load.id}`,
        class:
          "block rounded-lg border border-slate-200 bg-white p-3 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:hover:bg-slate-800",
      },
      [
        el("div", { class: "flex items-start justify-between gap-2" }, [
          el("div", { class: routeClass }, [
            `${load.origin.city}, ${load.origin.state} → ${load.destination.city}, ${load.destination.state}`,
          ]),
          el("div", { class: "text-right" }, [
            el("div", { class: payClass }, [fmtMoney(load.rate_total_usd)]),
            el("div", { class: rpmClass }, [`$${fmtNum(load.rpm, 2)}/mi`]),
          ]),
        ]),
        el("div", { class: "pt-1 text-xs text-slate-700 dark:text-slate-300" }, [
          el("span", { class: equipClass }, [load.equipment]),
          " • ",
          `${fmtNum(load.distance_miles)} mi • deadhead ${fmtNum(load.deadhead_miles)} mi • `,
          el("span", { class: weightClass }, [`${load.weight_lbs} lbs`]),
        ]),
        el(
          "div",
          { class: "pt-1 text-xs text-slate-600 dark:text-slate-400 flex items-end justify-between gap-3" },
          [
            el("div", { class: "min-w-0" }, [
              `Broker: ${load.broker.name} (${fmtNum(load.broker.rating, 1)})`,
              load.hazmat ? " • Hazmat" : "",
              load.detention ? " • " : "",
              load.detention ? el("span", { class: detentionClass }, ["Detention"]) : "",
              load.multi_stop ? " • Multi-stop" : "",
              load.lane_history ? " • Lane history" : "",
            ]),
            el(
              "span",
              {
                class: greenlightOk
                  ? "text-lg leading-none text-green-400 dark:text-green-300"
                  : "text-lg leading-none invisible",
              },
              ["🟢"]
            ),
          ]
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
    el("div", { class: "text-sm font-semibold" }, ["Preferred parameters"])
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
      row(
        "Detention",
        sel("detention", [
          { value: "true", label: "Required" },
          { value: "false", label: "No" },
        ])
      ),
      row(
        "Sort by GreenLight",
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
        "mt-3 w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white dark:bg-slate-100 dark:text-slate-900",
      onclick: () => {
        state.prefs = { ...state.prefsDraft };
        render();
      },
    },
    ["Apply preferred parameters"]
  );
  wrap.appendChild(applyBtn);

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
        sel("sort", [
          { value: "composite", label: "Composite" },
          { value: "rpm_desc", label: "$ / mi (desc)" },
          { value: "pickup_soonest", label: "Pickup (soonest)" },
          { value: "deadhead_asc", label: "Deadhead (asc)" },
          { value: "broker_desc", label: "Broker rating (desc)" },
        ])
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
            "w-full rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white dark:bg-slate-100 dark:text-slate-900",
          onclick: () => render(),
        },
        ["Apply"]
      ),
    ])
  );

  return wrap;
};

const renderDetail = async (root, id) => {
  const load = await apiGet(`/api/loads/${id}`);
  const back = el(
    "a",
    { href: "/#/", class: "text-sm font-medium underline" },
    ["← Back"]
  );

  const card = el("div", { class: "mt-3 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900" }, [
    el("div", { class: "text-base font-semibold" }, [
      `${load.origin.city}, ${load.origin.state} → ${load.destination.city}, ${load.destination.state}`,
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

window.addEventListener("hashchange", render);
applyTheme(getTheme());
state.prefsDraft = { ...state.prefs };
setMeta().then(render);
