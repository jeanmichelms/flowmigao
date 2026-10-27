from datetime import date, datetime, time, timedelta
from decimal import Decimal
from unittest import mock

from django.core import mail
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from clientes.models import Cliente
from usuarios.apoio_testes import entrar
from veiculos.models import Veiculo

from .forms import ManutencaoForm, ProjecaoPecasForm, add_months
from .graficos import colunas_empilhadas, escala
from .hosted_service import (
    AvisoRevisaoHostedService,
    _dias_antecedencia,
    _horario_envio,
    enviar_avisos_revisao,
)
from .models import Manutencao, Peca, PecaUsada
from .projecao import BASE_MEDIA_GERAL, BASE_MESMO_MES, BASE_SEM_HISTORICO, projetar_pecas


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

    def test_nao_envia_email_depois_do_prazo_de_antecedencia(self):
        data_base = date(2026, 5, 10)
        self._criar_manutencao(data_base + timedelta(days=4))

        resultado = enviar_avisos_revisao(data_base=data_base)

        self.assertEqual(resultado.encontrados, 0)
        self.assertEqual(resultado.enviados, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_envia_para_todas_as_revisoes_dentro_do_prazo(self):
        # Ex.: revisão cadastrada em cima da hora, ou dia em que o site ficou fora do ar
        data_base = date(2026, 5, 10)
        for dias in (0, 1, 2, 3):
            self._criar_manutencao(data_base + timedelta(days=dias))

        resultado = enviar_avisos_revisao(data_base=data_base)

        self.assertEqual((resultado.encontrados, resultado.enviados), (4, 4))
        self.assertEqual(len(mail.outbox), 4)
        self.assertFalse(Manutencao.objects.filter(email_aviso_revisao_enviado=False).exists())

    def test_nao_envia_para_revisao_que_ja_passou_ou_sem_data(self):
        data_base = date(2026, 5, 10)
        self._criar_manutencao(data_base - timedelta(days=1))
        self._criar_manutencao(None)

        resultado = enviar_avisos_revisao(data_base=data_base)

        self.assertEqual(resultado.encontrados, 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_cada_revisao_e_avisada_uma_vez_so(self):
        data_base = date(2026, 5, 10)
        self._criar_manutencao(data_base + timedelta(days=2))

        enviar_avisos_revisao(data_base=data_base)
        segunda = enviar_avisos_revisao(data_base=data_base + timedelta(days=1))

        self.assertEqual(segunda.encontrados, 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_nova_data_de_revisao_recebe_novo_aviso(self):
        data_base = date(2026, 5, 10)
        manutencao = self._criar_manutencao(data_base + timedelta(days=2))
        enviar_avisos_revisao(data_base=data_base)

        manutencao.refresh_from_db()
        manutencao.data_proxima_manutencao = data_base + timedelta(days=3)
        manutencao.save()
        resultado = enviar_avisos_revisao(data_base=data_base)

        self.assertEqual(resultado.enviados, 1)
        self.assertEqual(len(mail.outbox), 2)
        self.assertIn('13/05/2026', mail.outbox[1].body)

    def test_alterar_data_pela_tela_de_edicao_reseta_indicador_de_envio(self):
        entrar(self.client)
        manutencao = self._criar_manutencao(date(2026, 5, 13), email_aviso_revisao_enviado=True)
        dados = {
            'veiculo': self.veiculo.pk, 'tipo': 'PREVENTIVA', 'descricao': 'Revisão preventiva',
            'data_manutencao': '2026-01-10', 'quilometragem': 10000, 'valor': '250.00', 'observacoes': '',
        }

        # Salvar sem mudar a data mantém o indicador; mudar a data libera um novo aviso
        self.client.post(reverse('manutencoes_editar', args=[manutencao.pk]), {**dados, 'data_proxima_manutencao': '2026-05-13'})
        manutencao.refresh_from_db()
        self.assertTrue(manutencao.email_aviso_revisao_enviado)

        self.client.post(reverse('manutencoes_editar', args=[manutencao.pk]), {**dados, 'data_proxima_manutencao': '2026-06-13'})
        manutencao.refresh_from_db()
        self.assertFalse(manutencao.email_aviso_revisao_enviado)

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
        entrar(self.client)
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
        entrar(self.client)
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

    def setUp(self):
        entrar(self.client)

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
        entrar(self.client)
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


HOJE_PROJECAO = date(2026, 10, 26)


class ProjecaoPecasTests(TestCase):
    def setUp(self):
        cliente = Cliente.objects.create(nome='Ana', cpf='111.222.333-44', email='ana@example.com')
        self.veiculo = Veiculo.objects.create(cliente=cliente, marca='Fiat', modelo='Uno', ano=2020, placa='XYZ9A87')
        self.filtro = Peca.objects.create(nome='Filtro', preco_custo=Decimal('30.00'))
        self.vela = Peca.objects.create(nome='Vela', preco_custo=Decimal('10.00'))

    def _usar(self, peca, data, quantidade):
        manutencao = Manutencao.objects.create(
            veiculo=self.veiculo, descricao='Serviço', data_manutencao=data,
            quilometragem=10000, valor='100.00',
        )
        PecaUsada.objects.create(manutencao=manutencao, peca=peca, quantidade=quantidade)

    def test_media_do_mesmo_mes_nos_anos_anteriores(self):
        self._usar(self.filtro, date(2024, 11, 5), 2)
        self._usar(self.filtro, date(2025, 11, 20), 5)
        self._usar(self.filtro, date(2025, 12, 1), 7)  # outro mês, não entra em novembro

        projecao = projetar_pecas(date(2026, 11, 1), 1, HOJE_PROJECAO)

        mes = projecao.meses[0]
        self.assertEqual((mes.base, mes.anos_base, mes.total), (BASE_MESMO_MES, 2, 4))  # (2 + 5) / 2 = 3,5 -> 4
        linha = projecao.linhas[0]
        self.assertEqual((linha.peca, linha.quantidades, linha.custo), (self.filtro, [4], Decimal('120.00')))

    def test_mes_atual_nao_entra_no_historico(self):
        self._usar(self.filtro, date(2025, 10, 10), 4)
        self._usar(self.filtro, date(2026, 10, 3), 40)  # outubro/2026 ainda não terminou

        projecao = projetar_pecas(date(2027, 10, 1), 1, HOJE_PROJECAO)

        self.assertEqual(projecao.meses[0].anos_base, 1)
        self.assertEqual(projecao.linhas[0].quantidades, [4])

    def test_meses_antes_do_primeiro_registro_nao_contam_como_zero(self):
        self._usar(self.filtro, date(2025, 11, 10), 6)

        projecao = projetar_pecas(date(2026, 11, 1), 1, HOJE_PROJECAO)

        # novembro/2024 é anterior ao histórico: a média usa só novembro/2025
        self.assertEqual(projecao.meses[0].anos_base, 1)
        self.assertEqual(projecao.linhas[0].quantidades, [6])

    def test_sem_ano_anterior_usa_media_geral(self):
        # Histórico de agosto e setembro/2026: novembro ainda não tem ano anterior
        self._usar(self.filtro, date(2026, 8, 10), 3)
        self._usar(self.filtro, date(2026, 9, 10), 1)

        projecao = projetar_pecas(date(2026, 11, 1), 1, HOJE_PROJECAO)

        self.assertEqual(projecao.meses[0].base, BASE_MEDIA_GERAL)
        self.assertTrue(projecao.usa_media_geral)
        self.assertEqual(projecao.linhas[0].quantidades, [2])  # 4 peças em 2 meses

    def test_ordena_por_total_e_ignora_pecas_sem_projecao(self):
        self._usar(self.filtro, date(2025, 11, 10), 1)
        self._usar(self.vela, date(2025, 11, 10), 4)
        self._usar(self.filtro, date(2025, 6, 10), 9)  # junho fica fora do período

        projecao = projetar_pecas(date(2026, 11, 1), 2, HOJE_PROJECAO)

        self.assertEqual([linha.peca for linha in projecao.linhas], [self.vela, self.filtro])
        self.assertEqual([mes.total for mes in projecao.meses], [5, 0])
        self.assertEqual(projecao.total_pecas, 5)
        self.assertEqual(projecao.custo_total, Decimal('70.00'))

    def test_sem_historico(self):
        projecao = projetar_pecas(date(2026, 11, 1), 3, HOJE_PROJECAO)

        self.assertEqual(projecao.linhas, [])
        self.assertEqual([mes.base for mes in projecao.meses], [BASE_SEM_HISTORICO] * 3)

    def test_grafico_agrupa_as_demais_pecas(self):
        pecas = [Peca.objects.create(nome=f'Peça {i}', preco_custo=1) for i in range(7)]
        for i, peca in enumerate(pecas):
            self._usar(peca, date(2025, 11, 10), i + 1)

        series = projetar_pecas(date(2026, 11, 1), 1, HOJE_PROJECAO).series_grafico()

        self.assertEqual([serie['nome'] for serie in series],
                         ['Peça 6', 'Peça 5', 'Peça 4', 'Peça 3', 'Peça 2', 'Outras peças (2)'])
        self.assertEqual(series[-1]['valores'], [3])  # 1 + 2


class ProjecaoPecasFormTests(SimpleTestCase):
    def test_periodo_padrao_comeca_no_proximo_mes(self):
        form = ProjecaoPecasForm(hoje=HOJE_PROJECAO)

        self.assertEqual((form.initial['inicio'], form.initial['meses']), ('2026-11', 6))

    def test_periodo_valido(self):
        form = ProjecaoPecasForm({'inicio': '2027-10', 'meses': '12'}, hoje=HOJE_PROJECAO)

        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data, {'inicio': date(2027, 10, 1), 'meses': 12})

    def test_periodo_maximo_de_um_ano(self):
        form = ProjecaoPecasForm({'inicio': '2026-11', 'meses': '13'}, hoje=HOJE_PROJECAO)

        self.assertIn('meses', form.errors)

    def test_inicio_no_passado_ou_longe_demais(self):
        for inicio in ('2026-09', '2027-11'):
            with self.subTest(inicio=inicio):
                form = ProjecaoPecasForm({'inicio': inicio, 'meses': '1'}, hoje=HOJE_PROJECAO)
                self.assertIn('inicio', form.errors)


class GraficoColunasTests(SimpleTestCase):
    def test_escala_usa_passos_redondos(self):
        self.assertEqual(escala(0), (1, 4))
        self.assertEqual(escala(3), (1, 3))
        self.assertEqual(escala(39), (10, 40))
        self.assertEqual(escala(130), (50, 150))

    def test_segmentos_empilhados_so_para_valores_positivos(self):
        grafico = colunas_empilhadas(['jan', 'fev'], [
            {'nome': 'A', 'cor': '#000', 'valores': [2, 0]},
            {'nome': 'B', 'cor': '#fff', 'valores': [1, 0]},
        ])

        primeira, segunda = grafico['colunas']
        self.assertEqual([s['nome'] for s in primeira['segmentos']], ['A', 'B'])
        self.assertEqual((primeira['total'], segunda['segmentos']), (3, []))
        self.assertFalse(grafico['vazio'])


@mock.patch('manutencoes.views.timezone.localdate', return_value=HOJE_PROJECAO)
class ProjecaoPecasTelaTests(TestCase):
    def setUp(self):
        entrar(self.client)
        cliente = Cliente.objects.create(nome='Ana', cpf='111.222.333-44', email='ana@example.com')
        veiculo = Veiculo.objects.create(cliente=cliente, marca='Fiat', modelo='Uno', ano=2020, placa='XYZ9A87')
        manutencao = Manutencao.objects.create(
            veiculo=veiculo, descricao='Serviço', data_manutencao=date(2025, 12, 10),
            quilometragem=10000, valor='100.00',
        )
        self.peca = Peca.objects.create(nome='Filtro & Cia', preco_custo=Decimal('30.00'))
        PecaUsada.objects.create(manutencao=manutencao, peca=self.peca, quantidade=3)

    def test_painel_mostra_projecao_do_periodo_padrao(self, _hoje):
        resposta = self.client.get(reverse('dashboard'))

        projecao = resposta.context['projecao']
        self.assertEqual([mes.inicio for mes in projecao.meses][:2], [date(2026, 11, 1), date(2026, 12, 1)])
        self.assertEqual(len(projecao.meses), 6)
        self.assertEqual(projecao.linhas[0].quantidades, [0, 3, 0, 0, 0, 0])
        self.assertContains(resposta, 'id="grafico-projecao-titulo"')
        self.assertContains(resposta, '<th scope="row">Filtro &amp; Cia</th>', html=True)
        self.assertContains(resposta, f'{reverse("dashboard_projecao_pdf")}?inicio=2026-11&amp;meses=6')

    def test_periodo_escolhido(self, _hoje):
        resposta = self.client.get(reverse('dashboard'), {'inicio': '2026-12', 'meses': '1'})

        self.assertEqual(resposta.context['projecao'].linhas[0].quantidades, [3])

    def test_periodo_invalido_mostra_erro(self, _hoje):
        resposta = self.client.get(reverse('dashboard'), {'inicio': '2026-12', 'meses': '24'})

        self.assertIsNone(resposta.context['projecao'])
        self.assertContains(resposta, 'id="resumo-erros"')
        self.assertNotContains(resposta, 'Baixar relatório PDF')

    def test_sem_historico_avisa(self, _hoje):
        PecaUsada.objects.all().delete()

        resposta = self.client.get(reverse('dashboard'))

        self.assertContains(resposta, 'Ainda não há peças usadas em meses anteriores')

    def test_relatorio_pdf(self, _hoje):
        resposta = self.client.get(reverse('dashboard_projecao_pdf'), {'inicio': '2026-11', 'meses': '12'})

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta['Content-Type'], 'application/pdf')
        self.assertEqual(
            resposta['Content-Disposition'], 'attachment; filename="projecao-pecas-2026-11-a-2027-10.pdf"'
        )
        self.assertTrue(resposta.content.startswith(b'%PDF'))

    def test_relatorio_pdf_sem_historico(self, _hoje):
        PecaUsada.objects.all().delete()

        resposta = self.client.get(reverse('dashboard_projecao_pdf'))

        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(resposta.content.startswith(b'%PDF'))

    def test_relatorio_pdf_com_periodo_invalido_volta_ao_painel(self, _hoje):
        resposta = self.client.get(reverse('dashboard_projecao_pdf'), {'inicio': '2026-11', 'meses': '13'})

        self.assertRedirects(resposta, f'{reverse("dashboard")}?inicio=2026-11&meses=13#projecao',
                             fetch_redirect_response=False)


@mock.patch('manutencoes.views.timezone.localdate', return_value=HOJE_PROJECAO)
class PaginacaoTabelasPainelTests(TestCase):
    """As tabelas do painel paginam só na tela, cada uma com seus próprios parâmetros."""

    @classmethod
    def setUpTestData(cls):
        cliente = Cliente.objects.create(nome='Ana', cpf='111.222.333-44', email='ana@example.com')
        veiculo = Veiculo.objects.create(cliente=cliente, marca='Fiat', modelo='Uno', ano=2020, placa='XYZ9A87')
        # 13 meses de histórico (out/2025 a out/2026) e 12 peças usadas em novembro/2025
        for i in range(13):
            Manutencao.objects.create(
                veiculo=veiculo, descricao='Serviço', data_manutencao=add_months(date(2025, 10, 5), i),
                quilometragem=10000, valor='100.00',
            )
        novembro = Manutencao.objects.get(data_manutencao=date(2025, 11, 5))
        for i in range(12):
            peca = Peca.objects.create(nome=f'Peça {i:02d}', preco_custo=Decimal('10.00'))
            PecaUsada.objects.create(manutencao=novembro, peca=peca, quantidade=1)

    def setUp(self):
        entrar(self.client)

    def test_padrao_dez_itens_por_pagina(self, _hoje):
        resposta = self.client.get(reverse('dashboard'))

        self.assertEqual(len(resposta.context['tabela_historico']['pagina']), 10)
        self.assertEqual(len(resposta.context['tabela_projecao']['pagina']), 10)
        self.assertContains(resposta, '1–10 de 13 meses')
        self.assertContains(resposta, '1–10 de 12 peças')
        self.assertContains(resposta, 'aria-label="Páginas da tabela de meses"')
        # Totais da projeção continuam somando todas as peças, não só as da página
        self.assertEqual(resposta.context['projecao'].total_pecas, 12)
        self.assertContains(resposta, '(todas as peças)')

    def test_escolher_itens_por_pagina(self, _hoje):
        resposta = self.client.get(reverse('dashboard'), {'por_pagina_historico': '25'})

        self.assertEqual(len(resposta.context['tabela_historico']['pagina']), 13)
        self.assertNotContains(resposta, 'aria-label="Páginas da tabela de meses"')
        self.assertContains(resposta, '<option value="25" selected>25</option>', html=True)
        # A outra tabela não muda
        self.assertEqual(len(resposta.context['tabela_projecao']['pagina']), 10)

    def test_quantidade_fora_das_opcoes_usa_o_padrao(self, _hoje):
        for valor in ('7', 'abc', '1000'):
            with self.subTest(valor=valor):
                resposta = self.client.get(reverse('dashboard'), {'por_pagina_historico': valor})
                self.assertEqual(resposta.context['tabela_historico']['por_pagina'], 10)

    def test_paginas_independentes_e_links_mantem_a_tela(self, _hoje):
        resposta = self.client.get(
            reverse('dashboard'), {'inicio': '2026-11', 'meses': '3', 'pagina_historico': '2'}
        )

        historico = resposta.context['tabela_historico']
        self.assertEqual(historico['pagina'].number, 2)
        self.assertEqual(len(historico['pagina']), 3)
        self.assertEqual(resposta.context['tabela_projecao']['pagina'].number, 1)
        self.assertEqual(historico['url_anterior'], '?inicio=2026-11&meses=3&pagina_historico=1#titulo-tabela-historico')
        self.assertEqual(
            resposta.context['tabela_projecao']['url_proxima'],
            '?inicio=2026-11&meses=3&pagina_historico=2&pagina_pecas=2#titulo-tabela-projecao',
        )

    def test_pagina_inexistente_mostra_a_ultima(self, _hoje):
        resposta = self.client.get(reverse('dashboard'), {'pagina_pecas': '99'})

        self.assertEqual(resposta.context['tabela_projecao']['pagina'].number, 2)

    def test_formularios_mantem_os_parametros_da_outra_tabela(self, _hoje):
        resposta = self.client.get(reverse('dashboard'), {
            'inicio': '2026-11', 'meses': '3', 'pagina_pecas': '2', 'pagina_historico': '2',
            'por_pagina_historico': '10',
        })

        # Trocar o período mantém a paginação do histórico e volta a tabela de peças para a página 1
        self.assertEqual(
            resposta.context['ocultos_projecao'], [('pagina_historico', '2'), ('por_pagina_historico', '10')]
        )
        # Trocar a quantidade do histórico mantém período e página das peças
        self.assertEqual(
            resposta.context['tabela_historico']['ocultos'],
            [('inicio', '2026-11'), ('meses', '3'), ('pagina_pecas', '2')],
        )

    def test_tabela_pequena_nao_mostra_paginacao(self, _hoje):
        PecaUsada.objects.exclude(peca__nome='Peça 00').delete()

        resposta = self.client.get(reverse('dashboard'))

        self.assertNotContains(resposta, 'id="id_por_pagina_pecas"')
        self.assertContains(resposta, 'id="id_por_pagina_historico"')

    def test_relatorio_pdf_ignora_a_paginacao(self, _hoje):
        with mock.patch('manutencoes.views.gerar_pdf_projecao', return_value=b'%PDF') as gerar:
            resposta = self.client.get(
                reverse('dashboard_projecao_pdf'),
                {'inicio': '2026-11', 'meses': '1', 'pagina_pecas': '2', 'por_pagina_pecas': '10'},
            )

        self.assertEqual(resposta.status_code, 200)
        projecao = gerar.call_args.args[0]
        self.assertEqual(len(projecao.linhas), 12)


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
