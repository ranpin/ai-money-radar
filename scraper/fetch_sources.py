#!/usr/bin/env python3
"""ai-money-radar 每日抓取管线：抓取公开来源 → 原样快照（gzip）→ 写 manifest。

刻意不做任何分析/摘要/抽取，也绝不调用 LLM——分析由人后续在本地完成。
依赖仅 stdlib + pyyaml（urllib 抓取），可在 GitHub Actions 直接运行。

体积控制（关键）：
  - 所有快照 gzip 压缩（HTML 约 10x）。
  - 内容哈希去重：与 raw/state.json 里该源上次的 sha256 比对，
    内容没变就不落新文件、只在 manifest 记 "unchanged"。
    这样个人站/定价页这类很少变的源不会每天重复占空间，
    仓库体积 ≈ 只在内容真正变化时增长。

输出布局（日期为 UTC）：
    raw/<YYYY-MM-DD>/<source_id>.<ext>.gz   内容有变化的源（gzip 快照）
    raw/<YYYY-MM-DD>/manifest.json           本次 run 的逐源状态记录
    raw/state.json                           每源最近一次的 sha256/日期/文件（去重用）

用法：
    python3 scraper/fetch_sources.py                          # 抓全部源，写 raw/<今天 UTC>/
    python3 scraper/fetch_sources.py --sources datafast,hn_mrr # 调试：只抓指定源
    python3 scraper/fetch_sources.py --date 2026-11-15        # 指定快照目录日期
    python3 scraper/fetch_sources.py --out-dir /tmp/x         # 调试：改输出根目录
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import http.client
import json
import sys
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path
from urllib import error, parse, request

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("缺少依赖 pyyaml，请先: pip install pyyaml")

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
SOURCES_YAML = SCRIPT_DIR / "sources.yaml"

USER_AGENT = "ai-money-radar-bot/1.0 (+https://ranpin.github.io/ai-money-radar)"
TIMEOUT_S = 20.0
MAX_RETRIES = 2           # 首次之外的重试次数（共 3 次尝试）
BACKOFF_BASE_S = 2.0      # 指数退避：2s → 4s
SLEEP_BETWEEN_SOURCES_S = 1.5

EXT_BY_TYPE = {"json": ".json", "api": ".json", "html": ".html"}  # text → 取 URL 原后缀


def utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def load_sources() -> list[dict]:
    data = yaml.safe_load(SOURCES_YAML.read_text(encoding="utf-8")) or {}
    sources = data.get("sources") or []
    ids = [s.get("id") for s in sources]
    if not sources or len(ids) != len(set(ids)) or any(i is None for i in ids):
        sys.exit(f"{SOURCES_YAML} 不合法：sources 为空、id 缺失或重复")
    return sources


def load_state(raw_root: Path) -> dict:
    p = raw_root / "state.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            return {}
    return {}


def save_state(raw_root: Path, state: dict) -> None:
    (raw_root / "state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _decompress(body: bytes, encoding: str) -> bytes:
    """少数 CDN 无视请求头强行 gzip 时的兜底；正常情况走 identity 原样返回。"""
    if encoding == "gzip":
        return zlib.decompress(body, 16 + zlib.MAX_WBITS)
    if encoding == "deflate":
        try:
            return zlib.decompress(body)
        except zlib.error:
            return zlib.decompress(body, -zlib.MAX_WBITS)
    return body


def _download(url: str) -> tuple[bytes | None, dict]:
    """带重试地下载，返回 (body, 部分 record 字段)。源间隔离由调用方兜底。"""
    partial = {"http_code": None, "final_url": None, "attempts": 0, "error_msg": None}
    for attempt in range(1, MAX_RETRIES + 2):
        partial["attempts"] = attempt
        try:
            req = request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"})
            with request.urlopen(req, timeout=TIMEOUT_S) as resp:
                partial["http_code"] = resp.status
                partial["final_url"] = resp.geturl()
                body = resp.read()
                body = _decompress(body, (resp.headers.get("Content-Encoding") or "").lower())
                partial["error_msg"] = None
                return body, partial
        except error.HTTPError as e:
            partial["http_code"] = e.code
            partial["error_msg"] = f"HTTP {e.code} {e.reason}"
            if e.code < 500 and e.code not in (408, 429):
                return None, partial  # 其余 4xx 重试无意义
        except (error.URLError, OSError, http.client.HTTPException, zlib.error) as e:
            partial["error_msg"] = f"{type(e).__name__}: {getattr(e, 'reason', None) or e}"
        if attempt <= MAX_RETRIES:
            time.sleep(BACKOFF_BASE_S * (2 ** (attempt - 1)))
    return None, partial


def fetch_one(src: dict, out_dir: Path, state: dict, date: str) -> dict:
    """抓单个来源、去重、gzip 落盘。所有异常都收进 record 返回，绝不向上抛。"""
    url = src["url"]
    src_type = src.get("type", "html")
    started = time.monotonic()
    record: dict = {
        "id": src["id"],
        "type": src_type,
        "url": url,
        "status": "error",
        "http_code": None,
        "bytes": 0,
        "gz_bytes": 0,
        "duration_ms": 0,
        "error_msg": None,
        "file": None,
        "final_url": None,
        "attempts": 0,
        "sha256": None,
        "changed": None,
    }

    body, partial = _download(url)
    record.update({k: partial[k] for k in ("http_code", "final_url", "attempts", "error_msg")})
    record["duration_ms"] = int((time.monotonic() - started) * 1000)
    if body is None:
        return record

    digest = hashlib.sha256(body).hexdigest()
    record["sha256"] = digest
    record["bytes"] = len(body)

    prev = state.get(src["id"]) or {}
    if prev.get("sha256") == digest:
        # 内容没变：不落新文件，只记 unchanged（体积控制的关键）
        record["status"] = "unchanged"
        record["changed"] = False
        record["same_as"] = prev.get("date")
        return record

    ext = EXT_BY_TYPE.get(src_type)
    if ext is None:  # type=text：保留 URL 原后缀
        ext = Path(parse.urlparse(url).path).suffix or ".txt"
    filename = f"{src['id']}{ext}.gz"
    gz_path = out_dir / filename
    with gzip.open(gz_path, "wb", compresslevel=9) as fh:
        fh.write(body)

    record["status"] = "ok"
    record["changed"] = True
    record["gz_bytes"] = gz_path.stat().st_size
    record["file"] = filename
    if src_type in ("json", "api"):
        # 只校验「是否合法 JSON」供下游参考，不做任何内容分析
        try:
            json.loads(body.decode("utf-8", errors="replace"))
            record["json_valid"] = True
        except ValueError:
            record["json_valid"] = False

    # 更新去重状态
    state[src["id"]] = {
        "sha256": digest,
        "date": date,
        "file": f"{date}/{filename}",
        "bytes": len(body),
        "gz_bytes": record["gz_bytes"],
    }
    return record


def main() -> int:
    ap = argparse.ArgumentParser(description="ai-money-radar 抓取管线（抓取+去重+gzip 快照+manifest，无分析）")
    ap.add_argument("--date", default=utc_today(), help="快照目录日期 YYYY-MM-DD（UTC），默认今天")
    ap.add_argument("--sources", default=None, help="逗号分隔的来源 id，只抓这几个（调试用）")
    ap.add_argument("--out-dir", default=None, help="输出根目录，默认 <仓库根>/raw（调试用）")
    args = ap.parse_args()

    try:
        datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        ap.error(f"--date 需要 YYYY-MM-DD，实际收到: {args.date!r}")

    all_sources = load_sources()
    if args.sources:
        wanted = [s.strip() for s in args.sources.split(",") if s.strip()]
        known = {s["id"] for s in all_sources}
        unknown = [w for w in wanted if w not in known]
        if unknown:
            sys.exit(f"未知来源 id: {unknown}；可用: {sorted(known)}")
        sources = [s for s in all_sources if s["id"] in set(wanted)]
    else:
        sources = all_sources
    if not sources:
        sys.exit("没有可抓的来源")

    raw_root = Path(args.out_dir).expanduser() if args.out_dir else REPO_ROOT / "raw"
    out_dir = raw_root / args.date
    out_dir.mkdir(parents=True, exist_ok=True)
    state = load_state(raw_root)

    run_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"ai-money-radar 抓取开始 run_utc={run_utc} date={args.date} "
          f"sources={len(sources)} out={out_dir}")

    records = []
    for i, src in enumerate(sources, 1):
        try:
            rec = fetch_one(src, out_dir, state, args.date)
        except Exception as e:  # 双保险：fetch_one 内部已兜底，这里防任何意外
            rec = {"id": src["id"], "type": src.get("type", "html"), "url": src["url"],
                   "status": "error", "error_msg": f"{type(e).__name__}: {e}",
                   "http_code": None, "bytes": 0, "gz_bytes": 0, "duration_ms": 0,
                   "file": None, "final_url": None, "attempts": 0, "sha256": None, "changed": None}
        records.append(rec)
        if rec["status"] == "ok":
            detail = (f"HTTP {rec['http_code']} {rec['bytes']}B→gz {rec['gz_bytes']}B "
                      f"{rec['duration_ms']}ms -> {rec['file']}")
        elif rec["status"] == "unchanged":
            detail = f"内容未变（同 {rec.get('same_as')}），跳过快照"
        else:
            detail = rec["error_msg"] or "unknown error"
        print(f"[{i:>2}/{len(sources)}] {rec['status'][:9]:<9} {rec['id']}: {detail}", flush=True)
        if i < len(sources):
            time.sleep(SLEEP_BETWEEN_SOURCES_S)

    save_state(raw_root, state)

    ok = sum(1 for r in records if r["status"] == "ok")
    unchanged = sum(1 for r in records if r["status"] == "unchanged")
    err = len(records) - ok - unchanged
    manifest = {
        "run_utc": run_utc,
        "date": args.date,
        "generator": "scraper/fetch_sources.py",
        "summary": {"total": len(records), "changed": ok, "unchanged": unchanged, "error": err},
        "sources": records,
    }
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")

    print(f"\n==== 汇总 {args.date}: 变化 {ok} · 未变 {unchanged} · 失败 {err} / 共 {len(records)} ====")
    for r in records:
        if r["status"] == "error":
            print(f"  失败: {r['id']} — {r['error_msg']}")
    print(f"manifest: {manifest_path}")
    # 只要不是全部失败就视为成功（unchanged 也算正常运行）
    return 0 if (ok + unchanged) > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
