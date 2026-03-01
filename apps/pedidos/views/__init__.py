from __future__ import annotations

# Public views (imported here to keep urls.py clean)
from .list import pedido_list
from .create import pedido_create
from .update import pedido_update
from .detail import pedido_detail
from .items import (
    pedido_item_add_calculado,
    pedido_item_add,
    pedido_item_remove,
    item_filamento_add,
    item_filamento_remove,
)
from .delete import pedido_delete
from .pdf import pedido_pdf
from .email import pedido_enviar_email
from .calcular import pedido_calcular
from .kanban import pedido_kanban, pedido_kanban_move

__all__ = [
    "pedido_list",
    "pedido_create",
    "pedido_update",
    "pedido_detail",
    "pedido_item_add_calculado",
    "pedido_item_add",
    "pedido_item_remove",
    "item_filamento_add",
    "item_filamento_remove",
    "pedido_delete",
    "pedido_pdf",
    "pedido_enviar_email",
    "pedido_calcular",
    "pedido_kanban",
    "pedido_kanban_move",
]

