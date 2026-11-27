/* 集页 · 版式选择与应用(D65)
 *
 * 契约:
 *  - 选择优先级:?layout= 预览 > localStorage.jiye.layout > SITE_CONFIG.default_layout > TEMPLATES.default;
 *  - 只读/写自己的键,不碰 jiye.theme;?layout= 只预览,不写存储;
 *  - 版式 CSS 追加在 <head> 末尾(晚于 style.css / pages/*.css),同权重规则自然覆盖;
 *  - 文件缺失或注册表没有时回退 standard,保证老部署与半成品版式不白屏。
 */
(function () {
  'use strict';

  var KEY = 'jiye.layout';
  var FALLBACK = 'standard';
  var REG = window.TEMPLATES || {};
  var LIST = REG.list || {};

  function has(key) {
    return !!key && Object.prototype.hasOwnProperty.call(LIST, key);
  }

  function queryKey() {
    try {
      return new URLSearchParams(location.search).get('layout') || '';
    } catch (e) {
      return '';
    }
  }

  function storedKey() {
    try {
      return localStorage.getItem(KEY) || '';
    } catch (e) {
      return '';
    }
  }

  function siteKey() {
    var cfg = window.SITE_CONFIG;
    return cfg && cfg.default_layout ? cfg.default_layout : '';
  }

  function resolve() {
    var q = queryKey();
    if (has(q)) return { key: q, preview: true };
    var s = storedKey();
    if (has(s)) return { key: s, preview: false };
    var d = siteKey();
    if (has(d)) return { key: d, preview: false };
    var def = REG.default;
    return { key: has(def) ? def : FALLBACK, preview: false };
  }

  function fileOf(key) {
    return has(key) && LIST[key].file ? LIST[key].file : 'assets/layouts/standard.css';
  }

  function currentKey() {
    return document.documentElement.getAttribute('data-layout') || FALLBACK;
  }

  function updateSwitch() {
    var wrap = document.querySelector('.layout-switch');
    if (!wrap) return;
    var now = currentKey();
    wrap.querySelectorAll('.layout-btn').forEach(function (btn) {
      var on = btn.getAttribute('data-layout-choice') === now;
      btn.classList.toggle('active', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }

  function apply(key, persist) {
    if (!has(key)) key = has(REG.default) ? REG.default : FALLBACK;
    if (persist) {
      try { localStorage.setItem(KEY, key); } catch (e) { /* 隐私模式忽略 */ }
    }
    document.documentElement.setAttribute('data-layout', key);
    document.documentElement.removeAttribute('data-layout-fallback');

    var link = document.getElementById('layout-css');
    if (!link) {
      link = document.createElement('link');
      link.id = 'layout-css';
      link.rel = 'stylesheet';
      (document.head || document.documentElement).appendChild(link);
    }
    // 每次换 href 都重置回调,避免上一版的 onerror 误伤
    link.onerror = function () {
      if (key === FALLBACK) return;
      link.onerror = null;
      document.documentElement.setAttribute('data-layout', FALLBACK);
      document.documentElement.setAttribute('data-layout-fallback', key);
      link.href = fileOf(FALLBACK);
      updateSwitch();
      try {
        document.dispatchEvent(new CustomEvent('jiye:layout-fallback', { detail: { from: key, to: FALLBACK } }));
      } catch (e) { /* 老浏览器忽略 */ }
    };
    link.onload = function () {
      document.documentElement.removeAttribute('data-layout-fallback');
    };
    if (link.getAttribute('href') !== fileOf(key)) link.setAttribute('href', fileOf(key));

    updateSwitch();
    try {
      document.dispatchEvent(new CustomEvent('jiye:layout', { detail: { key: key, preview: !persist } }));
    } catch (e) { /* 老浏览器忽略 */ }
  }

  function renderSwitch() {
    var footer = document.querySelector('.site-footer:not(.mine-footer) .wrap');
    if (!footer || footer.querySelector('.layout-switch')) return;
    var keys = Object.keys(LIST);
    if (keys.length < 2) return;
    var wrap = document.createElement('div');
    wrap.className = 'layout-switch';
    var html = '<span>版式</span>';
    keys.forEach(function (key) {
      html += '<button type="button" class="layout-btn" data-layout-choice="' + key +
        '" aria-pressed="false">' + (LIST[key].label || key) + '</button>';
    });
    wrap.innerHTML = html;
    footer.appendChild(wrap);
    wrap.addEventListener('click', function (ev) {
      var btn = ev.target.closest && ev.target.closest('.layout-btn');
      if (!btn) return;
      var key = btn.getAttribute('data-layout-choice');
      if (!has(key)) return;
      // 手动选择后去掉 ?layout 预览参数,否则刷新仍被预览值覆盖
      try {
        var url = new URL(location.href);
        if (url.searchParams.has('layout')) {
          url.searchParams.delete('layout');
          history.replaceState(null, '', url.pathname + url.search + url.hash);
        }
      } catch (e) { /* file:// 或老浏览器忽略 */ }
      apply(key, true);
    });
    updateSwitch();
  }

  // head 内先应用,避免首屏先看到默认版式再跳
  var picked = resolve();
  apply(picked.key, false);

  function boot() {
    renderSwitch();
    apply(currentKey(), false);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  window.JiyeLayout = {
    list: function () { return Object.keys(LIST).map(function (k) { return { key: k, label: LIST[k].label, file: LIST[k].file }; }); },
    current: currentKey,
    resolve: resolve,
    set: function (key) { apply(key, true); }
  };
})();
