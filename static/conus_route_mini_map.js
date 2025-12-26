(() => {
  const CONUS_BOUNDS = { minLon: -125, maxLon: -66, minLat: 24, maxLat: 50 };
  const VIEWBOX = { width: 320, height: 180, padding: 10 };
  const OUTLINE_POINTS = [
    [-124.7, 48.4],
    [-123.4, 47.6],
    [-122.6, 46.0],
    [-123.9, 44.4],
    [-124.4, 42.2],
    [-124.2, 40.6],
    [-123.2, 39.2],
    [-122.4, 37.7],
    [-122.0, 36.2],
    [-121.0, 35.0],
    [-118.6, 34.2],
    [-117.1, 32.6],
    [-114.7, 32.4],
    [-112.2, 31.8],
    [-109.0, 31.4],
    [-106.6, 31.7],
    [-104.4, 30.6],
    [-101.8, 29.6],
    [-98.6, 27.8],
    [-96.6, 27.5],
    [-94.2, 28.4],
    [-91.3, 29.0],
    [-89.9, 29.6],
    [-88.0, 30.4],
    [-85.6, 30.2],
    [-83.6, 29.4],
    [-82.6, 28.6],
    [-81.3, 25.7],
    [-80.1, 25.1],
    [-80.4, 27.2],
    [-80.6, 30.2],
    [-81.6, 31.8],
    [-80.0, 32.8],
    [-79.0, 33.9],
    [-77.4, 35.3],
    [-75.4, 36.6],
    [-74.6, 39.0],
    [-73.9, 40.6],
    [-71.8, 41.7],
    [-70.7, 43.2],
    [-69.2, 44.7],
    [-71.0, 45.6],
    [-74.2, 45.7],
    [-77.5, 45.4],
    [-82.2, 46.1],
    [-87.5, 47.1],
    [-92.5, 48.8],
    [-97.2, 49.0],
    [-103.0, 49.0],
    [-110.0, 49.0],
    [-116.0, 49.0],
    [-124.7, 48.4],
  ];

  const createSvgEl = (tag, attrs = {}, children = []) => {
    const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (v !== undefined && v !== null) node.setAttribute(k, String(v));
    }
    for (const child of children) {
      if (child === null || child === undefined) continue;
      node.appendChild(typeof child === "string" ? document.createTextNode(child) : child);
    }
    return node;
  };

  const projectPoint = (lat, lon, { width, height, padding }) => {
    const x = padding + ((lon - CONUS_BOUNDS.minLon) / (CONUS_BOUNDS.maxLon - CONUS_BOUNDS.minLon)) * (width - padding * 2);
    const y = padding + ((CONUS_BOUNDS.maxLat - lat) / (CONUS_BOUNDS.maxLat - CONUS_BOUNDS.minLat)) * (height - padding * 2);
    return { x, y };
  };

  const buildOutlinePath = () => {
    const { width, height, padding } = VIEWBOX;
    const parts = OUTLINE_POINTS.map(([lon, lat], idx) => {
      const { x, y } = projectPoint(lat, lon, { width, height, padding });
      return `${idx === 0 ? "M" : "L"} ${x.toFixed(2)} ${y.toFixed(2)}`;
    });
    return `${parts.join(" ")} Z`;
  };

  const OUTLINE_PATH = buildOutlinePath();

  const renderPlaceholder = (className = "") => {
    const wrap = document.createElement("div");
    wrap.className =
      "relative flex h-full w-full items-center justify-center overflow-hidden rounded-md border border-slate-200/70 bg-white/70 text-[0.65rem] font-semibold uppercase tracking-[0.3em] text-slate-400 dark:border-slate-800 dark:bg-slate-900/60 dark:text-slate-500 " +
      className;
    wrap.textContent = "Map unavailable";
    return wrap;
  };

  const ConusRouteMiniMap = ({
    originLat,
    originLon,
    destLat,
    destLon,
    isGreenlight = false,
    className = "",
  } = {}) => {
    const hasCoords =
      Number.isFinite(originLat) &&
      Number.isFinite(originLon) &&
      Number.isFinite(destLat) &&
      Number.isFinite(destLon);
    if (!hasCoords) return renderPlaceholder(className);

    const wrap = document.createElement("div");
    wrap.className =
      "relative flex h-full w-full items-center justify-center overflow-hidden rounded-md border bg-white/70 dark:bg-slate-900/60 " +
      (isGreenlight
        ? "border-emerald-300/70 dark:border-emerald-500/50 "
        : "border-slate-200/70 dark:border-slate-800 ") +
      className;

    const svg = createSvgEl(
      "svg",
      {
        viewBox: `0 0 ${VIEWBOX.width} ${VIEWBOX.height}`,
        class: "h-full w-full",
        fill: "none",
        "aria-hidden": "true",
        preserveAspectRatio: "xMidYMid meet",
      },
      []
    );

    svg.appendChild(
      createSvgEl("path", {
        d: OUTLINE_PATH,
        fill: isGreenlight ? "rgba(16,185,129,0.08)" : "rgba(148,163,184,0.12)",
        stroke: isGreenlight ? "rgba(16,185,129,0.35)" : "rgba(148,163,184,0.45)",
        "stroke-width": "1.1",
      })
    );

    const origin = projectPoint(originLat, originLon, VIEWBOX);
    const dest = projectPoint(destLat, destLon, VIEWBOX);
    const routeStroke = isGreenlight ? "rgba(16,185,129,0.9)" : "rgba(59,130,246,0.85)";
    const markerFill = isGreenlight ? "rgba(16,185,129,0.95)" : "rgba(59,130,246,0.9)";

    svg.appendChild(
      createSvgEl("path", {
        d: `M ${origin.x.toFixed(2)} ${origin.y.toFixed(2)} L ${dest.x.toFixed(2)} ${dest.y.toFixed(2)}`,
        stroke: routeStroke,
        "stroke-width": "2",
        "stroke-linecap": "round",
      })
    );
    svg.appendChild(
      createSvgEl("circle", {
        cx: origin.x.toFixed(2),
        cy: origin.y.toFixed(2),
        r: "3",
        fill: markerFill,
      })
    );
    svg.appendChild(
      createSvgEl("circle", {
        cx: dest.x.toFixed(2),
        cy: dest.y.toFixed(2),
        r: "3.6",
        fill: markerFill,
      })
    );

    wrap.appendChild(svg);
    return wrap;
  };

  window.ConusRouteMiniMap = ConusRouteMiniMap;
})();
