from __future__ import annotations

import argparse
import csv
import glob
import re
import socket
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]

# Keep both raw and unit-suffixed column names to stay compatible with current
# and potential future extractors.
MOTOR_SOURCE_COLUMNS = [
    "电动机",
    "电机类型",
    "电动机总功率",
    "电动机总功率(kW)",
    "电动机总马力",
    "电动机总马力(Ps)",
    "电动机总扭矩",
    "电动机总扭矩(Nm)",
    "前电动机最大扭矩",
    "前电动机最大扭矩(Nm)",
    "前电动机最大功率",
    "前电动机最大功率(kW)",
    "后电动机最大扭矩",
    "后电动机最大扭矩(Nm)",
    "后电动机最大功率",
    "后电动机最大功率(kW)",
    "驱动电机数",
    "电机布局",
]

MISSING_VALUE = "未明确显示"

NUMERIC_FIELDS = [
    "电动机总功率",
    "电动机总功率(kW)",
    "电动机总马力",
    "电动机总马力(Ps)",
    "电动机总扭矩",
    "电动机总扭矩(Nm)",
    "前电动机最大扭矩",
    "前电动机最大扭矩(Nm)",
    "前电动机最大功率",
    "前电动机最大功率(kW)",
    "后电动机最大扭矩",
    "后电动机最大扭矩(Nm)",
    "后电动机最大功率",
    "后电动机最大功率(kW)",
]

BLOCK_LABELS = [
    "电动机描述",
    "电机类型",
    "电动机总功率(kW)",
    "电动机总马力(Ps)",
    "电动机总扭矩(N·m)",
    "前电动机最大功率(kW)",
    "前电动机最大扭矩(N·m)",
    "后电动机最大功率(kW)",
    "后电动机最大扭矩(N·m)",
    "驱动电机数",
    "电机布局",
]

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"


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


def _strip(s: str) -> str:
    return re.sub(r"\s+", "", s or "")


def _find_block(compact_text: str, label: str, next_labels: list[str]) -> str:
    i = compact_text.find(label)
    if i < 0:
        return ""
    start = i + len(label)
    end = len(compact_text)
    for n in next_labels:
        j = compact_text.find(n, start)
        if j >= 0:
            end = min(end, j)
    return compact_text[start:end]


def _max_number(text: str) -> str:
    nums = re.findall(r"\d+(?:\.\d+)?", text)
    if not nums:
        return ""
    vals = [float(n) for n in nums]
    mx = max(vals)
    return str(int(mx)) if abs(mx - int(mx)) < 1e-9 else f"{mx:g}"


def _parse_motor_from_html(html: str) -> dict[str, str]:
    compact = _strip(re.sub(r"<[^>]+>", "", html))

    blocks: dict[str, str] = {}
    for idx, label in enumerate(BLOCK_LABELS):
        blocks[label] = _find_block(compact, label, BLOCK_LABELS[idx + 1 :])

    out: dict[str, str] = {}

    kw = _max_number(blocks.get("电动机总功率(kW)", ""))
    ps = _max_number(blocks.get("电动机总马力(Ps)", ""))
    nm = _max_number(blocks.get("电动机总扭矩(N·m)", ""))
    fkw = _max_number(blocks.get("前电动机最大功率(kW)", ""))
    fnm = _max_number(blocks.get("前电动机最大扭矩(N·m)", ""))
    rkw = _max_number(blocks.get("后电动机最大功率(kW)", ""))
    rnm = _max_number(blocks.get("后电动机最大扭矩(N·m)", ""))

    if kw:
        out["电动机总功率"] = kw
        out["电动机总功率(kW)"] = kw
    if ps:
        out["电动机总马力"] = ps
        out["电动机总马力(Ps)"] = ps
    if nm:
        out["电动机总扭矩"] = nm
        out["电动机总扭矩(Nm)"] = nm
    if fkw:
        out["前电动机最大功率"] = fkw
        out["前电动机最大功率(kW)"] = fkw
    if fnm:
        out["前电动机最大扭矩"] = fnm
        out["前电动机最大扭矩(Nm)"] = fnm
    if rkw:
        out["后电动机最大功率"] = rkw
        out["后电动机最大功率(kW)"] = rkw
    if rnm:
        out["后电动机最大扭矩"] = rnm
        out["后电动机最大扭矩(Nm)"] = rnm

    motor_type_block = blocks.get("电机类型", "")
    for token in ["永磁/同步", "永磁同步", "感应/异步", "交流/异步", "同步"]:
        if token in motor_type_block:
            out["电机类型"] = token
            break

    motor_desc = blocks.get("电动机描述", "")
    if ps:
        out["电动机"] = f"纯电动{ps}马力"
    elif motor_desc:
        m = re.search(r"纯电动\d+马力", motor_desc)
        if m:
            out["电动机"] = m.group(0)

    motor_count_block = blocks.get("驱动电机数", "")
    for token in ["四电机", "三电机", "双电机", "单电机"]:
        if token in motor_count_block:
            out["驱动电机数"] = token
            break

    layout_block = blocks.get("电机布局", "")
    for token in ["前置+后置", "后置+前置", "前置", "后置"]:
        if token in layout_block:
            out["电机布局"] = token
            break

    return out


