/* 采集单元数据加载器(纯静态,file:// 与 http 均可)
 * 三个页面共用:从 URL 的 ?id= 读取单元 id,动态加载对应数据文件。
 * 数据文件为 assets/data/collections/<id>.js,内容形如
 *   window.COLLECTION_DATA["<id>"] = {...};
 */
(function (global) {
  'use strict';

  global.COLLECTION_DATA = global.COLLECTION_DATA || {};

  // 当前页面的单元 id:优先 URL 参数,可用 data-default-id 指定默认
  function currentId() {
    var params = new URLSearchParams(location.search);
    var id = params.get('id');
    if (!id) {
      var el = document.querySelector('[data-default-id]');
      if (el) id = el.getAttribute('data-default-id');
    }
    return id || '';
  }

  // 数据文件相对路径:页面在根目录时为 assets/data/collections/;可用 data-data-base 覆盖
  function dataBase() {
    var el = document.querySelector('[data-data-base]');
    return (el ? el.getAttribute('data-data-base') : 'assets/data/collections/') || 'assets/data/collections/';
  }

  // 安全的文件名:只允许字母数字下划线短横线,避免路径穿越
  function safeId(id) {
    return String(id || '').replace(/[^a-zA-Z0-9_-]/g, '');
  }

  // 加载指定 id 的单元数据,通过回调返回(兼容 file://,不用 fetch)
  function load(unitId, done) {
    var id = safeId(unitId);
    if (!id) { done(null, '缺少单元 id'); return; }
    if (global.COLLECTION_DATA[id]) { done(global.COLLECTION_DATA[id], null); return; }
    var script = document.createElement('script');
    var base = dataBase();
    if (base.charAt(base.length - 1) !== '/') base += '/';
    script.src = base + id + '.js';
    script.onload = function () {
      var data = global.COLLECTION_DATA[id];
      done(data || null, data ? null : '数据文件内容为空');
    };
    script.onerror = function () {
      done(null, '数据文件加载失败: ' + script.src);
    };
    document.head.appendChild(script);
  }

  // 读取已加载的索引(页面先 <script src="assets/data/index.js">)
  function index() {
    return global.COLLECTION_INDEX || global.TOPIC_INDEX || [];
  }

  // 找到索引里某个单元的元信息
  function meta(unitId) {
    return index().filter(function (t) { return t.id === unitId; })[0] || null;
  }

  global.CollectionLoader = {
    currentId: currentId,
    load: load,
    index: index,
    meta: meta,
    safeId: safeId
  };
})(window);
