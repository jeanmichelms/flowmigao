"""Paginação e busca das tabelas do sistema (listas de cadastro e tabelas do painel gerencial)."""
from django.core.paginator import Paginator
from django.db.models import Q

# Itens por página que o usuário pode escolher (o primeiro é o padrão)
OPCOES_POR_PAGINA = [10, 25, 50, 100]
# Os modais de busca (veículo na manutenção, cliente no veículo) mostram no máximo esta quantidade;
# a resposta informa o total encontrado para o modal avisar quando cortou resultados
LIMITE_RESULTADOS_MODAL = 50
# Números maiores que isso não são buscados como ID/ano (evita estouro do inteiro no banco)
MAXIMO_DIGITOS_BUSCA_NUMERICA = 9


def parametros_exceto(request, *nomes):
    """Parâmetros da URL atual, menos os indicados, como pares (nome, valor) para campos ocultos."""
    return [(nome, valor) for nome, valores in request.GET.lists() if nome not in nomes for valor in valores]


def paginar_tabela(request, itens, prefixo='', ancora=''):
    """Pagina `itens` conforme a URL. Com `prefixo`, os parâmetros viram `pagina_<prefixo>` e
    `por_pagina_<prefixo>`, para que tabelas da mesma tela paginem de forma independente."""
    sufixo = f'_{prefixo}' if prefixo else ''
    param_pagina, param_por_pagina = f'pagina{sufixo}', f'por_pagina{sufixo}'
    por_pagina = request.GET.get(param_por_pagina, '')
    por_pagina = int(por_pagina) if por_pagina.isdigit() and int(por_pagina) in OPCOES_POR_PAGINA else OPCOES_POR_PAGINA[0]
    pagina = Paginator(itens, por_pagina).get_page(request.GET.get(param_pagina))

    def url_da_pagina(numero):
        parametros = request.GET.copy()
        parametros[param_pagina] = numero
        return f'?{parametros.urlencode()}' + (f'#{ancora}' if ancora else '')

    return {
        'pagina': pagina,
        'ancora': ancora,
        'param_por_pagina': param_por_pagina,
        'por_pagina': por_pagina,
        'opcoes': OPCOES_POR_PAGINA,
        'url_anterior': url_da_pagina(pagina.previous_page_number()) if pagina.has_previous() else None,
        'url_proxima': url_da_pagina(pagina.next_page_number()) if pagina.has_next() else None,
        # Ao trocar a quantidade por página, mantém o resto da tela e volta para a primeira página desta tabela
        'ocultos': parametros_exceto(request, param_pagina, param_por_pagina),
    }


class ListaComBuscaMixin:
    """ListView com busca por texto (parâmetro `q`) em vários campos e paginação escolhida pelo usuário,
    no mesmo estilo da busca de veículos da tela de manutenção."""
    # Campos buscados com "contém", sem diferenciar maiúsculas
    campos_busca = []
    # Campos inteiros comparados quando a busca é só de números (ID, ano...)
    campos_busca_numericos = []
    # Textos da tela: "12 clientes", "Nome, CPF, e-mail..."
    rotulo_itens = 'registros'
    ajuda_busca = ''

    def termo_busca(self):
        return (self.request.GET.get('q') or '').strip()

    def get_queryset(self):
        itens = super().get_queryset()
        termo = self.termo_busca()
        if termo:
            condicao = Q()
            for campo in self.campos_busca:
                condicao |= Q(**{f'{campo}__icontains': termo})
            if termo.isdigit() and len(termo) <= MAXIMO_DIGITOS_BUSCA_NUMERICA:
                for campo in self.campos_busca_numericos:
                    condicao |= Q(**{campo: int(termo)})
            itens = itens.filter(condicao)
        return itens

    def get_context_data(self, **kwargs):
        tabela = paginar_tabela(self.request, self.object_list)
        kwargs.update(
            tabela=tabela,
            busca=self.termo_busca(),
            rotulo_itens=self.rotulo_itens,
            ajuda_busca=self.ajuda_busca,
            # Nova busca volta para a primeira página, mantendo a quantidade por página
            ocultos_busca=parametros_exceto(self.request, 'q', 'pagina'),
        )
        # A lista do template passa a ser só a página atual
        return super().get_context_data(object_list=tabela['pagina'], **kwargs)
