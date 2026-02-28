from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from decimal import Decimal
from django.db.models import Sum

from ..forms import ClienteForm
from ..models import Cliente
from apps.pedidos.models import Pedido
def cliente_list(request):
    q = (request.GET.get("q") or "").strip()
    sort = (request.GET.get("sort") or "nome").strip()
    page_number = request.GET.get("page") or 1

    qs = Cliente.objects.all()

    if q:
        qs = qs.filter(
            Q(nome__icontains=q) |
            Q(telefone__icontains=q) |
            Q(email__icontains=q)
        )

    sort_map = {
        "nome": "nome",
        "recentes": "-created_at",
        "atualizados": "-updated_at",
    }
    qs = qs.order_by(sort_map.get(sort, "nome"))

    total_clientes = Cliente.objects.count()
    total_filtrados = qs.count()

    paginator = Paginator(qs, 15)  # <-- troque 15 para 10/20 se preferir
    page_obj = paginator.get_page(page_number)

    context = {
        "clientes": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "sort": sort,
        "total_clientes": total_clientes,
        "total_filtrados": total_filtrados,
    }
    return render(request, "clientes/list.html", context)
