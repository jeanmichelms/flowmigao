import json
import os
import shlex
import shutil
import subprocess
import sys
from datetime import date
from unittest import mock, skipUnless

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from clientes.models import Cliente
from manutencoes.models import Manutencao, Peca
from usuarios.apoio_testes import entrar
from veiculos.models import Veiculo

from .ambiente import banco_mysql_da_url, ler_bool, ler_lista


class AcessibilidadeTests(TestCase):
    """Garante que as páginas mantêm a estrutura acessível (WCAG) montada nos templates."""

    @classmethod
    def setUpTestData(cls):
        cls.cliente = Cliente.objects.create(nome='Ana', cpf='111.222.333-44', email='ana@example.com')
        cls.veiculo = Veiculo.objects.create(
            cliente=cls.cliente, marca='Fiat', modelo='Uno', ano=2010, placa='ABC1D23'
        )
        cls.manutencao = Manutencao.objects.create(
            veiculo=cls.veiculo,
            descricao='Troca de óleo',
            data_manutencao=date(2026, 1, 10),
            quilometragem=50000,
            valor=250,
        )
        cls.peca = Peca.objects.create(nome='Filtro de óleo', preco_custo=30)

    def setUp(self):
        entrar(self.client)

    def paginas(self):
        return {
            'home': reverse('home'),
            'clientes': reverse('clientes_lista'),
            'cliente_novo': reverse('clientes_novo'),
            'cliente_detalhe': reverse('clientes_detalhe', args=[self.cliente.pk]),
            'veiculos': reverse('veiculos_lista'),
            'veiculo_novo': reverse('veiculos_novo'),
            'veiculo_detalhe': reverse('veiculos_detalhe', args=[self.veiculo.pk]),
            'manutencoes': reverse('manutencoes_lista'),
            'manutencao_nova': reverse('manutencoes_novo'),
            'manutencao_detalhe': reverse('manutencoes_detalhe', args=[self.manutencao.pk]),
            'pecas': reverse('pecas_lista'),
            'peca_nova': reverse('pecas_nova'),
            'dashboard': reverse('dashboard'),
        }

    def test_estrutura_basica_em_todas_as_paginas(self):
        for nome, url in self.paginas().items():
            with self.subTest(pagina=nome):
                resposta = self.client.get(url)
                self.assertEqual(resposta.status_code, 200)
                html = resposta.content.decode()

                self.assertIn('<html lang="pt-BR">', html)
                self.assertIn('<a class="pular-conteudo" href="#conteudo">', html)
                self.assertIn('<main id="conteudo"', html)
                self.assertIn('<nav aria-label="Menu principal">', html)
                self.assertIn('id="anuncios"', html)
                self.assertIn('aria-live="polite"', html)
                # Um único título principal por página
                self.assertEqual(html.count('<h1'), 1)
                # Barra com tamanho da fonte e alto contraste
                self.assertIn('aria-label="Opções de acessibilidade"', html)
                self.assertIn('id="fonte-aumentar"', html)
                self.assertIn('id="fonte-diminuir"', html)
                self.assertIn('id="alto-contraste" aria-pressed="false"', html)

    def test_titulo_da_aba_muda_conforme_a_pagina(self):
        titulos = {
            reverse('home'): '<title>Início – FlowMigao</title>',
            reverse('clientes_lista'): '<title>Clientes – FlowMigao</title>',
            reverse('clientes_novo'): '<title>Novo Cliente – FlowMigao</title>',
            reverse('dashboard'): '<title>Painel Gerencial – FlowMigao</title>',
        }
        for url, titulo in titulos.items():
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), titulo, html=False)

    def test_menu_marca_a_pagina_atual(self):
        resposta = self.client.get(reverse('veiculos_detalhe', args=[self.veiculo.pk]))

        self.assertContains(
            resposta,
            f'<a href="{reverse("veiculos_lista")}" aria-current="page">Veículos</a>',
            html=True,
        )
        self.assertContains(resposta, ' aria-current="page">', count=1)

    def test_tabelas_tem_legenda_e_cabecalhos_com_escopo(self):
        for url in (reverse('clientes_lista'), reverse('veiculos_lista'),
                    reverse('manutencoes_lista'), reverse('pecas_lista'), reverse('dashboard')):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertIn('<caption', html)
                self.assertIn('<th scope="col">', html)
                self.assertNotIn('<th>', html)

    def test_botoes_de_acao_identificam_o_registro(self):
        resposta = self.client.get(reverse('clientes_lista'))

        self.assertContains(resposta, 'Excluir<span class="visually-hidden"> cliente Ana</span>')

    def test_formulario_de_cliente_tem_rotulos_e_autocomplete(self):
        resposta = self.client.get(reverse('clientes_novo'))

        self.assertContains(resposta, '<label for="id_cpf">CPF', html=False)
        self.assertContains(resposta, '<label for="id_endereco">Endereço (rua/avenida)', html=False)
        self.assertContains(resposta, 'autocomplete="email"')
        self.assertContains(resposta, 'autocomplete="postal-code"')
        # Texto de ajuda do CEP ligado ao campo
        self.assertContains(resposta, 'aria-describedby="id_cep_helptext"')
        self.assertContains(resposta, 'id="id_cep_helptext"')

    def test_erro_de_validacao_fica_ligado_ao_campo(self):
        resposta = self.client.post(reverse('clientes_novo'), {'nome': '', 'cpf': '', 'email': 'invalido'})

        self.assertEqual(resposta.status_code, 200)
        # Resumo no topo, com link para cada campo com problema
        self.assertContains(resposta, 'id="resumo-erros"')
        self.assertContains(resposta, 'href="#id_email"')
        # Campo marcado como inválido e descrito pela mensagem de erro
        self.assertContains(resposta, 'aria-invalid="true"')
        self.assertContains(resposta, 'aria-describedby="id_email_error"')
        self.assertContains(resposta, 'id="id_email_error"')

    def test_erro_no_cliente_do_veiculo_aponta_para_o_campo_visivel(self):
        resposta = self.client.post(
            reverse('veiculos_novo'),
            {'marca': 'Fiat', 'modelo': 'Uno', 'ano': 2015, 'placa': 'XYZ9A87'},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'href="#id_cliente_busca"')
        self.assertContains(resposta, 'aria-describedby="id_cliente_busca_ajuda id_cliente_error"')
        self.assertContains(resposta, 'id="id_cliente_error"')

    def test_modal_de_busca_e_um_dialogo_rotulado(self):
        for url, titulo in ((reverse('veiculos_novo'), 'titulo-modal-cliente'),
                            (reverse('manutencoes_novo'), 'titulo-modal-veiculo')):
            with self.subTest(url=url):
                resposta = self.client.get(url)
                self.assertContains(
                    resposta, f'role="dialog" aria-modal="true" aria-labelledby="{titulo}"'
                )
                self.assertContains(resposta, 'aria-haspopup="dialog"')


