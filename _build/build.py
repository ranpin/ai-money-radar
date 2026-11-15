#!/usr/bin/env python3
"""Build ai-money-radar: data/*.json -> static HTML into dist/.

Run from repo root:  python3 _build/build.py

数据是唯一真相源（data/*.json）；本脚本只做渲染，不含任何内容硬编码。
情报流/案例/工具/打法的条目增删改都只动 JSON，不动这里。
"""
import json
import os
import shutil
from collections import Counter, OrderedDict
from html import escape

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DATA = os.path.join(ROOT, "data")
DIST = os.path.join(ROOT, "dist")

CSS = open(os.path.join(HERE, "template.css"), encoding="utf-8").read()

# 雷达图标 favicon（data URI，URL-encoded SVG）
FAVICON = (
    "%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
    "%3Crect width='32' height='32' rx='7' fill='%231a67eb'/%3E"
    "%3Ccircle cx='16' cy='16' r='9' fill='none' stroke='%23fff' stroke-width='2'/%3E"
    "%3Ccircle cx='16' cy='16' r='4.5' fill='none' stroke='%23fff' stroke-width='2'/%3E"
    "%3Ccircle cx='16' cy='16' r='1.6' fill='%23fff'/%3E"
    "%3Cline x1='16' y1='16' x2='24' y2='8' stroke='%23fff' stroke-width='2'/%3E%3C/svg%3E"
)


def load(name):
    with open(os.path.join(DATA, name), encoding="utf-8") as f:
        return json.load(f)


meta = load("meta.json")
cases = load("cases.json")
claims = load("claims.json")
tools = load("tools.json")
plays = load("plays.json")
news = load("news.json")

SITE = meta["site"]
GRADES = meta["evidence_grades"]
CASE_BY_ID = {c["id"]: c for c in cases}
CLAIM_BY_ID = {c["id"]: c for c in claims}

NAV = [
    ("index.html", "首页"),
    ("news.html", "情报流"),
    ("cases.html", "案例库"),
    ("tools.html", "工具库"),
    ("plays.html", "打法图谱"),
    ("insights.html", "收入洞察"),
    ("about.html", "方法"),
]

# 主题脚本内联：复用主站 localStorage['ranpin-theme']，与 ranpin.github.io 全站明暗同步。
# 必须在首屏绘制前同步执行，避免闪烁（FOUC）。
THEME_JS = """
(function(){var K='ranpin-theme';function apply(t){document.documentElement.setAttribute('data-theme',t);
var m=document.querySelector('meta[name=theme-color]');if(m)m.setAttribute('content',t==='dark'?'#0f172a':'#f8fafc');}
try{apply(localStorage.getItem(K)==='dark'?'dark':'light');}catch(e){apply('light');}
window.toggleTheme=function(){var n=document.documentElement.getAttribute('data-theme')==='dark'?'light':'dark';
apply(n);try{localStorage.setItem(K,n);}catch(e){}sync();};
function sync(){var d=document.documentElement.getAttribute('data-theme')==='dark';
var i=document.querySelectorAll('.theme-icon');for(var k=0;k<i.length;k++)i[k].textContent=d?'\\u2600\\ufe0f':'\\ud83c\\udf19';}
document.addEventListener('DOMContentLoaded',sync);})();
"""

FILTER_JS = """
function filterBy(btn, group, attr){
  var wrap=document.getElementById(group);
  var btns=wrap.previousElementSibling.querySelectorAll('button');
  for(var i=0;i<btns.length;i++)btns[i].classList.remove('on');
  btn.classList.add('on');
  var v=btn.getAttribute('data-v');
  var items=wrap.querySelectorAll('[data-'+attr+']');
  for(var j=0;j<items.length;j++){
    items[j].style.display=(v==='all'||items[j].getAttribute('data-'+attr)===v)?'':'none';
  }
}
"""


def e(s):
    return escape(str(s), quote=True) if s is not None else ""


def grade_badge(g, label=None):
    g = (g or "").upper()
    cls = g.lower() if g in ("A", "B", "C", "D") else "plain"
    text = label or (GRADES.get(g, {}).get("label", g) if g else "—")
    return f'<span class="badge {cls}" title="{e(GRADES.get(g, {}).get("desc", ""))}">{e(text)}</span>'


