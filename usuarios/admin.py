from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from .regras import motivo_para_nao_excluir

User = get_user_model()

admin.site.unregister(User)


@admin.register(User)
class UsuarioAdmin(UserAdmin):
    """Aplica no /admin/ as mesmas regras de exclusão das telas do sistema."""

    def has_delete_permission(self, request, obj=None):
        if obj is not None and motivo_para_nao_excluir(obj, request.user):
            return False
        return super().has_delete_permission(request, obj)

    def get_actions(self, request):
        # A exclusão em lote poderia incluir o próprio usuário
        actions = super().get_actions(request)
        actions.pop('delete_selected', None)
        return actions
