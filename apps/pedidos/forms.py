from django import forms
from django.forms import inlineformset_factory, BaseInlineFormSet
from decimal import Decimal
from django.db import models

from .models import Pedido, PedidoItem, PedidoItemFilamento


# ✅ Form principal do Pedido
class PedidoForm(forms.ModelForm):
    class Meta:
        model = Pedido
        fields = [
            "cliente", "status",
            "prazo_entrega", "prioridade",
            "titulo", "observacoes",
            "desconto", "frete", "taxa_extra",
        ]
        widgets = {
            "titulo": forms.TextInput(attrs={
                "placeholder": "Ex: Bonecos 3D - DC",
            }),
            "observacoes": forms.Textarea(attrs={
                "rows": 3,
                "placeholder": "Detalhes do pedido, prazos, acabamento, pintura, etc.",
            }),
            "desconto": forms.NumberInput(attrs={
                "step": "0.01",
                "min": "0",
                "placeholder": "0,00",
            }),
            "frete": forms.NumberInput(attrs={
                "step": "0.01",
                "min": "0",
                "placeholder": "0,00",
            }),
            "taxa_extra": forms.NumberInput(attrs={
                "step": "0.01",
                "min": "0",
                "placeholder": "0,00",
            }),
        }


# ✅ Item do pedido
class PedidoItemForm(forms.ModelForm):
    class Meta:
        model = PedidoItem
        fields = ["descricao", "quantidade", "tempo_horas", "preco_unitario"]
        widgets = {
            "descricao": forms.TextInput(attrs={
                "placeholder": "Ex: Boneco Superman 3D",
            }),
            "quantidade": forms.NumberInput(attrs={
                "min": 1,
            }),
            "preco_unitario": forms.NumberInput(attrs={
                "step": "0.01",
                "min": "0",
                "placeholder": "0,00",
            }),
        }


# ✅ Filamento vinculado ao item
class PedidoItemFilamentoForm(forms.ModelForm):
    class Meta:
        model = PedidoItemFilamento
        fields = ["filamento", "gramas_g"]
        widgets = {
            "gramas_g": forms.NumberInput(attrs={
                "min": 1,
                "placeholder": "Ex: 120",
            }),
        }


def clean_gramas_g(self):
    gramas = self.cleaned_data.get("gramas_g") or 0
    filamento = self.cleaned_data.get("filamento")
    if not filamento:
        return gramas

    # Validação imediata "simples": não permitir acima do estoque físico atual.
    # (A validação completa por pedido + reservas acontece ao tentar EM_PRODUÇÃO.)
    if gramas > filamento.peso_atual_g:
        raise ValidationError(
            f"Estoque insuficiente: este filamento tem {filamento.peso_atual_g}g em estoque."
        )
    return gramas


# ✅ (Opcional) Formsets para edição “tudo em uma tela”
PedidoItemFormSet = inlineformset_factory(
    parent_model=Pedido,
    model=PedidoItem,
    form=PedidoItemForm,
    extra=1,
    can_delete=True,
)


class BasePedidoItemFilamentoFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        # Soma por filamento no contexto do ITEM (formset pai)
        totais = {}
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get("DELETE"):
                continue
            filamento = form.cleaned_data.get("filamento")
            gramas = form.cleaned_data.get("gramas_g") or 0
            if not filamento:
                continue
            totais.setdefault(filamento, 0)
            totais[filamento] += int(gramas)

        # Valida contra estoque disponível (considera reservas de outros pedidos quando possível)
        pedido = None
        if getattr(self.instance, "pedido_id", None):
            pedido = self.instance.pedido

        for filamento, total_g in totais.items():
            disponivel = (
                filamento.disponivel_g(exclude_pedido=pedido)
                if hasattr(filamento, "disponivel_g")
                else int(filamento.peso_atual_g)
            )
            if total_g > disponivel:
                raise ValidationError(
                    f"Estoque insuficiente para {filamento}: "
                    f"você informou {total_g}g, mas o disponível é {disponivel}g."
                )


PedidoItemFilamentoFormSet = inlineformset_factory(
    parent_model=PedidoItem,
    model=PedidoItemFilamento,
    form=PedidoItemFilamentoForm,
    formset=BasePedidoItemFilamentoFormSet,
    extra=1,
    can_delete=True,
)


