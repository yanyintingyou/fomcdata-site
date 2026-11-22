(function () {
  "use strict";
  var FD = (window.FD = window.FD || {});
  var RANGES = { "1y": 365, "3y": 1095, "5y": 1825, "10y": 3650, "20y": 7300, "30y": 10950 };
  var cache = null;

  function load() {
    if (!cache) {
      cache = fetch("/data/market.json", { cache: "no-cache" }).then(function (r) {
        if (!r.ok) throw new Error("http " + r.status);
        return r.json();
      });
    }
    return cache;
  }

  function day(iso) {
    return Date.parse(iso + "T00:00:00Z");
  }

  function windowPoints(item, range, at) {
    var days = RANGES[range] || 365;
    var pts = item.points;
    if (!pts || !pts.length) return [];
    var end = at ? day(at) : day(pts[pts.length - 1][0]);
    var lo = at ? end - days * 43200000 : end - days * 86400000;
    var hi = at ? end + days * 43200000 : end + 86400000;
    return pts.filter(function (p) {
      var t = day(p[0]);
      return t >= lo && t <= hi;
    });
  }

  function fmt(v, d) {
    if (v == null || !isFinite(v)) return "—";
    return Number(v).toLocaleString("en-US", {
      minimumFractionDigits: d,
      maximumFractionDigits: d
    });
  }

  function deltaText(item) {
    var diff = item.last - item.prev;
    var sign = diff > 0 ? "+" : "";
    return sign + fmt(diff, item.decimals) + (item.unit === "%" ? " pp" : "");
  }

  function stats(points) {
    var vals = points.map(function (p) { return p[1]; });
    if (!vals.length) return null;
    var hi = Math.max.apply(null, vals);
    var lo = Math.min.apply(null, vals);
    var sum = vals.reduce(function (a, b) { return a + b; }, 0);
    var peak = vals[0];
    var dd = 0;
    vals.forEach(function (v) {
      if (v > peak) peak = v;
      var drop = peak ? (v / peak - 1) * 100 : 0;
      if (drop < dd) dd = drop;
    });
    return {
      high: hi,
      low: lo,
      mean: sum / vals.length,
      change: vals[0] ? (vals[vals.length - 1] / vals[0] - 1) * 100 : 0,
      drawdown: dd,
      first: points[0][0],
      last: points[points.length - 1][0],
      n: vals.length
    };
  }

  function readState(defaults) {
    var q = new URLSearchParams(location.search);
    var out = Object.assign({}, defaults);
    if (q.get("s")) out.keys = q.get("s").split(",").filter(Boolean).slice(0, 3);
    if (q.get("r") && RANGES[q.get("r")]) out.range = q.get("r");
    if (q.get("sc") === "log") out.scale = "log";
    if (q.get("sc") === "linear") out.scale = "linear";
    if (q.get("m")) out.mode = q.get("m");
    if (q.get("ov")) out.overlays = q.get("ov").split(",").filter(Boolean);
    if (q.get("at")) out.at = q.get("at");
    return out;
  }

  function writeState(state) {
    var q = new URLSearchParams();
    q.set("s", state.keys.join(","));
    q.set("r", state.range);
    q.set("sc", state.scale);
    q.set("m", state.mode);
    if (state.overlays.length) q.set("ov", state.overlays.join(","));
    if (state.at) q.set("at", state.at);
    history.replaceState(null, "", location.pathname + "?" + q.toString());
  }

  FD.load = load;
  FD.windowPoints = windowPoints;
  FD.fmt = fmt;
  FD.deltaText = deltaText;
  FD.stats = stats;
  FD.readState = readState;
  FD.writeState = writeState;
  FD.RANGES = RANGES;
})();
