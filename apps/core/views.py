from django.apps import apps
from django.db.models import Count, Q
from django.shortcuts import render
def dashboard(request):
    # Clientes
    Cliente = apps.get_model("clientes", "Cliente")
    total_clientes = Cliente.objects.count()

    # Pedidos (resiliente)
    total_pedidos = 0
    entregues = 0
    em_producao = 0
    abertos = 0
    cancelados = 0

    try:
        Pedido = apps.get_model("pedidos", "Pedido")

        kpis = Pedido.objects.aggregate(
            total=Count("id"),
            entregues=Count("id", filter=Q(status=Pedido.Status.ENTREGUE)),
            em_producao=Count("id", filter=Q(status=Pedido.Status.EM_PRODUCAO)),
            abertos=Count("id", filter=Q(status=Pedido.Status.ABERTO)),
            cancelados=Count("id", filter=Q(status=Pedido.Status.CANCELADO)),
        )

        total_pedidos = kpis["total"] or 0
        entregues = kpis["entregues"] or 0
        em_producao = kpis["em_producao"] or 0
        abertos = kpis["abertos"] or 0
        cancelados = kpis["cancelados"] or 0

    except LookupError:
        pass

    context = {
        "total_clientes": total_clientes,
        "total_pedidos": total_pedidos,
        "entregues": entregues,
        "em_producao": em_producao,
        "abertos": abertos,
        "cancelados": cancelados,
    }
    return render(request, "core/dashboard.html", context)
