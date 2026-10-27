from datetime import date

from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from clientes.models import Cliente
from manutencoes.models import Manutencao, Peca
from usuarios.apoio_testes import entrar
from veiculos.models import Veiculo

from .paginacao import paginar_tabela, parametros_exceto


class PaginarTabelaTests(SimpleTestCase):
    def _requisicao(self, **parametros):
        return RequestFactory().get('/lista/', parametros)

    def test_sem_prefixo_usa_pagina_e_por_pagina(self):
        tabela = paginar_tabela(self._requisicao(q='ana', pagina='2', por_pagina='25'), list(range(60)))

        self.assertEqual((tabela['pagina'].number, len(tabela['pagina'])), (2, 25))
        self.assertEqual(tabela['url_anterior'], '?q=ana&pagina=1&por_pagina=25')
        self.assertEqual(tabela['url_proxima'], '?q=ana&pagina=3&por_pagina=25')
        self.assertEqual(tabela['ocultos'], [('q', 'ana')])

    def test_com_prefixo_e_ancora(self):
        tabela = paginar_tabela(self._requisicao(pagina_x='1'), list(range(30)), 'x', 'tabela-x')

        self.assertEqual(tabela['param_por_pagina'], 'por_pagina_x')
        self.assertEqual(tabela['url_proxima'], '?pagina_x=2#tabela-x')

    def test_parametros_exceto_mantem_valores_repetidos(self):
        requisicao = RequestFactory().get('/?a=1&a=2&b=3&c=4')

        self.assertEqual(parametros_exceto(requisicao, 'c'), [('a', '1'), ('a', '2'), ('b', '3')])


class ListasComBuscaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.ana = Cliente.objects.create(
            nome='Ana Souza', cpf='111.222.333-44', email='ana@example.com', telefone='(11) 98888-7777',
            cidade='Campinas',
        )
        cls.bruno = Cliente.objects.create(nome='Bruno Lima', cpf='555.666.777-88', email='bruno@example.com')
        # Clientes extras para a lista ter mais de uma página (12 no total)
        for i in range(10):
            Cliente.objects.create(nome=f'Zé {i:02d}', cpf=f'000.000.000-{i:02d}', email=f'ze{i}@example.com')

        cls.uno = Veiculo.objects.create(cliente=cls.ana, marca='Fiat', modelo='Uno', ano=2015, placa='ABC1D23', cor='Prata')
        cls.gol = Veiculo.objects.create(cliente=cls.bruno, marca='Volkswagen', modelo='Gol', ano=2020, placa='XYZ9A87')
        cls.troca_oleo = Manutencao.objects.create(
            veiculo=cls.uno, descricao='Troca de óleo', data_manutencao=date(2026, 1, 10),
            quilometragem=50000, valor='250.00',
        )
        cls.freios = Manutencao.objects.create(
            veiculo=cls.gol, descricao='Revisão dos freios', data_manutencao=date(2026, 2, 10),
            quilometragem=30000, valor='400.00',
        )
        Peca.objects.create(nome='Filtro de óleo', marca='Tecfil', preco_custo=30)
        Peca.objects.create(nome='Vela de ignição', marca='NGK', preco_custo=32)

    def setUp(self):
        entrar(self.client)

    def _itens(self, rota, **parametros):
        resposta = self.client.get(reverse(rota), parametros)
        self.assertEqual(resposta.status_code, 200)
        return resposta, list(resposta.context['tabela']['pagina'])

    def test_lista_paginada_com_dez_por_padrao(self):
        resposta, clientes = self._itens('clientes_lista')

        self.assertEqual(len(clientes), 10)
        self.assertContains(resposta, '1–10 de 12 clientes')
        self.assertContains(resposta, 'href="?pagina=2"')

        _, clientes = self._itens('clientes_lista', pagina='2')
        self.assertEqual(len(clientes), 2)

    def test_usuario_escolhe_itens_por_pagina(self):
        resposta, clientes = self._itens('clientes_lista', por_pagina='25')

        self.assertEqual(len(clientes), 12)
        self.assertContains(resposta, '<option value="25" selected>25</option>', html=True)
        self.assertNotContains(resposta, 'Página 1 de')

    def test_busca_de_clientes_em_varios_campos(self):
        for termo in ('souza', '111.222', 'ana@', '98888', 'campinas', str(self.ana.pk)):
            with self.subTest(termo=termo):
                _, clientes = self._itens('clientes_lista', q=termo)
                self.assertIn(self.ana, clientes)
                self.assertNotIn(self.bruno, clientes)

    def test_busca_de_veiculos_em_varios_campos(self):
        for termo, esperado in (('ana souza', self.uno), ('555.666', self.gol), ('volks', self.gol),
                                ('gol', self.gol), ('xyz9', self.gol), ('prata', self.uno), ('2020', self.gol)):
            with self.subTest(termo=termo):
                _, veiculos = self._itens('veiculos_lista', q=termo)
                self.assertEqual(veiculos, [esperado])

    def test_busca_de_pecas_por_nome_e_marca(self):
        _, pecas = self._itens('pecas_lista', q='ngk')
        self.assertEqual([peca.nome for peca in pecas], ['Vela de ignição'])

        _, pecas = self._itens('pecas_lista', q='óleo')
        self.assertEqual([peca.nome for peca in pecas], ['Filtro de óleo'])

    def test_busca_de_manutencoes_em_varios_campos(self):
        for termo, esperado in (('bruno', self.freios), ('abc1', self.troca_oleo), ('freios', self.freios),
                                ('fiat', self.troca_oleo), ('2015', self.troca_oleo)):
            with self.subTest(termo=termo):
                _, manutencoes = self._itens('manutencoes_lista', q=termo)
                self.assertEqual(manutencoes, [esperado])

    def test_busca_sem_resultado(self):
        resposta, clientes = self._itens('clientes_lista', q='inexistente')

        self.assertEqual(clientes, [])
        self.assertContains(resposta, 'Nenhum cliente encontrado.')
        self.assertContains(resposta, '0 resultados para')
        self.assertNotContains(resposta, 'Nenhum cliente cadastrado.')

    def test_busca_com_numero_grande_nao_quebra(self):
        _, clientes = self._itens('clientes_lista', q='12345678901234567890')

        self.assertEqual(clientes, [])

    def test_paginacao_mantem_a_busca_e_busca_volta_para_a_primeira_pagina(self):
        # Todos os 12 clientes têm e-mail @example.com: a busca ocupa duas páginas
        resposta, _ = self._itens('clientes_lista', q='example', pagina='1')

        self.assertContains(resposta, '12 resultados para')
        self.assertEqual(resposta.context['tabela']['url_proxima'], '?q=example&pagina=2')

        resposta, clientes = self._itens('clientes_lista', q='example', pagina='2', por_pagina='10')
        self.assertEqual(len(clientes), 2)
        # A busca mantém a quantidade por página, mas não a página
        self.assertEqual(resposta.context['ocultos_busca'], [('por_pagina', '10')])
        self.assertContains(resposta, 'href="?por_pagina=10">Limpar busca</a>')

    def test_todas_as_listas_tem_busca_acessivel(self):
        for rota in ('clientes_lista', 'veiculos_lista', 'pecas_lista', 'manutencoes_lista'):
            with self.subTest(rota=rota):
                resposta = self.client.get(reverse(rota))
                self.assertContains(resposta, 'role="search"')
                self.assertContains(resposta, '<label for="id_q">Buscar</label>', html=True)
                self.assertContains(resposta, 'aria-describedby="id_q_ajuda"')
