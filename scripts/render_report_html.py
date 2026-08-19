#!/usr/bin/env python3
"""Render disk-clean audit data as a self-contained bilingual HTML report.

The renderer uses only the Python standard library.  English is the default view;
the page includes an in-page Chinese toggle and embeds the complete source reports,
receipt, and proof so the presentation layer cannot hide audit evidence.
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import quote


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def pair(en: str, zh: str, tag: str = "span", class_name: str = "") -> str:
    class_attr = f' class="{escape(class_name)}"' if class_name else ""
    return (
        f'<{tag}{class_attr}><span data-lang="en">{escape(en)}</span>'
        f'<span data-lang="zh">{escape(zh)}</span></{tag}>'
    )


def parse_meta(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"^- ([^:\n]+):\s*(.*)$", line)
        if match:
            values[match.group(1).strip()] = match.group(2).strip()
    return values


def split_table_row(line: str) -> list[str] | None:
    if not line.lstrip().startswith("|"):
        return None
    content = line.strip().strip("|")
    return [cell.strip() for cell in content.split("|")]


def is_separator(row: list[str]) -> bool:
    return bool(row) and all(
        re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in row
    )


def parse_tables(text: str) -> list[dict[str, list[list[str]] | list[str]]]:
    lines = text.splitlines()
    tables: list[dict[str, list[list[str]] | list[str]]] = []
    index = 0
    while index < len(lines) - 1:
        header = split_table_row(lines[index])
        separator = split_table_row(lines[index + 1])
        if header and separator and is_separator(separator):
            rows: list[list[str]] = []
            index += 2
            while index < len(lines):
                row = split_table_row(lines[index])
                if not row:
                    break
                rows.append(row)
                index += 1
            tables.append({"headers": header, "rows": rows})
        index += 1
    return tables


def table_with_header(
    tables: list[dict[str, list[list[str]] | list[str]]], needle: str
) -> dict[str, list[list[str]] | list[str]] | None:
    needle = needle.lower()
    for table in tables:
        headers = [str(value).lower() for value in table["headers"]]  # type: ignore[index]
        if needle in headers:
            return table
    return None


def table_value(table: dict[str, list[list[str]] | list[str]] | None, field: str) -> str:
    if not table:
        return ""
    for row in table["rows"]:  # type: ignore[index]
        if row and row[0].strip().lower() == field.lower():
            return row[1].strip() if len(row) > 1 else ""
    return ""


def section_lines(text: str, title_fragments: tuple[str, ...]) -> list[str]:
    lines = text.splitlines()
    start = None
    for index, line in enumerate(lines):
        if line.startswith("## ") and any(
            fragment.lower() in line.lower() for fragment in title_fragments
        ):
            start = index + 1
            break
    if start is None:
        return []
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith("## ") or lines[index].startswith("# "):
            end = index
            break
    return lines[start:end]


def bullet_items(lines: list[str]) -> list[str]:
    return [line[2:].strip() for line in lines if line.strip().startswith("- ")]


def integer(value: str) -> int | None:
    match = re.search(r"-?\d[\d,]*", value or "")
    if not match:
        return None
    try:
        return int(match.group(0).replace(",", ""))
    except ValueError:
        return None


def human_bytes(value: int | None) -> str:
    if value is None:
        return "—"
    units = ("B", "KB", "MB", "GB", "TB")
    amount = float(value)
    unit = units[0]
    for unit in units:
        if abs(amount) < 1024 or unit == units[-1]:
            break
        amount /= 1024
    if unit == "B":
        return f"{int(amount):,} B"
    return f"{amount:,.2f} {unit}"


def file_href(path: Path) -> str:
    normalized = str(path.resolve()).replace("\\", "/")
    if re.match(r"^[A-Za-z]:/", normalized):
        return "file:///" + quote(normalized, safe="/:@-._~")
    return "file://" + quote(normalized, safe="/:@-._~")


def find_manifest_hash(text: str) -> str:
    match = re.search(r"Manifest SHA-256:\s*([0-9a-f]{64})", text, flags=re.IGNORECASE)
    return match.group(1) if match else ""


TABLE_LABELS: dict[str, tuple[str, str]] = {
    "volume": ("Volume", "卷"),
    "root": ("Root", "根目录"),
    "category": ("Category", "类别"),
    "field": ("Field", "字段"),
    "check": ("Check", "检查项"),
    "absolute path": ("Absolute path", "绝对路径"),
    "total bytes": ("Total bytes", "总字节数"),
    "used bytes": ("Used bytes", "已用字节数"),
    "available bytes": ("Available bytes", "可用字节数"),
    "logical bytes": ("Logical bytes", "逻辑字节数"),
    "files": ("Files", "文件数"),
    "directories": ("Directories", "目录数"),
    "reparse points": ("Reparse points", "重解析点"),
    "metadata sidecars": ("Metadata sidecars", "Metadata sidecar 数"),
    "estimated bytes": ("Estimated bytes", "预计字节数"),
    "decision": ("Decision", "决定"),
    "status time utc": ("Status time UTC", "状态时间 UTC"),
    "delete_after utc": ("Delete after UTC", "允许删除时间 UTC"),
    "bytes": ("Bytes", "字节数"),
    "owner/metadata": ("Owner / metadata", "所有者 / metadata"),
    "lock": ("Lock", "锁"),
    "evidence": ("Evidence", "证据"),
    "result": ("Result", "结果"),
}


def localized_header(value: str) -> str:
    return pair(*TABLE_LABELS.get(value.lower(), (value, value)))


def render_table(
    table: dict[str, list[list[str]] | list[str]] | None,
    table_id: str = "",
    searchable: bool = False,
) -> str:
    if not table:
        return f'<div class="empty">{pair("No table was recorded.", "报告中没有记录表格。")}</div>'
    headers = [str(value) for value in table["headers"]]  # type: ignore[index]
    rows = table["rows"]  # type: ignore[index]
    table_id_attr = f' id="{escape(table_id)}"' if table_id else ""
    search_attr = ' data-searchable="true"' if searchable else ""
    head = "".join(f"<th scope=\"col\">{localized_header(value)}</th>" for value in headers)
    body_rows: list[str] = []
    for row in rows:  # type: ignore[union-attr]
        cells = list(row) + [""] * max(0, len(headers) - len(row))
        category = cells[1] if len(cells) > 1 else ""
        body_rows.append(
            f'<tr data-category="{escape(category)}">'
            + "".join(f"<td>{escape(value)}</td>" for value in cells[: len(headers)])
            + "</tr>"
        )
    return (
        f'<div class="table-scroll"><table class="data-table"{table_id_attr}{search_attr}>'
        f"<thead><tr>{head}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>"
    )


def render_bullets(items: list[str]) -> str:
    if not items:
        return f'<div class="empty">{pair("No additional items were recorded.", "没有记录其他项目。")}</div>'
    return "<ul class=\"clean-list\">" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def json_text(path: Path | None) -> str:
    if not path or not path.exists():
        return ""
    try:
        return json.dumps(json.loads(read_text(path)), ensure_ascii=False, indent=2)
    except (OSError, json.JSONDecodeError):
        return read_text(path)


CSS = r"""
:root { color-scheme: light; --paper:#f5f5f7; --card:rgba(255,255,255,.78); --ink:#1d1d1f; --muted:#6e6e73; --line:rgba(29,29,31,.10); --blue:#0071e3; --green:#1f8f55; --amber:#a85c00; --shadow:0 20px 50px rgba(20,28,45,.08),0 2px 8px rgba(20,28,45,.04); }
* { box-sizing:border-box; }
html { scroll-behavior:smooth; }
body { margin:0; color:var(--ink); background:radial-gradient(circle at 8% 0%,rgba(0,113,227,.12),transparent 26rem),radial-gradient(circle at 92% 18%,rgba(125,170,255,.12),transparent 30rem),var(--paper); font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI",sans-serif; line-height:1.5; -webkit-font-smoothing:antialiased; }
[data-lang] { display:none !important; }
body[data-language="en"] [data-lang="en"], body[data-language="zh"] [data-lang="zh"] { display:inline !important; }
a { color:var(--blue); text-decoration:none; } a:hover { text-decoration:underline; }
.shell { max-width:1440px; margin:0 auto; padding:0 28px 80px; }
.hero { margin:0 -28px; padding:26px 28px 72px; color:#fff; background:radial-gradient(circle at 86% 10%,rgba(102,194,255,.58),transparent 18rem),linear-gradient(135deg,#111827 0%,#253b59 58%,#0878d1 100%); border-radius:0 0 36px 36px; box-shadow:0 28px 80px rgba(26,56,94,.22); }
.nav { display:flex; justify-content:space-between; gap:24px; align-items:center; max-width:1440px; margin:0 auto 66px; }
.brand { display:flex; align-items:center; gap:10px; font-weight:700; letter-spacing:-.02em; } .brand-mark { width:25px; height:25px; border-radius:8px; display:grid; place-items:center; background:rgba(255,255,255,.18); border:1px solid rgba(255,255,255,.22); font-size:14px; }
.nav-right { display:flex; align-items:center; gap:18px; } .nav-links { display:flex; gap:18px; font-size:13px; color:rgba(255,255,255,.72); } .nav-links a { color:inherit; }
.language-control { display:flex; gap:4px; padding:3px; border:1px solid rgba(255,255,255,.22); border-radius:999px; background:rgba(255,255,255,.10); } .language-control button { cursor:pointer; border:0; border-radius:999px; padding:5px 9px; color:rgba(255,255,255,.72); background:transparent; font:600 11px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; } .language-control button[aria-pressed="true"] { color:#173454; background:#fff; }
.eyebrow { margin:0 0 14px; font-size:11px; font-weight:700; letter-spacing:.16em; text-transform:uppercase; color:rgba(255,255,255,.68); }
h1,h2,h3 { letter-spacing:-.045em; line-height:1.05; margin:0; } h1 { max-width:820px; font-size:clamp(42px,6vw,82px); font-weight:700; } h2 { font-size:clamp(25px,3vw,38px); } h3 { font-size:20px; }
.hero-copy { max-width:760px; margin:18px 0 0; color:rgba(255,255,255,.76); font-size:18px; }
.hero-meta { display:flex; flex-wrap:wrap; gap:10px; margin-top:28px; } .pill { display:inline-flex; align-items:center; gap:7px; padding:8px 12px; border-radius:999px; font-size:12px; font-weight:650; background:rgba(255,255,255,.13); border:1px solid rgba(255,255,255,.18); } .pill-dot { width:7px; height:7px; border-radius:99px; background:#72e3a6; box-shadow:0 0 0 4px rgba(114,227,166,.13); }
.main { position:relative; margin-top:-40px; } .section { margin-top:28px; } .section-heading { display:flex; align-items:end; justify-content:space-between; gap:24px; margin:56px 0 18px; } .section-heading p { max-width:560px; margin:0; color:var(--muted); font-size:14px; }
.grid { display:grid; gap:16px; } .summary-grid { grid-template-columns:repeat(5,minmax(0,1fr)); } .two-grid { grid-template-columns:repeat(2,minmax(0,1fr)); }
.card { background:var(--card); border:1px solid rgba(255,255,255,.84); border-radius:24px; padding:22px; box-shadow:var(--shadow); backdrop-filter:blur(18px); } .metric-label { color:var(--muted); font-size:12px; font-weight:600; } .metric-value { margin-top:12px; font-size:clamp(23px,3vw,36px); font-weight:700; letter-spacing:-.05em; } .metric-detail { margin-top:7px; color:var(--muted); font-size:12px; } .status-card { background:linear-gradient(145deg,#eaf7ef,#fff); } .status-card .metric-value { color:var(--green); font-size:25px; letter-spacing:-.035em; }
.warning { display:flex; align-items:flex-start; gap:14px; margin-top:18px; padding:16px 18px; border:1px solid #f0d6a1; border-radius:18px; background:#fff4df; color:#684111; } .warning strong { display:block; color:#7f4700; } .warning p { margin:3px 0 0; font-size:13px; }
.capacity { margin-top:18px; } .capacity-line { display:flex; justify-content:space-between; gap:18px; color:var(--muted); font-size:12px; } .capacity-track { height:11px; margin-top:9px; overflow:hidden; border-radius:99px; background:#e5e5e7; } .capacity-fill { height:100%; border-radius:inherit; background:linear-gradient(90deg,#34c759,#ff9f0a 72%,#ff453a); }
.table-scroll { overflow:auto; border:1px solid var(--line); border-radius:16px; background:rgba(255,255,255,.55); } .data-table { width:100%; min-width:680px; border-collapse:collapse; font-size:12px; } .data-table th { position:sticky; top:0; z-index:1; padding:12px 14px; text-align:left; white-space:nowrap; color:var(--muted); background:rgba(245,245,247,.94); border-bottom:1px solid var(--line); font-size:11px; letter-spacing:.02em; } .data-table td { max-width:580px; padding:12px 14px; vertical-align:top; border-bottom:1px solid rgba(29,29,31,.065); overflow-wrap:anywhere; } .data-table tr:last-child td { border-bottom:0; } .data-table tr:hover td { background:rgba(0,113,227,.045); } .data-table td:nth-child(1) { font-weight:620; }
.clean-list { margin:0; padding-left:20px; color:#343438; } .clean-list li { margin:9px 0; } .toolbar { display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin-bottom:13px; } .toolbar input,.toolbar select,.toolbar button { height:38px; border:1px solid rgba(29,29,31,.13); border-radius:12px; background:rgba(255,255,255,.72); color:var(--ink); font:inherit; font-size:13px; } .toolbar input { min-width:min(460px,100%); padding:0 13px; flex:1; } .toolbar select,.toolbar button { padding:0 13px; } .toolbar button { cursor:pointer; background:#fff; } .toolbar button:hover { border-color:var(--blue); color:var(--blue); } .result-count { margin-left:auto; color:var(--muted); font-size:12px; }
.evidence-list { display:grid; gap:10px; margin:0; padding:0; list-style:none; } .evidence-list li { display:flex; justify-content:space-between; gap:20px; padding:12px 0; border-bottom:1px solid var(--line); font-size:13px; } .evidence-list li:last-child { border-bottom:0; } .evidence-list span { color:var(--muted); } .evidence-list small { color:var(--muted); }
details { margin-top:12px; border:1px solid var(--line); border-radius:18px; background:rgba(255,255,255,.55); } summary { cursor:pointer; padding:16px 18px; color:var(--ink); font-weight:650; } summary::marker { color:var(--blue); } .raw-box { margin:0; padding:0 18px 18px; } .raw-box pre { max-height:600px; overflow:auto; margin:0; padding:18px; border-radius:14px; color:#33343a; background:#f0f0f2; font:12px/1.6 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; white-space:pre-wrap; overflow-wrap:anywhere; }
.empty { padding:20px; color:var(--muted); font-size:13px; } .footer { margin-top:70px; padding-top:24px; border-top:1px solid var(--line); color:var(--muted); font-size:12px; }
@media (max-width:1050px) { .summary-grid { grid-template-columns:repeat(3,minmax(0,1fr)); } } @media (max-width:760px) { .shell { padding:0 16px 56px; } .hero { margin:0 -16px; padding:22px 16px 60px; border-radius:0 0 28px 28px; } .nav { margin-bottom:54px; } .nav-links { display:none; } .nav-right { gap:8px; } .summary-grid,.two-grid { grid-template-columns:1fr; } .section-heading { display:block; } .section-heading p { margin-top:8px; } .card { border-radius:18px; padding:18px; } }
@media print { body { background:#fff; } .hero { color:#111; background:#fff; box-shadow:none; border-bottom:2px solid #111; } .nav-links,.language-control,.toolbar,.warning { display:none; } .main { margin-top:24px; } .card,details { box-shadow:none; break-inside:avoid; } .raw-box pre { max-height:none; } }
"""


JS = r"""
(function () {
  const body = document.body;
  const buttons = Array.from(document.querySelectorAll('[data-set-language]'));
  function setLanguage(language) {
    body.dataset.language = language;
    document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
    buttons.forEach(function (button) { button.setAttribute('aria-pressed', button.dataset.setLanguage === language ? 'true' : 'false'); });
    const search = document.getElementById('manifest-search');
    if (search) search.placeholder = language === 'zh' ? '搜索路径、类别或证据…' : 'Search path, category, or evidence…';
    filterManifest();
  }
  buttons.forEach(function (button) { button.addEventListener('click', function () { setLanguage(button.dataset.setLanguage); }); });
  const table = document.getElementById('manifest-table');
  const search = document.getElementById('manifest-search');
  const select = document.getElementById('manifest-category');
  const counter = document.getElementById('manifest-count');
  const rows = table ? Array.from(table.querySelectorAll('tbody tr')) : [];
  function filterManifest() {
    const query = search ? (search.value || '').trim().toLowerCase() : '';
    const category = select ? (select.value || '').toLowerCase() : '';
    let visible = 0;
    rows.forEach(function (row) {
      const text = row.textContent.toLowerCase();
      const rowCategory = (row.dataset.category || '').toLowerCase();
      const show = (!query || text.includes(query)) && (!category || rowCategory === category);
      row.hidden = !show;
      if (show) visible += 1;
    });
    if (counter) counter.textContent = visible.toLocaleString() + ' / ' + rows.length.toLocaleString() + (body.dataset.language === 'zh' ? ' 行' : ' rows');
  }
  if (search) search.addEventListener('input', filterManifest);
  if (select) select.addEventListener('change', filterManifest);
  const clear = document.getElementById('clear-manifest');
  if (clear) clear.addEventListener('click', function () { if (search) search.value = ''; if (select) select.value = ''; filterManifest(); });
  setLanguage('en');
})();
"""


def build_html(
    analysis_path: Path,
    cleanup_path: Path | None,
    receipt_path: Path | None,
    proof_path: Path | None,
    platform: str | None,
    target_label: str | None,
) -> str:
    analysis_text = read_text(analysis_path)
    cleanup_text = read_text(cleanup_path) if cleanup_path and cleanup_path.exists() else ""
    analysis_meta = parse_meta(analysis_text)
    cleanup_meta = parse_meta(cleanup_text)
    meta = {**analysis_meta, **cleanup_meta}
    analysis_tables = parse_tables(analysis_text)
    cleanup_tables = parse_tables(cleanup_text)
    volume_table = table_with_header(analysis_tables, "volume")
    roots_table = table_with_header(analysis_tables, "root")
    category_table = table_with_header(analysis_tables, "category")
    manifest_table = table_with_header(analysis_tables, "absolute path")
    result_table = table_with_header(cleanup_tables, "field")
    action_table = table_with_header(cleanup_tables, "check")

    total = used_bytes = available_before = available_after = None
    if volume_table:
        rows = volume_table["rows"]  # type: ignore[index]
        if rows:
            first = rows[0]
            total = integer(first[1]) if len(first) > 1 else None
            used_bytes = integer(first[2]) if len(first) > 2 else None
            available_before = integer(first[3]) if len(first) > 3 else None
    for row in action_table["rows"] if action_table else []:  # type: ignore[index]
        if row and "free bytes after" in row[0].lower() or row and "available bytes after" in row[0].lower():
            available_after = integer(row[1]) if len(row) > 1 else None
            break
    candidates = integer(table_value(result_table, "candidates"))
    quarantined = integer(table_value(result_table, "quarantined"))
    deleted = integer(table_value(result_table, "deleted"))
    skipped = integer(table_value(result_table, "skipped archived sessions"))
    failed = integer(table_value(result_table, "failed"))
    estimated = integer(table_value(result_table, "estimated_bytes"))
    quarantined_bytes = integer(table_value(result_table, "quarantined_bytes"))
    reclaimed = integer(table_value(result_table, "reclaimed_bytes"))
    if candidates is None:
        match = re.search(r"(?:total apply candidates|candidates):\s*(\d[\d,]*)", analysis_text, flags=re.IGNORECASE)
        candidates = integer(match.group(1)) if match else None
    if estimated is None:
        match = re.search(r"(?:estimated quarantine bytes|estimated_bytes):\s*(\d[\d,]*)", analysis_text, flags=re.IGNORECASE)
        estimated = integer(match.group(1)) if match else None

    run_id = meta.get("run_id", analysis_path.stem)
    status = meta.get("cleanup_status", meta.get("status", "ANALYSIS READY"))
    proof_state = meta.get("proof_state", "PENDING")
    host = meta.get("host/identity", meta.get("host", "configured host"))
    policy = meta.get("policy_version", "configured policy")
    target = target_label or meta.get("target_label") or meta.get("target_key", "Disk target")
    platform_name = platform or meta.get("platform", "Configured platform")
    observed = meta.get("observed_at", "")
    manifest_hash = find_manifest_hash(analysis_text)
    used_pct = (used_bytes / total * 100) if used_bytes and total else 0
    protected = bullet_items(section_lines(analysis_text, ("Protected and skipped", "Skipped and protected", "保护与跳过")))
    protected.extend(item for item in bullet_items(section_lines(cleanup_text, ("Skipped and protected", "保护与跳过"))) if item not in protected)
    rollback_risk = bullet_items(section_lines(cleanup_text, ("Rollback and residual risk", "回滚与残余风险")))
    receipt_json = json_text(receipt_path)
    proof_json = json_text(proof_path)

    category_options: list[str] = []
    if manifest_table:
        for row in manifest_table["rows"]:  # type: ignore[index]
            if len(row) > 1 and row[1] not in category_options:
                category_options.append(row[1])
    category_select = '<option value="">All categories / 全部类别</option>' + "".join(
        f'<option value="{escape(category)}">{escape(category)}</option>' for category in category_options
    )

    def metric(label_en: str, label_zh: str, value: object, detail_en: str, detail_zh: str, status_card: bool = False) -> str:
        class_name = "card status-card" if status_card else "card"
        return (
            f'<article class="{class_name}"><div class="metric-label">{pair(label_en, label_zh)}</div>'
            f'<div class="metric-value">{escape(value)}</div><div class="metric-detail">{pair(detail_en, detail_zh)}</div></article>'
        )

    def heading(number: str, anchor: str, en: str, zh: str, desc_en: str, desc_zh: str) -> str:
        return (
            f'<div class="section-heading" id="{escape(anchor)}"><div><p class="eyebrow" style="color:var(--blue)">{escape(number)}</p>'
            f'<h2>{pair(en, zh)}</h2></div><p>{pair(desc_en, desc_zh)}</p></div>'
        )

    quarantine_en, quarantine_zh = {
        "windows": ("Recycle Bin", "回收站"),
        "linux": ("Trash / quarantine", "Trash / 隔离区"),
        "macos": ("Trash / quarantine", "Trash / 隔离区"),
    }.get(platform_name.lower().replace(" ", ""), ("quarantine", "隔离区"))
    warning_block = ""
    if reclaimed == 0 and (quarantined_bytes or quarantined):
        warning_block = (
            '<div class="warning"><div aria-hidden="true">◌</div><div>'
            f'<strong>{pair("Quarantine still occupies logical space", "隔离区仍占用逻辑空间")}</strong>'
            f'<p>{pair(f"{human_bytes(quarantined_bytes or estimated)} remains in {quarantine_en}; permanent reclaim is 0 until separately approved.", f"{human_bytes(quarantined_bytes or estimated)} 仍在{quarantine_zh}中；单独授权清空前，永久释放为 0。")}</p>'
            '</div></div>'
        )

    evidence_items: list[str] = []
    for label_en, label_zh, path in (
        ("Analysis report", "分析报告", analysis_path),
        ("Cleanup report", "清理报告", cleanup_path),
        ("Cleanup receipt", "清理回执", receipt_path),
        ("DecisionProof", "DecisionProof", proof_path),
    ):
        if path:
            state_en, state_zh = ("available", "可用") if path.exists() else ("missing", "缺失")
            evidence_items.append(
                f'<li><span>{pair(label_en, label_zh)}</span><a href="{file_href(path)}">{escape(path.name)}</a><small>{pair(state_en, state_zh)}</small></li>'
            )

    title = f"Disk cleanup report · {run_id}"
    parts: list[str] = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="description" content="Bilingual disk cleanup audit report">',
        f"<title>{escape(title)}</title><style>{CSS}</style></head><body data-language=\"en\">",
        '<header class="hero"><nav class="nav" aria-label="Report navigation"><div class="brand"><span class="brand-mark">⌁</span><span>Disk Clean</span></div><div class="nav-right"><div class="nav-links"><a href="#overview">Overview</a><a href="#manifest">Manifest</a><a href="#evidence">Evidence</a></div><div class="language-control" aria-label="Language"><button type="button" data-set-language="en" aria-pressed="true">EN</button><button type="button" data-set-language="zh" aria-pressed="false">中文</button></div></div></nav>',
        '<div class="shell"><p class="eyebrow">DISK / RETENTION REPORT</p>',
        f"<h1>{pair('Disk cleanup report', '磁盘清理报告')}</h1>",
        f"<p class=\"hero-copy\">{pair('A readable, searchable, printable local audit surface. Actions, protection boundaries, evidence, and source records stay together.', '一份可读、可检索、可打印的本地审计页面。清理动作、保护边界、证据链和原始记录集中保留。')}</p>",
        f'<div class="hero-meta"><span class="pill"><span class="pill-dot"></span>{escape(status)}</span><span class="pill">Proof · {escape(proof_state)}</span><span class="pill">{escape(platform_name)}</span><span class="pill">{escape(target)}</span><span class="pill">{escape(run_id)}</span></div></div></header>',
        '<div class="shell"><main class="main"><section id="overview" class="section"><div class="grid summary-grid">',
        metric("Cleanup status", "清理状态", status, f"Proof: {proof_state}", f"Proof：{proof_state}", True),
        metric("Candidates", "候选对象", candidates if candidates is not None else "—", "exact manifest paths", "精确 manifest 路径"),
        metric("Quarantined", "已隔离", human_bytes(quarantined_bytes), f"{quarantined or 0:,} objects · {quarantine_en}", f"{quarantined or 0:,} 个对象 · {quarantine_zh}"),
        metric("Reclaimed", "永久释放", human_bytes(reclaimed), "direct capacity readback", "同卷容量直接读回"),
        metric("Available after", "清理后可用", human_bytes(available_after), f"{platform_name} · {target}", f"{platform_name} · {target}"),
        '</div>', warning_block,
        f'<article class="card capacity"><div class="capacity-line"><span>{pair("Disk capacity", "磁盘容量")}</span><span>{escape(human_bytes(used_bytes))} used / {escape(human_bytes(total))} total · {used_pct:.1f}%</span></div><div class="capacity-track" aria-label="Disk used capacity"><div class="capacity-fill" style="width:{min(100, max(0, used_pct)):.2f}%"></div></div><div class="capacity-line"><span>{pair(f"Before: {human_bytes(available_before)} available", f"清理前：可用 {human_bytes(available_before)}")}</span><span>{pair(f"After: {human_bytes(available_after)} available", f"清理后：可用 {human_bytes(available_after)}")}</span></div></article></section>',
        '<section class="section">', heading("01 / CLASSIFY", "classification", "Classification", "清理分类", "Classification precedes action; every allowlisted object is bound to an exact path and evidence.", "分类先于动作；所有进入白名单的对象都绑定到精确路径和证据。"), f'<div class="card">{render_table(category_table)}</div></section>',
        '<section class="section">', heading("02 / INVENTORY", "inventory", "Disk inventory", "磁盘盘点", "Read-only capacity, target-root, file, directory, and reparse-point evidence.", "只读容量、目标根、文件、目录和 reparse point 证据。"), f'<div class="grid two-grid"><article class="card">{render_table(volume_table)}</article><article class="card">{render_table(roots_table)}</article></div></section>',
        '<section class="section">', heading("03 / VERIFY", "action", "Cleanup result & direct readback", "清理结果与直接读回", "The action result sits beside the same-target action-after evidence.", "把清理结果和同一目标的 action-after 证据放在一起。"), f'<div class="grid two-grid"><article class="card"><h3>{pair("Cleanup result", "清理结果")}</h3>{render_table(result_table)}</article><article class="card"><h3>{pair("Action-after", "行动后读回")}</h3>{render_table(action_table)}</article></div><div class="card" style="margin-top:16px"><h3>{pair("Rollback & residual risk", "回滚与残余风险")}</h3>{render_bullets(rollback_risk)}</div></section>',
        '<section class="section">', heading("04 / MANIFEST", "manifest", "Exact candidate manifest", "精确候选清单", "Every row is an absolute path. Search and filter change only the view, never the evidence.", "每一行都是绝对路径。搜索和筛选只改变视图，不改变证据。"), f'<div class="card"><div class="toolbar"><input id="manifest-search" type="search" placeholder="Search path, category, or evidence…" aria-label="Search manifest"><select id="manifest-category" aria-label="Filter manifest category">{category_select}</select><button id="clear-manifest" type="button">Clear filter / 清除筛选</button><span id="manifest-count" class="result-count"></span></div>{render_table(manifest_table, table_id="manifest-table", searchable=True)}</div></section>',
        '<section class="section">', heading("05 / PROTECT", "protected", "Protected & skipped", "保护与跳过", "Objects without recovery evidence, with active references, or with unclear identity stay untouched.", "缺少恢复证据、仍有活动引用或身份不清的对象保持不动。"), f'<article class="card">{render_bullets(protected)}</article></section>',
        '<section class="section">', heading("06 / PROVE", "evidence", "Evidence chain", "证据链", "Reports, receipt, and DecisionProof cross-reference the same run.", "报告、回执和 DecisionProof 互相引用同一次运行。"), f'<div class="grid two-grid"><article class="card"><ul class="evidence-list">{"".join(evidence_items)}</ul></article><article class="card"><ul class="evidence-list"><li><span>{pair("Policy", "策略")}</span><code>{escape(policy)}</code></li><li><span>{pair("Observed", "观察时间")}</span><code>{escape(observed)}</code></li><li><span>{pair("Manifest SHA-256", "Manifest SHA-256")}</span><code>{escape(manifest_hash or "not recorded")}</code></li><li><span>{pair("Target", "目标")}</span><code>{escape(target)}</code></li></ul></article></div></section>',
        '<section class="section">', heading("07 / SOURCE", "source", "Original audit source", "原始审计全文", "The complete source text remains embedded so the presentation layer cannot truncate fields or paths.", "完整原始文本嵌入网页，呈现层不会截断字段或路径。"), f'<details open><summary>{pair("Analysis report · complete source", "分析报告 · 完整原文")}</summary><div class="raw-box"><pre>{escape(analysis_text)}</pre></div></details>',
    ]
    if cleanup_text:
        parts.append(f'<details open><summary>{pair("Cleanup report · complete source", "清理报告 · 完整原文")}</summary><div class="raw-box"><pre>{escape(cleanup_text)}</pre></div></details>')
    if receipt_json:
        parts.append(f'<details><summary>{pair("Cleanup receipt JSON", "清理回执 JSON")}</summary><div class="raw-box"><pre>{escape(receipt_json)}</pre></div></details>')
    if proof_json:
        parts.append(f'<details><summary>{pair("DecisionProof JSON", "DecisionProof JSON")}</summary><div class="raw-box"><pre>{escape(proof_json)}</pre></div></details>')
    parts.extend([
        f'<footer class="footer">{pair("Self-contained report · no external resources · generated by disk-clean HTML renderer", "自包含报告 · 无外部资源 · 由 disk-clean HTML renderer 生成")} · run_id: {escape(run_id)}</footer>',
        f'</main></div><script>{JS}</script></body></html>',
    ])
    return "".join(parts)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--analysis", required=True, type=Path)
    parser.add_argument("--cleanup", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--proof", type=Path)
    parser.add_argument("--platform", type=str)
    parser.add_argument("--target-label", type=str)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"Refusing to overwrite existing report: {args.output}")
    if not args.analysis.exists():
        raise SystemExit(f"Analysis report not found: {args.analysis}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        build_html(args.analysis, args.cleanup, args.receipt, args.proof, args.platform, args.target_label),
        encoding="utf-8",
        newline="\n",
    )
    print(f"wrote {args.output} ({args.output.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
