---
name: "wordpress-translate"
display_name: "WordPress 翻译"
display_name_en: "WordPress Translate"
description: "WordPress 站点页面翻译：生成 /es/ 等子路径多语言版本，默认 10 种语言并支持追加，不改原文、不换主题、不动 URL 结构，覆盖首页、商品页、博客与全部前台页面，并在前台输出语言切换入口。触发词：WordPress 翻译、WordPress 多语言、/es/ 子路径、网站西班牙语版、页面翻译、语言切换、多语言站点、Polylang、WPML。"
category: "marketing"
version: "1.0.0"
author: "Warm Paw Elle"
---

# WordPress 翻译

## 这个技能做什么

给一个已经上线的 WordPress 站点加多语言版本：原文一个字不动，译文作为独立的语言版本挂到 `/es/`、`/fr/` 这类子路径下，前台给出语言切换入口。

默认一次生成 10 种语言，用户还可以追加任意语言。覆盖首页、页面、文章、商品、分类归档、菜单、模板文案与插件文案，验收时逐项给出可复核的结果，而不是一句“已完成”。

技能先探测站点实际环境（WordPress 版本、主题、页面构建器、已装插件、可用写入接口），再决定走哪条实现路径。不假设站点长什么样。

## 触发条件

**触发**：

- 用户要求给 WordPress 站点做西班牙语版，并通过 `域名/es/` 访问
- 用户要求多语言但明确不换域名、不加子域
- 用户要求默认生成多种语言（10 种或“主流市场全都要”），并支持后续追加
- 用户要求在站点前台提供语言切换入口
- 用户强调“不要动我原来的页面 / 文章 / 产品”，只想加译文

**不触发**：

- 要改 URL 结构（换域名、上子域、加语言参数 `?lang=`）——先说明差异，不在本技能范围内直接执行
- 要翻译一段文本、一封邮件、一份文档——用通用翻译技能
- Shopify 站点的多语言——机制完全不同，用 Shopify 那套
- 只要插件选型建议、不落地——给对比表即可，不要开始改站

**前置条件**（缺一条就停下来说明，不要硬做）：

1. 有站点管理员权限，且至少一种写入通道可用：WP-CLI / SSH / 主机面板文件管理 / REST + 应用密码
2. 站点可正常访问 `wp-json`，或可执行 WP-CLI
3. 本地能拿到数据库快照，或主机面板能一键备份

REST 应用密码单独一条**不足以**完成任务：主流多语言插件都不开放译文关联的写入接口（Polylang 的 REST 译文接口在 Pro 版才有）。REST 只能读，写入需要 WP-CLI 或能执行 PHP 的通道。这一点必须在动手前讲清楚，否则做到一半会卡死。

## 输入参数

```yaml
site:
  base_url: "https://example.com"      # 必填，不带结尾斜杠
  default_language: en                 # 站点现有语言，通常是 en
  access: wp-cli                       # wp-cli | ssh | panel | rest | manual

languages:
  primary_target: es                   # 必须生成的语言，决定 /es/ 路径
  default_set:                         # 默认 10 种，可整组替换
    - es
    - fr
    - de
    - it
    - pt-BR
    - nl
    - pl
    - ja
    - ko
    - zh-Hans
  extra: []                            # 用户追加，如 [ru, tr, ar]
  exclude: []                          # 从默认集里剔除

scope:
  post_types: [page, post, product]    # 依次探测实际存在的类型
  include_home: true
  include_archives: true               # 分类、标签、商品分类、博客列表
  include_theme_strings: true          # 主题模板文案（按钮、页脚、面包屑）
  include_plugin_strings: true         # 插件文案（表单、评论、分页、Woo 流程）
  include_menus: true
  include_seo: true                    # title / description / OG / 结构化数据字段值
  exclude_urls:                        # 内置默认值，按需追加
    - /cart/
    - /checkout/
    - /my-account/
    - /wp-admin/

translation:
  tone: "电商，简洁，不用感叹号，不逐字直译"
  glossary: {}                         # 术语表，优先于模型判断
  keep_verbatim:                       # 原样保留，不翻译
    - 品牌名
    - SKU
    - 型号
    - 价格与数字
    - 代码与占位符
  translate_slugs: false               # 默认保持与原页相同 slug

safety:
  backup: true                         # 动手前必须备份
  dry_run: true                        # 先出清单与差异，确认后再写
```

