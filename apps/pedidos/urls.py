from django.urls import path

from .views import (
    pedido_list,
    pedido_create,
    pedido_detail,
    pedido_update,
    pedido_delete,
    pedido_item_add,
    pedido_item_add_calculado,
    pedido_item_remove,
    item_filamento_add,
    item_filamento_remove,
    pedido_calcular,
    pedido_enviar_email,
    pedido_pdf,
)

app_name = "pedidos"

urlpatterns = [
    path("", pedido_list, name="list"),
    path("novo/", pedido_create, name="create"),
    path("<int:pk>/", pedido_detail, name="detail"),
    path("<int:pk>/editar/", pedido_update, name="update"),
    path("<int:pk>/excluir/", pedido_delete, name="delete"),

    # ✅ Itens do pedido (produtos)
    path("<int:pk>/itens/adicionar/", pedido_item_add, name="item_add"),
    path("<int:pk>/itens/adicionar-calculado/", pedido_item_add_calculado, name="item_add_calculado"),
    path("<int:pk>/itens/<int:item_id>/remover/", pedido_item_remove, name="item_remove"),

    # ✅ Filamentos por item
    path("<int:pk>/itens/<int:item_id>/filamentos/adicionar/", item_filamento_add, name="item_filamento_add"),
    path("<int:pk>/itens/<int:item_id>/filamentos/<int:if_id>/remover/", item_filamento_remove, name="item_filamento_remove"),

    path("calcular/", pedido_calcular, name="calcular"),
    path("<int:pk>/enviar-email/", pedido_enviar_email, name="enviar_email"),
    path("<int:pk>/pdf/", pedido_pdf, name="pdf"),
]
