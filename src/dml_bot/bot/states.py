from enum import IntEnum, auto


class ReserveStates(IntEnum):
    CHOOSE_SERVER = auto()
    CHOOSE_GPU = auto()
    CHOOSE_DATE = auto()
    CHOOSE_START_TIME = auto()
    CHOOSE_DURATION = auto()
    CHOOSE_RAM = auto()
    CONFIRM = auto()


class CancelStates(IntEnum):
    CHOOSE_RESERVATION = auto()
    CONFIRM = auto()


class ScheduleStates(IntEnum):
    CHOOSE_SERVER = auto()
    CHOOSE_GPU = auto()
    CHOOSE_RANGE = auto()


class WatchFlowStates(IntEnum):
    """A single enum (not split per sub-flow) since one ConversationHandler mixes both
    the watch list/cancel screens and the new-watch wizard, and IntEnum members compare
    equal (and collide as dict keys) across different enums when their values match."""

    MENU = auto()
    CHOOSE_WATCH = auto()
    CONFIRM_CANCEL = auto()
    CHOOSE_SERVER = auto()
    CHOOSE_GPU = auto()
    CHOOSE_RANGE = auto()
    CHOOSE_RAM = auto()


class AdminUserStates(IntEnum):
    MENU = auto()
    ADD_TELEGRAM_ID = auto()
    ADD_FULL_NAME = auto()


class AdminServerStates(IntEnum):
    MENU = auto()
    ADD_SERVER_NAME = auto()
    CHOOSE_SERVER_FOR_GPU = auto()
    ADD_GPU_INDEX = auto()
    ADD_GPU_MODEL = auto()
    ADD_GPU_RAM = auto()


class AdminRegulationStates(IntEnum):
    MENU = auto()
    EDIT_VALUE = auto()


class AdminUsageStates(IntEnum):
    CHOOSE_SCOPE = auto()
    CHOOSE_TARGET = auto()
    CHOOSE_RANGE = auto()


class AdminReservationsStates(IntEnum):
    CHOOSE_RESERVATION = auto()
    CONFIRM_CANCEL = auto()