### 参数规则

| 参数 | 默认 | 说明 |
|---|---|---|
| `site.base_url` | 无，必填 | 猜不出来。缺失就问，不要用示例域名硬跑 |
| `languages.primary_target` | `es` | 用户要 /es/ 就填 `es`；要别的语言改这里，路径随之变化 |
| `languages.default_set` | 10 种 | 用户说“默认 10 种”就原样用；说“再加几个”用 `extra` 追加；说“只要西语”就置空只留 primary |
| `languages.extra` | `[]` | 追加语言写在这里，与默认集合去重后合并 |
| `scope.post_types` | 按站点实际 | 探测到 `product` 才纳入；没有 WooCommerce 就跳过 |
| `scope.exclude_urls` | 见上 | 购物车、结账、账户页属流程页，翻译会破坏支付与登录，默认排除 |
| `translation.translate_slugs` | `false` | 默认不动 slug，保证 URL 结构完全一致。改 true 会引入 301 与旧链接失效，需用户明确要求 |
| `safety.dry_run` | `true` | 第一次跑必须 dry-run，先输出待改清单 |

语言代码用 WordPress locale（`pt-BR`、`zh-Hans`），语言目录段用短码（`/pt/`、`/zh/`）。两者不要混：`/es/` 是路径，`es_ES` 是 locale。

## 处理范围

### 三层文案，缺一层页面就是半中半英

| 层 | 对象 | 默认处理 | 说明 |
|---|---|---|---|
| 内容层 | 页面、文章、商品的标题 / 正文 / 摘要 / 可见自定义字段 | 翻译 | 译文为独立 post，原文不动 |
| 内容层 | 分类、标签、商品分类的名称与描述 | 翻译 | term 译文独立存在，不覆盖原 term |
| 内容层 | 图片 alt、图注 | 默认不翻 | 翻译要改附件记录，违反“媒体不变”，列为可选开关 |
| 模板层 | 主题文案：按钮、页脚、面包屑、空状态、分页 | 翻译 | 优先走语言包（.po/.mo），其次字符串翻译，最后子主题覆盖 |
| 模板层 | 菜单项、小工具标题 | 翻译 | 按语言各一套菜单，不共用 |
| 模板层 | 主题自定义器里的文本（横幅、公告条） | 翻译 | 存的是 option，按语言分别写入 |
| 插件层 | WooCommerce：商品页、购物车、结账、账户、邮件 | 翻译 | 界面文案随 locale 加载官方语言包，端点与邮件需付费 add-on |
| 插件层 | 表单（CF7 / WPForms）、评论、搜索、404 | 翻译 | 表单文案在表单 post 里，属内容层 |
| SEO 层 | title、meta description、OG、canonical、hreflang | 翻译 + 生成 | 字段值翻译，标签结构不变 |
| 流程层 | 购物车、结账、支付、账户、后台 | 不翻 | 默认排除，误翻会导致支付失败 |

### 前台页面清单（逐项确认覆盖）

首页 · 静态页面 · 博客列表 · 博客文章 · 分类/标签归档 · 商品列表 · 商品详情 · 商品分类归档 · 搜索结果 · 404 · 联系页 · 表单页 · 页脚与菜单 · 分页 · 语言切换入口本身

归档与分页是漏翻重灾区：只翻 post 不翻归档，用户点“下一页”会掉回英文。

## 执行步骤

### 第 0 步：预检（只读，不改任何东西）

```bash
curl -s "$BASE/wp-json/" | jq '{name,home,url,gmt_offset,namespaces}'
curl -s "$BASE/wp-json/wp/v2/types" | jq 'to_entries[] | {type:.key, name:.value.name}'
curl -s "$BASE/wp-sitemap.xml" | grep -c "<loc>"
```

有 WP-CLI 时补齐：

```bash
wp core version
wp theme list --status=active --format=json
wp plugin list --status=active --format=json
wp option get permalink_structure
wp option get WPLANG
```

也可以直接跑 `scripts/wp_preflight.py`，一次输出环境报告。要记录的关键项：

