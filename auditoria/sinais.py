"""Registra automaticamente quem incluiu, alterou ou excluiu os registros monitorados.

Usa os sinais do Django, então vale para qualquer tela (e também para o /admin/ e para o serviço
de aviso de revisão), sem precisar mexer em cada view.
"""
import datetime
from dataclasses import dataclass, field

from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ObjectDoesNotExist
from django.db.models.signals import post_delete, post_save, pre_delete, pre_save
from django.utils import timezone

from .contexto import usuario_atual
from .models import RegistroAuditoria


@dataclass
class Monitorado:
    rotulos: dict = field(default_factory=dict)   # nome do campo -> rótulo exibido
    ignorar: set = field(default_factory=set)     # campos que não entram no histórico
    ocultar: set = field(default_factory=set)     # campos cujo valor nunca é gravado (só "alterado")


MONITORADOS = {
    'clientes.Cliente': Monitorado(
        rotulos={
            'nome': 'Nome', 'cpf': 'CPF', 'email': 'E-mail', 'telefone': 'Telefone', 'cep': 'CEP',
            'endereco': 'Endereço', 'numero': 'Número', 'bairro': 'Bairro', 'cidade': 'Cidade',
            'estado': 'Estado (UF)',
        },
        ignorar={'data_cadastro'},
    ),
    'veiculos.Veiculo': Monitorado(
        rotulos={
            'cliente': 'Cliente', 'marca': 'Marca', 'modelo': 'Modelo', 'ano': 'Ano', 'placa': 'Placa',
            'cor': 'Cor', 'chassi': 'Chassi',
        },
        ignorar={'data_cadastro'},
    ),
    'manutencoes.Manutencao': Monitorado(
        rotulos={
            'veiculo': 'Veículo', 'tipo': 'Tipo de manutenção', 'descricao': 'Descrição',
            'data_manutencao': 'Data da manutenção', 'quilometragem': 'Quilometragem', 'valor': 'Valor (R$)',
            'observacoes': 'Observações', 'data_proxima_manutencao': 'Data prevista da próxima manutenção',
            'email_aviso_revisao_enviado': 'Aviso de revisão enviado',
        },
        ignorar={'data_cadastro'},
    ),
    'manutencoes.Peca': Monitorado(
        rotulos={'nome': 'Nome', 'marca': 'Marca', 'preco_custo': 'Preço de custo (R$)'},
    ),
    'manutencoes.PecaUsada': Monitorado(
        rotulos={
            'manutencao': 'Manutenção', 'peca': 'Peça', 'quantidade': 'Quantidade',
            'valor_total_custo': 'Custo total (R$)',
        },
    ),
    'auth.User': Monitorado(
        rotulos={
            'username': 'Usuário', 'first_name': 'Nome', 'last_name': 'Sobrenome', 'email': 'E-mail',
            'is_active': 'Ativo', 'is_superuser': 'Administrador', 'is_staff': 'Acesso ao /admin/',
            'password': 'Senha',
        },
        # last_login muda a cada login e date_joined nunca muda: só gerariam ruído
        ignorar={'last_login', 'date_joined'},
        ocultar={'password'},
    ),
}


def modelos_monitorados():
    return {apps.get_model(nome): config for nome, config in MONITORADOS.items()}


def _formatar(instancia, campo):
    """Valor do campo como texto para exibição (None quando vazio)."""
    valor = getattr(instancia, campo.attname)
    if valor is None or valor == '':
        return None
    if campo.is_relation:
        try:
            return str(getattr(instancia, campo.name))
        except ObjectDoesNotExist:
            return f'#{valor}'
    if campo.choices:
        return str(dict(campo.flatchoices).get(valor, valor))
    if isinstance(valor, bool):
        return 'Sim' if valor else 'Não'
    if isinstance(valor, datetime.datetime):
        if timezone.is_aware(valor):
            valor = timezone.localtime(valor)
        return valor.strftime('%d/%m/%Y %H:%M')
    if isinstance(valor, datetime.date):
        return valor.strftime('%d/%m/%Y')
    return str(valor)


def _campos(modelo, config, somente=None):
    for campo in modelo._meta.concrete_fields:
        if campo.primary_key or campo.name in config.ignorar:
            continue
        if somente is not None and campo.name not in somente:
            continue
        yield campo


def _rotulo(campo, config):
    return config.rotulos.get(campo.name) or str(campo.verbose_name).capitalize()


