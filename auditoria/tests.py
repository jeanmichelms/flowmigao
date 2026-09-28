from datetime import date, timedelta
from unittest import mock

from django.contrib.auth import get_user_model
from django.core import mail
from django.db import DatabaseError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from manutencoes.hosted_service import enviar_avisos_revisao
from manutencoes.models import Manutencao, Peca
from usuarios.apoio_testes import entrar
from veiculos.models import Veiculo

from .models import RegistroAuditoria

User = get_user_model()
Acao = RegistroAuditoria.Acao


def dados_cliente(**extra):
    dados = {'nome': 'Maria Silva', 'cpf': '123.456.789-10', 'email': 'maria@example.com'}
    dados.update(extra)
    return dados


def registros_de(objeto):
    return RegistroAuditoria.objects.filter(objeto_id=str(objeto.pk), tipo__model=objeto._meta.model_name)


class RegistroPelasTelasTests(TestCase):
    def setUp(self):
        self.usuario = entrar(self.client, 'operador')

    def test_inclusao_registra_usuario_e_dados(self):
        self.client.post(reverse('clientes_novo'), dados_cliente(telefone='(11) 99999-0000'))

        cliente = Cliente.objects.get()
        registro = registros_de(cliente).get()
        self.assertEqual(registro.acao, Acao.INCLUSAO)
        self.assertEqual(registro.usuario, self.usuario)
        self.assertEqual(registro.autor, 'operador')
        self.assertEqual(registro.objeto_descricao, 'Maria Silva - 123.456.789-10')
        self.assertIn({'campo': 'Telefone', 'de': None, 'para': '(11) 99999-0000'}, registro.alteracoes)
        # Campos vazios não aparecem
        self.assertNotIn('Endereço', [item['campo'] for item in registro.alteracoes])

    def test_alteracao_registra_so_os_campos_alterados(self):
        cliente = Cliente.objects.create(**dados_cliente())

        self.client.post(reverse('clientes_editar', args=[cliente.pk]), dados_cliente(nome='Maria Souza', cidade='Santos'))

        registro = registros_de(cliente).get(acao=Acao.ALTERACAO)
        self.assertEqual(registro.autor, 'operador')
        self.assertEqual(registro.alteracoes, [
            {'campo': 'Nome', 'de': 'Maria Silva', 'para': 'Maria Souza'},
            {'campo': 'Cidade', 'de': None, 'para': 'Santos'},
        ])

    def test_salvar_sem_mudar_nada_nao_registra(self):
        cliente = Cliente.objects.create(**dados_cliente())

        self.client.post(reverse('clientes_editar', args=[cliente.pk]), dados_cliente())

        self.assertFalse(registros_de(cliente).filter(acao=Acao.ALTERACAO).exists())

    def test_exclusao_guarda_os_dados_do_registro(self):
        cliente = Cliente.objects.create(**dados_cliente())

        self.client.post(reverse('clientes_excluir', args=[cliente.pk]))

        registro = registros_de(cliente).get(acao=Acao.EXCLUSAO)
        self.assertEqual(registro.autor, 'operador')
        self.assertEqual(registro.objeto_descricao, 'Maria Silva - 123.456.789-10')
        self.assertIn({'campo': 'CPF', 'de': '123.456.789-10', 'para': None}, registro.alteracoes)

    def test_exclusao_em_cascata_registra_cada_registro(self):
        cliente = Cliente.objects.create(**dados_cliente())
        veiculo = Veiculo.objects.create(cliente=cliente, marca='Fiat', modelo='Uno', ano=2015, placa='ABC1D23')

        self.client.post(reverse('clientes_excluir', args=[cliente.pk]))

        registro = registros_de(veiculo).get(acao=Acao.EXCLUSAO)
        self.assertEqual(registro.autor, 'operador')
        self.assertIn({'campo': 'Cliente', 'de': 'Maria Silva - 123.456.789-10', 'para': None}, registro.alteracoes)

    def test_campos_de_relacao_escolha_data_e_valor_ficam_legiveis(self):
        cliente = Cliente.objects.create(**dados_cliente())
        veiculo = Veiculo.objects.create(cliente=cliente, marca='Fiat', modelo='Uno', ano=2015, placa='ABC1D23')

        self.client.post(reverse('manutencoes_novo'), {
            'veiculo': veiculo.pk, 'tipo': 'CORRETIVA', 'descricao': 'Troca de embreagem',
            'data_manutencao': '2026-05-10', 'data_proxima_manutencao': '', 'quilometragem': 10000,
            'valor': '1250.50', 'observacoes': '',
        })

        alteracoes = registros_de(Manutencao.objects.get()).get().alteracoes
        self.assertIn({'campo': 'Veículo', 'de': None, 'para': 'Fiat Uno - ABC1D23'}, alteracoes)
        self.assertIn({'campo': 'Tipo de manutenção', 'de': None, 'para': 'Corretiva'}, alteracoes)
        self.assertIn({'campo': 'Data da manutenção', 'de': None, 'para': '10/05/2026'}, alteracoes)
        self.assertIn({'campo': 'Valor (R$)', 'de': None, 'para': '1250.50'}, alteracoes)
        self.assertIn({'campo': 'Aviso de revisão enviado', 'de': None, 'para': 'Não'}, alteracoes)

    def test_pecas_usadas_tambem_sao_registradas(self):
        cliente = Cliente.objects.create(**dados_cliente())
        veiculo = Veiculo.objects.create(cliente=cliente, marca='Fiat', modelo='Uno', ano=2015, placa='ABC1D23')
        manutencao = Manutencao.objects.create(
            veiculo=veiculo, descricao='Revisão', data_manutencao=date(2026, 5, 10), quilometragem=1000, valor=100,
        )
        peca = Peca.objects.create(nome='Filtro', preco_custo=30)

        self.client.post(reverse('manutencoes_detalhe', args=[manutencao.pk]), {'peca': peca.pk, 'quantidade': 2})

        registro = RegistroAuditoria.objects.get(tipo__model='pecausada')
        self.assertEqual(registro.autor, 'operador')
        self.assertEqual(registro.objeto_descricao, '2x Filtro')
        self.assertIn({'campo': 'Custo total (R$)', 'de': None, 'para': '60.00'}, registro.alteracoes)


