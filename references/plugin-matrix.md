# 多语言插件对照

决定方案的不是功能表，而是**能不能被脚本写入**。10 种语言、上百个页面，靠后台手点不现实。

## 一张表看完

| | Polylang 免费 | Polylang Pro + Woo | WPML | TranslatePress 免费 | TranslatePress 付费 |
|---|---|---|---|---|---|
| 语言数量 | 不限 | 不限 | 不限 | **1 种额外语言** | 不限（多语言 add-on） |
| 每语言独立目录（`/JP/`、`/CN/`） | 支持 | 支持 | 支持 | 支持 | 支持 |
| 原文是否被改 | 不改内容，新增译文 post | 同左 | 不改内容，新增译文 post | 完全不改，译文存独立表 | 同左 |
| 译文 slug 可改 | 否（Pro 才有） | 是 | 是 | 否（SEO Pack 才有） | 是 |
| 语言切换器 | 区块 / 小工具 / 菜单项 | 同左 | 同左 | 短代码 / 菜单项 / 浮层 | 同左 + 独立菜单 |
| hreflang | 自动 | 自动 | 自动 | 自动 | 自动 |
| 字符串翻译 | 有 | 有 | 有（String Translation） | 可视化点选 | 同左 |
| WooCommerce | 商品内容可翻，端点/邮件不行 | 完整 | 完整（WooCommerce Multilingual） | 免费版含商品与流程 | 完整 |
| 自动翻译 | DeepL（Pro，自带 key） | 同左 | 自动翻译（消耗 credits） | Google（自带 key） | 自家 AI + DeepL |
| REST 写入译文 | **无** | 有 | 有限 | 无 | 无 |
| 可脚本化 | `wp eval-file` + 插件函数 | 同左 | `wp eval-file` + `wpml_*` 函数 | **几乎不可脚本化** | 同左 |
| 成本 | 免费 | 按年订阅 | 按年订阅 | 免费 | 按年订阅 |

## 选型判据

按顺序问四个问题：

1. **要几种语言？** 超过 2 种 → 排除 TranslatePress 免费版
2. **有没有商品页？** 有 WooCommerce 且要翻购物车/邮件/端点 → Polylang 需付费 add-on，或选 WPML
3. **要不要重复执行？** 要（新文章持续产出、要能重跑校验）→ 必须能脚本化，只剩 Polylang / WPML
4. **站点已装了什么？** 已装就沿用。两套多语言插件并存必然互相覆盖，迁移成本高于新增

结论：**默认推荐 Polylang 免费版**（10 语言零成本、目录 URL 原生、可脚本化），把 Woo 的深度集成缺口如实报给用户，由他决定要不要买 add-on。

## Polylang 的写入路径

优先顺序：

```bash
# 1. 插件自带命令，先确认存在
wp help pll

# 2. 不存在则用插件公开函数（最稳，跨版本）
wp eval-file setup_languages.php
```

`setup_languages.php` 的核心调用：

```php
// 建语言（只在缺失时）
if (!pll_languages_list() || !in_array('es', pll_languages_list())) {
    // 语言对象通过 PLL_Admin_Model::add_language() 或后台建，避免直接写 term
}

// 复制原文为译文草稿
$new_id = wp_insert_post([
    'post_title'   => $translated_title,
    'post_content' => $translated_content,
    'post_excerpt' => $translated_excerpt,
    'post_name'    => $original->post_name,   // slug 保持一致
    'post_status'  => 'publish',
    'post_type'    => $original->post_type,
    'post_parent'  => $translated_parent_id,
    'menu_order'   => $original->menu_order,
    'page_template'=> get_page_template_slug($original->ID),
], true);

// 设语言 + 建关联，两步都不能省
pll_set_post_language($new_id, 'es');
pll_save_post_translations(array_merge(
    pll_get_post_translations($original->ID),
    ['es' => $new_id]
));
```

要点：

- `pll_save_post_translations` 接收的是**全量映射**，不是增量。传单条会把其他语言关联冲掉
- 缩略图用 `set_post_thumbnail($new_id, get_post_thumbnail_id($original->ID))`，共用同一附件，不新建媒体
- 商品需先在 Polylang 设置里勾选 `product` 这个自定义类型的翻译支持

## WPML 的写入路径

```php
// 复制到目标语言（保留 slug、模板、父子关系）
$new_id = apply_filters('wpml_copy_post_to_language', $original_id, $lang, false);

// 设置语言归属
wpml_set_element_language_details([
    'element_id'   => $new_id,
    'element_type' => 'post_' . get_post_type($new_id),
    'trid'         => $trid,
    'language_code'=> $lang,
    'source_language_code' => 'en',
]);
```

WPML 的价格与授权按站点数计，多站部署前先确认授权范围。它的自动翻译按字符消耗 credits，批量前先估算用量，别跑到一半停住。

## TranslatePress 的写入路径

没有公开的写入 API。译文存在 `wp_trp_dictionary_<source>_<target>` 表里，直接写表能成，但表结构随版本变动，升一次级就可能全废。

因此只有两种情况选它：

- 只要 1-2 种语言，页面结构复杂（大量构建器内容），人工在页面上点选比脚本抽取更省事
- 站点已经用它，且翻译量不大

要求 10 语言 + 可重跑校验时不要选它。

## 迁移注意

- 从 TranslatePress 迁到 Polylang：先导出译文、卸载插件、清 `wp_trp_*` 表，再建语言。残留表会让新插件的语言判定错乱
- 从 WPML 迁到 Polylang：语言 term 前缀不同（`wpml_` vs `pll_`），迁移后必须重建关联，不能只改前缀
- 任何迁移前先做数据库全量备份。译文可以重做，原文丢了不可逆
