(function () {
  "use strict";
  var FD = (window.FD = window.FD || {});
  var KEY = "fomcdata-lang";

  function isZh() {
    return document.documentElement.lang === "zh-CN";
  }

  FD.t = function (en, zh) {
    return isZh() ? zh : en;
  };

  FD.setLang = function (lang) {
    var zh = lang === "zh";
    document.documentElement.lang = zh ? "zh-CN" : "en";
    var b = document.body.dataset;
    if (b.titleZh && b.titleEn) document.title = zh ? b.titleZh : b.titleEn;
    var m = document.querySelector('meta[name="description"]');
    if (m && b.descEn) m.setAttribute("content", zh ? b.descZh || "" : b.descEn);
    document.querySelectorAll("[data-lang]").forEach(function (el) {
      el.setAttribute("aria-pressed", el.dataset.lang === (zh ? "zh" : "en") ? "true" : "false");
    });
    if (FD.onLang) FD.onLang();
  };

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-lang]").forEach(function (el) {
      el.addEventListener("click", function () {
        localStorage.setItem(KEY, el.dataset.lang);
        FD.setLang(el.dataset.lang);
      });
    });
    FD.setLang(localStorage.getItem(KEY) || "en");
  });
})();
