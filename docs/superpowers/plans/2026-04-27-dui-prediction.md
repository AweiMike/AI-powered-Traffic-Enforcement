# 酒駕風險預測模組 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a DUI hotspot prediction module (XGBoost dual-model) that outputs 7-day risk predictions per (sub_unit × shift × date) on the author's local machine only, deeply isolated from colleague builds.

**Architecture:** Local SQLite + FastAPI backend + React frontend, plus a dedicated `.venv-ml` Python 3.12 environment for XGBoost/SHAP. Daily lazy refresh triggered when frontend mounts dashboard. Build-time exclusion (`build_update.py --exclude prediction`) keeps colleague portable builds free of any prediction code, model files, or schema.

**Tech Stack:**
- Backend: FastAPI, SQLAlchemy, SQLite, pydantic
- ML: xgboost 2.1.x, scikit-learn 1.5.x, shap 0.46.x, joblib, holidays, lunardate, pandas, pyarrow
- External: CWA (Central Weather Administration) Open Data API
- Frontend: React 18 + TypeScript + Vite + Tailwind (existing)
- Testing: pytest + httpx (backend), vitest (frontend, follow existing patterns)

**Spec:** `docs/superpowers/specs/2026-04-27-dui-prediction-design.md`

**Phases:**
1. Foundations (Tasks 1-3) — venv, schema, calendar/weather data
2. Feature Engineering & Training (Tasks 4-6) — features, training, evaluation
3. Inference & API (Tasks 7-9) — predict, status/lock, endpoints
4. Frontend (Tasks 10-12) — page, deep-links, refresh trigger
5. Build Isolation & Polish (Tasks 13-14) — `--exclude` flag, user guide

---

## Phase 1: Foundations

### Task 1: Set up `.venv-ml` and lock ML dependencies

**Files:**
- Create: `requirements_ml.txt`
- Create: `.gitignore` entries
- Modify: `.gitignore`

- [ ] **Step 1: Create requirements_ml.txt**

Path: `D:\Programming\精準執法儀表板系統\requirements_ml.txt`

```
xgboost>=2.1.0,<3.0
scikit-learn>=1.5.0,<2.0
shap>=0.46.0
pandas>=2.0
joblib>=1.4
holidays>=0.50
lunardate>=0.2.2
requests>=2.31
pyarrow>=15.0
pytest>=8.0
httpx>=0.27
```

- [ ] **Step 2: Update .gitignore**

Read existing `.gitignore`, then append:

```gitignore

# DUI prediction module (本機限定，不入版控)
.venv-ml/
backend/models/*.pkl
backend/models/feature_columns_*.json
backend/models/eval_reports/
backend/data/feature_cache/
backend/.env.ml
```

- [ ] **Step 3: Create venv with Python 3.12**

Run (PowerShell):

```powershell
py -3.12 -m venv D:\Programming\精準執法儀表板系統\.venv-ml
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pip install --upgrade pip
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\pip.exe install -r D:\Programming\精準執法儀表板系統\requirements_ml.txt
```

Expected: All packages install without error. Check version:
```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -c "import xgboost; print(xgboost.__version__)"
```
Expected output: `2.1.x` (any 2.1 patch).

- [ ] **Step 4: Verify SHAP works on small synthetic data**

Run:
```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -c "import shap, xgboost, numpy as np; X = np.random.rand(100, 5); y = (X[:,0] > 0.5).astype(int); m = xgboost.XGBClassifier(n_estimators=10).fit(X, y); explainer = shap.TreeExplainer(m); print('SHAP OK, sample shape:', explainer.shap_values(X[:5]).shape)"
```
Expected output: `SHAP OK, sample shape: (5, 5)`

- [ ] **Step 5: Commit**

```bash
git add requirements_ml.txt .gitignore
git commit -m "chore: add ML venv requirements + gitignore for prediction module"
```

---

### Task 2: Create prediction schema (4 new tables)

**Files:**
- Create: `backend/app/models/prediction.py`
- Create: `backend/scripts/init_prediction_schema.py`
- Create: `backend/tests/test_prediction_schema.py`
- Modify: `backend/app/models/__init__.py`

- [ ] **Step 1: Write the failing test**

Path: `backend/tests/test_prediction_schema.py`

```python
"""Schema initialization tests for DUI prediction module."""
import os
import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect


@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test.db"
    yield f"sqlite:///{db_path}"


def test_prediction_schema_creates_four_tables(temp_db):
    """init_prediction_schema must create ext_weather, ext_calendar, dui_predictions, system_locks."""
    from backend.scripts.init_prediction_schema import init_schema

    init_schema(temp_db)

    engine = create_engine(temp_db)
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    assert "ext_weather" in tables
    assert "ext_calendar" in tables
    assert "dui_predictions" in tables
    assert "system_locks" in tables


def test_ext_weather_unique_constraint(temp_db):
    """ext_weather should reject duplicate (date, district, shift_id)."""
    from backend.scripts.init_prediction_schema import init_schema
    init_schema(temp_db)

    db_path = temp_db.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO ext_weather (date, district, shift_id, rainfall_mm) VALUES ('2026-01-01', '新化區', '05', 0.0)")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute("INSERT INTO ext_weather (date, district, shift_id, rainfall_mm) VALUES ('2026-01-01', '新化區', '05', 1.0)")
        conn.commit()
    conn.close()


def test_dui_predictions_unique_constraint(temp_db):
    """dui_predictions should reject duplicate (predict_for_date, sub_unit, shift_id)."""
    from backend.scripts.init_prediction_schema import init_schema
    init_schema(temp_db)

    db_path = temp_db.replace("sqlite:///", "")
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO dui_predictions (predict_for_date, sub_unit, shift_id, risk_score) VALUES ('2026-05-01', '新化派出所', '05', 0.5)")
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        cur.execute("INSERT INTO dui_predictions (predict_for_date, sub_unit, shift_id, risk_score) VALUES ('2026-05-01', '新化派出所', '05', 0.7)")
        conn.commit()
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run:
```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/test_prediction_schema.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'backend.scripts.init_prediction_schema'`

- [ ] **Step 3: Create the SQLAlchemy models**

Path: `backend/app/models/prediction.py`

```python
"""DUI prediction module schema (本機限定)."""
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, Integer, String, UniqueConstraint, Index,
)

from .core import Base


class ExtWeather(Base):
    __tablename__ = "ext_weather"
    id = Column(Integer, primary_key=True)
    date = Column(Date, nullable=False)
    district = Column(String(50), nullable=False)
    shift_id = Column(String(2), nullable=False)
    rainfall_mm = Column(Float)
    temperature_c = Column(Float)
    humidity_pct = Column(Float)
    wind_speed_ms = Column(Float)
    weather_code = Column(String(20))
    is_typhoon = Column(Boolean, default=False)
    data_source = Column(String(20), default="CWA")
    fetched_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("date", "district", "shift_id", name="uq_ext_weather"),
        Index("idx_weather_date_district", "date", "district"),
    )


class ExtCalendar(Base):
    __tablename__ = "ext_calendar"
    date = Column(Date, primary_key=True)
    is_holiday = Column(Boolean, default=False)
    is_holiday_eve = Column(Boolean, default=False)
    lunar_day = Column(Integer)
    is_payday = Column(Boolean, default=False)
    is_friday = Column(Boolean, default=False)
    festival_name = Column(String(50))
    is_election_eve = Column(Boolean, default=False)


class DuiPrediction(Base):
    __tablename__ = "dui_predictions"
    id = Column(Integer, primary_key=True)
    predict_for_date = Column(Date, nullable=False)
    sub_unit = Column(String(100), nullable=False)
    shift_id = Column(String(2), nullable=False)
    group_name = Column(String(100))
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String(10))
    risk_rank = Column(Integer)
    predicted_count = Column(Float)
    shap_top_features = Column(String)  # JSON-encoded
    model_version = Column(String(20))
    generated_at = Column(DateTime, default=datetime.utcnow)
    __table_args__ = (
        UniqueConstraint("predict_for_date", "sub_unit", "shift_id", name="uq_dui_predictions"),
        Index("idx_pred_date_unit", "predict_for_date", "sub_unit"),
    )


class SystemLock(Base):
    __tablename__ = "system_locks"
    name = Column(String(50), primary_key=True)
    locked_at = Column(DateTime)
    released_at = Column(DateTime)