def _is_missing(v: str) -> bool:
    return not (v or "").strip() or v.strip() == MISSING_VALUE


def _offline_enrich_from_model_name(rows: list[dict[str, str]]) -> int:
    """Best-effort offline fallback from model name tokens.

    This intentionally fills only topology-like fields with high confidence
    and avoids guessing power/torque numeric specs.
    """
    filled_cells = 0

    dual_tokens = ["四驱", "双电机", "4MATIC", "quattro", "AWD", "全轮驱动"]
    single_rear_tokens = ["后驱", "后轮驱动", "RWD"]
    single_front_tokens = ["前驱", "前轮驱动", "FWD"]
    tri_tokens = ["三电机"]
    quad_tokens = ["四电机"]

    for row in rows:
        model = (row.get("车型") or "").strip()
        if not model:
            continue

        motor_count = ""
        layout = ""

        if any(t in model for t in quad_tokens):
            motor_count = "四电机"
            layout = "前置+后置"
        elif any(t in model for t in tri_tokens):
            motor_count = "三电机"
            layout = "前置+后置"
        elif any(t in model for t in dual_tokens):
            motor_count = "双电机"
            layout = "前置+后置"
        elif any(t in model for t in single_rear_tokens):
            motor_count = "单电机"
            layout = "后置"
        elif any(t in model for t in single_front_tokens):
            motor_count = "单电机"
            layout = "前置"

        if motor_count and "驱动电机数" in row and _is_missing(row.get("驱动电机数", "")):
            row["驱动电机数"] = motor_count
            filled_cells += 1

        if layout and "电机布局" in row and _is_missing(row.get("电机布局", "")):
            row["电机布局"] = layout
            filled_cells += 1

        if motor_count and "电动机" in row and _is_missing(row.get("电动机", "")):
            row["电动机"] = f"纯电动{motor_count}"
            filled_cells += 1

    return filled_cells


def _quick_connect(host: str, port: int, timeout_sec: int) -> tuple[bool, str]:
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True, ""
    except Exception as e:
        return False, str(e)


