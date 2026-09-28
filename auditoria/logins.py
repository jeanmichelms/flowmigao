"""Registra as tentativas de login malsucedidas (tela de login do sistema e do /admin/)."""
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_login_failed
from django.dispatch import receiver

from .models import TentativaLogin


def ip_do_cliente(request):
    # No Railway o site fica atrás de um proxy, que acrescenta o IP real no fim do X-Forwarded-For.
    # Os valores anteriores vêm do próprio navegador e podem ser forjados, por isso vale o último.
    encaminhado = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if encaminhado:
        return encaminhado.split(',')[-1].strip() or None
    return request.META.get('REMOTE_ADDR') or None


def _motivo_e_usuario(usuario_informado):
    User = get_user_model()
    usuario = User._default_manager.filter(**{User.USERNAME_FIELD: usuario_informado}).first()
    if usuario is None:
        return TentativaLogin.Motivo.USUARIO_INEXISTENTE, None
    if not usuario.is_active:
        return TentativaLogin.Motivo.USUARIO_DESATIVADO, usuario
    return TentativaLogin.Motivo.SENHA_INCORRETA, usuario


@receiver(user_login_failed, dispatch_uid='auditoria_login_malsucedido')
def registrar_login_malsucedido(sender, credentials, request=None, **kwargs):
    # credentials já vem com a senha mascarada pelo Django; só o usuário digitado é usado
    usuario_informado = str(credentials.get(get_user_model().USERNAME_FIELD) or '')[:150]
    motivo, usuario = _motivo_e_usuario(usuario_informado)
    TentativaLogin.objects.create(
        usuario_informado=usuario_informado,
        usuario=usuario,
        motivo=motivo,
        ip=ip_do_cliente(request) if request is not None else None,
        navegador=request.META.get('HTTP_USER_AGENT', '')[:255] if request is not None else '',
    )
