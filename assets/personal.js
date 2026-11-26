/* 个人收藏层(纯本地,localStorage only)
 * 规则(见 docs/PLAN-20261126.md D11/D12/D28/D30):
 *  - 只收藏站内已有条目,不收录自己录入的站外链接
 *  - 每条收藏存一份最小快照,单元下线后仍可读
 *  - 导出/导入 JSON;导入默认合并(同 key 保留较新),替换需二次确认;非法文件整体拒绝
 *  - 800 条软上限
 * 依赖 data-loader.js 的 escHtml;不依赖任何后端接口。
 */
(function (global) {
  'use strict';

  var STORE_KEY = 'jiye.mine.v1';
  var TITLE_KEY = 'jiye.mine.title.v1';
  var TITLE_MAX = 40;   // 支持换行,两行约 20 字/行
  var DEFAULT_TITLE = '我的收藏';
  // 我的页顶部副标题(与公开首页 hero 对齐,只存本机)
  var SUB_KEY = 'jiye.mine.subtitle.v1';
  // 顶部「公开 / 我的」开关里「我的」的显示名称(只显示名称,不显示收藏数)
  var SWITCH_KEY = 'jiye.mine.switch.v1';
  var SWITCH_MAX = 12;
  var DEFAULT_SWITCH = '我的';
  var SUB_MAX = 120;
  var DEFAULT_SUB = '只保存在这台设备的收藏,不上传、不同步。';
  var LIMIT = 800;

  function esc(v) {
    if (typeof global.escHtml === 'function') return global.escHtml(v);
    return String(v == null ? '' : v).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  function mineTitle() {
    try {
      var t = String(global.localStorage.getItem(TITLE_KEY) || '').trim();
      return t ? t.slice(0, TITLE_MAX) : DEFAULT_TITLE;
    } catch (e) {
      return DEFAULT_TITLE;
    }
  }

  function setMineTitle(value) {
    var t = String(value || '').trim().slice(0, TITLE_MAX);
    try {
      if (t) global.localStorage.setItem(TITLE_KEY, t);
      else global.localStorage.removeItem(TITLE_KEY);
    } catch (e) { /* 隐私模式忽略 */ }
    return t || DEFAULT_TITLE;
  }

  // 浏览器标签不支持换行,压成单行
  function docTitle() {
    return mineTitle().replace(/\s+/g, ' ') + ' · 集页';
  }

  function switchLabel() {
    try {
      var t = String(global.localStorage.getItem(SWITCH_KEY) || '').trim();
      return t ? t.slice(0, SWITCH_MAX) : DEFAULT_SWITCH;
    } catch (e) {
      return DEFAULT_SWITCH;
    }
  }

  function setSwitchLabel(value) {
    var t = String(value || '').trim().replace(/\s+/g, ' ').slice(0, SWITCH_MAX);
    try {
      if (t) global.localStorage.setItem(SWITCH_KEY, t);
      else global.localStorage.removeItem(SWITCH_KEY);
    } catch (e) { /* 隐私模式忽略 */ }
    return t || DEFAULT_SWITCH;
  }

  function mineSubtitle() {
    try {
      var t = String(global.localStorage.getItem(SUB_KEY) || '').trim();
      return t ? t.slice(0, SUB_MAX) : DEFAULT_SUB;
    } catch (e) {
      return DEFAULT_SUB;
    }
  }

  function setMineSubtitle(value) {
    var t = String(value || '').trim().slice(0, SUB_MAX);
    try {
      if (t) global.localStorage.setItem(SUB_KEY, t);
      else global.localStorage.removeItem(SUB_KEY);
    } catch (e) { /* 隐私模式忽略 */ }
    return t || DEFAULT_SUB;
  }

  function uid(unit, key) { return String(unit || '') + '|' + String(key || ''); }
  function isoNow() { return new Date().toISOString(); }
  function isHttp(u) { return /^https?:\/\//i.test(String(u || '')); }

  function emptyStore() { return { v: 1, updated: '', items: {} }; }

  function read() {
    try {
      var raw = global.localStorage.getItem(STORE_KEY);
      if (!raw) return emptyStore();
      var d = JSON.parse(raw);
      if (!d || typeof d !== 'object' || !d.items || typeof d.items !== 'object') return emptyStore();
      d.v = 1;
      return d;
    } catch (e) {
      return emptyStore();
    }
  }

  function write(d) {
    d.v = 1;
    d.updated = isoNow();
    global.localStorage.setItem(STORE_KEY, JSON.stringify(d));
  }

  // 只保留渲染需要的字段,避免 localStorage 膨胀
  function snapshot(it) {
    return {
      unit: String(it.unit || ''),
      key: String(it.key || ''),
      unitTitle: String(it.unitTitle || ''),
      title: String(it.title || ''),
      url: isHttp(it.url) ? String(it.url) : '',
      cover: isHttp(it.cover) ? String(it.cover) : '',
      date: String(it.date || ''),
      author: String(it.author || ''),
      kind: String(it.kind || 'video'),
      note: String(it.note || ''),
      addedAt: String(it.addedAt || isoNow())
    };
  }

  // 校验导入文件:任意一条不合格就整体拒绝
  function normalize(raw) {
    if (!raw || typeof raw !== 'object' || Array.isArray(raw)) throw new Error('不是有效的收藏文件');
    if (raw.v != null && raw.v !== 1) throw new Error('收藏文件版本不支持: ' + raw.v);
    if (!raw.items || typeof raw.items !== 'object' || Array.isArray(raw.items)) throw new Error('缺少 items 字段');
    var out = {};
    var n = 0;
    Object.keys(raw.items).forEach(function (k) {
      var it = raw.items[k];
      n++;
      if (!it || typeof it !== 'object') throw new Error('第 ' + n + ' 条收藏格式不正确');
      if (!it.unit || !it.key) throw new Error('第 ' + n + ' 条收藏缺少 unit / key');
      if (!it.title || typeof it.title !== 'string') throw new Error('第 ' + n + ' 条收藏缺少标题');
      if (it.url && !isHttp(it.url)) throw new Error('第 ' + n + ' 条收藏的链接不是 http(s) 地址');
      if (it.cover && !isHttp(it.cover)) throw new Error('第 ' + n + ' 条收藏的封面不是 http(s) 地址');
      var s = snapshot(it);
      out[uid(s.unit, s.key)] = s;
    });
    return out;
  }

  function count() { return Object.keys(read().items).length; }
  function has(unit, key) { return !!read().items[uid(unit, key)]; }
  function list() {
    var items = read().items;
    return Object.keys(items).map(function (k) { return items[k]; })
      .sort(function (a, b) { return String(b.addedAt).localeCompare(String(a.addedAt)); });
  }

  function add(it) {
    var d = read();
    var s = snapshot(it);
    var k = uid(s.unit, s.key);
    if (!s.unit || !s.key || !s.title) throw new Error('收藏信息不完整');
    if (d.items[k]) { s.addedAt = d.items[k].addedAt; } // 重复收藏保留首次时间
    else if (Object.keys(d.items).length >= LIMIT) throw new Error('收藏已达 ' + LIMIT + ' 条上限,请先清理或导出备份');
    d.items[k] = s;
    write(d);
    return s;
  }

  function remove(unit, key) {
    var d = read();
    delete d.items[uid(unit, key)];
    write(d);
  }

  function toggle(it) {
    var k = uid(it.unit, it.key);
    if (read().items[k]) { remove(it.unit, it.key); return false; }
    add(it);
    return true;
  }

  function exportJson(opts) {
    var d = read();
    var text = JSON.stringify({ v: 1, updated: isoNow(), items: d.items }, null, 2);
    if (opts && opts.download === false) return text;
    var stamp = isoNow().slice(0, 10).replace(/-/g, '');
    var blob = new Blob([text], { type: 'application/json' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = '个人收藏-' + stamp + '.json';
    document.body.appendChild(a);
    a.click();
    setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 0);
    return text;
  }

  // mode: 'merge'(默认) | 'replace'
  function importText(text, mode, opts) {
    var raw;
    try { raw = JSON.parse(text); } catch (e) { throw new Error('文件不是有效的 JSON'); }
    var incoming = normalize(raw);
    var d = read();
    var existed = Object.keys(d.items).length;
    if (existed && !(opts && opts.skipBackup)) exportJson(); // 导入前自动留一份
    if (mode === 'replace') {
      if (existed >= LIMIT) throw new Error('收藏已达 ' + LIMIT + ' 条上限');
      d.items = incoming;
    } else {
      Object.keys(incoming).forEach(function (k) {
        var a = d.items[k];
        if (!a || String(incoming[k].addedAt) > String(a.addedAt)) {
          d.items[k] = incoming[k];
        }
      });
      if (Object.keys(d.items).length > LIMIT) throw new Error('合并后超过 ' + LIMIT + ' 条上限,请用「替换」或先清理');
    }
    write(d);
    return { added: Object.keys(incoming).length, total: Object.keys(d.items).length };
  }

  function importFile(file, mode) {
    return new Promise(function (resolve, reject) {
      if (!file) { reject(new Error('没有选择文件')); return; }
      if (file.size > 5 * 1024 * 1024) { reject(new Error('文件超过 5MB,疑似不是收藏文件')); return; }
      var fr = new FileReader();
      fr.onload = function () {
        try { resolve(importText(String(fr.result), mode)); } catch (e) { reject(e); }
      };
      fr.onerror = function () { reject(new Error('文件读取失败')); };
      fr.readAsText(file, 'utf-8');
    });
  }

  /* ---------- 渲染辅助 ---------- */

  function starButton(it) {
    var s = snapshot(it);
    return '<button class="fav-btn" type="button" title="收藏到「我的」"' +
      ' data-unit="' + esc(s.unit) + '" data-key="' + esc(s.key) + '"' +
      ' data-title="' + esc(s.title) + '" data-url="' + esc(s.url) + '"' +
      ' data-cover="' + esc(s.cover) + '" data-date="' + esc(s.date) + '"' +
      ' data-author="' + esc(s.author) + '" data-kind="' + esc(s.kind) + '"' +
      ' data-unit-title="' + esc(s.unitTitle) + '">' + (has(s.unit, s.key) ? '★' : '☆') + '</button>';
  }

  function readEl(el) {
    return snapshot({
      unit: el.getAttribute('data-unit'),
      key: el.getAttribute('data-key'),
      title: el.getAttribute('data-title'),
      url: el.getAttribute('data-url'),
      cover: el.getAttribute('data-cover'),
      date: el.getAttribute('data-date'),
      author: el.getAttribute('data-author'),
      kind: el.getAttribute('data-kind'),
      unitTitle: el.getAttribute('data-unit-title')
    });
  }

  function syncStars(root) {
    (root || document).querySelectorAll('.fav-btn').forEach(function (el) {
      var on = has(el.getAttribute('data-unit'), el.getAttribute('data-key'));
      el.textContent = on ? '★' : '☆';
      el.classList.toggle('on', on);
    });
  }

  function initStars() {
    document.addEventListener('click', function (ev) {
      var btn = ev.target.closest ? ev.target.closest('.fav-btn') : null;
      if (!btn) return;
      ev.preventDefault();
      ev.stopPropagation();
      try {
        var it = readEl(btn);
        var on = toggle(it);
        btn.textContent = on ? '★' : '☆';
        btn.classList.toggle('on', on);
        updateSwitchCount();
        if (isMineView() && !on) renderMineContent();
      } catch (e) {
        alert(e.message || '收藏失败');
      }
    });
  }

  function isMineView() {
    return new URLSearchParams(location.search).get('view') === 'mine';
  }

  /* ---------- 顶部「公开 / 我的」开关(D28:按需显示) ---------- */

  function updateSwitchCount() {
    var wrap = document.getElementById('view-switch');
    if (!wrap) return;
    var n = count();
    wrap.hidden = n === 0;               // 零收藏不出现入口
    var mineBtn = wrap.querySelector('[data-view="mine"]');
    if (mineBtn) mineBtn.textContent = switchLabel();
  }

  function mountHeaderSwitch() {
    var wrap = document.getElementById('view-switch');
    if (!wrap) return;
    wrap.querySelectorAll('[data-view]').forEach(function (btn) {
      btn.classList.toggle('active', (btn.getAttribute('data-view') === 'mine') === isMineView());
      btn.addEventListener('click', function () {
        var v = btn.getAttribute('data-view');
        var params = new URLSearchParams(location.search);
        if (v === 'mine') params.set('view', 'mine'); else params.delete('view');
        var qs = params.toString();
        location.href = location.pathname + (qs ? '?' + qs : '');
      });
    });
    updateSwitchCount();
  }

  /* ---------- 个人视图 ---------- */

  function snapshotCard(it, opts) {
    var enabledMap = (opts && opts.units) || {};
    var offline = enabledMap[it.unit] === false;
    // 单元已下线/被关闭时,站内详情页取不到数据,退回原链接
    var href = (offline && it.url)
      ? it.url
      : 'single.html?id=' + encodeURIComponent(it.unit) + '&k=' + encodeURIComponent(it.key);
    var target = (offline && it.url) ? ' target="_blank" rel="noopener noreferrer"' : '';
    var cover = it.cover
      ? '<img src="' + esc(it.cover) + '" alt="' + esc(it.title) + '" loading="lazy" referrerpolicy="no-referrer">'
      : '<div class="fav-ph">' + esc((it.title || '内').charAt(0)) + '</div>';
    return '<div class="fav-card">' +
      '<a class="fav-thumb" href="' + esc(href) + '"' + target + '>' + cover + '</a>' +
      '<div class="fav-body"><a class="fav-title" href="' + esc(href) + '"' + target + '>' + esc(it.title) + '</a>' +
      '<div class="fav-meta"><span>' + esc(it.unitTitle || it.unit) + '</span>' +
      (it.date ? '<span>' + esc(it.date) + '</span>' : '') +
      (offline ? '<span class="fav-off">单元已下线 · 快照</span>' : '') + '</div>' +
      (it.note ? '<p class="fav-note">' + esc(it.note) + '</p>' : '') +
      '<div class="fav-act">' +
      (it.url ? '<a href="' + esc(it.url) + '" target="_blank" rel="noopener noreferrer">原链接 ↗</a>' : '') +
      '<button type="button" class="fav-del" data-unit="' + esc(it.unit) + '" data-key="' + esc(it.key) + '">取消收藏</button>' +
      '</div></div></div>';
  }

  function unitsEnabledMap() {
    var idx = (global.COLLECTION_INDEX || global.TOPIC_INDEX || []);
    var map = {};
    idx.forEach(function (t) { map[t.id] = t.enabled !== false; });
    return map;
  }

  function renderMineContent() {
    var panel = document.getElementById('mine-panel');
    if (!panel) return;
    var body = panel.querySelector('#mine-body');
    var titleEl = panel.querySelector('#mine-title');
    if (titleEl) titleEl.textContent = mineTitle();
    var subEl = panel.querySelector('#mine-sub');
    if (subEl) subEl.textContent = mineSubtitle();
    // 我的视图只渲染本机收藏(localStorage),不混入公开数据
    var items = list();
    var units = unitsEnabledMap();
    body.innerHTML = items.length
      ? '<div class="fav-grid">' + items.map(function (it) { return snapshotCard(it, { units: units }); }).join('') + '</div>'
      : '<div class="empty">还没有收藏。到合集页点条目右上角的 ☆ 即可收藏。</div>';
    var stat = panel.querySelector('#mine-stat');
    if (stat) stat.textContent = items.length ? '共 ' + items.length + ' 条收藏' + (items.length >= LIMIT ? '(已达软上限)' : '') : '';
    syncStars(body);
  }

  function mountMineView() {
    if (!isMineView()) return;
    var panel = document.getElementById('mine-panel');
    if (!panel) return;
    var bar = document.getElementById('filter-bar');
    var grid = document.getElementById('topic-grid');
    if (bar) bar.hidden = true;
    if (grid) grid.hidden = true;
    var sectionTitle = document.querySelector('.section-title');
    if (sectionTitle) sectionTitle.hidden = true;
    var hero = document.querySelector('.hero');
    if (hero) hero.hidden = true;
    panel.hidden = false;
    // 个人数据不上搜索引擎;静态页无法按参数改 meta,这里补一个(并写入 robots 头)
    if (!document.querySelector('meta[name="robots"]')) {
      var m = document.createElement('meta');
      m.name = 'robots';
      m.content = 'noindex, nofollow';
      document.head.appendChild(m);
    }
    document.title = docTitle();

    // 自定义页面标题:点击 ✎ 变输入框,回车/失焦保存,Esc 取消(只存本机)
    (function () {
      var edit = panel.querySelector('#mine-title-edit');
      var input = panel.querySelector('#mine-title-input');
      var titleEl = panel.querySelector('#mine-title');
      var cancelled = false;
      if (!edit || !input || !titleEl) return;
      function showInput() {
        input.value = mineTitle();
        titleEl.hidden = true;
        edit.hidden = true;
        input.hidden = false;
        input.focus();
        input.select();
      }
      function commit(save) {
        if (save) setMineTitle(input.value);
        input.hidden = true;
        edit.hidden = false;
        titleEl.hidden = false;
        titleEl.textContent = mineTitle();
        document.title = docTitle();
      }
      edit.addEventListener('click', showInput);
      input.addEventListener('keydown', function (e) {
        // 多行编辑:Enter 换行,⌘/Ctrl+Enter 保存,Esc 取消
        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); commit(true); }
        else if (e.key === 'Escape') { e.preventDefault(); cancelled = true; commit(false); }
      });
      // Esc 取消后隐藏输入框还会触发一次 blur,用标记避免把已取消的值写回
      input.addEventListener('blur', function () {
        if (cancelled) { cancelled = false; return; }
        commit(true);
      });
    })();

    // 设置面板:收藏页名称 + 我的页专属主题(不跟公开主题共用)
    (function () {
      var btn = panel.querySelector('#mine-settings');
      var box = panel.querySelector('#mine-settings-panel');
      var titleInput = panel.querySelector('#mine-set-title');
      var switchInput = panel.querySelector('#mine-set-switch');
      var switchReset = panel.querySelector('#mine-set-switch-reset');
      var subInput = panel.querySelector('#mine-set-sub');
      var subReset = panel.querySelector('#mine-set-sub-reset');
      var themeSel = panel.querySelector('#mine-set-theme');
      var saveBtn = panel.querySelector('#mine-set-save');
      var cancelBtn = panel.querySelector('#mine-set-cancel');
      var resetBtn = panel.querySelector('#mine-set-title-reset');
      if (!btn || !box || !titleInput || !themeSel) return;

      var theme = global.JiyeTheme;
      if (theme && theme.THEMES) {
        Object.keys(theme.THEMES).forEach(function (key) {
          var op = document.createElement('option');
          op.value = key;
          op.textContent = theme.THEMES[key].label;
          themeSel.appendChild(op);
        });
      }

      function fill() {
        titleInput.value = mineTitle() === DEFAULT_TITLE ? '' : mineTitle();
        titleInput.placeholder = DEFAULT_TITLE;
        if (switchInput) {
          switchInput.value = switchLabel() === DEFAULT_SWITCH ? '' : switchLabel();
          switchInput.placeholder = DEFAULT_SWITCH;
        }
        if (subInput) {
          subInput.value = mineSubtitle() === DEFAULT_SUB ? '' : mineSubtitle();
          subInput.placeholder = DEFAULT_SUB;
        }
        themeSel.value = theme && theme.mineChoice ? theme.mineChoice() : 'inherit';
      }

      function open() {
        fill();
        box.hidden = false;
        btn.setAttribute('aria-expanded', 'true');
        titleInput.focus();
        titleInput.select();
      }

      function close() {
        box.hidden = true;
        btn.setAttribute('aria-expanded', 'false');
      }

      btn.addEventListener('click', function () {
        if (box.hidden) open(); else close();
      });
      cancelBtn.addEventListener('click', close);
      resetBtn.addEventListener('click', function () {
        titleInput.value = '';
        titleInput.focus();
      });
      if (switchReset && switchInput) {
        switchReset.addEventListener('click', function () {
          switchInput.value = '';
          switchInput.focus();
        });
      }
      if (subReset && subInput) {
        subReset.addEventListener('click', function () {
          subInput.value = '';
          subInput.focus();
        });
      }
      saveBtn.addEventListener('click', function () {
        setMineTitle(titleInput.value);
        if (switchInput) setSwitchLabel(switchInput.value);
        updateSwitchCount();
        if (subInput) setMineSubtitle(subInput.value);
        var titleEl = panel.querySelector('#mine-title');
        if (titleEl) titleEl.textContent = mineTitle();
        var subEl = panel.querySelector('#mine-sub');
        if (subEl) subEl.textContent = mineSubtitle();
        document.title = docTitle();
        if (theme && theme.setMineChoice) theme.setMineChoice(themeSel.value);
        close();
      });
      box.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') { e.preventDefault(); close(); }
      });
    })();

    panel.querySelector('#mine-export').addEventListener('click', function () {
      if (!count()) { alert('还没有收藏可导出'); return; }
      exportJson();
    });
    panel.querySelector('#mine-import').addEventListener('click', function () {
      panel.querySelector('#mine-file').click();
    });
    panel.querySelector('#mine-file').addEventListener('change', function (e) {
      var file = e.target.files && e.target.files[0];
      e.target.value = '';
      if (!file) return;
      var mode = panel.querySelector('input[name="mine-mode"]:checked');
      importFile(file, mode ? mode.value : 'merge').then(function (r) {
        renderMineContent();
        updateSwitchCount();
        alert('导入完成:文件内 ' + r.added + ' 条,当前共 ' + r.total + ' 条');
      }).catch(function (err) {
        alert('导入失败(未写入任何数据):' + err.message);
      });
    });
    panel.addEventListener('click', function (e) {
      var btn = e.target.closest && e.target.closest('.fav-del');
      if (!btn) return;
      remove(btn.getAttribute('data-unit'), btn.getAttribute('data-key'));
      renderMineContent();
      updateSwitchCount();
    });

    renderMineContent();
  }

  function init() {
    initStars();
    mountHeaderSwitch();
    mountMineView();
    syncStars(document);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  global.Personal = {
    STORE_KEY: STORE_KEY,
    LIMIT: LIMIT,
    count: count,
    list: list,
    has: has,
    add: add,
    remove: remove,
    toggle: toggle,
    exportJson: exportJson,
    importText: importText,
    importFile: importFile,
    normalize: normalize,
    starButton: starButton,
    syncStars: syncStars,
    mineTitle: mineTitle,
    setMineTitle: setMineTitle,
    mineSubtitle: mineSubtitle,
    setMineSubtitle: setMineSubtitle,
    switchLabel: switchLabel,
    setSwitchLabel: setSwitchLabel,
    renderMineContent: renderMineContent
  };
})(window);