def layout(title, active, body, desc=None):
    nav_html = "".join(
        f'<a href="{href}"{" class=\"active\"" if href == active else ""}>{e(label)}</a>'
        for href, label in NAV
    )
    return f"""<!DOCTYPE html>
<html lang="zh-CN" data-theme="light">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{e(title)} · {e(SITE['name_zh'])}</title>
<meta name="description" content="{e(desc or SITE['description'])}">
<meta name="theme-color" content="#f8fafc">
<link rel="canonical" href="{e(SITE['base_url'])}{e(active)}">
<link rel="icon" href="data:image/svg+xml,{FAVICON}">
<style>{CSS}</style>
<script>{THEME_JS}</script>
</head>
<body>
<header class="top-nav">
  <a class="logo" href="index.html">{e(SITE['name'])}<small>{e(SITE['name_zh'])}</small></a>
  <nav>{nav_html}</nav>
  <div class="right">
    <button class="theme-btn" onclick="toggleTheme()" aria-label="切换主题"><span class="theme-icon">🌙</span></button>
  </div>
</header>
<main class="wrap">
{body}
<footer class="foot">
  <span>© 2026 {e(SITE['name'])} · 数据仅供研究参考</span>
  <span>更新 {e(SITE['updated'])}</span>
  <span class="sp"><a href="{e(SITE['repo'])}">GitHub</a> · <a href="about.html">方法与免责</a></span>
</footer>
</main>
<script>{FILTER_JS}</script>
</body>
</html>
"""


def write(name, html):
    with open(os.path.join(DIST, name), "w", encoding="utf-8") as f:
        f.write(html)


# ---------------------------------------------------------------- 首页
def build_index():
    n_cases = len(cases)
    n_tools = len(tools)
    n_claims = len(claims)
    n_news = len(news)
    n_plays = len(plays)
    n_grade_a = sum(1 for c in claims if c.get("evidence_grade") == "A")

    hl = meta["headline"]
    headline = f"""<a class="headline" href="{e(hl['href'])}">
  <span class="tag">{e(hl['tag'])} · 头条</span>
  <h3>{e(hl['title'])}</h3>
  <p>{e(hl['summary'])}</p>
  <div class="date">{e(hl['date'])} · 阅读全文 →</div>
</a>"""

    counters = f"""<div class="counters">
  <div class="counter"><div class="n">{n_news:,}</div><div class="l">情报</div></div>
  <div class="counter"><div class="n">{n_cases}</div><div class="l">案例</div></div>
  <div class="counter"><div class="n">{n_plays}</div><div class="l">变现打法</div></div>
  <div class="counter"><div class="n">{n_tools}</div><div class="l">工具与费率</div></div>
  <div class="counter"><div class="n">{n_claims}</div><div class="l">收入主张</div></div>
  <div class="counter"><div class="n">{n_grade_a}</div><div class="l">A 级证据</div></div>
</div>"""

    findings = "".join(
        f"""<div class="card"><a class="card-link" href="{e(f['href'])}">{e(f['title'])}</a>
<div class="desc">{e(f['body'])}</div></div>"""
        for f in meta["key_findings"]
    )

    dbs = "".join(
        f"""<a class="card" href="{href}" style="text-decoration:none">
<div class="cta">{e(label)} →</div>
<div class="desc">{e(desc)}</div></a>"""
        for href, label, desc in [
            ("cases.html", "案例库", "博主与独立开发者档案：定位、渠道、收入主张与证据等级、可复现动作"),
            ("tools.html", "工具库", "AI 编程/建站工具定价、付费载体费率、联盟返佣比例"),
            ("plays.html", "打法图谱", "8 类变现模式：客单价、启动门槛、天花板、流量依赖度、风险"),
            ("insights.html", "收入洞察", "证据等级分布、口径分布、X 归因分布、客单价分布"),
            ("news.html", "情报流", "按天梳理的行业信号：政策、数据、复盘、方向转变"),
        ]
    )

    latest_news = "".join(
        f"""<div class="item" data-type="{e(it['type'])}">
  <div class="date">{e(it['date'])}</div>
  <div class="body">
    <div class="title">{e(it['title'])}</div>
    <div class="sum">{e(it['summary'][:110])}{'…' if len(it['summary']) > 110 else ''}</div>
    <div class="tags"><span class="badge plain">{e(it['type'])}</span>{grade_badge(it.get('evidence_grade'))}</div>
  </div>
</div>"""
        for it in news[:6]
    )

    body = f"""<section class="hero">
  <div class="eyebrow"><span class="live-dot"></span>LIVE · AI 变现情报</div>
  <h1>{e(SITE['tagline'])}</h1>
  <p class="lede">{e(SITE['description'])} 每条收入主张都标注<b>证据等级</b>与<b>口径</b>——本站目前 <b>0 条 A 级独立可核验样本</b>（{n_grade_a}/{n_claims}），这不是缺陷，是这类数据的真实状态。</p>
  {counters}
  <div class="stat-note">统计截止：{e(SITE['updated'])}。金额口径逐条标注，不可跨条相加或年化。</div>
</section>

{headline}

<h2>核心发现<a class="more" href="insights.html">收入洞察 →</a></h2>
<div class="grid c2">{findings}</div>

<h2>探索情报库<a class="more" href="cases.html">全部案例 →</a></h2>
<div class="grid c3">{dbs}</div>

<h2>最新情报<a class="more" href="news.html">查看全部 →</a></h2>
<div class="feed">{latest_news}</div>

<div class="box warn"><div class="t">⚠️ 阅读前必读</div>
<p>{e(SITE['disclaimer'])} 口径纪律：含工资不能写作「自媒体变现」；单月 ×12 ≠ 全年；MRR/ARR ≠ 已到账现金；公司营收 ≠ 老板个人净赚。<a href="about.html">完整方法与免责 →</a></p></div>"""

    write("index.html", layout("首页", "index.html", body))


