from django.apps import apps
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, IntegerField, F
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce, Greatest
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import FilamentoForm
from ..models import Filamento
def filamento_update(request, pk):
    filamento = get_object_or_404(Filamento, pk=pk)
    form = FilamentoForm(request.POST or None, instance=filamento)

    if request.method == "POST" and form.is_valid():
        obj = form.save(commit=False)

        if obj.peso_inicial_g == 0 and obj.peso_atual_g == 0:
            messages.error(request, "Informe pelo menos o peso inicial ou o peso atual (em gramas).")
            return render(request, "filamentos/form.html", {"form": form, "titulo": "Editar Filamento"})

        obj.save()
        messages.success(request, "Filamento atualizado com sucesso.")
        return redirect("filamentos:detail", pk=obj.pk)

    return render(request, "filamentos/form.html", {"form": form, "titulo": "Editar Filamento"})
