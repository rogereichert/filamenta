from __future__ import annotations

from django.contrib import messages
from django.db import transaction
from django.db.models import F, Max, Sum
from django.db.models.functions import Coalesce
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_GET, require_POST
from decimal import Decimal
from django.db.models import Sum, Value, DecimalField, IntegerField
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
        .prefetch_related("itens")
        .annotate(
            # ✅ consumo total (gramas) -> inteiro
            consumo_total_g=Coalesce(
                Sum("itens__filamentos__gramas_g"),
                Value(0, output_field=IntegerField()),
                output_field=IntegerField(),
            ),
            # ✅ tempo total (horas) -> decimal
            tempo_total_h=Coalesce(
                Sum("itens__tempo_horas"),
                Value(Decimal("0.00"), output_field=DecimalField(max_digits=10, decimal_places=2)),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            ),
        )
        .order_by("status", "kanban_order", "-id")
    )

    colunas = {
        "RASCUNHO": [],
        "ORCAMENTO": [],
        "ABERTO": [],
        "EM_PRODUCAO": [],
        "ENTREGUE": [],
    }

    for p in qs:
        # garante chave existente (caso algum status antigo exista no banco)
        colunas.setdefault(p.status, [])
        colunas[p.status].append(p)

    return render(request, "pedidos/kanban.html", {"colunas": colunas})


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