# ---------------------------------------------------------------- 情报流
def build_news():
    types = sorted({it["type"] for it in news})
    btns = '<button class="on" data-v="all" onclick="filterBy(this,\'feed\',\'type\')">全部</button>' + "".join(
        f'<button data-v="{e(t)}" onclick="filterBy(this,\'feed\',\'type\')">{e(t)}</button>' for t in types
    )
    items = "".join(
        f"""<div class="item" data-type="{e(it['type'])}">
  <div class="date">{e(it['date'])}</div>
  <div class="body">
    <div class="title">{f'<a href="{e(it["source_url"])}">{e(it["title"])}</a>' if it.get('source_url') else e(it['title'])}</div>
    <div class="sum">{e(it['summary'])}</div>
    <div class="tags"><span class="badge plain">{e(it['type'])}</span>{grade_badge(it.get('evidence_grade'))}{''.join(f'<span class="badge plain">{e(t)}</span>' for t in it.get('tags', [])[:4])}</div>
  </div>
</div>"""
        for it in sorted(news, key=lambda x: x["date"], reverse=True)
    )
    body = f"""<h1>情报流</h1>
<p class="subtitle">按天梳理的 AI 变现行业信号：平台政策、公开数据、当事人复盘、方向转变。共 {len(news)} 条。</p>
<div class="filters">{btns}</div>
<div class="feed" id="feed">{items}</div>
<div class="box"><div class="t">关于证据等级</div><p>每条情报标注 A/B/C/D。B = 本人披露（无法单凭自述确认真实性与成本），C = 第三方转述，D = 无收入证据。详见<a href="about.html">方法页</a>。</p></div>"""
    write("news.html", layout("情报流", "news.html", body))