- WordPress 版本、PHP 版本、是否多站点
- 主题名与是否子主题；是否区块主题（FSE）
- 页面构建器：Elementor / Divi / WPBakery / Gutenberg / 古腾堡 + 自定义块
- 已装多语言插件（Polylang / WPML / TranslatePress / Weglot）及其版本
- WooCommerce 是否存在，商品类型是否自定义
- 固定链接结构，是否已是目录模式
- `/es/` 是否已被占用（已存在西语内容会冲突）
- 缓存层：对象缓存、页面缓存插件、CDN
- 残留数据：曾装过 TranslatePress 会留下 `wp_trp_*` 表，两套系统并存会互相覆盖

预检结论写进 `preflight.json`，后面所有判断都以它为准，不靠印象。

### 第 1 步：方案闸门（必须停下来等确认）

按预检结果给出唯一推荐路径 + 备选，说明代价，等用户点头再动手。安装插件、升级授权、改固定链接结构都属于「改变站点状态」，不能自作主张。

判据：

- 站点已装 Polylang → 直接沿用，补齐语言即可
- 站点已装 WPML → 沿用，按其 API 走，不要混装 Polylang
- 站点只有 TranslatePress 免费版 + 需要 10 语言 → 说明免费版只支持 1 种额外语言，需升级或换插件
- 什么都没有 + 要 10 语言 + 有商品页 → 推荐 Polylang（免费不限语言）+ 说明 Woo 深度集成需付费 add-on
- 什么都没有 + 只要 1-2 语言 + 页面结构复杂 → TranslatePress 更省事，因为它完全不产生译文 post

### 第 2 步：建语言与 URL 结构

目标形态：英文留在根路径，其他语言进目录。

```
https://example.com/about/          ← 英文（默认语言，隐藏前缀）
https://example.com/es/about/       ← 西语
https://example.com/de/about/       ← 德语
```

要做三件事：

1. URL 模式设为「目录名」（Polylang: 语言 → 设置 → URL 修改 → 目录名）
2. 勾选「隐藏默认语言的前缀」，否则英文会变成 `/en/about/`，等于改了原站 URL
3. 保存固定链接，刷新重写规则：`wp rewrite flush --hard`

建语言时语言目录段用短码，locale 用完整码：

```bash
wp pll lang create "Español" es es_ES 1 ltr
wp pll lang create "Français" fr fr_FR 2 ltr
wp pll lang create "Deutsch" de de_DE 3 ltr
```

`wp pll` 命令不存在时（版本差异），改用 `wp eval-file` 调插件公开函数，或走后台界面建语言。不要为了凑命令去改插件文件。

### 第 3 步：抽取待译文案

从**渲染结果**而不是数据库裸字段抽取，原因：构建器把文本塞在 JSON 或短代码里，直接读 `post_content` 会漏掉一半。

产出 `strings.json`，每条记录：`post_id` / `field` / `block_path` / `source` / `source_hash` / `char_count`。

去重后进翻译记忆库，同一句只翻一次。导航里的 “Shop”、页脚的 “Free shipping over $50” 会在上百个页面重复出现，不去重会翻出上百个版本。

### 第 4 步：翻译

顺序不能颠倒：

1. 先定术语表：品牌名、产品线名、品类词、按钮动词（Shop / Add to cart / Learn more）各语言固定一种译法
2. 占位符保护：把 `<code>`、`%s`、`{{name}}`、短代码整体替换成 token 再送翻，翻完回填
3. 批量翻译，同一批内共享术语表与语气
4. 长度约束：按钮 ≤ 24 字符，导航项 ≤ 18 字符，标题 ≤ 原文 1.3 倍。德语天然比英语长 30%，超了就换更短的表达，不要靠缩字号解决

不允许整段 HTML 直接送翻再塞回去。构建器的 JSON、块注释、短代码属性会被破坏，恢复成本高于重做。

### 第 5 步：写入

每个译文 post 必须复制这些属性，不能只复制正文：

- `post_name`（slug，与原页完全一致）
- `post_status`、`post_date`、`post_parent`、`menu_order`
- `page_template`（页面模板）
- 缩略图 ID、特色图片
- 分类 / 标签 / 商品分类的 term 关系（Polylang 会自动带过去，自建方案需手动映射）
- 商品的 SKU、价格、库存、属性（这些**不翻译**，只继承）

