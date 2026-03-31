from uuid import UUID
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.knowledge_base.models import ProcessingStatus, RuleScope

# --- Project Schemas ---
class ProjectBase(BaseModel):
    name: str
    description: Optional[str] = None
    source_db_host: Optional[str] = None
    source_db_port: Optional[int] = None
    source_db_name: Optional[str] = None
    source_db_user: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(ProjectBase):
    name: Optional[str] = None

class ProjectResponse(ProjectBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Rule Schemas ---
class RuleBase(BaseModel):
    scope: RuleScope
    scope_identifier: str
    rule_text: str
    is_active: bool = True

class RuleCreate(RuleBase):
    project_id: UUID

class RuleUpdate(BaseModel):
    rule_text: Optional[str] = None
    is_active: Optional[bool] = None

class RuleResponse(RuleBase):
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Column Schemas ---
class ColumnMetaBase(BaseModel):
    column_name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False
    is_foreign_key: bool = False
    fk_target_table: Optional[str] = None
    fk_target_column: Optional[str] = None
    user_description: Optional[str] = None
    generated_explanation: Optional[str] = None

class ColumnMetaResponse(ColumnMetaBase):
    id: UUID
    table_meta_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- Table Schemas ---
class TableMetaBase(BaseModel):
    table_name: str
    schema_name: str = "dbo"
    user_description: Optional[str] = None
    generated_explanation: Optional[str] = None
    status: ProcessingStatus = ProcessingStatus.PENDING

class TableMetaCreate(TableMetaBase):
    project_id: UUID

class TableMetaUpdate(BaseModel):
    user_description: Optional[str] = None
    generated_explanation: Optional[str] = None
    status: Optional[ProcessingStatus] = None

class TableMetaResponse(TableMetaBase):
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime
    columns: List[ColumnMetaResponse] = []
    model_config = ConfigDict(from_attributes=True)
