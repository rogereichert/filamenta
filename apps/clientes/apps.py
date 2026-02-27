from django.apps import AppConfig

# Django agora precisa saber que o app não é clientes, e sim apps.clientes.
class ClientesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.clientes"
