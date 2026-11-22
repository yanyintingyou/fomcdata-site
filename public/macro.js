document.addEventListener("DOMContentLoaded", function () {
  function spark(vals) {
    if (vals.length < 2) return "";
    var min = Math.min.apply(null, vals), max = Math.max.apply(null, vals);
    var span = max - min || 1;
    return vals.map(function (v, i) {
      return (i ? "L" : "M") + (i * 100 / (vals.length - 1)).toFixed(1) + " " +
        (30 - ((v - min) / span) * 26).toFixed(1);
    }).join(" ");
  }

  function draw(data) {
    Object.keys(data.series).forEach(function (k) {
      var it = data.series[k];
      if (!it.points) return;
      var box = document.getElementById("cat-" + it.category);
      if (!box) return;
      var a = document.createElement("a");
      a.className = "card";
      a.href = "/dashboard?s=" + k + "&r=5y";
      a.innerHTML =
        '<span class="name">' + FD.t(it.tile_en, it.tile_zh) + "</span>" +
        '<span class="value">' + FD.fmt(it.last, it.decimals) +
          (it.unit ? '<span class="unit">' + it.unit + "</span>" : "") + "</span>" +
        '<span class="sub"><span>' + FD.deltaText(it) + "</span><span>" + it.asof + "</span></span>" +
        '<svg class="spark" viewBox="0 0 100 30" preserveAspectRatio="none" aria-hidden="true"><path d="' +
          spark(it.points.slice(-90).map(function (p) { return p[1]; })) +
          '" fill="none" stroke="currentColor" stroke-width="1" vector-effect="non-scaling-stroke"/></svg>';
      box.appendChild(a);
    });
    document.getElementById("meta").textContent = data.updated
      ? FD.t("Last run ", "最近一次运行 ") + data.updated.slice(0, 16).replace("T", " ") + " UTC"
      : "";
    document.querySelectorAll(".cards").forEach(function (c) {
      if (!c.children.length) c.closest("section").hidden = true;
    });
  }

  FD.load().then(function (data) {
    FD.ensure(Object.keys(data.series)).then(function () {
      draw(data);
      FD.onLang = function () {
        document.querySelectorAll(".cards").forEach(function (c) { c.innerHTML = ""; });
        draw(data);
      };
    });
  }).catch(function () {});
});
