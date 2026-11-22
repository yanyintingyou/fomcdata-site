document.addEventListener("DOMContentLoaded", function () {
  var data = null, current = "dgs10", range = "1y";
  var plot = document.getElementById("home-plot");

  function render() {
    var item = data.series[current];
    if (!item || !item.points) return;
    var zh = document.documentElement.lang === "zh-CN";
    FDChart.render(plot, {
      data: data,
      keys: [current],
      range: range,
      scale: "linear",
      mode: "level",
      overlays: [],
      height: 250,
      ariaLabel: FD.t(item.label_en, item.label_zh),
      title: FD.t(item.label_en, item.label_zh) + " · " + range.toUpperCase(),
      subtitle: FD.t("Source: ", "来源：") + item.source + " · " + item.asof
    });
    document.getElementById("chart-label").textContent =
      (zh ? item.label_zh : item.label_en) + " · " + FD.fmt(item.last, item.decimals) +
      (item.unit ? item.unit : "") + " · " + item.asof;
    var stale = document.getElementById("stale-note");
    stale.hidden = !item.stale;
    stale.textContent = item.stale
      ? (zh ? "最近一次抓取未完成，图表显示截至 " + item.asof + " 的数据。" : "The latest refresh did not complete. Chart shows data through " + item.asof + ".")
      : "";
    document.getElementById("run-time").textContent = data.updated
      ? " · " + (zh ? "最近一次运行 " : "Last run ") + data.updated.slice(0, 16).replace("T", " ") + " UTC"
      : "";
    document.querySelectorAll(".tile").forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.key === current ? "true" : "false");
    });
    document.querySelectorAll("#ranges button").forEach(function (b) {
      b.setAttribute("aria-pressed", b.dataset.range === range ? "true" : "false");
    });
  }

  function draw() {
    FD.ensure([current]).then(render);
  }

  function tiles() {
    var box = document.getElementById("tiles");
    box.innerHTML = "";
    Object.keys(data.series).forEach(function (key) {
      var item = data.series[key];
      if (!item.featured) return;
      var b = document.createElement("button");
      b.type = "button";
      b.className = "tile";
      b.dataset.key = key;
      var last30 = (item.points || []).slice(-30).map(function (p) { return p[1]; });
      var d = "";
      if (last30.length > 1) {
        var min = Math.min.apply(null, last30), max = Math.max.apply(null, last30);
        var span = max - min || 1;
        d = last30.map(function (v, i) {
          return (i ? "L" : "M") + (i * 100 / (last30.length - 1)).toFixed(1) + " " +
            (26 - ((v - min) / span) * 22).toFixed(1);
        }).join(" ");
      }
      var flag = item.stale
        ? '<span class="flag" role="img" aria-label="' + FD.t("Latest refresh failed", "最近一次抓取未完成") + '"></span>'
        : "";
      b.innerHTML =
        '<span class="tile-name"><span class="en">' + item.tile_en + '</span><span class="zh">' + item.tile_zh + "</span>" + flag + "</span>" +
        '<span class="tile-value">' + FD.fmt(item.last, item.decimals) +
          (item.unit ? '<span class="unit">' + item.unit + "</span>" : "") + "</span>" +
        '<span class="tile-delta">' + FD.deltaText(item) + "</span>" +
        '<svg class="spark" viewBox="0 0 100 28" preserveAspectRatio="none" aria-hidden="true"><path d="' + d +
        '" fill="none" stroke="currentColor" stroke-width="1" vector-effect="non-scaling-stroke"/></svg>';
      box.appendChild(b);
    });
  }

  document.getElementById("tiles").addEventListener("click", function (e) {
    var b = e.target.closest(".tile");
    if (!b) return;
    current = b.dataset.key;
    draw();
  });

  document.getElementById("ranges").addEventListener("click", function (e) {
    var b = e.target.closest("button");
    if (!b) return;
    range = b.dataset.range;
    draw();
  });

  FD.onLang = function () { if (data) { tiles(); draw(); } };

  FD.load().then(function (d) {
    data = d;
    var featured = Object.keys(data.series).filter(function (k) { return data.series[k].featured; });
    if (!data.series[current]) current = featured[0] || Object.keys(data.series)[0];
    document.getElementById("snapshot").hidden = false;
    FD.ensure(featured).then(function () {
      tiles();
      draw();
    });
  }).catch(function () {});
});
