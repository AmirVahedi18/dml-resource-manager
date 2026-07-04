from enum import IntEnum, auto


class ReserveStates(IntEnum):
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
    CHOOSE_GPU = auto()
    CHOOSE_RANGE = auto()


class WatchFlowStates(IntEnum):
    """A single enum (not split per sub-flow), matching the legacy interface's precedent -- one
    ConversationHandler mixes the watch list/cancel screens and the new-watch wizard, and IntEnum
    members compare equal (and collide as dict keys) across different enums when values match."""

    MENU = auto()
    CONFIRM_CANCEL = auto()
    CHOOSE_GPU = auto()
    CHOOSE_RANGE = auto()
    CHOOSE_RAM = auto()


class AdminUserStates(IntEnum):
    MENU = auto()
    ADD_FULL_NAME = auto()
    ADD_SERVER_ACCESS = auto()
    RENAME = auto()
    CONFIRM_DELETE = auto()
    EDIT_SERVER_ACCESS = auto()


class AdminServerStates(IntEnum):
    MENU = auto()
    ADD_SERVER_NAME = auto()
    CHOOSE_SERVER_FOR_GPU = auto()
    ADD_GPU_INDEX = auto()
    ADD_GPU_MODEL = auto()
    ADD_GPU_RAM = auto()
    ADD_GPU_RAM_CUSTOM = auto()
    SERVER_DETAIL = auto()
    RENAME_SERVER = auto()
    CONFIRM_DELETE_SERVER = auto()
    GPU_DETAIL = auto()
    RENAME_GPU = auto()
    CONFIRM_DELETE_GPU = auto()


class AdminRegulationStates(IntEnum):
    MENU = auto()
    EDIT_VALUE = auto()


class AdminUsageStates(IntEnum):
    CHOOSE_SCOPE = auto()
    CHOOSE_RANGE = auto()


class AdminReservationsStates(IntEnum):
    CHOOSE_SCOPE = auto()
    CHOOSE_USER = auto()
    CHOOSE_RESERVATION = auto()
    CONFIRM_CANCEL = auto()
    CONFIRM_CANCEL_ALL_USER = auto()
    TYPE_CONFIRM_CANCEL_ALL_LAB = auto()
