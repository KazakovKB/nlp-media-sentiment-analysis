from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


def _fmt_dt(dt: datetime | None, fmt: str = "%d.%m.%Y %H:%M") -> str:
    if not dt:
        return "—"
    return dt.astimezone().strftime(fmt)


def _parse_iso_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _pct(x: float) -> str:
    return f"{x * 100:.1f}%"


def _safe_float(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def _safe_int(x: Any, default: int = 0) -> int:
    try:
        return int(x)
    except Exception:
        return default


@dataclass(frozen=True)
class OverviewView:
    # raw
    total_documents: int
    sources: list[int]
    query: str
    sentiment_mode: str
    trends_found: int
    created_at: str

    # period
    period: str
    date_from: str
    date_to: str

    # sentiment
    sentiment: dict[str, Any]
    dominant_sentiment: str

    # KPI
    days_count: int
    avg_per_day: float
    peak_per_day: int
    peak_day: str

    # series for charts
    daily_labels: list[str]
    daily_values: list[int]


def present_overview(rep) -> OverviewView:
    metrics: Mapping[str, Any] = rep.metrics or {}
    share: Mapping[str, Any] = rep.sentiment_share or {"negative": 0.0, "neutral": 1.0, "positive": 0.0}

    # period
    date_from_iso = metrics.get("date_from")
    date_to_iso = metrics.get("date_to")
    dt_from = _parse_iso_dt(date_from_iso)
    dt_to = _parse_iso_dt(date_to_iso)

    date_from = _fmt_dt(dt_from, "%d.%m.%Y %H:%M") if dt_from else "—"
    date_to = _fmt_dt(dt_to, "%d.%m.%Y %H:%M") if dt_to else "—"
    period = f"{date_from} — {date_to}" if dt_from and dt_to else "—"

    # query / sources
    query = metrics.get("query") or "—"
    sources = [int(x) for x in (metrics.get("source_ids") or [])]

    sentiment_mode = str(metrics.get("sentiment_mode", "unknown"))
    trends_found = _safe_int(metrics.get("trends_found", 0))

    # daily series
    series = metrics.get("daily_series") or []
    daily_labels: list[str] = []
    daily_values: list[int] = []

    if isinstance(series, list):
        for p in series:
            if not isinstance(p, dict):
                continue
            ts = str(p.get("ts", ""))
            val = _safe_int(p.get("value", 0))
            daily_labels.append(ts[:10] if len(ts) >= 10 else ts)
            daily_values.append(val)

    days_count = len(daily_values)
    total_documents = _safe_int(rep.total_documents, 0)

    avg_per_day = round(total_documents / days_count, 2) if days_count > 0 else 0.0

    if days_count > 0:
        peak_per_day = max(daily_values)
        peak_idx = daily_values.index(peak_per_day)
        peak_day = daily_labels[peak_idx] if 0 <= peak_idx < len(daily_labels) else "—"
    else:
        peak_per_day = 0
        peak_day = "—"

    # sentiment
    neg = _safe_float(share.get("negative", 0.0))
    neu = _safe_float(share.get("neutral", 1.0))
    pos = _safe_float(share.get("positive", 0.0))

    sentiment = {
        "negative": {"raw": neg, "pct": _pct(neg)},
        "neutral":  {"raw": neu, "pct": _pct(neu)},
        "positive": {"raw": pos, "pct": _pct(pos)},
    }

    dominant_sentiment = max(
        (("negative", neg), ("neutral", neu), ("positive", pos)),
        key=lambda x: x[1],
    )[0]

    return OverviewView(
        total_documents=total_documents,
        sentiment=sentiment,
        dominant_sentiment=dominant_sentiment,
        period=period,
        date_from=date_from,
        date_to=date_to,
        sources=sources,
        query=str(query),
        trends_found=trends_found,
        sentiment_mode=sentiment_mode,
        created_at=_fmt_dt(getattr(rep, "created_at", None)),
        days_count=days_count,
        avg_per_day=avg_per_day,
        peak_per_day=peak_per_day,
        peak_day=peak_day,
        daily_labels=daily_labels,
        daily_values=daily_values,
    )