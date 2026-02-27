from __future__ import annotations

from django.contrib import messages
from django.forms import inlineformset_factory
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import PedidoForm, PedidoItemForm
from ..models import Pedido, PedidoItem
from .helpers import _recalc_pedido_total


def pedido_update(request, pk):
    """
    (FALLBACK) Você pode manter essa tela, mas com a Opção A
    você vai praticamente usar só o /pedidos/<id>/ (detail/OS).
    """
    pedido = get_object_or_404(Pedido, pk=pk)

    ItensFormSet = inlineformset_factory(
        parent_model=Pedido,
        model=PedidoItem,
        form=PedidoItemForm,
        extra=1,
        can_delete=True,
        fields=("descricao", "quantidade", "preco_unitario"),
    )

    if request.method == "POST":
        form = PedidoForm(request.POST, instance=pedido)
        itens_formset = ItensFormSet(request.POST, instance=pedido)

        if form.is_valid() and itens_formset.is_valid():
            pedido = form.save()
            itens_formset.save()

            # ✅ baixa estoque se virou ENTREGUE
            pedido.baixar_estoque_se_necessario()

            _recalc_pedido_total(pedido)

            messages.success(request, "Pedido atualizado com sucesso.")
            return redirect("pedidos:detail", pk=pedido.pk)

        messages.error(request, "Revise os campos do pedido e dos itens.")
    else:
        form = PedidoForm(instance=pedido)
        itens_formset = ItensFormSet(instance=pedido)

    return render(request, "pedidos/form.html", {
        "form": form,
        "modo": "editar",
        "pedido": pedido,
        "itens_formset": itens_formset,
    })