class TransacaoDaRequisicaoTests(TestCase):
    def setUp(self):
        entrar(self.client, 'operador')
        self.cliente = Cliente.objects.create(**dados_cliente())

    def test_falha_na_auditoria_desfaz_a_alteracao(self):
        self.client.raise_request_exception = False
        with mock.patch.object(RegistroAuditoria.objects, 'create', side_effect=DatabaseError('falhou')):
            resposta = self.client.post(
                reverse('clientes_editar', args=[self.cliente.pk]), dados_cliente(nome='Maria Souza')
            )

        self.assertEqual(resposta.status_code, 500)
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.nome, 'Maria Silva')


class RegistroDeUsuariosTests(TestCase):
    def setUp(self):
        self.admin = entrar(self.client, 'chefe', administrador=True)

    def test_senha_nunca_e_gravada(self):
        self.client.post(reverse('usuarios_novo'), {
            'username': 'ana', 'password1': 'Senha-da-ana-789', 'password2': 'Senha-da-ana-789',
        })
        ana = User.objects.get(username='ana')
        self.client.post(reverse('usuarios_editar', args=[ana.pk]), {
            'username': 'ana', 'is_active': 'on', 'password1': 'Outra-senha-456', 'password2': 'Outra-senha-456',
        })

        inclusao = registros_de(ana).get(acao=Acao.INCLUSAO)
        self.assertNotIn('Senha', [item['campo'] for item in inclusao.alteracoes])
        alteracao = registros_de(ana).get(acao=Acao.ALTERACAO)
        self.assertEqual(alteracao.alteracoes, [{'campo': 'Senha', 'de': None, 'para': '(alterada)'}])
        self.assertNotIn('pbkdf2', str(RegistroAuditoria.objects.values_list('alteracoes', flat=True)))

    def test_login_nao_gera_registro(self):
        User.objects.create_user('maria', password='Senha-de-teste-123')
        self.client.logout()
        antes = RegistroAuditoria.objects.count()

        self.client.post(reverse('login'), {'username': 'maria', 'password': 'Senha-de-teste-123'})

        self.assertEqual(RegistroAuditoria.objects.count(), antes)

    def test_registro_continua_com_o_nome_depois_que_o_usuario_e_excluido(self):
        operador = entrar(self.client, 'operador')
        self.client.post(reverse('clientes_novo'), dados_cliente())
        entrar(self.client, 'chefe2', administrador=True)

        self.client.post(reverse('usuarios_excluir', args=[operador.pk]))

        registro = registros_de(Cliente.objects.get()).get()
        self.assertIsNone(registro.usuario)
        self.assertEqual(registro.autor, 'operador')


