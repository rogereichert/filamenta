from django.urls import path
from . import views

app_name = "pedidos"

urlpatterns = [
    path("", views.pedido_list, name="list"),
    path("novo/", views.pedido_create, name="create"),
    path("<int:pk>/", views.pedido_detail, name="detail"),
    path("<int:pk>/editar/", views.pedido_update, name="update"),
    path("<int:pk>/excluir/", views.pedido_delete, name="delete"),

    # ✅ Itens do pedido (produtos)
    path("<int:pk>/itens/adicionar/", views.pedido_item_add, name="item_add"),
    path("<int:pk>/itens/adicionar-calculado/", views.pedido_item_add_calculado, name="item_add_calculado"),
    path("<int:pk>/itens/<int:item_id>/remover/", views.pedido_item_remove, name="item_remove"),

    # ✅ Filamentos por item
    path("<int:pk>/itens/<int:item_id>/filamentos/adicionar/", views.item_filamento_add, name="item_filamento_add"),
    path("<int:pk>/itens/<int:item_id>/filamentos/<int:if_id>/remover/", views.item_filamento_remove, name="item_filamento_remove"),

    path("calcular/", views.pedido_calcular, name="calcular"),
    path("<int:pk>/enviar-email/", views.pedido_enviar_email, name="enviar_email"),
    path("<int:pk>/pdf/", views.pedido_pdf, name="pdf"),
]
