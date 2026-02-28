from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from decimal import Decimal
from django.db.models import Sum

from ..forms import ClienteForm
from ..models import Cliente
from apps.pedidos.models import Pedido
def cliente_create(request):
    form = ClienteForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        cliente = form.save()
        messages.success(request, "Cliente cadastrado com sucesso.")

        if "salvar_continuar" in request.POST:
            return redirect("clientes:update", pk=cliente.pk)

        return redirect("clientes:list")

    return render(request, "clientes/form.html", {"form": form, "titulo": "Novo Cliente"})
