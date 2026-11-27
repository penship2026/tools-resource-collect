/* 版式选择逻辑单测:用 vm + 假 DOM 跑 layout.js,不依赖浏览器。
 * 覆盖:优先级、?layout 不落盘、手动切换写存储、非法值回退。
 */
'use strict';
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const root = path.dirname(__dirname);

function makeEnv(search, initialStore, siteConfig) {
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
    SITE_CONFIG: siteConfig,
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

// 7) site.yml 默认版式:仅在本机无存储时生效
env = makeEnv('', null, { default_layout: 'news' });
eq('站点默认 news', env.window.JiyeLayout.current(), 'news');
eq('站点默认不落盘', env.store['jiye.layout'], undefined);

env = makeEnv('', { 'jiye.layout': 'magazine' }, { default_layout: 'news' });
eq('存储优先于站点默认', env.window.JiyeLayout.current(), 'magazine');

env = makeEnv('', null, { default_layout: 'unknown' });
eq('非法站点默认回退', env.window.JiyeLayout.current(), 'standard');

// 8) 版本注册表:三套都在
eq('注册表数量', Object.keys(env.window.TEMPLATES.list).length, 3);

// 9) 我的页专属版式:?view=mine 时优先于公开存储
env = makeEnv('?view=mine', { 'jiye.mine.layout.v1': 'magazine', 'jiye.layout': 'news' });
eq('我的版式优先', env.window.JiyeLayout.current(), 'magazine');
eq('我的版式 CSS', env.link._href, 'assets/layouts/magazine.css');
eq('我的版式取值', env.window.JiyeLayout.mineChoice(), 'magazine');

// 10) 我的页未单独设置 → 跟随公开版式
env = makeEnv('?view=mine', { 'jiye.layout': 'news' });
eq('我的页跟随公开', env.window.JiyeLayout.current(), 'news');
eq('未设置时 mineChoice', env.window.JiyeLayout.mineChoice(), 'inherit');

// 11) 公开页不受我的版式影响
env = makeEnv('', { 'jiye.mine.layout.v1': 'magazine', 'jiye.layout': 'news' });
eq('公开页忽略我的版式', env.window.JiyeLayout.current(), 'news');

// 12) 保存我的版式:写自己的键,不覆盖公开键
env = makeEnv('?view=mine', { 'jiye.layout': 'standard' });
env.window.JiyeLayout.setMineChoice('magazine');
eq('保存我的版式', env.window.JiyeLayout.current(), 'magazine');
eq('我的键写入', env.store['jiye.mine.layout.v1'], 'magazine');
eq('公开键不变', env.store['jiye.layout'], 'standard');

// 13) 选「跟随公开」删除我的键并回落到公开版式
env.window.JiyeLayout.setMineChoice('inherit');
eq('跟随公开后恢复', env.window.JiyeLayout.current(), 'standard');
eq('跟随公开删除我的键', env.store['jiye.mine.layout.v1'], undefined);

// 14) ?layout 预览优先于我的版式
env = makeEnv('?view=mine&layout=news', { 'jiye.mine.layout.v1': 'magazine' });
eq('预览覆盖我的版式', env.window.JiyeLayout.current(), 'news');

if (process.exitCode) {
  console.error('版式逻辑用例失败');
} else {
  console.log('版式逻辑 ' + pass + ' 个用例全部通过');
}
