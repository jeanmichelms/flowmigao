from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from veiculos.models import Veiculo

from .forms import ManutencaoForm, add_months
from .hosted_service import (
    AvisoRevisaoHostedService,
    _dias_antecedencia,
    _horario_envio,
    enviar_avisos_revisao,
)
from .models import Manutencao, Peca, PecaUsada


@override_settings(
    AVISO_REVISAO_EMAIL_DIAS_ANTECEDENCIA=3,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
    DEFAULT_FROM_EMAIL='teste@flowmigao.local',
)
class AvisoRevisaoEmailTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nome='Maria Silva',
            cpf='123.456.789-10',
            email='maria@example.com',
        )
        self.veiculo = Veiculo.objects.create(
            cliente=self.cliente,
            marca='Fiat',
            modelo='Uno',
            ano=2020,
            placa='ABC1D23',
        )

    def test_envia_email_e_marca_manutencao_como_enviada(self):
        data_base = date(2026, 5, 10)
        manutencao = self._criar_manutencao(data_base + timedelta(days=3))

        resultado = enviar_avisos_revisao(data_base=data_base)

        manutencao.refresh_from_db()
        self.assertEqual(resultado.encontrados, 1)
        self.assertEqual(resultado.enviados, 1)
        self.assertEqual(resultado.falhas, 0)
        self.assertTrue(manutencao.email_aviso_revisao_enviado)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['maria@example.com'])
        self.assertIn('13/05/2026', mail.outbox[0].body)

    def test_nao_reenvia_email_ja_marcado_como_enviado(self):
        data_base = date(2026, 5, 10)
        self._criar_manutencao(
            data_base + timedelta(days=3),
            email_aviso_revisao_enviado=True,
        )

        resultado = enviar_avisos_revisao(data_base=data_base)

        self.assertEqual(resultado.encontrados, 0)
        self.assertEqual(resultado.enviados, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_nao_envia_email_fora_da_data_alvo(self):
        data_base = date(2026, 5, 10)
        self._criar_manutencao(data_base + timedelta(days=4))

        resultado = enviar_avisos_revisao(data_base=data_base)

        self.assertEqual(resultado.encontrados, 0)
        self.assertEqual(resultado.enviados, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_alterar_data_proxima_manutencao_reseta_indicador_de_envio(self):
        manutencao = self._criar_manutencao(
            date(2026, 5, 13),
            email_aviso_revisao_enviado=True,
        )

        manutencao.data_proxima_manutencao = date(2026, 6, 13)
        manutencao.save(update_fields=['data_proxima_manutencao'])

        manutencao.refresh_from_db()
        self.assertFalse(manutencao.email_aviso_revisao_enviado)

    def _criar_manutencao(self, data_proxima_manutencao, **kwargs):
        dados = {
            'veiculo': self.veiculo,
            'descricao': 'Revisão preventiva',
            'data_manutencao': date(2026, 1, 10),
            'quilometragem': 10000,
            'valor': '250.00',
            'data_proxima_manutencao': data_proxima_manutencao,
        }
        dados.update(kwargs)
        return Manutencao.objects.create(**dados)


class PecaCadastroTests(TestCase):
    def setUp(self):
        cliente = Cliente.objects.create(nome='Ana', cpf='111.222.333-44', email='ana@example.com')
        veiculo = Veiculo.objects.create(cliente=cliente, marca='Fiat', modelo='Uno', ano=2020, placa='XYZ9A87')
        self.manutencao = Manutencao.objects.create(
            veiculo=veiculo,
            descricao='Troca de óleo',
            data_manutencao=date(2026, 5, 10),
            quilometragem=10000,
            valor='200.00',
        )

    def test_cadastra_edita_e_lista_peca(self):
        resposta = self.client.post(
            reverse('pecas_nova'),
            {'nome': 'Filtro de óleo', 'marca': 'Tecfil', 'preco_custo': '35.10'},
        )
        self.assertRedirects(resposta, reverse('pecas_lista'))
        peca = Peca.objects.get(nome='Filtro de óleo')

        resposta = self.client.post(
            reverse('pecas_editar', args=[peca.pk]),
            {'nome': 'Filtro de óleo', 'marca': 'Tecfil', 'preco_custo': '40.00'},
        )
        self.assertRedirects(resposta, reverse('pecas_lista'))
        peca.refresh_from_db()
        self.assertEqual(peca.preco_custo, Decimal('40.00'))
        self.assertContains(self.client.get(reverse('pecas_lista')), 'Filtro de óleo')

    def test_rejeita_preco_negativo(self):
        resposta = self.client.post(
            reverse('pecas_nova'),
            {'nome': 'Vela', 'marca': '', 'preco_custo': '-1'},
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Peca.objects.exists())

    def test_cadastro_a_partir_da_manutencao_volta_para_ela(self):
        resposta = self.client.post(
            reverse('pecas_nova') + f'?manutencao={self.manutencao.pk}',
            {'nome': 'Vela', 'marca': '', 'preco_custo': '20.00'},
        )
        self.assertRedirects(resposta, reverse('manutencoes_detalhe', args=[self.manutencao.pk]))

    def test_adiciona_peca_na_manutencao_e_calcula_total(self):
        peca = Peca.objects.create(nome='Filtro', preco_custo='35.10')
        url = reverse('manutencoes_detalhe', args=[self.manutencao.pk])

        self.client.post(url, {'peca': peca.pk, 'quantidade': 2})
        resposta = self.client.post(url, {'peca': peca.pk, 'quantidade': 0})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(self.manutencao.pecas_usadas.count(), 1)
        self.assertEqual(self.manutencao.pecas_usadas.get().valor_total_custo, Decimal('70.20'))
        self.assertEqual(resposta.context['total_pecas'], Decimal('70.20'))

    def test_nao_exclui_peca_usada_em_manutencao(self):
        peca = Peca.objects.create(nome='Filtro', preco_custo='35.10')
        PecaUsada.objects.create(manutencao=self.manutencao, peca=peca, quantidade=1)

        resposta = self.client.post(reverse('pecas_excluir', args=[peca.pk]))

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, 'já foi usada em manutenções')
        self.assertTrue(Peca.objects.filter(pk=peca.pk).exists())

    def test_exclui_peca_sem_uso(self):
        peca = Peca.objects.create(nome='Filtro', preco_custo='35.10')

        resposta = self.client.post(reverse('pecas_excluir', args=[peca.pk]))

        self.assertRedirects(resposta, reverse('pecas_lista'))
        self.assertFalse(Peca.objects.exists())

    def test_remove_peca_usada_da_manutencao(self):
        peca = Peca.objects.create(nome='Filtro', preco_custo='35.10')
        peca_usada = PecaUsada.objects.create(manutencao=self.manutencao, peca=peca, quantidade=1)
        url = reverse('pecas_usadas_remover', args=[peca_usada.pk])

        self.assertEqual(self.client.get(url).status_code, 405)
        resposta = self.client.post(url)

        self.assertRedirects(resposta, reverse('manutencoes_detalhe', args=[self.manutencao.pk]))
        self.assertFalse(PecaUsada.objects.exists())
        self.assertTrue(Peca.objects.filter(pk=peca.pk).exists())


class AddMonthsTests(SimpleTestCase):
    def test_soma_meses_no_mesmo_ano(self):
        self.assertEqual(add_months(date(2026, 1, 15), 6), date(2026, 7, 15))

    def test_vira_o_ano(self):
        self.assertEqual(add_months(date(2026, 11, 10), 3), date(2027, 2, 10))

    def test_ajusta_para_o_ultimo_dia_do_mes(self):
        self.assertEqual(add_months(date(2026, 8, 31), 6), date(2027, 2, 28))
        self.assertEqual(add_months(date(2027, 8, 31), 6), date(2028, 2, 29))  # ano bissexto


class ManutencaoCadastroTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nome='Ana', cpf='111.222.333-44', email='ana@example.com')
        self.veiculo = Veiculo.objects.create(cliente=self.cliente, marca='Fiat', modelo='Uno', ano=2020, placa='XYZ9A87')

    def dados(self, **extra):
        dados = {
            'veiculo': self.veiculo.pk,
            'tipo': 'PREVENTIVA',
            'descricao': 'Troca de óleo',
            'data_manutencao': '2026-05-10',
            'data_proxima_manutencao': '2026-11-10',
            'quilometragem': 10000,
            'valor': '250.00',
            'observacoes': '',
        }
        dados.update(extra)
        return dados

    def test_formulario_novo_sugere_proxima_revisao_em_seis_meses(self):
        form = ManutencaoForm()
        hoje = date.today()

        self.assertEqual(form.initial['data_manutencao'], hoje.strftime('%Y-%m-%d'))
        self.assertEqual(form.initial['data_proxima_manutencao'], add_months(hoje, 6).strftime('%Y-%m-%d'))

    def test_cadastra_manutencao(self):
        resposta = self.client.post(reverse('manutencoes_novo'), self.dados())

        self.assertRedirects(resposta, reverse('manutencoes_lista'))
        manutencao = Manutencao.objects.get()
        self.assertEqual(manutencao.veiculo, self.veiculo)
        self.assertEqual(manutencao.data_proxima_manutencao, date(2026, 11, 10))
        self.assertEqual(manutencao.valor, Decimal('250.00'))

    def test_cadastro_a_partir_do_veiculo_volta_para_o_veiculo(self):
        url = reverse('manutencoes_novo') + f'?veiculo={self.veiculo.pk}&origem=veiculo_detalhe'

        self.assertEqual(self.client.get(url).context['selected_veiculo'], self.veiculo)
        resposta = self.client.post(url, self.dados())

        self.assertRedirects(resposta, reverse('veiculos_detalhe', args=[self.veiculo.pk]))

    def test_exige_veiculo_e_campos_obrigatorios(self):
        resposta = self.client.post(reverse('manutencoes_novo'), self.dados(veiculo='', descricao='', valor=''))

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue({'veiculo', 'descricao', 'valor'} <= set(resposta.context['form'].errors))
        self.assertFalse(Manutencao.objects.exists())

    def test_edita_e_exclui_manutencao(self):
        self.client.post(reverse('manutencoes_novo'), self.dados())
        manutencao = Manutencao.objects.get()

        resposta = self.client.post(
            reverse('manutencoes_editar', args=[manutencao.pk]),
            self.dados(tipo='CORRETIVA', quilometragem=12000),
        )
        self.assertRedirects(resposta, reverse('manutencoes_lista'))
        manutencao.refresh_from_db()
        self.assertEqual(manutencao.tipo, 'CORRETIVA')
        self.assertEqual(manutencao.quilometragem, 12000)

        resposta = self.client.post(reverse('manutencoes_excluir', args=[manutencao.pk]))
        self.assertRedirects(resposta, reverse('manutencoes_lista'))
        self.assertFalse(Manutencao.objects.exists())


class VeiculoBuscaViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        ana = Cliente.objects.create(nome='Ana', cpf='111.222.333-44', email='ana@example.com')
        bruno = Cliente.objects.create(nome='Bruno', cpf='555.666.777-88', email='bruno@example.com')
        Veiculo.objects.create(cliente=ana, marca='Fiat', modelo='Uno', ano=2015, placa='ABC1D23')
        Veiculo.objects.create(cliente=bruno, marca='VW', modelo='Gol', ano=2020, placa='XYZ9A87')

    def buscar(self, termo):
        resposta = self.client.get(reverse('manutencoes_buscar_veiculos'), {'q': termo})
        self.assertEqual(resposta.status_code, 200)
        return [item['placa'] for item in resposta.json()['results']]

    def test_filtra_por_cliente_marca_modelo_placa_e_ano(self):
        self.assertEqual(self.buscar(''), ['ABC1D23', 'XYZ9A87'])
        self.assertEqual(self.buscar('bruno'), ['XYZ9A87'])
        self.assertEqual(self.buscar('111.222'), ['ABC1D23'])
        self.assertEqual(self.buscar('fiat'), ['ABC1D23'])
        self.assertEqual(self.buscar('gol'), ['XYZ9A87'])
        self.assertEqual(self.buscar('xyz9'), ['XYZ9A87'])
        self.assertEqual(self.buscar('2015'), ['ABC1D23'])

    def test_retorna_dados_do_cliente_junto(self):
        resultado = self.client.get(reverse('manutencoes_buscar_veiculos'), {'q': 'ABC'}).json()['results'][0]

        self.assertEqual(resultado['cliente_nome'], 'Ana')
        self.assertEqual(resultado['cliente_cpf'], '111.222.333-44')
        self.assertEqual(resultado['ano'], 2015)


