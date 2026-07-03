"""Shared preset / finer-grained option generators for amount-picking screens, so every screen
stays button-driven without needing a typed "custom value" fallback (see keyboards.preset_keyboard
and keyboards.paginated_list_keyboard, which the "More amounts" escape hatch pages through).
"""
from dml_bot.bot.formatting import fmt_ram

GPU_RAM_PRESETS_MB = [8192, 16384, 24576, 40960, 81920]
RAM_THRESHOLD_PRESETS_MB = [1024, 2048, 4096, 8192, 16384]


def fine_ram_options(cap_mb: int, step_mb: int = 1024) -> list[tuple[str, int]]:
    options = [(fmt_ram(mb), mb) for mb in range(step_mb, cap_mb + 1, step_mb)]
    if not options or options[-1][1] != cap_mb:
        options.append((fmt_ram(cap_mb), cap_mb))
    return options
