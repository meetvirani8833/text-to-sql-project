import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Initialize DB tables
    from app.dependencies import init_db
    print("Initializing database...")
    await init_db()
    print("Database initialized.")
    
    # Seed global rules from docs/rules/global_rules.yaml
    await seed_global_rules()
    
    yield
    # Shutdown
    print("Shutting down...")


async def seed_global_rules():
    """Reads docs/rules/global_rules.yaml and upserts them as database-scope rules."""
    import os
    import yaml
    from app.dependencies import AsyncSessionLocal
    from app.knowledge_base.models import Rule, RuleScope
    from sqlalchemy import select, delete
    
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rules_path = os.path.join(base_dir, "docs", "rules", "global_rules.yaml")
    
    if not os.path.exists(rules_path):
        print("  No global_rules.yaml found, skipping.")
        return
    
    with open(rules_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    
    rules_list = data.get("rules", [])
    if not rules_list:
        return
    
    async with AsyncSessionLocal() as session:
        # Get or create the default project
        from app.knowledge_base.models import Project
        proj_res = await session.execute(select(Project).where(Project.name == "Curriculum DB"))
        project = proj_res.scalar_one_or_none()
        if not project:
            project = Project(name="Curriculum DB", description="University Curriculum Database")
            session.add(project)
            await session.flush()

        # Clear old global rules and re-insert fresh
        await session.execute(
            delete(Rule).where(
                Rule.scope == RuleScope.DATABASE,
                Rule.scope_identifier == "global"
            )
        )
        for rule_text in rules_list:
            session.add(Rule(
                project_id=project.id,
                scope=RuleScope.DATABASE,
                scope_identifier="global",
                rule_text=rule_text,
                is_active=True
            ))
        await session.commit()
    print(f"  Seeded {len(rules_list)} global rules from global_rules.yaml.")


# Setup LangSmith Tracing if API key is provided
if settings.LANGSMITH_API_KEY:
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    os.environ["LANGCHAIN_PROJECT"] = settings.LANGSMITH_PROJECT

app = FastAPI(title="Curriculum Agent API", lifespan=lifespan)

# Add CORS middleware for local frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include routers
from app.api.kb_routes import router as kb_router
from app.api.chat_routes import router as chat_router

app.include_router(kb_router)
app.include_router(chat_router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
