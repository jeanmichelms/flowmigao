from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db import models


class RegistroAuditoria(models.Model):
    """Uma inclusão, alteração ou exclusão feita em um registro do sistema."""

    class Acao(models.TextChoices):
        INCLUSAO = 'INCLUSAO', 'Inclusão'
        ALTERACAO = 'ALTERACAO', 'Alteração'
        EXCLUSAO = 'EXCLUSAO', 'Exclusão'

    data_hora = models.DateTimeField('Data e hora', auto_now_add=True, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    # Nome guardado à parte: o registro continua dizendo quem foi mesmo que o usuário seja excluído.
    # Vazio quando a alteração foi feita pelo próprio sistema.
    usuario_nome = models.CharField('Usuário', max_length=150, blank=True)
    acao = models.CharField('Ação', max_length=10, choices=Acao.choices)
    tipo = models.ForeignKey(ContentType, on_delete=models.PROTECT, verbose_name='Tipo de registro')
    objeto_id = models.CharField('ID do registro', max_length=64)
    objeto_descricao = models.CharField('Registro', max_length=255)
    # Lista de {"campo": rótulo, "de": valor anterior, "para": valor novo}, já formatados para exibição
    alteracoes = models.JSONField('Alterações', default=list, blank=True)

    class Meta:
        ordering = ['-data_hora', '-id']
        indexes = [models.Index(fields=['tipo', 'objeto_id'])]
        verbose_name = 'Registro de auditoria'
        verbose_name_plural = 'Registros de auditoria'

    def __str__(self):
        return f'{self.get_acao_display()} de {self.objeto_descricao} por {self.autor}'

    @property
    def autor(self):
        return self.usuario_nome or 'Sistema'

    @property
    def tipo_nome(self):
        modelo = self.tipo.model_class()
        return modelo._meta.verbose_name if modelo else self.tipo.model


class TentativaLogin(models.Model):
    """Tentativa de login que não deu certo. A senha digitada nunca é gravada."""

    class Motivo(models.TextChoices):
        SENHA_INCORRETA = 'SENHA', 'Senha incorreta'
        USUARIO_INEXISTENTE = 'INEXISTENTE', 'Usuário não cadastrado'
        USUARIO_DESATIVADO = 'DESATIVADO', 'Usuário desativado'

    data_hora = models.DateTimeField('Data e hora', auto_now_add=True, db_index=True)
    usuario_informado = models.CharField('Usuário informado', max_length=150)
    # Preenchido quando o usuário digitado existe (senha incorreta ou usuário desativado)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='+'
    )
    motivo = models.CharField('Motivo', max_length=12, choices=Motivo.choices)
    ip = models.GenericIPAddressField('IP', null=True, blank=True)
    navegador = models.CharField('Navegador', max_length=255, blank=True)

    class Meta:
        ordering = ['-data_hora', '-id']
        verbose_name = 'Tentativa de login malsucedida'
        verbose_name_plural = 'Tentativas de login malsucedidas'

    def __str__(self):
        return f'{self.usuario_informado} ({self.get_motivo_display()})'
