# fomcdata-site

[English](README.md)

美联储公开市场委员会研究相关的公开数据源索引，另附一份取自公开序列的市场快照。

在线地址：<https://fomcdata.dpdns.org>

## 站点内容

索引分五组共 21 个来源：美联储、国际组织、财政与跨境资本、市场与监管、文献。每条给出发布机构、域名，以及一句话说明这个来源收什么数据。

快照跟踪七个序列，画在同一张图上，区间可选 1Y、3Y、5Y、10Y、20Y、30Y。鼠标移到图上会出现十字准线和当天的数值。

| 序列 | 来源 | 频率 | 起点 |
|---|---|---|---|
| 联邦基金有效利率 | FRED `DFF` | 日 | 1996 |
| CPI 同比 | FRED `CPIAUCSL`，本站计算 | 月 | 1997 |
| 失业率 | FRED `UNRATE` | 月 | 1996 |
| 标普 500 | Yahoo Finance `^GSPC` | 日 | 1996 |
| 黄金期货主力合约 | Yahoo Finance `GC=F` | 日 | 2000 |
| WTI 原油期货主力合约 | Yahoo Finance `CL=F` | 日 | 2000 |
| VIX | Yahoo Finance `^VIX` | 日 | 1996 |

六个页面共用一份样式和三个脚本：索引、图表工作台、宏观卡片、FOMC 日历、研究、关于。图表工作台支持最多四个指标对比、区间与坐标切换、窗口统计，以及 CSV、PNG、SVG 导出。视图状态写在查询串里，可以直接分享。

页面默认英文。点「中文」会切换全部文字、页面标题和图表标签，选择保存在 `localStorage`。

## 数据怎么更新

`scripts/fetch_data.py` 在 GitHub Actions 里每天 23:00 UTC 跑一次，时点在美股收盘之后。每次只抓最近 400 天，再合并进已经存下的历史。90 天以前的部分按周采样，30 年历史压在一个 180 KB 的文件里。脚本提交新的 `public/data/market.json`，随后部署 Worker。

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
public/data/           market.json、calendar.json
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

定时任务通常在 23:00 UTC 之后半小时内启动。

索引里的链接指向第三方站点，数据归各发布方所有。本仓库没有许可证文件。
