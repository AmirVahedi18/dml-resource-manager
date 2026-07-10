from pydantic import BaseModel


class ServerAdminOut(BaseModel):
    id: int
    name: str
    description: str | None
    is_active: bool
    model_config = {"from_attributes": True}


class ServerCreateRequest(BaseModel):
    name: str
    description: str | None = None


class ServerRenameRequest(BaseModel):
    name: str


class SetServerActiveRequest(BaseModel):
    is_active: bool


class GpuAdminOut(BaseModel):
    id: int
    server_id: int
    index_on_server: int
    model_name: str
    total_ram_mb: int
    is_active: bool
    model_config = {"from_attributes": True}


class GpuCreateRequest(BaseModel):
    index_on_server: int
    model_name: str
    total_ram_mb: int


class GpuRenameRequest(BaseModel):
    model_name: str


class SetGpuActiveRequest(BaseModel):
    is_active: bool
