from src.app.domain.value_objects import TrendSignal

def detect_trends(
    time_series: list[dict],
    window: int = 5,
    z_threshold: float = 2.0,
    min_points: int = 8,
) -> list[TrendSignal]:
    """
    MVP: rolling z-score.
    """
    if not time_series or len(time_series) < min_points:
        return []

    values = [float(p["value"]) for p in time_series]
    tss = [p["ts"] for p in time_series]

    events: list[TrendSignal] = []

    for i in range(len(values)):
        left = max(0, i - window)
        right = i
        if right - left < max(3, window // 2):
            continue

        hist = values[left:right]
        mean = sum(hist) / len(hist)
        var = sum((x - mean) ** 2 for x in hist) / max(1, (len(hist) - 1))
        std = var ** 0.5

        if std < 1e-9:
            continue

        z = (values[i] - mean) / std

        if z >= z_threshold:
            events.append(TrendSignal(ts=tss[i], kind="spike", value=values[i], baseline=mean, z=z))
        elif z <= -z_threshold:
            events.append(TrendSignal(ts=tss[i], kind="drop", value=values[i], baseline=mean, z=z))

    return events