def _valores(instancia, config, somente=None):
    """{campo: (valor bruto para comparar, texto para exibir)}"""
    valores = {}
    for campo in _campos(type(instancia), config, somente):
        bruto = getattr(instancia, campo.attname)
        if not campo.is_relation and bruto is not None:
            bruto = campo.to_python(bruto)
        if bruto == '':
            bruto = None
        exibir = None if campo.name in config.ocultar else _formatar(instancia, campo)
        valores[campo.name] = (bruto, exibir)
    return valores


def _registrar(acao, modelo, objeto_id, descricao, alteracoes):
    usuario = usuario_atual()
    RegistroAuditoria.objects.create(
        usuario=usuario,
        usuario_nome=usuario.get_username() if usuario else '',
        acao=acao,
        tipo=ContentType.objects.get_for_model(modelo),
        objeto_id=str(objeto_id),
        objeto_descricao=descricao[:255],
        alteracoes=alteracoes,
    )


def _lista_de_valores(modelo, config, valores, chave):
    """Todos os campos preenchidos, para inclusão ("para") ou exclusão ("de")."""
    lista = []
    for campo in _campos(modelo, config):
        if campo.name in config.ocultar:
            continue
        exibir = valores[campo.name][1]
        if exibir is not None:
            lista.append({'campo': _rotulo(campo, config), 'de': None, 'para': None, chave: exibir})
    return lista


def _criar_receptores(modelo, config):
    def antes_de_salvar(sender, instance, raw=False, update_fields=None, **kwargs):
        instance._auditoria_antes = None
        if raw or instance.pk is None:
            return
        antigo = sender._default_manager.filter(pk=instance.pk).first()
        if antigo is not None:
            instance._auditoria_antes = _valores(antigo, config, update_fields)

    def depois_de_salvar(sender, instance, created, raw=False, update_fields=None, **kwargs):
        if raw:
            return
        if created:
            valores = _valores(instance, config)
            _registrar(
                RegistroAuditoria.Acao.INCLUSAO, sender, instance.pk, str(instance),
                _lista_de_valores(sender, config, valores, 'para'),
            )
            return

        antes = getattr(instance, '_auditoria_antes', None)
        if antes is None:
            return
        depois = _valores(instance, config, update_fields)
        alteracoes = []
        for campo in _campos(sender, config, update_fields):
            if antes[campo.name][0] == depois[campo.name][0]:
                continue
            if campo.name in config.ocultar:
                alteracoes.append({'campo': _rotulo(campo, config), 'de': None, 'para': '(alterada)'})
            else:
                alteracoes.append({
                    'campo': _rotulo(campo, config), 'de': antes[campo.name][1], 'para': depois[campo.name][1],
                })
        if alteracoes:
            _registrar(RegistroAuditoria.Acao.ALTERACAO, sender, instance.pk, str(instance), alteracoes)

    def antes_de_excluir(sender, instance, **kwargs):
        # Guarda os dados agora: depois da exclusão, registros ligados (ex.: o cliente do veículo) podem já não existir
        instance._auditoria_exclusao = (instance.pk, str(instance), _valores(instance, config))

    def depois_de_excluir(sender, instance, **kwargs):
        dados = getattr(instance, '_auditoria_exclusao', None)
        if dados is None:
            return
        objeto_id, descricao, valores = dados
        _registrar(
            RegistroAuditoria.Acao.EXCLUSAO, sender, objeto_id, descricao,
            _lista_de_valores(sender, config, valores, 'de'),
        )

    return antes_de_salvar, depois_de_salvar, antes_de_excluir, depois_de_excluir


_receptores = []  # mantém referência forte aos receptores criados dinamicamente


def conectar_sinais():
    for modelo, config in modelos_monitorados().items():
        antes_salvar, depois_salvar, antes_excluir, depois_excluir = _criar_receptores(modelo, config)
        _receptores.append((antes_salvar, depois_salvar, antes_excluir, depois_excluir))
        uid = f'auditoria_{modelo._meta.label_lower}'
        pre_save.connect(antes_salvar, sender=modelo, dispatch_uid=uid)
        post_save.connect(depois_salvar, sender=modelo, dispatch_uid=uid)
        pre_delete.connect(antes_excluir, sender=modelo, dispatch_uid=uid)
        post_delete.connect(depois_excluir, sender=modelo, dispatch_uid=uid)
