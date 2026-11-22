(function () {
  "use strict";
  var FD = window.FD;
  var COLORS = ["#8a3d28", "#2f5d62", "#8a6d1f", "#2b4d7d"];
  var C = {
    ink: "#1b1a17", muted: "#6d675d", dim: "#9a9388",
    rule: "#ded8cb", hair: "#ece8dd", paper: "#faf9f6",
    band: "#efece2", event: "#c8c1b1"
  };
  var FONT = "-apple-system, 'Segoe UI', 'PingFang SC', 'Microsoft YaHei', sans-serif";

  function day(iso) { return Date.parse(iso + "T00:00:00Z"); }

  function rollingVol(vals, freq) {
    if (freq !== "daily") return vals.map(function () { return null; });
    var out = [];
    for (var i = 0; i < vals.length; i++) {
      if (i < 20) { out.push(null); continue; }
      var rets = [];
      for (var j = i - 19; j <= i; j++) {
        if (vals[j - 1] > 0 && vals[j] > 0) rets.push(Math.log(vals[j] / vals[j - 1]));
      }
      if (rets.length < 10) { out.push(null); continue; }
      var mean = rets.reduce(function (a, b) { return a + b; }, 0) / rets.length;
      var varr = rets.reduce(function (a, b) { return a + (b - mean) * (b - mean); }, 0) / (rets.length - 1);
      out.push(Math.sqrt(varr) * Math.sqrt(252) * 100);
    }
    return out;
  }

  function buildSets(data, opt) {
    var mode = opt.keys.length > 1 ? "norm" : opt.mode || "level";
    return opt.keys.map(function (key, i) {
      var item = data.series[key];
      var pts = FD.windowPoints(item, opt.range, opt.at);
      var vals = pts.map(function (p) { return p[1]; });
      var base = vals[0];
      var out;
      if (mode === "norm") out = vals.map(function (v) { return base ? (v / base) * 100 : null; });
      else if (mode === "pct") out = vals.map(function (v) { return base ? (v / base - 1) * 100 : null; });
      else if (mode === "vol") out = rollingVol(vals, item.frequency);
      else out = vals.slice();
      return { key: key, item: item, pts: pts, vals: vals, out: out, color: COLORS[i], mode: mode };
    }).filter(function (s) { return s.pts.length > 1; });
  }

  function render(host, opt) {
    host._fd = opt;
    var data = opt.data;
    var sets = buildSets(data, opt);
    host.innerHTML = "";
    if (!sets.length) {
      host.innerHTML = '<p class="chart-note">No data in this window.</p>';
      return;
    }

    var W = Math.max(host.clientWidth || 640, 320);
    var H = opt.height || 300;
    var L = 8, R = 54, T = 14, B = 26;
    var plotW = W - L - R, plotH = H - T - B;

    var t0 = Infinity, t1 = -Infinity;
    sets.forEach(function (s) {
      s.pts.forEach(function (p) {
        var t = day(p[0]);
        if (t < t0) t0 = t;
        if (t > t1) t1 = t;
      });
    });
    if (!isFinite(t0) || t1 <= t0) t1 = t0 + 86400000;

    var all = [];
    sets.forEach(function (s) {
      s.out.forEach(function (v) { if (v != null && isFinite(v)) all.push(v); });
    });
    var logOk = opt.scale === "log" && all.length && all.every(function (v) { return v > 0; });
    var lo = Math.min.apply(null, all), hi = Math.max.apply(null, all);
    if (logOk) {
      lo = lo / 1.04; hi = hi * 1.04;
    } else {
      var pad = (hi - lo) * 0.08 || 1;
      lo -= pad; hi += pad;
    }
    if (hi === lo) { hi += 1; lo -= 1; }

    function xOf(iso) { return L + ((day(iso) - t0) / (t1 - t0)) * plotW; }
    function yOf(v) {
      if (logOk) {
        var a = (Math.log(v) - Math.log(lo)) / (Math.log(hi) - Math.log(lo));
        return T + (1 - a) * plotH;
      }
      return T + (1 - (v - lo) / (hi - lo)) * plotH;
    }

    var out = ['<svg viewBox="0 0 ' + W + " " + H + '" width="' + W + '" height="' + H +
      '" role="img" aria-label="' + (opt.ariaLabel || "Time series chart") + '"' +
      ' font-family="' + FONT + '">'];

    var re = data.recessions || [];
    if ((opt.overlays || []).indexOf("re") >= 0) {
      re.forEach(function (span) {
        var a = Math.max(day(span[0]), t0), b = Math.min(day(span[1]), t1);
        if (b <= a) return;
        var x1 = L + ((a - t0) / (t1 - t0)) * plotW;
        var x2 = L + ((b - t0) / (t1 - t0)) * plotW;
        out.push('<rect x="' + x1.toFixed(1) + '" y="' + T + '" width="' + Math.max(x2 - x1, 1).toFixed(1) +
          '" height="' + plotH + '" fill="' + C.band + '"/>');
      });
    }

    for (var g = 0; g <= 3; g++) {
      var yv = T + (g / 3) * plotH;
      var val = logOk
        ? Math.exp(Math.log(hi) - (g / 3) * (Math.log(hi) - Math.log(lo)))
        : hi - (g / 3) * (hi - lo);
      var digits = Math.abs(val) >= 100 ? 0 : 2;
      out.push('<line x1="' + L + '" y1="' + yv.toFixed(1) + '" x2="' + (W - R) + '" y2="' + yv.toFixed(1) +
        '" stroke="' + C.hair + '" stroke-width="1"/>');
      out.push('<text x="' + (W - R + 7) + '" y="' + (yv + 3.5).toFixed(1) + '" font-size="10" fill="' +
        C.dim + '">' + FD.fmt(val, digits) + "</text>");
    }

    var events = (opt.overlays || []).indexOf("ev") >= 0 ? (opt.events || []) : [];
    var marks = [];
    events.forEach(function (ev) {
      var t = day(ev.date);
      if (t < t0 || t > t1) return;
      marks.push({ x: L + ((t - t0) / (t1 - t0)) * plotW, ev: ev });
    });
    var eventSvg = [];
    if (marks.length > 120) {
      var seenYear = {};
      marks.forEach(function (m) {
        var y = m.ev.date.slice(0, 4);
        if (seenYear[y]) return;
        seenYear[y] = 1;
        eventSvg.push('<line x1="' + m.x.toFixed(1) + '" y1="' + (T + plotH - 9) + '" x2="' + m.x.toFixed(1) +
          '" y2="' + (T + plotH) + '" stroke="' + C.event + '" stroke-width="1.5" stroke-opacity="0.75"/>');
      });
    } else {
      marks.forEach(function (m) {
        eventSvg.push('<line x1="' + m.x.toFixed(1) + '" y1="' + T + '" x2="' + m.x.toFixed(1) + '" y2="' + (T + plotH) +
          '" stroke="' + C.event + '" stroke-width="1" stroke-dasharray="2 3" stroke-opacity="0.55"/>');
      });
    }

    if (sets[0].mode === "pct") {
      var y0 = yOf(0);
      out.push('<line x1="' + L + '" y1="' + y0.toFixed(1) + '" x2="' + (W - R) + '" y2="' + y0.toFixed(1) +
        '" stroke="' + C.rule + '" stroke-width="1"/>');
    }

    sets.forEach(function (s) {
      var d = "", pen = false;
      s.pts.forEach(function (p, i) {
        var v = s.out[i];
        if (v == null || !isFinite(v)) { pen = false; return; }
        d += (pen ? "L" : "M") + xOf(p[0]).toFixed(1) + " " + yOf(v).toFixed(1) + " ";
        pen = true;
      });
      d = d.trim();
      if (sets.length === 1 && s.mode === "level") {
        var firstX = null, lastX = null;
        s.pts.forEach(function (p, i) {
          if (s.out[i] == null) return;
          if (firstX == null) firstX = xOf(p[0]);
          lastX = xOf(p[0]);
        });
        if (firstX != null) {
          out.push('<path d="' + d + " L" + lastX.toFixed(1) + " " + (T + plotH) + " L" + firstX.toFixed(1) + " " +
            (T + plotH) + ' Z" fill="' + s.color + '" opacity="0.06"/>');
        }
      }
      out.push('<path d="' + d + '" fill="none" stroke="' + s.color +
        '" stroke-width="1.4" stroke-linejoin="round" stroke-linecap="round"/>');
    });

    out.push(eventSvg.join(""));

    var ticks = W < 560 ? 2 : 3;
    for (var k = 0; k <= ticks; k++) {
      var t = t0 + (k / ticks) * (t1 - t0);
      var dt = new Date(t);
      var label = dt.getUTCFullYear() + "-" + String(dt.getUTCMonth() + 1).padStart(2, "0");
      var x = L + (k / ticks) * plotW;
      out.push('<text x="' + x.toFixed(1) + '" y="' + (H - 8) + '" font-size="10" fill="' + C.dim + '"' +
        (k === 0 ? "" : k === ticks ? ' text-anchor="end"' : ' text-anchor="middle"') + ">" + label + "</text>");
    }

    out.push('<g class="cross"></g></svg>');
    host.innerHTML = out.join("");
    var svg = host.querySelector("svg");

    var tip = document.createElement("div");
    tip.className = "tip";
    tip.hidden = true;
    host.appendChild(tip);
    var live = document.createElement("p");
    live.className = "visually-hidden";
    live.setAttribute("aria-live", "polite");
    live.style.cssText = "position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)";
    host.appendChild(live);

    var focusIdx = -1;
    var ref = sets[0];

    function nearestTime(iso, s) {
      var target = day(iso), best = 0, bd = Infinity;
      for (var i = 0; i < s.pts.length; i++) {
        var d = Math.abs(day(s.pts[i][0]) - target);
        if (d < bd) { bd = d; best = i; }
      }
      return best;
    }

    function showAt(idx) {
      if (idx < 0 || idx >= ref.pts.length) return;
      focusIdx = idx;
      var iso = ref.pts[idx][0];
      var x = xOf(iso);
      var cross = svg.querySelector(".cross");
      var lines = ['<line x1="' + x.toFixed(1) + '" y1="' + T + '" x2="' + x.toFixed(1) + '" y2="' + (T + plotH) +
        '" stroke="' + C.muted + '" stroke-width="1" stroke-dasharray="3 3"/>'];
      var rows = ["<div><b>" + iso + "</b></div>"];
      var spoken = [iso];
      sets.forEach(function (s) {
        var i = nearestTime(iso, s);
        var v = s.out[i];
        if (v != null) {
          lines.push('<circle cx="' + xOf(s.pts[i][0]).toFixed(1) + '" cy="' + yOf(v).toFixed(1) +
            '" r="2.8" fill="' + s.color + '"/>');
        }
        var name = FD.t(s.item.tile_en, s.item.tile_zh);
        var raw = s.vals[i];
        rows.push('<div><span style="color:' + s.color + '">■</span> ' + name + " " +
          FD.fmt(raw, s.item.decimals) + (s.item.unit || "") + "</div>");
        spoken.push(name + " " + FD.fmt(raw, s.item.decimals));
      });
      cross.innerHTML = lines.join("");
      tip.innerHTML = rows.join("");
      tip.hidden = false;
      var lastY = T + plotH / 2;
      sets.forEach(function (s) {
        var i = nearestTime(iso, s);
        if (s.out[i] != null) lastY = Math.min(lastY, yOf(s.out[i]));
      });
      var left = Math.min(Math.max(x, 70), W - 70);
      tip.style.left = (left / W) * 100 + "%";
      tip.style.top = (lastY / H) * 100 + "%";
      tip.style.transform = "translate(-50%, -100%) translateY(-10px)";
      live.textContent = spoken.join(", ");
    }

    function hide() {
      svg.querySelector(".cross").innerHTML = "";
      tip.hidden = true;
    }

    svg.addEventListener("pointermove", function (e) {
      var rect = svg.getBoundingClientRect();
      var px = ((e.clientX - rect.left) / rect.width) * W;
      var best = 0, bd = Infinity;
      for (var i = 0; i < ref.pts.length; i++) {
        var d = Math.abs(xOf(ref.pts[i][0]) - px);
        if (d < bd) { bd = d; best = i; }
      }
      showAt(best);
    });
    svg.addEventListener("pointerleave", hide);

    svg.addEventListener("click", function (e) {
      if (!marks.length || !opt.onEvent) return;
      var rect = svg.getBoundingClientRect();
      var px = ((e.clientX - rect.left) / rect.width) * W;
      var hit = null;
      marks.forEach(function (m) { if (Math.abs(m.x - px) < 6) hit = m.ev; });
      if (hit) opt.onEvent(hit);
    });

    host.addEventListener("keydown", function (e) {
      if (e.key === "ArrowRight") { showAt(Math.min(focusIdx + 1, ref.pts.length - 1)); e.preventDefault(); }
      else if (e.key === "ArrowLeft") { showAt(Math.max(focusIdx - 1, 0)); e.preventDefault(); }
      else if (e.key === "Home") { showAt(0); e.preventDefault(); }
      else if (e.key === "End") { showAt(ref.pts.length - 1); e.preventDefault(); }
      else if (e.key === "Escape") hide();
    });
    host.addEventListener("focus", function () { if (focusIdx < 0) showAt(ref.pts.length - 1); });
    host.addEventListener("blur", hide);

    host._geom = { W: W, H: H, xOf: xOf, yOf: yOf, sets: sets, opt: opt };
  }

  function svgText(host) {
    var g = host._geom;
    if (!g) return "";
    var svg = host.querySelector("svg");
    var clone = svg.cloneNode(true);
    clone.querySelector(".cross").remove();
    var title = g.opt.title || "FOMC Data";
    var sub = g.opt.subtitle || "";
    var extra = 40;
    var wrap = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    wrap.setAttribute("xmlns", "http://www.w3.org/2000/svg");
    wrap.setAttribute("width", g.W);
    wrap.setAttribute("height", g.H + extra);
    wrap.setAttribute("viewBox", "0 0 " + g.W + " " + (g.H + extra));
    wrap.setAttribute("font-family", FONT);
    wrap.innerHTML = '<rect width="100%" height="100%" fill="' + C.paper + '"/>' +
      '<text x="8" y="18" font-size="13" fill="' + C.ink + '">' + title + "</text>" +
      '<text x="8" y="33" font-size="10" fill="' + C.dim + '">' + sub + "</text>";
    clone.removeAttribute("style");
    clone.setAttribute("y", String(extra));
    wrap.appendChild(clone);
    var out = new XMLSerializer().serializeToString(wrap);
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + out;
  }

  function download(blob, name) {
    var a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(function () { URL.revokeObjectURL(a.href); }, 1000);
  }

  function exportSVG(host, name) {
    download(new Blob([svgText(host)], { type: "image/svg+xml" }), name + ".svg");
  }

  function exportPNG(host, name) {
    var markup = svgText(host);
    var g = host._geom;
    var img = new Image();
    var svg64 = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(markup);
    img.onload = function () {
      var scale = 2;
      var canvas = document.createElement("canvas");
      canvas.width = g.W * scale;
      canvas.height = (g.H + 40) * scale;
      var ctx = canvas.getContext("2d");
      ctx.fillStyle = C.paper;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(function (blob) { if (blob) download(blob, name + ".png"); }, "image/png");
    };
    img.src = svg64;
  }

  var timer = null;
  window.addEventListener("resize", function () {
    clearTimeout(timer);
    timer = setTimeout(function () {
      document.querySelectorAll(".plot").forEach(function (host) {
        if (host._fd && host._fd.data) render(host, host._fd);
      });
    }, 160);
  });

  window.FDChart = { render: render, svg: svgText, png: exportPNG, exportSVG: exportSVG, download: download };
})();
