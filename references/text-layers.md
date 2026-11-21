# 三层文案怎么抽

只翻 `post_content` 一定会漏。漏掉的部分不会报错，只会安静地显示英文，验收时才发现，返工成本翻倍。

正确做法是**从渲染后的 HTML 反查**：抓一份英文页，提取可见文本节点，记录它来自哪个字段或哪个模板，再逐条替换。

## 内容层

| 对象 | 字段 | 注意 |
|---|---|---|
| 页面 / 文章 | `post_title`、`post_content`、`post_excerpt` | 摘要常被主题用在卡片和列表，漏翻列表页就是英文 |
| 商品 | `post_title`、`post_content`（长描述）、`post_excerpt`（短描述） | 短描述出现在商品列表与购物车，优先翻 |
| 商品属性 | term 名称 | 颜色、尺码这类属性值是 term，不是字符串 |
| 自定义字段 | 仅前台可见的 | 先扫描渲染 HTML 确认哪些真的显示了，别按字段名字猜 |
| 分类 / 标签 | `name`、`description` | 归档页标题来自这里 |
| 菜单项 | `post_title`（nav_menu_item） | 每种语言一套菜单对象 |

### Gutenberg

块结构必须保留。`<!-- wp:paragraph -->` 注释是结构的一部分，删了编辑器会提示区块损坏。

只改 `innerHTML` 里的文本节点：

```php
$blocks = parse_blocks($content);
// 递归：只处理有 innerHTML 的块，属性里的 url / id / className 一律不动
// 序列化用 serialize_blocks()，不要自己拼字符串
```

图片块要翻的是 `attrs.alt`，不是 `attrs.url`。按钮块要翻 `attrs.text`，`attrs.url` 保持原值。

### Elementor

文本全在 `_elementor_data` 这一个 JSON 字符串里。**不能正则替换整串**——引号、转义、嵌套结构会被打坏。

```php
$data = json_decode(get_post_meta($id, '_elementor_data', true), true);
// 递归遍历 $data，命中的键只有：
//   settings.title / settings.editor / settings.text / settings.description
//   settings.button_text / settings.heading / settings.testimonial_content
// 明确跳过的键：
//   _id, settings.link.url, settings.image.url, settings.url, elType, widgetType
```

写的字段名以实际 JSON 为准，不同 widget 的键名不一样，先用 `jq` 把树打出来看一眼再写映射表。

### Divi

短代码包裹，文本在开闭标签之间：

```
[et_pb_text _builder_version="4.27" ...]这里是要翻的[/et_pb_text]
```

规则：只改 `]` 与 `[/` 之间的部分，属性一律不动。`admin_label` 是后台标签，前台不显示，不用翻。

### WPBakery

同理，`[vc_column_text]...[/vc_column_text]` 之间是正文。`[vc_single_image image="123"]` 这类只带属性的短代码整条跳过。

### 经典编辑器

纯 HTML。用 DOM 解析后只改文本节点，`href`、`src`、`class`、`style`、`data-*` 全部保留。

## 模板层

主题文案不随页面走，改一次全站生效。

处理顺序：

1. **语言包优先**。主题用 `__()` / `_e()` 且带 textdomain 的，用 Loco Translate 生成 `es_ES.po/.mo` 即可，不动任何代码。这是唯一零风险的方式
2. **字符串翻译**。插件把字符串注册到 Polylang String Translation / WPML String Translation 后，在后台逐条翻
3. **子主题覆盖**。前两条都覆盖不到才用。只建子主题改 `header.php` / `footer.php`，父主题一行不动

常见漏翻点，逐个确认：

- 页眉公告条（存 `theme_mod`，不是 post）
- 页脚版权与备案信息
- 面包屑的 “Home” / “You are here”
- 分页的 “Previous” / “Next” / “Page 2 of 7”
- 空状态：“No products found”
- 搜索框 placeholder 与按钮
- 404 页文案
- Cookie 同意条
- 返回顶部、加载更多

## 插件层

| 插件 | 文案位置 | 处理 |
|---|---|---|
| WooCommerce | 商品页按钮、购物车、结账、账户、邮件 | 界面文案随 locale 自动加载官方语言包；端点 slug 与邮件模板需付费 add-on |
| 联系表单 | 表单 post 内的字段标签 + 提交后的提示语 | 表单本身当内容翻；提示语属插件设置 |
| 评论 | “Leave a reply”、字段标签 | 主题或插件语言包 |
| 搜索 | 结果计数、无结果提示 | 主题语言包 |

WooCommerce 的邮件模板是最容易被忽略的一环：客户下完单收到英文邮件，前面的翻译全白做。验收时要单独测一封订单邮件。

## 不翻译清单

这些看起来像文本，翻了会出问题：

- 价格、货币符号、数字、百分比、尺寸
- SKU、型号、条码、订单号
- 品牌名、注册商标、产品系列代号
- URL、路径、文件名、邮箱地址、电话
- HTML 属性值：`class`、`id`、`data-*`、`style`、`action`、`method`
- 短代码名与属性：`[gallery ids="1,2"]` 里的 `gallery` 和 `ids`
- 占位符：`%s`、`%1$s`、`{name}`、`{{ variable }}`
- 代码块内容
- JSON-LD 的 `@type`、`@id`、`@context`
- 用户生成内容：评论正文、晒单、问答（翻了就不是用户说的了）

## 抽取的最小实现

```python
# 伪代码，重点是判定顺序
for node in visible_text_nodes(html):
    if node.inside('script', 'style', 'code', 'pre'):   continue
    if node.text.strip() == '':                          continue
    if is_numeric_or_price(node.text):                   continue
    if matches_keep_verbatim(node.text):                 continue
    record(node.text, path=node.xpath, source_id=post_id)
```

`path` 一定要记，否则回写时不知道这一段来自哪。用 XPath 或「区块序号 + 字段名」都行，只要能唯一定位。
