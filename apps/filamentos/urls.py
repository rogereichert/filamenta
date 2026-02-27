from django.urls import path
from . import views

app_name = "filamentos"

urlpatterns = [
    path("", views.filamento_list, name="list"),
    path("novo/", views.filamento_create, name="create"),
    path("<int:pk>/", views.filamento_detail, name="detail"),
    path("<int:pk>/editar/", views.filamento_update, name="update"),
    path("<int:pk>/excluir/", views.filamento_delete, name="delete"),
]
