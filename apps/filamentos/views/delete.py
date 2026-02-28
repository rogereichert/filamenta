from django.apps import apps
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, IntegerField, F
from django.db.models.expressions import ExpressionWrapper
from django.db.models.functions import Coalesce, Greatest
from django.shortcuts import get_object_or_404, redirect, render

from ..forms import FilamentoForm
from ..models import Filamento
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
