# WordPress 翻译

`wordpress-translate` — 每种语言一个独立目录（`/JP/`、`/CN/`、`/ES/`），一次生成 10 种语言，原文不动。

给 WordPress 站点加多语言版本：日语 `/JP/`、中文 `/CN/`、西班牙语 `/ES/`、德语 `/DE/`，一种语言一个目录段。原文不动、URL 结构不动、主题不换，默认 10 种语言，可追加任意语言。

## 它解决的不是“翻译”问题

装个多语言插件就能翻译，这话只对了一半。真正会翻车的是后面几件事：

- 译文页的链接还指向英文页，读者点两下就掉回英文
- 只翻了文章，归档、分页、菜单、页脚还是英文
- 原文被顺手改了，客户发现首页文案变了
- 切了 10 种语言，验收时说不清哪页翻了哪页没翻

这个技能把「怎么翻」和「怎么证明翻对了」放在一起：先探测站点实际环境，再选实现路径，最后逐项出验收结果。

## 安装

```bash
git clone <this-repo> wordpress-translate
cp -r wordpress-translate ~/.workbuddy/skills/
# 或 Claude Code: cp -r wordpress-translate ~/.claude/skills/
```

重启会话后对它说：「给 example.com 加多语言，日语走 /JP/、中文走 /CN/，默认 10 种语言」。

## 快速开始（手动）

```bash
# 1. 探测站点：版本、主题、插件、post type、sitemap、多语言状态
python scripts/wp_preflight.py --base-url https://example.com --segments ES,JP,CN --json preflight.json

# 2. 按 references/plugin-matrix.md 选实现路径（默认 Polylang + 目录 URL）

# 3. 建语言、写译文、装切换器（见 SKILL.md 第 2-6 步）

# 4. 验收：状态码、html lang、链接集合、媒体集合、区块数、残留英文
python scripts/wp_verify.py --base-url https://example.com --segment JP --locale ja --from-sitemap
```

两个脚本都只读，不改站点。`wp_verify.py` 退出码 0 表示全部通过，1 表示有失败项。

Windows 上用 Git Bash 时，路径参数会被 MSYS 改写，加 `MSYS_NO_PATHCONV=1`：

```bash
MSYS_NO_PATHCONV=1 python scripts/wp_verify.py --base-url https://example.com --segment JP --paths "/,/about/"
```

## 会输出什么

| 产物 | 内容 |
|---|---|
| `preflight.json` | WP 版本、主题、插件、post type 数量、固定链接形态、sitemap、各目录段是否已被占用 |
| 覆盖矩阵 | 语言 × 目录段 × 页面，逐格 200 / 缺失 |
| 验收报告 | A1–A10 逐项结论 + 证据 |
| 缺口清单 | 哪些文案没翻、为什么、补齐要什么代价 |
| 回滚步骤 | 删哪些 post ID、恢复哪些选项、清哪些缓存 |

## 硬前提

- 需要写入通道：WP-CLI、SSH、主机面板或 REST + 应用密码。**只有 REST 应用密码不够**，主流多语言插件都不开放译文关联的写入接口
- 动手前必须有数据库备份
- 购物车、结账、账户页默认排除，翻错会直接坏支付

## 不做什么

- 不换域名、不加子域、不用 `?lang=` 参数（改了 URL 结构就不是“原文不动”了）
- 不把 10 种语言塞进同一个 `/es/`：每种语言必须有自己的目录段，共用会串内容
- 不翻用户生成内容（评论、晒单）
- 不保证机器翻译的法律页可直接上线，这类页面标人工复核
- 不替你做插件采购决策：10 语言 + 完整 WooCommerce 覆盖需要付费插件，技能会报价，选择权在你

## 文件

```
SKILL.md                        技能主体：触发条件、参数、范围、约束、验收
references/plugin-matrix.md     Polylang / WPML / TranslatePress 的能力与写入路径
references/text-layers.md       三层文案怎么抽，构建器内容怎么改
references/verification.md      A1–A10 的命令与判定口径
references/pitfalls.md          已知的坑，按踩到频率排序
scripts/wp_preflight.py         只读环境探测
scripts/wp_verify.py            译文页不变量与覆盖率校验
```
