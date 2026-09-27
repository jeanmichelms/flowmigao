from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente

from .models import Veiculo


class VeiculoFormTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nome='Ana', cpf='111.222.333-44', email='ana@example.com')
        self.veiculo = Veiculo.objects.create(
            cliente=self.cliente,
            marca='Fiat',
            modelo='UNO MILLE 1.0 Fire/ F.Flex/ ECONOMY 4p',
            ano=2010,
            placa='ABC1D23',
        )

    def test_edicao_traz_marca_e_modelo_selecionados(self):
        resposta = self.client.get(reverse('veiculos_editar', args=[self.veiculo.pk]))

        self.assertContains(resposta, '<option value="Fiat" selected>Fiat</option>', html=True)
        self.assertContains(
            resposta,
            '<option value="UNO MILLE 1.0 Fire/ F.Flex/ ECONOMY 4p" selected>'
            'UNO MILLE 1.0 Fire/ F.Flex/ ECONOMY 4p</option>',
            html=True,
        )

    def test_edicao_mantem_marca_e_modelo_ao_salvar(self):
        resposta = self.client.post(
            reverse('veiculos_editar', args=[self.veiculo.pk]),
            {
                'cliente': self.cliente.pk,
                'marca': 'Fiat',
                'modelo': 'UNO MILLE 1.0 Fire/ F.Flex/ ECONOMY 4p',
                'ano': 2011,
                'placa': 'ABC1D23',
            },
        )

        self.assertRedirects(resposta, reverse('veiculos_lista'))
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.ano, 2011)
        self.assertEqual(self.veiculo.marca, 'Fiat')

    def test_erro_de_validacao_preserva_marca_e_modelo(self):
        resposta = self.client.post(
            reverse('veiculos_novo'),
            {'cliente': self.cliente.pk, 'marca': 'VW - VolksWagen', 'modelo': 'Gol 1.0', 'ano': 2015, 'placa': 'ABC1D23'},
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, '<option value="VW - VolksWagen" selected>VW - VolksWagen</option>', html=True)
        self.assertContains(resposta, '<option value="Gol 1.0" selected>Gol 1.0</option>', html=True)

    def test_cadastro_novo_comeca_sem_marca(self):
        resposta = self.client.get(reverse('veiculos_novo'))

        self.assertContains(resposta, '<option value="" selected>---------</option>', html=True)
