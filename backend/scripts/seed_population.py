# -*- coding: utf-8 -*-
"""
行政區人口資料匯入（高齡事故率與過度代表倍數之分母）

資料來源：臺南市政府民政局「各區人口數按三階段年齡百分比分及其扶養比」
  https://bca.tainan.gov.tw/News_Content.aspx?n=1134&s=8157
  → 下載表 04 的 .xls，放到 分析報告/臺南市各區人口三階段年齡_民政局.xls

⚠️ 下載注意：該站直接 curl 會回 0 bytes，必須帶 referer 與 User-Agent。
⚠️ 檔案為 BIFF 格式（.xls），需 xlrd 2.x（xlrd 2.x 只支援 .xls，正合用）。
⚠️ 僅切至「65 歲以上」單一級距，無法拆 5 歲組。

用法：
    python backend/scripts/seed_population.py            # 匯入全部可用月份
    python backend/scripts/seed_population.py --from 112 # 僅匯入民國 112 年起
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import SessionLocal, init_db          # noqa: E402
from app.models.dimension import Population             # noqa: E402

DEFAULT_XLS = os.path.join(
    os.path.dirname(__file__), "..", "..",
    "分析報告", "臺南市各區人口三階段年齡_民政局.xls",
)
DISTRICTS = ("新化區", "山上區", "左鎮區")
SHEET_RE = re.compile(r"^(\d{3})\.(\d{1,2})")      # 例：115.6三階段年齡


def parse_sheet(sheet):
    """回傳 {行政區: (總人口, 65歲以上人口)}；欄位位置：0=區名 1=總計 4=65歲以上"""
    out = {}
    for r in range(sheet.nrows):
        name = str(sheet.cell_value(r, 0)).replace("\xa0", "").strip()
        if name in DISTRICTS:
            try:
                out[name] = (int(sheet.cell_value(r, 1)), int(sheet.cell_value(r, 4)))
            except (ValueError, TypeError):
                continue
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xls", default=DEFAULT_XLS)
    ap.add_argument("--from", dest="from_year", type=int, default=112,
                    help="起始民國年（預設 112，與事故資料庫涵蓋範圍對齊）")
    args = ap.parse_args()

    if not os.path.exists(args.xls):
        print(f"FAIL: 找不到人口檔 {args.xls}")
        print("  請至民政局網站下載表 04 後放入 分析報告/ 目錄")
        return 1

    try:
        import xlrd
    except ImportError:
        print("FAIL: 需要 xlrd（pip install 'xlrd>=2.0'）")
        return 1

    init_db()
    wb = xlrd.open_workbook(args.xls)
    db = SessionLocal()

    written, skipped, months = 0, 0, []
    for sheet_name in wb.sheet_names():
        m = SHEET_RE.match(sheet_name.strip())
        if not m:
            continue
        year, month = int(m.group(1)), int(m.group(2))
        if year < args.from_year:
            skipped += 1
            continue
        ym = f"{year:03d}-{month:02d}"
        data = parse_sheet(wb.sheet_by_name(sheet_name))
        if len(data) < len(DISTRICTS):
            continue
        months.append(ym)
        for dist, (total, e65) in data.items():
            row = db.query(Population).filter(
                Population.year_month == ym, Population.district == dist
            ).first()
            if row:
                row.total_pop, row.elderly_pop = total, e65      # 冪等更新
            else:
                db.add(Population(year_month=ym, district=dist,
                                  total_pop=total, elderly_pop=e65))
            written += 1
    db.commit()

    months.sort()
    total_rows = db.query(Population).count()
    print(f"OK: 寫入/更新 {written} 列，涵蓋 {len(months)} 個月"
          f"（{months[0]} ~ {months[-1]}），表內共 {total_rows} 列")
    print(f"    早於民國 {args.from_year} 年而略過的 sheet：{skipped}")
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
