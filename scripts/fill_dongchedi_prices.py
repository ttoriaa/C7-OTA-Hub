from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRICE_MAP = ROOT / "dongchedi_price_map.csv"

PRICE_BY_SERIES = {
    "10136": "23.99-37.99",
    "10162": "17.98-26.28",
    "10177": "20.29-24.29",
    "10178": "33.98",
    "10180": "24.98-31.98",
    "20041": "23.35-38.99",
    "25072": "26.98-31.98",
    "25079": "29.98-41.98",
    "25557": "24.98-26.98",
    "25621": "27.98-35.98",
    "25651": "33.9",
    "25718": "21.98-26.98",
    "25816": "19.99-26.39",
    "25819": "22.99-28.99",
    "25994": "19.98-23.98",
    "3503": "23.66-41.96",
    "4363": "26.35-31.35",
    "4980": "17.99-20.99",
    "5308": "28.99-42.99",
    "5461": "24.88-27.88",
    "5805": "91.05",
    "5832": "33.8-39.8",
    "6116": "40.98-51.98",
    "8835": "21.59-33.98",
    "8966": "18.98-30.18",
    "9118": "22.49-28.49",
    "9345": "18.99-22.99",
    "9440": "27.98-39.98",
    "9778": "22.98-26.98",
    "9833": "",
}


def main() -> int:
    rows = list(csv.DictReader(PRICE_MAP.open("r", encoding="utf-8-sig")))
    updated = 0
    for row in rows:
        sid = row["车系ID"]
        price = PRICE_BY_SERIES.get(sid, "")
        if price and not row.get("价格(万元)", "").strip():
            row["价格(万元)"] = price
            row["价格来源"] = "懂车帝参数页官方指导价"
            row["更新时间"] = "2026-06-08"
            updated += 1
        elif sid == "9833" and not row.get("价格(万元)", "").strip():
            row["价格来源"] = "懂车帝参数页"
            row["更新时间"] = "2026-06-08"

    with PRICE_MAP.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["车系ID", "车型", "价格(万元)", "价格来源", "更新时间"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Updated {updated} rows in {PRICE_MAP}")
    print("Series with unresolved price: 9833")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
