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
  var THEMES = {
    default: { file: 'default.css', label: '浅色' },
    dark: { file: 'dark.css', label: '深色' },
    tech: { file: 'tech.css', label: '科技' },
    campus: { file: 'campus.css', label: '学院' },
    classical: { file: 'classical.css', label: '古典' },
    anime: { file: 'anime.css', label: '二次元' }
  };
  var AUTO_LABEL = '跟随系统';

  function storedChoice() {
    try {
      var v = localStorage.getItem(KEY);
      return v === 'auto' || THEMES[v] ? v : 'auto';
    } catch (e) {
      return 'auto';
    }
  }

  function systemTheme() {
    try {
      return matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'default';
    } catch (e) {
      return 'default';
    }
  }

  function previewParam() {
    var q = new URLSearchParams(location.search).get('theme');
    if (!q) return '';
    if (q === 'light') return 'default';   // 预览别名:light ⇄ default
    return THEMES[q] ? q : '';
  }

  function resolve() {
    var preview = previewParam();
    if (preview) return preview;
    var choice = storedChoice();
    return choice === 'auto' ? systemTheme() : choice;
  }

  // 由本脚本自身位置推出 themes 目录(支持 file:// 与 collector/ 子目录)
  function cssHref(name) {
    var script = document.currentScript;
    var src = script && script.src ? script.src : '';
    var base = src ? src.replace(/theme\.js(?:[?#].*)?$/, '') : '';
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
    var footer = document.querySelector('.site-footer .wrap');
    if (!footer || footer.querySelector('.theme-switch')) return;
    var wrap = document.createElement('div');
    wrap.className = 'theme-switch';
    var html = '<span>主题</span>';
    ['auto'].concat(Object.keys(THEMES)).forEach(function (key) {
      var label = key === 'auto' ? AUTO_LABEL : THEMES[key].label;
      html += '<button type="button" class="theme-btn" data-theme-choice="' + key + '">' + label + '</button>';
    });
    wrap.innerHTML = html;
    footer.appendChild(wrap);
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

  window.JiyeTheme = { THEMES: THEMES, apply: apply, current: resolve };
})();
