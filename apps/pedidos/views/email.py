from __future__ import annotations

import ssl

from django.conf import settings
from django.contrib import messages
from django.core.mail import EmailMessage, get_connection
from django.shortcuts import get_object_or_404, redirect

from ..models import Pedido
from .pdf import get_pedido_pdf_cached




def pedido_enviar_email(request, pk):
    pedido = get_object_or_404(
        Pedido.objects.select_related("cliente").prefetch_related("itens"),
        pk=pk,
    )

    if request.method == "POST":
        pdf_bytes = get_pedido_pdf_cached(pedido)

        email = EmailMessage(
            subject=f"Pedido #{pedido.id} - Filamenta",
            body=f"Segue em anexo o PDF do pedido #{pedido.id}.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[settings.PEDIDO_DESTINO_EMAIL],
        )

        email.attach(
            f"pedido_{pedido.id}.pdf",
            pdf_bytes,
            "application/pdf"
        )

        try:
            email.send(fail_silently=False)

        except ssl.SSLCertVerificationError:
            # fallback sem verificação SSL (apenas dev/local)
            connection = get_connection()
            connection.ssl_context = ssl._create_unverified_context()
            email.connection = connection
            email.send(fail_silently=False)

        messages.success(request, "Pedido enviado por e-mail com sucesso.")
        return redirect("pedidos:detail", pk=pedido.pk)

    return redirect("pedidos:detail", pk=pedido.pk)

