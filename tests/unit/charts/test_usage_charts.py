from dml_bot.charts.usage_charts import render_bar_chart

_PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_renders_png_with_values():
    png = render_bar_chart(["Alice", "Bob"], [12.5, 4.0], "Usage by user", "GPU-hours")
    assert png.startswith(_PNG_MAGIC)


def test_renders_png_with_single_bar():
    png = render_bar_chart(["Alice"], [12.5], "Usage by user", "GPU-hours")
    assert png.startswith(_PNG_MAGIC)


def test_renders_png_with_many_bars():
    labels = [f"User {i}" for i in range(50)]
    values = [float(i) for i in range(50)]
    png = render_bar_chart(labels, values, "Usage by user", "GPU-hours")
    assert png.startswith(_PNG_MAGIC)
