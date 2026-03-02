from decimal import Decimal
from django.db import models, transaction
from django.db.models import F, Sum
from django.db.models.functions import Coalesce, Greatest


class Pedido(models.Model):
    class Status(models.TextChoices):
        RASCUNHO = "rascunho", "Rascunho"
        ORCAMENTO = "orcamento", "Orçamento"
        ABERTO = "aberto", "Aberto"
        EM_PRODUCAO = "em_producao", "Em produção"
        ENTREGUE = "entregue", "Entregue"
        CANCELADO = "cancelado", "Cancelado"

    class Prioridade(models.TextChoices):
        BAIXA = "baixa", "Baixa"
        MEDIA = "media", "Média"
        ALTA = "alta", "Alta"
        URGENTE = "urgente", "Urgente"


    cliente = models.ForeignKey(
        "clientes.Cliente",
        on_delete=models.PROTECT,
        related_name="pedidos",
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.RASCUNHO,
    )

    prazo_entrega = models.DateField(null=True, blank=True)

    prioridade = models.CharField(
        max_length=20,
        choices=Prioridade.choices,
        default=Prioridade.MEDIA,
    )

    kanban_order = models.PositiveIntegerField(default=0)

    # ✅ descrição geral do pedido (ex: "Bonecos 3D - DC")
    titulo = models.CharField(max_length=120, blank=True, default="")
    observacoes = models.TextField(blank=True, default="")

    # ✅ ajustes financeiros (opcionais)
    desconto = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    frete = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    taxa_extra = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    # ✅ total calculado (cache)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    # evita baixar estoque 2x
    estoque_baixado = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status"], name="pedido_status_idx"),
            models.Index(fields=["created_at"], name="pedido_created_idx"),
            models.Index(fields=["cliente"], name="pedido_cliente_idx"),
        ]

    def __str__(self):
        return f"Pedido #{self.id} - {self.cliente}"


    @property
    def tempo_total_estimado_h(self):
        """Soma do tempo (em horas) de todos os itens do pedido."""
        return (
            self.itens.aggregate(total=Coalesce(Sum("tempo_horas"), 0))["total"]
            or 0
        )

    def recalcular_total(self, save=True):
        """
        Soma dos itens + frete + taxa_extra - desconto.
        """
        soma_itens = self.itens.aggregate(
            total=Coalesce(Sum("subtotal"), Decimal("0.00"))
        )["total"]

        total = (soma_itens + (self.frete or 0) + (self.taxa_extra or 0)) - (self.desconto or 0)
        if total < 0:
            total = Decimal("0.00")

        self.valor_total = total

        if save:
            # update_fields reduz risco de efeitos colaterais e é mais performático
            self.save(update_fields=["valor_total", "updated_at"])

        return total

    @transaction.atomic
    def baixar_estoque_se_necessario(self):
        """
        Baixa do estoque quando virar ENTREGUE (apenas 1x).
        Consome os filamentos a partir dos itens (PedidoItemFilamento).
        """
        if self.status != self.Status.ENTREGUE or self.estoque_baixado:
            return

        from apps.filamentos.models import Filamento  # ✅ caminho correto

        # agrega por filamento (mais eficiente)
        consumos = (
            PedidoItemFilamento.objects
            .filter(item__pedido=self)
            .values("filamento_id")
            .annotate(total_g=Coalesce(Sum("gramas_g"), 0))
        )

        for c in consumos:
            # ✅ atualização atômica no banco
            Filamento.objects.filter(pk=c["filamento_id"]).update(
                peso_atual_g=Greatest(F("peso_atual_g") - c["total_g"], 0)
            )

            # ✅ (Opcional) se você quiser evitar estoque negativo no banco,
            # faça isso via constraint/validação ou com uma segunda query "clamp":
            # Filamento.objects.filter(pk=c["filamento_id"], peso_atual_g__lt=0).update(peso_atual_g=0)

        self.estoque_baixado = True
        self.save(update_fields=["estoque_baixado", "updated_at"])

    def save(self, *args, **kwargs):
        status_anterior = None
        if self.pk:
            status_anterior = Pedido.objects.only("status").get(pk=self.pk).status

        super().save(*args, **kwargs)

        # se mudou para entregue, baixa estoque
        if status_anterior != self.status:
            self.baixar_estoque_se_necessario()


class PedidoItem(models.Model):
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name="itens",
    )

    # ✅ “Boneco Superman 3D”, “Boneco Aquaman 3D” etc.
    descricao = models.CharField(max_length=160)

    quantidade = models.PositiveIntegerField(default=1)

    # ✅ preço por unidade (se for 1 peça só, é o preço final do item)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    # ✅ tempo total estimado do item (horas). Ex.: 1.50 = 1h30
    tempo_horas = models.DecimalField(max_digits=7, decimal_places=2, default=Decimal("0.00"))

    # ✅ subtotal “cache” (quantidade * preco_unitario)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return f"{self.pedido} - {self.descricao} (x{self.quantidade})"

    def recalcular_subtotal(self):
        q = self.quantidade or 0
        pu = self.preco_unitario or Decimal("0.00")
        return Decimal(q) * pu

    def save(self, *args, **kwargs):
        self.subtotal = self.recalcular_subtotal()
        super().save(*args, **kwargs)
        # ✅ sempre que item muda, atualiza total do pedido
        self.pedido.recalcular_total(save=True)

    def delete(self, *args, **kwargs):
        pedido = self.pedido
        super().delete(*args, **kwargs)
        pedido.recalcular_total(save=True)


class PedidoItemFilamento(models.Model):
    item = models.ForeignKey(
        PedidoItem,
        on_delete=models.CASCADE,
        related_name="filamentos",
    )

    filamento = models.ForeignKey(
        "filamentos.Filamento",
        on_delete=models.PROTECT,
        related_name="consumos_itens",
    )

    gramas_g = models.PositiveIntegerField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Consumo de filamento do item"
        verbose_name_plural = "Consumos de filamento do item"

    def __str__(self):
        return f"{self.item} - {self.filamento} ({self.gramas_g}g)"
