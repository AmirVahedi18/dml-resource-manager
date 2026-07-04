from datetime import datetime, timezone

from sqlalchemy.orm import Session

from dml_bot.db.models.chart_settings import SINGLETON_ID, ChartSettings

# "legacy" is the original fixed-width monospace text chart; the rest render a Plotly figure to a
# PNG and send it as a photo (Telegram can't show an interactive Plotly chart inline in chat).
RENDERERS = ["legacy", "plotly_bars", "plotly_area", "plotly_gantt"]

RENDERER_LABELS = {
    "legacy": "Legacy (text chart)",
    "plotly_bars": "Plotly — stacked bars",
    "plotly_area": "Plotly — stacked area",
    "plotly_gantt": "Plotly — per-user timeline",
}


def ensure_seeded(session: Session, default_renderer: str) -> ChartSettings:
    settings = session.get(ChartSettings, SINGLETON_ID)
    if settings is not None:
        return settings

    if default_renderer not in RENDERERS:
        default_renderer = "legacy"
    settings = ChartSettings(id=SINGLETON_ID, renderer=default_renderer)
    session.add(settings)
    session.flush()
    return settings


def get_renderer(session: Session) -> str:
    settings = session.get(ChartSettings, SINGLETON_ID)
    return settings.renderer if settings is not None else "legacy"


def set_renderer(session: Session, updated_by: int, renderer: str) -> ChartSettings:
    if renderer not in RENDERERS:
        raise ValueError(f"Unknown chart renderer: {renderer}")
    settings = session.get(ChartSettings, SINGLETON_ID)
    if settings is None:
        settings = ChartSettings(id=SINGLETON_ID, renderer=renderer)
        session.add(settings)
    else:
        settings.renderer = renderer
    settings.updated_by = updated_by
    settings.updated_at = datetime.now(timezone.utc)
    session.flush()
    return settings