@override_settings(
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    AVISO_REVISAO_EMAIL_DIAS_ANTECEDENCIA=3,
)
class RegistroDoSistemaTests(TestCase):
    def test_alteracao_fora_de_uma_requisicao_fica_como_sistema(self):
        cliente = Cliente.objects.create(**dados_cliente())
        veiculo = Veiculo.objects.create(cliente=cliente, marca='Fiat', modelo='Uno', ano=2015, placa='ABC1D23')
        manutencao = Manutencao.objects.create(
            veiculo=veiculo, descricao='Revisão', data_manutencao=date(2026, 1, 10), quilometragem=1000,
            valor=100, data_proxima_manutencao=date(2026, 5, 13),
        )

        enviar_avisos_revisao(data_base=date(2026, 5, 10))

        self.assertEqual(len(mail.outbox), 1)
        registro = registros_de(manutencao).get(acao=Acao.ALTERACAO)
        self.assertEqual(registro.autor, 'Sistema')
        self.assertEqual(registro.alteracoes, [{'campo': 'Aviso de revisão enviado', 'de': 'Não', 'para': 'Sim'}])

    def test_fixtures_carregadas_nao_geram_registro(self):
        from django.db.models.signals import post_save
        with mock.patch.object(RegistroAuditoria.objects, 'create') as criar:
            post_save.send(Cliente, instance=Cliente(pk=1, **dados_cliente()), created=True, raw=True)
        criar.assert_not_called()


