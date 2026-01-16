import urllib.request
import json

print("測試日期篩選修復...")
print("=" * 50)

for days in [30, 90, 180, 365]:
    try:
        url = f'http://localhost:8080/api/v1/recommendations/accidents/hotspots?days={days}'
        with urllib.request.urlopen(url) as response:
            d = json.loads(response.read().decode())
            total = d["summary"]["total_accidents"]
            a1 = d["summary"]["a1_total"]
            start = d["query_period"]["start_date"]
            end = d["query_period"]["end_date"]
            print(f"{days:3d}天: {total:3d}事故, A1={a1}, 期間: {start} ~ {end}")
    except Exception as e:
        print(f"{days}天: 錯誤 - {e}")
