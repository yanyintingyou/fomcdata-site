document.addEventListener("DOMContentLoaded", function () {
  var MON = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  var data = null;
  var filter = "all";
  var byDate = {};

  function zh() { return document.documentElement.lang === "zh-CN"; }

  function md(iso) {
    var m = +iso.slice(5, 7), d = +iso.slice(8, 10);
    return zh() ? m + " 月 " + d + " 日" : MON[m - 1] + " " + d;
  }

  function span(ev) {
    var f = byDate[ev.meeting];
    if (!f) return md(ev.meeting);
    var start = f.start || f.date;
    if (start === f.date) return md(f.date);
    var m1 = +start.slice(5, 7), d1 = +start.slice(8, 10);
    var m2 = +f.date.slice(5, 7), d2 = +f.date.slice(8, 10);
    if (m1 === m2) return zh() ? m1 + " 月 " + d1 + "–" + d2 + " 日" : MON[m1 - 1] + " " + d1 + "–" + d2;
    return zh() ? m1 + " 月 " + d1 + " 日–" + m2 + " 月 " + d2 + " 日"
                : MON[m1 - 1] + " " + d1 + "–" + MON[m2 - 1] + " " + d2;
  }

  function labels(ev) {
    if (ev.type === "minutes") {
      return { title: FD.t("Minutes", "会议纪要"), sub: span(ev) + FD.t(" meeting", " 会议") };
    }
    if (ev.type === "beige") {
      return { title: FD.t("Beige Book", "褐皮书"), sub: "" };
    }
    return {
      title: FD.t("FOMC decision", "FOMC 决议"),
      sub: ev.sep ? FD.t("with projections", "含经济预测") : ""
    };
  }

  function chartHref(ev) {
    return "/dashboard?s=effr&r=1y&at=" + ev.date + "&ov=ev";
  }

  function links(ev, past) {
    var out = [];
    if (ev.type === "fomc") {
      if (ev.links.press) out.push([ev.links.press, FD.t("Press conf.", "发布会")]);
      if (ev.links.projections) out.push([ev.links.projections, FD.t("Projections", "预测")]);
      if (past) out.push([chartHref(ev), FD.t("Chart", "图表")]);
    }
    return out;
  }

  function row(ev, today) {
    var days = Math.round((Date.parse(ev.date + "T00:00:00Z") - Date.parse(today + "T00:00:00Z")) / 86400000);
    var past = ev.date <= today;
    var lab = labels(ev);
    var target = ev.type === "fomc" ? ev.links.statement : ev.url;

    var wrap = document.createElement("div");
    wrap.className = "cal-row" + (ev.date < today ? " past" : "") + (days >= 0 && days <= 30 ? " cal-soon" : "");

    var when = document.createElement("span");
    when.className = "cal-date";
    when.textContent = ev.date;

    var main = document.createElement(target || past ? "a" : "span");
    main.className = "cal-main";
    if (target || past) {
      main.href = target || chartHref(ev);
      if (target) {
        main.target = "_blank";
        main.rel = "noopener";
      }
    }
    main.innerHTML = '<span class="cal-title">' + lab.title +
      (lab.sub ? '<span class="cal-sub">' + lab.sub + "</span>" : "") +
      (target ? '<span class="cal-out">&#8599;</span>' : "") + "</span>";

    var side = document.createElement("span");
    side.className = "cal-side";
    var tag = days === 0 ? FD.t("today", "今天") : days > 0 ? FD.t("in " + days + " days", days + " 天后") : "";
    side.innerHTML = '<span class="cal-links">' + links(ev, past).map(function (l) {
      return '<a href="' + l[0] + '"' + (l[0].charAt(0) === "/" ? "" : ' target="_blank" rel="noopener"') + ">" + l[1] + "</a>";
    }).join("") + '</span><span class="cal-tag">' + tag + "</span>";

    wrap.appendChild(when);
    wrap.appendChild(main);
    wrap.appendChild(side);
    return wrap;
  }

  function counts(events) {
    var n = { fomc: 0, minutes: 0, beige: 0 };
    events.forEach(function (e) { n[e.type] += 1; });
    var parts = [];
    if (n.fomc) parts.push(n.fomc + FD.t(" decisions", " 次决议"));
    if (n.minutes) parts.push(n.minutes + FD.t(" minutes", " 份纪要"));
    if (n.beige) parts.push(n.beige + FD.t(" Beige Books", " 期褐皮书"));
    return parts.join(" · ");
  }

  function nextUp(today) {
    var box = document.getElementById("next");
    var upcoming = data.events.filter(function (e) { return e.date >= today; })
      .sort(function (a, b) { return a.date < b.date ? -1 : 1; })[0];
    if (!upcoming) { box.hidden = true; return; }
    var lab = labels(upcoming);
    var days = Math.round((Date.parse(upcoming.date + "T00:00:00Z") - Date.parse(today + "T00:00:00Z")) / 86400000);
    var cd = days === 0 ? FD.t("today", "今天") : FD.t("in " + days + " days", days + " 天后");
    box.hidden = false;
    box.innerHTML = '<span class="cal-next-label">' + FD.t("Next", "下一项") + "</span>" +
      '<span class="cal-next-body">' + upcoming.date + " · " + lab.title +
      (lab.sub ? " · " + lab.sub : "") + "</span>" +
      '<span class="cal-next-cd">' + cd + "</span>";
  }

  function draw() {
    var list = document.getElementById("list");
    list.innerHTML = "";
    var today = new Date().toISOString().slice(0, 10);
    var thisYear = today.slice(0, 4);
    var years = {};
    data.events.filter(function (e) {
      return filter === "all" || e.type === filter;
    }).forEach(function (ev) {
      var y = ev.date.slice(0, 4);
      (years[y] = years[y] || []).push(ev);
    });

    Object.keys(years).sort().reverse().forEach(function (y) {
      var evs = years[y].slice().sort(function (a, b) {
        return a.date === b.date ? (a.type < b.type ? -1 : 1) : (a.date < b.date ? -1 : 1);
      });
      var det = document.createElement("details");
      det.className = "cal-year-block";
      det.open = y >= thisYear;

      var sum = document.createElement("summary");
      sum.className = "cal-year";
      sum.innerHTML = '<span class="cal-arrow">&#9654;</span><span>' + y + "</span>" +
        '<span class="cal-count">' + counts(evs) + "</span>";
      det.appendChild(sum);
      evs.forEach(function (ev) { det.appendChild(row(ev, today)); });
      list.appendChild(det);
    });

    if (!Object.keys(years).length) {
      list.innerHTML = '<p class="chart-note">' +
        FD.t("Nothing in this category yet.", "这一类暂时还没有条目。") + "</p>";
    }

    nextUp(today);
    document.getElementById("meta").textContent = FD.t("Compiled ", "整理于 ") + (data.updated || "");
  }

  function setFilter(kind) {
    filter = ["fomc", "minutes", "beige"].indexOf(kind) >= 0 ? kind : "all";
    document.querySelectorAll("#filter .chip").forEach(function (c) {
      c.setAttribute("aria-pressed", c.dataset.kind === filter ? "true" : "false");
    });
    var url = filter === "all" ? location.pathname : location.pathname + "?f=" + filter;
    history.replaceState(null, "", url);
    draw();
  }

  document.getElementById("filter").addEventListener("click", function (e) {
    var b = e.target.closest(".chip");
    if (b) setFilter(b.dataset.kind);
  });

  fetch("/data/calendar.json", { cache: "no-cache" })
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (json) {
      data = json;
      data.events.forEach(function (e) { if (e.type === "fomc") byDate[e.date] = e; });
      setFilter(new URLSearchParams(location.search).get("f"));
      FD.onLang = draw;
    })
    .catch(function () {
      document.getElementById("list").innerHTML = '<p class="chart-note">Calendar unavailable.</p>';
    });
});