class PainelGerencialTests(TestCase):
    def setUp(self):
        self.hoje = timezone.localdate()
        self.mes_passado = add_months(self.hoje.replace(day=1), -1)

        self.cliente = Cliente.objects.create(nome='Ana', cpf='111.222.333-44', email='ana@example.com')
        antigo = Cliente.objects.create(nome='Bruno', cpf='555.666.777-88', email='bruno@example.com')
        # Cliente cadastrado há dois meses não conta como novo
        Cliente.objects.filter(pk=antigo.pk).update(
            data_cadastro=timezone.now() - timedelta(days=70)
        )

        veiculo = Veiculo.objects.create(cliente=self.cliente, marca='Fiat', modelo='Uno', ano=2020, placa='XYZ9A87')
        filtro = Peca.objects.create(nome='Filtro', preco_custo=Decimal('30.00'))

        preventiva = self._manutencao(veiculo, self.hoje, 'PREVENTIVA')
        self._manutencao(veiculo, self.hoje, 'CORRETIVA')
        antiga = self._manutencao(veiculo, self.mes_passado, 'CORRETIVA')

        PecaUsada.objects.create(manutencao=preventiva, peca=filtro, quantidade=2)  # 60,00 neste mês
        PecaUsada.objects.create(manutencao=antiga, peca=filtro, quantidade=5)      # mês passado, não conta

    def _manutencao(self, veiculo, data, tipo):
        return Manutencao.objects.create(
            veiculo=veiculo, descricao='Serviço', data_manutencao=data,
            quilometragem=10000, valor='100.00', tipo=tipo,
        )

    def test_indicadores_do_mes(self):
        resposta = self.client.get(reverse('dashboard'))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta.context['clientes_mes'], 1)
        self.assertEqual(resposta.context['gasto_pecas_mes'], Decimal('60.00'))

    def test_historico_separa_preventivas_e_corretivas_por_mes(self):
        historico = list(self.client.get(reverse('dashboard')).context['historico_servicos'])

        self.assertEqual(len(historico), 2)
        atual, anterior = historico  # mais recente primeiro
        self.assertEqual((atual['total_servicos'], atual['preventivas'], atual['corretivas']), (2, 1, 1))
        self.assertEqual((anterior['total_servicos'], anterior['preventivas'], anterior['corretivas']), (1, 0, 1))

    def test_painel_vazio(self):
        Manutencao.objects.all().delete()

        resposta = self.client.get(reverse('dashboard'))

        self.assertEqual(resposta.context['gasto_pecas_mes'], 0)
        self.assertContains(resposta, 'Nenhum serviço registrado ainda.')


