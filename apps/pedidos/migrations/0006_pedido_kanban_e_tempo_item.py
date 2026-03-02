from django.db import migrations, models
import decimal


class Migration(migrations.Migration):

    dependencies = [
        ("pedidos", "0005_pedido_indexes"),
    ]

    operations = [
        migrations.AddField(
            model_name="pedido",
            name="prazo_entrega",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="pedido",
            name="prioridade",
            field=models.CharField(
                choices=[
                    ("baixa", "Baixa"),
                    ("media", "Média"),
                    ("alta", "Alta"),
                    ("urgente", "Urgente"),
                ],
                default="media",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="pedido",
            name="kanban_order",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="pedidoitem",
            name="tempo_horas",
            field=models.DecimalField(
                decimal_places=2,
                default=decimal.Decimal("0.00"),
                max_digits=7,
            ),
        ),
    ]
