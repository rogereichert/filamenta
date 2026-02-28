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
def filamento_detail(request, pk):
    qs = _annotate_estoque_por_pedido(Filamento.objects.all())
    filamento = get_object_or_404(qs, pk=pk)
    return render(request, "filamentos/detail.html", {"filamento": filamento})
