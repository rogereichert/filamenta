from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.db import models
from django.shortcuts import get_object_or_404, redirect

from ..forms import (
    PedidoItemForm,
    PedidoItemFilamentoForm,
    PedidoItemCalculoAddForm,
)
from ..models import Pedido, PedidoItem, PedidoItemFilamento
from .helpers import _to_decimal, _calc_orcamento, _recalc_pedido_total


def pedido_item_add_calculado(request, pk):
    """Adiciona um item ao pedido usando o mesmo cálculo do menu Calcular Pedido.

    Isso resolve a inconsistência: ao criar um pedido e adicionar itens, você
    não precisa calcular manualmente o preço unitário.
    """
    pedido = get_object_or_404(Pedido, pk=pk)
    if request.method != "POST":
        return redirect("pedidos:detail", pk=pedido.pk)

    form = PedidoItemCalculoAddForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Revise os campos do cálculo (item calculado).")
        return redirect("pedidos:detail", pk=pedido.pk)

    cd = form.cleaned_data
    filamento = cd.get("filamento")
    preco_kg = cd["preco_kg"]
    if filamento and getattr(filamento, "preco_kg", None):
        preco_kg = filamento.preco_kg

    resultado = _calc_orcamento(
        gramas=cd["gramas_total"],
        desperdicio_pct=cd.get("desperdicio_pct") or Decimal("0"),
        tempo_horas=cd["tempo_total"],
        preco_kg=preco_kg,
        custo_hora=cd["custo_hora_maquina"],
        energia=cd["energia_fixa"],
    )

    multiplicador = cd.get("multiplicador")
    if multiplicador == "3":
        preco_unitario = resultado["preco_3"]
    elif multiplicador == "manual":
        preco_manual = cd.get("preco_venda_manual")
        if not preco_manual or preco_manual <= 0:
            messages.error(request, "Informe um preço manual válido (maior que 0).")
            return redirect("pedidos:detail", pk=pedido.pk)
        preco_unitario = _to_decimal(preco_manual)
    else:
        preco_unitario = resultado["preco_25"]

    # cria item
    item = PedidoItem.objects.create(
        pedido=pedido,
        descricao=cd["descricao"].strip(),
        quantidade=cd["quantidade"],
        preco_unitario=preco_unitario,
    )

    # registra consumo total (por item) se filamento foi selecionado
    if filamento:
        gramas_total = resultado["gramas_cobradas"] * Decimal(cd["quantidade"])
        gramas_int = int(gramas_total.to_integral_value(rounding=ROUND_HALF_UP))
        if gramas_int < 1:
            gramas_int = 1
        PedidoItemFilamento.objects.create(
            item=item,
            filamento=filamento,
            gramas_g=gramas_int,
        )

    # log leve no pedido (útil p/ auditoria)
    log = (
        f"[CALC] {item.descricao} | g={resultado['gramas']:.2f} | "
        f"h={resultado['tempo_horas']:.2f} | kg={resultado['preco_kg']:.2f} | "
        f"mat={resultado['custo_material']:.2f} maq={resultado['custo_maquina']:.2f} "
        f"ene={resultado['custo_energia']:.2f} total={resultado['custo_total']:.2f} | "
        f"unit={_to_decimal(preco_unitario):.2f}\n"
    )
    pedido.observacoes = (pedido.observacoes or "") + log
    pedido.save(update_fields=["observacoes"])

    messages.success(
        request,
        f"Item calculado adicionado. Custo: R$ {resultado['custo_total']:.2f} | "
        f"Preço unit.: R$ {_to_decimal(preco_unitario):.2f}"
    )
    return redirect("pedidos:detail", pk=pedido.pk)


def pedido_item_add(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)
    form = PedidoItemForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.pedido = pedido
        item.save()
        _recalc_pedido_total(pedido)
        messages.success(request, "Item adicionado ao pedido.")
    else:
        messages.error(request, "Verifique os campos do item (descrição, quantidade e preço).")

    return redirect("pedidos:detail", pk=pedido.pk)


def pedido_item_remove(request, pk, item_id):
    pedido = get_object_or_404(Pedido, pk=pk)
    item = get_object_or_404(PedidoItem, pk=item_id, pedido=pedido)
    item.delete()
    _recalc_pedido_total(pedido)
    messages.success(request, "Item removido.")
    return redirect("pedidos:detail", pk=pedido.pk)


def item_filamento_add(request, pk, item_id):
    pedido = get_object_or_404(Pedido, pk=pk)
    item = get_object_or_404(PedidoItem, pk=item_id, pedido=pedido)

    form = PedidoItemFilamentoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        itf = form.save(commit=False)
        itf.item = item

        # ✅ Bloqueia consumo acima do estoque disponível (considera reservas de outros pedidos)
        fil = itf.filamento

        # total já existente no pedido para esse filamento
        total_atual = (
            PedidoItemFilamento.objects.filter(item__pedido=pedido, filamento=fil)
            .aggregate(total=models.Sum("gramas_g"))["total"]
            or 0
        )
        total_novo = int(total_atual) + int(itf.gramas_g or 0)

        disponivel = (
            fil.disponivel_g(exclude_pedido=pedido)
            if hasattr(fil, "disponivel_g")
            else int(fil.peso_atual_g)
        )

        if total_novo > disponivel:
            messages.error(
                request,
                f"Estoque insuficiente para {fil}. Você tentou totalizar {total_novo}g neste pedido, "
                f"mas o disponível é {disponivel}g."
            )
            return redirect("pedidos:detail", pk=pedido.pk)

        itf.save()
        messages.success(request, "Consumo de filamento adicionado ao item.")
    else:
        messages.error(request, "Verifique o filamento e as gramas informadas.")

    return redirect("pedidos:detail", pk=pedido.pk)


def item_filamento_remove(request, pk, item_id, if_id):
    pedido = get_object_or_404(Pedido, pk=pk)
    item = get_object_or_404(PedidoItem, pk=item_id, pedido=pedido)
    itf = get_object_or_404(PedidoItemFilamento, pk=if_id, item=item)
    itf.delete()
    messages.success(request, "Consumo de filamento removido do item.")
    return redirect("pedidos:detail", pk=pedido.pk)