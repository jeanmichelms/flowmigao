from django.test import TestCase
from django.urls import reverse

from veiculos.models import Veiculo

from .forms import ClienteForm
from .models import Cliente


def dados_cliente(**extra):
    dados = {
        'nome': 'Maria Silva',
        'cpf': '123.456.789-10',
        'email': 'maria@example.com',
        'telefone': '(11) 99999-0000',
        'cep': '01001-000',
        'endereco': 'Praça da Sé',
        'numero': '100',
        'bairro': 'Sé',
        'cidade': 'São Paulo',
        'estado': 'SP',
    }
    dados.update(extra)
    return dados


class ClienteFormTests(TestCase):
    def test_aceita_cliente_completo(self):
        form = ClienteForm(data=dados_cliente())

        self.assertTrue(form.is_valid(), form.errors)

    def test_apenas_nome_cpf_e_email_sao_obrigatorios(self):
        form = ClienteForm(data={})

        self.assertFalse(form.is_valid())
        self.assertEqual(set(form.errors), {'nome', 'cpf', 'email'})

    def test_rejeita_email_invalido(self):
        form = ClienteForm(data=dados_cliente(email='maria-sem-arroba'))

        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_rejeita_cpf_e_email_ja_cadastrados(self):
        Cliente.objects.create(nome='Outra', cpf='123.456.789-10', email='maria@example.com')

        form = ClienteForm(data=dados_cliente())

        self.assertFalse(form.is_valid())
        self.assertIn('cpf', form.errors)
        self.assertIn('email', form.errors)


class ClienteViewsTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(nome='Ana Souza', cpf='111.222.333-44', email='ana@example.com')

    def test_lista_clientes_em_ordem_alfabetica(self):
        Cliente.objects.create(nome='Bruno Lima', cpf='555.666.777-88', email='bruno@example.com')
        Cliente.objects.create(nome='Aline Costa', cpf='999.888.777-66', email='aline@example.com')

        resposta = self.client.get(reverse('clientes_lista'))

        self.assertEqual(resposta.status_code, 200)
        nomes = [cliente.nome for cliente in resposta.context['clientes']]
        self.assertEqual(nomes, ['Aline Costa', 'Ana Souza', 'Bruno Lima'])

    def test_cadastra_cliente_e_volta_para_lista(self):
        resposta = self.client.post(reverse('clientes_novo'), dados_cliente())

        self.assertRedirects(resposta, reverse('clientes_lista'))
        cliente = Cliente.objects.get(cpf='123.456.789-10')
        self.assertEqual(cliente.cidade, 'São Paulo')
        self.assertIsNotNone(cliente.data_cadastro)

    def test_cadastro_invalido_nao_salva_e_mostra_erros(self):
        resposta = self.client.post(reverse('clientes_novo'), dados_cliente(nome='', email='invalido'))

        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(Cliente.objects.count(), 1)
        self.assertTrue(resposta.context['form'].errors)

    def test_edita_cliente(self):
        resposta = self.client.post(
            reverse('clientes_editar', args=[self.cliente.pk]),
            dados_cliente(nome='Ana Souza Lima', cpf=self.cliente.cpf, email=self.cliente.email),
        )

        self.assertRedirects(resposta, reverse('clientes_lista'))
        self.cliente.refresh_from_db()
        self.assertEqual(self.cliente.nome, 'Ana Souza Lima')
        self.assertEqual(self.cliente.telefone, '(11) 99999-0000')

    def test_detalhe_mostra_veiculos_do_cliente(self):
        Veiculo.objects.create(cliente=self.cliente, marca='Fiat', modelo='Uno', ano=2015, placa='ABC1D23')

        resposta = self.client.get(reverse('clientes_detalhe', args=[self.cliente.pk]))

        self.assertContains(resposta, 'Ana Souza')
        self.assertContains(resposta, 'ABC1D23')

    def test_detalhe_de_cliente_inexistente_retorna_404(self):
        resposta = self.client.get(reverse('clientes_detalhe', args=[9999]))

        self.assertEqual(resposta.status_code, 404)

    def test_confirmacao_nao_exclui_e_post_exclui_com_veiculos(self):
        Veiculo.objects.create(cliente=self.cliente, marca='Fiat', modelo='Uno', ano=2015, placa='ABC1D23')
        url = reverse('clientes_excluir', args=[self.cliente.pk])

        self.assertContains(self.client.get(url), 'Tem certeza que deseja excluir')
        self.assertTrue(Cliente.objects.filter(pk=self.cliente.pk).exists())

        resposta = self.client.post(url)

        self.assertRedirects(resposta, reverse('clientes_lista'))
        self.assertFalse(Cliente.objects.filter(pk=self.cliente.pk).exists())
        self.assertFalse(Veiculo.objects.exists())