class TelaDeAuditoriaTests(TestCase):
    def setUp(self):
        self.admin = entrar(self.client, 'chefe', administrador=True)
        RegistroAuditoria.objects.all().delete()  # descarta a inclusão do próprio usuário de teste
        self.client.post(reverse('clientes_novo'), dados_cliente())
        self.cliente = Cliente.objects.get()
        self.client.post(reverse('clientes_editar', args=[self.cliente.pk]), dados_cliente(nome='Maria Souza'))
        self.client.post(reverse('pecas_nova'), {'nome': 'Filtro', 'marca': '', 'preco_custo': '30'})

    def test_somente_administrador_acessa(self):
        entrar(self.client, 'comum')

        self.assertEqual(self.client.get(reverse('auditoria_lista')).status_code, 403)
        self.assertNotContains(self.client.get(reverse('home')), reverse('auditoria_lista'))

    def test_lista_mostra_quem_fez_o_que(self):
        resposta = self.client.get(reverse('auditoria_lista'))

        self.assertContains(resposta, '<title>Auditoria – FlowMigao</title>', html=False)
        self.assertContains(resposta, f'href="{reverse("auditoria_lista")}" aria-current="page"')
        self.assertContains(resposta, '3 registros encontrados.')
        self.assertContains(resposta, 'Maria Souza - 123.456.789-10')
        self.assertContains(resposta, '<span class="visually-hidden">de</span> Maria Silva')
        self.assertContains(resposta, '<caption')
        self.assertContains(resposta, '<th scope="col">Usuário</th>', html=True)

    def test_filtros(self):
        url = reverse('auditoria_lista')
        casos = {
            'tipo': ({'tipo': 'manutencoes.peca'}, 1),
            'acao': ({'acao': 'ALTERACAO'}, 1),
            'usuario': ({'usuario': 'chefe'}, 3),
            'sistema': ({'usuario': '__sistema__'}, 0),
            'busca': ({'busca': 'filtro'}, 1),
            'objeto': ({'tipo': 'clientes.cliente', 'objeto': self.cliente.pk}, 2),
            'hoje': ({'data_inicio': timezone.localdate().isoformat()}, 3),
            'amanha': ({'data_inicio': (timezone.localdate() + timedelta(days=1)).isoformat()}, 0),
            'ate_hoje': ({'data_fim': timezone.localdate().isoformat()}, 3),
            'ate_ontem': ({'data_fim': (timezone.localdate() - timedelta(days=1)).isoformat()}, 0),
        }
        for nome, (parametros, esperado) in casos.items():
            with self.subTest(filtro=nome):
                resposta = self.client.get(url, parametros)
                self.assertEqual(resposta.context['paginator'].count, esperado)

    def test_periodo_invertido_mostra_erro(self):
        resposta = self.client.get(reverse('auditoria_lista'), {'data_inicio': '2026-05-10', 'data_fim': '2026-05-01'})

        self.assertContains(resposta, 'A data final deve ser igual ou posterior à data inicial.')
        self.assertContains(resposta, 'href="#id_data_fim"')

    def test_paginacao_mantem_os_filtros(self):
        for numero in range(55):
            Peca.objects.create(nome=f'Peça {numero}', preco_custo=1)

        resposta = self.client.get(reverse('auditoria_lista'), {'tipo': 'manutencoes.peca'})

        self.assertEqual(len(resposta.context['registros']), 50)
        self.assertContains(resposta, 'href="?tipo=manutencoes.peca&amp;page=2"')


class ResumoNoDetalheTests(TestCase):
    def setUp(self):
        self.admin = entrar(self.client, 'chefe', administrador=True)
        self.client.post(reverse('clientes_novo'), dados_cliente())
        self.cliente = Cliente.objects.get()

    def test_detalhe_mostra_quem_cadastrou_e_quem_alterou(self):
        entrar(self.client, 'operador')
        self.client.post(reverse('clientes_editar', args=[self.cliente.pk]), dados_cliente(nome='Maria Souza'))

        resposta = self.client.get(reverse('clientes_detalhe', args=[self.cliente.pk]))

        self.assertContains(resposta, 'Cadastrado por <strong>chefe</strong>')
        self.assertContains(resposta, 'Última alteração por <strong>operador</strong>')
        # Usuário comum não vê o link para a tela de auditoria
        self.assertNotContains(resposta, 'Ver histórico completo')

    def test_administrador_ve_link_para_o_historico_do_registro(self):
        resposta = self.client.get(reverse('clientes_detalhe', args=[self.cliente.pk]))

        self.assertContains(
            resposta, f'href="{reverse("auditoria_lista")}?tipo=clientes.cliente&amp;objeto={self.cliente.pk}"'
        )

    def test_registro_antigo_sem_historico(self):
        RegistroAuditoria.objects.all().delete()

        resposta = self.client.get(reverse('clientes_detalhe', args=[self.cliente.pk]))

        self.assertContains(resposta, 'Sem histórico de alterações')

    def test_detalhes_de_veiculo_e_manutencao_tambem_mostram(self):
        veiculo = Veiculo.objects.create(cliente=self.cliente, marca='Fiat', modelo='Uno', ano=2015, placa='ABC1D23')
        manutencao = Manutencao.objects.create(
            veiculo=veiculo, descricao='Revisão', data_manutencao=date(2026, 5, 10), quilometragem=1000, valor=100,
        )
        for url in (reverse('veiculos_detalhe', args=[veiculo.pk]), reverse('manutencoes_detalhe', args=[manutencao.pk])):
            with self.subTest(url=url):
                self.assertContains(self.client.get(url), 'Cadastrado por <strong>Sistema</strong>')
