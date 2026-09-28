import datetime

from django import forms
from django.utils import timezone

from .models import RegistroAuditoria, TentativaLogin
from .sinais import modelos_monitorados

SISTEMA = '__sistema__'


def opcoes_de_tipo():
    opcoes = [(m._meta.label_lower, str(m._meta.verbose_name).capitalize()) for m in modelos_monitorados()]
    return [('', 'Todos')] + sorted(opcoes, key=lambda opcao: opcao[1])


def opcoes_de_usuario():
    # Nomes gravados nos registros: inclui usuários que já foram excluídos
    nomes = (
        RegistroAuditoria.objects.exclude(usuario_nome='')
        .order_by('usuario_nome').values_list('usuario_nome', flat=True).distinct()
    )
    return [('', 'Todos'), (SISTEMA, 'Sistema')] + [(nome, nome) for nome in nomes]


def inicio_do_dia(data):
    return timezone.make_aware(datetime.datetime.combine(data, datetime.time.min))


class FiltroPeriodoForm(forms.Form):
    data_inicio = forms.DateField(label='De', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    data_fim = forms.DateField(label='Até', required=False, widget=forms.DateInput(attrs={'type': 'date'}))

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get('data_inicio'), dados.get('data_fim')
        if inicio and fim and inicio > fim:
            self.add_error('data_fim', 'A data final deve ser igual ou posterior à data inicial.')
        return dados

    def filtrar_periodo(self, itens):
        # Faixa de data/hora em vez de __date: no MySQL, __date depende das tabelas de fuso horário,
        # que normalmente não estão carregadas, e o filtro não encontraria nada
        if self.cleaned_data['data_inicio']:
            itens = itens.filter(data_hora__gte=inicio_do_dia(self.cleaned_data['data_inicio']))
        if self.cleaned_data['data_fim']:
            itens = itens.filter(data_hora__lt=inicio_do_dia(self.cleaned_data['data_fim'] + datetime.timedelta(days=1)))
        return itens


class FiltroAuditoriaForm(FiltroPeriodoForm):
    tipo = forms.ChoiceField(label='Tipo de registro', required=False)
    acao = forms.ChoiceField(
        label='Ação', required=False, choices=[('', 'Todas')] + RegistroAuditoria.Acao.choices
    )
    usuario = forms.ChoiceField(label='Usuário', required=False)
    busca = forms.CharField(
        label='Registro contém', required=False, max_length=100,
        help_text='Parte do nome, placa, CPF, descrição...',
    )
    # Usado pelo link "Ver histórico" das telas de detalhe (junto com o tipo)
    objeto = forms.CharField(required=False, widget=forms.HiddenInput())

    field_order = ['tipo', 'acao', 'usuario', 'data_inicio', 'data_fim', 'busca']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo'].choices = opcoes_de_tipo()
        self.fields['usuario'].choices = opcoes_de_usuario()

    def filtrar(self, registros):
        dados = self.cleaned_data
        if dados['tipo']:
            app_label, modelo = dados['tipo'].split('.')
            registros = registros.filter(tipo__app_label=app_label, tipo__model=modelo)
            if dados['objeto']:
                registros = registros.filter(objeto_id=dados['objeto'])
        if dados['acao']:
            registros = registros.filter(acao=dados['acao'])
        if dados['usuario'] == SISTEMA:
            registros = registros.filter(usuario_nome='')
        elif dados['usuario']:
            registros = registros.filter(usuario_nome=dados['usuario'])
        if dados['busca']:
            registros = registros.filter(objeto_descricao__icontains=dados['busca'])
        return self.filtrar_periodo(registros)


class FiltroLoginForm(FiltroPeriodoForm):
    usuario = forms.CharField(label='Usuário informado contém', required=False, max_length=150)
    motivo = forms.ChoiceField(
        label='Motivo', required=False, choices=[('', 'Todos')] + TentativaLogin.Motivo.choices
    )
    ip = forms.GenericIPAddressField(label='IP', required=False)

    field_order = ['usuario', 'motivo', 'ip', 'data_inicio', 'data_fim']

    def filtrar(self, tentativas):
        dados = self.cleaned_data
        if dados['usuario']:
            tentativas = tentativas.filter(usuario_informado__icontains=dados['usuario'])
        if dados['motivo']:
            tentativas = tentativas.filter(motivo=dados['motivo'])
        if dados['ip']:
            tentativas = tentativas.filter(ip=dados['ip'])
        return self.filtrar_periodo(tentativas)
