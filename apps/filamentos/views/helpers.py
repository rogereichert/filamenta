from django.apps import apps
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, IntegerField, F
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce, Greatest
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import FilamentoForm
from ..models import Filamento
def _get_reserva_status():
    """
    Status do Pedido que contam como "reserva" (consumo futuro).
    Aqui: tudo que NÃO é entregue/cancelado.
    """
    try:
        Pedido = apps.get_model("pedidos", "Pedido")
        return [
            Pedido.Status.RASCUNHO,
            Pedido.Status.ORCAMENTO,
            Pedido.Status.ABERTO,
            Pedido.Status.EM_PRODUCAO,
        ]
    except Exception:
        return ["rascunho", "orcamento", "aberto", "em_producao"]

def _annotate_estoque_por_pedido(qs):
    """
    Anota:
      reservado_g  = soma de gramas consumidas (PedidoItemFilamento) em pedidos com status de reserva
      disponivel_g = peso_atual_g - reservado_g (mínimo 0)
    """
    RESERVA_STATUS = _get_reserva_status()
    related_name = "consumos_itens"  # FK do PedidoItemFilamento -> Filamento

    try:
        apps.get_model("pedidos", "PedidoItemFilamento")  # sanity check

        return (
            qs.annotate(
                reservado_g=Coalesce(
                    Sum(
                        f"{related_name}__gramas_g",
                        # ✅ caminho correto: consumos_itens -> item -> pedido -> status
                        filter=Q(**{f"{related_name}__item__pedido__status__in": RESERVA_STATUS}),
                    ),
                    0,
                    output_field=IntegerField(),
                )
            )
            .annotate(
                disponivel_g=Greatest(
                    ExpressionWrapper(
                        F("peso_atual_g") - F("reservado_g"),
                        output_field=IntegerField(),
                    ),
                    0,
                )
            )
        )
    except Exception:
        # fallback (se você usasse um model antigo de reservas)
        return (
            qs.annotate(
                reservado_g=Coalesce(
                    Sum("reservas__gramas_g"),
                    0,
                    output_field=IntegerField(),
                )
            )
            .annotate(
                disponivel_g=Greatest(
                    ExpressionWrapper(
                        F("peso_atual_g") - F("reservado_g"),
                        output_field=IntegerField(),
                    ),
                    0,
                )
            )
        )
