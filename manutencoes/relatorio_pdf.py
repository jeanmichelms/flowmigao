"""Relatório em PDF da projeção de peças: resumo, gráfico de colunas empilhadas e tabela por mês."""
from html import escape
from io import BytesIO

from django.utils import dateformat, timezone
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.legends import Legend
from reportlab.graphics.shapes import Drawing, String
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .graficos import escala

TINTA = colors.HexColor('#111827')
TINTA_SECUNDARIA = colors.HexColor('#4b5563')
GRADE = colors.HexColor('#e5e7eb')
EIXO = colors.HexColor('#9ca3af')
FUNDO_CABECALHO = colors.HexColor('#1f2937')
FUNDO_ZEBRA = colors.HexColor('#f9fafb')


def moeda(valor):
    inteiro, centavos = f'{valor:,.2f}'.split('.')
    return f'R$ {inteiro.replace(",", ".")},{centavos}'


def _estilos():
    base = getSampleStyleSheet()
    return {
        'titulo': ParagraphStyle('titulo', parent=base['Title'], alignment=0, fontSize=18, spaceAfter=2, textColor=TINTA),
        'subtitulo': ParagraphStyle('subtitulo', parent=base['Normal'], fontSize=10, textColor=TINTA_SECUNDARIA),
        'secao': ParagraphStyle('secao', parent=base['Heading2'], fontSize=12, spaceBefore=10, spaceAfter=6, textColor=TINTA),
        'texto': ParagraphStyle('texto', parent=base['Normal'], fontSize=9, leading=12, textColor=TINTA),
        'nota': ParagraphStyle('nota', parent=base['Normal'], fontSize=8, leading=10, textColor=TINTA_SECUNDARIA),
        'celula': ParagraphStyle('celula', parent=base['Normal'], fontSize=8, leading=10),
        'cabecalho': ParagraphStyle('cabecalho', parent=base['Normal'], fontSize=8, leading=10,
                                    textColor=colors.white, fontName='Helvetica-Bold'),
        'cabecalho_numero': ParagraphStyle('cabecalho_numero', parent=base['Normal'], fontSize=8, leading=10,
                                           textColor=colors.white, fontName='Helvetica-Bold', alignment=TA_RIGHT),
    }


def _grafico(projecao, largura):
    series = projecao.series_grafico()
    altura = 7 * cm
    desenho = Drawing(largura, altura)

    grafico = VerticalBarChart()
    grafico.x, grafico.y = 30, 30
    grafico.width = largura - 180
    grafico.height = altura - 45
    grafico.data = [serie['valores'] for serie in series]
    grafico.categoryAxis.style = 'stacked'
    grafico.categoryAxis.categoryNames = [mes.rotulo_curto for mes in projecao.meses]
    grafico.categoryAxis.labels.fontSize = 8
    grafico.categoryAxis.labels.fillColor = TINTA_SECUNDARIA
    grafico.categoryAxis.strokeColor = EIXO
    grafico.categoryAxis.tickDown = 0

    passo, topo = escala(max((mes.total for mes in projecao.meses), default=0))
    grafico.valueAxis.valueMin = 0
    grafico.valueAxis.valueMax = topo
    grafico.valueAxis.valueStep = passo
    grafico.valueAxis.labels.fontSize = 8
    grafico.valueAxis.labels.fillColor = TINTA_SECUNDARIA
    grafico.valueAxis.strokeColor = colors.transparent
    grafico.valueAxis.visibleGrid = True
    grafico.valueAxis.gridStrokeColor = GRADE
    grafico.valueAxis.gridStrokeWidth = 0.5
    grafico.valueAxis.labelTextFormat = '%d'

    grafico.barWidth = 10
    grafico.groupSpacing = 10
    grafico.bars.strokeColor = colors.white
    grafico.bars.strokeWidth = 1
    for i, serie in enumerate(series):
        grafico.bars[i].fillColor = colors.HexColor(serie['cor'])
    desenho.add(grafico)

    # Total no topo de cada coluna
    faixa = grafico.width / max(len(projecao.meses), 1)
    for i, mes in enumerate(projecao.meses):
        if mes.total:
            y = grafico.y + mes.total / topo * grafico.height + 3
            desenho.add(String(grafico.x + faixa * (i + 0.5), y, str(mes.total),
                               fontName='Helvetica-Bold', fontSize=7, fillColor=TINTA, textAnchor='middle'))

    legenda = Legend()
    legenda.x = grafico.x + grafico.width + 20
    legenda.y = grafico.y + grafico.height
    legenda.alignment = 'right'
    legenda.fontSize = 8
    legenda.fillColor = TINTA
    legenda.boxAnchor = 'nw'
    legenda.columnMaximum = 10
    legenda.dx = legenda.dy = 8
    legenda.deltay = 12
    legenda.strokeColor = colors.transparent
    # De cima para baixo na mesma ordem em que os segmentos aparecem empilhados
    legenda.colorNamePairs = [
        (colors.HexColor(serie['cor']), serie['nome'][:28]) for serie in reversed(series)
    ]
    desenho.add(legenda)
    return desenho


