import re
import calendar
from datetime import datetime, timedelta

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}


def extract_time_filter(cleaned_text: str, date_columns: list[str], reference_date: datetime | None = None) -> dict | None:
    """
    Rule-based time expression parsing — no LLM. Covers the phrasings from
    Module 6: today/yesterday, last month/year, this year, Q1-Q4 [year],
    month names [+ year], last N days, before/after YYYY.
    """
    if not date_columns:
        return None

    ref = reference_date or datetime.utcnow()
    col = date_columns[0]

    if "today" in cleaned_text:
        d = ref.date()
        return {"column": col, "start": d.isoformat(), "end": d.isoformat()}

    if "yesterday" in cleaned_text:
        d = (ref - timedelta(days=1)).date()
        return {"column": col, "start": d.isoformat(), "end": d.isoformat()}

    if "last month" in cleaned_text:
        first_this = ref.replace(day=1)
        last_month_end = first_this - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)
        return {"column": col, "start": last_month_start.date().isoformat(), "end": last_month_end.date().isoformat()}

    if "this year" in cleaned_text:
        return {"column": col, "start": f"{ref.year}-01-01", "end": f"{ref.year}-12-31"}

    if "last year" in cleaned_text:
        y = ref.year - 1
        return {"column": col, "start": f"{y}-01-01", "end": f"{y}-12-31"}

    m = re.search(r"last\s+(\d+)\s+days?", cleaned_text)
    if m:
        n = int(m.group(1))
        return {"column": col, "start": (ref - timedelta(days=n)).date().isoformat(), "end": ref.date().isoformat()}

    if "last week" in cleaned_text or "previous week" in cleaned_text:
        return {"column": col, "start": (ref - timedelta(days=7)).date().isoformat(), "end": ref.date().isoformat()}

    q_match = re.search(r"\bq([1-4])\b\s*(\d{4})?", cleaned_text)
    if q_match:
        q = int(q_match.group(1))
        year = int(q_match.group(2)) if q_match.group(2) else ref.year
        start_month = (q - 1) * 3 + 1
        end_month = start_month + 2
        end_day = calendar.monthrange(year, end_month)[1]
        return {"column": col, "start": f"{year}-{start_month:02d}-01", "end": f"{year}-{end_month:02d}-{end_day:02d}"}

    for month_name, month_num in MONTHS.items():
        if re.search(rf"\b{month_name}\b", cleaned_text):
            year_match = re.search(r"\b(20\d{2})\b", cleaned_text)
            year = int(year_match.group(1)) if year_match else ref.year
            end_day = calendar.monthrange(year, month_num)[1]
            return {"column": col, "start": f"{year}-{month_num:02d}-01", "end": f"{year}-{month_num:02d}-{end_day:02d}"}

    before_match = re.search(r"before\s+(\d{4})", cleaned_text)
    if before_match:
        return {"column": col, "operator": "before", "start": None, "end": f"{before_match.group(1)}-01-01"}

    after_match = re.search(r"after\s+(\d{4})", cleaned_text)
    if after_match:
        return {"column": col, "operator": "after", "start": f"{after_match.group(1)}-12-31", "end": None}

    year_match = re.search(r"\b(20\d{2})\b", cleaned_text)
    if year_match:
        year = year_match.group(1)
        return {"column": col, "start": f"{year}-01-01", "end": f"{year}-12-31"}

    return None