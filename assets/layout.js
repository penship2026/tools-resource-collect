/* 集页 · 版式选择与应用(D65)
 *
 * 契约:
 *  - 选择优先级:?layout= 预览 > 我的页专属版式(?view=mine 且设过) > localStorage.jiye.layout
 *    > SITE_CONFIG.default_layout > TEMPLATES.default;
 *  - 只读/写自己的键,不碰 jiye.theme;我的页版式用 jiye.mine.layout.v1,「跟随公开」时删除该键;
 *  - 版式 CSS 追加在 <head> 末尾(晚于 style.css / pages/*.css),同权重规则自然覆盖;
 *  - 文件缺失或注册表没有时回退 standard,保证老部署与半成品版式不白屏。
 */
(function () {
  'use strict';

  var KEY = 'jiye.layout';
  // 我的页专属版式(与公开版式互不影响);'inherit' 表示跟随公开版式
  var MINE_KEY = 'jiye.mine.layout.v1';
  var INHERIT = 'inherit';
  var FALLBACK = 'standard';
  var REG = window.TEMPLATES || {};
  var LIST = REG.list || {};

  function has(key) {
    return !!key && Object.prototype.hasOwnProperty.call(LIST, key);
  }

  // 展示清单由 site.yml display.visible_layouts 控制;旧部署缺字段时退回全部内置
  function visibleKeys() {
    var cfg = window.SITE_CONFIG && window.SITE_CONFIG.display;
    var keys = cfg && Array.isArray(cfg.visible_layouts) ? cfg.visible_layouts : [];
    keys = keys.filter(has);
    return keys.length ? keys : Object.keys(LIST);
  }

  function usable(key) {
    return has(key) && visibleKeys().indexOf(key) >= 0;
  }

  function defaultKey() {
    var d = REG.default;
    if (usable(d)) return d;
    if (usable('standard')) return 'standard';
    return visibleKeys()[0];
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

  function isMineView() {
    try {
      return new URLSearchParams(location.search).get('view') === 'mine';
    } catch (e) {
      return false;
    }
  }

  function storedMineChoice() {
    try {
      var v = localStorage.getItem(MINE_KEY) || '';
      return usable(v) ? v : INHERIT;
    } catch (e) {
      return INHERIT;
    }
  }

  function siteKey() {
    var cfg = window.SITE_CONFIG;
    return cfg && cfg.default_layout ? cfg.default_layout : '';
  }

  function resolve() {
    var q = queryKey();
    if (usable(q)) return { key: q, preview: true };
    // 我的页单独设过版式就优先用它,否则跟随公开版式
    if (isMineView()) {
      var mine = storedMineChoice();
      if (usable(mine)) return { key: mine, preview: false };
    }
    var s = storedKey();
    if (usable(s)) return { key: s, preview: false };
    var d = siteKey();
    if (usable(d)) return { key: d, preview: false };
    return { key: defaultKey(), preview: false };
  }

  function fileOf(key) {
    return usable(key) && LIST[key].file ? LIST[key].file : 'assets/layouts/standard.css';
  }

  function currentKey() {
    return document.documentElement.getAttribute('data-layout') || FALLBACK;
  }

  function updateSwitch() {
    var wrap = document.querySelector('.layout-switch');
    if (!wrap) return;
    var now = currentKey();
    var sel = wrap.querySelector('.layout-select');
    if (sel) sel.value = now;
    wrap.querySelectorAll('.layout-btn').forEach(function (btn) {
      var on = btn.getAttribute('data-layout-choice') === now;
      btn.classList.toggle('active', on);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }

  function apply(key, persist) {
    var fallback = defaultKey();
    if (!usable(key)) key = fallback;
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
      if (key === fallback) return;
      link.onerror = null;
      document.documentElement.setAttribute('data-layout', fallback);
      document.documentElement.setAttribute('data-layout-fallback', key);
      link.href = fileOf(fallback);
      updateSwitch();
      try {
        document.dispatchEvent(new CustomEvent('jiye:layout-fallback', { detail: { from: key, to: fallback } }));
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

  function clearPreviewParam() {
    if (typeof URL === 'undefined' || typeof history === 'undefined') return;
    try {
      var url = new URL(location.href);
      if (!url.searchParams.has('layout')) return;
      url.searchParams.delete('layout');
      history.replaceState(null, '', url.pathname + url.search + url.hash);
    } catch (e) { /* file:// 或老浏览器忽略 */ }
  }

  function renderSwitch() {
    var footer = document.querySelector('.site-footer:not(.mine-footer) .wrap');
    if (!footer || footer.querySelector('.layout-switch')) return;
    var keys = visibleKeys();
    if (keys.length < 2) return;
    var wrap = document.createElement('div');
    wrap.className = 'layout-switch';
    var html = '<span>页面版式</span>';
    if (keys.length >= 5) {
      // 5 套时按钮在 390px 溢出,改为下拉
      html += '<select class="layout-select" aria-label="页面版式">';
      keys.forEach(function (key) {
        html += '<option value="' + key + '">' + (LIST[key].label || key) + '</option>';
      });
      html += '</select>';
    } else {
      keys.forEach(function (key) {
        html += '<button type="button" class="layout-btn" data-layout-choice="' + key +
          '" aria-pressed="false">' + (LIST[key].label || key) + '</button>';
      });
    }
    wrap.innerHTML = html;
    footer.appendChild(wrap);
    wrap.addEventListener('change', function (ev) {
      var sel = ev.target.closest && ev.target.closest('.layout-select');
      if (!sel) return;
      if (!usable(sel.value)) return;
      clearPreviewParam();
      apply(sel.value, true);
    });
    wrap.addEventListener('click', function (ev) {
      var btn = ev.target.closest && ev.target.closest('.layout-btn');
      if (!btn) return;
      var key = btn.getAttribute('data-layout-choice');
      if (!usable(key)) return;
      // 手动选择后去掉 ?layout 预览参数,否则刷新仍被预览值覆盖
      clearPreviewParam();
      apply(key, true);
    });
    updateSwitch();
  }

  // head 内先应用,避免首屏先看到默认版式再跳
  var picked = resolve();
  apply(picked.key, false);

  function setMineChoice(key) {
    try {
      if (!usable(key) || key === INHERIT) localStorage.removeItem(MINE_KEY);
      else localStorage.setItem(MINE_KEY, key);
    } catch (e) { /* 隐私模式忽略 */ }
    clearPreviewParam();
    if (isMineView()) {
      var picked = resolve();
      apply(picked.key, false);
    }
  }

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
    list: function () { return visibleKeys().map(function (k) { return { key: k, label: LIST[k].label, file: LIST[k].file }; }); },
    visible: visibleKeys,
    current: currentKey,
    resolve: resolve,
    set: function (key) { apply(key, true); },
    mineChoice: storedMineChoice,
    setMineChoice: setMineChoice
  };
})();
