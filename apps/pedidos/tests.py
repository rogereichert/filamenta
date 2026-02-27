from decimal import Decimal

from django.test import TestCase
from django.db import IntegrityError

from apps.clientes.models import Cliente
from apps.filamentos.models import Filamento
from apps.pedidos.models import Pedido, PedidoItem, PedidoItemFilamento


class PedidoCalculosTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nome="Cliente Teste")
        self.pedido = Pedido.objects.create(cliente=self.cliente)

    def test_item_recalcula_subtotal_e_total(self):
        item = PedidoItem.objects.create(
            pedido=self.pedido,
            descricao="Peça A",
            quantidade=2,
            preco_unitario=Decimal("10.00"),
        )
        item.refresh_from_db()
        self.pedido.refresh_from_db()
        self.assertEqual(item.subtotal, Decimal("20.00"))
        self.assertEqual(self.pedido.valor_total, Decimal("20.00"))

        # altera quantidade
        item.quantidade = 3
        item.save()
        item.refresh_from_db()
        self.pedido.refresh_from_db()
        self.assertEqual(item.subtotal, Decimal("30.00"))
        self.assertEqual(self.pedido.valor_total, Decimal("30.00"))

    def test_pedido_total_nunca_negativo(self):
        PedidoItem.objects.create(
            pedido=self.pedido,
            descricao="Peça B",
            quantidade=1,
            preco_unitario=Decimal("5.00"),
        )
        self.pedido.desconto = Decimal("999.00")
        self.pedido.save()
        self.pedido.recalcular_total(save=True)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.valor_total, Decimal("0.00"))


class BaixaEstoqueTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nome="Cliente Teste")
        self.filamento = Filamento.objects.create(
            nome="PLA Preto",
            cor="Preto",
            material="PLA",
            peso_inicial_g=100,
            peso_atual_g=30,
            preco_kg=Decimal("120.00"),
        )
        self.pedido = Pedido.objects.create(cliente=self.cliente)

        self.item = PedidoItem.objects.create(
            pedido=self.pedido,
            descricao="Peça C",
            quantidade=1,
            preco_unitario=Decimal("10.00"),
        )

        PedidoItemFilamento.objects.create(
            item=self.item,
            filamento=self.filamento,
            gramas_g=50,
        )

    def test_baixa_estoque_so_uma_vez_e_nao_fica_negativo(self):
        # vira entregue -> baixa
        self.pedido.status = Pedido.Status.ENTREGUE
        self.pedido.save()

        self.filamento.refresh_from_db()
        self.pedido.refresh_from_db()

        # 30 - 50 -> clamp para 0
        self.assertEqual(self.filamento.peso_atual_g, 0)
        self.assertTrue(self.pedido.estoque_baixado)

        # salvar novamente não deve baixar outra vez
        self.pedido.save()
        self.filamento.refresh_from_db()
        self.assertEqual(self.filamento.peso_atual_g, 0)


class FilamentoConstraintTests(TestCase):
    def test_unique_filamento_nome_cor_material(self):
        Filamento.objects.create(nome="PLA", cor="Azul", material="PLA")
        with self.assertRaises(IntegrityError):
            Filamento.objects.create(nome="PLA", cor="Azul", material="PLA")
