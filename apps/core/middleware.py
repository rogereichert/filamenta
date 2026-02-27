from __future__ import annotations

from django.conf import settings
from django.http import HttpRequest
from django.shortcuts import redirect
from django.urls import resolve


class LoginRequiredMiddleware:
    """Exige autenticação para todo o sistema por padrão.

    Libera URLs do Django Auth (/accounts/), Admin (/admin/), arquivos estáticos
    e media. Assim, ao "ativar" o sistema, a primeira tela será o login.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        if self._should_require_login(request):
            return redirect(f"{settings.LOGIN_URL}?next={request.get_full_path()}")
        return self.get_response(request)

    def _should_require_login(self, request: HttpRequest) -> bool:
        # Já autenticado
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            return False

        path = request.path

        # Permitir login/logout do Django auth
        if path.startswith("/accounts/"):
            return False

        # Permitir admin
        if path.startswith("/admin/"):
            return False

        # Permitir estáticos e media
        if settings.STATIC_URL and path.startswith(settings.STATIC_URL):
            return False
        if settings.MEDIA_URL and path.startswith(settings.MEDIA_URL):
            return False

        # Permitir a favicon
        if path == "/favicon.ico":
            return False

        # Para o restante, exige login
        return True
