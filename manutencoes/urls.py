from django.urls import path
from . import views
from .views import (
    ManutencaoListView,
    ManutencaoCreateView,
    ManutencaoUpdateView,
    ManutencaoDeleteView,
    ManutencaoDetailView,
    VeiculoBuscaView,
    PecaListView,
    PecaCreateView,
    PecaUpdateView,
    PecaDeleteView,
    PecaUsadaRemoverView,
)

urlpatterns = [
    path('', ManutencaoListView.as_view(), name='manutencoes_lista'),
    path('novo/', ManutencaoCreateView.as_view(), name='manutencoes_novo'),
    path('buscar-veiculos/', VeiculoBuscaView.as_view(), name='manutencoes_buscar_veiculos'),
    path('<int:pk>/', ManutencaoDetailView.as_view(), name='manutencoes_detalhe'),
    path('<int:pk>/editar/', ManutencaoUpdateView.as_view(), name='manutencoes_editar'),
    path('<int:pk>/excluir/', ManutencaoDeleteView.as_view(), name='manutencoes_excluir'),
    path('dashboard/', views.dashboard_gerencial, name='dashboard'),
    path('pecas-usadas/<int:pk>/remover/', PecaUsadaRemoverView.as_view(), name='pecas_usadas_remover'),
    path('pecas/', PecaListView.as_view(), name='pecas_lista'),
    path('pecas/nova/', PecaCreateView.as_view(), name='pecas_nova'),
    path('pecas/<int:pk>/editar/', PecaUpdateView.as_view(), name='pecas_editar'),
    path('pecas/<int:pk>/excluir/', PecaDeleteView.as_view(), name='pecas_excluir'),
]
