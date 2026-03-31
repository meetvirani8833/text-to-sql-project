import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import AsyncSessionLocal
from app.knowledge_base.models import TableMeta, ColumnMeta, Rule, Project
from app.knowledge_base.kb_pipeline import rebuild_all, process_table

router = APIRouter(prefix="/api/kb", tags=["Knowledge Base"])

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session

@router.get("/tables")
async def list_tables(db: AsyncSession = Depends(get_db)):
    stmt = select(TableMeta)
    result = await db.execute(stmt)
    tables = result.scalars().all()
    return {"tables": [{"id": str(t.id), "table_name": t.table_name, "status": t.status, "explanation": t.generated_explanation} for t in tables]}

@router.post("/tables/rebuild")
async def rebuild_kb(table: Optional[str] = None):
    try:
        if table:
            await process_table(table)
        else:
            await rebuild_all()
        return {"status": "success", "message": "KB rebuild triggered"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seed-rules")
async def seed_all_yaml_rules():
    """Fast endpoint: seed rules from all table YAMLs + global_rules.yaml without re-running LLM pipeline."""
    import os
    import yaml
    from sqlalchemy import delete as sql_delete
    from app.knowledge_base.models import Rule, RuleScope, Project
    from app.knowledge_base.kb_pipeline import load_table_yaml
    
    seeded = {}
    
    async with AsyncSessionLocal() as session:
        # Get project
        proj_res = await session.execute(select(Project).limit(1))
        project = proj_res.scalar_one_or_none()
        if not project:
            raise HTTPException(status_code=400, detail="No project found. Run a full rebuild first.")
        
        # Seed table-level rules from each YAML
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        docs_dir = os.path.join(base_dir, "docs", "tables")
        
        for fname in os.listdir(docs_dir):
            if not fname.endswith(".yaml") or fname.startswith("_"):
                continue
            table_name = fname.replace(".yaml", "")
            try:
                data = load_table_yaml(table_name)
            except Exception:
                continue
            
            yaml_rules = data.get("rules", [])
            if not yaml_rules:
                continue
            
            # Delete old table-scoped rules then insert fresh
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
            seeded[table_name] = len(yaml_rules)
        
        await session.commit()
    
    # Also re-seed global rules
    from app.main import seed_global_rules
    await seed_global_rules()
    
    return {"status": "success", "seeded_table_rules": seeded}


@router.get("/tables/{name}")
async def get_table(name: str, db: AsyncSession = Depends(get_db)):
    stmt = select(TableMeta).options(selectinload(TableMeta.columns)).where(TableMeta.table_name == name)
    result = await db.execute(stmt)
    table = result.scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    return {
        "id": str(table.id),
        "table_name": table.table_name,
        "schema_name": table.schema_name,
        "user_description": table.user_description,
        "generated_explanation": table.generated_explanation,
        "status": table.status,
        "columns": [
            {
                "id": str(c.id),
                "column_name": c.column_name,
                "data_type": c.data_type,
                "is_nullable": c.is_nullable,
                "is_primary_key": c.is_primary_key,
                "is_foreign_key": c.is_foreign_key,
                "user_description": c.user_description,
                "generated_explanation": c.generated_explanation
            } for c in table.columns
        ]
    }

@router.put("/tables/{name}")
async def update_table_desc(name: str, payload: dict, db: AsyncSession = Depends(get_db)):
    stmt = select(TableMeta).where(TableMeta.table_name == name)
    result = await db.execute(stmt)
    table = result.scalar_one_or_none()
    if not table:
        raise HTTPException(status_code=404, detail="Table not found")
    
    if "user_description" in payload:
        table.user_description = payload["user_description"]
        await db.commit()
    return {"status": "success", "message": "Table updated"}

@router.get("/rules")
async def list_rules(scope: Optional[str] = None, scope_identifier: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    stmt = select(Rule)
    if scope:
        stmt = stmt.where(Rule.scope == scope)
    if scope_identifier:
        stmt = stmt.where(Rule.scope_identifier == scope_identifier)
        
    result = await db.execute(stmt)
    rules = result.scalars().all()
    return {"rules": [{"id": str(r.id), "scope": r.scope, "scope_identifier": r.scope_identifier, "rule_text": r.rule_text, "is_active": r.is_active} for r in rules]}

@router.post("/rules")
async def create_rule(payload: dict, db: AsyncSession = Depends(get_db)):
    stmt = select(Project).limit(1)
    res = await db.execute(stmt)
    proj = res.scalar_one_or_none()
    if not proj:
        proj = Project(name="Curriculum DB")
        db.add(proj)
        await db.flush()
        
    new_rule = Rule(
        project_id=proj.id,
        scope=payload["scope"],
        scope_identifier=payload["scope_identifier"],
        rule_text=payload["rule_text"],
        is_active=payload.get("is_active", True)
    )
    db.add(new_rule)
    await db.commit()
    await db.refresh(new_rule)
    return {"status": "success", "rule_id": str(new_rule.id)}

@router.put("/rules/{id}")
async def update_rule(id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    try:
        rule_id = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
        
    stmt = select(Rule).where(Rule.id == rule_id)
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    if "rule_text" in payload:
        rule.rule_text = payload["rule_text"]
    if "is_active" in payload:
        rule.is_active = payload["is_active"]
        
    await db.commit()
    return {"status": "success"}

@router.delete("/rules/{id}")
async def delete_rule(id: str, db: AsyncSession = Depends(get_db)):
    try:
        rule_id = uuid.UUID(id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID")
        
    stmt = select(Rule).where(Rule.id == rule_id)
    result = await db.execute(stmt)
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
        
    await db.delete(rule)
    await db.commit()
    return {"status": "success"}
