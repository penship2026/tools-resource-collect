/* 主题展示清单与 5 套下拉切换器单测:用 vm + 假 DOM 跑 theme.js。 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.dirname(__dirname);

function makeEnv(search, initialStore, siteConfig, withFooter) {
  const attrs = {};
  const store = Object.assign({}, initialStore || {});
  const link = {
    id: 'theme-css', rel: '',
    _href: '',
    getAttribute(name) { return name === 'href' ? this._href : this[name]; },
    setAttribute(name, value) { if (name === 'href') this._href = value; else this[name] = value; }
  };
  const documentElement = {
    getAttribute(name) { return Object.prototype.hasOwnProperty.call(attrs, name) ? attrs[name] : null; },
    setAttribute(name, value) { attrs[name] = String(value); },
    removeAttribute(name) { delete attrs[name]; }
  };
  const wrap = {
    className: '', innerHTML: '', children: [],
    appendChild(el) { this.children.push(el); },
    querySelector(sel) {
      if (sel === '.theme-select' && /class="theme-select"/.test(this.innerHTML)) return { value: '' };
      return null;
    },
    querySelectorAll() { return []; },
    addEventListener() {}
  };
  const footer = { appendChild(el) { wrap.children.push(el); }, querySelector() { return null; } };
  const document = {
    documentElement,
    head: { appendChild() {} },
    readyState: 'complete',
    getElementById(id) { return id === 'theme-css' ? link : null; },
    createElement(tag) { return tag === 'div' ? wrap : { id: '', rel: '', setAttribute() {} }; },
    querySelector(sel) {
      if (withFooter && sel.indexOf('.site-footer') === 0) return footer;
      if (withFooter && sel === '.theme-switch') return wrap;
      return null;
    },
    addEventListener() {},
    dispatchEvent() {}
  };
  const window = { SITE_CONFIG: siteConfig, localStorage: undefined, JiyeTheme: undefined };
  window.window = window;
  const localStorage = {
    getItem(k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
    setItem(k, v) { store[k] = String(v); },
    removeItem(k) { delete store[k]; }
  };
  window.localStorage = localStorage;
  const context = {
    window, document, localStorage,
    location: { search, href: 'file:///repo/index.html' + search },
    URLSearchParams,
    matchMedia() { return { matches: false, addEventListener() {} }; },
    console
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(root, 'assets/theme.js'), 'utf8'), context);
  return { window, documentElement, link, store, wrap };
}

let pass = 0;
function eq(name, actual, expected) {
  if (actual !== expected) {
    console.error('FAIL ' + name + ': got ' + JSON.stringify(actual) + ', want ' + JSON.stringify(expected));
    process.exitCode = 1;
  } else {
    pass++;
  }
}

// 1) 无展示清单 → 全部 6 套
let env = makeEnv('', null, {});
eq('旧部署回退 6 套', env.window.JiyeTheme.visible().length, 6);

// 2) 5 套展示清单 → anime 隐藏
env = makeEnv('', null, { default_layout: 'standard', display: {
  visible_themes: ['default', 'dark', 'tech', 'campus', 'classical'] } });
eq('展示 5 套', env.window.JiyeTheme.visible().length, 5);
eq('anime 不可见', env.window.JiyeTheme.visible().indexOf('anime'), -1);

// 3) 旧存储指向隐藏主题 → 跟随系统
env = makeEnv('', { 'jiye.theme': 'anime' }, { display: {
  visible_themes: ['default', 'dark', 'tech', 'campus', 'classical'] } });
eq('隐藏主题回退 auto', env.window.JiyeTheme.current(), 'default');
eq('存储仍保留原值', env.store['jiye.theme'], 'anime');

// 4) ?theme=隐藏主题不生效
env = makeEnv('?theme=anime', null, { display: {
  visible_themes: ['default', 'dark', 'tech', 'campus', 'classical'] } });
eq('隐藏主题预览回退', env.window.JiyeTheme.current(), 'default');

// 5) ?theme=可见主题生效
env = makeEnv('?theme=classical', null, { display: {
  visible_themes: ['default', 'dark', 'tech', 'campus', 'classical'] } });
eq('可见主题预览', env.window.JiyeTheme.current(), 'classical');

// 6) 我的主题隐藏值回退 inherit
env = makeEnv('?view=mine', { 'jiye.mine.theme.v1': 'anime' }, { display: {
  visible_themes: ['default', 'dark', 'tech', 'campus', 'classical'] } });
eq('我的隐藏主题回退', env.window.JiyeTheme.mineChoice(), 'inherit');

// 7) 5 套时页脚渲染下拉,不渲染按钮
env = makeEnv('', null, { display: {
  visible_themes: ['default', 'dark', 'tech', 'campus', 'classical'] } }, true);
eq('5 套用下拉', /class="theme-select"/.test(env.wrap.innerHTML), true);
eq('5 套无按钮', /class="theme-btn"/.test(env.wrap.innerHTML), false);

// 8) 4 套时保持按钮
env = makeEnv('', null, { display: {
  visible_themes: ['default', 'dark', 'tech', 'campus'] } }, true);
eq('4 套用按钮', /class="theme-btn"/.test(env.wrap.innerHTML), true);
eq('4 套无下拉', /class="theme-select"/.test(env.wrap.innerHTML), false);

if (process.exitCode) {
  console.error('主题逻辑用例失败');
} else {
  console.log('主题逻辑 ' + pass + ' 个用例全部通过');
}
