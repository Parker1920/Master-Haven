"""Router assembly — main.py includes everything listed here behind the
auth seam (Depends(require_user), a Phase 1 no-op)."""
from ..models import (Account, Asset, Client, ComplianceItem, EnvironmentItem,
                      Flag, Initiative, Person, Task, Template, Transaction)
from .company import router as company_router
from .crud import crud_router
from .documents import assets_router as asset_files_router
from .documents import router as documents_router
from .emit import router as emit_router
from .engagements import router as engagements_router
from .hooks import router as hooks_router

all_routers = [
    company_router,
    engagements_router,
    documents_router,
    asset_files_router,  # POST /api/assets/{id}/receipt (upload)
    hooks_router,        # site → Ops relays, gated by OPS_SERVICE_TOKEN
    emit_router,
    crud_router(Person, prefix="people", entity="person", order_attr="sort"),
    crud_router(Initiative, prefix="initiatives", entity="initiative", order_attr="sort"),
    crud_router(EnvironmentItem, prefix="environment", entity="environment_item", order_attr="sort"),
    crud_router(Flag, prefix="flags", entity="flag"),
    crud_router(Client, prefix="clients", entity="client"),
    crud_router(Task, prefix="tasks", entity="task"),
    crud_router(ComplianceItem, prefix="compliance", entity="compliance_item"),
    crud_router(Account, prefix="accounts", entity="account"),
    crud_router(Transaction, prefix="transactions", entity="transaction"),
    crud_router(Asset, prefix="assets", entity="asset"),
    crud_router(Template, prefix="templates", entity="template"),
]
