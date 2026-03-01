from django.db import models

class Filamento(models.Model):
    MATERIAIS = [
        ("PLA", "PLA"),
        ("PETG", "PETG"),
        ("ABS", "ABS"),
        ("TPU", "TPU"),
        ("OUTRO", "Outro"),
    ]

    nome = models.CharField(max_length=120)
    cor = models.CharField(max_length=60, blank=True, default="")
    material = models.CharField(max_length=10, choices=MATERIAIS, default="PLA")

    peso_inicial_g = models.PositiveIntegerField(default=0)
    peso_atual_g = models.PositiveIntegerField(default=0)

    preco_kg = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["nome", "cor", "-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["nome", "cor", "material"], name="uniq_filamento_nome_cor_material"),
        ]

    def __str__(self):
        return f"{self.nome} ({self.material}) - {self.cor}".strip()

    @property
    def estoque_pct(self) -> int:
        if not self.peso_inicial_g:
            return 0
        pct = int(round((self.peso_atual_g / self.peso_inicial_g) * 100))
        return max(0, min(100, pct))

    @property
    def estoque_nivel(self) -> str:
        if not self.peso_inicial_g:
            return "sem_base"
        pct = self.estoque_pct
        if pct < 5:
            return "critico"
        if pct < 20:
            return "baixo"
        if pct < 50:
            return "atencao"
        return "ok"


# ✅ NOVO MODEL — ADICIONE ABAIXO
class FilamentoConsumo(models.Model):
    STATUS = [
        ("RAS", "Rascunho"),
        ("RES", "Reservado"),
        ("CON", "Confirmado"),
        ("CAN", "Cancelado"),
    ]

    filamento = models.ForeignKey(
        Filamento,
        on_delete=models.CASCADE,
        related_name="reservas"
    )

    pedido = models.ForeignKey(
        "pedidos.Pedido",
        on_delete=models.CASCADE,
        related_name="filamento_consumos",
        null=True,
        blank=True,
    )

    gramas_g = models.PositiveIntegerField()
    status = models.CharField(max_length=3, choices=STATUS, default="RES")

    referencia = models.CharField(max_length=80, blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.filamento.nome} - {self.gramas_g}g ({self.get_status_display()})"