# ---------------------------------------------------------------- 案例库
def build_cases():
    types = ["全部"] + sorted({c["type"] for c in cases})
    btns = "".join(
        f'<button{" class=\"on\"" if t == "全部" else ""} data-v="{"all" if t == "全部" else e(t)}" onclick="filterBy(this,\'caselist\',\'type\')">{e(t)}</button>'
        for t in types
    )

    cards = []
    for c in sorted(cases, key=lambda x: (x.get("evidence_grade") or "Z", x["name"])):
        cl = [CLAIM_BY_ID[i] for i in c.get("claim_ids", []) if i in CLAIM_BY_ID]
        claim_rows = "".join(
            f"""<tr><td>{e(x['amount_display'])}</td><td>{e(x['period'])}</td><td>{e(x['caliber'])}</td>
<td>{grade_badge(x['evidence_grade'])}</td></tr>"""
            for x in cl
        )
        claim_tbl = (
            f'<div class="tbl-wrap"><table><thead><tr><th>金额</th><th>期间</th><th>口径</th><th>证据</th></tr></thead><tbody>{claim_rows}</tbody></table></div>'
            if cl
            else '<p class="small muted">无收入主张记录（证据等级 D：禁止宣传「年入百万/千万」）。</p>'
        )
        limits = "".join(
            f"<li>{e(l)}</li>" for x in cl for l in x.get("limitations", [])
        )
        actions = "".join(f"<li>{e(a)}</li>" for a in c.get("actions", []))
        quotes = "".join(f"<li>「{e(q)}」</li>" for q in c.get("key_quotes", []))
        srcs = "".join(f'<li><a href="{e(s)}">{e(s.replace("https://", ""))[:60]}</a></li>' for s in c.get("sources", []))
        aud = f'{c["audience"]:,}' if c.get("audience") else "未披露"

        cards.append(f"""<details class="card" data-type="{e(c['type'])}" id="{e(c['id'])}" style="display:block">
<summary>
  <span style="font-weight:700">{e(c['name'])}</span>
  <span class="mono small muted">{e(c.get('handle') or '—')}</span>
  {grade_badge(c.get('evidence_grade'))}
  <span class="badge plain">{e(c['type'])}</span>
  <span class="badge plain">{e(c.get('region') or '')}</span>
</summary>
<div class="dbody">
  <p><b>定位：</b>{e(c['positioning'])}</p>
  <p class="small"><b>受众：</b><span class="mono">{aud}</span> · {e(c.get('audience_note') or '')}　<b>平台：</b>{e(c.get('platform') or '—')}</p>
  <p class="small"><b>变现渠道：</b>{e('、'.join(c.get('channels') or []) or '未披露')}</p>
  <p class="small"><b>自有产品：</b>{e('、'.join(c.get('own_products') or []) or '无')}{('　<span class="muted">— ' + e(c['own_products_note']) + '</span>') if c.get('own_products_note') else ''}</p>
  <h3>收入主张</h3>
  {claim_tbl}
  {f'<h3>可复现动作</h3><ul>{actions}</ul>' if actions else ''}
  {f'<h3>关键原话</h3><ul>{quotes}</ul>' if quotes else ''}
  {f'<p class="small"><b>备注：</b>{e(c["notes"])}</p>' if c.get('notes') else ''}
  {f'<h3>口径限制与风险</h3><ul class="small">{limits}</ul>' if limits else ''}
  {f'<h3>来源</h3><ul class="small">{srcs}</ul>' if srcs else ''}
</div>
</details>""")

    body = f"""<h1>案例库</h1>
<p class="subtitle">博主与独立开发者档案：定位、变现渠道、收入主张（带证据等级与口径）、可复现动作。共 {len(cases)} 例。点击展开。</p>
<div class="filters">{btns}</div>
<div id="caselist" style="display:flex;flex-direction:column;gap:9px">{''.join(cards)}</div>
<div class="box warn"><div class="t">⚠️ 读这些数字之前</div>
<p>全库 <b>无一条 A 级（独立可核验）证据</b>，最高只到 B（本人自述）。所有金额都是<b>流水口径</b>而非利润，且大多无法归因到 X 平台。案例库原文：「目前公开数据不存在本研究已独立认证的个人年净所得千万级样本。」</p></div>"""
    write("cases.html", layout("案例库", "cases.html", body))


