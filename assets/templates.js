/* 集页 · 版式注册表(D65/D68)
 * 新增一套版式:在 layouts/ 放一个 CSS,在下方 list 里加一条,页脚切换器自动出现。
 * 能力声明(nav/lead/bands/sidebar/toc)只作为渲染开关,供 render.js 在 M3/M4 读取;
 * 注册表不含颜色与尺寸,版式差异全部写在对应的 layouts/*.css。
 */
window.TEMPLATES = {
  default: 'standard',
  list: {
    standard: {
      label: '简洁',
      desc: '单列 Hero + 卡片网格(现行)',
      file: 'assets/layouts/standard.css',
      nav: false,
      lead: false,
      bands: false,
      sidebar: false,
      toc: false
    },
    news: {
      label: '门户',
      desc: '板块导航 + 头条区 + 分节 + 侧栏',
      file: 'assets/layouts/news.css',
      nav: true,
      lead: true,
      bands: true,
      sidebar: true,
      toc: false
    },
    magazine: {
      label: '画册',
      desc: '单栏宽幅 + 章节编号 + 目录',
      file: 'assets/layouts/magazine.css',
      nav: true,
      lead: false,
      bands: true,
      sidebar: false,
      toc: true
    }
  }
};