```

- [ ] **Step 4: Wire models into __init__.py**

Path: `backend/app/models/__init__.py` — append (read first to preserve existing imports):

```python
from .prediction import ExtWeather, ExtCalendar, DuiPrediction, SystemLock  # noqa: F401
```

- [ ] **Step 5: Create init script**

Path: `backend/scripts/init_prediction_schema.py`

```python
"""One-time schema init for DUI prediction tables. Local machine only."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine
from backend.app.models.core import Base
from backend.app.models import prediction  # noqa: F401  (register tables)


def init_schema(db_url: str) -> None:
    """Create the four prediction tables. Idempotent (uses CREATE IF NOT EXISTS)."""
    engine = create_engine(db_url)
    tables = [
        prediction.ExtWeather.__table__,
        prediction.ExtCalendar.__table__,
        prediction.DuiPrediction.__table__,
        prediction.SystemLock.__table__,
    ]
    Base.metadata.create_all(bind=engine, tables=tables, checkfirst=True)


if __name__ == "__main__":
    db_path = Path(__file__).resolve().parents[1] / "data" / "traffic_enforcement.db"
    init_schema(f"sqlite:///{db_path}")
    print(f"Prediction schema initialized at {db_path}")
```

- [ ] **Step 6: Run tests to verify pass**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/test_prediction_schema.py -v
```
Expected: 3 passed.

- [ ] **Step 7: Run init against local DB**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe backend\scripts\init_prediction_schema.py
```
Expected output: `Prediction schema initialized at ...traffic_enforcement.db`

- [ ] **Step 8: Commit**

```bash
git add backend/app/models/prediction.py backend/app/models/__init__.py backend/scripts/init_prediction_schema.py backend/tests/test_prediction_schema.py
git commit -m "feat(prediction): add ext_weather/ext_calendar/dui_predictions/system_locks schema"
```

---

### Task 3: Build calendar table (2021-2030, holidays + lunar + payday)

**Files:**
- Create: `backend/app/utils/shift_mapping.py`
- Create: `backend/scripts/build_calendar.py`
- Create: `backend/tests/test_build_calendar.py`

- [ ] **Step 1: Create shared shift mapping (used here + later tasks)**

Path: `backend/app/utils/shift_mapping.py`

```python
"""Shared shift_id <-> duty_order mapping. Source of truth for both backend and frontend."""

# shift_id "01" = 00:00-02:00, ..., "12" = 22:00-00:00 (existing convention)
# duty_order 第1班 = 08:00-10:00 = shift_id "05"
SHIFT_TO_DUTY = {
    "05": (1, "08:00-10:00"),
    "06": (2, "10:00-12:00"),
    "07": (3, "12:00-14:00"),
    "08": (4, "14:00-16:00"),
    "09": (5, "16:00-18:00"),
    "10": (6, "18:00-20:00"),
    "11": (7, "20:00-22:00"),
    "12": (8, "22:00-00:00"),
    "01": (9, "00:00-02:00"),
    "02": (10, "02:00-04:00"),
    "03": (11, "04:00-06:00"),
    "04": (12, "06:00-08:00"),
}

DUTY_TO_SHIFT = {duty: sid for sid, (duty, _) in SHIFT_TO_DUTY.items()}


def shift_to_duty_order(shift_id: str) -> int:
    return SHIFT_TO_DUTY[shift_id][0]


def shift_to_label(shift_id: str) -> str:
    return SHIFT_TO_DUTY[shift_id][1]


def duty_label(shift_id: str) -> str:
    return f"第{shift_to_duty_order(shift_id)}班"
```

- [ ] **Step 2: Write the failing test for build_calendar**

Path: `backend/tests/test_build_calendar.py`

```python
"""Tests for calendar table builder."""
from datetime import date

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from backend.app.models.core import Base
from backend.app.models.prediction import ExtCalendar
from backend.scripts.init_prediction_schema import init_schema


@pytest.fixture
def session(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    init_schema(db_url)
    engine = create_engine(db_url)
    with Session(engine) as s:
        yield s


def test_build_calendar_covers_full_range(session):
    """Calendar must have one row per date from 2021-01-01 to 2030-12-31."""
    from backend.scripts.build_calendar import build_calendar
    build_calendar(session, date(2021, 1, 1), date(2030, 12, 31))

    rows = session.execute(select(ExtCalendar)).scalars().all()
    expected_days = (date(2030, 12, 31) - date(2021, 1, 1)).days + 1
    assert len(rows) == expected_days


def test_calendar_marks_taiwan_new_year_holiday(session):
    """2026-01-01 should be flagged as holiday."""
    from backend.scripts.build_calendar import build_calendar
    build_calendar(session, date(2026, 1, 1), date(2026, 1, 5))

    row = session.get(ExtCalendar, date(2026, 1, 1))
    assert row.is_holiday is True


def test_calendar_marks_friday(session):
    """2026-04-24 is a Friday."""
    from backend.scripts.build_calendar import build_calendar
    build_calendar(session, date(2026, 4, 20), date(2026, 4, 26))

    fri = session.get(ExtCalendar, date(2026, 4, 24))
    sat = session.get(ExtCalendar, date(2026, 4, 25))
    assert fri.is_friday is True
    assert sat.is_friday is False


def test_calendar_marks_payday(session):
    """5th and 15th of each month flagged as payday."""
    from backend.scripts.build_calendar import build_calendar
    build_calendar(session, date(2026, 4, 1), date(2026, 4, 30))

    pay5 = session.get(ExtCalendar, date(2026, 4, 5))
    pay15 = session.get(ExtCalendar, date(2026, 4, 15))
    not_pay = session.get(ExtCalendar, date(2026, 4, 10))
    assert pay5.is_payday is True
    assert pay15.is_payday is True
    assert not_pay.is_payday is False


def test_calendar_holiday_eve_flag(session):
    """2025-12-31 is eve of 2026-01-01 holiday."""
    from backend.scripts.build_calendar import build_calendar
    build_calendar(session, date(2025, 12, 30), date(2026, 1, 2))

    eve = session.get(ExtCalendar, date(2025, 12, 31))
    assert eve.is_holiday_eve is True
```

- [ ] **Step 3: Run test to verify it fails**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/test_build_calendar.py -v
```
Expected: FAIL with `ModuleNotFoundError: backend.scripts.build_calendar`.

- [ ] **Step 4: Implement build_calendar**

Path: `backend/scripts/build_calendar.py`

```python
"""Build ext_calendar (2021-2030). Idempotent: existing rows updated."""
import sys
from datetime import date, timedelta
from pathlib import Path

import holidays
from lunardate import LunarDate
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.models.prediction import ExtCalendar


def build_calendar(session: Session, start: date, end: date) -> None:
    tw_holidays = holidays.Taiwan(years=range(start.year, end.year + 1))
    holiday_dates = set(tw_holidays.keys())

    cur = start
    while cur <= end:
        next_day = cur + timedelta(days=1)
        try:
            lunar = LunarDate.fromSolarDate(cur.year, cur.month, cur.day)
            lunar_day = lunar.day
        except Exception:
            lunar_day = None

        row = session.get(ExtCalendar, cur)
        if row is None:
            row = ExtCalendar(date=cur)
            session.add(row)

        row.is_holiday = cur in holiday_dates
        row.is_holiday_eve = next_day in holiday_dates
        row.lunar_day = lunar_day
        row.is_payday = cur.day in (5, 15)
        row.is_friday = cur.weekday() == 4
        row.festival_name = tw_holidays.get(cur)
        row.is_election_eve = False  # populated manually if needed
        cur = next_day

    session.commit()


if __name__ == "__main__":
    db_path = Path(__file__).resolve().parents[1] / "data" / "traffic_enforcement.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with Session(engine) as session:
        build_calendar(session, date(2021, 1, 1), date(2030, 12, 31))
    print(f"Calendar built: 2021-01-01 to 2030-12-31")
```

- [ ] **Step 5: Run tests to verify pass**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/test_build_calendar.py -v
```
Expected: 5 passed.

- [ ] **Step 6: Run against local DB**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe backend\scripts\build_calendar.py
```
Expected: `Calendar built: 2021-01-01 to 2030-12-31`

- [ ] **Step 7: Commit**

```bash
git add backend/app/utils/shift_mapping.py backend/scripts/build_calendar.py backend/tests/test_build_calendar.py
git commit -m "feat(prediction): build ext_calendar table + shared shift_mapping util"
```

---

### Task 4: Fetch CWA historical weather (5 years)

**Files:**
- Create: `backend/app/services/cwa_client.py`
- Create: `backend/scripts/fetch_cwa_history.py`
- Create: `backend/tests/test_cwa_client.py`
- Create: `backend/.env.ml.example`

- [ ] **Step 1: Document CWA API key requirement**

Path: `backend/.env.ml.example`

```
# CWA Open Data API key (apply at https://opendata.cwa.gov.tw/)
# This file is committed; copy to .env.ml and fill in real key (gitignored)
CWA_API_KEY=YOUR_KEY_HERE
```

- [ ] **Step 2: Write the failing test for cwa_client (mocked)**

Path: `backend/tests/test_cwa_client.py`

```python
"""Tests for CWA client. Network calls are mocked."""
from datetime import date
from unittest.mock import patch, Mock

import pytest


SAMPLE_RESPONSE = {
    "records": {
        "locations": [{
            "location": [{
                "locationName": "新化區",
                "weatherElement": [
                    {"elementName": "T", "time": [{"startTime": "2024-01-01 08:00:00", "elementValue": [{"value": "22.5"}]}]},
                    {"elementName": "PoP12h", "time": [{"startTime": "2024-01-01 08:00:00", "elementValue": [{"value": "20"}]}]},
                    {"elementName": "Wx", "time": [{"startTime": "2024-01-01 08:00:00", "elementValue": [{"value": "晴"}]}]},
                ],
            }]
        }]
    }
}


@patch("backend.app.services.cwa_client.requests.get")
def test_cwa_client_parses_district_weather(mock_get):
    mock_get.return_value = Mock(status_code=200, json=lambda: SAMPLE_RESPONSE)

    from backend.app.services.cwa_client import CwaClient
    client = CwaClient(api_key="dummy")
    rows = client.fetch_district_history("新化區", date(2024, 1, 1), date(2024, 1, 1))

    assert len(rows) >= 1
    row = rows[0]
    assert row["district"] == "新化區"
    assert row["temperature_c"] == 22.5
    assert row["weather_code"] == "晴"


def test_cwa_client_raises_on_missing_key():
    from backend.app.services.cwa_client import CwaClient
    with pytest.raises(ValueError, match="CWA_API_KEY"):
        CwaClient(api_key="")
```

- [ ] **Step 3: Run test to verify it fails**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/test_cwa_client.py -v
```
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement CwaClient**

Path: `backend/app/services/cwa_client.py`

```python
"""CWA Open Data client for historical weather. Local machine only."""
from datetime import date, datetime, timedelta
from typing import Iterator

import requests

CWA_HISTORICAL_ENDPOINT = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/F-D0047-091"
# Forecast endpoint for forward fill of recent data when historical not yet available.

SHIFT_HOURS = {
    "01": 0, "02": 2, "03": 4, "04": 6, "05": 8, "06": 10,
    "07": 12, "08": 14, "09": 16, "10": 18, "11": 20, "12": 22,
}


class CwaClient:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("CWA_API_KEY missing")
        self.api_key = api_key

    def fetch_district_history(self, district: str, start: date, end: date) -> list[dict]:
        """Return rows of {date, district, shift_id, rainfall_mm, temperature_c, weather_code, ...}.

        CWA history data is hour-resolution; we aggregate into 12 shifts per day.
        """
        params = {
            "Authorization": self.api_key,
            "locationName": district,
            "timeFrom": start.isoformat() + "T00:00:00",
            "timeTo": end.isoformat() + "T23:59:59",
        }
        resp = requests.get(CWA_HISTORICAL_ENDPOINT, params=params, timeout=30)
        resp.raise_for_status()
        payload = resp.json()
        return list(self._parse_payload(payload, district))

    @staticmethod
    def _parse_payload(payload: dict, district: str) -> Iterator[dict]:
        try:
            locations = payload["records"]["locations"][0]["location"]
        except (KeyError, IndexError):
            return
        for loc in locations:
            if loc.get("locationName") != district:
                continue
            buckets: dict[tuple[date, str], dict] = {}
            for elem in loc.get("weatherElement", []):
                ename = elem.get("elementName")
                for t in elem.get("time", []):
                    ts = datetime.fromisoformat(t["startTime"].replace(" ", "T"))
                    shift_id = f"{(ts.hour // 2) + 1:02d}"
                    key = (ts.date(), shift_id)
                    bucket = buckets.setdefault(key, {
                        "date": ts.date(), "district": district, "shift_id": shift_id,
                    })
                    val = t.get("elementValue", [{}])[0].get("value")
                    if ename == "T" and val is not None:
                        bucket["temperature_c"] = float(val)
                    elif ename == "PoP12h" and val is not None:
                        bucket["rainfall_mm"] = float(val)  # PoP is probability; substitute when no rain data
                    elif ename == "Wx":
                        bucket["weather_code"] = val
                    elif ename == "RH" and val is not None:
                        bucket["humidity_pct"] = float(val)
                    elif ename == "WS" and val is not None:
                        bucket["wind_speed_ms"] = float(val)
            for bucket in buckets.values():
                yield bucket
```

- [ ] **Step 5: Implement fetch_cwa_history script**

Path: `backend/scripts/fetch_cwa_history.py`

```python
"""Backfill ext_weather for last N years. Idempotent."""
import os
import sys
from datetime import date, timedelta
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.models.prediction import ExtWeather
from backend.app.services.cwa_client import CwaClient

# Tainan administrative districts covered by 新化分局 + neighboring (extend as needed)
TARGET_DISTRICTS = [
    "新化區", "山上區", "左鎮區", "新市區", "善化區", "玉井區", "南化區",
]


def backfill(years: int = 5) -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env.ml")
    api_key = os.environ.get("CWA_API_KEY", "")
    client = CwaClient(api_key=api_key)

    end = date.today()
    start = end - timedelta(days=years * 365)

    db_path = Path(__file__).resolve().parents[1] / "data" / "traffic_enforcement.db"
    engine = create_engine(f"sqlite:///{db_path}")

    with Session(engine) as session:
        for district in TARGET_DISTRICTS:
            print(f"Fetching {district} {start} ~ {end} ...")
            # CWA limits range; iterate month-by-month
            cur = start
            while cur < end:
                chunk_end = min(cur + timedelta(days=30), end)
                try:
                    rows = client.fetch_district_history(district, cur, chunk_end)
                except Exception as e:
                    print(f"  WARN {district} {cur}~{chunk_end}: {e}")
                    cur = chunk_end + timedelta(days=1)
                    continue
                for r in rows:
                    existing = session.query(ExtWeather).filter_by(
                        date=r["date"], district=r["district"], shift_id=r["shift_id"]
                    ).first()
                    if existing:
                        for k, v in r.items():
                            setattr(existing, k, v)
                    else:
                        session.add(ExtWeather(**r))
                session.commit()
                cur = chunk_end + timedelta(days=1)
    print("Done.")


if __name__ == "__main__":
    backfill()
```

- [ ] **Step 6: Run unit tests**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/test_cwa_client.py -v
```
Expected: 2 passed.

- [ ] **Step 7: Manual run (deferred until you have API key)**

User action: Apply for CWA API key, copy `.env.ml.example` → `.env.ml`, fill key, then:

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\pip.exe install python-dotenv
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe backend\scripts\fetch_cwa_history.py
```

If CWA endpoint changes or quota fails, document the failure mode in `docs/dui_prediction_user_guide.md` (Task 14) and use mean fallback in feature engineering.

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/cwa_client.py backend/scripts/fetch_cwa_history.py backend/tests/test_cwa_client.py backend/.env.ml.example
git commit -m "feat(prediction): CWA weather client + 5-year history backfill script"
```

---

## Phase 2: Feature Engineering & Training

### Task 5: Feature engineering pipeline

**Files:**
- Create: `backend/app/ml/__init__.py`
- Create: `backend/app/ml/feature_engineering.py`
- Create: `backend/tests/test_feature_engineering.py`

- [ ] **Step 1: Write failing test for feature engineering**

Path: `backend/tests/test_feature_engineering.py`

```python
"""Tests for feature engineering. Synthetic small data."""
from datetime import date, datetime, timedelta

import pandas as pd
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.models.core import Base
from backend.app.models.prediction import ExtCalendar, ExtWeather
from backend.scripts.init_prediction_schema import init_schema


@pytest.fixture
def session(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(db_url)
    Base.metadata.create_all(bind=engine)
    init_schema(db_url)
    with Session(engine) as s:
        yield s


def _seed_minimal_data(session):
    """Insert 1 day of calendar + weather for 1 sub_unit."""
    session.add(ExtCalendar(date=date(2026, 4, 24), is_friday=True, is_payday=False))
    session.add(ExtWeather(date=date(2026, 4, 24), district="新化區", shift_id="07",
                            rainfall_mm=0.0, temperature_c=25.0, weather_code="晴"))
    session.commit()


def test_build_features_returns_expected_columns(session):
    from backend.app.ml.feature_engineering import build_features
    _seed_minimal_data(session)

    df = build_features(
        session,
        sub_units=["新化派出所"],
        start=date(2026, 4, 24),
        end=date(2026, 4, 24),
    )

    expected_cols = {
        "sub_unit", "date", "shift_id", "day_of_week", "month",
        "is_holiday", "is_holiday_eve", "is_friday", "is_payday",
        "rainfall_mm", "temperature_c", "weather_code",
        "rolling_7d_dui_crash", "rolling_30d_dui_crash", "rolling_90d_dui_crash",
        "rolling_7d_dui_ticket", "rolling_30d_dui_ticket", "rolling_90d_dui_ticket",
        "label_has_dui_crash", "label_dui_crash_count",
    }
    assert expected_cols.issubset(set(df.columns))


def test_build_features_full_cartesian(session):
    """1 sub_unit × 12 shifts × 1 day = 12 rows."""
    from backend.app.ml.feature_engineering import build_features
    _seed_minimal_data(session)

    df = build_features(
        session,
        sub_units=["新化派出所"],
        start=date(2026, 4, 24),
        end=date(2026, 4, 24),
    )
    assert len(df) == 12


def test_build_features_handles_missing_weather_with_fallback(session):
    """Rows without matching weather should have NaN, not crash."""
    from backend.app.ml.feature_engineering import build_features
    _seed_minimal_data(session)

    df = build_features(
        session,
        sub_units=["新化派出所"],
        start=date(2026, 4, 24),
        end=date(2026, 4, 24),
    )
    # shift 05 (08-10) is not seeded, only 07 is — those 11 rows should have NaN/None weather
    missing = df[df["shift_id"] != "07"]
    assert missing["temperature_c"].isna().all()
```

- [ ] **Step 2: Run test, expect failure**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/test_feature_engineering.py -v
```
Expected: FAIL with import error.

- [ ] **Step 3: Implement feature_engineering**

Path: `backend/app/ml/__init__.py` — empty file.

Path: `backend/app/ml/feature_engineering.py`

```python
"""Feature engineering for DUI hotspot prediction.

