# Dongchedi Daily Motor Benchmarking Pipeline

## Goal

Generate a daily motor-performance report for pure EV models and publish each day to a dedicated Confluence child page at 09:00 local time.

## Filtering Rules

1. 纯电车型 (`动力形式` contains `纯电`)
2. 价格(万元) > 20
3. 续航里程 > 400km (priority: `纯电续航里程(km)CLTC`, fallback: `纯电续航里程(km)工信部`)

## Motor Fields

The report tracks these fields:

- 电动机
- 电机类型
- 电动机总功率(kW)
- 电动机总马力(Ps)
- 电动机总扭矩(Nm)
- 前电动机最大扭矩(Nm)
- 前电动机最大功率(kW)
- 后电动机最大扭矩(Nm)
- 后电动机最大功率(kW)
- 驱动电机数
- 电机布局

Note:
- Current source CSV may not include motor columns yet. Missing values are marked as `未明确显示`, and `缺失状态` will track completeness.
- The generator now auto-backfills missing source motor columns before filtering, so the source header stays complete.
- The generator also tries online enrichment from Dongchedi parameter pages by series ID. When network/page parsing succeeds, source motor values are filled automatically.

## Environment Variables

Add to `.env`:

```env
CONFLUENCE_MOTOR_PAGE_ID=<optional-fallback-page-id>
CONFLUENCE_MOTOR_PARENT_PAGE_ID=<preferred-parent-page-id>
```

Rules:
- If `CONFLUENCE_MOTOR_PARENT_PAGE_ID` is set, each date report is created/updated as a child page under that parent.
- If same date reruns, page is updated in place.

## Commands

Generate local artifacts:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_dongchedi_motor_daily.py --dry-run
```

Run without online enrichment (faster, keeps placeholder-only behavior):

```powershell
.\.venv\Scripts\python.exe .\scripts\run_dongchedi_motor_daily.py --dry-run --no-enrich-online
```

Only patch source CSV motor columns (standalone):

```powershell
.\.venv\Scripts\python.exe .\scripts\fill_dongchedi_motor_fields.py
```

If needed, disable auto backfill in generator:

```powershell
.\.venv\Scripts\python.exe .\scripts\run_dongchedi_motor_daily.py --dry-run --no-patch-source-motor-columns
```

Publish latest generated motor report:

```powershell
.\.venv\Scripts\python.exe .\scripts\push_dongchedi_motor_to_confluence.py
```

## Outputs

Per day folder under `reports/dongchedi_motor_daily/YYYY-MM-DD/`:

- `filtered.csv`
- `filtered.json`
- `summary.md`
- `confluence_section.html`

## Scheduling (09:00)

Register/update scheduled task:

```powershell
.\scripts\register_dongchedi_motor_daily_task.ps1 -TaskName "DongchediDailyMotorBenchmark" -Time "09:00"
```

Pipeline order:
1. generate motor daily artifacts
2. publish to Confluence
