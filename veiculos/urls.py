from django.urls import path
from .views import (
    VeiculoListView,
    VeiculoCreateView,
    VeiculoUpdateView,
    VeiculoDeleteView,
    VeiculoDetailView,
    ClienteBuscaView,
)

urlpatterns = [
    path('', VeiculoListView.as_view(), name='veiculos_lista'),
    path('novo/', VeiculoCreateView.as_view(), name='veiculos_novo'),
    path('buscar-clientes/', ClienteBuscaView.as_view(), name='veiculos_buscar_clientes'),
    path('<int:pk>/', VeiculoDetailView.as_view(), name='veiculos_detalhe'),
    path('<int:pk>/editar/', VeiculoUpdateView.as_view(), name='veiculos_editar'),
    path('<int:pk>/excluir/', VeiculoDeleteView.as_view(), name='veiculos_excluir'),
]
