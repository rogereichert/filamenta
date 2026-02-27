from django.apps import apps
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, IntegerField, F
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce, Greatest
from django.shortcuts import get_object_or_404, redirect, render

from .forms import FilamentoForm
from .models import Filamento
def _get_reserva_status():
    """
    Status do Pedido que contam como "reserva" (consumo futuro).
    Aqui: tudo que NÃO é entregue/cancelado.
    """
    try:
        Pedido = apps.get_model("pedidos", "Pedido")
        return [
            Pedido.Status.RASCUNHO,
            Pedido.Status.ORCAMENTO,
            Pedido.Status.ABERTO,
            Pedido.Status.EM_PRODUCAO,
        ]
    except Exception:
        return ["rascunho", "orcamento", "aberto", "em_producao"]
def _annotate_estoque_por_pedido(qs):
    """
    Anota:
      reservado_g  = soma de gramas consumidas (PedidoItemFilamento) em pedidos com status de reserva
      disponivel_g = peso_atual_g - reservado_g (mínimo 0)
    """
    RESERVA_STATUS = _get_reserva_status()
    related_name = "consumos_itens"  # FK do PedidoItemFilamento -> Filamento

    try:
        apps.get_model("pedidos", "PedidoItemFilamento")  # sanity check

        return (
            qs.annotate(
                reservado_g=Coalesce(
                    Sum(
                        f"{related_name}__gramas_g",
                        # ✅ caminho correto: consumos_itens -> item -> pedido -> status
                        filter=Q(**{f"{related_name}__item__pedido__status__in": RESERVA_STATUS}),
                    ),
                    0,
                    output_field=IntegerField(),
                )
            )
            .annotate(
                disponivel_g=Greatest(
                    ExpressionWrapper(
                        F("peso_atual_g") - F("reservado_g"),
                        output_field=IntegerField(),
                    ),
                    0,
                )
            )
        )
    except Exception:
        # fallback (se você usasse um model antigo de reservas)
        return (
            qs.annotate(
                reservado_g=Coalesce(
                    Sum("reservas__gramas_g"),
                    0,
                    output_field=IntegerField(),
                )
            )
            .annotate(
                disponivel_g=Greatest(
                    ExpressionWrapper(
                        F("peso_atual_g") - F("reservado_g"),
                        output_field=IntegerField(),
                    ),
                    0,
                )
            )
        )
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
def filamento_detail(request, pk):
    qs = _annotate_estoque_por_pedido(Filamento.objects.all())
    filamento = get_object_or_404(qs, pk=pk)
    return render(request, "filamentos/detail.html", {"filamento": filamento})
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
def filamento_delete(request, pk):
    filamento = get_object_or_404(Filamento, pk=pk)

    if request.method == "POST":
        confirm = (request.POST.get("confirm") or "").strip().upper()
        if confirm != "EXCLUIR":
            messages.error(request, "Confirmação inválida. Digite EXCLUIR para remover.")
            return redirect("filamentos:delete", pk=filamento.pk)

        filamento.delete()
        messages.success(request, "Filamento removido com sucesso.")
        return redirect("filamentos:list")

    return render(request, "filamentos/confirm_delete.html", {"filamento": filamento})
