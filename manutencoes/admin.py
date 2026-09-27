from django.contrib import admin
from .models import Manutencao, Peca, PecaUsada


@admin.register(Manutencao)
class ManutencaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'veiculo', 'tipo', 'descricao', 'data_manutencao', 'quilometragem', 'valor')
    search_fields = ('descricao', 'veiculo__marca', 'veiculo__modelo', 'veiculo__placa')
    list_filter = ('tipo', 'data_manutencao')


@admin.register(Peca)
class PecaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome', 'marca', 'preco_custo')
    search_fields = ('nome', 'marca')


@admin.register(PecaUsada)
class PecaUsadaAdmin(admin.ModelAdmin):
    list_display = ('id', 'manutencao', 'peca', 'quantidade', 'valor_total_custo')
    search_fields = ('peca__nome', 'manutencao__veiculo__placa')
