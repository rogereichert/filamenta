from __future__ import annotations

from decimal import Decimal

from ..models import Pedido


def _to_decimal(v) -> Decimal:
    """
    Converte entrada BR/EN para Decimal.
    Aceita: 5,50 | 5.50 | 5 | "" | None
    """
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    s = str(v).strip()
    if not s:
        return Decimal("0")
    # suporte BR: "1.234,56" -> "1234.56"
    s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")
def _recalc_pedido_total(pedido: Pedido) -> None:
    """
    Recalcula e salva pedido.valor_total com base em:
    soma(itens.subtotal) - desconto + frete + taxa_extra
    """
    itens_total = Decimal("0")
    for it in pedido.itens.all():
        itens_total += (it.subtotal or Decimal("0"))

    desconto = _to_decimal(pedido.desconto)
    frete = _to_decimal(pedido.frete)
    taxa = _to_decimal(pedido.taxa_extra)

    total = (itens_total - desconto + frete + taxa)
    if total < 0:
        total = Decimal("0")

    pedido.valor_total = total
    pedido.save(update_fields=["valor_total"])
def _calc_orcamento(
    *,
    gramas: Decimal,
    desperdicio_pct: Decimal,
    tempo_horas: Decimal,
    preco_kg: Decimal,
    custo_hora: Decimal,
    energia: Decimal,
) -> dict:
    """Mesma lógica do menu 'Calcular Pedido'.

    Retorna valores já quantizados (2 casas) para dinheiro e com campos úteis.
    """
    fator = (Decimal("1") + (desperdicio_pct / Decimal("100")))
    gramas_cobradas = (gramas * fator)

    custo_material = (gramas_cobradas * (preco_kg / Decimal("1000")))
    custo_maquina = (tempo_horas * custo_hora)
    custo_total = (custo_material + custo_maquina + energia)

    preco_25 = (custo_total * Decimal("2.5"))
    preco_3 = (custo_total * Decimal("3"))

    q = Decimal("0.01")
    return {
        "gramas": gramas,
        "gramas_cobradas": gramas_cobradas,
        "tempo_horas": tempo_horas,
        "preco_kg": preco_kg,
        "custo_material": custo_material.quantize(q),
        "custo_maquina": custo_maquina.quantize(q),
        "custo_energia": energia.quantize(q),
        "custo_total": custo_total.quantize(q),
        "preco_25": preco_25.quantize(q),
        "preco_3": preco_3.quantize(q),
    }

