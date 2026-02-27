from django.contrib import admin
from django.db.models import Sum
from django.utils.html import format_html

from .models import Pedido, PedidoItem, PedidoItemFilamento


# ---------- Inlines ----------
class PedidoItemFilamentoInline(admin.TabularInline):
    model = PedidoItemFilamento
    extra = 0
    fields = ("filamento", "gramas_g", "created_at")
    readonly_fields = ("created_at",)


class PedidoItemInline(admin.TabularInline):
    model = PedidoItem
    extra = 0
    show_change_link = True
    fields = ("descricao", "quantidade", "preco_unitario", "subtotal")
    readonly_fields = ("subtotal",)


# ---------- Admins ----------
@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = (
        "id", "cliente", "status",
        "valor_total", "total_gramas_admin",
        "estoque_baixado", "created_at",
    )
    list_filter = ("status", "estoque_baixado", "created_at")
    search_fields = ("id", "cliente__nome", "titulo")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at", "valor_total", "estoque_baixado")

    inlines = [PedidoItemInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        # soma gramas de todos os filamentos ligados aos itens do pedido
        return qs.annotate(_total_gramas=Sum("itens__filamentos__gramas_g"))

    @admin.display(description="Total gramas")
    def total_gramas_admin(self, obj):
        total = obj._total_gramas or 0
        # deixa visual melhor
        return format_html("<span style='font-weight:600'>{}g</span>", total)

    def has_change_permission(self, request, obj=None):
        """
        Trava edição se pedido já estiver ENTREGUE ou CANCELADO.
        (Se quiser permitir, pode remover esse bloco.)
        """
        perm = super().has_change_permission(request, obj=obj)
        if not perm or not obj:
            return perm

        if obj.status in [Pedido.Status.ENTREGUE, Pedido.Status.CANCELADO]:
            return False
        return True


@admin.register(PedidoItem)
class PedidoItemAdmin(admin.ModelAdmin):
    list_display = ("id", "pedido", "descricao", "quantidade", "preco_unitario", "subtotal")
    search_fields = ("descricao", "pedido__cliente__nome", "pedido__id")
    readonly_fields = ("subtotal",)

    inlines = [PedidoItemFilamentoInline]


@admin.register(PedidoItemFilamento)
class PedidoItemFilamentoAdmin(admin.ModelAdmin):
    list_display = ("id", "item", "filamento", "gramas_g", "created_at")
    search_fields = ("item__descricao", "filamento__nome", "filamento__cor")
