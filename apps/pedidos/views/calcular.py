from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render

from ..forms import PedidoCalculoForm
from ..models import Pedido, PedidoItem, PedidoItemFilamento
from .helpers import _calc_orcamento, _recalc_pedido_total, _to_decimal


def pedido_calcular(request):
    """
    Tela simples para calcular custo (material + energia + máquina) a partir de:
    - gramas (do slicer)
    - tempo total (do slicer)

    Também permite criar um Pedido em modo ORÇAMENTO a partir do resultado.
    """
    resultado = None

    if request.method == "POST":
        form = PedidoCalculoForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data

            filamento = cd.get("filamento")
            preco_kg = cd["preco_kg"]
            if filamento and getattr(filamento, "preco_kg", None):
                preco_kg = filamento.preco_kg

            desperdicio_pct = cd.get("desperdicio_pct") or Decimal("0")
            gramas = cd["gramas_total"]
            tempo_horas = cd["tempo_total"]
            custo_hora = cd["custo_hora_maquina"]
            energia_fixa = cd["energia_fixa"]

            resultado = _calc_orcamento(
                gramas=gramas,
                desperdicio_pct=desperdicio_pct,
                tempo_horas=tempo_horas,
                preco_kg=preco_kg,
                custo_hora=custo_hora,
                energia=energia_fixa,
            )

            preco_25 = resultado["preco_25"]
            preco_3 = resultado["preco_3"]

            # --- Ação: transformar em Orçamento/Pedido ---
            acao = (request.POST.get("acao") or "").strip()
            if acao in {"criar_25", "criar_3", "criar_manual"}:
                cliente = cd.get("cliente")
                if not cliente:
                    messages.error(request, "Selecione um cliente para criar o orçamento.")
                    return render(request, "pedidos/calcular.html", {"form": form, "resultado": resultado})

                titulo = (cd.get("titulo") or "").strip()
                item_descricao = (cd.get("item_descricao") or "").strip()
                if not item_descricao:
                    messages.error(request, "Informe a descrição do item para criar o orçamento.")
                    return render(request, "pedidos/calcular.html", {"form": form, "resultado": resultado})

                quantidade = cd.get("quantidade") or 1

                if acao == "criar_25":
                    preco_venda = preco_25
                elif acao == "criar_3":
                    preco_venda = preco_3
                else:
                    preco_manual = cd.get("preco_venda_manual")
                    if not preco_manual or preco_manual <= 0:
                        messages.error(request, "Informe um preço manual válido para salvar o orçamento.")
                        return render(request, "pedidos/calcular.html", {"form": form, "resultado": resultado})
                    preco_venda = _to_decimal(preco_manual)

                # quantiza para 2 casas (preço unitário)
                preco_venda_q = _to_decimal(preco_venda).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

                # Para consumo, guarda gramas inteiras (do total cobrado * quantidade)
                gramas_total_consumo = _to_decimal(resultado["gramas_cobradas"]) * Decimal(int(quantidade))
                gramas_int = int(gramas_total_consumo.to_integral_value(rounding=ROUND_HALF_UP))
                if gramas_int < 1:
                    gramas_int = 1

                # Observações
                obs = (
                    "Cálculo (slicer):\n"
                    f"- Gramas (total): {_to_decimal(gramas).quantize(Decimal('0.01'))} g\n"
                    f"- Desperdício: {_to_decimal(desperdicio_pct).quantize(Decimal('0.01'))}%\n"
                    f"- Gramas cobradas: {_to_decimal(resultado['gramas_cobradas']).quantize(Decimal('0.01'))} g\n"
                    f"- Tempo: {_to_decimal(tempo_horas).quantize(Decimal('0.01'))} h\n"
                    f"- Filamento: R$ {_to_decimal(preco_kg).quantize(Decimal('0.01'))}/kg\n"
                    f"- Máquina: R$ {_to_decimal(custo_hora).quantize(Decimal('0.01'))}/h\n"
                    f"- Energia: R$ {_to_decimal(energia_fixa).quantize(Decimal('0.01'))}\n"
                    f"- Material: R$ {_to_decimal(resultado['custo_material']).quantize(Decimal('0.01'))}\n"
                    f"- Máquina: R$ {_to_decimal(resultado['custo_maquina']).quantize(Decimal('0.01'))}\n"
                    f"- Total custo: R$ {_to_decimal(resultado['custo_total']).quantize(Decimal('0.01'))}\n"
                    f"- Preço 2,5x: R$ {_to_decimal(resultado['preco_25']).quantize(Decimal('0.01'))}\n"
                    f"- Preço 3x: R$ {_to_decimal(resultado['preco_3']).quantize(Decimal('0.01'))}\n"
                )

                with transaction.atomic():
                    pedido = Pedido.objects.create(
                        cliente=cliente,
                        status=Pedido.Status.ORCAMENTO,
                        titulo=titulo or item_descricao,
                        observacoes=obs,
                    )

                    item = PedidoItem.objects.create(
                        pedido=pedido,
                        descricao=item_descricao,
                        quantidade=quantidade,
                        preco_unitario=preco_venda_q,
                    )

                    if filamento and gramas_int > 0:
                        PedidoItemFilamento.objects.create(
                            item=item,
                            filamento=filamento,
                            gramas_g=gramas_int,
                        )

                    # ✅ recalcula total do pedido
                    _recalc_pedido_total(pedido)

                messages.success(request, "Orçamento criado! Você já pode ver na lista de pedidos.")
                return redirect("pedidos:detail", pk=pedido.pk)

    else:
        form = PedidoCalculoForm(
            initial={
                "quantidade": 1,
                "preco_kg": Decimal("120.00"),
                "custo_hora_maquina": Decimal("1.30"),
                "energia_fixa": Decimal("0.60"),
                "desperdicio_pct": Decimal("0.00"),
            }
        )

    return render(request, "pedidos/calcular.html", {"form": form, "resultado": resultado})