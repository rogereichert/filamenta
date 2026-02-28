from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from decimal import Decimal
from django.db.models import Sum

from ..forms import ClienteForm
from ..models import Cliente
from apps.pedidos.models import Pedido
def cliente_delete(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)

    if request.method == "POST":
        confirm = (request.POST.get("confirm") or "").strip().upper()
        if confirm != "EXCLUIR":
            messages.error(request, "Confirmação inválida. Digite EXCLUIR para remover.")
            return redirect("clientes:delete", pk=cliente.pk)

        cliente.delete()
        messages.success(request, "Cliente removido com sucesso.")
        return redirect("clientes:list")

    return render(request, "clientes/confirm_delete.html", {"cliente": cliente})
