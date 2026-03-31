import argparse
import asyncio
import sys
import os
import yaml

# Add backend directory to sys.path to allow imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.knowledge_base.kb_pipeline import process_table, rebuild_all, load_table_yaml
from app.dependencies import init_db, AsyncSessionLocal
from app.kb_pipeline_checkpoint import (
    load_kb_checkpoint, get_remaining_kb_tables, clear_kb_checkpoint,
    print_kb_checkpoint_status
)
try:
    from app.entity_resolution.cache import clear_cache as clear_entity_cache
except ImportError:
    def clear_entity_cache():
        print("  (entity_resolution cache module not found, skipping)")



async def seed_rules_from_yaml(project_name: str = "Curriculum DB"):
    """Seed all YAML table rules & global_rules.yaml into Postgres without re-running LLM."""
    from sqlalchemy import delete as sql_delete, select
    from app.knowledge_base.models import Rule, RuleScope, Project

    async with AsyncSessionLocal() as session:
        proj_res = await session.execute(select(Project).where(Project.name == project_name))
        project = proj_res.scalar_one_or_none()
        if not project:
            print("  [RULES] No project found in DB, skipping rule seeding.")
            return

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        docs_dir = os.path.join(base_dir, "docs", "tables")
        total = 0

        for fname in sorted(os.listdir(docs_dir)):
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
            total += len(yaml_rules)
            print(f"  [RULES] '{table_name}': {len(yaml_rules)} rule(s) seeded.")

        await session.commit()

    # Seed global rules from docs/rules/global_rules.yaml
    global_rules_path = os.path.join(base_dir, "docs", "rules", "global_rules.yaml")
    if os.path.exists(global_rules_path):
        with open(global_rules_path, "r", encoding="utf-8") as f:
            global_data = yaml.safe_load(f)
        global_rules = global_data.get("rules", [])
        if global_rules:
            from sqlalchemy import delete as sql_delete
            from app.knowledge_base.models import Rule, RuleScope
            async with AsyncSessionLocal() as session:
                await session.execute(
                    sql_delete(Rule).where(
                        Rule.scope == RuleScope.DATABASE,
                        Rule.scope_identifier == "global"
                    )
                )
                proj_res = await session.execute(select(Project).where(Project.name == project_name))
                project = proj_res.scalar_one_or_none()
                for rule_text in global_rules:
                    session.add(Rule(
                        project_id=project.id if project else None,
                        scope=RuleScope.DATABASE,
                        scope_identifier="global",
                        rule_text=rule_text,
                        is_active=True
                    ))
                await session.commit()
            total += len(global_rules)
            print(f"  [RULES] global_rules.yaml: {len(global_rules)} global rule(s) seeded.")

    print(f"  [RULES] Done. Total {total} rule(s) seeded.")


async def main():
    parser = argparse.ArgumentParser(description="Rebuild Knowledge Base")
    parser.add_argument("--table", type=str, help="Specific table to rebuild", default=None)
    parser.add_argument("--project", type=str, help="Project name", default="Curriculum DB")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from last checkpoint (skip already-completed tables)"
    )
    parser.add_argument(
        "--clear-checkpoint",
        action="store_true",
        help="Clear checkpoint and rebuild all tables from scratch"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show current checkpoint status"
    )
    parser.add_argument(
        "--rules-only",
        action="store_true",
        help="Only re-seed rules from YAML files (skip LLM pipeline)"
    )

    args = parser.parse_args()

    # Show checkpoint status if requested
    if args.status:
        print_kb_checkpoint_status()
        return

    # Ensure DB tables exist
    await init_db()

    # Rules-only mode: fast re-seed without running LLM pipeline
    if args.rules_only:
        print("=== Rules-Only Mode: Seeding rules from YAML files ===")
        await seed_rules_from_yaml(args.project)
        print("Done.")
        return

    # Clear checkpoint if requested
    if args.clear_checkpoint:
        clear_kb_checkpoint()
        print("Checkpoint cleared - will rebuild all tables\n")

    # Determine which tables to rebuild
    if args.table:
        print(f"Starting KB Rebuild for table: {args.table}")
        await process_table(args.table, args.project)
    else:
        if args.resume:
            print("[RESUME MODE] Resuming KB rebuild from checkpoint\n")
        print(f"Starting KB Rebuild for all tables...")
        await rebuild_all(args.project, use_checkpoint=args.resume or False)

    # Clear entity resolution cache since KB has changed
    print("\n[CACHE] Clearing entity resolution cache (KB was rebuilt)...")
    clear_entity_cache()

    # Seed rules from YAML files (table-level + global)
    print("\n[RULES] Seeding rules from YAML files...")
    await seed_rules_from_yaml(args.project)

    print("KB Rebuild Finished.")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
