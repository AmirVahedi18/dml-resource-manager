from pydantic import BaseModel, Field


class UserAdminOut(BaseModel):
    id: int
    username: str | None
    full_name: str
    is_active: bool
    is_admin: bool
    is_bootstrap: bool
    max_concurrent_gpus: int
    server_ids: list[int]


class BulkUserCreateItem(BaseModel):
    username: str
    password: str
    full_name: str
    max_concurrent_gpus: int = 1
    server_ids: list[int] = Field(default_factory=list)


class BulkUserCreateRequest(BaseModel):
    users: list[BulkUserCreateItem]


class BulkUserCreateResultItem(BaseModel):
    username: str
    success: bool
    user_id: int | None = None
    error: str | None = None


class BulkUserCreateResponse(BaseModel):
    results: list[BulkUserCreateResultItem]


class RenameUserRequest(BaseModel):
    full_name: str


class SetActiveRequest(BaseModel):
    is_active: bool


class SetAdminRequest(BaseModel):
    is_admin: bool


class SetMaxConcurrentGpusRequest(BaseModel):
    max_concurrent_gpus: int


class SetServerAccessRequest(BaseModel):
    server_ids: list[int]


class ResetPasswordRequest(BaseModel):
    new_password: str
