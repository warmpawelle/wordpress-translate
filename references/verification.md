# 验收怎么跑

每条都给命令和判定口径。跑不完就不要说“已完成”。

## 先做基线（动任何东西之前）

```bash
# 原文指纹：标题、正文、摘要、slug、guid、修改时间
wp db query "
SELECT ID,
       MD5(CONCAT_WS('|', post_title, post_content, post_excerpt,
                     post_name, guid, post_modified_gmt)) AS fp
FROM wp_posts
WHERE post_type IN ('page','post','product')
  AND post_status = 'publish'
ORDER BY ID" --skip-column-names > baseline_posts.tsv

# 对象数量与状态分布
wp db query "SELECT post_type, post_status, COUNT(*) FROM wp_posts
             WHERE post_type NOT IN ('revision','nav_menu_item')
             GROUP BY 1,2" > baseline_counts.tsv

# 附件指纹（媒体不变）
wp db query "SELECT ID, MD5(CONCAT_WS('|', guid, post_title)) FROM wp_posts
             WHERE post_type='attachment'" --skip-column-names > baseline_media.tsv

# 数据库全量备份
wp db export backup_before_i18n.sql
```

没有 WP-CLI 就用主机面板的 phpMyAdmin 导出同样的查询结果。**基线没做，A1 无法判定，不要开工。**

## A1 原文零改动

```bash
# 改动完成后重跑同样查询，与基线 diff
diff baseline_posts.tsv after_posts.tsv && echo "PASS: 原文未变"
diff baseline_media.tsv after_media.tsv && echo "PASS: 媒体未变"
```

判定：差异行数必须为 0。

注意两点：

- `post_modified_gmt` 也在指纹里。有人手动打开原文点了一下“更新”，指纹就会变，这是真实改动信号，要查清原因，不能当误报跳过
- 语言 term 关系变化**不在**此指纹内。这是插件必需的写入，单独记录：`SELECT COUNT(*) FROM wp_term_relationships WHERE term_taxonomy_id IN (...)` 前后对比，报告里说明

## A2 `/es/` 可访问

```bash
while read -r url; do
  code=$(curl -s -o /dev/null -w "%{http_code}" -L --max-redirs 0 "$url")
  loc=$(curl -sI "$url" | grep -i "^location:" | tr -d '\r')
  printf "%s %s %s\n" "$code" "${url}" "${loc}"
done < translated_urls.txt
```

通过条件：

- HTTP 200
- 无 `Location` 头指向英文页（`--max-redirs 0` 下拿到 301/302 即失败）
- `<html lang="es">` 或 `<html lang="es-ES">`，不是 `en`

```bash
curl -s "$BASE/es/" | grep -o '<html[^>]*lang="[^"]*"' | head -1
```

## A3 语言切换可用

三件事都要验：

1. **存在**：每页能找到切换器，且包含全部启用语言（不是只显示当前语言）
2. **可达**：切换器里每个链接的状态码都是 200
3. **往返**：英文 → 西语 → 英文，落地页 URL 与语言都正确

```bash
# 抓切换器里的语言链接
curl -s "$BASE/about/" | grep -oE 'href="[^"]*/(es|fr|de|it|pt|nl|pl|ja|ko|zh)/[^"]*"' | sort -u
```

往返失败最常见的原因是只建了译文 post 没建语言关联。表现：切换器有链接，点过去 404，或跳回英文首页。

## A4 覆盖完整

```bash
# 前台 URL 全集（优先用 sitemap，比遍历 post 表准）
curl -s "$BASE/wp-sitemap.xml" | grep -oE '<loc>[^<]+</loc>' | sed 's/<[^>]*>//g' > sitemap_urls.txt

# 逐个探 /es/ 版本
while read -r u; do
  path=${u#"$BASE"}
  code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/es$path")
  [ "$code" = "200" ] || echo "MISS $code $path"
done < sitemap_urls.txt
```

