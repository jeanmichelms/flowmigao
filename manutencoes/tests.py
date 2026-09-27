from datetime import date, timedelta
from decimal import Decimal

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from clientes.models import Cliente
from veiculos.models import Veiculo

from .hosted_service import enviar_avisos_revisao
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
