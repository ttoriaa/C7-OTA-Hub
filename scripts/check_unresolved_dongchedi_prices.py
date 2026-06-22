#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import run_dongchedi_daily as daily


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List unresolved Dongchedi price models using the daily report resolver.")
    parser.add_argument("--source", default="", help="Source CSV path. Defaults to latest dongchedi_full_configs_*.csv")
    parser.add_argument("--price-map", default=str(daily.PRICE_MAP_DEFAULT), help="Price mapping CSV path.")
    parser.add_argument("--all-powertrains", action="store_true", help="Inspect all rows instead of only pure-EV rows.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_file = daily._find_latest_source(args.source or None)

    price_map_path = Path(args.price_map)
    if not price_map_path.is_absolute():
        price_map_path = daily.ROOT / price_map_path

    source_rows = daily._load_csv_rows(source_file)
    pair_price_map, series_price_map = daily._load_price_map(price_map_path)
    source_price_cols = [
        column
        for column in ["官方指导价(万元)", "厂商指导价(万元)", "指导价(万元)", "价格(万元)", "价格"]
        if source_rows and column in source_rows[0]
    ]

    unresolved: list[tuple[str, str]] = []
    seen: set[str] = set()

    for row in source_rows:
        if daily._clean(row.get("车型")) == "本批合计提取44条配置":
            continue
        if not args.all_powertrains and "纯电" not in daily._clean(row.get("动力形式")):
            continue
        if daily._resolve_price(row, pair_price_map, series_price_map, source_price_cols) is not None:
            continue

        model_key = daily._model_key(row)
        if model_key in seen:
            continue
        seen.add(model_key)
        unresolved.append((daily._clean(row.get("车系ID")), daily._clean(row.get("车型"))))

    print(f"Source: {source_file}")
    print(f"Price map: {price_map_path}")
    print(f"Unresolved models: {len(unresolved)}")
    for series_id, model in unresolved:
        print(f"{series_id}\t{model}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())