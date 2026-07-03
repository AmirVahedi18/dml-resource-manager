import io

import matplotlib

matplotlib.use("Agg")
from matplotlib import pyplot as plt


def render_bar_chart(labels: list[str], values: list[float], title: str, ylabel: str) -> bytes:
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(labels, values)
    ax.set_title(title)
    ax.set_ylabel(ylabel)
    ax.tick_params(axis="x", rotation=45, labelsize=8)
    fig.tight_layout()

    buffer = io.BytesIO()
    fig.savefig(buffer, format="png")
    plt.close(fig)
    buffer.seek(0)
    return buffer.getvalue()