def _enrich_from_web(rows: list[dict[str, str]], timeout_sec: int, max_series: int) -> tuple[int, int, int, str]:
    sids = []
    seen = set()
    for r in rows:
        sid = (r.get("车系ID") or "").strip()
        if sid and sid not in seen:
            seen.add(sid)
            sids.append(sid)
    if max_series > 0:
        sids = sids[:max_series]

    ok, reason = _quick_connect("www.dongchedi.com", 443, timeout_sec=min(timeout_sec, 3))
    if not ok:
        return 0, len(sids), 0, f"precheck failed: {reason}"

    session = requests.Session()
    session.headers.update({"User-Agent": UA})

    filled_cells = 0
    success_series = 0
    failed_series = 0
    parsed_by_sid: dict[str, dict[str, str]] = {}
    first_error = ""

    for sid in sids:
        url = f"https://www.dongchedi.com/auto/params-carIds-x-{sid}"
        try:
            resp = session.get(url, timeout=(3, timeout_sec))
            resp.raise_for_status()
            parsed = _parse_motor_from_html(resp.text)
            if parsed:
                parsed_by_sid[sid] = parsed
                success_series += 1
            else:
                failed_series += 1
                if not first_error:
                    first_error = "page parsed but no motor block"
        except Exception:
            failed_series += 1
            if not first_error:
                first_error = "request failed"

    for row in rows:
        sid = (row.get("车系ID") or "").strip()
        parsed = parsed_by_sid.get(sid)
        if not parsed:
            continue
        for col, val in parsed.items():
            if col in row and _is_missing(row.get(col, "")) and val:
                row[col] = val
                filled_cells += 1

    return success_series, failed_series, filled_cells, first_error


def ensure_motor_columns(
    source_csv: Path,
    default_value: str = MISSING_VALUE,
    enrich_online: bool = False,
    timeout_sec: int = 12,
    max_series: int = 0,
) -> dict[str, object]:
    with source_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)

    missing_columns = [c for c in MOTOR_SOURCE_COLUMNS if c not in fieldnames]
    new_fieldnames = fieldnames + missing_columns

    for row in rows:
        for c in missing_columns:
            row[c] = row.get(c) or default_value

    success_series = 0
    failed_series = 0
    filled_cells = 0
    fail_reason = ""
    if enrich_online:
        success_series, failed_series, filled_cells, fail_reason = _enrich_from_web(
            rows, timeout_sec=timeout_sec, max_series=max_series
        )

    offline_filled_cells = _offline_enrich_from_model_name(rows)

    with source_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=new_fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return {
        "source": str(source_csv),
        "added_columns": missing_columns,
        "rows_updated": len(rows),
        "online_success_series": success_series,
        "online_failed_series": failed_series,
        "online_filled_cells": filled_cells,
        "online_fail_reason": fail_reason,
        "offline_filled_cells": offline_filled_cells,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill missing motor columns in Dongchedi source CSV.")
    parser.add_argument("--source", default="", help="Optional source CSV path. Defaults to latest dongchedi_full_configs_*.csv.")
    parser.add_argument("--default-value", default=MISSING_VALUE, help="Default value for newly added columns.")
    parser.add_argument("--enrich-online", action="store_true", help="Try to enrich motor values by scraping Dongchedi params pages.")
    parser.add_argument("--timeout-sec", type=int, default=12, help="Per-request timeout for online enrichment.")
    parser.add_argument("--max-series", type=int, default=0, help="Limit number of series to enrich online (0 means all).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = _find_latest_source(args.source)
    result = ensure_motor_columns(
        source,
        default_value=args.default_value,
        enrich_online=args.enrich_online,
        timeout_sec=args.timeout_sec,
        max_series=args.max_series,
    )

    added_columns = result["added_columns"]
    if added_columns:
        print(f"Updated source: {result['source']}")
        print(f"Added motor columns: {len(added_columns)}")
        print(" - " + "\n - ".join(str(x) for x in added_columns))
        print(f"Rows updated: {result['rows_updated']}")
    else:
        print(f"No changes needed: {result['source']}")

    if args.enrich_online:
        print(
            "Online enrichment: "
            f"success series={result['online_success_series']}, "
            f"failed series={result['online_failed_series']}, "
            f"filled cells={result['online_filled_cells']}"
        )
        if result.get("online_fail_reason"):
            print(f"Online enrichment note: {result['online_fail_reason']}")
    print(f"Offline enrichment: filled cells={result.get('offline_filled_cells', 0)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())