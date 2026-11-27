/* 主题加载与切换(纯前端,零依赖)
 *
 * 契约(见 docs/PLAN-20261126.md D23/D25/D31/D33):
 *  - 主题 = assets/themes/<file>.css,只定义 token(变量),不改 DOM/不写业务逻辑;
 *  - 内置 6 套:浅色 / 深色 / 科技 / 学院 / 古典 / 二次元,外加「跟随系统」;
 *  - 新增主题:复制一份 CSS 改成自己的取值 + 在下方 THEMES 注册一行;
 *  - 选择保存于 localStorage(键 jiye.theme:auto 或任一套主题 key),?theme= 仅作预览不入索引;
 *  - 默认跟随系统 prefers-color-scheme;首屏在本脚本内同步注入 <link>,避免主题闪烁。
 */
(function () {
  'use strict';

  var KEY = 'jiye.theme';
  // 我的页专属主题(与公开主题互不影响);'inherit' 表示跟随公开主题
  var MINE_KEY = 'jiye.mine.theme.v1';
  var THEMES = {
    default: { file: 'default.css', label: '浅色' },
    dark: { file: 'dark.css', label: '深色' },
    tech: { file: 'tech.css', label: '科技' },
    campus: { file: 'campus.css', label: '学院' },
    classical: { file: 'classical.css', label: '古典' },
    anime: { file: 'anime.css', label: '二次元' }
  };
  var AUTO_LABEL = '跟随系统';
  var INHERIT = 'inherit';

  // 展示清单由 site.yml display.visible_themes 控制;旧部署缺字段时退回全部内置
  function visibleThemes() {
    var cfg = window.SITE_CONFIG && window.SITE_CONFIG.display;
    var keys = cfg && Array.isArray(cfg.visible_themes) ? cfg.visible_themes : [];
    keys = keys.filter(function (key) { return !!THEMES[key]; });
    return keys.length ? keys : Object.keys(THEMES);
  }

  function valid(key) {
    return !!THEMES[key] && visibleThemes().indexOf(key) >= 0;
  }

  function storedChoice() {
    try {
      var v = localStorage.getItem(KEY);
      return v === 'auto' || valid(v) ? v : 'auto';
    } catch (e) {
      return 'auto';
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
      var v = localStorage.getItem(MINE_KEY);
      return v === 'auto' || valid(v) ? v : INHERIT;
    } catch (e) {
      return INHERIT;
    }
  }

  function systemTheme() {
    try {
      var dark = matchMedia('(prefers-color-scheme: dark)').matches;
      if (dark && valid('dark')) return 'dark';
      return valid('default') ? 'default' : visibleThemes()[0];
    } catch (e) {
      return valid('default') ? 'default' : visibleThemes()[0];
    }
  }

  function previewParam() {
    var q = new URLSearchParams(location.search).get('theme');
    if (!q) return '';
    if (q === 'light') return valid('default') ? 'default' : '';   // 预览别名:light ⇄ default
    return valid(q) ? q : '';
  }

  function resolve() {
    var preview = previewParam();
    if (preview) return preview;
    var choice = storedChoice();
    // 我的页单独设过主题就优先用它,否则跟随公开主题
    if (isMineView()) {
      var mine = storedMineChoice();
      if (mine !== INHERIT) choice = mine;
    }
    return choice === 'auto' ? systemTheme() : choice;
  }

  // 由本脚本自身位置推出 themes 目录(支持 file:// 与 collector/ 子目录)
  function cssHref(name) {
    var script = document.currentScript;
    var src = script && script.src ? script.src : '';
    var base = window.__THEME_BASE || (src ? src.replace(/theme\.js(?:[?#].*)?$/, '') : '');
    if (!base) base = 'assets/';
    return base + 'themes/' + THEMES[name].file;
  }

  var link = null;

  function apply() {
    var name = resolve();
    if (!link) {
      link = document.getElementById('theme-css');
    }
    if (!link) {
      link = document.createElement('link');
      link.rel = 'stylesheet';
      link.id = 'theme-css';
      // 同步插入 <head>:阻塞脚本尚未返回,不会出现"先浅色再深色"的闪烁
      (document.head || document.documentElement).appendChild(link);
    }
    var href = cssHref(name);
    if (link.getAttribute('href') !== href) link.setAttribute('href', href);
    document.documentElement.setAttribute('data-theme', name);
    updateSwitch();
  }

  function renderSwitch() {
    var footer = document.querySelector('.site-footer:not(.mine-footer) .wrap');
    if (!footer || footer.querySelector('.theme-switch')) return;
    var keys = visibleThemes();
    var wrap = document.createElement('div');
    wrap.className = 'theme-switch';
    var html = '<span>主题</span>';
    var choices = ['auto'].concat(keys);
    if (keys.length >= 5) {
      // 5 套时 390px 按钮会溢出,改为下拉;auto 作为第一项
      html += '<select class="theme-select" aria-label="主题">';
      choices.forEach(function (key) {
        var label = key === 'auto' ? AUTO_LABEL : THEMES[key].label;
        html += '<option value="' + key + '">' + label + '</option>';
      });
      html += '</select>';
    } else {
      choices.forEach(function (key) {
        var label = key === 'auto' ? AUTO_LABEL : THEMES[key].label;
        html += '<button type="button" class="theme-btn" data-theme-choice="' + key + '">' + label + '</button>';
      });
    }
    wrap.innerHTML = html;
    footer.appendChild(wrap);
    wrap.addEventListener('change', function (ev) {
      var sel = ev.target.closest && ev.target.closest('.theme-select');
      if (!sel) return;
      try { localStorage.setItem(KEY, sel.value); } catch (e) {}
      apply();
    });
    wrap.addEventListener('click', function (ev) {
      var btn = ev.target.closest && ev.target.closest('.theme-btn');
      if (!btn) return;
      var choice = btn.getAttribute('data-theme-choice');
      try { localStorage.setItem(KEY, choice); } catch (e) {}
      apply();
    });
    updateSwitch();
  }

  function updateSwitch() {
    var wrap = document.querySelector('.theme-switch');
    if (!wrap) return;
    var choice = storedChoice();
    var sel = wrap.querySelector('.theme-select');
    if (sel) sel.value = choice;
    wrap.querySelectorAll('.theme-btn').forEach(function (btn) {
      btn.classList.toggle('active', btn.getAttribute('data-theme-choice') === choice);
    });
  }

  function updateSwitch() {
    var wrap = document.querySelector('.theme-switch');
    if (!wrap) return;
    var choice = storedChoice();
    wrap.querySelectorAll('.theme-btn').forEach(function (btn) {
      btn.classList.toggle('active', btn.getAttribute('data-theme-choice') === choice);
    });
  }

  // 系统主题变化时,只有"跟随系统"才重新应用
  try {
    matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function () {
      if (storedChoice() === 'auto' && !previewParam()) apply();
    });
  } catch (e) {
    /* 老浏览器忽略 */
  }

  function boot() {
    apply();
    renderSwitch();
    apply(); // 页脚渲染后再同步一次 href/状态
  }

  apply();
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }

  function setMineChoice(choice) {
    try {
      if (!choice || choice === INHERIT) localStorage.removeItem(MINE_KEY);
      else if (choice === 'auto' || valid(choice)) localStorage.setItem(MINE_KEY, choice);
    } catch (e) { /* 隐私模式忽略 */ }
    apply();
  }

  window.JiyeTheme = {
    THEMES: THEMES,
    AUTO_LABEL: AUTO_LABEL,
    INHERIT: INHERIT,
    visible: visibleThemes,
    apply: apply,
    current: resolve,
    mineChoice: storedMineChoice,
    setMineChoice: setMineChoice
  };
})();
