from urllib.parse import urlencode

from django import template
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse

from ..models import RegistroAuditoria

register = template.Library()


@register.inclusion_tag('auditoria/resumo.html', takes_context=True)
def resumo_auditoria(context, objeto):
    """Quem cadastrou e quem alterou por último o registro. Uso: {% resumo_auditoria cliente %}"""
    tipo = ContentType.objects.get_for_model(objeto)
    registros = RegistroAuditoria.objects.filter(tipo=tipo, objeto_id=str(objeto.pk))
    usuario = context['request'].user
    historico_url = None
    if usuario.is_superuser:
        historico_url = reverse('auditoria_lista') + '?' + urlencode(
            {'tipo': f'{tipo.app_label}.{tipo.model}', 'objeto': objeto.pk}
        )
    return {
        'inclusao': registros.filter(acao=RegistroAuditoria.Acao.INCLUSAO).order_by('data_hora', 'id').first(),
        'alteracao': registros.filter(acao=RegistroAuditoria.Acao.ALTERACAO).first(),
        'historico_url': historico_url,
    }