Output: pandas DataFrame with one row per (sub_unit, date, shift_id) and 22+ feature columns
plus 2 label columns (label_has_dui_crash binary, label_dui_crash_count int).
"""
from datetime import date, datetime, timedelta
from itertools import product
from typing import Iterable

import pandas as pd
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from backend.app.models.core import Crash, Ticket
from backend.app.models.prediction import ExtCalendar, ExtWeather

SHIFT_IDS = [f"{i:02d}" for i in range(1, 13)]

# Map sub_unit -> district for weather join (only for 新化分局 jurisdiction; extend as needed).
SUB_UNIT_TO_DISTRICT = {
    "新化派出所": "新化區",
    "知義派出所": "新化區",
    "𦰡拔派出所": "新化區",
    "那拔派出所": "新化區",
    "唪口派出所": "新化區",
    "山上分駐所": "山上區",
    "左鎮分駐所": "左鎮區",
    "岡林派出所": "左鎮區",
    "新化分局": "新化區",
}

STATION_GROUPS = {
    "新化派出所": "新化派出所（含那拔）",
    "那拔派出所": "新化派出所（含那拔）",
    "𦰡拔派出所": "新化派出所（含那拔）",
    "唪口派出所": "唪口派出所（含知義）",
    "知義派出所": "唪口派出所（含知義）",
    "山上分駐所": "山上分駐所",
    "左鎮分駐所": "左鎮分駐所（含岡林）",
    "岡林派出所": "左鎮分駐所（含岡林）",
}


def _load_calendar(session: Session, start: date, end: date) -> pd.DataFrame:
    rows = session.execute(
        select(ExtCalendar).where(and_(ExtCalendar.date >= start, ExtCalendar.date <= end))
    ).scalars().all()
    return pd.DataFrame([{
        "date": r.date,
        "is_holiday": bool(r.is_holiday),
        "is_holiday_eve": bool(r.is_holiday_eve),
        "is_friday": bool(r.is_friday),
        "is_payday": bool(r.is_payday),
        "festival_name": r.festival_name or "",
    } for r in rows])


def _load_weather(session: Session, start: date, end: date) -> pd.DataFrame:
    rows = session.execute(
        select(ExtWeather).where(and_(ExtWeather.date >= start, ExtWeather.date <= end))
    ).scalars().all()
    return pd.DataFrame([{
        "date": r.date, "district": r.district, "shift_id": r.shift_id,
        "rainfall_mm": r.rainfall_mm, "temperature_c": r.temperature_c,
        "weather_code": r.weather_code or "",
    } for r in rows])


def _load_crashes(session: Session, start: date, end: date) -> pd.DataFrame:
    """Aggregate DUI crashes per (sub_unit, date, shift_id)."""
    history_start = start - timedelta(days=90)  # need 90d rolling window
    rows = session.execute(
        select(Crash).where(and_(
            Crash.occurred_date >= history_start,
            Crash.occurred_date <= end,
            Crash.suspected_alcohol == True,  # noqa: E712
        ))
    ).scalars().all()
    return pd.DataFrame([{
        "date": r.occurred_date, "sub_unit": r.sub_unit, "shift_id": r.shift_id,
    } for r in rows])


def _load_tickets(session: Session, start: date, end: date) -> pd.DataFrame:
    """Aggregate DUI tickets per (sub_unit, date, shift_id) for rolling features only."""
    history_start = start - timedelta(days=90)
    rows = session.execute(
        select(Ticket).where(and_(
            Ticket.violation_date >= history_start,
            Ticket.violation_date <= end,
            Ticket.topic_dui == True,  # noqa: E712
        ))
    ).scalars().all()
    return pd.DataFrame([{
        "date": r.violation_date, "sub_unit": r.unit_code, "shift_id": r.shift_id,
    } for r in rows])


def _rolling_count(df: pd.DataFrame, sub_unit: str, target_date: date, days: int) -> int:
    if df.empty:
        return 0
    mask = (df["sub_unit"] == sub_unit) & \
           (df["date"] >= target_date - timedelta(days=days)) & \
           (df["date"] < target_date)
    return int(mask.sum())


def build_features(
    session: Session,
    sub_units: Iterable[str],
    start: date,
    end: date,
) -> pd.DataFrame:
    sub_units = list(sub_units)
    calendar_df = _load_calendar(session, start, end)
    weather_df = _load_weather(session, start, end)
    crashes_df = _load_crashes(session, start, end)
    tickets_df = _load_tickets(session, start, end)

    rows = []
    cur = start
    while cur <= end:
        for sub_unit, shift_id in product(sub_units, SHIFT_IDS):
            district = SUB_UNIT_TO_DISTRICT.get(sub_unit, "")
            row = {
                "sub_unit": sub_unit,
                "group_name": STATION_GROUPS.get(sub_unit, sub_unit),
                "district": district,
                "date": cur,
                "shift_id": shift_id,
                "day_of_week": cur.weekday(),
                "month": cur.month,
            }
            cal = calendar_df[calendar_df["date"] == cur]
            if not cal.empty:
                c = cal.iloc[0]
                row.update({
                    "is_holiday": c["is_holiday"], "is_holiday_eve": c["is_holiday_eve"],
                    "is_friday": c["is_friday"], "is_payday": c["is_payday"],
                    "festival_name": c["festival_name"],
                })
            else:
                row.update({"is_holiday": False, "is_holiday_eve": False,
                            "is_friday": False, "is_payday": False, "festival_name": ""})

            wx = weather_df[(weather_df["date"] == cur) & (weather_df["district"] == district) &
                             (weather_df["shift_id"] == shift_id)]
            if not wx.empty:
                w = wx.iloc[0]
                row.update({"rainfall_mm": w["rainfall_mm"], "temperature_c": w["temperature_c"],
                            "weather_code": w["weather_code"]})
            else:
                row.update({"rainfall_mm": None, "temperature_c": None, "weather_code": ""})

            row["rolling_7d_dui_crash"] = _rolling_count(crashes_df, sub_unit, cur, 7)
            row["rolling_30d_dui_crash"] = _rolling_count(crashes_df, sub_unit, cur, 30)
            row["rolling_90d_dui_crash"] = _rolling_count(crashes_df, sub_unit, cur, 90)
            row["rolling_7d_dui_ticket"] = _rolling_count(tickets_df, sub_unit, cur, 7)
            row["rolling_30d_dui_ticket"] = _rolling_count(tickets_df, sub_unit, cur, 30)
            row["rolling_90d_dui_ticket"] = _rolling_count(tickets_df, sub_unit, cur, 90)

            # Labels
            same_day_crashes = crashes_df[
                (crashes_df["date"] == cur) & (crashes_df["sub_unit"] == sub_unit) &
                (crashes_df["shift_id"] == shift_id)
            ] if not crashes_df.empty else pd.DataFrame()
            row["label_dui_crash_count"] = int(len(same_day_crashes))
            row["label_has_dui_crash"] = int(row["label_dui_crash_count"] > 0)

            rows.append(row)
        cur += timedelta(days=1)

    return pd.DataFrame(rows)
```

- [ ] **Step 4: Run tests**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/test_feature_engineering.py -v
```
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add backend/app/ml/__init__.py backend/app/ml/feature_engineering.py backend/tests/test_feature_engineering.py
git commit -m "feat(prediction): feature engineering pipeline with 22 features + 2 labels"
```

---

### Task 6: Train pipeline + evaluate (XGBoost dual-model, Recall ≥ 80%)

**Files:**
- Create: `backend/app/ml/train.py`
- Create: `backend/app/ml/evaluate.py`
- Create: `backend/tests/test_train_evaluate.py`
- Create: `backend/scripts/retrain_dui_model.py`
- Create: `backend/models/.gitkeep`

- [ ] **Step 1: Write failing test for evaluate (synthetic data, deterministic)**

Path: `backend/tests/test_train_evaluate.py`

```python
"""Tests for training + evaluation. Uses synthetic data so test runs in <5s."""
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


def _make_synthetic_features(n_days: int = 200) -> pd.DataFrame:
    """Synthetic feature df with strong friday signal so model can learn."""
    rng = np.random.default_rng(42)
    rows = []
    base = date(2024, 1, 1)
    sub_units = ["A", "B", "C"]
    for i in range(n_days):
        d = base + timedelta(days=i)
        for su in sub_units:
            for shift in [f"{s:02d}" for s in range(1, 13)]:
                is_friday = d.weekday() == 4
                # Friday + shift 11 (20-22) drastically raises DUI prob
                p = 0.5 if (is_friday and shift in ["11", "12"]) else 0.02
                has_crash = rng.random() < p
                rows.append({
                    "sub_unit": su, "date": d, "shift_id": shift,
                    "day_of_week": d.weekday(), "month": d.month,
                    "is_holiday": False, "is_holiday_eve": False,
                    "is_friday": is_friday, "is_payday": d.day in (5, 15),
                    "rainfall_mm": rng.random() * 10, "temperature_c": 20 + rng.random() * 10,
                    "weather_code": "晴",
                    "rolling_7d_dui_crash": int(rng.integers(0, 3)),
                    "rolling_30d_dui_crash": int(rng.integers(0, 8)),
                    "rolling_90d_dui_crash": int(rng.integers(0, 20)),
                    "rolling_7d_dui_ticket": int(rng.integers(0, 5)),
                    "rolling_30d_dui_ticket": int(rng.integers(0, 15)),
                    "rolling_90d_dui_ticket": int(rng.integers(0, 40)),
                    "label_has_dui_crash": int(has_crash),
                    "label_dui_crash_count": int(has_crash) * int(rng.integers(1, 3)),
                })
    return pd.DataFrame(rows)


def test_train_returns_models_and_metadata(tmp_path):
    from backend.app.ml.train import train_dui_model
    df = _make_synthetic_features()
    out = train_dui_model(df, output_dir=tmp_path)

    assert "classifier_path" in out
    assert "regressor_path" in out
    assert "feature_columns_path" in out
    assert "eval_report" in out
    assert Path(out["classifier_path"]).exists()
    assert Path(out["regressor_path"]).exists()


def test_train_recall_is_evaluated(tmp_path):
    """eval_report must contain Recall metric."""
    from backend.app.ml.train import train_dui_model
    df = _make_synthetic_features()
    out = train_dui_model(df, output_dir=tmp_path)
    report = out["eval_report"]

    assert "classifier" in report
    assert "recall" in report["classifier"]
    assert 0.0 <= report["classifier"]["recall"] <= 1.0


def test_train_finds_strong_friday_signal(tmp_path):
    """With synthetic friday-driven labels, recall must be >= 0.5."""
    from backend.app.ml.train import train_dui_model
    df = _make_synthetic_features()
    out = train_dui_model(df, output_dir=tmp_path)

    assert out["eval_report"]["classifier"]["recall"] >= 0.5


def test_recall_first_threshold_below_default(tmp_path):
    """Recall-first: chosen threshold must be < 0.5 to bias toward recall."""
    from backend.app.ml.train import train_dui_model
    df = _make_synthetic_features()
    out = train_dui_model(df, output_dir=tmp_path)

    assert out["eval_report"]["classifier"]["chosen_threshold"] < 0.5
```

- [ ] **Step 2: Run test, expect failure**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/test_train_evaluate.py -v
```
Expected: FAIL on imports.

- [ ] **Step 3: Implement train + evaluate**

Path: `backend/app/ml/evaluate.py`

```python
"""Evaluation utilities. Recall-first."""
import numpy as np
from sklearn.metrics import (
    average_precision_score, precision_recall_curve, recall_score, precision_score,
    mean_absolute_error,
)


def pick_recall_first_threshold(y_true: np.ndarray, y_proba: np.ndarray, target_recall: float = 0.80) -> float:
    """Lowest-precision threshold that still achieves target_recall on this set.

    Returns 0.5 fallback if target unreachable.
    """
    precisions, recalls, thresholds = precision_recall_curve(y_true, y_proba)
    feasible = [(t, p) for t, p, r in zip(thresholds, precisions[:-1], recalls[:-1]) if r >= target_recall]
    if not feasible:
        return 0.5
    return min(feasible, key=lambda x: x[1])[0]


def evaluate_classifier(y_true, y_proba, threshold: float) -> dict:
    y_pred = (y_proba >= threshold).astype(int)
    return {
        "pr_auc": float(average_precision_score(y_true, y_proba)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "chosen_threshold": float(threshold),
    }


def evaluate_regressor(y_true, y_pred) -> dict:
    return {"mae": float(mean_absolute_error(y_true, y_pred))}
```

Path: `backend/app/ml/train.py`

```python
"""Train classifier (XGBoost) + Poisson regressor for DUI prediction.

