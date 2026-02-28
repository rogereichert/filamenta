from django.apps import apps
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, IntegerField, F
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce, Greatest
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import FilamentoForm
from ..models import Filamento
def filamento_create(request):
    form = FilamentoForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        filamento = form.save(commit=False)

        if not filamento.peso_atual_g and filamento.peso_inicial_g:
            filamento.peso_atual_g = filamento.peso_inicial_g

        if not filamento.peso_inicial_g and filamento.peso_atual_g:
            filamento.peso_inicial_g = filamento.peso_atual_g

        if filamento.peso_inicial_g == 0 and filamento.peso_atual_g == 0:
            messages.error(request, "Informe pelo menos o peso inicial ou o peso atual (em gramas).")
            return render(request, "filamentos/form.html", {"form": form, "titulo": "Novo Filamento"})

        filamento.save()
        messages.success(request, "Filamento cadastrado com sucesso.")
        return redirect("filamentos:list")

    return render(request, "filamentos/form.html", {"form": form, "titulo": "Novo Filamento"})
