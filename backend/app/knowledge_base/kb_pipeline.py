import asyncio
import os
import yaml
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ValidationError
from sqlalchemy.future import select

from app.dependencies import get_mysql_inspector, AsyncSessionLocal
from app.knowledge_base.models import Project, TableMeta, ColumnMeta, ProcessingStatus
from app.knowledge_base.schemas import TableMetaCreate
from app.knowledge_base.rag_pipeline import generate_table_explanation, generate_column_explanations
from app.knowledge_base.vector_store import upsert_table_embedding
from app.knowledge_base.neo4j_graph import upsert_table_node, upsert_fk_edge

# --- YAML Loader ---
class ColumnDoc(BaseModel):
    name: str
    description: str

class TableDoc(BaseModel):
    table_name: str
    table_description: str
    columns: List[ColumnDoc] = []
    rules: List[str] = []
    relationships: Optional[List[Dict[str, Any]]] = []

def load_table_yaml(table_name: str) -> Dict[str, Any]:
    """
    Loads a YAML documentation file for a given table from backend/docs/tables/.
    """
    # Construct path: assuming this runs from backend/ root or app is in python path
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    docs_dir = os.path.join(base_dir, "docs", "tables")
    file_path = os.path.join(docs_dir, f"{table_name}.yaml")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Documentation file not found: {file_path}")
        
    with open(file_path, "r", encoding="utf-8") as f:
        try:
            data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file {file_path}: {e}")
            
    # Validate with Pydantic
    try:
        doc = TableDoc(**data)
        return doc.model_dump()
    except ValidationError as e:
        raise ValueError(f"Invalid documentation format in {file_path}: {e}")


# --- Orchestration ---

async def get_or_create_project(session, name="Curriculum DB"):
    stmt = select(Project).where(Project.name == name)
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    
    if not project:
        project = Project(name=name, description="University Curriculum Database")
        session.add(project)
        await session.commit()
        await session.refresh(project)
    
    return project