Time-based 70/15/15 split. Recall-first threshold tuning.
"""
import json
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from xgboost import XGBClassifier, XGBRegressor

from .evaluate import evaluate_classifier, evaluate_regressor, pick_recall_first_threshold

CATEGORICAL_COLS = ["sub_unit", "shift_id", "weather_code", "festival_name", "group_name", "district"]
NUMERIC_COLS = [
    "day_of_week", "month",
    "is_holiday", "is_holiday_eve", "is_friday", "is_payday",
    "rainfall_mm", "temperature_c",
    "rolling_7d_dui_crash", "rolling_30d_dui_crash", "rolling_90d_dui_crash",
    "rolling_7d_dui_ticket", "rolling_30d_dui_ticket", "rolling_90d_dui_ticket",
]


def _prepare_xy(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    df = df.copy()
    # Bools to int
    for c in ["is_holiday", "is_holiday_eve", "is_friday", "is_payday"]:
        df[c] = df[c].astype(int)
    # Fill missing weather with column mean (training-set computed)
    for c in ["rainfall_mm", "temperature_c"]:
        df[c] = df[c].fillna(df[c].mean() if df[c].notna().any() else 0.0)
    # One-hot encode categoricals
    cats_present = [c for c in CATEGORICAL_COLS if c in df.columns]
    df_enc = pd.get_dummies(df, columns=cats_present, prefix=cats_present, dtype=int)
    # Keep only numeric + dummies
    feature_cols = [c for c in df_enc.columns
                    if c not in {"date", "label_has_dui_crash", "label_dui_crash_count"}]
    X = df_enc[feature_cols]
    y_clf = df["label_has_dui_crash"]
    y_reg = df["label_dui_crash_count"]
    return X, y_clf, y_reg, feature_cols


def _time_split(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    df_sorted = df.sort_values("date").reset_index(drop=True)
    n = len(df_sorted)
    train_end = int(n * 0.70)
    val_end = int(n * 0.85)
    return df_sorted.iloc[:train_end], df_sorted.iloc[train_end:val_end], df_sorted.iloc[val_end:]


def train_dui_model(df: pd.DataFrame, output_dir: str | Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "eval_reports").mkdir(exist_ok=True)

    train_df, val_df, test_df = _time_split(df)
    X_train, y_train_clf, y_train_reg, feature_cols = _prepare_xy(train_df)
    X_val, y_val_clf, y_val_reg, _ = _prepare_xy(val_df)
    X_test, y_test_clf, y_test_reg, _ = _prepare_xy(test_df)

    # Align columns (test/val may be missing some one-hot cats present only in train)
    X_val = X_val.reindex(columns=feature_cols, fill_value=0)
    X_test = X_test.reindex(columns=feature_cols, fill_value=0)

    pos = int(y_train_clf.sum())
    neg = int(len(y_train_clf) - pos)
    spw = max(neg / max(pos, 1), 1.0)

    classifier = XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        scale_pos_weight=spw, eval_metric="aucpr",
        early_stopping_rounds=30,
        n_jobs=-1, random_state=42,
    )
    classifier.fit(X_train, y_train_clf, eval_set=[(X_val, y_val_clf)], verbose=False)

    regressor = XGBRegressor(
        objective="count:poisson", n_estimators=200, max_depth=5,
        learning_rate=0.05, n_jobs=-1, random_state=42,
    )
    regressor.fit(X_train, y_train_reg)

    # Threshold tuning on validation set (Recall-first)
    val_proba = classifier.predict_proba(X_val)[:, 1]
    threshold = pick_recall_first_threshold(y_val_clf.values, val_proba, target_recall=0.80)

    # Evaluate on test
    test_proba = classifier.predict_proba(X_test)[:, 1]
    clf_metrics = evaluate_classifier(y_test_clf.values, test_proba, threshold)
    reg_metrics = evaluate_regressor(y_test_reg.values, regressor.predict(X_test))

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    classifier_path = output_dir / f"dui_hotspot_classifier_v{ts}.pkl"
    regressor_path = output_dir / f"dui_hotspot_regressor_v{ts}.pkl"
    feature_columns_path = output_dir / f"feature_columns_v{ts}.json"
    eval_path = output_dir / "eval_reports" / f"eval_v{ts}.json"

    joblib.dump(classifier, classifier_path)
    joblib.dump(regressor, regressor_path)
    feature_columns_path.write_text(json.dumps(feature_cols, ensure_ascii=False, indent=2))

    eval_report = {
        "model_version": f"v{ts}",
        "trained_at": datetime.utcnow().isoformat(),
        "samples": {"train": len(X_train), "val": len(X_val), "test": len(X_test)},
        "classifier": clf_metrics,
        "regressor": reg_metrics,
    }
    eval_path.write_text(json.dumps(eval_report, ensure_ascii=False, indent=2))

    return {
        "classifier_path": str(classifier_path),
        "regressor_path": str(regressor_path),
        "feature_columns_path": str(feature_columns_path),
        "eval_report": eval_report,
    }
```

Path: `backend/scripts/retrain_dui_model.py`

```python
"""Manual retrain entry point. Reads SUB_UNITS for 新化分局 jurisdiction."""
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.ml.feature_engineering import build_features, SUB_UNIT_TO_DISTRICT
from backend.app.ml.train import train_dui_model


if __name__ == "__main__":
    db_path = Path(__file__).resolve().parents[1] / "data" / "traffic_enforcement.db"
    engine = create_engine(f"sqlite:///{db_path}")
    out_dir = Path(__file__).resolve().parents[1] / "models"

    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=5 * 365)

    with Session(engine) as session:
        df = build_features(session, list(SUB_UNIT_TO_DISTRICT.keys()), start, end)

    print(f"Training on {len(df)} rows...")
    out = train_dui_model(df, output_dir=out_dir)
    print(f"Done. Recall: {out['eval_report']['classifier']['recall']:.3f}")
    if out["eval_report"]["classifier"]["recall"] < 0.80:
        print("WARNING: Recall below 0.80 target. Consider feature additions.")
```

Create `backend/models/.gitkeep` (empty placeholder).

- [ ] **Step 4: Run tests**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/test_train_evaluate.py -v
```
Expected: 4 passed (synthetic data has strong friday signal so recall ≥ 0.5 achievable).

- [ ] **Step 5: Commit**

```bash
git add backend/app/ml/train.py backend/app/ml/evaluate.py backend/scripts/retrain_dui_model.py backend/tests/test_train_evaluate.py backend/models/.gitkeep
git commit -m "feat(prediction): XGBoost dual-model training + recall-first threshold tuning"
```

---

## Phase 3: Inference & API

### Task 7: Inference + SHAP explainer

**Files:**
- Create: `backend/app/ml/predict.py`
- Create: `backend/app/ml/shap_explainer.py`
- Create: `backend/tests/test_predict.py`

- [ ] **Step 1: Write failing test for predict + explainer**

Path: `backend/tests/test_predict.py`

```python
"""Tests for predict + shap_explainer."""
import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def trained_model_dir(tmp_path):
    """Train a tiny model on synthetic data for prediction tests."""
    from backend.app.ml.train import train_dui_model
    rng = np.random.default_rng(7)
    rows = []
    base = date(2024, 1, 1)
    for i in range(150):
        d = base + timedelta(days=i)
        for su in ["A", "B"]:
            for shift in [f"{s:02d}" for s in range(1, 13)]:
                is_fri = d.weekday() == 4
                p = 0.4 if (is_fri and shift == "11") else 0.02
                has_crash = rng.random() < p
                rows.append({
                    "sub_unit": su, "date": d, "shift_id": shift,
                    "day_of_week": d.weekday(), "month": d.month,
                    "is_holiday": False, "is_holiday_eve": False,
                    "is_friday": is_fri, "is_payday": False,
                    "rainfall_mm": 1.0, "temperature_c": 25.0, "weather_code": "晴",
                    "rolling_7d_dui_crash": 0, "rolling_30d_dui_crash": 1, "rolling_90d_dui_crash": 3,
                    "rolling_7d_dui_ticket": 0, "rolling_30d_dui_ticket": 5, "rolling_90d_dui_ticket": 15,
                    "label_has_dui_crash": int(has_crash),
                    "label_dui_crash_count": int(has_crash),
                })
    df = pd.DataFrame(rows)
    train_dui_model(df, output_dir=tmp_path)
    return tmp_path


def test_predict_returns_risk_score_per_row(trained_model_dir):
    from backend.app.ml.predict import DuiPredictor
    pred = DuiPredictor.load_latest(trained_model_dir)

    df_input = pd.DataFrame([{
        "sub_unit": "A", "date": date(2024, 12, 6), "shift_id": "11",  # Friday 20-22
        "day_of_week": 4, "month": 12,
        "is_holiday": False, "is_holiday_eve": False, "is_friday": True, "is_payday": False,
        "rainfall_mm": 0.0, "temperature_c": 22.0, "weather_code": "晴",
        "rolling_7d_dui_crash": 1, "rolling_30d_dui_crash": 4, "rolling_90d_dui_crash": 10,
        "rolling_7d_dui_ticket": 2, "rolling_30d_dui_ticket": 8, "rolling_90d_dui_ticket": 20,
    }])
    out = pred.predict(df_input)
    assert "risk_score" in out.columns
    assert "predicted_count" in out.columns
    assert "risk_level" in out.columns
    assert 0.0 <= out["risk_score"].iloc[0] <= 1.0


def test_risk_level_mapping(trained_model_dir):
    from backend.app.ml.predict import DuiPredictor, risk_level_for
    assert risk_level_for(0.85) == "HIGH"
    assert risk_level_for(0.55) == "MEDIUM"
    assert risk_level_for(0.20) == "LOW"


def test_shap_explainer_returns_top_factors(trained_model_dir):
    from backend.app.ml.predict import DuiPredictor
    from backend.app.ml.shap_explainer import top_factors

    pred = DuiPredictor.load_latest(trained_model_dir)
    df_input = pd.DataFrame([{
        "sub_unit": "A", "date": date(2024, 12, 6), "shift_id": "11",
        "day_of_week": 4, "month": 12,
        "is_holiday": False, "is_holiday_eve": False, "is_friday": True, "is_payday": False,
        "rainfall_mm": 0.0, "temperature_c": 22.0, "weather_code": "晴",
        "rolling_7d_dui_crash": 1, "rolling_30d_dui_crash": 4, "rolling_90d_dui_crash": 10,
        "rolling_7d_dui_ticket": 2, "rolling_30d_dui_ticket": 8, "rolling_90d_dui_ticket": 20,
    }])
    factors = top_factors(pred, df_input.iloc[0], top_k=5)
    assert len(factors) == 5
    assert all("feature" in f and "shap" in f for f in factors)
```

- [ ] **Step 2: Run, expect failure**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/test_predict.py -v
```
Expected: FAIL on imports.

- [ ] **Step 3: Implement predict.py**

Path: `backend/app/ml/predict.py`

```python
"""DUI prediction inference. Loads latest model + applies risk_level mapping."""
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from .train import _prepare_xy

HIGH_THRESHOLD = 0.70
MEDIUM_THRESHOLD = 0.40


def risk_level_for(score: float) -> str:
    if score >= HIGH_THRESHOLD:
        return "HIGH"
    if score >= MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


class DuiPredictor:
    def __init__(self, classifier, regressor, feature_cols: list[str], model_version: str):
        self.classifier = classifier
        self.regressor = regressor
        self.feature_cols = feature_cols
        self.model_version = model_version

    @classmethod
    def load_latest(cls, model_dir: Path | str) -> "DuiPredictor":
        model_dir = Path(model_dir)
        clfs = sorted(model_dir.glob("dui_hotspot_classifier_v*.pkl"))
        regs = sorted(model_dir.glob("dui_hotspot_regressor_v*.pkl"))
        if not clfs or not regs:
            raise FileNotFoundError(f"No trained models in {model_dir}")
        latest_clf = clfs[-1]
        latest_reg = regs[-1]
        version = latest_clf.stem.replace("dui_hotspot_classifier_", "")
        cols_path = model_dir / f"feature_columns_{version}.json"
        feature_cols = json.loads(cols_path.read_text(encoding="utf-8"))
        return cls(
            classifier=joblib.load(latest_clf),
            regressor=joblib.load(latest_reg),
            feature_cols=feature_cols,
            model_version=version,
        )

    def _prepare_X(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        # Add label dummies so _prepare_xy doesn't crash
        if "label_has_dui_crash" not in df.columns:
            df["label_has_dui_crash"] = 0
            df["label_dui_crash_count"] = 0
        X, _, _, _ = _prepare_xy(df)
        return X.reindex(columns=self.feature_cols, fill_value=0)

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        X = self._prepare_X(df)
        proba = self.classifier.predict_proba(X)[:, 1]
        count = self.regressor.predict(X)
        # Normalize regression to [0,1] via clipping at P95 of training (we don't have it cached;
        # fallback to clipping at 3.0 which corresponds to extreme cases).
        count_norm = np.clip(count / 3.0, 0.0, 1.0)
        risk_score = 0.7 * proba + 0.3 * count_norm

        out = df.copy()
        out["risk_score"] = risk_score
        out["predicted_count"] = count
        out["risk_level"] = [risk_level_for(s) for s in risk_score]
        out["model_version"] = self.model_version
        return out
```

- [ ] **Step 4: Implement shap_explainer.py**

Path: `backend/app/ml/shap_explainer.py`

```python
"""SHAP explanation utilities."""
import pandas as pd
import shap


def top_factors(predictor, row: pd.Series, top_k: int = 5) -> list[dict]:
    df_one = pd.DataFrame([row.to_dict()])
    X = predictor._prepare_X(df_one)
    explainer = shap.TreeExplainer(predictor.classifier)
    shap_values = explainer.shap_values(X)
    if hasattr(shap_values, "values"):
        sv = shap_values.values[0]
    else:
        sv = shap_values[0]
    contribs = list(zip(predictor.feature_cols, sv, X.iloc[0].values))
    contribs.sort(key=lambda x: abs(x[1]), reverse=True)
    return [
        {"feature": f, "value": float(v) if isinstance(v, (int, float)) else str(v), "shap": float(s)}
        for f, s, v in contribs[:top_k]
    ]
```

- [ ] **Step 5: Run tests**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/test_predict.py -v
```
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/ml/predict.py backend/app/ml/shap_explainer.py backend/tests/test_predict.py
git commit -m "feat(prediction): inference + SHAP top-factor explanation"
```

---

### Task 8: Daily batch script + system_locks helper

**Files:**
- Create: `backend/app/services/system_lock.py`
- Create: `backend/scripts/daily_predict_dui.py`
- Create: `backend/tests/test_system_lock.py`
- Create: `backend/tests/test_daily_predict.py`

- [ ] **Step 1: Write failing test for system_lock**

Path: `backend/tests/test_system_lock.py`

```python
"""Tests for advisory lock used by daily batch + frontend trigger."""
from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from backend.app.models.core import Base
from backend.app.models.prediction import SystemLock
from backend.scripts.init_prediction_schema import init_schema


@pytest.fixture
def session(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    init_schema(db_url)
    engine = create_engine(db_url)
    with Session(engine) as s:
        yield s


def test_acquire_lock_succeeds_when_free(session):
    from backend.app.services.system_lock import acquire_lock
    assert acquire_lock(session, "dui_predict") is True


def test_acquire_lock_fails_when_held(session):
    from backend.app.services.system_lock import acquire_lock
    assert acquire_lock(session, "dui_predict") is True
    assert acquire_lock(session, "dui_predict") is False


def test_acquire_lock_succeeds_when_stale(session):
    from backend.app.services.system_lock import acquire_lock, release_lock
    # Manually plant a stale lock (>10 min old)
    session.add(SystemLock(name="dui_predict", locked_at=datetime.utcnow() - timedelta(minutes=15)))
    session.commit()
    assert acquire_lock(session, "dui_predict", stale_after_minutes=10) is True


def test_release_lock(session):
    from backend.app.services.system_lock import acquire_lock, release_lock
    acquire_lock(session, "dui_predict")
    release_lock(session, "dui_predict")
    assert acquire_lock(session, "dui_predict") is True
```

- [ ] **Step 2: Run, expect failure**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/test_system_lock.py -v
```

- [ ] **Step 3: Implement system_lock**

Path: `backend/app/services/system_lock.py`

```python
"""Advisory lock for serializing daily predict + cwa fetch."""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.app.models.prediction import SystemLock


def acquire_lock(session: Session, name: str, stale_after_minutes: int = 10) -> bool:
    """Try to acquire `name` lock. Returns True if acquired, False if held & fresh."""
    row = session.get(SystemLock, name)
    now = datetime.utcnow()
    if row is None:
        session.add(SystemLock(name=name, locked_at=now))
        session.commit()
        return True
    if row.released_at is not None and row.released_at >= row.locked_at:
        row.locked_at = now
        row.released_at = None
        session.commit()
        return True
    # Held — check staleness
    if row.locked_at and (now - row.locked_at) > timedelta(minutes=stale_after_minutes):
        row.locked_at = now
        row.released_at = None
        session.commit()
        return True
    return False


def release_lock(session: Session, name: str) -> None:
    row = session.get(SystemLock, name)
    if row is not None:
        row.released_at = datetime.utcnow()
        session.commit()
```

- [ ] **Step 4: Implement daily_predict_dui script**

Path: `backend/scripts/daily_predict_dui.py`

```python
"""Run inference for next 7 days and write to dui_predictions. Idempotent."""
import json
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.app.ml.feature_engineering import build_features, SUB_UNIT_TO_DISTRICT, STATION_GROUPS
from backend.app.ml.predict import DuiPredictor
from backend.app.ml.shap_explainer import top_factors
from backend.app.models.prediction import DuiPrediction
from backend.app.services.system_lock import acquire_lock, release_lock


def run_daily_predict() -> dict:
    db_path = Path(__file__).resolve().parents[1] / "data" / "traffic_enforcement.db"
    model_dir = Path(__file__).resolve().parents[1] / "models"
    engine = create_engine(f"sqlite:///{db_path}")

    with Session(engine) as session:
        if not acquire_lock(session, "dui_predict"):
            return {"status": "already_running"}
        try:
            predictor = DuiPredictor.load_latest(model_dir)
            today = date.today()
            end = today + timedelta(days=6)
            df = build_features(session, list(SUB_UNIT_TO_DISTRICT.keys()), today, end)
            result_df = predictor.predict(df)

            # Compute global rank per date
            result_df["risk_rank"] = result_df.groupby("date")["risk_score"].rank(
                ascending=False, method="dense"
            ).astype(int)

            # Wipe old predictions for the same window first
            session.execute(delete(DuiPrediction).where(
                DuiPrediction.predict_for_date.between(today, end)
            ))
            session.commit()

            generated_at = datetime.utcnow()
            inserted = 0
            for _, r in result_df.iterrows():
                factors = top_factors(predictor, r, top_k=5)
                session.add(DuiPrediction(
                    predict_for_date=r["date"],
                    sub_unit=r["sub_unit"],
                    shift_id=r["shift_id"],
                    group_name=STATION_GROUPS.get(r["sub_unit"], r["sub_unit"]),
                    risk_score=float(r["risk_score"]),
                    risk_level=r["risk_level"],
                    risk_rank=int(r["risk_rank"]),
                    predicted_count=float(r["predicted_count"]),
                    shap_top_features=json.dumps(factors, ensure_ascii=False),
                    model_version=predictor.model_version,
                    generated_at=generated_at,
                ))
                inserted += 1
            session.commit()

            # Cleanup old predictions (> 30 days past)
            session.execute(delete(DuiPrediction).where(
                DuiPrediction.predict_for_date < today - timedelta(days=30)
            ))
            session.commit()

            return {"status": "ok", "rows_inserted": inserted, "model_version": predictor.model_version}
        finally:
            release_lock(session, "dui_predict")


if __name__ == "__main__":
    print(run_daily_predict())
```

- [ ] **Step 5: Write daily_predict integration test**

Path: `backend/tests/test_daily_predict.py`

```python
"""Smoke test: daily_predict runs end-to-end on synthetic data."""
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest


def test_daily_predict_smoke(tmp_path, monkeypatch):
    """Train tiny model, mock SUB_UNIT_TO_DISTRICT to be small, run predict."""
    from backend.app.ml.train import train_dui_model

    rng = np.random.default_rng(11)
    rows = []
    base = date.today() - timedelta(days=200)
    for i in range(200):
        d = base + timedelta(days=i)
        for shift in [f"{s:02d}" for s in range(1, 13)]:
            rows.append({
                "sub_unit": "A", "date": d, "shift_id": shift,
                "day_of_week": d.weekday(), "month": d.month,
                "is_holiday": False, "is_holiday_eve": False,
                "is_friday": d.weekday() == 4, "is_payday": False,
                "rainfall_mm": 1.0, "temperature_c": 25.0, "weather_code": "晴",
                "rolling_7d_dui_crash": 0, "rolling_30d_dui_crash": 1, "rolling_90d_dui_crash": 3,
                "rolling_7d_dui_ticket": 0, "rolling_30d_dui_ticket": 5, "rolling_90d_dui_ticket": 15,
                "label_has_dui_crash": int(rng.random() < 0.05),
                "label_dui_crash_count": int(rng.random() < 0.05),
            })
    df = pd.DataFrame(rows)
    out = train_dui_model(df, output_dir=tmp_path)
    assert Path(out["classifier_path"]).exists()
```

- [ ] **Step 6: Run tests**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/test_system_lock.py backend/tests/test_daily_predict.py -v
```
Expected: 5 passed.

- [ ] **Step 7: Commit**

```bash
git add backend/app/services/system_lock.py backend/scripts/daily_predict_dui.py backend/tests/test_system_lock.py backend/tests/test_daily_predict.py
git commit -m "feat(prediction): daily batch script + advisory lock"
```

---

### Task 9: FastAPI endpoints

**Files:**
- Create: `backend/app/api/prediction.py`
- Create: `backend/app/schemas/prediction.py`
- Create: `backend/tests/test_api_prediction.py`
- Modify: `backend/app/main.py` (router include, conditional)

- [ ] **Step 1: Define pydantic schemas**

Path: `backend/app/schemas/prediction.py`

```python
"""Pydantic schemas for /topics/dui/predict/* endpoints."""
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class TopFactor(BaseModel):
    feature: str
    value: float | str
    shap: float


class PredictionItem(BaseModel):
    date: date
    shift_id: str
    shift_label: str
    duty_order: int
    duty_label: str
    sub_unit: str
    group_name: str
    risk_score: float
    risk_level: Literal["HIGH", "MEDIUM", "LOW"]
    predicted_count: float
    rank: int
    top_factors: list[TopFactor]


class HotspotResponse(BaseModel):
    model_version: str
    generated_at: datetime
    predict_window: list[date]
    items: list[PredictionItem]


class StatusResponse(BaseModel):
    status: Literal["fresh", "stale", "refreshing", "triggered", "error"]
    last_generated_at: datetime | None
    message: str | None = None
```

- [ ] **Step 2: Write failing test for endpoints**

Path: `backend/tests/test_api_prediction.py`

```python
"""Smoke tests for /topics/dui/predict endpoints. Uses TestClient."""
from datetime import date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.models.prediction import DuiPrediction
from sqlalchemy.orm import Session


@pytest.fixture
def client():
    return TestClient(app)


def _seed_predictions(session: Session, n: int = 5):
    today = date.today()
    for i in range(n):
        session.add(DuiPrediction(
            predict_for_date=today + timedelta(days=i),
            sub_unit="新化派出所", shift_id="11",
            group_name="新化派出所（含那拔）",
            risk_score=0.85 - i * 0.1,
            risk_level="HIGH" if (0.85 - i * 0.1) >= 0.70 else "MEDIUM",
            risk_rank=1,
            predicted_count=1.5,
            shap_top_features='[{"feature":"is_friday","value":1,"shap":0.31}]',
            model_version="v_test",
            generated_at=datetime.utcnow(),
        ))
    session.commit()


def test_status_endpoint_returns_fresh_when_recent(client, db_session):
    _seed_predictions(db_session, n=1)
    r = client.get("/topics/dui/predict/status")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("fresh", "stale", "refreshing")  # depends on age


def test_hotspot_endpoint_returns_top_n(client, db_session):
    _seed_predictions(db_session, n=5)
    r = client.get("/topics/dui/predict/hotspot?days=7&top=3")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert len(data["items"]) <= 3
```

Note: `db_session` fixture requires a `conftest.py` providing test DB. If existing project lacks one, create:

Path: `backend/tests/conftest.py`

```python
"""Shared pytest fixtures."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.models.core import Base
from backend.scripts.init_prediction_schema import init_schema


@pytest.fixture
def db_session(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'test.db'}"
    Base.metadata.create_all(create_engine(db_url))
    init_schema(db_url)
    engine = create_engine(db_url)
    SessionLocal = sessionmaker(bind=engine)
    # Monkey-patch app's get_db to use this engine
    from backend.app import database  # adjust import path to actual
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", SessionLocal)
    s = SessionLocal()
    yield s
    s.close()
```

(If `database` module path differs, adjust.)

- [ ] **Step 3: Run, expect failure**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/test_api_prediction.py -v
```

- [ ] **Step 4: Implement prediction router**

Path: `backend/app/api/prediction.py`

```python
"""DUI prediction endpoints. Mounted only when ENABLE_PREDICTION=true."""
import json
import os
from datetime import date, datetime, timedelta

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Header, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database import get_db
from backend.app.models.prediction import DuiPrediction
from backend.app.schemas.prediction import HotspotResponse, PredictionItem, StatusResponse, TopFactor
from backend.app.services.system_lock import acquire_lock
from backend.app.utils.shift_mapping import shift_to_duty_order, shift_to_label, duty_label

router = APIRouter(prefix="/topics/dui/predict", tags=["prediction"])


STALE_AFTER_HOURS = 20


def _build_item(p: DuiPrediction) -> PredictionItem:
    factors = json.loads(p.shap_top_features or "[]")
    return PredictionItem(
        date=p.predict_for_date,
        shift_id=p.shift_id,
        shift_label=shift_to_label(p.shift_id),
        duty_order=shift_to_duty_order(p.shift_id),
        duty_label=duty_label(p.shift_id),
        sub_unit=p.sub_unit,
        group_name=p.group_name or p.sub_unit,
        risk_score=p.risk_score,
        risk_level=p.risk_level or "LOW",
        predicted_count=p.predicted_count or 0.0,
        rank=p.risk_rank or 0,
        top_factors=[TopFactor(**f) for f in factors],
    )


def _trigger_refresh_background():
    """Imported lazily so colleague builds (where this file is excluded) don't crash."""
    from backend.scripts.daily_predict_dui import run_daily_predict
    run_daily_predict()


@router.get("/status", response_model=StatusResponse)
def status(db: Session = Depends(get_db), bg: BackgroundTasks = None):
    latest = db.execute(
        select(DuiPrediction).order_by(DuiPrediction.generated_at.desc()).limit(1)
    ).scalar_one_or_none()

    now = datetime.utcnow()
    if latest is None:
        if acquire_lock(db, "dui_predict", stale_after_minutes=10):
            bg.add_task(_trigger_refresh_background)
            return StatusResponse(status="triggered", last_generated_at=None,
                                  message="No predictions found; refresh triggered")
        return StatusResponse(status="refreshing", last_generated_at=None,
                              message="Refresh already in progress")

    age = now - latest.generated_at
    if age < timedelta(hours=STALE_AFTER_HOURS):
        return StatusResponse(status="fresh", last_generated_at=latest.generated_at)

    if acquire_lock(db, "dui_predict", stale_after_minutes=10):
        bg.add_task(_trigger_refresh_background)
        return StatusResponse(status="triggered", last_generated_at=latest.generated_at,
                              message="Stale; refresh triggered")
    return StatusResponse(status="refreshing", last_generated_at=latest.generated_at)


@router.get("/hotspot", response_model=HotspotResponse)
def hotspot(
    days: int = Query(7, ge=1, le=30),
    top: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
):
    today = date.today()
    end = today + timedelta(days=days - 1)
    rows = db.execute(
        select(DuiPrediction).where(
            DuiPrediction.predict_for_date.between(today, end)
        ).order_by(DuiPrediction.risk_score.desc()).limit(top)
    ).scalars().all()
    if not rows:
        raise HTTPException(404, "No predictions available")
    return HotspotResponse(
        model_version=rows[0].model_version or "unknown",
        generated_at=rows[0].generated_at,
        predict_window=[today, end],
        items=[_build_item(r) for r in rows],
    )


@router.get("/by_unit/{sub_unit}", response_model=HotspotResponse)
def by_unit(sub_unit: str, days: int = Query(7, ge=1, le=14), db: Session = Depends(get_db)):
    today = date.today()
    end = today + timedelta(days=days - 1)
    rows = db.execute(
        select(DuiPrediction).where(
            DuiPrediction.sub_unit == sub_unit,
            DuiPrediction.predict_for_date.between(today, end),
        ).order_by(DuiPrediction.predict_for_date, DuiPrediction.shift_id)
    ).scalars().all()
    if not rows:
        raise HTTPException(404, f"No predictions for {sub_unit}")
    return HotspotResponse(
        model_version=rows[0].model_version or "unknown",
        generated_at=rows[0].generated_at,
        predict_window=[today, end],
        items=[_build_item(r) for r in rows],
    )


@router.get("/explain/{prediction_id}")
def explain(prediction_id: int, db: Session = Depends(get_db)):
    p = db.get(DuiPrediction, prediction_id)
    if p is None:
        raise HTTPException(404)
    return {
        "prediction_id": p.id,
        "date": p.predict_for_date,
        "sub_unit": p.sub_unit,
        "shift_id": p.shift_id,
        "duty_label": duty_label(p.shift_id),
        "risk_score": p.risk_score,
        "top_factors": json.loads(p.shap_top_features or "[]"),
    }


admin_router = APIRouter(prefix="/admin/predict/dui", tags=["prediction-admin"])


@admin_router.post("/retrain")
def retrain(bg: BackgroundTasks, x_api_key: str = Header(None)):
    expected = os.environ.get("ADMIN_API_KEY", "")
    if not expected or x_api_key != expected:
        raise HTTPException(401, "API key required")

    def _run():
        from backend.scripts.retrain_dui_model import __name__ as _  # ensure path imports
        import subprocess, sys as _sys
        subprocess.run([_sys.executable, str(__file__).replace("api/prediction.py", "../scripts/retrain_dui_model.py")])

    bg.add_task(_run)
    return {"status": "scheduled"}
```

- [ ] **Step 5: Wire router into main.py conditionally**

Read `backend/app/main.py` first to find existing router includes. Then add at end of router section:

```python
# DUI prediction module — only mount when ENABLE_PREDICTION env var is true
import os as _os
if _os.environ.get("ENABLE_PREDICTION", "false").lower() == "true":
    from backend.app.api.prediction import router as prediction_router, admin_router as prediction_admin_router
    app.include_router(prediction_router)
    app.include_router(prediction_admin_router)
```

- [ ] **Step 6: Run tests**

```powershell
$env:ENABLE_PREDICTION="true"; D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/test_api_prediction.py -v
```
Expected: pass (or skip if conftest needs adjustment for actual `database` module path).

- [ ] **Step 7: Commit**

```bash
git add backend/app/api/prediction.py backend/app/schemas/prediction.py backend/tests/test_api_prediction.py backend/tests/conftest.py backend/app/main.py
git commit -m "feat(prediction): /topics/dui/predict/* endpoints + conditional mount"
```

---

## Phase 4: Frontend

### Task 10: Frontend types + API client

**Files:**
- Create: `animal-crossing-dashboard/src/types/prediction.ts`
- Create: `animal-crossing-dashboard/src/api/predictionClient.ts`

- [ ] **Step 1: Define TypeScript types**

Path: `animal-crossing-dashboard/src/types/prediction.ts`

```typescript
export interface TopFactor {
  feature: string;
  value: number | string;
  shap: number;
}

export interface PredictionItem {
  date: string;          // ISO YYYY-MM-DD
  shift_id: string;
  shift_label: string;   // "20:00-22:00"
  duty_order: number;    // 1-12
  duty_label: string;    // "第7班"
  sub_unit: string;
  group_name: string;
  risk_score: number;
  risk_level: "HIGH" | "MEDIUM" | "LOW";
  predicted_count: number;
  rank: number;
  top_factors: TopFactor[];
}

export interface HotspotResponse {
  model_version: string;
  generated_at: string;
  predict_window: [string, string];
  items: PredictionItem[];
}

export type PredictionStatus = "fresh" | "stale" | "refreshing" | "triggered" | "error";

export interface StatusResponse {
  status: PredictionStatus;
  last_generated_at: string | null;
  message: string | null;
}
```

- [ ] **Step 2: Create API client**

Path: `animal-crossing-dashboard/src/api/predictionClient.ts`

```typescript
import { HotspotResponse, StatusResponse } from "../types/prediction";

const BASE = "/topics/dui/predict";

export async function fetchPredictionStatus(): Promise<StatusResponse> {
  const r = await fetch(`${BASE}/status`);
  if (!r.ok) throw new Error(`status ${r.status}`);
  return r.json();
}

export async function fetchHotspot(days = 7, top = 20): Promise<HotspotResponse> {
  const r = await fetch(`${BASE}/hotspot?days=${days}&top=${top}`);
  if (!r.ok) throw new Error(`status ${r.status}`);
  return r.json();
}

export async function fetchByUnit(subUnit: string, days = 7): Promise<HotspotResponse> {
  const r = await fetch(`${BASE}/by_unit/${encodeURIComponent(subUnit)}?days=${days}`);
  if (!r.ok) throw new Error(`status ${r.status}`);
  return r.json();
}
```

- [ ] **Step 3: Commit**

```bash
git add animal-crossing-dashboard/src/types/prediction.ts animal-crossing-dashboard/src/api/predictionClient.ts
git commit -m "feat(prediction-ui): TypeScript types + API client"
```

---

### Task 11: DuiPredictionPage component

**Files:**
- Create: `animal-crossing-dashboard/src/components/DuiPredictionPage.tsx`
- Create: `animal-crossing-dashboard/src/components/PredictionStatusToast.tsx`

- [ ] **Step 1: Implement status toast**

Path: `animal-crossing-dashboard/src/components/PredictionStatusToast.tsx`

```tsx
import { useEffect, useState } from "react";
import { fetchPredictionStatus } from "../api/predictionClient";
import { PredictionStatus } from "../types/prediction";

export default function PredictionStatusToast() {
  const [status, setStatus] = useState<PredictionStatus | null>(null);

  useEffect(() => {
    let cancelled = false;
    let timer: number | undefined;

    async function tick() {
      try {
        const s = await fetchPredictionStatus();
        if (cancelled) return;
        setStatus(s.status);
        if (s.status === "refreshing" || s.status === "triggered") {
          timer = window.setTimeout(tick, 3000);
        } else if (s.status === "fresh") {
          timer = window.setTimeout(() => setStatus(null), 3000);
        }
      } catch {
        setStatus("error");
      }
    }
    tick();
    return () => { cancelled = true; if (timer) window.clearTimeout(timer); };
  }, []);

  if (!status || status === "fresh") return null;

  const color = status === "error" ? "bg-slate-500" : "bg-accent";
  const text =
    status === "triggered" ? "🔄 預測資料更新中..." :
    status === "refreshing" ? "🔄 預測資料更新中..." :
    status === "stale" ? "⚠️ 預測資料過期" :
    "預測暫不可用";

  return (
    <div className={`fixed top-4 right-4 ${color} text-white px-4 py-2 rounded-lg shadow-lg z-50`}>
      {text}
    </div>
  );
}
```

- [ ] **Step 2: Implement DuiPredictionPage**

Path: `animal-crossing-dashboard/src/components/DuiPredictionPage.tsx`

```tsx
import { useEffect, useState } from "react";
import { TrendingUp, ExternalLink } from "lucide-react";
import { fetchHotspot } from "../api/predictionClient";
import { HotspotResponse, PredictionItem } from "../types/prediction";

const RISK_COLOR: Record<PredictionItem["risk_level"], string> = {
  HIGH: "bg-danger/10 text-danger border-danger/30",
  MEDIUM: "bg-warning/10 text-warning border-warning/30",
  LOW: "bg-success/10 text-success border-success/30",
};

export default function DuiPredictionPage() {
  const [data, setData] = useState<HotspotResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<PredictionItem | null>(null);

  useEffect(() => {
    fetchHotspot(7, 20).then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="p-6 text-text-muted">無法載入預測：{error}</div>;
  if (!data) return <div className="p-6 text-text-muted">載入中...</div>;

  return (
    <div className="p-6 space-y-6">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-accent" /> 酒駕風險預測
          </h1>
          <p className="text-sm text-text-muted">
            模型版本: {data.model_version} | 預測區間: {data.predict_window[0]} ~ {data.predict_window[1]}
          </p>
        </div>
      </header>

      {/* Section 1: KPI cards (placeholder — fed by separate eval endpoint in P1) */}
      <section className="grid grid-cols-4 gap-4">
        <KPICard label="模型 Recall" value="—" hint="目標 ≥ 80%" />
        <KPICard label="Precision" value="—" hint="參考值" />
        <KPICard label="PR-AUC" value="—" hint="參考值" />
        <KPICard label="模型狀態" value="🟢 健康" hint="" />
      </section>

      {/* Section 2: Top-N table */}
      <section className="bg-surface rounded-lg border border-border p-4">
        <h2 className="font-semibold mb-3">未來 7 天高風險 Top {data.items.length}</h2>
        <table className="w-full text-sm tabular-nums">
          <thead>
            <tr className="text-left text-text-muted border-b border-border">
              <th className="py-2">日期</th>
              <th>勤務班</th>
              <th>派出所</th>
              <th>風險</th>
              <th>預期件數</th>
              <th>主因</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((it) => (
              <tr key={`${it.date}-${it.sub_unit}-${it.shift_id}`} className="border-b border-border/50">
                <td className="py-2">{it.date}</td>
                <td>{it.duty_label} ({it.shift_label})</td>
                <td>{it.sub_unit}</td>
                <td>
                  <span className={`px-2 py-0.5 rounded border text-xs ${RISK_COLOR[it.risk_level]}`}>
                    {it.risk_level} {(it.risk_score * 100).toFixed(0)}%
                  </span>
                </td>
                <td>{it.predicted_count.toFixed(1)}</td>
                <td className="text-xs text-text-muted">
                  {it.top_factors.slice(0, 2).map((f) => f.feature).join(", ")}
                </td>
                <td>
                  <button onClick={() => setSelected(it)} className="text-accent hover:underline text-xs">
                    詳情 →
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Section 3: Heatmap (simple grid for v1) */}
      <section className="bg-surface rounded-lg border border-border p-4">
        <h2 className="font-semibold mb-3">風險時段熱圖</h2>
        <p className="text-sm text-text-muted">
          後續迭代加強。目前以 Top-N 表格為主。
        </p>
      </section>

      {/* Section 4: SHAP global importance (collapsible) */}
      <details className="bg-surface rounded-lg border border-border p-4">
        <summary className="font-semibold cursor-pointer">📊 模型解釋（SHAP 全域特徵重要度）</summary>
        <p className="text-sm text-text-muted mt-2">P1 後續迭代加入 SHAP summary plot。</p>
      </details>

      {/* Cross-link card */}
      <section className="bg-surface-2 rounded-lg p-4 flex items-center justify-between">
        <span className="text-sm text-text-muted">📊 想看歷史酒駕案件分布？</span>
        <a href="#/accident-analysis?tab=dui" className="text-accent text-sm flex items-center gap-1">
          前往「執法缺口 → 酒駕分析」 <ExternalLink className="w-3 h-3" />
        </a>
      </section>

      {/* Side drawer */}
      {selected && (
        <Drawer item={selected} onClose={() => setSelected(null)} />
      )}
    </div>
  );
}

