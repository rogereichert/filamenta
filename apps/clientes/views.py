from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.core.paginator import Paginator
from decimal import Decimal
from django.db.models import Sum

from .forms import ClienteForm
from .models import Cliente
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
def cliente_create(request):
    form = ClienteForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        cliente = form.save()
        messages.success(request, "Cliente cadastrado com sucesso.")

        if "salvar_continuar" in request.POST:
            return redirect("clientes:update", pk=cliente.pk)

        return redirect("clientes:list")

    return render(request, "clientes/form.html", {"form": form, "titulo": "Novo Cliente"})
def cliente_update(request, pk):
    cliente = get_object_or_404(Cliente, pk=pk)
    form = ClienteForm(request.POST or None, instance=cliente)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Cliente atualizado com sucesso.")

        if "salvar_continuar" in request.POST:
            return redirect("clientes:update", pk=cliente.pk)

        return redirect("clientes:detail", pk=cliente.pk)

    return render(request, "clientes/form.html", {"form": form, "titulo": "Editar Cliente"})
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

