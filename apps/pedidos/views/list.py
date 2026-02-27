from __future__ import annotations

from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render

from ..models import Pedido


def pedido_list(request):
    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    page_number = request.GET.get("page") or 1

    qs = Pedido.objects.select_related("cliente").all()

    if q:
        qs = qs.filter(
            Q(cliente__nome__icontains=q) |
            Q(id__icontains=q) |
            Q(titulo__icontains=q)
        )

    if status:
        qs = qs.filter(status=status)

    qs = qs.order_by("-created_at")

    paginator = Paginator(qs, 7)
    page_obj = paginator.get_page(page_number)

    return render(request, "pedidos/list.html", {
        "pedidos": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "status": status,
        "total": qs.count(),
        "status_choices": Pedido.Status.choices,
    })