判定：`MISS` 行数为 0，白名单（`/cart/`、`/checkout/`、`/my-account/`、隐私政策等）单独列出并说明原因。

## A5 无残留英文

抽检页：首页、最贵商品、最新文章，每种语言各 3 页。

```bash
python scripts/wp_verify.py --base-url "$BASE" --lang es --from-sitemap --sample 3
```

判定口径：

- 取正文可见文本（剔除 `script`、`style`、`code`、品牌名、产品名、SKU）
- 统计英文功能词（the / and / with / your / from / this / that / for / you / our）占比
- **< 2% 通过**；2%–8% 人工复核；> 8% 判失败

另外三条硬性检查：

- 页面无 `translation missing`
- 无裸 token（`__TRP_TOKEN_3__` 这类占位符没回填）
- 无连续两个以上英文单词组成的句子（品牌名与产品名除外）

## A6 链接与媒体不变

归一化规则（顺序执行，缺一步就会假失败）：

1. 相对地址按页面 URL 解析成绝对地址
2. 去掉 `/<lang>/` 前缀
3. 去掉结尾斜杠差异
4. 丢弃 `#` 锚点
5. 丢弃 `mailto:`、`tel:`、`javascript:`
6. 丢弃动态参数：`_wpnonce`、`ver`、`nocache`、`preview`
7. `srcset` 只取文件名集合，不比尺寸描述符

然后比对 `href` 集合与 `src` 集合：

```bash
python scripts/wp_verify.py --base-url "$BASE" --lang es --from-sitemap
```

判定：差集为空。出现差异通常是主题把链接写死成绝对地址，或者翻译时误改了 `href`。

## A7 语言齐全

输出矩阵，不要口头保证：

| 语言 | 首页 | 商品页 | 文章页 | 归档 | 切换器 |
|---|---|---|---|---|---|
| es | 200 | 200 | 200 | 200 | 有 |
| fr | … | … | … | … | … |

判定：10 种默认语言 + 用户 `extra` 全部在表内，每格 200 且切换器存在。

## A8 hreflang 互指

```bash
curl -s "$BASE/es/about/" | grep -oE '<link[^>]+hreflang="[^"]+"[^>]*>'
```

通过条件：

- 页面含全部启用语言的 `hreflang`
- 含 `x-default`
- **双向**：英文页也声明了西语，西语页也声明了英文。单向声明 Google 会忽略
- 语言代码与语言目录一致（`es` 对应 `/es/`）

## A9 结构不变

```bash
# 区块数 / 短代码数
curl -s "$BASE/about/"   | grep -c "<!-- wp:"
curl -s "$BASE/es/about/"| grep -c "<!-- wp:"

curl -s "$BASE/about/"   | grep -oE '\[/?(vc_|et_pb_|gallery|contact-form)[a-z_]*' | sort | uniq -c
curl -s "$BASE/es/about/"| grep -oE '\[/?(vc_|et_pb_|gallery|contact-form)[a-z_]*' | sort | uniq -c
```

判定：区块数、短代码种类与数量一致，差异为 0。DOM 深度差 1 级以内算通过（语言包可能引入额外的 `<span>`）。

## A10 站点不退化

- 全站抽 30 个 URL，状态码无 5xx
- 首页 TTFB 与基线相比增幅 < 30%
- 后台能正常打开发布文章，编辑器不报“区块包含意外内容”
- 清除缓存后 `/es/` 仍 200（排除缓存掩盖 404）

```bash
curl -s -o /dev/null -w "ttfb=%{time_starttransfer}s code=%{http_code}\n" "$BASE/"
```

## 缓存别忘

配置语言后 404 十有八九是缓存：

```bash
wp rewrite flush --hard
wp cache flush
# 再清页面缓存插件与 CDN（Cloudflare / 阿里云 CDN）
```

先清缓存再跑 A2，否则会把缓存问题误判成配置失败，也可能反过来——缓存命中导致 404 被掩盖。
