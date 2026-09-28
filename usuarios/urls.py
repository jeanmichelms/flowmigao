from django.contrib.auth.views import LogoutView
from django.urls import path

from .views import (
    AlterarSenhaView,
    EntrarView,
    UsuarioCreateView,
    UsuarioDeleteView,
    UsuarioListView,
    UsuarioUpdateView,
)

urlpatterns = [
    path('login/', EntrarView.as_view(), name='login'),
    path('sair/', LogoutView.as_view(), name='logout'),
    path('minha-senha/', AlterarSenhaView.as_view(), name='alterar_senha'),
    path('usuarios/', UsuarioListView.as_view(), name='usuarios_lista'),
    path('usuarios/novo/', UsuarioCreateView.as_view(), name='usuarios_novo'),
    path('usuarios/<int:pk>/editar/', UsuarioUpdateView.as_view(), name='usuarios_editar'),
    path('usuarios/<int:pk>/excluir/', UsuarioDeleteView.as_view(), name='usuarios_excluir'),
]
