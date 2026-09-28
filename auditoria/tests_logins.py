from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from usuarios.apoio_testes import entrar

from .models import TentativaLogin

User = get_user_model()
Motivo = TentativaLogin.Motivo
SENHA = 'Senha-de-teste-123'
# O hash padrão das senhas é lento de propósito; nos testes isso só atrasa
HASH_RAPIDO = override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])


@HASH_RAPIDO
class RegistroDeLoginMalsucedidoTests(TestCase):
    def setUp(self):
        self.maria = User.objects.create_user('maria', password=SENHA)

    def tentar(self, usuario, senha, **cabecalhos):
        return self.client.post(
            reverse('login'), {'username': usuario, 'password': senha},
            HTTP_USER_AGENT='Navegador de teste/1.0', **cabecalhos,
        )

    def test_senha_incorreta(self):
        self.tentar('maria', 'senha-errada-123')

        tentativa = TentativaLogin.objects.get()
        self.assertEqual(tentativa.usuario_informado, 'maria')
        self.assertEqual(tentativa.usuario, self.maria)
        self.assertEqual(tentativa.motivo, Motivo.SENHA_INCORRETA)
        self.assertEqual(tentativa.ip, '127.0.0.1')
        self.assertEqual(tentativa.navegador, 'Navegador de teste/1.0')

    def test_usuario_nao_cadastrado(self):
        self.tentar('fulano', 'qualquer-coisa')

        tentativa = TentativaLogin.objects.get()
        self.assertEqual(tentativa.usuario_informado, 'fulano')
        self.assertIsNone(tentativa.usuario)
        self.assertEqual(tentativa.motivo, Motivo.USUARIO_INEXISTENTE)

    def test_usuario_desativado_mesmo_com_a_senha_certa(self):
        self.maria.is_active = False
        self.maria.save()

        self.tentar('maria', SENHA)

        self.assertEqual(TentativaLogin.objects.get().motivo, Motivo.USUARIO_DESATIVADO)

    def test_senha_digitada_nunca_e_gravada(self):
        self.tentar('maria', 'minha-senha-secreta')

        valores = TentativaLogin.objects.values_list(flat=False)
        self.assertNotIn('minha-senha-secreta', str(list(valores)))

    def test_login_certo_nao_registra(self):
        self.tentar('maria', SENHA)

        self.assertFalse(TentativaLogin.objects.exists())

    def test_formulario_incompleto_nao_registra(self):
        # Sem usuário ou senha o Django nem tenta autenticar
        self.tentar('', SENHA)

        self.assertFalse(TentativaLogin.objects.exists())

    def test_login_do_admin_do_django_tambem_registra(self):
        self.client.post(reverse('admin:login'), {'username': 'maria', 'password': 'errada'})

        self.assertEqual(TentativaLogin.objects.get().motivo, Motivo.SENHA_INCORRETA)

    def test_ip_atras_do_proxy_do_railway(self):
        # O último IP é o que o proxy acrescentou; o primeiro veio do navegador e pode ser forjado
        self.tentar('maria', 'errada', HTTP_X_FORWARDED_FOR='1.2.3.4, 200.10.20.30')

        self.assertEqual(TentativaLogin.objects.get().ip, '200.10.20.30')

    def test_usuario_excluido_mantem_o_nome_informado(self):
        self.tentar('maria', 'errada')
        User.objects.create_user('outro')

        self.maria.delete()

        tentativa = TentativaLogin.objects.get()
        self.assertIsNone(tentativa.usuario)
        self.assertEqual(tentativa.usuario_informado, 'maria')


class TelaDeLoginsMalsucedidosTests(TestCase):
    def setUp(self):
        TentativaLogin.objects.create(
            usuario_informado='maria', motivo=Motivo.SENHA_INCORRETA, ip='10.0.0.1', navegador='Firefox'
        )
        TentativaLogin.objects.create(usuario_informado='fulano', motivo=Motivo.USUARIO_INEXISTENTE, ip='10.0.0.2')
        entrar(self.client, 'chefe', administrador=True)

    def test_somente_administrador_acessa(self):
        entrar(self.client, 'comum')

        self.assertEqual(self.client.get(reverse('auditoria_logins')).status_code, 403)

    def test_lista_as_tentativas(self):
        resposta = self.client.get(reverse('auditoria_logins'))

        self.assertContains(resposta, '<title>Logins malsucedidos – FlowMigao</title>', html=False)
        self.assertContains(resposta, '2 registros encontrados.')
        self.assertContains(resposta, 'Usuário não cadastrado')
        self.assertContains(resposta, 'Firefox')
        self.assertContains(resposta, '<caption')
        self.assertEqual(resposta.content.decode().count('<h1'), 1)
        # Menu principal marca "Auditoria" e a aba atual fica marcada
        self.assertContains(resposta, f'href="{reverse("auditoria_lista")}" aria-current="page">Auditoria')
        self.assertContains(resposta, f'href="{reverse("auditoria_logins")}" aria-current="page">Logins malsucedidos')

    def test_abas_na_tela_de_alteracoes(self):
        resposta = self.client.get(reverse('auditoria_lista'))

        self.assertContains(resposta, f'href="{reverse("auditoria_lista")}" aria-current="page">Alterações de registros')
        self.assertContains(resposta, f'href="{reverse("auditoria_logins")}">Logins malsucedidos')

    def test_filtros(self):
        url = reverse('auditoria_logins')
        casos = {
            'usuario': ({'usuario': 'MAR'}, 1),
            'motivo': ({'motivo': 'INEXISTENTE'}, 1),
            'ip': ({'ip': '10.0.0.2'}, 1),
            'hoje': ({'data_inicio': timezone.localdate().isoformat()}, 2),
            'ontem': ({'data_fim': (timezone.localdate() - timedelta(days=1)).isoformat()}, 0),
        }
        for nome, (parametros, esperado) in casos.items():
            with self.subTest(filtro=nome):
                self.assertEqual(self.client.get(url, parametros).context['paginator'].count, esperado)

    def test_ip_invalido_mostra_erro(self):
        resposta = self.client.get(reverse('auditoria_logins'), {'ip': 'abc'})

        self.assertContains(resposta, 'href="#id_ip"')
        self.assertEqual(resposta.context['paginator'].count, 2)
