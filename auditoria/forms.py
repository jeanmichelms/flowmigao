import datetime

from django import forms
from django.utils import timezone

from .models import RegistroAuditoria
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


class FiltroAuditoriaForm(forms.Form):
    tipo = forms.ChoiceField(label='Tipo de registro', required=False)
    acao = forms.ChoiceField(
        label='Ação', required=False, choices=[('', 'Todas')] + RegistroAuditoria.Acao.choices
    )
    usuario = forms.ChoiceField(label='Usuário', required=False)
    data_inicio = forms.DateField(label='De', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    data_fim = forms.DateField(label='Até', required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    busca = forms.CharField(
        label='Registro contém', required=False, max_length=100,
        help_text='Parte do nome, placa, CPF, descrição...',
    )
    # Usado pelo link "Ver histórico" das telas de detalhe (junto com o tipo)
    objeto = forms.CharField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo'].choices = opcoes_de_tipo()
        self.fields['usuario'].choices = opcoes_de_usuario()

    def clean(self):
        dados = super().clean()
        inicio, fim = dados.get('data_inicio'), dados.get('data_fim')
        if inicio and fim and inicio > fim:
            self.add_error('data_fim', 'A data final deve ser igual ou posterior à data inicial.')
        return dados

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
        # Faixa de data/hora em vez de __date: no MySQL, __date depende das tabelas de fuso horário,
        # que normalmente não estão carregadas, e o filtro não encontraria nada
        if dados['data_inicio']:
            registros = registros.filter(data_hora__gte=inicio_do_dia(dados['data_inicio']))
        if dados['data_fim']:
            registros = registros.filter(data_hora__lt=inicio_do_dia(dados['data_fim'] + datetime.timedelta(days=1)))
        if dados['busca']:
            registros = registros.filter(objeto_descricao__icontains=dados['busca'])
        return registros