# ---------------------------------------------------------------- 工具库
def build_tools():
    cats = sorted({t["category"] for t in tools})
    btns = '<button class="on" data-v="all" onclick="filterBy(this,\'toollist\',\'cat\')">全部</button>' + "".join(
        f'<button data-v="{e(c)}" onclick="filterBy(this,\'toollist\',\'cat\')">{e(c)}</button>' for c in cats
    )
    rows = []
    for t in sorted(tools, key=lambda x: (x["category"], x["name"])):
        price = "<br>".join(
            f'{e(p["tier"])}：<b class="mono">{e(p["price"])}</b>' for p in t.get("pricing", [])
        ) or "—"
        aff = e(t["affiliate"]) if t.get("affiliate") else "—"
        mrr = f'<b class="mono">{e(t["public_mrr"])}</b>' if t.get("public_mrr") else "—"
        rows.append(f"""<tr data-cat="{e(t['category'])}">
<td><b>{e(t['name'])}</b><br><span class="small muted">{e(t['category'])}</span></td>
<td>{price}{f'<div class="small muted">{e(t["annual_note"])}</div>' if t.get('annual_note') else ''}</td>
<td class="small">{aff}</td><td class="small">{mrr}</td>
<td class="small">{grade_badge('', t.get('evidence'))}</td>
<td class="small">{e(t.get('notes') or '')}{f' <a href="{e(t["url"])}">↗</a>' if t.get('url') else ''}</td>
</tr>""")
    body = f"""<h1>工具库</h1>
<p class="subtitle">AI 编程/建站工具定价、付费载体费率、联盟返佣比例。共 {len(tools)} 项。价格随时变动，用前复核。</p>
<div class="filters">{btns}</div>
<div class="tbl-wrap" id="toollist"><table>
<thead><tr><th>工具</th><th>定价</th><th>联盟返佣</th><th>公开 MRR</th><th>证据</th><th>备注</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>
<div class="box ok"><div class="t">选型速查</div><ul>
<li><b>冷启动付费专栏</b>：小报童 15% &lt; 知识星球 20%；年收入破 10 万后切知识星球（降到 10%）</li>
<li><b>出海收款</b>：优先 Lemon Squeezy（5% + 50¢，是 MoR，代缴全球税）；Stripe 不是 MoR，需自己处理税务</li>
<li><b>AI 建站</b>：Lovable / bolt.new 都是 $25/月档起步；Lovable 代码与项目归用户所有</li>
<li><b>Claude Code</b>：官方 $200/月太贵 → 中转月包 289 元/月（⚠️ 有封号/掺假风险）</li>
</ul></div>"""
    write("tools.html", layout("工具库", "tools.html", body))


