from django.contrib import admin
from .models import Veiculo


@admin.register(Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'marca', 'modelo', 'ano', 'placa', 'chassi', 'data_cadastro')
    search_fields = ('marca', 'modelo', 'placa', 'chassi', 'cliente__nome')
    list_filter = ('marca', 'ano')