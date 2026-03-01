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

    
    def _referencia_consumo(self) -> str:
        # Mantém compatibilidade com dados antigos que possam ter sido criados via "referencia"
        return f"PEDIDO:{self.pk}"

    def _totais_filamento_por_pedido(self):
        """
        Retorna um queryset agregando o consumo total (em gramas) por filamento, baseado nos itens do pedido.
        """
        return (
            PedidoItemFilamento.objects
            .filter(item__pedido=self)
            .values("filamento_id")
            .annotate(total_g=Coalesce(Sum("gramas_g"), 0))
        )

    @transaction.atomic
    def sincronizar_reservas_filamento(self, *, criar_se_vazio: bool = False) -> None:
        """
        Cria/atualiza reservas (FilamentoConsumo) quando o pedido entra em EM_PRODUCAO.

        - Cria/atualiza 1 reserva (status RES) por filamento do pedido.
        - Cancelar reservas RES/RAS que não existem mais nos itens.
        - Se 'criar_se_vazio' for True e não existirem reservas, cria reservas mesmo se o pedido não passou por EM_PRODUCAO.
        """
        from apps.filamentos.models import FilamentoConsumo

        if not self.pk:
            return

        if self.status != self.Status.EM_PRODUCAO and not criar_se_vazio:
            return

        referencia = self._referencia_consumo()

        totais = list(self._totais_filamento_por_pedido())
        totais_map = {t["filamento_id"]: int(t["total_g"] or 0) for t in totais if int(t["total_g"] or 0) > 0}

        # (1) Cancela reservas antigas que não existem mais nos itens
        FilamentoConsumo.objects.filter(
            pedido=self,
            status__in=["RAS", "RES"],
        ).exclude(
            filamento_id__in=list(totais_map.keys()),
        ).update(status="CAN")

        # (2) Upsert das reservas atuais
        for filamento_id, total_g in totais_map.items():
            # Se existirem registros antigos (antes do FK), tenta vinculá-los
            FilamentoConsumo.objects.filter(
                pedido__isnull=True,
                referencia=referencia,
                filamento_id=filamento_id,
                status="RES",
            ).update(pedido=self)

            obj, created = FilamentoConsumo.objects.get_or_create(
                pedido=self,
                filamento_id=filamento_id,
                status="RES",
                defaults={
                    "gramas_g": total_g,
                    "referencia": referencia,
                },
            )

            if not created:
                # Se já existia, sincroniza quantidade e referência (caso itens tenham mudado)
                updates = {}
                if obj.gramas_g != total_g:
                    updates["gramas_g"] = total_g
                if obj.referencia != referencia:
                    updates["referencia"] = referencia
                if updates:
                    FilamentoConsumo.objects.filter(pk=obj.pk).update(**updates)

    @transaction.atomic
    def cancelar_reservas_filamento(self) -> None:
        """Cancela reservas pendentes (RAS/RES) do pedido."""
        from apps.filamentos.models import FilamentoConsumo

        if not self.pk:
            return

        FilamentoConsumo.objects.filter(
            pedido=self,
            status__in=["RAS", "RES"],
        ).update(status="CAN")

    @transaction.atomic
    def baixar_estoque_se_necessario(self) -> None:
        """
        Confirma reservas e baixa do estoque quando virar ENTREGUE (apenas 1x).

        Fluxo:
        - EM_PRODUCAO: cria/atualiza reservas (RES)
        - ENTREGUE: transforma RES -> CON e baixa do estoque com base nos consumos confirmados
        - CANCELADO: cancela reservas (RES/RAS)
        """
        if self.status != self.Status.ENTREGUE or self.estoque_baixado:
            return

        from apps.filamentos.models import Filamento, FilamentoConsumo  # ✅ caminho correto

        # Se o pedido foi entregue sem passar por EM_PRODUCAO, criamos reservas agora para manter histórico
        self.sincronizar_reservas_filamento(criar_se_vazio=True)

        # Confirma tudo que estiver reservado/rascunho
        FilamentoConsumo.objects.filter(
            pedido=self,
            status__in=["RAS", "RES"],
        ).update(status="CON")

        consumos_confirmados = (
            FilamentoConsumo.objects
            .filter(pedido=self, status="CON")
            .values("filamento_id")
            .annotate(total_g=Coalesce(Sum("gramas_g"), 0))
        )

        for c in consumos_confirmados:
            Filamento.objects.filter(pk=c["filamento_id"]).update(
                peso_atual_g=Greatest(F("peso_atual_g") - c["total_g"], 0)
            )

        self.estoque_baixado = True
        self.save(update_fields=["estoque_baixado", "updated_at"])

    def save(self, *args, **kwargs):
        status_anterior = None
        if self.pk:
            status_anterior = Pedido.objects.only("status").get(pk=self.pk).status

        super().save(*args, **kwargs)

        # ✅ Regras de transição de status (efeitos colaterais)
        if status_anterior != self.status:
            # Entrou em produção => cria/atualiza reservas
            if self.status == self.Status.EM_PRODUCAO:
                self.sincronizar_reservas_filamento()

            # Saiu de produção (voltou) => libera reservas
            if status_anterior == self.Status.EM_PRODUCAO and self.status in {
                self.Status.RASCUNHO,
                self.Status.ORCAMENTO,
                self.Status.ABERTO,
            }:
                self.cancelar_reservas_filamento()

            # Cancelado => cancela reservas pendentes
            if self.status == self.Status.CANCELADO:
                self.cancelar_reservas_filamento()

            # Entregue => confirma e baixa estoque
            if self.status == self.Status.ENTREGUE:
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
