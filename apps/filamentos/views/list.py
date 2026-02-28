from django.apps import apps
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, IntegerField, F
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce, Greatest
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import FilamentoForm
from ..models import Filamento
from .helpers import _annotate_estoque_por_pedido
def filamento_list(request):
    q = (request.GET.get("q") or "").strip()
    sort = (request.GET.get("sort") or "nome").strip()
    page_number = request.GET.get("page") or 1

    qs = _annotate_estoque_por_pedido(Filamento.objects.all())

    if q:
        qs = qs.filter(
            Q(nome__icontains=q) |
            Q(cor__icontains=q) |
            Q(material__icontains=q)
        )

    sort_map = {
        "nome": "nome",
        "recentes": "-created_at",
        "atualizados": "-updated_at",
        "menor_estoque": "disponivel_g",
    }
    qs = qs.order_by(sort_map.get(sort, "nome"))

    total_filamentos = Filamento.objects.count()
    total_filtrados = qs.count()

    paginator = Paginator(qs, 10)
    page_obj = paginator.get_page(page_number)

    context = {
        "filamentos": page_obj.object_list,
        "page_obj": page_obj,
        "q": q,
        "sort": sort,
        "total_filamentos": total_filamentos,
        "total_filtrados": total_filtrados,
    }
    return render(request, "filamentos/list.html", context)
