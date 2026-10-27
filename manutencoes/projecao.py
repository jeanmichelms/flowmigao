"""Projeção da quantidade de peças necessárias por mês, a partir do histórico de peças usadas.

Para cada mês do período escolhido, a quantidade de cada peça é a média do que foi usado no mesmo
mês dos anos anteriores (ex.: março/2027 usa a média de março/2026, março/2025...). Só entram meses
já encerrados e a partir do primeiro mês com peça registrada: antes disso o sistema não registrava
peças, e contar esses meses como zero puxaria a média para baixo. Quando ainda não há nenhum ano
anterior daquele mês, usa-se a média mensal de todo o histórico. As médias são arredondadas para
o inteiro mais próximo, porque a projeção é em unidades de peça.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Min, Sum
from django.db.models.functions import TruncMonth
from django.utils import dateformat

from .forms import add_months
from .models import Peca, PecaUsada

BASE_MESMO_MES = 'mesmo_mes'
BASE_MEDIA_GERAL = 'media_geral'
BASE_SEM_HISTORICO = 'sem_historico'

# Quantas peças aparecem separadas no gráfico; as demais somam em "Outras peças"
PECAS_NO_GRAFICO = 5
# Paleta categórica (ordem fixa, validada para daltonismo entre vizinhos) + cinza para "Outras"
CORES_SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4']
COR_OUTRAS = '#898781'


@dataclass
class MesProjetado:
    inicio: date
    base: str
    anos_base: int = 0
    total: int = 0

    @property
    def rotulo(self):
        return dateformat.format(self.inicio, 'M/Y')

    @property
    def rotulo_curto(self):
        return dateformat.format(self.inicio, 'M/y')

    @property
    def descricao_base(self):
        if self.base == BASE_MESMO_MES:
            return f'{self.anos_base} ano{"s" if self.anos_base > 1 else ""}'
        if self.base == BASE_MEDIA_GERAL:
            return 'Média geral'
        return 'Sem histórico'


@dataclass
class LinhaProjecao:
    peca: Peca
    quantidades: list
    total: int = 0
    custo: Decimal = Decimal('0.00')


@dataclass
class Projecao:
    meses: list
    linhas: list = field(default_factory=list)
    inicio_historico: date | None = None

    @property
    def total_pecas(self):
        return sum(linha.total for linha in self.linhas)

    @property
    def custo_total(self):
        return sum((linha.custo for linha in self.linhas), Decimal('0.00'))

    @property
    def usa_media_geral(self):
        return any(mes.base == BASE_MEDIA_GERAL for mes in self.meses)

    def series_grafico(self):
        """Séries do gráfico de colunas empilhadas: as peças com maior total e o restante somado."""
        principais = sorted(self.linhas, key=lambda linha: (-linha.total, str(linha.peca)))[:PECAS_NO_GRAFICO]
        series = [
            {'nome': str(linha.peca), 'cor': cor, 'valores': linha.quantidades}
            for linha, cor in zip(principais, CORES_SERIES)
        ]
        demais = [linha for linha in self.linhas if linha not in principais]
        if demais:
            series.append({
                'nome': f'Outras peças ({len(demais)})',
                'cor': COR_OUTRAS,
                'valores': [sum(linha.quantidades[i] for linha in demais) for i in range(len(self.meses))],
            })
        return series


def inicio_do_mes(data):
    return data.replace(day=1)


def arredondar(valor):
    return int(Decimal(valor).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def projetar_pecas(inicio, quantidade_meses, hoje):
    """Projeta, mês a mês, a quantidade de cada peça a partir de `inicio` (primeiro dia do mês)."""
    mes_atual = inicio_do_mes(hoje)
    meses = [MesProjetado(add_months(inicio, i), BASE_SEM_HISTORICO) for i in range(quantidade_meses)]

    # Mês corrente ainda não terminou: o histórico vai só até o mês anterior
    usadas = PecaUsada.objects.filter(manutencao__data_manutencao__lt=mes_atual)
    inicio_historico = usadas.aggregate(primeiro=Min('manutencao__data_manutencao'))['primeiro']
    if inicio_historico is None:
        return Projecao(meses=meses)
    inicio_historico = inicio_do_mes(inicio_historico)

    # {peca_id: {mês: quantidade}}
    historico = defaultdict(dict)
    por_mes = (
        usadas.annotate(mes=TruncMonth('manutencao__data_manutencao'))
        .values('peca_id', 'mes')
        .annotate(quantidade=Sum('quantidade'))
    )
    for item in por_mes:
        historico[item['peca_id']][inicio_do_mes(item['mes'])] = item['quantidade']

    meses_no_historico = (mes_atual.year - inicio_historico.year) * 12 + mes_atual.month - inicio_historico.month

    # Para cada mês projetado, os mesmos meses de anos anteriores que já estão no histórico
    referencias = []
    for mes in meses:
        anteriores = []
        ano = mes.inicio.year - 1
        while date(ano, mes.inicio.month, 1) >= inicio_historico:
            if date(ano, mes.inicio.month, 1) < mes_atual:
                anteriores.append(date(ano, mes.inicio.month, 1))
            ano -= 1
        referencias.append(anteriores)
        mes.base = BASE_MESMO_MES if anteriores else BASE_MEDIA_GERAL
        mes.anos_base = len(anteriores)

    pecas = Peca.objects.in_bulk(historico.keys())
    linhas = []
    for peca_id, usos in historico.items():
        total_historico = sum(usos.values())
        quantidades = []
        for mes, anteriores in zip(meses, referencias):
            if anteriores:
                media = Decimal(sum(usos.get(ano, 0) for ano in anteriores)) / len(anteriores)
            else:
                media = Decimal(total_historico) / meses_no_historico
            quantidades.append(arredondar(media))

        total = sum(quantidades)
        if total:
            peca = pecas[peca_id]
            linhas.append(LinhaProjecao(peca, quantidades, total, total * peca.preco_custo))

    linhas.sort(key=lambda linha: (-linha.total, str(linha.peca)))
    for i, mes in enumerate(meses):
        mes.total = sum(linha.quantidades[i] for linha in linhas)

    return Projecao(meses=meses, linhas=linhas, inicio_historico=inicio_historico)
