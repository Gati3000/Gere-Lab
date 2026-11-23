const Common = (() => {
  const get = (k, d) => { try { return localStorage.getItem(k) || d; } catch (e) { return d; } };
  const put = (k, v) => { try { localStorage.setItem(k, v); } catch (e) {} };
  let lang = get("lang", "pl"), theme = get("theme", "dark");
  const dict = {};
  const t = k => (dict[lang] && dict[lang][k]) || (dict.en && dict.en[k]) || k;
  async function load(code) {
    if (dict[code]) return;
    try { const r = await fetch("/Language/" + code + ".json", { cache: "no-store" }); dict[code] = await r.json(); }
    catch (e) { dict[code] = {}; console.error("lang load failed:", code, e); }
  }
  function apply() {
    document.documentElement.setAttribute("data-theme", theme);
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach(e => e.textContent = t(e.dataset.i18n));
    document.querySelectorAll("[data-i18n-ph]").forEach(e => e.placeholder = t(e.dataset.i18nPh));
    const tb = document.getElementById("themeBtn"); if (tb) tb.textContent = theme === "dark" ? t("light") : t("dark");
    const ls = document.getElementById("langSel"); if (ls) ls.value = lang;
    document.dispatchEvent(new Event("uichange"));
  }
  async function init() {
    document.documentElement.setAttribute("data-theme", theme);
    const tb = document.getElementById("themeBtn"), ls = document.getElementById("langSel");
    if (tb) tb.onclick = () => { theme = theme === "dark" ? "light" : "dark"; put("theme", theme); apply(); };
    if (ls) ls.onchange = async () => { lang = ls.value; put("lang", lang); await load(lang); apply(); };
    await Promise.all([load("en"), load(lang)]);
    apply();
  }
  return { t, init };
})();
