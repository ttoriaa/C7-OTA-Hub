from __future__ import annotations

import argparse
import csv
import datetime as dt
import glob
import html
import json
import re
from pathlib import Path
from typing import Any

try:
    from fill_dongchedi_motor_fields import ensure_motor_columns
except Exception:
    ensure_motor_columns = None

ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "reports" / "dongchedi_motor_daily"
PRICE_MAP_DEFAULT = ROOT / "dongchedi_price_map.csv"

MOTOR_OUTPUT_COLUMNS = [
    "数据日期",
    "车系ID",
    "车型",
    "品牌",
    "动力形式",
    "价格(万元)",
    "纯电续航里程(km)工信部",
    "纯电续航里程(km)CLTC",
    "电动机",
    "电机类型",
    "电动机总功率(kW)",
    "电动机总马力(Ps)",
    "电动机总扭矩(Nm)",
    "前电动机最大扭矩(Nm)",
    "前电动机最大功率(kW)",
    "后电动机最大扭矩(Nm)",
    "后电动机最大功率(kW)",
    "驱动电机数",
    "电机布局",
    "缺失状态",
    "数据状态",
]

MOTOR_FIELDS = [
    "电动机",
    "电机类型",
    "电动机总功率(kW)",
    "电动机总马力(Ps)",
    "电动机总扭矩(Nm)",
    "前电动机最大扭矩(Nm)",
    "前电动机最大功率(kW)",
    "后电动机最大扭矩(Nm)",
    "后电动机最大功率(kW)",
    "驱动电机数",
    "电机布局",
]

MOTOR_SOURCE_MAP = {
    "电动机": ["电动机"],
    "电机类型": ["电机类型"],
    "电动机总功率(kW)": ["电动机总功率", "电动机总功率(kW)"],
    "电动机总马力(Ps)": ["电动机总马力", "电动机总马力(Ps)"],
    "电动机总扭矩(Nm)": ["电动机总扭矩", "电动机总扭矩(Nm)"],
    "前电动机最大扭矩(Nm)": ["前电动机最大扭矩", "前电动机最大扭矩(Nm)"],
    "前电动机最大功率(kW)": ["前电动机最大功率", "前电动机最大功率(kW)", "前电动机最大攻略"],
    "后电动机最大扭矩(Nm)": ["后电动机最大扭矩", "后电动机最大扭矩(Nm)"],
    "后电动机最大功率(kW)": ["后电动机最大功率", "后电动机最大功率(kW)"],
    "驱动电机数": ["驱动电机数"],
    "电机布局": ["电机布局"],
}


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _extract_first_number(text: str) -> float | None:
    t = _clean(text)
    if not t:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)", t)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _is_missing(v: str) -> bool:
    t = _clean(v)
    return not t or t == "未明确显示"


def _model_key(row: dict[str, str]) -> str:
    return f"{_clean(row.get('车系ID'))}||{_clean(row.get('车型'))}"


