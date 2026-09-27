import os
import sys

from django.apps import AppConfig
from django.conf import settings


class ManutencoesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'manutencoes'

    def ready(self):
        if not self._deve_iniciar_servico():
            return

        from .hosted_service import iniciar_servico_aviso_revisao

        iniciar_servico_aviso_revisao()

    @staticmethod
    def _deve_iniciar_servico():
        if not getattr(settings, 'AVISO_REVISAO_EMAIL_SERVICO_ATIVO', True):
            return False

        if len(sys.argv) <= 1:
            return True

        comando = sys.argv[1]
        if comando == 'runserver':
            return os.environ.get('RUN_MAIN') == 'true' or '--noreload' in sys.argv

        return os.path.basename(sys.argv[0]).lower() != 'manage.py'
