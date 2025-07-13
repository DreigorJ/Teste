from django.test import TestCase
from django.contrib.auth.models import User
from django.utils import timezone
from django.db import models
from datetime import date, timedelta
from App.models import Estoque, Produto, Categoria, Metrica, CompraRecorrente, Movimentacao


class CompraRecorrenteTestCase(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(username='testuser', password='testpass')
        
        # Create test estoque
        self.estoque = Estoque.objects.create(nome='Test Estoque')
        self.estoque.usuarios.add(self.user)
        
        # Create test categoria
        self.categoria = Categoria.objects.create(nome='Test Categoria', estoque=self.estoque)
        
        # Get or create test metrica
        self.metrica, created = Metrica.objects.get_or_create(
            nome='Test Metrica', 
            defaults={'codigo': 'tst'}
        )
        
        # Create test produto
        self.produto = Produto.objects.create(
            nome='Test Produto',
            categoria=self.categoria,
            marca='Test Marca',
            preco=10.00,
            metrica=self.metrica,
            estoque=self.estoque,
            unidades=0
        )
        
        # Add some stock to the product
        Movimentacao.objects.create(
            produto=self.produto,
            tipo=Movimentacao.ENTRADA,
            quantidade=50
        )

    def test_legacy_fields_removed(self):
        """Test that the old date-based fields have been removed"""
        # Create a new CompraRecorrente and ensure old fields don't exist
        compra_recorrente = CompraRecorrente.objects.create(
            produto=self.produto,
            cota_minima=50,
            checar_periodicamente=True
        )
        
        # Test that old fields are no longer available
        with self.assertRaises(AttributeError):
            compra_recorrente.data_inicio
        with self.assertRaises(AttributeError):
            compra_recorrente.intervalo_valor
        with self.assertRaises(AttributeError):
            compra_recorrente.intervalo_tipo
        with self.assertRaises(AttributeError):
            compra_recorrente.ultima_compra

    def test_new_simplified_compra_recorrente_behavior(self):
        """Test new simplified recurring purchase behavior with quota-only logic"""
        # Create a recurring purchase with the new simplified model
        compra_recorrente = CompraRecorrente.objects.create(
            produto=self.produto,
            cota_minima=100,  # Higher than current stock (50)
            checar_periodicamente=True
        )
        
        # Test that we no longer have date-based methods
        self.assertFalse(hasattr(compra_recorrente, 'proxima_data'))
        self.assertFalse(hasattr(compra_recorrente, 'esta_atrasada'))
        
        # Test the fields exist and have correct values
        self.assertEqual(compra_recorrente.cota_minima, 100)
        self.assertTrue(compra_recorrente.checar_periodicamente)
        self.assertFalse(compra_recorrente.ignorar_ate_logout)

    def test_new_alert_generation_logic(self):
        """Test new alert generation logic - quota based only"""
        # Create a recurring purchase that should generate an alert (quota based)
        CompraRecorrente.objects.create(
            produto=self.produto,
            cota_minima=100,  # Higher than current stock (50)
            checar_periodicamente=True,
            ignorar_ate_logout=False
        )
        
        # Simulate the new view logic for generating alerts
        compras_recorrentes = CompraRecorrente.objects.filter(produto__estoque=self.estoque)
        avisos_recorrentes = []
        
        for compra in compras_recorrentes:
            if compra.checar_periodicamente and not compra.ignorar_ate_logout:
                produto = compra.produto
                saldo = Movimentacao.objects.filter(produto=produto, tipo=Movimentacao.ENTRADA).aggregate(
                    total=models.Sum('quantidade'))['total'] or 0
                saldo -= Movimentacao.objects.filter(produto=produto, tipo=Movimentacao.SAIDA).aggregate(
                    total=models.Sum('quantidade'))['total'] or 0
                if compra.cota_minima > 0 and saldo < compra.cota_minima:
                    avisos_recorrentes.append({
                        'compra_id': compra.id,
                        'produto_nome': produto.nome,
                        'saldo_atual': saldo,
                        'minimo': compra.cota_minima,
                    })
        
        # Should have one alert
        self.assertEqual(len(avisos_recorrentes), 1)
        self.assertEqual(avisos_recorrentes[0]['saldo_atual'], 50)
        self.assertEqual(avisos_recorrentes[0]['minimo'], 100)

    def test_no_alert_when_checar_periodicamente_false(self):
        """Test that no alert is generated when checar_periodicamente is False"""
        # Create a recurring purchase with checking disabled
        CompraRecorrente.objects.create(
            produto=self.produto,
            cota_minima=100,  # Higher than current stock (50)
            checar_periodicamente=False,  # Disabled
            ignorar_ate_logout=False
        )
        
        # Simulate the new view logic
        compras_recorrentes = CompraRecorrente.objects.filter(produto__estoque=self.estoque)
        avisos_recorrentes = []
        
        for compra in compras_recorrentes:
            if compra.checar_periodicamente and not compra.ignorar_ate_logout:
                produto = compra.produto
                saldo = Movimentacao.objects.filter(produto=produto, tipo=Movimentacao.ENTRADA).aggregate(
                    total=models.Sum('quantidade'))['total'] or 0
                saldo -= Movimentacao.objects.filter(produto=produto, tipo=Movimentacao.SAIDA).aggregate(
                    total=models.Sum('quantidade'))['total'] or 0
                if compra.cota_minima > 0 and saldo < compra.cota_minima:
                    avisos_recorrentes.append({
                        'compra_id': compra.id,
                        'produto_nome': produto.nome,
                        'saldo_atual': saldo,
                        'minimo': compra.cota_minima,
                    })
        
        # Should have no alerts because checar_periodicamente is False
        self.assertEqual(len(avisos_recorrentes), 0)

    def test_no_alert_when_cota_minima_zero(self):
        """Test that no alert is generated when cota_minima is 0"""
        # Create a recurring purchase with cota_minima = 0
        CompraRecorrente.objects.create(
            produto=self.produto,
            cota_minima=0,  # Zero means no alerts
            checar_periodicamente=True,
            ignorar_ate_logout=False
        )
        
        # Simulate the new view logic
        compras_recorrentes = CompraRecorrente.objects.filter(produto__estoque=self.estoque)
        avisos_recorrentes = []
        
        for compra in compras_recorrentes:
            if compra.checar_periodicamente and not compra.ignorar_ate_logout:
                produto = compra.produto
                saldo = Movimentacao.objects.filter(produto=produto, tipo=Movimentacao.ENTRADA).aggregate(
                    total=models.Sum('quantidade'))['total'] or 0
                saldo -= Movimentacao.objects.filter(produto=produto, tipo=Movimentacao.SAIDA).aggregate(
                    total=models.Sum('quantidade'))['total'] or 0
                if compra.cota_minima > 0 and saldo < compra.cota_minima:
                    avisos_recorrentes.append({
                        'compra_id': compra.id,
                        'produto_nome': produto.nome,
                        'saldo_atual': saldo,
                        'minimo': compra.cota_minima,
                    })
        
        # Should have no alerts because cota_minima is 0
        self.assertEqual(len(avisos_recorrentes), 0)