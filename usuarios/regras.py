"""Regras de negócio dos usuários do sistema.

- Administrador é o usuário com is_superuser (o mesmo criado pelo createsuperuser).
- Ninguém pode excluir o próprio usuário.
- A tabela de usuários nunca pode ficar vazia.
"""
from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete
from django.dispatch import receiver

User = get_user_model()


class UsuarioObrigatorioError(Exception):
    """Tentativa de excluir o último usuário cadastrado."""


def eh_administrador(usuario):
    return usuario.is_authenticated and usuario.is_superuser


def motivo_para_nao_excluir(usuario, solicitante):
    """Devolve o motivo que impede a exclusão ou None se ela for permitida."""
    if usuario.pk == solicitante.pk:
        return 'Você não pode excluir o seu próprio usuário.'
    if not User.objects.exclude(pk=usuario.pk).exists():
        return 'Deve existir pelo menos um usuário cadastrado.'
    return None


@receiver(post_delete, sender=User)
def impedir_tabela_vazia(sender, instance, **kwargs):
    # Roda dentro da transação da exclusão: o erro desfaz tudo, inclusive exclusões em lote
    # (pelo shell ou pelo /admin/), que não passam pelas telas do sistema.
    if not User.objects.exists():
        raise UsuarioObrigatorioError('Deve existir pelo menos um usuário cadastrado.')