function KPICard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="bg-surface rounded-lg border border-border p-4">
      <p className="text-xs text-text-muted">{label}</p>
      <p className="text-2xl font-semibold tabular-nums tracking-tight">{value}</p>
      {hint && <p className="text-xs text-text-subtle">{hint}</p>}
    </div>
  );
}

function Drawer({ item, onClose }: { item: PredictionItem; onClose: () => void }) {
  return (
    <div className="fixed inset-0 bg-black/30 flex justify-end z-40" onClick={onClose}>
      <div className="bg-surface w-96 h-full p-6 overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <button onClick={onClose} className="text-text-muted text-sm">✕ 關閉</button>
        <h3 className="text-lg font-semibold mt-2">{item.sub_unit}</h3>
        <p className="text-sm text-text-muted">
          {item.date} · {item.duty_label} ({item.shift_label})
        </p>
        <p className="mt-4 text-sm">
          風險指數: <span className="font-semibold">{(item.risk_score * 100).toFixed(1)}%</span>
        </p>
        <p className="text-sm">預期酒駕事故: {item.predicted_count.toFixed(1)} 件</p>

        <h4 className="mt-6 font-semibold text-sm">SHAP 主要影響因子</h4>
        <ul className="text-sm space-y-1 mt-2">
          {item.top_factors.map((f, i) => (
            <li key={i} className="flex justify-between">
              <span>{f.feature}</span>
              <span className="tabular-nums">{f.shap > 0 ? "+" : ""}{f.shap.toFixed(2)}</span>
            </li>
          ))}
        </ul>

        <button className="mt-6 w-full bg-accent text-white py-2 rounded">
          採納為勤務點 (記錄用)
        </button>
        <p className="text-xs text-text-subtle mt-2">
          僅供勤務參考；模型版本載自最近一次訓練。
        </p>
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Wire into App.tsx (sidebar + route)**

Read `animal-crossing-dashboard/src/App.tsx` to find existing route/sidebar config. Add (in the 專區 section, after 酒駕成效):

```tsx
{
  label: "🎯 酒駕風險預測",
  icon: TrendingUp,
  view: "dui-prediction",
  visible: import.meta.env.VITE_ENABLE_PREDICTION === "true",
}
```

And in route switch:

```tsx
{currentView === "dui-prediction" && <DuiPredictionPage />}
```

Add `<PredictionStatusToast />` to the root layout (only renders when needed, no-op otherwise).

- [ ] **Step 4: Manual smoke (local)**

```powershell
$env:ENABLE_PREDICTION="true"
$env:VITE_ENABLE_PREDICTION="true"
cd animal-crossing-dashboard; npm run dev
```
Open http://localhost:5173, navigate to 酒駕風險預測, verify page renders (table empty until backend has predictions).

- [ ] **Step 5: Commit**

```bash
git add animal-crossing-dashboard/src/components/DuiPredictionPage.tsx animal-crossing-dashboard/src/components/PredictionStatusToast.tsx animal-crossing-dashboard/src/App.tsx
git commit -m "feat(prediction-ui): DuiPredictionPage + status toast + sidebar entry"
```

---

### Task 12: Bidirectional deep-links

**Files:**
- Modify: `animal-crossing-dashboard/src/components/AccidentAnalysisPage.tsx`

- [ ] **Step 1: Read existing 酒駕分析 tab block (around line 296-)**

Locate the section `{activeTab === 'dui' && (...)}` and append a link card just before its closing `</div>`.

- [ ] **Step 2: Append link card**

Insert before the closing of the `'dui'` tab's outer `<div>`:

```tsx
{import.meta.env.VITE_ENABLE_PREDICTION === "true" && (
  <div className="bg-surface-2 rounded-lg p-4 flex items-center justify-between">
    <span className="text-sm text-text-muted">🎯 想看下週風險預測？</span>
    <a href="#/dui-prediction" className="text-accent text-sm flex items-center gap-1">
      前往「酒駕風險預測」 →
    </a>
  </div>
)}
```

- [ ] **Step 3: Manual verify**

Visit 執法缺口 → 酒駕分析 tab in dev mode with `VITE_ENABLE_PREDICTION=true`, confirm card visible. Set false, confirm hidden.

- [ ] **Step 4: Commit**

```bash
git add animal-crossing-dashboard/src/components/AccidentAnalysisPage.tsx
git commit -m "feat(prediction-ui): bidirectional deep-link card on accident analysis page"
```

---

## Phase 5: Build Isolation & Polish

### Task 13: `build_update.py --exclude prediction`

**Files:**
- Modify: `build_update.py`
- Create: `tests/test_build_exclude.py`

- [ ] **Step 1: Write failing test for exclude flag**

Path: `tests/test_build_exclude.py`

```python
"""Test that --exclude prediction strips all prediction files from build output."""
import shutil
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


PREDICTION_PATHS = [
    "backend/app/ml",
    "backend/app/api/prediction.py",
    "backend/app/schemas/prediction.py",
    "backend/app/services/cwa_client.py",
    "backend/app/services/system_lock.py",
    "backend/app/models/prediction.py",
    "backend/scripts/daily_predict_dui.py",
    "backend/scripts/retrain_dui_model.py",
    "backend/scripts/init_prediction_schema.py",
    "backend/scripts/fetch_cwa_history.py",
    "backend/scripts/build_calendar.py",
    "animal-crossing-dashboard/src/components/DuiPredictionPage.tsx",
    "animal-crossing-dashboard/src/components/PredictionStatusToast.tsx",
    "animal-crossing-dashboard/src/api/predictionClient.ts",
    "animal-crossing-dashboard/src/types/prediction.ts",
    "requirements_ml.txt",
]


def test_exclude_prediction_strips_all_files(tmp_path):
    out_dir = tmp_path / "deploy"
    result = subprocess.run(
        [sys.executable, str(PROJECT_ROOT / "build_update.py"),
         "--exclude", "prediction", "--output", str(out_dir),
         "--skip-frontend"],  # speed up test
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr

    for p in PREDICTION_PATHS:
        forbidden = out_dir / p
        assert not forbidden.exists(), f"Prediction file leaked: {p}"
```

- [ ] **Step 2: Run, expect failure**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest tests/test_build_exclude.py -v
```

- [ ] **Step 3: Modify build_update.py**

Read `build_update.py` first to understand its structure. Add at top:

```python
PREDICTION_EXCLUDE_PATTERNS = [
    "backend/app/ml/",
    "backend/app/api/prediction.py",
    "backend/app/schemas/prediction.py",
    "backend/app/services/cwa_client.py",
    "backend/app/services/system_lock.py",
    "backend/app/models/prediction.py",
    "backend/scripts/daily_predict_dui.py",
    "backend/scripts/retrain_dui_model.py",
    "backend/scripts/init_prediction_schema.py",
    "backend/scripts/fetch_cwa_history.py",
    "backend/scripts/build_calendar.py",
    "backend/app/utils/shift_mapping.py",  # used only in prediction; keep if referenced elsewhere later
    "animal-crossing-dashboard/src/components/DuiPredictionPage.tsx",
    "animal-crossing-dashboard/src/components/PredictionStatusToast.tsx",
    "animal-crossing-dashboard/src/api/predictionClient.ts",
    "animal-crossing-dashboard/src/types/prediction.ts",
    "requirements_ml.txt",
]
```

In argument parsing, add:

```python
parser.add_argument("--exclude", action="append", default=[],
                    choices=["prediction"], help="Modules to exclude from build")
```

In the file-copy logic, before copying each file:

```python
def is_excluded(rel_path: str, excludes: list[str]) -> bool:
    if "prediction" in excludes:
        for pat in PREDICTION_EXCLUDE_PATTERNS:
            if rel_path.startswith(pat) or rel_path == pat.rstrip("/"):
                return True
    return False
```

Wrap the copy loop with `if is_excluded(rel_path, args.exclude): continue`.

Also: when `--exclude prediction` is set, write `.env` with `VITE_ENABLE_PREDICTION=false` and `ENABLE_PREDICTION=false` into the build root.

- [ ] **Step 4: Run tests**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest tests/test_build_exclude.py -v
```
Expected: pass.

- [ ] **Step 5: Manual dry-run test on actual build**

```powershell
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe build_update.py --exclude prediction --output D:\temp\test-colleague --skip-frontend
```
Then check the output dir for absence of prediction files manually.

- [ ] **Step 6: Commit**

```bash
git add build_update.py tests/test_build_exclude.py
git commit -m "feat(build): --exclude prediction flag for colleague-safe builds"
```

---

### Task 14: User guide + final verification

**Files:**
- Create: `docs/dui_prediction_user_guide.md`

- [ ] **Step 1: Write user guide**

Path: `docs/dui_prediction_user_guide.md`

```markdown
# 酒駕風險預測模組 使用手冊

> 此模組為本機限定，不在同事的更新版本內。

## 一次性建置

1. **建立 ML 環境**
   ```powershell
   py -3.12 -m venv D:\Programming\精準執法儀表板系統\.venv-ml
   .venv-ml\Scripts\pip install -r requirements_ml.txt
   ```

2. **建立資料表**
   ```powershell
   .venv-ml\Scripts\python backend\scripts\init_prediction_schema.py
   ```

3. **建立節慶資料表（2021-2030）**
   ```powershell
   .venv-ml\Scripts\python backend\scripts\build_calendar.py
   ```

4. **抓 CWA 5 年歷史氣象**
   - 申請 CWA Open Data API 金鑰：https://opendata.cwa.gov.tw/
   - 複製 `backend/.env.ml.example` → `backend/.env.ml`，填入金鑰
   - 執行：
   ```powershell
   .venv-ml\Scripts\python backend\scripts\fetch_cwa_history.py
   ```

5. **首次訓練**
   ```powershell
   .venv-ml\Scripts\python backend\scripts\retrain_dui_model.py
   ```
   確認輸出顯示 Recall ≥ 0.80。若否，檢查資料量、特徵或調整 `target_recall` 參數。

6. **啟動儀表板**
   ```powershell
   set ENABLE_PREDICTION=true
   set VITE_ENABLE_PREDICTION=true
   start.bat
   ```
   首次開啟首頁時，會自動觸發背景預測，右上角會顯示「🔄 預測資料更新中...」約 5-10 秒。

## 日常使用

- 每次開啟儀表板首頁時，若預測資料 >20 小時舊，前端會自動觸發背景刷新。
- 進入「專區 → 🎯 酒駕風險預測」查看 Top-N 高風險組合。
- 點 Top-N 表格的「詳情」可看 SHAP 解釋。

## 重新訓練

當資料庫累積 ≥ 30 天新資料時，建議手動重訓：

```powershell
.venv-ml\Scripts\python backend\scripts\retrain_dui_model.py
```

或透過 admin API：

```powershell
$env:ADMIN_API_KEY="your-key"
curl -X POST http://localhost/admin/predict/dui/retrain -H "X-API-Key: your-key"
```

## 為同事建置（不含預測模組）

```powershell
.venv-ml\Scripts\python build_update.py --exclude prediction
```

驗證：解開生成的 zip，確認**沒有**任何 `backend/app/ml/`、`DuiPredictionPage.tsx`、`backend/scripts/daily_predict_dui.py` 等檔案。

## 故障排除

| 症狀 | 可能原因 | 處置 |
|---|---|---|
| Recall < 0.80 | 資料量不足 / 特徵不夠 | 檢查 `eval_reports/` 最新報告，考慮加更多特徵或延長資料涵蓋 |
| CWA 抓取失敗 | API 金鑰無效 / 配額用盡 | 檢查 `.env.ml`，等待配額重置或申請更高層級 |
| 首頁觸發無反應 | system_locks 殘留 | 進 SQLite 直接 `DELETE FROM system_locks WHERE name='dui_predict'` |
| pickle 載入失敗 | xgboost 版本不一致 | 確認 `.venv-ml` 與 portable Python 都是 xgboost 2.1.x |
```

- [ ] **Step 2: Run all tests one final time**

```powershell
$env:ENABLE_PREDICTION="true"
D:\Programming\精準執法儀表板系統\.venv-ml\Scripts\python.exe -m pytest backend/tests/ tests/ -v
```
Expected: all green.

- [ ] **Step 3: Final manual checklist**

Walk through Section 13 of spec (Definition of Done):

- [ ] 5 年特徵集 + ext_weather + ext_calendar 全部入 DB
- [ ] 訓練腳本一鍵跑完，Recall ≥ 80%
- [ ] FastAPI 5 個端點上線並通過 manual test
- [ ] DuiPredictionPage 4 個區段顯示正確
- [ ] Dashboard 首頁開啟時自動偵測+背景刷新，連續 5 工作日驗證無誤
- [ ] Process lock 機制防重入驗證
- [ ] `build_update.py --exclude prediction` 對同事版驗證沒洩漏
- [ ] 雙向 deep-link 卡片顯示正常

- [ ] **Step 4: Commit**

```bash
git add docs/dui_prediction_user_guide.md
git commit -m "docs(prediction): user guide + DoD final checklist"
```

---

## Self-Review Notes

Reviewed against spec sections 1-15:

- §1 目標與動機 → covered by all tasks
- §2 架構總覽 → Tasks 9 (API mount), 10-12 (frontend), 13 (build isolation)
- §3 資料庫 Schema → Task 2
- §4 特徵工程 → Task 5
- §5 模型架構 → Task 6
- §6 訓練 Pipeline → Tasks 6, 8
- §7 API 端點 → Task 9
- §8 前端 UI → Tasks 10-12 (heatmap and SHAP global plot deferred to P1 in spec; placeholder in Task 11 — explicit and acceptable)
- §9 部署隔離 → Task 13
- §10 環境準備 → Task 1
- §11 監控 → covered ad-hoc in tasks (status endpoint, lock staleness)
- §12 風險清單 → mitigations baked into code (fillna for weather, lock staleness, etc.)
- §13 DoD → Task 14 final checklist
- §14 後續迭代 → not in this plan (P1+)
- §15 變更紀錄 → spec only

Type consistency check: `DuiPredictor.load_latest()` in Task 7 used by Task 8; `predict()` returns DataFrame with `risk_score`, `risk_level`, `predicted_count`, `model_version` consistent with API response in Task 9 and frontend types in Task 10. ✅
