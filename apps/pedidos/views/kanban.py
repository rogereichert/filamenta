from __future__ import annotations

from django.contrib import messages
from django.db import transaction
from django.db.models import F, Max, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST

from ..models import Pedido


KANBAN_STATUSES = [
    Pedido.Status.RASCUNHO,
    Pedido.Status.ORCAMENTO,
    Pedido.Status.ABERTO,
    Pedido.Status.EM_PRODUCAO,
    Pedido.Status.ENTREGUE,
]


@require_GET
def pedido_kanban(request):
    qs = (
        Pedido.objects.select_related("cliente")
        .annotate(
            total_gramas=Coalesce(Sum("itens__filamentos__gramas_g"), 0),
            tempo_total_h=Coalesce(Sum("itens__tempo_horas"), 0),
        )
        .order_by("status", "kanban_order", "-prioridade", "-id")
    )

    colunas = {s: [] for s in KANBAN_STATUSES}
    for p in qs:
        if p.status in colunas:
            colunas[p.status].append(p)

    return render(
        request,
        "pedidos/kanban.html",
        {
            "colunas": colunas,
            "status_list": KANBAN_STATUSES,
        },
    )


@require_POST
@transaction.atomic
def pedido_kanban_mover(request, pk: int):
    pedido = get_object_or_404(Pedido, pk=pk)

    novo_status = (request.POST.get("status") or "").strip()
    novo_order = request.POST.get("order")

    if novo_status not in KANBAN_STATUSES:
        return JsonResponse({"ok": False, "error": "Status inválido."}, status=400)

    try:
        novo_order_int = int(novo_order) if novo_order is not None else 0
    except Exception:
        novo_order_int = 0

    # Atualiza status e ordem
    pedido.status = novo_status
    pedido.kanban_order = max(0, novo_order_int)

    try:
        # Aqui mantém validações de estoque etc (clean/full_clean)
        pedido.full_clean()
        pedido.save(update_fields=["status", "kanban_order"])
    except Exception as e:
        return JsonResponse({"ok": False, "error": str(e)}, status=400)

    return JsonResponse({"ok": True})
