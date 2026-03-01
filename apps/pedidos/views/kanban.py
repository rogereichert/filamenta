from __future__ import annotations

import json

from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from ..models import Pedido


def _apply_kanban_update(pedido: Pedido, new_status: str, new_order: int | None, errors: list[str]) -> None:
    allowed = {
        Pedido.Status.RASCUNHO,
        Pedido.Status.ORCAMENTO,
        Pedido.Status.ABERTO,
        Pedido.Status.EM_PRODUCAO,
        Pedido.Status.ENTREGUE,
    }
    if new_status not in allowed:
        errors.append(f"Status inválido para kanban: {new_status}")
        return

    pedido.status = new_status
    if isinstance(new_order, int):
        pedido.kanban_order = new_order

    try:
        # full_clean dispara validações (ex.: bloquear EM_PRODUCAO sem estoque)
        pedido.full_clean()
        pedido.save()
    except Exception as e:
        errors.append(str(e))


@login_required
def pedido_kanban(request: HttpRequest):
    # Colunas do kanban (mantém separado backlog vs fluxo principal)
    columns = [
        (Pedido.Status.RASCUNHO, "Rascunho"),
        (Pedido.Status.ORCAMENTO, "Orçamento"),
        (Pedido.Status.ABERTO, "Aberto"),
        (Pedido.Status.EM_PRODUCAO, "Em produção"),
        (Pedido.Status.ENTREGUE, "Entregue"),
    ]

    pedidos = (
        Pedido.objects.exclude(status=Pedido.Status.CANCELADO)
        .select_related("cliente")
        .order_by("status", "kanban_order", "prazo_entrega", "-created_at")
    )

    by_status = {key: [] for key, _ in columns}
    for p in pedidos:
        by_status.setdefault(p.status, []).append(p)

    return render(
        request,
        "pedidos/kanban.html",
        {
            "columns": columns,
            "by_status": by_status,
        },
    )


@require_POST
@login_required
@transaction.atomic
def pedido_kanban_move(request: HttpRequest):
    """Move pedido entre colunas (drag-and-drop) e ajusta ordenação.

    Payload aceito:
    - {pedido_id, status, order}
    - {updates: [{pedido_id, status, order}, ...]}
    """
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"ok": False, "error": "Payload inválido."}, status=400)

    updates = payload.get("updates")
    errors: list[str] = []

    if isinstance(updates, list) and updates:
        for u in updates:
            pid = u.get("pedido_id")
            st = u.get("status")
            order = u.get("order")
            if not pid or not st:
                continue
            pedido = get_object_or_404(Pedido, pk=pid)
            _apply_kanban_update(pedido, st, order, errors)

        if errors:
            return JsonResponse({"ok": False, "error": "\n".join(errors)}, status=400)
        return JsonResponse({"ok": True})

    pedido_id = payload.get("pedido_id")
    new_status = payload.get("status")
    new_order = payload.get("order")

    if not pedido_id or not new_status:
        return JsonResponse({"ok": False, "error": "Campos obrigatórios: pedido_id, status."}, status=400)

    pedido = get_object_or_404(Pedido, pk=pedido_id)
    _apply_kanban_update(pedido, new_status, new_order, errors)

    if errors:
        return JsonResponse({"ok": False, "error": "\n".join(errors)}, status=400)

    return JsonResponse({"ok": True})
