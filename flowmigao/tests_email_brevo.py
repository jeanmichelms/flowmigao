import io
import json
from datetime import date
from unittest import mock
from urllib.error import HTTPError, URLError

from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.core.mail import EmailMessage, EmailMultiAlternatives, send_mail
from django.test import SimpleTestCase, TestCase, override_settings

from clientes.models import Cliente
from manutencoes.hosted_service import enviar_avisos_revisao
from manutencoes.models import Manutencao
from veiculos.models import Veiculo

from .email_brevo import URL_API, BrevoEmailBackend, ErroEnvioBrevo, montar_payload


BREVO = {
    'EMAIL_BACKEND': 'flowmigao.email_brevo.BrevoEmailBackend',
    'BREVO_API_KEY': 'chave-de-teste',
    'DEFAULT_FROM_EMAIL': 'FlowMigao <avisos@flowmigao.com.br>',
}


def resposta_brevo(status=201, corpo=b'{"messageId": "<abc@smtp-relay.brevo.com>"}'):
    resposta = mock.MagicMock()
    resposta.status = status
    resposta.read.return_value = corpo
    resposta.__enter__.return_value = resposta
    return resposta


def erro_http(codigo, corpo):
    return HTTPError(URL_API, codigo, 'erro', {}, io.BytesIO(corpo))


class MontarPayloadTests(SimpleTestCase):
    def test_mensagem_de_texto_gera_html_equivalente(self):
        mensagem = EmailMessage(
            'Lembrete', 'Olá, Maria.\n\nRevisão em 13/05 <amanhã>', 'FlowMigao <avisos@flowmigao.com.br>',
            ['Maria Silva <maria@example.com>', 'joao@example.com'],
        )

        payload = montar_payload(mensagem)

        self.assertEqual(payload['sender'], {'name': 'FlowMigao', 'email': 'avisos@flowmigao.com.br'})
        self.assertEqual(payload['to'], [
            {'name': 'Maria Silva', 'email': 'maria@example.com'},
            {'email': 'joao@example.com'},
        ])
        self.assertEqual(payload['subject'], 'Lembrete')
        self.assertEqual(payload['textContent'], 'Olá, Maria.\n\nRevisão em 13/05 <amanhã>')
        # O texto vira HTML escapado, mantendo as quebras de linha
        self.assertIn('Revisão em 13/05 &lt;amanhã&gt;', payload['htmlContent'])
        self.assertIn('white-space: pre-line', payload['htmlContent'])

    def test_usa_a_versao_html_quando_existe(self):
        mensagem = EmailMultiAlternatives('Assunto', 'versão texto', 'a@b.com', ['c@d.com'])
        mensagem.attach_alternative('<p>versão <b>HTML</b></p>', 'text/html')

        payload = montar_payload(mensagem)

        self.assertEqual(payload['htmlContent'], '<p>versão <b>HTML</b></p>')
        self.assertEqual(payload['textContent'], 'versão texto')

    def test_copias_e_responder_para(self):
        mensagem = EmailMessage(
            'Assunto', 'corpo', 'a@b.com', ['c@d.com'],
            cc=['copia@d.com'], bcc=['oculta@d.com'], reply_to=['Oficina <oficina@d.com>'],
        )

        payload = montar_payload(mensagem)

        self.assertEqual(payload['cc'], [{'email': 'copia@d.com'}])
        self.assertEqual(payload['bcc'], [{'email': 'oculta@d.com'}])
        self.assertEqual(payload['replyTo'], {'name': 'Oficina', 'email': 'oficina@d.com'})


