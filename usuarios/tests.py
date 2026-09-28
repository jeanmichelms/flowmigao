import importlib
from unittest import mock

from django.apps import apps as apps_do_projeto
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import post_delete
from django.test import TestCase, override_settings
from django.urls import reverse

from .apoio_testes import entrar
from .regras import UsuarioObrigatorioError, impedir_tabela_vazia

User = get_user_model()
SENHA = 'Senha-de-teste-123'
# O hash padrão das senhas é lento de propósito; nos testes isso só atrasa
HASH_RAPIDO = override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])

migracao_inicial = importlib.import_module('usuarios.migrations.0001_administrador_inicial')


def esvaziar_tabela_de_usuarios():
    """Simula um banco novo, sem usuários (desliga a regra do último usuário só durante a limpeza)."""
    post_delete.disconnect(impedir_tabela_vazia, sender=User)
    try:
        User.objects.all().delete()
    finally:
        post_delete.connect(impedir_tabela_vazia, sender=User)


@HASH_RAPIDO
class LoginTests(TestCase):
    def setUp(self):
        self.usuario = User.objects.create_user('maria', password=SENHA)

    def test_login_e_a_primeira_tela(self):
        resposta = self.client.get(reverse('home'))

        self.assertRedirects(resposta, f"{reverse('login')}?next=/")

    def test_todas_as_paginas_exigem_login(self):
        for nome in ('clientes_lista', 'veiculos_lista', 'manutencoes_lista', 'dashboard', 'usuarios_lista'):
            with self.subTest(pagina=nome):
                resposta = self.client.get(reverse(nome))
                self.assertEqual(resposta.status_code, 302)
                self.assertTrue(resposta['Location'].startswith(reverse('login')))

    def test_healthcheck_continua_sem_login(self):
        self.assertEqual(self.client.get(reverse('saude')).status_code, 200)

    def test_tela_de_login_e_acessivel_e_sem_menu(self):
        resposta = self.client.get(reverse('login'))

        self.assertContains(resposta, '<title>Entrar – FlowMigao</title>', html=False)
        self.assertContains(resposta, '<label for="id_username">Usuário', html=False)
        self.assertContains(resposta, '<label for="id_password">Senha', html=False)
        self.assertContains(resposta, 'aria-label="Opções de acessibilidade"')
        self.assertNotContains(resposta, 'Menu principal')
        self.assertEqual(resposta.content.decode().count('<h1'), 1)

    def test_entra_com_usuario_e_senha_corretos(self):
        resposta = self.client.post(reverse('login'), {'username': 'maria', 'password': SENHA})

        self.assertRedirects(resposta, reverse('home'))
        self.assertContains(self.client.get(reverse('home')), 'Usuário: <strong>maria</strong>')

    def test_volta_para_a_pagina_pedida_depois_do_login(self):
        resposta = self.client.post(
            reverse('login'), {'username': 'maria', 'password': SENHA, 'next': reverse('clientes_lista')}
        )

        self.assertRedirects(resposta, reverse('clientes_lista'))

    def test_senha_errada_mostra_erro(self):
        resposta = self.client.post(reverse('login'), {'username': 'maria', 'password': 'errada'})

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'Usuário ou senha incorretos')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_usuario_desativado_nao_entra(self):
        self.usuario.is_active = False
        self.usuario.save()

        resposta = self.client.post(reverse('login'), {'username': 'maria', 'password': SENHA})

        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_sair_volta_para_o_login(self):
        self.client.force_login(self.usuario)

        resposta = self.client.post(reverse('logout'))

        self.assertRedirects(resposta, reverse('login'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_usuario_troca_a_propria_senha(self):
        self.client.force_login(self.usuario)

        resposta = self.client.post(reverse('alterar_senha'), {
            'old_password': SENHA, 'new_password1': 'Outra-senha-456', 'new_password2': 'Outra-senha-456',
        })

        self.assertRedirects(resposta, reverse('home'))
        self.usuario.refresh_from_db()
        self.assertTrue(self.usuario.check_password('Outra-senha-456'))


@HASH_RAPIDO
class UsuarioComumTests(TestCase):
    def setUp(self):
        self.usuario = entrar(self.client, 'comum')
        self.outro = User.objects.create_user('outro', password=SENHA)

    def test_nao_ve_o_menu_de_usuarios(self):
        resposta = self.client.get(reverse('home'))

        self.assertNotContains(resposta, reverse('usuarios_lista'))

    def test_nao_acessa_a_manutencao_de_usuarios(self):
        urls = [
            reverse('usuarios_lista'),
            reverse('usuarios_novo'),
            reverse('usuarios_editar', args=[self.outro.pk]),
            reverse('usuarios_excluir', args=[self.outro.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                resposta = self.client.get(url)
                self.assertEqual(resposta.status_code, 403)
                self.assertContains(resposta, 'Acesso negado', status_code=403)

    def test_nao_consegue_excluir_nem_promover_pelo_post(self):
        self.client.post(reverse('usuarios_excluir', args=[self.outro.pk]))
        self.client.post(reverse('usuarios_editar', args=[self.usuario.pk]), {
            'username': 'comum', 'administrador': 'on', 'is_active': 'on',
        })

        self.assertTrue(User.objects.filter(pk=self.outro.pk).exists())
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.is_superuser)


@HASH_RAPIDO
class ManutencaoUsuariosTests(TestCase):
    def setUp(self):
        self.admin = entrar(self.client, 'chefe', administrador=True)
        self.comum = User.objects.create_user('joao', password=SENHA, first_name='João')

    def dados(self, **extra):
        dados = {
            'username': 'ana', 'first_name': 'Ana', 'email': 'ana@example.com',
            'password1': 'Senha-da-ana-789', 'password2': 'Senha-da-ana-789',
        }
        dados.update(extra)
        return dados

    def test_admin_ve_o_menu_e_a_lista(self):
        resposta = self.client.get(reverse('usuarios_lista'))

        self.assertContains(resposta, '<title>Usuários – FlowMigao</title>', html=False)
        self.assertContains(resposta, f'href="{reverse("usuarios_lista")}" aria-current="page"')
        self.assertContains(resposta, 'chefe (você)')
        self.assertContains(resposta, 'João')
        self.assertContains(resposta, '<caption')
        self.assertContains(resposta, 'Excluir<span class="visually-hidden"> usuário joao</span>')

    def test_lista_nao_oferece_excluir_o_proprio_usuario(self):
        resposta = self.client.get(reverse('usuarios_lista'))

        self.assertNotContains(resposta, reverse('usuarios_excluir', args=[self.admin.pk]))

    def test_cadastra_usuario_comum(self):
        resposta = self.client.post(reverse('usuarios_novo'), self.dados(), follow=True)

        self.assertRedirects(resposta, reverse('usuarios_lista'))
        self.assertContains(resposta, 'Usuário &quot;ana&quot; cadastrado com sucesso.')
        ana = User.objects.get(username='ana')
        self.assertTrue(ana.check_password('Senha-da-ana-789'))
        self.assertFalse(ana.is_superuser)
        self.assertFalse(ana.is_staff)

    def test_cadastra_administrador(self):
        self.client.post(reverse('usuarios_novo'), self.dados(administrador='on'))

        ana = User.objects.get(username='ana')
        self.assertTrue(ana.is_superuser)
        self.assertTrue(ana.is_staff)

    def test_nao_cadastra_com_senhas_diferentes_ou_usuario_repetido(self):
        resposta = self.client.post(reverse('usuarios_novo'), self.dados(username='JOAO', password2='outra'))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'id="resumo-erros"')
        self.assertContains(resposta, 'href="#id_username"')
        self.assertContains(resposta, 'href="#id_password2"')
        self.assertFalse(User.objects.filter(username__iexact='joao').exclude(pk=self.comum.pk).exists())

    def test_edita_sem_trocar_a_senha(self):
        resposta = self.client.post(reverse('usuarios_editar', args=[self.comum.pk]), {
            'username': 'joao', 'first_name': 'João Silva', 'email': '', 'administrador': 'on', 'is_active': 'on',
        })

        self.assertRedirects(resposta, reverse('usuarios_lista'))
        self.comum.refresh_from_db()
        self.assertEqual(self.comum.first_name, 'João Silva')
        self.assertTrue(self.comum.is_superuser)
        self.assertTrue(self.comum.check_password(SENHA))

    def test_edita_trocando_a_senha(self):
        self.client.post(reverse('usuarios_editar', args=[self.comum.pk]), {
            'username': 'joao', 'is_active': 'on', 'password1': 'Nova-senha-321', 'password2': 'Nova-senha-321',
        })

        self.comum.refresh_from_db()
        self.assertTrue(self.comum.check_password('Nova-senha-321'))

    def test_desativa_usuario(self):
        self.client.post(reverse('usuarios_editar', args=[self.comum.pk]), {'username': 'joao'})

        self.comum.refresh_from_db()
        self.assertFalse(self.comum.is_active)

    def test_nao_remove_o_proprio_perfil_de_admin_nem_se_desativa(self):
        url = reverse('usuarios_editar', args=[self.admin.pk])
        self.assertContains(self.client.get(url), 'Você não pode remover o seu próprio perfil de administrador')

        # Campos desabilitados: o valor enviado é ignorado
        resposta = self.client.post(url, {'username': 'chefe', 'first_name': 'Chefe'})

        self.assertRedirects(resposta, reverse('usuarios_lista'))
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.first_name, 'Chefe')
        self.assertTrue(self.admin.is_superuser)
        self.assertTrue(self.admin.is_active)

    def test_trocar_a_propria_senha_mantem_a_sessao(self):
        self.client.post(reverse('usuarios_editar', args=[self.admin.pk]), {
            'username': 'chefe', 'password1': 'Nova-senha-321', 'password2': 'Nova-senha-321',
        })

        self.assertEqual(self.client.get(reverse('usuarios_lista')).status_code, 200)

    def test_exclui_outro_usuario(self):
        url = reverse('usuarios_excluir', args=[self.comum.pk])
        self.assertContains(self.client.get(url), 'Tem certeza que deseja excluir o usuário')

        resposta = self.client.post(url)

        self.assertRedirects(resposta, reverse('usuarios_lista'))
        self.assertFalse(User.objects.filter(pk=self.comum.pk).exists())

    def test_nao_exclui_a_si_mesmo(self):
        url = reverse('usuarios_excluir', args=[self.admin.pk])
        resposta_get = self.client.get(url)
        self.assertContains(resposta_get, 'Você não pode excluir o seu próprio usuário.')
        self.assertNotContains(resposta_get, 'Confirmar Exclusão')

        resposta = self.client.post(url, follow=True)

        self.assertRedirects(resposta, reverse('usuarios_lista'))
        self.assertContains(resposta, 'Você não pode excluir o seu próprio usuário.')
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_formularios_acessiveis(self):
        for url in (reverse('usuarios_novo'), reverse('usuarios_editar', args=[self.comum.pk])):
            with self.subTest(url=url):
                html = self.client.get(url).content.decode()
                self.assertEqual(html.count('<h1'), 1)
                self.assertIn('<label for="id_username">Usuário', html)
                self.assertIn('<label for="id_administrador">Administrador</label>', html)
                self.assertIn('aria-describedby="id_administrador_helptext"', html)
                self.assertIn('id="id_administrador_helptext"', html)


@HASH_RAPIDO
class SempreExisteUmUsuarioTests(TestCase):
    def test_nao_deixa_excluir_o_ultimo_usuario(self):
        unico = User.objects.create_user('unico', password=SENHA)
        User.objects.exclude(pk=unico.pk).delete()

        with self.assertRaises(UsuarioObrigatorioError), transaction.atomic():
            unico.delete()

        self.assertTrue(User.objects.filter(pk=unico.pk).exists())

    def test_nao_deixa_excluir_todos_de_uma_vez(self):
        User.objects.create_user('a', password=SENHA)
        User.objects.create_user('b', password=SENHA)

        with self.assertRaises(UsuarioObrigatorioError), transaction.atomic():
            User.objects.all().delete()

        self.assertTrue(User.objects.filter(username='a').exists())

    def test_exclui_normalmente_quando_sobram_outros(self):
        User.objects.create_user('a', password=SENHA)
        b = User.objects.create_user('b', password=SENHA)

        b.delete()

        self.assertFalse(User.objects.filter(username='b').exists())


@HASH_RAPIDO
class AdminDoDjangoTests(TestCase):
    def setUp(self):
        self.admin = entrar(self.client, 'chefe', administrador=True)
        self.outro = User.objects.create_user('outro', password=SENHA)

    def test_nao_exclui_o_proprio_usuario_pelo_admin(self):
        resposta = self.client.post(
            reverse('admin:auth_user_delete', args=[self.admin.pk]), {'post': 'yes'}
        )

        self.assertEqual(resposta.status_code, 403)
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())

    def test_exclui_outro_usuario_pelo_admin(self):
        self.client.post(reverse('admin:auth_user_delete', args=[self.outro.pk]), {'post': 'yes'})

        self.assertFalse(User.objects.filter(pk=self.outro.pk).exists())

    def test_admin_nao_oferece_exclusao_em_lote(self):
        resposta = self.client.get(reverse('admin:auth_user_changelist'))

        self.assertNotContains(resposta, 'value="delete_selected"')


@HASH_RAPIDO
class AdministradorInicialTests(TestCase):
    def criar(self, **ambiente):
        with mock.patch.dict('os.environ', ambiente, clear=False), mock.patch('builtins.print') as imprimir:
            migracao_inicial.criar_administrador_inicial(apps_do_projeto, None)
        return imprimir

    def test_cria_administrador_com_dados_do_ambiente(self):
        esvaziar_tabela_de_usuarios()

        imprimir = self.criar(DJANGO_ADMIN_USUARIO='dono', DJANGO_ADMIN_SENHA='Senha-do-dono-1')

        dono = User.objects.get()
        self.assertEqual(dono.username, 'dono')
        self.assertTrue(dono.is_superuser and dono.is_staff and dono.is_active)
        self.assertTrue(dono.check_password('Senha-do-dono-1'))
        imprimir.assert_not_called()

    def test_sem_senha_no_ambiente_gera_e_mostra_uma_senha(self):
        esvaziar_tabela_de_usuarios()

        with mock.patch.dict('os.environ', {}, clear=False) as ambiente:
            ambiente.pop('DJANGO_ADMIN_SENHA', None)
            ambiente.pop('DJANGO_ADMIN_USUARIO', None)
            imprimir = self.criar()

        admin = User.objects.get()
        self.assertEqual(admin.username, 'admin')
        mensagem = imprimir.call_args.args[0]
        senha = mensagem.split('senha "')[1].split('"')[0]
        self.assertTrue(admin.check_password(senha))

    def test_nao_faz_nada_se_ja_existem_usuarios(self):
        User.objects.create_user('existente', password=SENHA)
        total = User.objects.count()

        self.criar(DJANGO_ADMIN_USUARIO='dono', DJANGO_ADMIN_SENHA='Senha-do-dono-1')

        self.assertEqual(User.objects.count(), total)
        self.assertFalse(User.objects.filter(username='dono').exists())
