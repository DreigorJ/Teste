from django.db import models
from django.contrib.auth.models import User

from dateutil.relativedelta import relativedelta
from datetime import timedelta, date

class Estoque(models.Model):
    nome = models.CharField(max_length=100)
    usuarios = models.ManyToManyField(User, related_name='estoques')

    def __str__(self):
        return self.nome

class Categoria(models.Model):
    nome = models.CharField(max_length=100)
    estoque = models.ForeignKey(Estoque, on_delete=models.CASCADE, related_name='categorias')

    def __str__(self):
        return self.nome

class Metrica(models.Model):
    nome = models.CharField(max_length=100, unique=True)
    codigo = models.CharField(max_length=10, unique=True)
    fixa = models.BooleanField(default=False)

    def __str__(self):
        return self.nome

class Produto(models.Model):
    nome = models.CharField(max_length=100)
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, blank=True)
    marca = models.CharField(max_length=100, blank=True)
    dataValidade = models.DateField(null=True, blank=True)
    preco = models.DecimalField(max_digits=8, decimal_places=2)
    metrica = models.ForeignKey(Metrica, on_delete=models.PROTECT, related_name='produtos')
    estoque = models.ForeignKey(Estoque, on_delete=models.CASCADE, related_name='produtos')
    unidades = models.PositiveIntegerField(default=0)
    dataCadastro = models.DateTimeField(auto_now_add=True)
    dataModificacao = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.nome

class Movimentacao(models.Model):
    ENTRADA = 'E'
    SAIDA = 'S'
    TIPO_CHOICES = [
        (ENTRADA, 'Entrada'),
        (SAIDA, 'Saída'),
    ]
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE)
    tipo = models.CharField(max_length=1, choices=TIPO_CHOICES)
    quantidade = models.PositiveIntegerField()
    data = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.produto.nome} ({self.quantidade})"

class CompraRecorrente(models.Model):
    INTERVALO_CHOICES = [
        ('dias', 'Dias'),
        ('meses', 'Meses'),
        ('anos', 'Anos'),
    ]
    produto = models.ForeignKey(Produto, on_delete=models.CASCADE, related_name='compras_recorrentes')
    data_inicio = models.DateField()
    intervalo_valor = models.PositiveIntegerField(default=30)
    intervalo_tipo = models.CharField(max_length=6, choices=INTERVALO_CHOICES, default='meses')
    cota_minima = models.PositiveIntegerField()
    ultima_compra = models.DateField(null=True, blank=True)
    ignorar_ate_logout = models.BooleanField(default=False)

    def proxima_data(self):
        """Calcula a próxima data esperada da compra recorrente."""
        base = self.ultima_compra or self.data_inicio
        if self.intervalo_tipo == 'dias':
            return base + timedelta(days=self.intervalo_valor)
        elif self.intervalo_tipo == 'meses':
            return base + relativedelta(months=self.intervalo_valor)
        elif self.intervalo_tipo == 'anos':
            return base + relativedelta(years=self.intervalo_valor)
        return base

    def esta_atrasada(self):
        """Retorna (True, dias_atraso) se está atrasada, caso contrário (False, 0)."""
        if self.ignorar_ate_logout:
            return False, 0
        hoje = date.today()
        proxima = self.proxima_data()
        if hoje > proxima:
            return True, (hoje - proxima).days
        return False, 0