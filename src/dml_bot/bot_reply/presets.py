"""Shared preset generators for amount-picking screens that are still button-driven (see
keyboards.action_keyboard) -- currently just the admin's "Add GPU" total-RAM step. The
reservation/watch RAM steps are typed integers instead (see ram_unit_mb below).
"""
GPU_RAM_PRESETS_MB = [8192, 16384, 24576, 40960, 81920]


def ram_unit_mb(unit: str) -> int:
    """Size, in MB, of one typed-RAM-input unit -- "GB" (1024) or "MB" (1). Stored/validated
    reservation and watch values are always MB; `unit` only controls what students type."""
    return 1024 if unit.upper() == "GB" else 1
