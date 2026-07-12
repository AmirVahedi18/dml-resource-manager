from pydantic import BaseModel, Field


class ServerAdminOut(BaseModel):
    id: int
    name: str
    is_active: bool
    model_config = {"from_attributes": True}


class ServerCreateRequest(BaseModel):
    name: str


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
    index_on_server: int = Field(ge=0)
    model_name: str
    total_ram_mb: int = Field(gt=0)


class GpuRenameRequest(BaseModel):
    model_name: str


class SetGpuActiveRequest(BaseModel):
    is_active: bool