class SaudeTests(TestCase):
    def test_responde_ok_quando_o_banco_conecta(self):
        resposta = self.client.get(reverse('saude'))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.json(), {'status': 'ok'})

    def test_responde_503_quando_o_banco_esta_fora(self):
        with mock.patch('flowmigao.urls.connection.ensure_connection', side_effect=OperationalError):
            resposta = self.client.get(reverse('saude'))

        self.assertEqual(resposta.status_code, 503)
        self.assertEqual(resposta.json()['status'], 'erro')

    def test_responde_503_com_migracoes_pendentes(self):
        # Foi o que aconteceu no primeiro deploy: banco conectava, mas sem tabelas
        with mock.patch('flowmigao.urls.MigrationExecutor.migration_plan', return_value=[('migracao', False)] * 3):
            resposta = self.client.get(reverse('saude'))

        self.assertEqual(resposta.status_code, 503)
        self.assertEqual(resposta.json(), {'status': 'erro', 'migracoes_pendentes': 3})


class AmbienteTests(SimpleTestCase):
    def test_converte_mysql_url_do_railway(self):
        conexao = banco_mysql_da_url('mysql://root:s3nh4@mysql.railway.internal:3306/railway')

        self.assertEqual(conexao, {
            'NAME': 'railway',
            'USER': 'root',
            'PASSWORD': 's3nh4',
            'HOST': 'mysql.railway.internal',
            'PORT': '3306',
        })

    def test_decodifica_caracteres_especiais_e_usa_porta_padrao(self):
        conexao = banco_mysql_da_url('mysql://app:a%40b%3Ac@db.exemplo.com/flowmigao')

        self.assertEqual(conexao['PASSWORD'], 'a@b:c')
        self.assertEqual(conexao['PORT'], '3306')

    def test_rejeita_url_invalida(self):
        for url in ('postgres://u:s@host/banco', 'mysql://u:s@host/', 'mysql:///banco'):
            with self.subTest(url=url), self.assertRaises(ImproperlyConfigured):
                banco_mysql_da_url(url)

    def test_ler_lista_e_ler_bool(self):
        with mock.patch.dict(os.environ, {'LISTA': ' a.com, ,b.com ', 'LIGADO': 'Sim', 'VAZIO': ''}):
            self.assertEqual(ler_lista('LISTA'), ['a.com', 'b.com'])
            self.assertEqual(ler_lista('NAO_EXISTE_XYZ'), [])
            self.assertTrue(ler_bool('LIGADO', padrao=False))
            self.assertTrue(ler_bool('VAZIO', padrao=True))
            self.assertFalse(ler_bool('NAO_EXISTE_XYZ', padrao=False))


