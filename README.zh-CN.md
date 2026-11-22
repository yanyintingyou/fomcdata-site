# fomcdata-site

[English](README.md)

美联储公开市场委员会研究相关的公开数据源索引，另附一份取自公开序列的市场快照。

在线地址：<https://fomcdata.dpdns.org>

## 站点内容

索引分五组共 21 个来源：美联储、国际组织、财政与跨境资本、市场与监管、文献。每条给出发布机构、域名，以及一句话说明这个来源收什么数据。

快照跟踪五个分组共 35 个序列。利率组包括目标区间、EFFR、SOFR、2/10/30 年美债收益率、利差、实际利率、通胀预期、美联储资产负债表、逆回购与 IORB。通胀组包括 CPI、核心 CPI、PCE、核心 PCE 与密歇根预期。就业组包括失业率、U6、非农、参与率、时薪、职位空缺与初请。市场组包括标普 500、黄金、WTI、VIX、广义美元指数、NFCI 与高收益、投资级利差。

| 分组 | 序列 | 来源 | 起点 |
|---|---|---|---|
| 利率 | 目标区间、SOFR、美债收益率、利差、实际利率、通胀预期、资产负债表、逆回购、IORB | FRED | 1996–2021，视序列而定 |
| 通胀 | CPI、核心 CPI、PCE、核心 PCE、密歇根预期 | FRED | 1996 |
| 就业 | 失业率、U6、非农、参与率、时薪、职位空缺、初请 | FRED | 1996 |
| 市场 | 标普 500、黄金、WTI、VIX | Yahoo Finance | 1996–2000 |
| 市场 | 广义美元指数、NFCI、高收益与投资级利差 | FRED | 1996–2023 |

六个页面共用一份样式和三个脚本：索引、图表工作台、宏观卡片、FOMC 日历、研究、关于。图表工作台支持最多四个指标对比、区间与坐标切换、窗口统计，以及 CSV、PNG、SVG 导出。视图状态写在查询串里，可以直接分享。

页面默认英文。点「中文」会切换全部文字、页面标题和图表标签，选择保存在 `localStorage`。

## 数据怎么更新

`scripts/fetch_data.py` 在 GitHub Actions 里每天 23:17 UTC 跑一次。FRED 请求走六个线程，Yahoo 串行、两次重试。日频与周频序列抓最近 400 天，月频序列抓全量，保证同比基数与年度修订。90 天以前按周采样，5 年以前按月采样。

输出为 `public/data/meta.json` 加三个分组文件：`rates.json`、`macro.json`、`markets.json`。清单保存标签与最新值，页面只在打开某个指标时才取对应分组。任务提交 `public/data` 并部署 Worker，点位没有变化时跳过提交。

推送到 main 只部署当前文件，不抓数据。要手动刷新数据，在 Actions 页面运行 `deploy` 工作流。

## 抓取失败时

脚本保留这个序列已有的点，标记 `stale: true`，把错误写进 `warnings`，其余序列照常更新。页面上该指标的格子会多出一个小圆点，图表下方注明数据截至哪一天。

FRED 和 Yahoo 要的 User-Agent 不同：FRED 用普通标识，Yahoo 用浏览器标识。脚本按域名分别设置，两边都带重试，等待时间逐次拉长。

## 目录

```
public/                索引、图表、宏观、日历、研究、关于、404
public/style.css       设计令牌与组件
public/site.js         语言切换与页面元信息
public/data.js         取数、窗口、统计、URL 状态
public/chart.js        SVG 绘图、十字准线、导出
public/data/           meta、rates、macro、markets、calendar
scripts/fetch_data.py  抓取、合并、降采样、标记失败序列
.github/workflows/     每日刷新与部署
wrangler.toml          Worker 名称与资源目录
```

Worker 只提供静态资源。

## 本地预览

```
python -m http.server -d public 8123
```

## 部署

GitHub Actions 用 `cloudflare/wrangler-action` 部署，读取两个仓库密钥：

- `CLOUDFLARE_API_TOKEN`，权限为 `Account › Workers Scripts › Edit`
- `CLOUDFLARE_ACCOUNT_ID`

在本机部署时，把 token 放进环境变量，运行 `npx wrangler deploy`。

## 许可

站点代码用 MIT，见 `LICENSE`。`public/data/` 里的数据按来源条款，逐条列在 `LICENSE-DATA.md`。研究数据集单独成库发布，各带许可证与 DOI。

## 说明

定时任务通常在 23:17 UTC 之后半小时内启动。

索引里的链接指向第三方站点，数据归各发布方所有。本仓库没有许可证文件。
