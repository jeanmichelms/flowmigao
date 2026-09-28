"""Leitura das configurações vindas de variáveis de ambiente (arquivo .env local ou Railway)."""

import os
from urllib.parse import unquote, urlsplit

from django.core.exceptions import ImproperlyConfigured


VERDADEIROS = ('1', 'true', 'yes', 'sim', 'on')


def ler_bool(nome, padrao):
    valor = os.getenv(nome)
    if valor is None or valor.strip() == '':
        return padrao
    return valor.strip().lower() in VERDADEIROS


def ler_lista(nome):
    """Lê uma lista separada por vírgulas, ignorando espaços e itens vazios."""
    return [item.strip() for item in os.getenv(nome, '').split(',') if item.strip()]


def banco_mysql_da_url(url):
    """Converte uma URL como mysql://usuario:senha@host:3306/banco (MYSQL_URL do Railway)
    nos campos de conexão do Django."""
    partes = urlsplit(url)
    if partes.scheme != 'mysql':
        raise ImproperlyConfigured(f'DATABASE_URL deve começar com mysql://, recebido: {partes.scheme}://')

    nome = unquote(partes.path.lstrip('/'))
    if not nome or not partes.hostname:
        raise ImproperlyConfigured('DATABASE_URL precisa informar o host e o nome do banco.')

    return {
        'NAME': nome,
        'USER': unquote(partes.username or ''),
        'PASSWORD': unquote(partes.password or ''),
        'HOST': partes.hostname,
        'PORT': str(partes.port or 3306),
    }
