/* 版式选择逻辑单测:用 vm + 假 DOM 跑 layout.js,不依赖浏览器。
 * 覆盖:优先级、?layout 不落盘、手动切换写存储、非法值回退。
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.dirname(__dirname);

function makeEnv(search, initialStore) {
  const attrs = {};
  const store = Object.assign({}, initialStore || {});
  const link = {
    id: '', rel: '',
    _href: '',
    getAttribute(name) { return name === 'href' ? this._href : this[name]; },
    setAttribute(name, value) { if (name === 'href') this._href = value; else this[name] = value; }
  };
  const documentElement = {
    getAttribute(name) { return Object.prototype.hasOwnProperty.call(attrs, name) ? attrs[name] : null; },
    setAttribute(name, value) { attrs[name] = String(value); },
    removeAttribute(name) { delete attrs[name]; }
  };
  const document = {
    documentElement,
    head: { appendChild() {} },
    readyState: 'complete',
    getElementById(id) { return id === 'layout-css' ? link : null; },
    createElement() { return link; },
    querySelector() { return null; },
    addEventListener() {},
    dispatchEvent() {}
  };
  const window = {
    TEMPLATES: undefined,
    SITE_CONFIG: undefined,
    JiyeLayout: undefined
  };
  window.window = window;
  const localStorage = {
    getItem(k) { return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null; },
    setItem(k, v) { store[k] = String(v); },
    removeItem(k) { delete store[k]; }
  };
  const context = {
    window, document, localStorage,
    location: { search, href: 'file:///repo/index.html' + search },
    URLSearchParams, CustomEvent: function (type, init) { this.type = type; this.detail = init && init.detail; },
    console
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync(path.join(root, 'assets/templates.js'), 'utf8'), context);
  vm.runInContext(fs.readFileSync(path.join(root, 'assets/layout.js'), 'utf8'), context);
  return { window, documentElement, link, store };
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

// 1) 无参数、无存储 → standard
let env = makeEnv('');
eq('默认 standard', env.window.JiyeLayout.current(), 'standard');
eq('默认 CSS', env.link._href, 'assets/layouts/standard.css');

// 2) ?layout=news 预览:生效但不写存储
env = makeEnv('?layout=news');
eq('预览 news', env.window.JiyeLayout.current(), 'news');
eq('预览加载 news.css', env.link._href, 'assets/layouts/news.css');
eq('预览不落盘', env.store['jiye.layout'], undefined);

// 3) 本机存储优先于站点默认
env = makeEnv('', { 'jiye.layout': 'magazine' });
eq('存储 magazine', env.window.JiyeLayout.current(), 'magazine');

// 4) ?layout 覆盖存储
env = makeEnv('?layout=standard', { 'jiye.layout': 'magazine' });
eq('预览覆盖存储', env.window.JiyeLayout.current(), 'standard');

// 5) 非法参数回退默认
env = makeEnv('?layout=unknown');
eq('非法参数', env.window.JiyeLayout.current(), 'standard');

// 6) 手动切换写入 jiye.layout
env = makeEnv('');
env.window.JiyeLayout.set('news');
eq('手动切换', env.window.JiyeLayout.current(), 'news');
eq('手动切换落盘', env.store['jiye.layout'], 'news');

// 7) 版本注册表:三套都在
eq('注册表数量', Object.keys(env.window.TEMPLATES.list).length, 3);

if (process.exitCode) {
  console.error('版式逻辑用例失败');
} else {
  console.log('版式逻辑 ' + pass + ' 个用例全部通过');
}