def _tabela(projecao, largura, estilos):
    meses = projecao.meses
    largura_peca, largura_total, largura_custo = 5.2 * cm, 1.4 * cm, 2.4 * cm
    largura_mes = (largura - largura_peca - largura_total - largura_custo) / len(meses)

    cabecalho = (
        [Paragraph('Peça', estilos['cabecalho'])]
        + [Paragraph(mes.rotulo_curto, estilos['cabecalho_numero']) for mes in meses]
        + [Paragraph('Total', estilos['cabecalho_numero']), Paragraph('Custo estimado', estilos['cabecalho_numero'])]
    )
    dados = [cabecalho]
    for linha in projecao.linhas:
        dados.append(
            [Paragraph(escape(str(linha.peca)), estilos['celula'])]
            + [str(q) if q else '–' for q in linha.quantidades]
            + [str(linha.total), moeda(linha.custo)]
        )
    dados.append(['Total por mês'] + [str(mes.total) for mes in meses]
                 + [str(projecao.total_pecas), moeda(projecao.custo_total)])
    dados.append(['Base do cálculo'] + [mes.descricao_base for mes in meses] + ['', ''])

    tabela = Table(
        dados,
        colWidths=[largura_peca] + [largura_mes] * len(meses) + [largura_total, largura_custo],
        repeatRows=1,
    )
    ultima = len(dados) - 1
    estilo = [
        ('BACKGROUND', (0, 0), (-1, 0), FUNDO_CABECALHO),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
        ('TEXTCOLOR', (0, 1), (-1, -1), TINTA),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, GRADE),
        ('FONTNAME', (-2, 1), (-2, ultima - 1), 'Helvetica-Bold'),
        ('FONTNAME', (0, ultima - 1), (-1, ultima - 1), 'Helvetica-Bold'),
        ('LINEABOVE', (0, ultima - 1), (-1, ultima - 1), 1, EIXO),
        ('FONTSIZE', (1, ultima), (-1, ultima), 6.5),
        ('TEXTCOLOR', (0, ultima), (-1, ultima), TINTA_SECUNDARIA),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]
    for i in range(1, ultima - 1, 2):
        estilo.append(('BACKGROUND', (0, i), (-1, i), FUNDO_ZEBRA))
    tabela.setStyle(TableStyle(estilo))
    return tabela


def _rodape(canvas, documento):
    canvas.saveState()
    canvas.setFont('Helvetica', 7)
    canvas.setFillColor(TINTA_SECUNDARIA)
    canvas.drawString(documento.leftMargin, 0.8 * cm, 'FlowMigao – Projeção de peças')
    canvas.drawRightString(documento.pagesize[0] - documento.rightMargin, 0.8 * cm, f'Página {documento.page}')
    canvas.restoreState()


def gerar_pdf_projecao(projecao):
    buffer = BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=landscape(A4),
        leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.3 * cm, bottomMargin=1.5 * cm,
        title='Projeção de peças necessárias', author='FlowMigao',
    )
    estilos = _estilos()
    largura = documento.width
    primeiro, ultimo = projecao.meses[0], projecao.meses[-1]
    gerado_em = dateformat.format(timezone.localtime(), 'd/m/Y \\à\\s H:i')

    historia = [
        Paragraph('Projeção de peças necessárias', estilos['titulo']),
        Paragraph(
            f'Período: {primeiro.rotulo} a {ultimo.rotulo} ({len(projecao.meses)} '
            f'{"mês" if len(projecao.meses) == 1 else "meses"}) · Gerado em {gerado_em}',
            estilos['subtitulo'],
        ),
        Spacer(1, 10),
    ]

    if not projecao.linhas:
        historia.append(Paragraph(
            'Não há histórico de peças usadas suficiente para projetar este período.', estilos['texto']
        ))
        documento.build(historia, onFirstPage=_rodape, onLaterPages=_rodape)
        return buffer.getvalue()

    resumo = Table(
        [
            ['Peças projetadas', 'Custo estimado', 'Tipos de peça', 'Histórico desde'],
            [str(projecao.total_pecas), moeda(projecao.custo_total), str(len(projecao.linhas)),
             dateformat.format(projecao.inicio_historico, 'M/Y')],
        ],
        colWidths=[largura / 4] * 4,
    )
    resumo.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, 0), 8),
        ('TEXTCOLOR', (0, 0), (-1, 0), TINTA_SECUNDARIA),
        ('FONTNAME', (0, 1), (-1, 1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 1), (-1, 1), 15),
        ('TOPPADDING', (0, 1), (-1, 1), 6),
        ('BOX', (0, 0), (-1, -1), 0.5, GRADE),
        ('LINEAFTER', (0, 0), (-2, -1), 0.5, GRADE),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 8),
    ]))

    historia += [
        resumo,
        Paragraph('Peças por mês', estilos['secao']),
        _grafico(projecao, largura),
        Paragraph('Quantidade projetada por peça', estilos['secao']),
        _tabela(projecao, largura, estilos),
        Spacer(1, 8),
        Paragraph(
            'Como é calculado: a quantidade de cada peça em um mês é a média do que foi usado no mesmo mês '
            'dos anos anteriores ("Base do cálculo" indica quantos anos entraram na média), arredondada para '
            'o inteiro mais próximo. '
            + ('Meses sem ano anterior no histórico usam a média mensal de todo o histórico ("Média geral"). '
               if projecao.usa_media_geral else '')
            + 'O mês atual não entra no histórico porque ainda não terminou. O custo estimado usa '
            'o preço de custo atual de cada peça.',
            estilos['nota'],
        ),
    ]
    documento.build(historia, onFirstPage=_rodape, onLaterPages=_rodape)
    return buffer.getvalue()