@override_settings(
    AVISO_REVISAO_EMAIL_DIAS_ANTECEDENCIA=3,
    EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend',
)
class AvisoRevisaoFalhasTests(TestCase):
    def test_cliente_sem_email_conta_como_falha_e_nao_marca_envio(self):
        cliente = Cliente.objects.create(nome='Sem E-mail', cpf='000.000.000-00', email='')
        veiculo = Veiculo.objects.create(cliente=cliente, marca='Fiat', modelo='Uno', ano=2020, placa='SEM0E00')
        manutencao = Manutencao.objects.create(
            veiculo=veiculo, descricao='Revisão', data_manutencao=date(2026, 1, 10),
            quilometragem=10000, valor='100.00', data_proxima_manutencao=date(2026, 5, 13),
        )

        with self.assertLogs('manutencoes.hosted_service', level='ERROR'):
            resultado = enviar_avisos_revisao(data_base=date(2026, 5, 10))

        manutencao.refresh_from_db()
        self.assertEqual((resultado.encontrados, resultado.enviados, resultado.falhas), (1, 0, 1))
        self.assertFalse(manutencao.email_aviso_revisao_enviado)
        self.assertEqual(len(mail.outbox), 0)


class ConfiguracaoAvisoRevisaoTests(SimpleTestCase):
    @override_settings(AVISO_REVISAO_EMAIL_HORARIO_ENVIO='07:30')
    def test_horario_de_envio_configurado(self):
        self.assertEqual(_horario_envio(), time(7, 30))

    def test_horario_invalido_usa_oito_horas(self):
        for valor in ('25:00', 'manhã', ''):
            with self.subTest(valor=valor), override_settings(AVISO_REVISAO_EMAIL_HORARIO_ENVIO=valor):
                with self.assertLogs('manutencoes.hosted_service', level='WARNING'):
                    self.assertEqual(_horario_envio(), time(8, 0))

    @override_settings(AVISO_REVISAO_EMAIL_DIAS_ANTECEDENCIA='dez')
    def test_dias_de_antecedencia_invalido_usa_sete(self):
        with self.assertLogs('manutencoes.hosted_service', level='WARNING'):
            self.assertEqual(_dias_antecedencia(), 7)


