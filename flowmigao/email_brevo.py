"""Backend de e-mail do Django que envia pela API HTTPS do Brevo.

O Railway bloqueia SMTP nos planos Free, Trial e Hobby, então o envio usa a API
(https://developers.brevo.com/reference/sendtransacemail) em vez do servidor SMTP.
Ativado quando a variável BREVO_API_KEY está definida (veja settings.py).
"""

import json
import logging
from email.utils import getaddresses, parseaddr
from html import escape
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend


logger = logging.getLogger(__name__)

URL_API = 'https://api.brevo.com/v3/smtp/email'


class ErroEnvioBrevo(Exception):
    pass


class BrevoEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, api_key=None, timeout=None, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = api_key or getattr(settings, 'BREVO_API_KEY', '')
        self.timeout = timeout or getattr(settings, 'BREVO_TIMEOUT', 10)
        if not self.api_key:
            raise ImproperlyConfigured('Defina BREVO_API_KEY para enviar e-mails pelo Brevo.')

    def send_messages(self, email_messages):
        enviados = 0
        for mensagem in email_messages:
            if not mensagem.recipients():
                continue
            try:
                self._enviar(mensagem)
                enviados += 1
            except Exception:
                if not self.fail_silently:
                    raise
                logger.exception('Falha ao enviar e-mail pelo Brevo.')
        return enviados

    def _enviar(self, mensagem):
        corpo = json.dumps(montar_payload(mensagem)).encode('utf-8')
        requisicao = Request(
            URL_API,
            data=corpo,
            method='POST',
            headers={
                'api-key': self.api_key,
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
        )
        try:
            with urlopen(requisicao, timeout=self.timeout) as resposta:
                return json.loads(resposta.read() or b'{}')
        except HTTPError as erro:
            detalhe = erro.read().decode('utf-8', errors='replace')
            raise ErroEnvioBrevo(f'Brevo recusou o e-mail (HTTP {erro.code}): {detalhe}') from erro
        except URLError as erro:
            raise ErroEnvioBrevo(f'Não foi possível conectar ao Brevo: {erro.reason}') from erro


def _montar_endereco(nome, email):
    endereco = {'email': email}
    if nome:
        endereco['name'] = nome[:70]  # limite do Brevo
    return endereco


def _endereco(texto):
    """'FlowMigao <avisos@exemplo.com>' -> {'name': 'FlowMigao', 'email': 'avisos@exemplo.com'}"""
    return _montar_endereco(*parseaddr(texto))


def _enderecos(lista):
    return [_montar_endereco(nome, email) for nome, email in getaddresses(lista) if email]


def montar_payload(mensagem):
    """Converte um EmailMessage do Django no JSON esperado pela API do Brevo."""
    html = next(
        (conteudo for conteudo, tipo in getattr(mensagem, 'alternatives', []) if tipo == 'text/html'),
        None,
    )
    if mensagem.content_subtype == 'html':
        html, texto = mensagem.body, None
    else:
        texto = mensagem.body

    payload = {
        'sender': _endereco(mensagem.from_email or settings.DEFAULT_FROM_EMAIL),
        'to': _enderecos(mensagem.to),
        'subject': mensagem.subject,
        # O Brevo exige htmlContent; para mensagens só de texto, gera um HTML equivalente
        'htmlContent': html or f'<div style="white-space: pre-line">{escape(texto or "")}</div>',
    }
    if texto:
        payload['textContent'] = texto
    if mensagem.cc:
        payload['cc'] = _enderecos(mensagem.cc)
    if mensagem.bcc:
        payload['bcc'] = _enderecos(mensagem.bcc)
    if mensagem.reply_to:
        payload['replyTo'] = _endereco(mensagem.reply_to[0])
    return payload