NEUTRAS = (
    'RAILWAY_ENVIRONMENT_ID', 'RAILWAY_PUBLIC_DOMAIN', 'DATABASE_URL', 'BREVO_API_KEY', 'EMAIL_BACKEND',
    'DJANGO_DEBUG', 'DJANGO_SECRET_KEY', 'DJANGO_ALLOWED_HOSTS', 'DJANGO_CSRF_TRUSTED_ORIGINS',
)


class ConfiguracaoProducaoTests(SimpleTestCase):
    """Carrega o settings em um processo separado, simulando as variáveis do Railway."""

    CHAVE = 'chave-de-teste-com-mais-de-cinquenta-caracteres-0123456789abcdef'

    def rodar(self, comando, **variaveis):
        ambiente = dict(os.environ)
        # Valores vazios têm prioridade sobre o .env local (o load_dotenv não sobrescreve),
        # assim o resultado não depende da configuração da máquina de quem roda os testes.
        for chave in NEUTRAS:
            ambiente[chave] = ''
        ambiente.update(variaveis)
        return subprocess.run(
            [sys.executable, '-c', comando],
            cwd=settings.BASE_DIR, env=ambiente, capture_output=True, text=True, timeout=60,
        )

    def ler_settings(self, **variaveis):
        comando = (
            'import json, os; os.environ["DJANGO_SETTINGS_MODULE"] = "flowmigao.settings"; '
            'from django.conf import settings as s; '
            'print(json.dumps({"DEBUG": s.DEBUG, "HOSTS": s.ALLOWED_HOSTS, "CSRF": s.CSRF_TRUSTED_ORIGINS, '
            '"SSL": getattr(s, "SECURE_SSL_REDIRECT", False), "BANCO": s.DATABASES["default"].get("HOST", ""), "EMAIL": s.EMAIL_BACKEND}))'
        )
        resultado = self.rodar(comando, **variaveis)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        return json.loads(resultado.stdout)

    def test_no_railway_desliga_debug_e_libera_o_dominio_publico(self):
        config = self.ler_settings(
            RAILWAY_ENVIRONMENT_ID='abc',
            RAILWAY_PUBLIC_DOMAIN='flowmigao.up.railway.app',
            DJANGO_SECRET_KEY=self.CHAVE,
            DATABASE_URL='mysql://root:senha@mysql.railway.internal:3306/railway',
            BREVO_API_KEY='chave-brevo',
        )

        self.assertFalse(config['DEBUG'])
        self.assertTrue(config['SSL'])
        self.assertIn('flowmigao.up.railway.app', config['HOSTS'])
        self.assertIn('healthcheck.railway.app', config['HOSTS'])
        self.assertEqual(config['CSRF'], ['https://flowmigao.up.railway.app'])
        self.assertEqual(config['BANCO'], 'mysql.railway.internal')
        self.assertEqual(config['EMAIL'], 'flowmigao.email_brevo.BrevoEmailBackend')

    def test_local_mantem_debug_ligado(self):
        config = self.ler_settings(DB_ENGINE='sqlite')

        self.assertTrue(config['DEBUG'])
        self.assertFalse(config['SSL'])
        self.assertEqual(config['HOSTS'], ['localhost', '127.0.0.1', '[::1]'])
        self.assertEqual(config['EMAIL'], 'django.core.mail.backends.smtp.EmailBackend')

    def test_railway_aplica_as_migracoes_antes_de_subir_o_site(self):
        with open(settings.BASE_DIR / 'railway.json', encoding='utf-8') as arquivo:
            deploy = json.load(arquivo)['deploy']
        inicio = deploy['startCommand']

        self.assertIn('python manage.py migrate --noinput && exec gunicorn', inicio)
        self.assertEqual(deploy['healthcheckPath'], '/saude/')

    @skipUnless(shutil.which('sh'), 'precisa do sh, como no build do Railway')
    def test_build_do_railway_roda_sem_a_chave_secreta(self):
        # O Railway executa o buildCommand com "sh -c"; o collectstatic não pode depender da DJANGO_SECRET_KEY
        with open(settings.BASE_DIR / 'railway.json', encoding='utf-8') as arquivo:
            comando = json.load(arquivo)['build']['buildCommand']
        comando = comando.replace('python ', f'{shlex.quote(sys.executable)} ', 1)

        ambiente = dict(os.environ, RAILWAY_ENVIRONMENT_ID='abc', DB_ENGINE='sqlite')
        for chave in NEUTRAS:
            if chave != 'RAILWAY_ENVIRONMENT_ID':
                ambiente[chave] = ''
        resultado = subprocess.run(
            ['sh', '-c', comando], cwd=settings.BASE_DIR, env=ambiente,
            capture_output=True, text=True, timeout=120,
        )

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
        self.assertIn('static files', resultado.stdout)

    def test_producao_sem_chave_secreta_nao_sobe(self):
        resultado = self.rodar(
            'import os; os.environ["DJANGO_SETTINGS_MODULE"] = "flowmigao.settings"; '
            'from django.conf import settings; settings.DEBUG',
            RAILWAY_ENVIRONMENT_ID='abc',
        )

        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn('DJANGO_SECRET_KEY', resultado.stderr)

    def test_checklist_de_deploy_do_django_sem_avisos(self):
        resultado = self.rodar(
            'import sys; from django.core.management import execute_from_command_line; '
            'execute_from_command_line(["manage.py", "check", "--deploy", "--fail-level", "WARNING"])',
            DJANGO_SETTINGS_MODULE='flowmigao.settings',
            RAILWAY_ENVIRONMENT_ID='abc',
            RAILWAY_PUBLIC_DOMAIN='flowmigao.up.railway.app',
            DJANGO_SECRET_KEY=self.CHAVE,
            DB_ENGINE='sqlite',
        )

        self.assertEqual(resultado.returncode, 0, resultado.stdout + resultado.stderr)
