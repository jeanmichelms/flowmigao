from datetime import date

from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from manutencoes.models import Manutencao, Peca
from veiculos.models import Veiculo


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