# ✅ Form de cálculo rápido (orçamento)
class PedidoCalculoForm(forms.Form):
    # --- Dados para salvar como orçamento/pedido ---
    cliente = forms.ModelChoiceField(queryset=None, required=False, label="Cliente")
    titulo = forms.CharField(label="Título (opcional)", required=False)
    item_descricao = forms.CharField(label="Descrição do item", required=False)
    quantidade = forms.IntegerField(label="Quantidade", min_value=1, initial=1)

    filamento = forms.ModelChoiceField(
        queryset=None, required=False, empty_label="(Opcional) Selecionar filamento..."
    )
    preco_kg = forms.DecimalField(label="Preço do filamento (R$/kg)", max_digits=10, decimal_places=2, initial=Decimal("120.00"))
    gramas_total = forms.DecimalField(label="Gramas totais (g)", max_digits=10, decimal_places=2)
    tempo_total = forms.CharField(label="Tempo total (ex: 11h36m ou 11:36)", required=True)
    desperdicio_pct = forms.DecimalField(label="Desperdício (%)", max_digits=5, decimal_places=2, initial=Decimal("0.00"), required=False)
    custo_hora_maquina = forms.DecimalField(label="Custo hora máquina (R$/h)", max_digits=10, decimal_places=2, initial=Decimal("1.30"))
    energia_fixa = forms.DecimalField(label="Energia (R$ fixo)", max_digits=10, decimal_places=2, initial=Decimal("0.60"))
    preco_venda_manual = forms.DecimalField(
        label="Preço de venda manual (opcional)",
        max_digits=10,
        decimal_places=2,
        required=False,
        help_text="Se quiser, informe um preço final manual para salvar o orçamento.",
    )

    def __init__(self, *args, **kwargs):
        from apps.filamentos.models import Filamento
        from apps.clientes.models import Cliente
        super().__init__(*args, **kwargs)
        self.fields["filamento"].queryset = Filamento.objects.all()
        self.fields["cliente"].queryset = Cliente.objects.all().order_by("nome")

    def clean_tempo_total(self):
        return parse_tempo_total(self.cleaned_data.get("tempo_total"))


def parse_tempo_total(raw_value):
    """Converte tempo para horas decimais.

    Aceita:
      - 11.6
      - 11:36
      - 11h36m
      - 7m48s
    """
    raw = (raw_value or "").strip()
    if not raw:
        raise forms.ValidationError("Informe o tempo total.")
    import re
    from decimal import Decimal

    s = raw.lower().replace(",", ".").strip()

    # número puro (horas decimais)
    try:
        return Decimal(s)
    except Exception:
        pass

    # HH:MM
    m = re.fullmatch(r"(\d+)\s*:\s*(\d+)", s)
    if m:
        h = int(m.group(1))
        mn = int(m.group(2))
        return Decimal(h) + (Decimal(mn) / Decimal(60))

    # 11h36m / 7m48s / etc
    m = re.fullmatch(r"(?:(\d+)\s*h)?\s*(?:(\d+)\s*m)?\s*(?:(\d+)\s*s)?", s)
    if m and (m.group(1) or m.group(2) or m.group(3)):
        h = int(m.group(1) or 0)
        mn = int(m.group(2) or 0)
        sec = int(m.group(3) or 0)
        return Decimal(h) + (Decimal(mn) / Decimal(60)) + (Decimal(sec) / Decimal(3600))

    raise forms.ValidationError("Formato inválido. Use 11h36m, 11:36 ou 11.6")


class PedidoItemCalculoAddForm(forms.Form):
    """Adicionar item ao pedido usando o mesmo cálculo do 'Calcular Pedido'."""
    descricao = forms.CharField(label="Descrição do item", required=True)
    quantidade = forms.IntegerField(label="Quantidade", min_value=1, initial=1)

    filamento = forms.ModelChoiceField(
        queryset=None, required=False, empty_label="(Opcional) Selecionar filamento..."
    )
    preco_kg = forms.DecimalField(
        label="Preço do filamento (R$/kg)",
        max_digits=10,
        decimal_places=2,
        initial=Decimal("120.00"),
    )
    gramas_total = forms.DecimalField(label="Gramas totais (g)", max_digits=10, decimal_places=2)
    tempo_total = forms.CharField(label="Tempo total (ex: 11h36m ou 11:36)")
    desperdicio_pct = forms.DecimalField(
        label="Desperdício (%)",
        max_digits=5,
        decimal_places=2,
        initial=Decimal("0.00"),
        required=False,
    )
    custo_hora_maquina = forms.DecimalField(
        label="Custo hora máquina (R$/h)",
        max_digits=10,
        decimal_places=2,
        initial=Decimal("1.30"),
    )
    energia_fixa = forms.DecimalField(
        label="Energia (R$ fixo)",
        max_digits=10,
        decimal_places=2,
        initial=Decimal("0.60"),
    )

    class Multiplicador(models.TextChoices):
        M25 = "2.5", "2,5× (mínimo saudável)"
        M3 = "3", "3× (ideal)"
        MANUAL = "manual", "Manual"

    multiplicador = forms.ChoiceField(
        label="Preço de venda",
        choices=Multiplicador.choices,
        initial=Multiplicador.M25,
    )
    preco_venda_manual = forms.DecimalField(
        label="Preço manual (R$)",
        max_digits=10,
        decimal_places=2,
        required=False,
    )

    def __init__(self, *args, **kwargs):
        from apps.filamentos.models import Filamento
        super().__init__(*args, **kwargs)
        self.fields["filamento"].queryset = Filamento.objects.all()

    def clean_tempo_total(self):
        return parse_tempo_total(self.cleaned_data.get("tempo_total"))
