# AI Money Radar · AI 变现情报库

🔗 **在线站点：<https://ranpin.github.io/ai-money-radar/>**

持续扫描「用 AI 赚钱」的每一个真实信号：案例、产品、打法与收入主张。板块设计参考 [theroboradar.com](https://theroboradar.com/) 的情报库形态，**内容全部自建**。每条收入主张都标注**证据等级（A/B/C/D）+ 口径 + 来源链接**——本站目前 **0 条 A 级独立可核验样本**，这不是缺陷，是这类数据的真实状态。

> ⚠️ 站内数据仅供研究参考，不构成投资建议或收入承诺。所有收入数字均为公开主张，未经独立审计。

## 板块

| 页面 | 内容 |
|---|---|
| 首页 | LIVE 计数器、头条、核心发现、数据库入口 |
| 情报流 `news.html` | 按天梳理的行业信号：政策、数据、复盘、方向转变 |
| 案例库 `cases.html` | 博主/独立开发者档案：定位、渠道、收入主张、可复现动作 |
| 工具库 `tools.html` | AI 编程/建站工具定价、付费载体费率、联盟返佣比例 |
| 打法图谱 `plays.html` | 8 类变现模式：客单价、门槛、天花板、流量依赖、风险 |
| 收入洞察 `insights.html` | 证据等级 / X 归因 / 收入主体 / 主张类型的分布与明细 |
| 方法 `about.html` | 证据分级标准、口径纪律、来源与更新机制、免责 |

## 目录结构

```
data/            # 结构化数据（唯一真相源，改内容只动这里）
  meta.json      #   站点元信息、证据分级定义、口径纪律、头条、核心发现
  cases.json     #   案例库
  claims.json    #   收入主张（带证据等级、口径、限制）
  tools.json     #   工具与费率
  plays.json     #   变现打法
  news.json      #   情报流
_build/          # 生成器：build.py + template.css → dist/
scraper/         # 每日抓取管线（只抓不分析，CI 内不调用 LLM）
raw/             # 抓取到的原始快照（由 scrape workflow 提交）
.github/workflows/
  scrape.yml     #   每日定时抓取 → 提交 raw/
  deploy.yml     #   push 到 main → build → 部署 Pages
```

## 本地构建与预览

```bash
python3 _build/build.py          # data/*.json → dist/
cd dist && python3 -m http.server 8000
```

依赖：Python 3.11+，标准库即可（build.py 不依赖第三方包）。

## 数据更新流程（半自动）

1. **GitHub Actions 每日抓取**：`scrape.yml` 定时抓原始数据快照到 `raw/<日期>/`（只抓不分析，不调用 LLM）。
2. **本地分析**：人读 `raw/`，把有价值的信号结构化进 `data/*.json`。
3. **构建发布**：push 到 main，`deploy.yml` 自动 build 并部署 Pages。

抓取源：GitHub 案例库（`AIPMAndy/chinese-x-creators`）、Hacker News Algolia API、博主个人站、工具定价页。不可达源（X / Product Hunt / 小红书）不尝试。

## 约定

- **证据分级**：A 独立可核验 / B 本人披露 / C 第三方转述 / D 无收入证据（禁止宣传「年入百万/千万」）。
- **口径纪律**：含工资不写「自媒体变现」；单月 ×12 ≠ 全年；MRR/ARR ≠ 已到账现金；公司营收 ≠ 个人净赚；严禁拿粉丝数乘系数估算收入。
- **标注纪律**：每条信息标来源并区分一手/二手/推断；找不到的写「未找到公开信息」，不用猜测填充数字。
- **双层结构**：本仓是**公开脱敏层**，只放对他人有价值且无风险的内容；不含任何人的 PII、返佣追踪参数、人身指向措辞、站主个人策略与收支——那些在私有研究仓 `ai-monetization-lab`。

## 许可

本人原创内容按 CC-BY-4.0；引用的第三方收入主张与原文归各自权利人，本站仅作带出处的转录与归类。
