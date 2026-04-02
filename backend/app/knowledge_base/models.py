import uuid
from datetime import datetime
from enum import Enum
from typing import Optional, List
from sqlalchemy import String, Text, Boolean, ForeignKey, Integer, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship, DeclarativeBase
from sqlalchemy.dialects.postgresql import UUID

class Base(DeclarativeBase):
    pass

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSED = "processed"
    ERROR = "error"

class RuleScope(str, Enum):
    DATABASE = "database"
    SCHEMA = "schema"
    TABLE = "table"
    COLUMN = "column"

class Project(Base):
    __tablename__ = "projects"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String, unique=True, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Source DB Connection Info
    source_db_host: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_db_port: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_db_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_db_user: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    tables: Mapped[List["TableMeta"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    rules: Mapped[List["Rule"]] = relationship(back_populates="project", cascade="all, delete-orphan")

class TableMeta(Base):
    __tablename__ = "table_meta"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    
    table_name: Mapped[str] = mapped_column(String, index=True)
    schema_name: Mapped[str] = mapped_column(String, default="dbo")
    
    user_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    status: Mapped[ProcessingStatus] = mapped_column(
        SQLEnum(ProcessingStatus, name="processing_status"), 
        default=ProcessingStatus.PENDING
    )
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project: Mapped["Project"] = relationship(back_populates="tables")
    columns: Mapped[List["ColumnMeta"]] = relationship(back_populates="table_meta", cascade="all, delete-orphan")

class ColumnMeta(Base):
    __tablename__ = "column_meta"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    table_meta_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("table_meta.id"))
    
    column_name: Mapped[str] = mapped_column(String, index=True)
    data_type: Mapped[str] = mapped_column(String)
    is_nullable: Mapped[bool] = mapped_column(Boolean, default=True)
    is_primary_key: Mapped[bool] = mapped_column(Boolean, default=False)
    
    is_foreign_key: Mapped[bool] = mapped_column(Boolean, default=False)
    fk_target_table: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fk_target_column: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    user_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    generated_explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    visualization_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    table_meta: Mapped["TableMeta"] = relationship(back_populates="columns")

class Rule(Base):
    __tablename__ = "rules"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"))
    
    scope: Mapped[RuleScope] = mapped_column(SQLEnum(RuleScope, name="rule_scope"))
    scope_identifier: Mapped[str] = mapped_column(String, index=True)  # e.g. "students" or "dbo.students.id"
    rule_text: Mapped[str] = mapped_column(Text)
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    project: Mapped["Project"] = relationship(back_populates="rules")

class EntityAlias(Base):
    __tablename__ = "entity_aliases"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String, index=True)
    alias: Mapped[str] = mapped_column(String, index=True)
    canonical_name: Mapped[str] = mapped_column(String)
    entity_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[str] = mapped_column(String, default="extracted")
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
