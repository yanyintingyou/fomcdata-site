document.addEventListener("DOMContentLoaded", function () {
  var state = FD.readState({ keys: ["dgs10"], range: "1y", scale: "linear", mode: "level", overlays: ["re"] });
  var data = null, events = [], query = "";
  var plot = document.getElementById("plot");
  var atInput = document.getElementById("at");
  var atNote = document.getElementById("at-note");
  var CATS = ["rates", "inflation", "labor", "markets", "commodities"];
  var LABEL = {
    rates: ["Policy rates", "政策利率"],
    inflation: ["Inflation", "通胀"],
    labor: ["Employment", "就业"],
    markets: ["Markets", "市场"],
    commodities: ["Commodities", "商品"]
  };

  function allPercent() {
    return state.keys.every(function (k) { return data.series[k] && data.series[k].unit === "%"; });
  }

  function normalizeState() {
    if (state.keys.length > 1) state.mode = allPercent() ? "diff" : "norm";
    else if (state.mode === "norm") state.mode = "level";
  }

  function syncButtons() {
    document.querySelectorAll("#chips .chip").forEach(function (b) {
      b.setAttribute("aria-pressed", state.keys.indexOf(b.dataset.key) >= 0 ? "true" : "false");
    });
    document.querySelectorAll("#ranges button").forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.range === state.range ? "true" : "false");
    });
    document.querySelectorAll("#scale button").forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.scale === state.scale ? "true" : "false");
    });
    document.querySelectorAll("#mode button").forEach(function (b) {
      b.disabled = state.keys.length > 1;
      b.setAttribute("aria-pressed", state.mode === b.dataset.mode ? "true" : "false");
    });
    document.querySelectorAll("#overlays button").forEach(function (b) {
      b.setAttribute("aria-pressed", state.overlays.indexOf(b.dataset.ov) >= 0 ? "true" : "false");
    });
  }

  function renderChips() {
    var box = document.getElementById("chips");
    box.innerHTML = "";
    var q = query.trim().toLowerCase();
    var groups = {};
    CATS.forEach(function (c) { groups[c] = []; });
    Object.keys(data.series).forEach(function (k) {
      var it = data.series[k];
      if (it.hidden) return;
      var hay = (it.label_en + " " + it.label_zh + " " + it.tile_en + " " + it.tile_zh + " " + it.source).toLowerCase();
      if (q && hay.indexOf(q) < 0) return;
      (groups[it.category] || groups.rates).push(k);
    });
    CATS.forEach(function (cat) {
      if (!groups[cat].length) return;
      var wrap = document.createElement("div");
      wrap.className = "chip-group";
      var lab = document.createElement("span");
      lab.className = "chip-cat";
      lab.textContent = FD.t(LABEL[cat][0], LABEL[cat][1]);
      wrap.appendChild(lab);
      groups[cat].forEach(function (k) {
        var it = data.series[k];
        var b = document.createElement("button");
        b.type = "button";
        b.className = "chip";
        b.dataset.key = k;
        b.textContent = FD.t(it.tile_en, it.tile_zh);
        wrap.appendChild(b);
      });
      box.appendChild(wrap);
    });
  }

  function syncAt() {
    var it = data.series[state.keys[0]];
    if (it && it.points && it.points.length) {
      atInput.min = it.points[0][0];
      atInput.max = it.points[it.points.length - 1][0];
    }
    if (document.activeElement !== atInput) atInput.value = state.at || "";
  }

  function applyAt(value) {
    if (!value) {
      state.at = null;
      atNote.hidden = true;
      atNote.textContent = "";
      draw();
      return;
    }
    FD.ensure([state.keys[0]]).then(function () {
      var it = data.series[state.keys[0]];
      var snapped = it && it.points ? FD.nearest(it, value, 2) : value;
      state.at = snapped;
      if (snapped === value) {
        atNote.hidden = true;
        atNote.textContent = "";
      } else {
        atNote.hidden = false;
        atNote.textContent = FD.t(
          "No observation on " + value + ". Window centered on " + snapped + ".",
          value + " 没有观测值，窗口已定位到最近的 " + snapped + "。");
      }
      draw();
    });
  }

  function render() {
    normalizeState();
    FD.writeState(state);
    syncAt();
    syncButtons();
    var names = state.keys.map(function (k) {
      var it = data.series[k];
      return FD.t(it.label_en, it.label_zh);
    });
    FDChart.render(plot, {
      data: data,
      keys: state.keys,
      range: state.range,
      scale: state.scale,
      mode: state.mode,
      overlays: state.overlays,
      events: events,
      at: state.at,
      height: 360,
      ariaLabel: names.join(", "),
      title: names.join(" · ") + " · " + state.range.toUpperCase(),
      subtitle: FD.t("Source: ", "来源：") + state.keys.map(function (k) { return data.series[k].source; }).join(", "),
      onEvent: function (ev) { state.at = state.at === ev.date ? null : ev.date; draw(); }
    });

    var legend = document.getElementById("legend");
    legend.innerHTML = state.keys.map(function (k, i) {
      var it = data.series[k];
      return '<span class="c' + i + '"><i></i>' + FD.t(it.label_en, it.label_zh) + "</span>";
    }).join("");
    if (state.at) {
      var tag = document.createElement("span");
      tag.className = "dim";
      tag.textContent = FD.t("centered on ", "以 ") + state.at + FD.t("", " 为中心");
      legend.appendChild(tag);
    }

    renderStats();
    renderTable();
    document.getElementById("meta").textContent = data.updated
      ? (FD.t("Last run ", "最近一次运行 ") + data.updated.slice(0, 16).replace("T", " ") + " UTC")
      : "";
    var stale = state.keys.filter(function (k) { return data.series[k].stale; });
    var note = document.getElementById("note");
    if (stale.length) {
      note.textContent = FD.t("Refresh failed for: ", "抓取未完成的指标：") +
        stale.map(function (k) { return data.series[k].tile_en; }).join(", ") + ".";
    } else if (state.keys.length > 1 && state.mode === "diff") {
      note.textContent = FD.t("Change from the window start, in percentage points. Hover for levels.",
        "相对窗口起点的变化，单位为百分点。悬停可读水平值。");
    } else if (state.keys.length > 1) {
      note.textContent = FD.t("Normalized to 100 at the start of the window. Hover for raw values.",
        "以窗口起点为 100 归一化。悬停可读原始值。");
    } else {
      note.textContent = FD.t("Hover or drag for values. Arrow keys move point by point when the chart is focused.",
        "悬停或拖动读取数值。图表获得焦点后可用左右方向键逐点移动。");
    }
  }

  function draw() {
    FD.ensure(state.keys).then(render);
  }

  function renderStats() {
    var box = document.getElementById("stats");
    box.innerHTML = "";
    var cells = [];
    if (state.keys.length === 1) {
      var it = data.series[state.keys[0]];
      var pts = FD.windowPoints(it, state.range, state.at);
      var st = FD.stats(pts);
      if (!st) return;
      cells.push([FD.t("High", "最高"), FD.fmt(st.high, it.decimals) + (it.unit || "")]);
      cells.push([FD.t("Low", "最低"), FD.fmt(st.low, it.decimals) + (it.unit || "")]);
      cells.push([FD.t("Mean", "均值"), FD.fmt(st.mean, it.decimals) + (it.unit || "")]);
      if (it.unit === "%") {
        var pp = pts[pts.length - 1][1] - pts[0][1];
        cells.push([FD.t("Change", "区间变化"), (pp >= 0 ? "+" : "") + FD.fmt(pp, 2) + " pp"]);
        var peak = pts[0][1], worst = 0;
        pts.forEach(function (p) {
          if (p[1] > peak) peak = p[1];
          if (p[1] - peak < worst) worst = p[1] - peak;
        });
        cells.push([FD.t("Max drawdown", "最大回撤"), FD.fmt(worst, 2) + " pp"]);
      } else {
        cells.push([FD.t("Change", "区间涨跌"), (st.change >= 0 ? "+" : "") + FD.fmt(st.change, 2) + "%"]);
        cells.push([FD.t("Max drawdown", "最大回撤"), FD.fmt(st.drawdown, 2) + "%"]);
      }
      cells.push([FD.t("Points", "点数"), String(st.n)]);
    } else {
      state.keys.forEach(function (k) {
        var it = data.series[k];
        var pts = FD.windowPoints(it, state.range, state.at);
        var st = FD.stats(pts);
        if (!st) return;
        var val = it.unit === "%" ? pts[pts.length - 1][1] - pts[0][1] : st.change;
        cells.push([FD.t(it.tile_en, it.tile_zh), (val >= 0 ? "+" : "") + FD.fmt(val, 2) + (it.unit === "%" ? " pp" : "%")]);
      });
    }
    cells.forEach(function (c) {
      var wrap = document.createElement("div");
      wrap.className = "stat";
      wrap.innerHTML = "<dt>" + c[0] + "</dt><dd>" + c[1] + "</dd>";
      box.appendChild(wrap);
    });
  }

  function renderTable() {
    var box = document.getElementById("recent");
    if (state.keys.length !== 1) { box.innerHTML = ""; return; }
    var it = data.series[state.keys[0]];
    var pts = FD.windowPoints(it, state.range, state.at).slice(-12).reverse();
    var rows = pts.map(function (p) {
      return "<tr><td>" + p[0] + "</td><td>" + FD.fmt(p[1], it.decimals) + (it.unit || "") + "</td></tr>";
    }).join("");
    box.innerHTML = '<table class="data"><thead><tr><th>' + FD.t("Date", "日期") + "</th><th>" +
      FD.t(it.tile_en, it.tile_zh) + "</th></tr></thead><tbody>" + rows + "</tbody></table>";
  }

  function fileBase() {
    return "fomcdata_" + state.keys.join("-") + "_" + state.range + "_" + new Date().toISOString().slice(0, 10);
  }

  function exportCSV() {
    var lines = ["date," + state.keys.join(",")];
    var sets = state.keys.map(function (k) { return FD.windowPoints(data.series[k], state.range, state.at); });
    var map = {};
    sets.forEach(function (pts, i) {
      pts.forEach(function (p) { (map[p[0]] = map[p[0]] || [])[i] = p[1]; });
    });
    Object.keys(map).sort().forEach(function (d) {
      lines.push(d + "," + state.keys.map(function (_, i) { return map[d][i] == null ? "" : map[d][i]; }).join(","));
    });
    FDChart.download(new Blob([lines.join("\n")], { type: "text/csv" }), fileBase() + ".csv");
  }

  atInput.addEventListener("change", function () { applyAt(this.value); });
  document.getElementById("at-clear").addEventListener("click", function () { applyAt(""); });

  document.getElementById("search").addEventListener("input", function () {
    query = this.value;
    renderChips();
  });

  document.getElementById("chips").addEventListener("click", function (e) {
    var b = e.target.closest(".chip");
    if (!b) return;
    var k = b.dataset.key;
    var i = state.keys.indexOf(k);
    if (i >= 0) {
      if (state.keys.length > 1) state.keys.splice(i, 1);
    } else if (state.keys.length < 4) {
      state.keys.push(k);
    }
    draw();
  });

  document.getElementById("ranges").addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (b) { state.range = b.dataset.range; draw(); }
  });
  document.getElementById("scale").addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (b) { state.scale = b.dataset.scale; draw(); }
  });
  document.getElementById("mode").addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (b && !b.disabled) { state.mode = b.dataset.mode; draw(); }
  });
  document.getElementById("overlays").addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (!b) return;
    var i = state.overlays.indexOf(b.dataset.ov);
    if (i >= 0) state.overlays.splice(i, 1);
    else state.overlays.push(b.dataset.ov);
    draw();
  });

  document.getElementById("csv").addEventListener("click", exportCSV);
  document.getElementById("png").addEventListener("click", function () { FDChart.png(plot, fileBase()); });
  document.getElementById("svg").addEventListener("click", function () { FDChart.exportSVG(plot, fileBase()); });
  document.getElementById("copy").addEventListener("click", function () {
    var btn = this;
    navigator.clipboard.writeText(location.href).then(function () {
      var old = btn.innerHTML;
      btn.textContent = FD.t("Copied", "已复制");
      setTimeout(function () { btn.innerHTML = old; }, 1400);
    });
  });

  FD.onLang = function () { if (data) { renderChips(); draw(); } };

  Promise.all([
    FD.load(),
    fetch("/data/calendar.json", { cache: "no-cache" }).then(function (r) { return r.ok ? r.json() : { events: [] }; }).catch(function () { return { events: [] }; })
  ]).then(function (res) {
    data = res[0];
    events = (res[1].events || []).filter(function (e) { return e.type === "fomc"; });
    state.keys = state.keys.filter(function (k) { return data.series[k]; });
    if (!state.keys.length) state.keys = ["dgs10"];
    renderChips();
    if (state.at) applyAt(state.at);
    else draw();
  }).catch(function () {
    plot.innerHTML = '<p class="chart-note">Data unavailable.</p>';
  });
});
