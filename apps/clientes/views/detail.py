from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from decimal import Decimal
from django.db.models import Sum

from ..forms import ClienteForm
from ..models import Cliente
from apps.pedidos.models import Pedido
def cliente_detail(request, pk):
    cliente = get_object_or_404(
        Cliente.objects.prefetch_related("pedidos"),
        pk=pk
    )

    pedidos = cliente.pedidos.all().order_by("-created_at")

    total_pedidos = pedidos.count()

    # Caso você ainda não tenha valor_total no Pedido,
    # isso NÃO quebra o sistema
    total_gasto = Decimal("0.00")
    try:
        agg = pedidos.aggregate(total=Sum("valor_total"))
        total_gasto = agg["total"] or Decimal("0.00")
    except Exception:
        pass

    context = {
        "cliente": cliente,
        "pedidos": pedidos,
        "total_pedidos": total_pedidos,
        "total_gasto": total_gasto,
    }

    return render(request, "clientes/detail.html", context)
