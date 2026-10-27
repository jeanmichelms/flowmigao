"""Geometria de gráficos de colunas empilhadas, desenhados em SVG no template (sem JavaScript)."""
import math

LARGURA = 760
ALTURA = 300
MARGEM_ESQUERDA = 44
MARGEM_DIREITA = 12
MARGEM_TOPO = 24
MARGEM_BASE = 32
LARGURA_MAXIMA_COLUNA = 34
# Espaço entre os segmentos empilhados: o fundo aparece entre eles, sem contorno desenhado
ESPACO_SEGMENTOS = 2
RAIO = 4


def escala(maximo, divisoes=4):
    """Passo "redondo" (1, 2, 5 x 10^n, nunca fracionário) e topo do eixo para o maior valor."""
    if maximo <= 0:
        return 1, divisoes
    bruto = maximo / divisoes
    potencia = 10 ** math.floor(math.log10(bruto))
    passo = next(m * potencia for m in (1, 2, 5, 10) if m * potencia >= bruto)
    passo = max(1, int(passo))
    return passo, passo * math.ceil(maximo / passo)


def caminho_coluna(x, y, largura, altura, arredondar_topo):
    """Retângulo com os cantos de cima arredondados (ponta do dado) e base reta."""
    if not arredondar_topo:
        return f'M{x:.1f},{y:.1f}h{largura:.1f}v{altura:.1f}h{-largura:.1f}Z'
    r = min(RAIO, largura / 2, altura)
    return (
        f'M{x:.1f},{y + altura:.1f}V{y + r:.1f}Q{x:.1f},{y:.1f} {x + r:.1f},{y:.1f}'
        f'H{x + largura - r:.1f}Q{x + largura:.1f},{y:.1f} {x + largura:.1f},{y + r:.1f}'
        f'V{y + altura:.1f}Z'
    )


def colunas_empilhadas(rotulos, series):
    """`series`: lista de {'nome', 'cor', 'valores'}, com um valor por rótulo, de baixo para cima."""
    totais = [sum(serie['valores'][i] for serie in series) for i in range(len(rotulos))]
    passo, topo = escala(max(totais, default=0))

    area_altura = ALTURA - MARGEM_TOPO - MARGEM_BASE
    area_largura = LARGURA - MARGEM_ESQUERDA - MARGEM_DIREITA
    base_y = MARGEM_TOPO + area_altura
    faixa = area_largura / max(len(rotulos), 1)
    largura_coluna = min(LARGURA_MAXIMA_COLUNA, faixa * 0.6)

    def y_do_valor(valor):
        return base_y - valor / topo * area_altura

    linhas_grade = [
        {'y': round(y_do_valor(valor), 1), 'valor': valor}
        for valor in range(0, topo + 1, passo)
    ]

    colunas = []
    for i, rotulo in enumerate(rotulos):
        centro = MARGEM_ESQUERDA + faixa * (i + 0.5)
        x = centro - largura_coluna / 2
        presentes = [serie for serie in series if serie['valores'][i] > 0]
        segmentos = []
        acumulado = 0
        for posicao, serie in enumerate(presentes):
            valor = serie['valores'][i]
            y_inferior = y_do_valor(acumulado) - (ESPACO_SEGMENTOS if posicao else 0)
            acumulado += valor
            y_superior = y_do_valor(acumulado)
            altura = y_inferior - y_superior
            if altura <= 0:
                continue
            segmentos.append({
                'caminho': caminho_coluna(x, y_superior, largura_coluna, altura, posicao == len(presentes) - 1),
                'cor': serie['cor'],
                'nome': serie['nome'],
                'valor': valor,
            })
        colunas.append({
            'rotulo': rotulo,
            'centro': round(centro, 1),
            'total': totais[i],
            'y_total': round(y_do_valor(totais[i]) - 6, 1),
            'segmentos': segmentos,
            # Área de passar o mouse: a faixa inteira, maior que a coluna
            'faixa_x': round(MARGEM_ESQUERDA + faixa * i, 1),
        })

    return {
        'largura': LARGURA,
        'altura': ALTURA,
        'esquerda': MARGEM_ESQUERDA,
        'direita': LARGURA - MARGEM_DIREITA,
        'topo': MARGEM_TOPO,
        'base_y': base_y,
        'area_altura': area_altura,
        'faixa': round(faixa, 1),
        'rotulo_y': base_y + 20,
        'linhas_grade': linhas_grade,
        'colunas': colunas,
        'series': series,
        'vazio': not any(totais),
    }
