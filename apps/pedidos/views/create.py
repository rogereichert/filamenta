from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.clientes.models import Cliente
from ..forms import PedidoForm
from .helpers import _recalc_pedido_total


def pedido_create(request):
    cliente_id = (request.GET.get("cliente") or "").strip()
    cliente_initial = None
    if cliente_id.isdigit():
        cliente_initial = get_object_or_404(Cliente, pk=int(cliente_id))

    if request.method == "POST":
        form = PedidoForm(request.POST)
        if form.is_valid():
            pedido = form.save()

            # Define ordem inicial no Kanban (fim da coluna)
            if pedido.kanban_order == 0:
                from django.db.models import Max
                max_ord = (
                    Pedido.objects.filter(status=pedido.status)
                    .exclude(pk=pedido.pk)
                    .aggregate(m=Max("kanban_order"))["m"]
                    or 0
                )
                pedido.kanban_order = int(max_ord) + 1
                pedido.save(update_fields=["kanban_order"])
            _recalc_pedido_total(pedido)
            # ✅ se criou já como ENTREGUE (raro), baixa estoque
            pedido.baixar_estoque_se_necessario()

            messages.success(request, "Pedido criado com sucesso.")
            return redirect("pedidos:detail", pk=pedido.pk)
    else:
        form = PedidoForm(initial={"cliente": cliente_initial} if cliente_initial else None)

    return render(request, "pedidos/form.html", {
        "form": form,
        "modo": "novo",
    })