@override_settings(**BREVO)
class BrevoEmailBackendTests(SimpleTestCase):
    def test_envia_para_a_api_com_a_chave(self):
        with mock.patch('flowmigao.email_brevo.urlopen', return_value=resposta_brevo()) as urlopen:
            enviados = send_mail('Assunto', 'Corpo', None, ['maria@example.com'])

        self.assertEqual(enviados, 1)
        requisicao = urlopen.call_args.args[0]
        self.assertEqual(requisicao.full_url, 'https://api.brevo.com/v3/smtp/email')
        self.assertEqual(requisicao.get_method(), 'POST')
        self.assertEqual(requisicao.get_header('Api-key'), 'chave-de-teste')
        corpo = json.loads(requisicao.data)
        self.assertEqual(corpo['sender'], {'name': 'FlowMigao', 'email': 'avisos@flowmigao.com.br'})
        self.assertEqual(corpo['to'], [{'email': 'maria@example.com'}])

    def test_erro_da_api_vira_excecao_com_a_mensagem_do_brevo(self):
        erro = erro_http(401, b'{"code": "unauthorized", "message": "Key not found"}')

        with mock.patch('flowmigao.email_brevo.urlopen', side_effect=erro):
            with self.assertRaisesMessage(ErroEnvioBrevo, 'HTTP 401'):
                send_mail('Assunto', 'Corpo', None, ['maria@example.com'])

    def test_falha_de_conexao_vira_excecao(self):
        with mock.patch('flowmigao.email_brevo.urlopen', side_effect=URLError('sem internet')):
            with self.assertRaisesMessage(ErroEnvioBrevo, 'sem internet'):
                send_mail('Assunto', 'Corpo', None, ['maria@example.com'])

    def test_fail_silently_nao_levanta_erro(self):
        with mock.patch('flowmigao.email_brevo.urlopen', side_effect=erro_http(400, b'{}')):
            with self.assertLogs('flowmigao.email_brevo', level='ERROR'):
                enviados = send_mail('Assunto', 'Corpo', None, ['maria@example.com'], fail_silently=True)

        self.assertEqual(enviados, 0)

    @override_settings(BREVO_API_KEY='')
    def test_exige_a_chave_da_api(self):
        with self.assertRaises(ImproperlyConfigured):
            BrevoEmailBackend()


@override_settings(**BREVO, AVISO_REVISAO_EMAIL_DIAS_ANTECEDENCIA=3)
class AvisoRevisaoPeloBrevoTests(TestCase):
    """O serviço de aviso de revisão funciona igual, só trocando o transporte para o Brevo."""

    def setUp(self):
        cliente = Cliente.objects.create(nome='Maria Silva', cpf='123.456.789-10', email='maria@example.com')
        veiculo = Veiculo.objects.create(cliente=cliente, marca='Fiat', modelo='Uno', ano=2020, placa='ABC1D23')
        self.manutencao = Manutencao.objects.create(
            veiculo=veiculo, descricao='Revisão', data_manutencao=date(2026, 1, 10),
            quilometragem=10000, valor='250.00', data_proxima_manutencao=date(2026, 5, 13),
        )

    def test_envia_aviso_e_marca_como_enviado(self):
        with mock.patch('flowmigao.email_brevo.urlopen', return_value=resposta_brevo()) as urlopen:
            resultado = enviar_avisos_revisao(data_base=date(2026, 5, 10))

        self.assertEqual(resultado.enviados, 1)
        corpo = json.loads(urlopen.call_args.args[0].data)
        self.assertEqual(corpo['to'], [{'email': 'maria@example.com'}])
        self.assertIn('13/05/2026', corpo['textContent'])
        self.manutencao.refresh_from_db()
        self.assertTrue(self.manutencao.email_aviso_revisao_enviado)
        self.assertEqual(len(mail.outbox), 0)  # nada passou pelo backend de testes: foi para a API

    def test_falha_no_brevo_nao_marca_e_tenta_de_novo_depois(self):
        with mock.patch('flowmigao.email_brevo.urlopen', side_effect=erro_http(500, b'{}')):
            with self.assertLogs('manutencoes.hosted_service', level='ERROR'):
                resultado = enviar_avisos_revisao(data_base=date(2026, 5, 10))

        self.assertEqual((resultado.enviados, resultado.falhas), (0, 1))
        self.manutencao.refresh_from_db()
        self.assertFalse(self.manutencao.email_aviso_revisao_enviado)