写入后立刻建立语言关联：`pll_save_post_translations(['en'=>101,'es'=>205])`。只建 post 不建关联，切换器找不到对应版本，表现为“切换后 404”。

商品页额外一步：Polylang 需要开启商品这个自定义类型的翻译支持，否则后台看不到译文入口。

### 第 6 步：语言切换入口

按侵入性从低到高选，能用前者就不用后者：

1. 导航菜单里加一个语言切换器菜单项（Polylang 自带，显示全部语言）
2. 区块主题：在页眉模板插入 language switcher 区块，一次改全站生效
3. 经典主题：放进页眉小工具区，或用短代码放进页脚
4. 都不行：子主题 `header.php` 里调 `pll_the_languages()`。**只改子主题，不碰父主题**

10 种语言不能平铺在页眉，移动端会挤爆。用下拉或「当前语言 + 展开」，折叠态只显示当前语言。

### 第 7 步：验收

按下面的验收标准逐条跑，输出矩阵表。任何一条不过，不进第 8 步。

### 第 8 步：交付报告

给出：语言 × 页面覆盖矩阵、未覆盖清单及原因、原文校验结果、遗留风险（付费插件缺口、法律页需人工复核等）、回滚方法。

## 约束规则

### 必须保持的不变量

| 编号 | 不变量 | 判据 |
|---|---|---|
| R1 | 原文内容不变 | 每个原 post 的 `post_title`、`post_content`、`post_excerpt`、`post_name`、`guid`、`post_modified_gmt` 与快照逐字节一致 |
| R2 | 原对象不增不删不改名 | 原 post ID 集合不变，状态不变，数量不变 |
| R3 | 媒体不变 | 附件 ID、`_wp_attached_file`、文件 URL、`srcset`、尺寸全部不变，不上传替换图，不改文件名 |
| R4 | 链接地址不变 | 译文页所有 `href` 去掉语言前缀后，与英文页 `href` 集合完全相等 |
| R5 | 跳转目标不变 | canonical、表单 `action`、按钮目标地址归一化后一致；不新增重定向 |
| R6 | 路由不变 | 译文 URL = `/<lang>/` + 英文 URL 路径，逐字符相同；slug 不加后缀、不改写 |
| R7 | URL 参数不变 | `?utm_`、`?filter=`、`?orderby=`、`?s=` 等查询串原样保留 |
| R8 | 页面结构不变 | 区块顺序、区块数量、短代码及其属性、小工具树、DOM 层级与英文页一致 |
| R9 | 只翻可见文本 | 只改文本节点与 `alt` / `title` / `aria-label` / `placeholder`；`class`、`id`、`data-*`、`style`、JSON-LD 的 `@type` / `@id` 一律不动 |
| R10 | 代码与数字不翻 | `%s`、`{name}`、`{{ }}`、短代码、`<code>`、价格数字、SKU、型号、品牌名原样保留 |
| R11 | 语言互不污染 | 西语页不出现德语残留，德语页不出现西语残留；每种语言独立校验 |

### 允许的系统性写入（需在报告里报备）

- 语言 term 关系：多语言插件会把原文归到默认语言，这会在 `wp_term_relationships` 写行。内容字段不变，属插件运行必需，不算改动原文
- 新增译文 post 行、翻译存储表、缓存表
- 选项：语言列表、URL 模式、hreflang 开关、每语言菜单分配
- 模板层插入切换器（仅限区块模板、小工具、子主题）

### 明确禁止

- 覆盖父主题文件、改插件源码
- 改 `siteurl` / `home`、改固定链接结构（会动到全部原 URL）
- 批量替换原 post 的 slug
- 给附件改名、重新生成缩略图覆盖原图
- 用 301 把英文页跳到某一语言版本
- 把 10 种语言塞进同一份 post 的自定义字段
- 翻译价格、货币符号、数字、日期格式串（日期交给 locale 格式化，不翻字符串）
- 为了“看起来翻全了”翻购物车、结账、支付页

## 验收标准