async def process_table(table_name: str, project_name: str = "Curriculum DB"):
    """
    Full pipeline to process a single table.
    """
    print(f"Processing table: {table_name}")
    
    # 1. Load YAML
    try:
        yaml_data = load_table_yaml(table_name)
    except FileNotFoundError:
        print(f"YAML file for {table_name} not found. Skipping.")
        return
    
    user_table_desc = yaml_data.get("table_description", "")
    columns_list = yaml_data.get("columns", [])
    user_col_descs = {c['name']: c['description'] for c in columns_list}
    
    # 2. Introspect MySQL
    inspector = get_mysql_inspector()
    if table_name not in inspector.get_table_names():
        print(f"Table {table_name} not found in source MySQL database.")
        return

    columns_info = []
    for col in inspector.get_columns(table_name):
        columns_info.append({
            "name": col["name"],
            "type": str(col["type"]),
            "nullable": col["nullable"],
            "primary_key": col.get("primary_key", False)
        })
    
    # Introspect PK
    try:
        pk_constraint = inspector.get_pk_constraint(table_name)
        pk_columns = pk_constraint.get("constrained_columns", [])
        for col in columns_info:
            if col["name"] in pk_columns:
                col["primary_key"] = True
    except Exception as e:
        print(f"Warning: Error fetching PKs: {e}")

    # Introspect FKs
    try:
        fks = inspector.get_foreign_keys(table_name)
    except Exception as e:
        print(f"Warning: Error fetching FKs: {e}")
        fks = []

    fk_map = {}
    for fk in fks:
        for idx, col_name in enumerate(fk["constrained_columns"]):
            fk_map[col_name] = {
                "target_table": fk["referred_table"],
                "target_column": fk["referred_columns"][idx]
            }
            
    # Process Manual Relationships from YAML
    # Expected format in YAML:
    # relationships:
    #   - column: "batch_id"
    #     target_table: "batches"
    #     target_column: "id"
    # PyYAML / Pydantic might parse empty `relationships:` as None, so we default to []
    manual_rels = yaml_data.get("relationships") or []
    for rel in manual_rels:
        col = rel.get("column")
        tgt_table = rel.get("target_table")
        tgt_col = rel.get("target_column")
        
        if col and tgt_table and tgt_col:
            # Check if this column already has a relationship defined (e.g. from MySQL)
            if col in fk_map:
                existing_rel = fk_map[col]
                # If it's the exact same relationship, skip it silently or log a debug message
                if existing_rel["target_table"] == tgt_table and existing_rel["target_column"] == tgt_col:
                     print(f"Skipping YAML relationship (already in DB): {table_name}.{col} -> {tgt_table}.{tgt_col}")
                     continue
                else:
                     print(f"Warning: YAML relationship for {table_name}.{col} conflicts with DB foreign key. Using DB version.")
                     continue
                     
            print(f"Adding manual relationship: {table_name}.{col} -> {tgt_table}.{tgt_col}")
            fk_map[col] = {
                "target_table": tgt_table,
                "target_column": tgt_col
            }

    # 3. Generate Table Explanation
    try:
        table_explanation = generate_table_explanation(table_name, columns_info, user_table_desc)
    except Exception as e:
        print(f"Error generating table explanation: {e}")
        table_explanation = user_table_desc

    # 4. Generate Column Explanations
    try:
        col_explanations = generate_column_explanations(table_name, table_explanation, columns_info, user_col_descs)
        col_expl_map = {c["column_name"]: c["explanation"] for c in col_explanations}
    except Exception as e:
        print(f"Error generating column explanations: {e}")
        col_expl_map = {}

    # 5. Upsert Metadata in Postgres
    async with AsyncSessionLocal() as session:
        project = await get_or_create_project(session, project_name)
        
        # Check if table meta exists
        stmt = select(TableMeta).where(
            TableMeta.project_id == project.id, 
            TableMeta.table_name == table_name
        )
        result = await session.execute(stmt)
        table_meta = result.scalar_one_or_none()
        
        if not table_meta:
            table_meta = TableMeta(
                project_id=project.id,
                table_name=table_name,
                schema_name="dbo",
                user_description=user_table_desc,
                generated_explanation=table_explanation,
                status=ProcessingStatus.PROCESSED
            )
            session.add(table_meta)
            await session.commit()
            await session.refresh(table_meta)
        else:
            table_meta.user_description = user_table_desc
            table_meta.generated_explanation = table_explanation
            table_meta.status = ProcessingStatus.PROCESSED
        
        # Process columns
        stmt = select(ColumnMeta).where(ColumnMeta.table_meta_id == table_meta.id)
        result = await session.execute(stmt)
        existing_cols = {c.column_name: c for c in result.scalars().all()}
        
        for col_info in columns_info:
            c_name = col_info["name"]
            is_fk = c_name in fk_map
            fk_target = fk_map.get(c_name, {})
            
            if c_name in existing_cols:
                c = existing_cols[c_name]
                c.data_type = col_info["type"]
                c.is_nullable = col_info["nullable"]
                c.is_primary_key = col_info["primary_key"]
                c.is_foreign_key = is_fk
                c.fk_target_table = fk_target.get("target_table")
                c.fk_target_column = fk_target.get("target_column")
                c.user_description = user_col_descs.get(c_name)
                c.generated_explanation = col_expl_map.get(c_name)
            else:
                new_col = ColumnMeta(
                    table_meta_id=table_meta.id,
                    column_name=c_name,
                    data_type=col_info["type"],
                    is_nullable=col_info["nullable"],
                    is_primary_key=col_info["primary_key"],
                    is_foreign_key=is_fk,
                    fk_target_table=fk_target.get("target_table"),
                    fk_target_column=fk_target.get("target_column"),
                    user_description=user_col_descs.get(c_name),
                    generated_explanation=col_expl_map.get(c_name)
                )
                session.add(new_col)
        
        await session.commit()
        
        # Upsert table-level rules from YAML
        yaml_rules = yaml_data.get("rules", [])
        if yaml_rules:
            from app.knowledge_base.models import Rule, RuleScope
            from sqlalchemy import delete as sql_delete
            # Clear existing table rules for this table (idempotent)
            await session.execute(
                sql_delete(Rule).where(
                    Rule.scope == RuleScope.TABLE,
                    Rule.scope_identifier == table_name
                )
            )
            for rule_text in yaml_rules:
                session.add(Rule(
                    project_id=project.id,
                    scope=RuleScope.TABLE,
                    scope_identifier=table_name,
                    rule_text=rule_text,
                    is_active=True
                ))
            await session.commit()
            print(f"  Seeded {len(yaml_rules)} rules for table '{table_name}'.")
    
    # 6. Upsert Vector Embedding
    try:
        upsert_table_embedding(table_name, table_explanation)
    except Exception as e:
        print(f"Error upserting vector embedding: {e}")

    # 7. Upsert Neo4j Nodes & Edges
    try:
        upsert_table_node(table_name)
        for col_name, fk_info in fk_map.items():
            target_table = fk_info["target_table"]
            target_col = fk_info["target_column"]
            upsert_table_node(target_table)
            upsert_fk_edge(table_name, col_name, target_table, target_col)
    except Exception as e:
        print(f"Error updating Neo4j: {e}")
    
    print(f"Finished processing {table_name}.\n")

async def rebuild_all(project_name: str = "Curriculum DB", use_checkpoint: bool = False):
    """
    Scans docs/tables/*.yaml and processes all of them.
    Supports checkpoint-based resuming if use_checkpoint=True.
    """
    import os
    from app.kb_pipeline_checkpoint import (
        load_kb_checkpoint, mark_kb_table_complete, save_kb_checkpoint
    )
    
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    docs_dir = os.path.join(base_dir, "docs", "tables")
    
    if not os.path.exists(docs_dir):
        print("No docs directory found.")
        return

    files = [f for f in os.listdir(docs_dir) if f.endswith(".yaml") and not f.startswith("_")]
    table_names = [f.replace(".yaml", "") for f in files]
    print(f"Found {len(table_names)} table documentation files.")
    
    # Load checkpoint if resuming
    completed_tables = []
    if use_checkpoint:
        checkpoint = load_kb_checkpoint()
        if checkpoint:
            completed_tables = checkpoint.get('completed_tables', [])
            # Filter out already-completed tables
            table_names = [t for t in table_names if t not in completed_tables]
            if not table_names:
                print("All tables already processed. Checkpoint complete!")
                return
    
    # Process tables
    for table_name in table_names:
        await process_table(table_name, project_name)
        
        # Save checkpoint after each table
        if use_checkpoint:
            mark_kb_table_complete(table_name, completed_tables, [f.replace(".yaml", "") for f in files])
