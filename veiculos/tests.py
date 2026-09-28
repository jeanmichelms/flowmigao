from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from usuarios.apoio_testes import entrar

from .models import Veiculo


class VeiculoFormTests(TestCase):
    def setUp(self):
        entrar(self.client)
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


class VeiculoCadastroTests(TestCase):
    def setUp(self):
        entrar(self.client)
        self.cliente = Cliente.objects.create(nome='Ana', cpf='111.222.333-44', email='ana@example.com')

    def dados(self, **extra):
        dados = {'cliente': self.cliente.pk, 'marca': 'Fiat', 'modelo': 'Uno', 'ano': 2015, 'placa': 'ABC1D23'}
        dados.update(extra)
        return dados

    def test_cadastra_veiculo_e_volta_para_lista(self):
        resposta = self.client.post(reverse('veiculos_novo'), self.dados())

        self.assertRedirects(resposta, reverse('veiculos_lista'))
        self.assertEqual(Veiculo.objects.get().cliente, self.cliente)

    def test_cadastro_a_partir_do_cliente_volta_para_o_cliente(self):
        url = reverse('veiculos_novo') + f'?cliente={self.cliente.pk}&origem=cliente_detalhe'

        resposta_get = self.client.get(url)
        self.assertEqual(resposta_get.context['selected_cliente'], self.cliente)
        self.assertEqual(
            str(resposta_get.context['cancel_url']),
            reverse('clientes_detalhe', args=[self.cliente.pk]),
        )

        resposta = self.client.post(url, self.dados())
        self.assertRedirects(resposta, reverse('clientes_detalhe', args=[self.cliente.pk]))

    def test_exige_cliente(self):
        resposta = self.client.post(reverse('veiculos_novo'), self.dados(cliente=''))

        self.assertEqual(resposta.status_code, 200)
        self.assertIn('cliente', resposta.context['form'].errors)
        self.assertFalse(Veiculo.objects.exists())

    def test_rejeita_placa_repetida(self):
        Veiculo.objects.create(cliente=self.cliente, marca='VW', modelo='Gol', ano=2012, placa='ABC1D23')

        resposta = self.client.post(reverse('veiculos_novo'), self.dados())

        self.assertEqual(resposta.status_code, 200)
        self.assertIn('placa', resposta.context['form'].errors)
        self.assertEqual(Veiculo.objects.count(), 1)

    def test_exclui_veiculo(self):
        veiculo = Veiculo.objects.create(cliente=self.cliente, marca='VW', modelo='Gol', ano=2012, placa='ABC1D23')

        resposta = self.client.post(reverse('veiculos_excluir', args=[veiculo.pk]))

        self.assertRedirects(resposta, reverse('veiculos_lista'))
        self.assertFalse(Veiculo.objects.exists())
        self.assertTrue(Cliente.objects.filter(pk=self.cliente.pk).exists())


class ClienteBuscaViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = Cliente.objects.create(nome='Ana Souza', cpf='111.222.333-44', email='ana@example.com')
        cls.bruno = Cliente.objects.create(
            nome='Bruno Lima', cpf='555.666.777-88', email='bruno@example.com', telefone='(11) 98888-7777'
        )

    def setUp(self):
        entrar(self.client)

    def buscar(self, termo):
        resposta = self.client.get(reverse('veiculos_buscar_clientes'), {'q': termo})
        self.assertEqual(resposta.status_code, 200)
        return [item['nome'] for item in resposta.json()['results']]

    def test_sem_filtro_retorna_todos_em_ordem_alfabetica(self):
        self.assertEqual(self.buscar(''), ['Ana Souza', 'Bruno Lima'])

    def test_filtra_por_nome_cpf_email_e_telefone(self):
        self.assertEqual(self.buscar('souza'), ['Ana Souza'])
        self.assertEqual(self.buscar('555.666'), ['Bruno Lima'])
        self.assertEqual(self.buscar('ana@'), ['Ana Souza'])
        self.assertEqual(self.buscar('98888'), ['Bruno Lima'])

    def test_filtra_pelo_id(self):
        self.assertIn('Bruno Lima', self.buscar(str(self.bruno.pk)))

    def test_retorna_campos_usados_pelo_modal(self):
        resposta = self.client.get(reverse('veiculos_buscar_clientes'), {'q': 'Ana'})

        self.assertEqual(
            resposta.json()['results'][0],
            {'id': self.ana.pk, 'nome': 'Ana Souza', 'cpf': '111.222.333-44', 'email': 'ana@example.com', 'telefone': ''},
        )

    def test_nao_encontra_nada(self):
        self.assertEqual(self.buscar('inexistente'), [])
