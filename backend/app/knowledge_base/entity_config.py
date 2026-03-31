import yaml
from pathlib import Path
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

class EntityTypeConfig(BaseModel):
    table: str
    name_column: str
    id_column: Optional[str] = None
    alias_columns: Optional[List[str]] = Field(default_factory=list)
    description: str
    filter_condition: Optional[str] = None

class EntityConfig(BaseModel):
    entities: Dict[str, EntityTypeConfig]

def load_entity_config() -> Dict[str, EntityTypeConfig]:
    config_path = Path(__file__).resolve().parent.parent.parent / "docs" / "entities" / "entities.yaml"
    with open(config_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    config = EntityConfig(**data)
    return config.entities
