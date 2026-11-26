/* 视图层单测(D21/D14):纯字符串渲染,不需要浏览器。
 * 运行: node tests/test_render.js
 */
const fs = require('fs');
const path = require('path');
const assert = require('assert');

global.window = global;
eval(fs.readFileSync(path.join(__dirname, '..', 'assets', 'render.js'), 'utf8'));
const R = global.Render;

let passed = 0;
function ok(name, fn) {
  fn();
  passed++;
  console.log('PASS ' + name);
}

const topic = {
  id: 'daily-website', type: 'series', title: '每天挖掘一个<b>网站</b>',
  slogan: '一集一个网站', count: 24, latest: '2026.11.19',
  cover: 'https://i0.hdslb.com/x.jpg', source: { platform: 'B站' }, tags: ['网站', '工具']
};
const video = {
  title: '一个免费学拼音的网站', key: 'BV1JUs86EESY', bv: 'BV1JUs86EESY',
  url: 'https://www.bilibili.com/video/BV1JUs86EESY/', cover: 'https://i0.hdslb.com/c.jpg',
  date: '2026.11.19', author: '草根的异世界', kind: 'video', desc: '介绍一个网站'
};

ok('esc 转义 5 类字符', () => {
  assert.strictEqual(R.esc(`<img src="x" onerror='1' & >`),
    '&lt;img src=&quot;x&quot; onerror=&#39;1&#39; &amp; &gt;');
});

ok('topicCard 结构/徽标/标签/转义', () => {
  const html = R.topicCard(topic, { href: 'series.html?id=daily-website', updated: '2026-11-26', tags: topic.tags });
  assert(html.includes('href="series.html?id=daily-website"'));
  assert(html.includes('24 条内容'));
  assert(html.includes('var(--plat-bilibili)'));          // 徽标走主题 token
  assert(html.includes('每天挖掘一个&lt;b&gt;网站&lt;/b&gt;')); // 标题已转义
  assert(!html.includes('<b>网站</b>'), '不能透出原始 HTML');
  assert(html.includes('mini-tag'));
});

ok('videoCard 列表形态(平台标签 + 摘要 + 作者)', () => {
  const html = R.videoCard(video, {
    href: 'single.html?id=daily-website&k=BV1JUs86EESY',
    plat: 'B站', platTag: true, metaRight: '草根的异世界'
  });
  assert(html.includes('class="plat-tag"'));
  assert(html.includes('var(--plat-bilibili)'));
  assert(html.includes('class="desc"'));
  assert(html.includes('草根的异世界'));
  assert(html.includes('class="play"'));
});

ok('videoCard 合集形态(右侧显示平台+BV,无平台标签)', () => {
  const html = R.videoCard(video, { href: '#', plat: 'B站', metaRight: 'B站 · BV1JUs86EESY' });
  assert(!html.includes('plat-tag'));
  assert(html.includes('B站 · BV1JUs86EESY'));
});

ok('detail 分派:四个渠道', () => {
  const base = { topic: { updated: '2026-11-26', slogan: '' }, author: '作者', tags: [], sourceUrl: 'https://space.bilibili.com/x' };
  const b = R.detail(Object.assign({}, base, { v: video, plat: 'B站', platKey: 'bilibili' }));
  assert.strictEqual(b.tpl, 'bilibili');
  assert(b.html.includes('player.bilibili.com'));
  assert(b.html.includes('BV1JUs86EESY'));
  const w = R.detail(Object.assign({}, base, { v: { title: '文章', url: 'https://mp.weixin.qq.com/s/a', desc: 'd' }, plat: '公众号', platKey: 'wechat' }));
  assert.strictEqual(w.tpl, 'wechat');
  assert(w.html.includes('wx-article'));
  const x = R.detail(Object.assign({}, base, { v: { title: '笔记', url: 'https://www.xiaohongshu.com/explore/a', desc: 'd' }, plat: '小红书', platKey: 'xhs' }));
  assert.strictEqual(x.tpl, 'xhs');
  assert(x.html.includes('xhs-card'));
  const g = R.detail(Object.assign({}, base, { v: { title: '其他', url: 'https://example.com/a', kind: 'article' }, plat: '其他', platKey: '' }));
  assert.strictEqual(g.tpl, 'generic');
  assert(g.html.includes('tpl-generic'));
});

ok('detail 标题注入被转义', () => {
  const evil = Object.assign({}, video, { title: '<img src=x onerror=alert(1)>' });
  const out = R.detail({ v: evil, topic: { updated: '2026-11-26' }, author: 'a', tags: [], plat: 'B站', platKey: 'bilibili' });
  assert(!out.html.includes('<img src=x'), '原始标签不应出现在输出里');
  assert(out.html.includes('&lt;img src=x'));
});

ok('episodes:上/下一集、序号、当前标记、路由编码', () => {
  const list = [video, Object.assign({}, video, { key: 'BV2', bv: 'BV2', title: '第二条' }),
    Object.assign({}, video, { key: 'BV3', bv: 'BV3', title: '第三条' })];
  const html = R.episodes(list[1], list, '合集名', 'daily-website');
  assert(html.includes('ep-nav'));
  assert(html.includes('第 <b>2</b> / 3 集'));
  assert(html.includes('li class="ep-item cur"'));
  assert(html.includes('&k=BV2'));
  assert(html.includes('全集列表'));
  // 第一条没有上一集
  const first = R.episodes(list[0], list, '合集名', 'daily-website');
  assert(first.includes('ep-btn prev disabled'));
});

ok('topicCard 支持整卡收藏按钮', () => {
  const html = R.topicCard({ id: 'u1', title: '合集', count: 3 }, {
    href: 'series.html?id=u1',
    starHtml: '<button class="fav-btn" data-unit="u1" data-key="__series">☆</button>'
  });
  assert(html.includes('data-key="__series"'));
  assert(html.includes('class="fav-btn"'));
});

ok('episodes 单条时不渲染导航', () => {
  assert.strictEqual(R.episodes(video, [video], '合集名', 'u'), '');
});

ok('detailHref 只生成站内路由', () => {
  assert.strictEqual(R.detailHref('u1', { key: 'k 1' }), 'single.html?id=u1&k=k%201');
  assert.strictEqual(R.detailHref('u1', {}), 'single.html?id=u1');
});

ok('fmtDate 兼容 ISO 与点号', () => {
  assert.strictEqual(R.fmtDate('2026-11-19'), '2026.11.19');
  assert.strictEqual(R.fmtDate('2026.11.19'), '2026.11.19');
  assert.strictEqual(R.fmtDate(''), '—');
});

console.log(`\n${passed} 个视图层用例全部通过`);