@override_settings(AVISO_REVISAO_EMAIL_HORARIO_ENVIO='08:00', TIME_ZONE='America/Sao_Paulo')
class ProximaExecucaoTests(SimpleTestCase):
    def momento(self, dia, hora, minuto=0):
        return timezone.make_aware(datetime(2026, 5, dia, hora, minuto))

    def test_antes_do_horario_agenda_para_hoje(self):
        servico = AvisoRevisaoHostedService()

        self.assertEqual(servico._proxima_execucao(self.momento(10, 6)), self.momento(10, 8))

    def test_depois_do_horario_sem_ter_rodado_hoje_executa_agora(self):
        servico = AvisoRevisaoHostedService()
        agora = self.momento(10, 15, 30)

        self.assertEqual(servico._proxima_execucao(agora), agora)

    def test_ja_rodou_hoje_agenda_para_amanha(self):
        servico = AvisoRevisaoHostedService()
        servico._ultima_execucao = date(2026, 5, 10)

        self.assertEqual(servico._proxima_execucao(self.momento(10, 15)), self.momento(11, 8))


class RepresentacaoTextoTests(TestCase):
    def test_textos_exibidos_nas_listas_e_no_admin(self):
        cliente = Cliente(nome='Ana', cpf='111.222.333-44')
        veiculo = Veiculo(cliente=cliente, marca='Fiat', modelo='Uno', placa='ABC1D23')
        peca = Peca(nome='Filtro', marca='Tecfil', preco_custo=Decimal('30.00'))

        self.assertEqual(str(cliente), 'Ana - 111.222.333-44')
        self.assertEqual(str(veiculo), 'Fiat Uno - ABC1D23')
        self.assertEqual(str(peca), 'Filtro (Tecfil)')
        self.assertEqual(str(Peca(nome='Vela')), 'Vela')
        self.assertEqual(str(PecaUsada(peca=peca, quantidade=2)), '2x Filtro (Tecfil)')