# ---------------------------------------------------------------- 打法图谱
def build_plays():
    cards = []
    for p in plays:
        steps = "".join(f"<li>{e(s)}</li>" for s in p.get("steps", []))
        risks = "".join(f"<li>{e(r)}</li>" for r in p.get("risks", []))
        reps = "、".join(
            f'<a href="cases.html#{e(r)}">{e(CASE_BY_ID[r]["name"])}</a>' if r in CASE_BY_ID else e(r)
            for r in p.get("representatives", [])
        ) or "—"
        tc = "、".join(p.get("toolchain", [])) or "—"
        dep = "否" if not p.get("traffic_dependent") else "是"
        cards.append(f"""<details class="card" id="{e(p['id'])}" style="display:block">
<summary>
  <span style="font-weight:700">{e(p['name'])}</span>
  <span class="badge plain">{e(p['category'])}</span>
  <span class="badge b">{e(p['unit_price'])}</span>
  <span class="badge {'ok' if not p.get('traffic_dependent') else 'hot'}">依赖流量：{dep}</span>
</summary>
<div class="dbody">
  <div class="tbl-wrap"><table><tbody>
    <tr><th style="width:130px">卖什么</th><td>{e(p['what_you_sell'])}</td></tr>
    <tr><th>谁付钱、为什么</th><td>{e(p['why_they_pay'])}</td></tr>
    <tr><th>客单价</th><td><b>{e(p['unit_price'])}</b></td></tr>
    <tr><th>需要多少受众</th><td>{e(p['audience_needed'])}{f'　<span class="muted">（{e(p["traffic_dependent_note"])}）</span>' if p.get('traffic_dependent_note') else ''}</td></tr>
    <tr><th>启动门槛</th><td>{e(p['startup_barrier'])}</td></tr>
    <tr><th>天花板</th><td>{e(p['ceiling'])}</td></tr>
    <tr><th>见效速度</th><td>{e(p.get('time_to_first_revenue') or '—')}</td></tr>
    <tr><th>获客</th><td>{e(p['acquisition'])}</td></tr>
    <tr><th>工具链</th><td class="small">{e(tc)}</td></tr>
    <tr><th>成本</th><td>{e(p['cost'])}</td></tr>
    <tr><th>代表案例</th><td class="small">{reps}　{grade_badge(p.get('evidence_grade'))}</td></tr>
  </tbody></table></div>
  {f'<h3>步骤</h3><ol>{steps}</ol>' if steps else ''}
  {f'<div class="box"><div class="t">关键洞察</div><p>{e(p["key_insight"])}</p></div>' if p.get('key_insight') else ''}
  {f'<h3>风险</h3><ul class="small">{risks}</ul>' if risks else ''}
</div>
</details>""")

    cmp_rows = "".join(
        f"""<tr><td><a href="#{e(p['id'])}"><b>{e(p['name'])}</b></a></td><td>{e(p['unit_price'])}</td>
<td>{e(p['audience_needed'])}</td><td>{'否' if not p.get('traffic_dependent') else '是'}</td>
<td>{e(p['startup_barrier'])}</td><td>{e(p['ceiling'])}</td></tr>"""
        for p in plays
    )

    body = f"""<h1>打法图谱</h1>
<p class="subtitle">8 类变现模式的完整拆解：客单价、启动门槛、天花板、流量依赖度、步骤、风险。点击展开。</p>

<div class="box"><div class="t">⭐ 核心模型：客单价决定你是否需要先有流量</div>
<p>3~5 万元/项目的企业交付一年只需 10~20 个客户；399 元/永久的社群需要数千粉。<b>没有流量的人不应该从低客单价起步。</b></p></div>

<h2>横向对比</h2>
<div class="tbl-wrap"><table>
<thead><tr><th>打法</th><th>客单价</th><th>需要多少受众</th><th>依赖流量</th><th>启动门槛</th><th>天花板</th></tr></thead>
<tbody>{cmp_rows}</tbody></table></div>

<h2>逐个拆解</h2>
<div id="playlist" style="display:flex;flex-direction:column;gap:9px">{''.join(cards)}</div>"""
    write("plays.html", layout("打法图谱", "plays.html", body))


# ---------------------------------------------------------------- 收入洞察
def bars(counter, total, grade_cls=False):
    out = []
    for k, v in counter.most_common():
        pct = (v / total * 100) if total else 0
        cls = ""
        if grade_cls:
            g = (k or "")[0:1].lower()
            cls = f" g-{g}" if g in ("a", "b", "c", "d") else " g-d"
        out.append(
            f"""<div class="bar-row"><div class="lbl">{e(k or '未标注')}</div>
<div class="bar-track"><div class="bar-fill{cls}" style="width:{pct:.1f}%"></div></div>
<div class="val">{v}</div></div>"""
        )
    return "".join(out)


