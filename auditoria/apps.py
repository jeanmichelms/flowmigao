from django.apps import AppConfig


class AuditoriaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auditoria'
    verbose_name = 'Auditoria'

    def ready(self):
        from . import logins  # noqa: F401  (registra as tentativas de login malsucedidas)
        from .sinais import conectar_sinais
        conectar_sinais()
