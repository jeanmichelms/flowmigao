from django.apps import AppConfig


class UsuariosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'usuarios'

    def ready(self):
        # Registra a regra que impede a tabela de usuários de ficar vazia
        from . import regras  # noqa: F401