def build_insights():
    total = len(claims)
    g_dist = Counter(c.get("evidence_grade") for c in claims)
    subj_dist = Counter(c.get("subject") for c in claims)
    attr_dist = Counter(c.get("x_attribution") for c in claims)
    kind_dist = Counter(c.get("kind") for c in claims)
    salary = sum(1 for c in claims if c.get("includes_salary"))
    with_amount = [c for c in claims if c.get("amount")]

    attr_label = {
        "creator_claimed": "creator_claimed（本人明确归因 X）",
        "unknown": "unknown（未知）",
        "related_unquantified": "related_unquantified（相关但无法量化）",
        "not_established": "not_established（未建立）",
    }
    attr_named = Counter(attr_label.get(k, k) for k in attr_dist.elements())

    rows = "".join(
        f"""<tr><td><a href="cases.html#{e(CASE_BY_ID[c['case_id']]['id'])}">{e(CASE_BY_ID[c['case_id']]['name'])}</a></td>
<td class="num">{e(c['amount_display'])}</td><td>{e(c['currency'] or '—')}</td><td>{e(c['period'])}</td>
<td>{e(c['subject'])}</td><td class="small">{e(c['caliber'])}</td>
<td>{grade_badge(c['evidence_grade'])}</td><td class="small mono">{e(c['x_attribution'])}</td></tr>"""
        for c in sorted(claims, key=lambda x: (x.get("amount") or 0), reverse=True)
    )

    body = f"""<h1>收入洞察</h1>
<p class="subtitle">{total} 条结构化收入主张的分布与口径。所有金额均为公开主张，未经独立审计。</p>

<div class="box err"><div class="t">🔴 最重要的一条：A 级证据 = {g_dist.get('A', 0)} 条</div>
<p>案例库原文：「目前公开数据不存在本研究已独立认证的个人年净所得千万级样本。」所有「千万级」都是公司营收、历史营收、采访标题或 ARR，<b>不是个人净收入</b>，且几乎都无法归因到 X 平台。</p></div>

<h2>证据等级分布</h2>
<div class="bars">{bars(g_dist, total, grade_cls=True)}</div>
<p class="small muted">A 独立可核验 · B 本人披露 · C 第三方转述 · D 无收入证据</p>

<h2 id="attribution">X 归因分布</h2>
<div class="bars">{bars(attr_named, total)}</div>
<div class="box warn"><div class="t">X 几乎从不直接产生收入</div>
<p>{total} 条主张里，本人明确归因于 X 的只有 <b>{attr_dist.get('creator_claimed', 0)} 条</b>。Jacky Chou 案例的反事实原文：「若移除 X，SEO、服务、联盟和短租仍可能带来收入；缺少渠道对照，不能把总收入归因于 X。」⇒ <b>X 是信任与获客前端，不是收入来源本身。</b></p></div>

<h2>收入主体分布</h2>
<div class="bars">{bars(subj_dist, total)}</div>
<p class="small muted">其中 <b>{salary}</b> 条明确含工资（含工资不能写作「自媒体变现」）。</p>

<h2>主张类型分布</h2>
<div class="bars">{bars(kind_dist, total)}</div>
<p class="small muted">self_report 本人自述 · business_claim 业务口径主张 · undisclosed 未披露</p>

<h2>全部收入主张明细</h2>
<div class="tbl-wrap"><table>
<caption>按金额降序。⚠️ 币种不同、口径不同、期间不同，<b>不可跨行相加或比较</b>。</caption>
<thead><tr><th>案例</th><th class="num">金额</th><th>币种</th><th>期间</th><th>主体</th><th>口径</th><th>证据</th><th>X 归因</th></tr></thead>
<tbody>{rows}</tbody></table></div>

<h2>口径纪律（引用任何数字前必过）</h2>
<div class="box"><ul>{''.join(f'<li>{e(r)}</li>' for r in meta['caliber_rules'])}</ul></div>"""
    write("insights.html", layout("收入洞察", "insights.html", body))