| 编号 | 验收项 | 通过条件 | 方法 |
|---|---|---|---|
| A1 | 原文零改动 | 全部原 post 的标题 / 正文 / 摘要 / slug / 修改时间哈希与基线一致，差异数 = 0 | 快照 diff |
| A2 | `/es/` 可访问 | 每个译文 URL 返回 200，不是 301/302 跳回英文页，`<html lang="es">` 正确 | 全量 `curl -I` |
| A3 | 切换可用 | 每页存在切换器且包含全部启用语言；点过去再点回来，落地页正确；切换后 404 数 = 0 | 冒烟脚本逐页点 |
| A4 | 覆盖完整 | sitemap 内前台 URL 的译文覆盖率 100%，白名单（结账等）单独列出 | 覆盖率脚本 |
| A5 | 无残留英文 | 译文页可见文本英文句占比 < 2%，无 `translation missing`、无未回填占位符、无裸 token | 抽样 + 正则 |
| A6 | 链接与媒体不变 | 归一化后 `href` / `src` 集合差集为空 | 逐页 diff |
| A7 | 语言齐全 | 10 种默认语言 + 用户追加语言全部建成；每种抽检首页 / 商品 / 文章各 1 | 语言 × 页面矩阵 |
| A8 | hreflang 互指 | 每页含全部语言 + `x-default`，双向互指，无单向声明 | 解析 `<head>` |
| A9 | 结构不变 | 区块数、短代码数、DOM 层级深度与英文页一致 | DOM 计数 |
| A10 | 站点不退化 | 无 5xx；首页 TTFB 增幅 < 30%；后台可正常编辑原内容 | 巡检 + 后台抽查 |

判定口径：

- A1 里“零改动”指内容字段，语言 term 关系不计入，但要在报告里说明
- A5 的 2% 是阈值不是目标，品牌名、产品名、SKU 计入分子时应剔除后再算
- A7 的抽检页固定为：首页、最贵商品、最新文章。三者覆盖模板最复杂的路径

## 输出物

1. `preflight.json`：环境探测结果
2. `strings.json`：抽取的待译文案与来源定位
3. 语言 × 页面覆盖矩阵（Markdown 表）
4. 验收报告 A1–A10，逐项给通过/不通过 + 证据
5. 缺口清单：哪些文案没翻、为什么、要补需要什么代价
6. 回滚步骤：删哪些 post ID、恢复哪些选项、清哪些缓存

## 失败模式与降级

| 现象 | 原因 | 处置 |
|---|---|---|
| `/es/` 404 | 重写规则未刷新 / 缓存未清 | `wp rewrite flush --hard`，清页面缓存与 CDN，再测 |
| 切换后回到英文 | 只建了 post 没建语言关联 | 补 `pll_save_post_translations`，重建关联 |
| 译文页链接全丢语言前缀 | 主题硬编码了相对路径或用 `home_url()` 拼绝对地址 | 用 `pll_home_url()` 或 `product.url` 类接口，改子主题，不改父主题 |
| 页面模板文案仍是英文 | 主题字符串没注册，也不在语言包里 | 用 Loco Translate 生成 `es_ES.mo`；仍不行则子主题覆盖，列入缺口 |
| 商品页半翻 | 免费的 Woo 集成不含端点与邮件 | 报缺口，给出付费 add-on 成本，不要假装翻完了 |
| 归档页退回英文 | 分类 / term 没建译文 | 补 term 译文并建立关联 |
| 保存后原文被改 | 误在原文 post 上覆盖字段 | 立即从备份恢复该 post，重做写入逻辑（必须先建新 post 再写） |
| 两套多语言插件打架 | 旧 TranslatePress 表残留 | 先卸载旧插件并清表，再上新方案 |

## 参考文件

- `references/plugin-matrix.md`：Polylang / WPML / TranslatePress 的能力、成本、写入通道与坑
- `references/text-layers.md`：三层文案的抽取方式，Elementor / Divi / Gutenberg 各自怎么处理
- `references/verification.md`：A1–A10 的具体命令与归一化规则
- `references/pitfalls.md`：URL、缓存、hreflang、Woo、RTL 的已知坑
- `scripts/wp_preflight.py`：只读环境探测
- `scripts/wp_verify.py`：译文页不变量与覆盖率校验
