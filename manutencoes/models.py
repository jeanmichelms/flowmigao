from django.db import models
from veiculos.models import Veiculo

TIPO_MANUTENCAO_CHOICES = [
    ('PREVENTIVA', 'Preventiva'),
    ('CORRETIVA', 'Corretiva'),
]

class Manutencao(models.Model):
    veiculo = models.ForeignKey(Veiculo, on_delete=models.CASCADE, related_name='manutencoes')
    descricao = models.TextField()
    data_manutencao = models.DateField()
    quilometragem = models.PositiveIntegerField()
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    observacoes = models.TextField(blank=True, null=True)
    data_proxima_manutencao = models.DateField(blank=True, null=True)
    email_aviso_revisao_enviado = models.BooleanField(default=False, editable=False)
    data_cadastro = models.DateTimeField(auto_now_add=True)
    tipo = models.CharField(max_length=15, choices=TIPO_MANUTENCAO_CHOICES, default='PREVENTIVA')

    class Meta:
        ordering = ['-data_manutencao', '-id']
        verbose_name = 'Manutenção'
        verbose_name_plural = 'Manutenções'

    def __str__(self):
        return f'{self.veiculo} - {self.descricao} ({self.data_manutencao})'

    def save(self, *args, **kwargs):
        if self.pk:
            data_anterior = (
                Manutencao.objects
                .filter(pk=self.pk)
                .values_list('data_proxima_manutencao', flat=True)
                .first()
            )

            if data_anterior != self.data_proxima_manutencao:
                self.email_aviso_revisao_enviado = False
                update_fields = kwargs.get('update_fields')
                if update_fields is not None:
                    kwargs['update_fields'] = set(update_fields) | {
                        'email_aviso_revisao_enviado',
                    }

        super().save(*args, **kwargs)

class Peca(models.Model):
    nome = models.CharField(max_length=100)
    marca = models.CharField(max_length=50, blank=True, null=True)
    preco_custo = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço de Custo")

    class Meta:
        ordering = ['nome', 'marca']
        verbose_name = 'Peça'
        verbose_name_plural = 'Peças'

    def __str__(self):
        if self.marca:
            return f"{self.nome} ({self.marca})"
        return self.nome

class PecaUsada(models.Model):
    manutencao = models.ForeignKey(Manutencao, on_delete=models.CASCADE, related_name='pecas_usadas')
    peca = models.ForeignKey(Peca, on_delete=models.PROTECT)
    quantidade = models.PositiveIntegerField(default=1)
    valor_total_custo = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)

    class Meta:
        verbose_name = 'Peça usada'
        verbose_name_plural = 'Peças usadas'

    def __str__(self):
        return f'{self.quantidade}x {self.peca}'

    def save(self, *args, **kwargs):
        # Multiplica a quantidade pelo custo da peça automaticamente antes de salvar
        if self.peca:
            self.valor_total_custo = self.quantidade * self.peca.preco_custo
        super().save(*args, **kwargs)
