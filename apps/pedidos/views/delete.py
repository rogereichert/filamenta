from __future__ import annotations

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from ..models import Pedido


def pedido_delete(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk)

    if request.method == "POST":
        pedido.delete()
        messages.success(request, "Pedido excluído.")
        return redirect("pedidos:list")

    return render(request, "pedidos/confirm_delete.html", {"pedido": pedido})

