/* 视图层(唯一实现):数据 → DOM 片段
 *
 * 页面只保留容器、路由与数据加载,不再各自拼 HTML(D21)。
 * 所有拼接一律经 esc() 转义;颜色一律引用主题 token(D22);
 * 数据里不含路由:路由由页面传入,或由另一方面推导(D24 的方向)。
 *
 * 三组渲染:
 *   topicCard(t, opts)   首页主题卡片
 *   videoCard(v, opts)   合集页 / 全部内容页的条目卡片
 *   detail(ctx)          详情页四套模板(B站 / 公众号 / 小红书 / 兜底)+ 多集导航
 */
(function (global) {
  'use strict';

  var ESC_MAP = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (ch) { return ESC_MAP[ch]; });
  }

  // 渠道稳定 key → 展示名(D24:数据里只存 key,中文名由视图层映射)
  var PLAT = { bilibili: 'B站', wechat: '公众号', xhs: '小红书', multi: '多平台' };
  var PLAT_TO_KEY = { 'B站': 'bilibili', '公众号': 'wechat', '小红书': 'xhs', '多平台': 'multi' };
  var PLAT_COLORS = {
    bilibili: 'var(--plat-bilibili)',
    wechat: 'var(--plat-wechat)',
    xhs: 'var(--plat-xhs)',
    multi: 'var(--plat-multi)'
  };

  // 兼容三种取值:稳定 key(bilibili)/旧中文名(B站)/空(历史 B站 数据)
  function platKey(value) {
    var v = String(value || '').trim();
    if (!v) return 'bilibili';
    if (PLAT[v]) return v;
    return PLAT_TO_KEY[v] || v;
  }

  function platLabel(value) {
    var k = platKey(value);
    return PLAT[k] || String(value || '');
  }

  function platColor(value) {
    return PLAT_COLORS[platKey(value)] || 'rgba(0,0,0,.72)';
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    var m = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(iso);
    if (!m) return iso;
    return m[1] + '.' + ('0' + Number(m[2])).slice(-2) + '.' + ('0' + Number(m[3])).slice(-2);
  }

  // 条目唯一键:与采集端 item_key 一致(B站=BV,公众号=原文地址,小红书=笔记ID)
  function itemKey(v) {
    return v.key || v.bv || v.url || '';
  }

  // 站内详情路由:只走站内页面,不直接跳源平台
  function detailHref(unitId, v) {
    var k = itemKey(v);
    return 'single.html?id=' + encodeURIComponent(unitId || '') + (k ? '&k=' + encodeURIComponent(k) : '');
  }

  /* ---------------- 一、首页主题卡片 ---------------- */

  // opts: { href, updated, platName, tags[] }
  function topicCard(t, opts) {
    opts = opts || {};
    var type = t.type || 'series';
    var cover = t.cover
      ? '<img src="' + esc(t.cover) + '" alt="' + esc(t.title) + '" loading="lazy" referrerpolicy="no-referrer">'
      : '<div class="topic-ph">' + esc((t.title || '内').charAt(0)) + '</div>';
    var platName = opts.platName || (t.source && t.source.platform) || 'B站';
    var badge = '<span class="badge" style="background:' + platColor(platName) + '">' + esc(platLabel(platName)) + '</span>';
    var typeTag = type === 'single'
      ? '<span class="type-tag single">单条</span>'
      : '<span class="type-tag">合集</span>';
    var tags = (opts.tags || []).slice(0, 6).map(function (x) {
      return '<span class="mini-tag">' + esc(x) + '</span>';
    }).join('');
    var latest = t.latest || opts.updated || '';
    var pin = opts.pin ? '<span class="pin-badge">置顶</span>' : '';
    return '<a class="topic-card" href="' + esc(opts.href || '#') + '">' +
      '<div class="topic-cover">' + cover + typeTag + pin + badge + (opts.starHtml || '') + '</div>' +
      '<div class="topic-body"><h3>' + esc(t.title) + '</h3>' +
      '<p class="slogan">' + esc(t.slogan || '') + '</p>' +
      (tags ? '<div class="tag-line">' + tags + '</div>' : '') +
      '<div class="foot"><span class="count">' + esc(t.count || 0) + ' 条内容 →</span>' +
      '<span>' + esc(latest) + '</span></div></div></a>';
  }

  /* ---------------- 二、条目卡片(合集页 / 全部内容页) ---------------- */

  // opts: { unitId, unitTitle, href, plat, mark(right-bottom meta), badge, desc, starHtml }
  function videoCard(v, opts) {
    opts = opts || {};
    var isVideo = (v.kind || 'video') === 'video';
    var cover = v.cover
      ? '<img src="' + esc(v.cover) + '" alt="' + esc(v.title) + '" loading="lazy" referrerpolicy="no-referrer">'
      : '<div class="thumb-placeholder">' + esc((v.title || '内').charAt(0)) + '</div>';
    var mark = isVideo ? '<span class="play"><i>▶</i></span>' : '<span class="kind-tag">图文</span>';
    var badge = opts.platTag
      ? '<span class="plat-tag" style="background:' + platColor(opts.plat) + '">' + esc(platLabel(opts.plat)) + '</span>'
      : '';
    var metaRight = opts.metaRight != null
      ? opts.metaRight
      : esc((opts.plat || '') + (v.bv ? ' · ' + v.bv : ''));
    return '<a class="video-card" href="' + esc(opts.href || '#') + '">' +
      '<div class="video-thumb">' + cover + mark + badge + '</div>' +
      (opts.starHtml || '') +
      '<div class="video-info"><h3>' + esc(v.title) + '</h3>' +
      (opts.desc !== false && v.desc ? '<p class="desc">' + esc(v.desc) + '</p>' : '') +
      '<div class="meta"><span>' + (opts.dateText != null ? opts.dateText : esc(v.date || '—')) +
      '</span><span>' + metaRight + '</span></div></div></a>';
  }

  /* ---------------- 三、板块导航 / 门户区块(M3) ---------------- */

  function enabledSections(sections) {
    return (sections || []).filter(function (s) { return s && s.enabled !== false; })
      .slice().sort(function (a, b) { return (a.order || 0) - (b.order || 0); });
  }

  // 板块一级导航:全部 + 启用板块;少于 2 个板块时整条不渲染(D66)
  function sectionNav(sections, activeId) {
    var list = enabledSections(sections);
    if (list.length < 2) return '';
    var active = activeId || 'all';
    var html = '<div class="wrap nav-scroll">';
    html += '<a class="section-tab' + (active === 'all' ? ' active' : '') + '" href="index.html"' +
      (active === 'all' ? ' aria-current="page"' : '') + '>全部</a>';
    list.forEach(function (s) {
      html += '<a class="section-tab' + (active === s.id ? ' active' : '') +
        '" href="index.html?section=' + encodeURIComponent(s.id) + '"' +
        (active === s.id ? ' aria-current="page"' : '') + '>' + esc(s.title) +
        '<span class="tab-count">' + esc(s.count || 0) + '</span></a>';
    });
    return html + '</div>';
  }

  // 门户头条:主位 1 + 副位 2;opts 提供 href/平台/标签/收藏按钮
  function lead(items, opts) {
    opts = opts || {};
    var list = (items || []).slice(0, 4);
    if (!list.length) {
      return '<div class="empty">还没有内容,去采集入口新增第一集 →</div>';
    }
    var cardOpts = function (t) {
      return {
        href: opts.href ? opts.href(t) : '#',
        updated: opts.updated || '',
        platName: opts.plat ? opts.plat(t) : '',
        tags: opts.tags ? opts.tags(t) : [],
        starHtml: opts.star ? opts.star(t) : '',
        pin: opts.pin ? opts.pin(t) : false
      };
    };
    var main = topicCard(list[0], cardOpts(list[0]));
    var side = list.slice(1).map(function (t) {
      var cover = t.cover
        ? '<img src="' + esc(t.cover) + '" alt="" loading="lazy" referrerpolicy="no-referrer">'
        : '<span class="lead-mini-ph">' + esc((t.title || '内').charAt(0)) + '</span>';
      return '<a class="lead-mini" href="' + esc(opts.href ? opts.href(t) : '#') + '">' +
        '<div class="lead-mini-cover">' + cover + '</div>' +
        '<div class="lead-mini-body"><h3>' + esc(t.title) + '</h3>' +
        '<span>' + esc((t.type || 'series') === 'single' ? '单条精选' : (t.count || 0) + ' 条内容') +
        ' · ' + esc(t.latest || opts.updated || '') + '</span></div></a>';
    }).join('');
    return '<div class="lead-main">' + main + '</div>' +
      '<div class="lead-side">' + (side || '<div class="empty">暂无副头条</div>') + '</div>';
  }

  // 板块分节:标题 + 说明 + 计数 + 查看全部;最多 6 张,空板块保留一行占位
  function magazineChapter(section, items, opts, index) {
    var list = (items || []).slice(0, 3);
    var no = (index || 1) < 10 ? '0' + (index || 1) : String(index || 1);
    var head = '<div class="mag-chapter-head"><span class="mag-no">第 ' + no + ' 章</span>' +
      '<h2>' + esc(section.title) + '</h2>' +
      '<p>' + esc(section.description || '') + '</p>' +
      '<a href="index.html?section=' + encodeURIComponent(section.id) + '">本章全部 →</a></div>';
    if (!list.length) {
      return '<section class="mag-chapter is-empty" id="band-' + esc(section.id) + '">' + head +
        '<div class="mag-empty">本章还没有内容,采集后会出现在这里</div></section>';
    }
    var main = list[0];
    var img = opts.hero ? opts.hero(main) : (main.cover || '');
    var cover = img
      ? '<img src="' + esc(img) + '" alt="' + esc(main.title) + '" loading="lazy" referrerpolicy="no-referrer"' +
        ' data-cover="' + esc(main.cover || '') + '">'
      : '<span class="mag-cover-ph">' + esc((main.title || '内').charAt(0)) + '</span>';
    var pin = opts.pin && opts.pin(main) ? '<span class="pin-badge">置顶</span>' : '';
    var hero = '<a class="mag-hero" href="' + esc(opts.href ? opts.href(main) : '#') + '">' +
      '<figure class="mag-cover">' + cover + pin + '</figure>' +
      '<div class="mag-hero-body"><h3>' + esc(main.title) + '</h3>' +
      '<p>' + esc(main.slogan || '') + '</p>' +
      '<span>' + esc((main.type || 'series') === 'single' ? '单条精选' : (main.count || 0) + ' 条内容') +
      ' · ' + esc(main.latest || opts.updated || '') + '</span></div></a>';
    var rows = list.slice(1).map(function (t, i) {
      return '<a class="mag-row" href="' + esc(opts.href ? opts.href(t) : '#') + '">' +
        '<span class="mag-index">' + no + '.' + (i + 2) + '</span>' +
        '<span class="mag-row-title">' + esc(t.title) + '</span>' +
        '<span class="mag-row-meta">' + esc((t.type || 'series') === 'single' ? '单条' : (t.count || 0) + ' 条') + '</span></a>';
    }).join('');
    return '<section class="mag-chapter" id="band-' + esc(section.id) + '">' + head + hero +
      (rows ? '<div class="mag-rows">' + rows + '</div>' : '') + '</section>';
  }

  function magazineToc(sections, items, opts) {
    opts = opts || {};
    var list = (sections || []).filter(function (s) { return s.enabled !== false; });
    if (!list.length) return '';
    var links = list.map(function (s, i) {
      var no = (i + 1) < 10 ? '0' + (i + 1) : String(i + 1);
      return '<a href="#band-' + esc(s.id) + '"><span>' + no + '</span>' + esc(s.title) +
        '<b>' + esc(s.count || 0) + '</b></a>';
    }).join('');
    return '<nav class="mag-toc" aria-label="本刊目录"><span class="mag-toc-title">目录</span>' + links + '</nav>';
  }

  function sectionBand(section, items, opts, index) {
    opts = opts || {};
    if (opts.magazine) return magazineChapter(section, items, opts, index);
    var list = (items || []).slice(0, 6);
    var no = (index || 1) < 10 ? '0' + (index || 1) : String(index || 1);
    var head = '<div class="band-head">' +
      '<div class="band-title"><span class="band-no">' + no + '</span>' +
      '<h2>' + esc(section.title) + '</h2>' +
      '<span class="band-count">' + esc(section.count || 0) + ' 个主题</span></div>' +
      '<div class="band-desc">' + esc(section.description || '') + '</div>' +
      '<a class="band-more" href="index.html?section=' + encodeURIComponent(section.id) + '">查看全部 →</a>' +
      '</div>';
    if (!list.length) {
      return '<section class="section-band" id="band-' + esc(section.id) + '">' + head +
        '<div class="band-empty">本板块还没有内容,采集后会出现在这里</div></section>';
    }
    var cards = list.map(function (t) {
      return topicCard(t, {
        href: opts.href ? opts.href(t) : '#',
        updated: opts.updated || '',
        platName: opts.plat ? opts.plat(t) : '',
        tags: opts.tags ? opts.tags(t) : [],
        starHtml: opts.star ? opts.star(t) : '',
        pin: opts.pin ? opts.pin(t) : false
      });
    }).join('');
    return '<section class="section-band" id="band-' + esc(section.id) + '">' + head +
      '<div class="band-grid">' + cards + '</div></section>';
  }

  // 详情页面包屑:全部主题 / 板块 / 主题(D66 一级导航的落点)
  function breadcrumb(section, title) {
    var html = '<a href="index.html">全部主题</a>';
    if (section && section.id) {
      html += '<span>/</span><a href="index.html?section=' + encodeURIComponent(section.id) + '">' +
        esc(section.title) + '</a>';
    }
    return html + '<span>/</span><span>' + esc(title || '') + '</span>';
  }

  /* ---------------- 四、详情页模板 ---------------- */

  function row(label, value) {
    return '<div class="detail-row"><span class="label">' + label + '</span><span class="value">' + value + '</span></div>';
  }

  function pills(tags, cls) {
    if (!tags || !tags.length) return '';
    return '<div class="' + cls + '">' + tags.map(function (t) {
      return '<i>' + (cls === 'xhs-tags' ? '#' : '') + esc(t) + '</i>';
    }).join('') + '</div>';
  }

  function tagsRow(tags) {
    if (!tags || !tags.length) return '';
    return '<div class="detail-row"><span class="label">标签</span><span class="value">' +
      '<span class="tag-chips">' + tags.map(function (t) { return '<i>' + esc(t) + '</i>'; }).join('') +
      '</span></span></div>';
  }

  // 模板 A:B站视频(页内 iframe 播放)
  function renderBilibili(ctx) {
    var v = ctx.v, plat = ctx.plat;
    var iframeSrc = 'https://player.bilibili.com/player.html?bvid=' + encodeURIComponent(v.bv) +
      '&autoplay=0&danmaku=0&high_quality=1&as_wide=1';
    var rows = row('来源平台', esc(plat)) +
      row('发布者', esc(ctx.author)) +
      row('发布日期', esc(v.date)) +
      row('最近采集', fmtDate(ctx.topic.updated)) +
      tagsRow(ctx.tags) +
      row('视频编号', esc(v.bv));
    return '<div class="tpl-bili"><div class="single-layout">' +
      '<div>' +
        '<div class="player-frame"><iframe src="' + iframeSrc +
          '" scrolling="no" frameborder="0" allowfullscreen="true" title="B站视频 ' + esc(v.bv) + '"></iframe></div>' +
        '<div class="player-fallback">若上方播放器无法播放(部分 UP 主关闭了站外播放),请' +
          '<a href="' + esc(v.url) + '" target="_blank" rel="noopener">前往 B站 观看 →</a></div>' +
        '<div class="parts-slot"></div>' +
        '<div class="desc-box"><h3>简介</h3><p>' + esc(v.desc || '该视频暂无简介。') + '</p></div>' +
      '</div>' +
      '<div class="detail">' +
        '<span class="plat-pill" style="background:' + PLAT_COLORS['B站'] + '">B站 · 视频</span>' +
        '<h1>' + esc(v.title) + '</h1>' +
        '<p class="sub">' + esc(ctx.topic.slogan || '') + '</p>' +
        rows +
        '<a class="watch-btn" href="' + esc(v.url) + '" target="_blank" rel="noopener">前往 B站 观看 →</a>' +
        (ctx.sourceUrl ? '<div class="side-link"><a href="' + esc(ctx.sourceUrl) +
          '" target="_blank" rel="noopener">查看 UP 主主页 →</a></div>' : '') +
      '</div></div></div>';
  }

  // 模板 B:公众号文章(单栏阅读版式)
  function renderWechat(ctx) {
    var v = ctx.v;
    var cover = v.cover
      ? '<img src="' + esc(v.cover) + '" alt="' + esc(v.title) + '" referrerpolicy="no-referrer">'
      : '<div class="cover-ph" style="background:linear-gradient(135deg,#0f5132,#07c160)">' + esc((v.title || '文').charAt(0)) + '</div>';
    var meta = '<span class="wx-name">' + esc(ctx.author || '公众号') + '</span>' +
      (v.date ? '<span>·</span><span>' + esc(v.date) + '</span>' : '') +
      '<span>·</span><span>采集于 ' + fmtDate(ctx.topic.updated) + '</span>';
    return '<div class="tpl-wechat"><article class="wx-article">' +
      '<div class="wx-cover">' + cover + '</div>' +
      '<div class="wx-body">' +
        '<span class="plat-pill" style="background:' + PLAT_COLORS['公众号'] + '">公众号 · 文章</span>' +
        '<h1>' + esc(v.title) + '</h1>' +
        '<div class="wx-meta">' + meta + '</div>' +
        pills(ctx.tags, 'wx-tags') +
        '<p class="wx-lead">' + esc(v.desc || '该文章暂无摘要,点击下方按钮阅读原文。') + '</p>' +
        '<div class="wx-foot">' +
          '<a class="wx-btn" href="' + esc(v.url) + '" target="_blank" rel="noopener">阅读原文 →</a>' +
          '<span class="wx-hint">正文在公众号内,本站仅收录标题、封面与摘要</span>' +
        '</div>' +
      '</div></article></div>';
  }

  // 模板 C:小红书笔记(图左文右)
  function renderXhs(ctx) {
    var v = ctx.v;
    var media = v.cover
      ? '<img src="' + esc(v.cover) + '" alt="' + esc(v.title) + '" referrerpolicy="no-referrer">'
      : '<div class="cover-ph" style="height:100%;background:linear-gradient(135deg,#8c1d2f,#ff2442)">' + esc((v.title || '笔').charAt(0)) + '</div>';
    var initial = esc((ctx.author || '红').charAt(0));
    return '<div class="tpl-xhs"><article class="xhs-card">' +
      '<div class="xhs-media">' + media + '</div>' +
      '<div class="xhs-side">' +
        '<span class="plat-pill" style="background:' + PLAT_COLORS['小红书'] + '">小红书 · 图文笔记</span>' +
        '<h1>' + esc(v.title) + '</h1>' +
        '<div class="xhs-author">' +
          '<span class="xhs-avatar">' + initial + '</span>' +
          '<div><div class="who">' + esc(ctx.author || '小红书用户') + '</div>' +
          '<div class="when">' + esc(v.date || '—') + ' · 采集于 ' + fmtDate(ctx.topic.updated) + '</div></div>' +
        '</div>' +
        pills(ctx.tags, 'xhs-tags') +
        '<p class="xhs-desc">' + esc(v.desc || '该笔记暂无摘要。') + '</p>' +
        '<a class="xhs-btn" href="' + esc(v.url) + '" target="_blank" rel="noopener">打开笔记 →</a>' +
        '<div class="xhs-note">笔记正文需在 App / 网页内查看;封面与标题来自公开分享页。</div>' +
      '</div></article></div>';
  }

  // 模板 D:其他渠道兜底
  function renderGeneric(ctx) {
    var v = ctx.v, plat = ctx.plat;
    var cover = v.cover
      ? '<img src="' + esc(v.cover) + '" alt="' + esc(v.title) + '" referrerpolicy="no-referrer">'
      : '<div class="cover-ph">' + esc((v.title || '内').charAt(0)) + '</div>';
    var isVideo = (v.kind || 'video') === 'video';
    return '<div class="tpl-generic"><div class="single-layout">' +
      '<div>' +
        '<a class="cover-link" href="' + esc(v.url) + '" target="_blank" rel="noopener">' + cover +
          '<span class="read-note">前往 ' + esc(plat) + (isVideo ? ' 观看' : ' 阅读原文') + ' →</span></a>' +
        '<div class="desc-box"><h3>' + (isVideo ? '简介' : '摘要') + '</h3><p>' +
          esc(v.desc || '该内容暂无摘要。') + '</p></div>' +
      '</div>' +
      '<div class="detail">' +
        '<span class="plat-pill" style="background:' + platColor(plat) + '">' +
          esc(plat) + (isVideo ? ' · 视频' : ' · 图文') + '</span>' +
        '<h1>' + esc(v.title) + '</h1>' +
        '<p class="sub">' + esc(ctx.topic.slogan || '') + '</p>' +
        row('来源平台', esc(plat)) +
        row('发布者', esc(ctx.author)) +
        row('发布日期', esc(v.date)) +
        row('最近采集', fmtDate(ctx.topic.updated)) +
        tagsRow(ctx.tags) +
        '<a class="watch-btn" href="' + esc(v.url) + '" target="_blank" rel="noopener">前往 ' + esc(plat) +
          (isVideo ? ' 观看 →' : ' 阅读原文 →') + '</a>' +
      '</div></div></div>';
  }

  // 按渠道选模板:返回 { tpl, label, html }
  function detail(ctx) {
    var v = ctx.v;
    var platKey = ctx.platKey || '';
    var label, tpl, html;
    if (platKey === 'bilibili' && v.bv) {
      tpl = 'bilibili'; label = '单条精选 · B站'; html = renderBilibili(ctx);
    } else if (platKey === 'wechat') {
      tpl = 'wechat'; label = '公众号文章'; html = renderWechat(ctx);
    } else if (platKey === 'xhs') {
      tpl = 'xhs'; label = '小红书笔记'; html = renderXhs(ctx);
    } else {
      tpl = 'generic';
      label = (v.kind === 'article') ? '图文精选' : '单条精选';
      html = renderGeneric(ctx);
    }
    return { tpl: tpl, label: label, html: html };
  }

  // 短标题:去掉【第 N 期】标记与合集同名前缀,过长截断
  function shortTitle(raw, unitTitle) {
    var t = String(raw || '').trim();
    t = t.replace(/^[【\[][^】\]]{1,24}[】\]]\s*/, '');
    var base = String(unitTitle || '').trim();
    if (base && t.indexOf(base) === 0) {
      t = t.slice(base.length).replace(/^[\s:：\-—–|·,，、]+/, '');
    }
    if (!t) t = String(raw || '').trim();
    return t.length > 26 ? t.slice(0, 26) + '…' : t;
  }

  // 多集导航:上一集 / 下一集 + 全集列表
  // 秒 → mm:ss / h:mm:ss
  function fmtDur(sec) {
    var n = Math.max(0, Math.round(Number(sec) || 0));
    var h = Math.floor(n / 3600);
    var m = Math.floor((n % 3600) / 60);
    var s = n % 60;
    var mm = (h ? ('0' + m).slice(-2) : String(m));
    var ss = ('0' + s).slice(-2);
    return (h ? h + ':' + mm : mm) + ':' + ss;
  }

  // 视频详情页的「所属合集 / 分P 目录」:横向可滑动,点分集直接在当前播放区切换
  function parts(video, opts) {
    opts = opts || {};
    var parts = (video && video.parts) || [];
    var season = (video && video.season) || opts.season || null;
    var out = '';

    function strip(heading, note, chips) {
      return '<section class="parts-strip"><div class="parts-head"><h3>' + esc(heading) + '</h3>' +
        '<span class="parts-note">' + esc(note) + '</span>' +
        '<span class="parts-now"></span>' +
        '<button type="button" class="parts-toggle">展开全部</button></div>' +
        '<div class="parts-scroll">' + chips + '</div></section>';
    }

    function chip(no, title, duration, bvid, page) {
      return '<button type="button" class="part-chip" data-play-bvid="' + esc(bvid) + '"' +
        ' data-play-page="' + esc(page || 1) + '" title="在当前播放区播放: ' + esc(title) + '">' +
        '<span class="pc-no">' + esc(no) + '</span>' +
        '<span class="pc-t">' + esc(title) + '</span>' +
        '<span class="pc-d">' + esc(fmtDur(duration)) + '</span></button>';
    }

    if (season && Array.isArray(season.episodes) && season.episodes.length) {
      var eps = season.episodes.map(function (e, idx) {
        return chip(('0' + (idx + 1)).slice(-2), e.title || e.bvid, e.duration, e.bvid, 1);
      }).join('');
      out += strip('所属合集 · ' + (season.title || 'B站合集'), '共 ' + season.episodes.length + ' 集,点分集在上方播放区直接切播', eps);
    }

    if (parts.length > 1) {
      var pitems = parts.map(function (p, idx) {
        return chip('P' + ('0' + (p.p || idx + 1)).slice(-2), p.title || ('第 ' + (idx + 1) + ' P'),
          p.duration, video.bv, p.p || idx + 1);
      }).join('');
      out += strip('分P 目录', '共 ' + parts.length + ' P,点击即在下方播放区播放', pitems);
    }
    return out;
  }

  function episodes(cur, list, unitTitle, unitId) {
    if (!list || list.length < 2) return '';
    var i = list.indexOf(cur);
    var allVideo = list.every(function (x) { return (x.kind || 'video') === 'video'; });
    var unitWord = allVideo ? '集' : '条';

    function href(item, idx) {
      var k = itemKey(item);
      return 'single.html?id=' + encodeURIComponent(unitId || '') +
        (k ? '&k=' + encodeURIComponent(k) : '&i=' + idx);
    }

    var prev = i > 0 ? list[i - 1] : null;
    var next = i < list.length - 1 ? list[i + 1] : null;

    function stepBtn(item, idx, dir) {
      var isPrev = dir === 'prev';
      var dirText = isPrev ? '← 上一' + unitWord : '下一' + unitWord + ' →';
      if (!item) {
        return '<span class="ep-btn ' + dir + ' disabled"><span class="ep-dir">' + dirText + '</span></span>';
      }
      return '<a class="ep-btn ' + dir + '" href="' + href(item, idx) + '">' +
        '<span class="ep-dir">' + dirText + '</span>' +
        '<span class="ep-name">' + esc(shortTitle(item.title, unitTitle)) + '</span>' +
        '</a>';
    }

    var nav = '<nav class="ep-nav">' +
      stepBtn(prev, i - 1, 'prev') +
      '<span class="ep-pos">第 <b>' + (i + 1) + '</b> / ' + list.length + ' ' + unitWord + '</span>' +
      stepBtn(next, i + 1, 'next') +
      '</nav>';

    var items = list.map(function (x, idx) {
      return '<li class="ep-item' + (x === cur ? ' cur' : '') + '">' +
        '<a href="' + href(x, idx) + '">' +
          '<span class="ep-no">' + ('0' + (idx + 1)).slice(-2) + '</span>' +
          '<span class="ep-t">' + esc(x.title) + '</span>' +
          '<span class="ep-d">' + esc(x.date || '') + '</span>' +
        '</a></li>';
    }).join('');

    return nav +
      '<section class="ep-list"><div class="ep-head"><h3>' + (allVideo ? '全集列表' : '全部内容') + '</h3>' +
      '<span>共 ' + list.length + ' ' + unitWord + ' · 按发布顺序</span></div>' +
      '<ol class="ep-items">' + items + '</ol></section>';
  }

  global.Render = {
    esc: esc,
    PLAT: PLAT,
    PLAT_COLORS: PLAT_COLORS,
    platKey: platKey,
    platLabel: platLabel,
    platColor: platColor,
    fmtDate: fmtDate,
    itemKey: itemKey,
    detailHref: detailHref,
    topicCard: topicCard,
    videoCard: videoCard,
    sectionNav: sectionNav,
    lead: lead,
    sectionBand: sectionBand,
    magazineChapter: magazineChapter,
    magazineToc: magazineToc,
    breadcrumb: breadcrumb,
    detail: detail,
    episodes: episodes,
    parts: parts,
    fmtDur: fmtDur,
    shortTitle: shortTitle
  };
})(window);