def _brand_name(model_name: str) -> str:
    name = _clean(model_name)
    if not name:
        return "未明确显示"

    eng = re.match(r"[A-Za-z][A-Za-z0-9\-#]*", name)
    if eng:
        return eng.group(0)

    for i in range(2, min(8, len(name) // 2 + 1)):
        if name[:i] == name[i : 2 * i]:
            return name[:i]

    token = re.split(r"[\sA-Za-z0-9#\-\+\(\)]", name, maxsplit=1)[0].strip()
    return token or name[:2]


def _load_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return [dict((k, _clean(v)) for k, v in row.items()) for row in csv.DictReader(f)]


def _find_latest_source(source_override: str | None) -> Path:
    if source_override:
        p = Path(source_override)
        if not p.is_absolute():
            p = ROOT / p
        if not p.exists():
            raise FileNotFoundError(f"Source CSV not found: {p}")
        return p

    candidates = sorted(glob.glob(str(ROOT / "dongchedi_full_configs_*.csv")))
    if not candidates:
        raise FileNotFoundError("No source CSV found. Expected dongchedi_full_configs_YYYY-MM-DD.csv in workspace root.")
    return Path(candidates[-1])


def _parse_price_floor_wan(text: str) -> float | None:
    t = _clean(text)
    if not t:
        return None
    nums = re.findall(r"\d+(?:\.\d+)?", t)
    if not nums:
        return None
    try:
        return float(nums[0])
    except ValueError:
        return None


def _load_price_map(price_map_path: Path) -> tuple[dict[tuple[str, str], float], dict[str, float]]:
    if not price_map_path.exists():
        return {}, {}

    rows = _load_csv_rows(price_map_path)
    pair_map: dict[tuple[str, str], float] = {}
    series_map: dict[str, float] = {}

    for r in rows:
        sid = _clean(r.get("车系ID"))
        model = _clean(r.get("车型"))
        price = _parse_price_floor_wan(_clean(r.get("价格(万元)")))
        if price is None:
            continue
        if sid and model:
            pair_map[(sid, model)] = price
        if sid:
            series_map[sid] = price

    return pair_map, series_map


def _resolve_price(
    row: dict[str, str],
    pair_map: dict[tuple[str, str], float],
    series_map: dict[str, float],
    source_price_cols: list[str],
) -> float | None:
    sid = _clean(row.get("车系ID"))
    model = _clean(row.get("车型"))

    if sid and model and (sid, model) in pair_map:
        return pair_map[(sid, model)]
    if sid and sid in series_map:
        return series_map[sid]

    for c in source_price_cols:
        val = _parse_price_floor_wan(_clean(row.get(c)))
        if val is not None:
            return val

    return None


def _resolve_range_km(row: dict[str, str]) -> float | None:
    cltc = _extract_first_number(_clean(row.get("纯电续航里程(km)CLTC")))
    if cltc is not None:
        return cltc
    return _extract_first_number(_clean(row.get("纯电续航里程(km)工信部")))


def _get_motor_field(row: dict[str, str], output_key: str) -> str:
    aliases = MOTOR_SOURCE_MAP.get(output_key, [output_key])
    for key in aliases:
        val = _clean(row.get(key))
        if val:
            return val
    return "未明确显示"


def _missing_status(out: dict[str, str]) -> str:
    missing = [f for f in MOTOR_FIELDS if _is_missing(out.get(f, ""))]
    if not missing:
        return "完整"
    return "缺失:" + "、".join(missing)


def _to_output_row(row: dict[str, str], run_date: str, price_wan: float, data_status: str) -> dict[str, str]:
    model = _clean(row.get("车型"))
    out = {
        "数据日期": run_date,
        "车系ID": _clean(row.get("车系ID")),
        "车型": model,
        "品牌": _brand_name(model),
        "动力形式": _clean(row.get("动力形式")) or "纯电动",
        "价格(万元)": f"{price_wan:.2f}",
        "纯电续航里程(km)工信部": _clean(row.get("纯电续航里程(km)工信部")) or "未明确显示",
        "纯电续航里程(km)CLTC": _clean(row.get("纯电续航里程(km)CLTC")) or "未明确显示",
        "电动机": _get_motor_field(row, "电动机"),
        "电机类型": _get_motor_field(row, "电机类型"),
        "电动机总功率(kW)": _get_motor_field(row, "电动机总功率(kW)"),
        "电动机总马力(Ps)": _get_motor_field(row, "电动机总马力(Ps)"),
        "电动机总扭矩(Nm)": _get_motor_field(row, "电动机总扭矩(Nm)"),
        "前电动机最大扭矩(Nm)": _get_motor_field(row, "前电动机最大扭矩(Nm)"),
        "前电动机最大功率(kW)": _get_motor_field(row, "前电动机最大功率(kW)"),
        "后电动机最大扭矩(Nm)": _get_motor_field(row, "后电动机最大扭矩(Nm)"),
        "后电动机最大功率(kW)": _get_motor_field(row, "后电动机最大功率(kW)"),
        "驱动电机数": _get_motor_field(row, "驱动电机数"),
        "电机布局": _get_motor_field(row, "电机布局"),
        "缺失状态": "",
        "数据状态": data_status,
    }
    out["缺失状态"] = _missing_status(out)
    return out


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=MOTOR_OUTPUT_COLUMNS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def _find_latest_previous_report(run_date: str) -> Path | None:
    if not REPORT_ROOT.exists():
        return None

    previous_dirs = [p for p in REPORT_ROOT.iterdir() if p.is_dir() and p.name < run_date]
    if not previous_dirs:
        return None

    latest_dir = sorted(previous_dirs)[-1]
    candidate = latest_dir / "filtered.json"
    if not candidate.exists():
        return None
    return candidate


def _load_previous_rows(run_date: str) -> list[dict[str, str]]:
    prev = _find_latest_previous_report(run_date)
    if not prev:
        return []
    return json.loads(prev.read_text(encoding="utf-8"))


def _rows_to_markdown(rows: list[dict[str, str]]) -> str:
    lines = ["| " + " | ".join(MOTOR_OUTPUT_COLUMNS[1:]) + " |", "|" + "|".join(["---"] * (len(MOTOR_OUTPUT_COLUMNS) - 1)) + "|"]
    for r in rows:
        vals = [str(r.get(h, "")).replace("\n", " ").replace("|", "/") for h in MOTOR_OUTPUT_COLUMNS[1:]]
        lines.append("| " + " | ".join(vals) + " |")
    return "\n".join(lines)


def _rows_to_html_table(rows: list[dict[str, str]]) -> str:
    headers = MOTOR_OUTPUT_COLUMNS[1:]
    thead = "<tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in headers) + "</tr>"
    body_rows = []
    for r in rows:
        tds = "".join(f"<td>{html.escape(_clean(r.get(h)).replace(chr(10), ' '))}</td>" for h in headers)
        body_rows.append(f"<tr>{tds}</tr>")
    return f"<table><thead>{thead}</thead><tbody>{''.join(body_rows)}</tbody></table>"


def _to_num(row: dict[str, str], field: str) -> float | None:
    return _extract_first_number(row.get(field, ""))


def _top_rows(rows: list[dict[str, str]], field: str, n: int = 5) -> list[dict[str, str]]:
    pool: list[tuple[float, dict[str, str]]] = []
    for r in rows:
        v = _to_num(r, field)
        if v is not None:
            pool.append((v, r))
    pool.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in pool[:n]]


def _summary_markdown(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "## 摘要结论\n\n暂无数据。"

    count_all = len(rows)
    complete = sum(1 for r in rows if r.get("缺失状态") == "完整")
    dual_motor = sum(1 for r in rows if "双" in _clean(r.get("驱动电机数")))

    lines = [
        "## 摘要结论",
        "",
        f"- 在售样本车型: {count_all}",
        f"- 电机字段完整车型: {complete} ({(complete / count_all * 100):.1f}%)",
        f"- 双电机车型: {dual_motor} ({(dual_motor / count_all * 100):.1f}%)",
        "",
        "## Top 5 电动机总功率",
        "",
    ]

    top_power = _top_rows(rows, "电动机总功率(kW)")
    top_torque = _top_rows(rows, "电动机总扭矩(Nm)")

    def mini_table(src: list[dict[str, str]], metric: str) -> str:
        headers = ["车系ID", "品牌", "车型", metric, "驱动电机数", "电机布局"]
        out = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
        for r in src:
            vals = [str(r.get(h, "")).replace("\n", " ").replace("|", "/") for h in headers]
            out.append("| " + " | ".join(vals) + " |")
        return "\n".join(out)

    lines.append(mini_table(top_power, "电动机总功率(kW)"))
    lines.extend(["", "## Top 5 电动机总扭矩", "", mini_table(top_torque, "电动机总扭矩(Nm)")])
    return "\n".join(lines)


def _summary_html(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "<h3>摘要结论</h3><p>暂无数据。</p>"

    count_all = len(rows)
    complete = sum(1 for r in rows if r.get("缺失状态") == "完整")
    dual_motor = sum(1 for r in rows if "双" in _clean(r.get("驱动电机数")))

    parts = [
        "<h3>摘要结论</h3>",
        "<ul>",
        f"<li>在售样本车型: {count_all}</li>",
        f"<li>电机字段完整车型: {complete} ({(complete / count_all * 100):.1f}%)</li>",
        f"<li>双电机车型: {dual_motor} ({(dual_motor / count_all * 100):.1f}%)</li>",
        "</ul>",
    ]

    def html_rank(src: list[dict[str, str]], metric: str, title: str) -> str:
        headers = ["车系ID", "品牌", "车型", metric, "驱动电机数", "电机布局"]
        thead = "<tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in headers) + "</tr>"
        rows_html = []
        for r in src:
            tds = "".join(f"<td>{html.escape(_clean(r.get(h)))}</td>" for h in headers)
            rows_html.append(f"<tr>{tds}</tr>")
        return f"<h4>{html.escape(title)}</h4><table><thead>{thead}</thead><tbody>{''.join(rows_html)}</tbody></table>"

    parts.append(html_rank(_top_rows(rows, "电动机总功率(kW)"), "电动机总功率(kW)", "Top 5 电动机总功率"))
    parts.append(html_rank(_top_rows(rows, "电动机总扭矩(Nm)"), "电动机总扭矩(Nm)", "Top 5 电动机总扭矩"))
    return "".join(parts)


def _sort_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    def key(r: dict[str, str]) -> tuple[Any, ...]:
        p = _to_num(r, "电动机总功率(kW)")
        t = _to_num(r, "电动机总扭矩(Nm)")
        hp = _to_num(r, "电动机总马力(Ps)")
        price = _to_num(r, "价格(万元)")
        return (
            0 if p is not None else 1,
            -(p or 0),
            0 if t is not None else 1,
            -(t or 0),
            0 if hp is not None else 1,
            -(hp or 0),
            -(price or 0),
            _clean(r.get("品牌")),
            _clean(r.get("车型")),
        )

    return sorted(rows, key=key)


def _collect_existing_report_dates() -> set[str]:
    existing: set[str] = set()
    if not REPORT_ROOT.exists():
        return existing

    for p in REPORT_ROOT.iterdir():
        if not p.is_dir():
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.name):
            continue
        if (p / "filtered.json").exists():
            existing.add(p.name)

    return existing


def run(args: argparse.Namespace) -> int:
    # Auto backfill: replay missing historical days only.
    # Today runs only when missing, never rerun if already generated.
    if (
        not getattr(args, "_backfill_dispatch", False)
        and not args.date
        and not args.no_backfill_missing
    ):
        today = dt.date.today()
        today_str = today.isoformat()
        backfill_days = max(0, int(args.backfill_days))
        existing_dates = _collect_existing_report_dates()

        planned_dates: list[str] = []

        # Historical window excludes today: [today-backfill_days, today-1]
        for offset in range(backfill_days, 0, -1):
            d = (today - dt.timedelta(days=offset)).isoformat()
            if d not in existing_dates:
                planned_dates.append(d)

        # Run today only when missing.
        if today_str not in existing_dates:
            planned_dates.append(today_str)

        if planned_dates:
            print("Backfill planned dates: " + ", ".join(planned_dates))
        else:
            print("Backfill planned dates: none (all existing, today already generated)")

        failed: list[str] = []
        for d in planned_dates:
            child = argparse.Namespace(**vars(args))
            child.date = d
            child._backfill_dispatch = True
            try:
                run(child)
            except Exception as exc:
                failed.append(f"{d}: {exc}")
                print(f"Backfill failed for {d}: {exc}")

        if failed:
            raise RuntimeError("Backfill failed for dates: " + " | ".join(failed))
        return 0

    run_date = args.date or dt.date.today().isoformat()
    source_file = _find_latest_source(args.source)

    if not args.no_patch_source_motor_columns:
        if ensure_motor_columns is None:
            print("Warning: motor column backfill helper not available; skipping source patch step.")
        else:
            patched = ensure_motor_columns(
                source_file,
                default_value="未明确显示",
                enrich_online=not args.no_enrich_online,
                timeout_sec=args.enrich_timeout_sec,
                max_series=args.enrich_max_series,
            )
            if patched["added_columns"]:
                print(
                    f"Patched source motor columns: +{len(patched['added_columns'])} on {source_file.name}"
                )
            if not args.no_enrich_online:
                print(
                    "Online motor enrichment: "
                    f"success series={patched.get('online_success_series', 0)}, "
                    f"failed series={patched.get('online_failed_series', 0)}, "
                    f"filled cells={patched.get('online_filled_cells', 0)}"
                )
                if patched.get("online_fail_reason"):
                    print(f"Online motor enrichment note: {patched.get('online_fail_reason')}")
            print(f"Offline motor enrichment: filled cells={patched.get('offline_filled_cells', 0)}")

    source_rows = _load_csv_rows(source_file)

    price_map_path = Path(args.price_map)
    if not price_map_path.is_absolute():
        price_map_path = ROOT / price_map_path

    pair_price_map, series_price_map = _load_price_map(price_map_path)

    source_price_cols = [
        c
        for c in ["官方指导价(万元)", "厂商指导价(万元)", "指导价(万元)", "价格(万元)", "价格"]
        if source_rows and c in source_rows[0]
    ]

    previous_rows = _load_previous_rows(run_date)
    prev_map = {_model_key(r): r for r in previous_rows}

    today_selected: list[dict[str, str]] = []
    unresolved_price_models: list[str] = []

    for row in source_rows:
        if _clean(row.get("车型")) == "本批合计提取44条配置":
            continue

        power = _clean(row.get("动力形式"))
        if "纯电" not in power:
            continue

        range_km = _resolve_range_km(row)
        if range_km is None or range_km <= args.range_threshold_km:
            continue

        price_wan = _resolve_price(row, pair_price_map, series_price_map, source_price_cols)
        if price_wan is None:
            unresolved_price_models.append(_model_key(row))
            continue

        if price_wan <= args.price_threshold_wan:
            continue

        today_selected.append(_to_output_row(row, run_date, price_wan, "当日采集"))

    today_map = {_model_key(r): r for r in today_selected}

    carried_rows: list[dict[str, str]] = []
    for k, prev in prev_map.items():
        if k in today_map:
            continue

        prev_price = _to_num(prev, "价格(万元)") or 0
        prev_range = _to_num(prev, "纯电续航里程(km)CLTC") or _to_num(prev, "纯电续航里程(km)工信部") or 0
        if prev_price <= args.price_threshold_wan or prev_range <= args.range_threshold_km:
            continue

        carry = dict(prev)
        carry["数据日期"] = run_date
        carry["数据状态"] = "昨日沿用(当日未出现)"
        carry["缺失状态"] = _missing_status(carry)
        carried_rows.append(carry)

    final_rows = _sort_rows(today_selected + carried_rows)

    output_dir = REPORT_ROOT / run_date
    output_dir.mkdir(parents=True, exist_ok=True)

    filtered_csv = output_dir / "filtered.csv"
    filtered_json = output_dir / "filtered.json"
    summary_md = output_dir / "summary.md"
    section_html = output_dir / "confluence_section.html"

    _write_csv(filtered_csv, final_rows)
    filtered_json.write_text(json.dumps(final_rows, ensure_ascii=False, indent=2), encoding="utf-8")

    md_lines = [
        f"# 懂车帝电机性能日报 {run_date}",
        "",
        f"- 数据源: {source_file.name}",
        f"- 筛选规则: 价格>{args.price_threshold_wan}万 且 续航>{args.range_threshold_km}km 且 纯电车型",
        f"- 当日总车型: {len(final_rows)}",
        f"- 昨日沿用车型: {sum(1 for r in final_rows if r.get('数据状态') != '当日采集')}",
        f"- 价格缺失(未纳入筛选): {len(set(unresolved_price_models))}",
        "",
        _summary_markdown(final_rows),
        "",
        "## 车型明细",
        "",
        _rows_to_markdown(final_rows),
        "",
    ]
    summary_md.write_text("\n".join(md_lines), encoding="utf-8")

    html_body = (
        f"<!-- DONGCHEDI_MOTOR_DAILY:{run_date}:START -->"
        f"<h2>懂车帝电机性能日报 {html.escape(run_date)}</h2>"
        f"<p>数据源: {html.escape(source_file.name)}</p>"
        f"<p>筛选规则: 价格&gt;{args.price_threshold_wan}万 且 续航&gt;{args.range_threshold_km}km 且 纯电车型。</p>"
        f"<p>当日总车型: {len(final_rows)}；昨日沿用车型: {sum(1 for r in final_rows if r.get('数据状态') != '当日采集')}；价格缺失(未纳入筛选): {len(set(unresolved_price_models))}</p>"
        f"{_summary_html(final_rows)}"
        f"{_rows_to_html_table(final_rows)}"
        f"<!-- DONGCHEDI_MOTOR_DAILY:{run_date}:END -->"
    )
    section_html.write_text(html_body, encoding="utf-8")

    print(f"Run date: {run_date}")
    print(f"Source: {source_file}")
    print(f"Output: {output_dir}")
    print(f"Rows: {len(final_rows)}")
    if len(set(unresolved_price_models)) > 0:
        print(f"Warning: unresolved price models not included: {len(set(unresolved_price_models))}")

    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate Dongchedi motor benchmarking daily report.")
    parser.add_argument("--date", default="", help="Run date in YYYY-MM-DD. Defaults to today.")
    parser.add_argument("--source", default="", help="Optional source CSV path.")
    parser.add_argument("--price-map", default=str(PRICE_MAP_DEFAULT), help="Price map CSV path.")
    parser.add_argument("--price-threshold-wan", type=float, default=20.0, help="Price threshold in wan.")
    parser.add_argument("--range-threshold-km", type=float, default=400.0, help="Range threshold in km.")
    parser.add_argument(
        "--no-backfill-missing",
        action="store_true",
        help="Disable auto backfill for missing days when --date is not provided.",
    )
    parser.add_argument(
        "--backfill-days",
        type=int,
        default=7,
        help="Look back this many days to detect and replay missing report dates.",
    )
    parser.add_argument(
        "--no-patch-source-motor-columns",
        action="store_true",
        help="Disable auto backfill for missing motor columns in source CSV.",
    )
    parser.add_argument(
        "--no-enrich-online",
        action="store_true",
        help="Disable online motor value enrichment from Dongchedi pages.",
    )
    parser.add_argument(
        "--enrich-timeout-sec",
        type=int,
        default=12,
        help="Per-request timeout in seconds for online enrichment.",
    )
    parser.add_argument(
        "--enrich-max-series",
        type=int,
        default=0,
        help="Max series to enrich online (0 means all).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Compatibility flag. Output is still written.")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(run(parse_args()))