# ---------------------------------------------------------------- 方法
def build_about():
    grade_rows = "".join(
        f"""<tr><td>{grade_badge(k)}</td><td>{e(v['desc'])}</td><td class="small">{e(v['limit'])}</td></tr>"""
        for k, v in GRADES.items()
    )
    body = f"""<h1>方法与免责</h1>
<p class="subtitle">这个站怎么采数据、怎么分级、怎么标注口径，以及它不承诺什么。</p>

<h2>定位</h2>
<p>{e(SITE['name_zh'])}（{e(SITE['name'])}）追踪「用 AI 赚钱」的真实信号：案例、产品、打法与收入主张。板块设计参考 <a href="https://theroboradar.com/">theroboradar.com</a> 的情报库形态（资讯/公司/产品/技术/资本/人物 → 情报流/案例库/工具库/打法图谱/收入洞察），<b>内容全部自建，不复制其数据、设计与品牌</b>。</p>

<h2>证据分级</h2>
<p>沿用开源案例库 <a href="https://github.com/AIPMAndy/chinese-x-creators">AIPMAndy/chinese-x-creators</a> 的标准。最高原则：<b>千万级企业经营结果 ≠ 千万级 X 内容收入 ≠ 创作者个人年净收入。</b></p>
<div class="tbl-wrap"><table><thead><tr><th>等级</th><th>含义</th><th>限制</th></tr></thead><tbody>{grade_rows}</tbody></table></div>

<h2>口径纪律</h2>
<div class="box warn"><ul>{''.join(f'<li>{e(r)}</li>' for r in meta['caliber_rules'])}</ul></div>

<h2>标注纪律</h2>
<ul>
<li>每条关键信息标注来源 URL，并区分 <b>一手</b>（本人原话）/ <b>二手</b>（第三方转述）/ <b>推断</b>（分析）</li>
<li>找不到的信息明确写「未找到公开信息」，<b>不用行业常识或合理猜测填充数字</b></li>
<li>价格、费率、佣金比例这类数字必须有来源</li>
<li>单个来源抓取失败就换来源，不反复重试</li>
</ul>

<h2>数据来源与更新机制</h2>
<p><b>半自动</b>：GitHub Actions 每日定时抓取原始数据快照到 <code>raw/&lt;日期&gt;/</code>（只抓不分析，CI 内不调用任何 LLM），分析与结构化由人在本地完成后写入 <code>data/*.json</code>，再构建发布。</p>
<p>当前抓取源：GitHub 案例库（<code>creators.json</code> / <code>revenue_claims.json</code>）、Hacker News Algolia API、博主个人站（marclou.com / weijunext.com 等）、工具定价页（Cursor / Lovable / bolt.new / v0 / DataFast）。</p>
<p><b>不可达来源</b>（不尝试）：X/推特（反爬）、Product Hunt（需 auth）、小红书（需登录）。</p>

<h2>双层结构</h2>
<p>本站是<b>公开脱敏层</b>：只放对他人也有价值且无风险的内容（工具定价、平台费率、变现模式分类、案例的证据分级拆解）。不含任何人的微信号等 PII、不含带追踪参数的返佣链接、不含人身指向的批判性措辞、不含站主个人的变现策略与收支记账——那些留在私有研究仓 <code>ai-monetization-lab</code>。</p>

<h2>差异化</h2>
<p>同类情报站通常只笼统写「汇集全球行业媒体报道」，不声明是否人工审核。本站<b>每条收入主张都带证据等级 + 口径标注 + 来源链接 + 限制条款</b>，并在首页直接挂出「A 级证据 = 0 条」。这既是诚实，也是这类站最缺的公信力。</p>

<h2>免责声明</h2>
<div class="box err"><p>{e(SITE['disclaimer'])}</p>
<p>本站不构成对任何个人或机构的指控、评价或推荐。所有收入数字均为公开主张的转录与归类，标注了证据等级与口径限制；若与本人原话冲突，以直接披露为准。发现错误欢迎提 Issue。</p>
<p>加密资产及其推广涉及高风险，地域法规差异大，本站相关内容不构成投资建议。</p></div>

<h2>仓库</h2>
<ul>
<li>本站（公开）：<a href="{e(SITE['repo'])}">{e(SITE['repo'].replace('https://', ''))}</a></li>
<li>研究仓（私有）：<code>ai-monetization-lab</code>——调研全文、个人策略、实验与收支记账</li>
</ul>"""
    write("about.html", layout("方法与免责", "about.html", body))


# ---------------------------------------------------------------- main
def main():
    if os.path.isdir(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)
    build_index()
    build_news()
    build_cases()
    build_tools()
    build_plays()
    build_insights()
    build_about()
    # 静态资源
    shutil.copy(os.path.join(HERE, "template.css"), os.path.join(DIST, "template.css"))
    with open(os.path.join(DIST, ".nojekyll"), "w") as f:
        f.write("")
    pages = [f for f in sorted(os.listdir(DIST)) if f.endswith(".html")]
    print(f"built {len(pages)} pages -> dist/")
    for p in pages:
        size = os.path.getsize(os.path.join(DIST, p))
        print(f"  {p:16s} {size/1024:6.1f} KB")
    print(f"data: {len(cases)} cases, {len(claims)} claims, {len(tools)} tools, {len(plays)} plays, {len(news)} news")


if __name__ == "__main__":
    main()
