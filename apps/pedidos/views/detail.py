from __future__ import annotations

from django.contrib import messages
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import (
    PedidoForm,
    PedidoItemForm,
    PedidoItemFilamentoForm,
    PedidoItemCalculoAddForm,
)
from ..models import Pedido, PedidoItem, PedidoItemFilamento
from .helpers import _recalc_pedido_total


def pedido_detail(request, pk):
    """
    ✅ Tela principal (OS). Aqui fica:
    - visualizar pedido
    - adicionar/remover itens
    - adicionar/remover consumos
    - gerar PDF
    - editar cabeçalho via MODAL (sem sair da tela)
    """
    pedido = get_object_or_404(Pedido.objects.select_related("cliente"), pk=pk)

    form_item = PedidoItemForm()
    form_item_filamento = PedidoItemFilamentoForm()
    form_header = PedidoForm(instance=pedido)
    form_item_calc = PedidoItemCalculoAddForm()

    # ✅ POST do modal: atualizar cabeçalho
    if request.method == "POST" and (request.POST.get("acao") == "update_header"):
        form_header = PedidoForm(request.POST, instance=pedido)

        if form_header.is_valid():
            pedido = form_header.save()

            # ✅ baixa estoque se virou ENTREGUE
            pedido.baixar_estoque_se_necessario()

            _recalc_pedido_total(pedido)
            messages.success(request, "Cabeçalho do pedido atualizado com sucesso.")
            return redirect("pedidos:detail", pk=pedido.pk)

        messages.error(request, "Revise os campos do pedido (cabeçalho).")

    itens = (
        pedido.itens
        .prefetch_related("filamentos__filamento")
        .order_by("id")
    )

    total_gramas = (
        PedidoItemFilamento.objects
        .filter(item__pedido=pedido)
        .aggregate(total=Sum("gramas_g"))
    )["total"] or 0

    return render(request, "pedidos/detail.html", {
        "pedido": pedido,
        "itens": itens,
        "total_gramas": total_gramas,
        "form_item": form_item,
        "form_item_filamento": form_item_filamento,
        "form_header": form_header,
        "form_item_calc": form_item_calc,
    })

