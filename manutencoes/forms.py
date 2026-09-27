from calendar import monthrange
from datetime import date

from django import forms
from .models import Manutencao  
from .models import Peca, PecaUsada


HTML5_DATE_FORMAT = '%Y-%m-%d'


def add_months(base_date, months):
    month = base_date.month - 1 + months
    year = base_date.year + month // 12
    month = month % 12 + 1
    day = min(base_date.day, monthrange(year, month)[1])
    return date(year, month, day)

class PecaForm(forms.ModelForm):
    class Meta:
        model = Peca
        fields = ['nome', 'marca', 'preco_custo']
        labels = {
            'nome': 'Nome',
            'marca': 'Marca',
            'preco_custo': 'Preço de custo (R$)',
        }
        widgets = {
            'preco_custo': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
        }

    def clean_preco_custo(self):
        preco = self.cleaned_data['preco_custo']
        if preco < 0:
            raise forms.ValidationError('O preço de custo não pode ser negativo.')
        return preco


class PecaUsadaForm(forms.ModelForm):
    class Meta:
        model = PecaUsada
        fields = ['peca', 'quantidade']
        widgets = {
            'peca': forms.Select(attrs={'class': 'form-select'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
        }

    def clean_quantidade(self):
        quantidade = self.cleaned_data['quantidade']
        if quantidade < 1:
            raise forms.ValidationError('A quantidade deve ser pelo menos 1.')
        return quantidade

class ManutencaoForm(forms.ModelForm):
    class Meta:
        model = Manutencao
        fields = [
            'veiculo',
            'tipo',
            'descricao',
            'data_manutencao',
            'data_proxima_manutencao',
            'quilometragem',
            'valor',
            'observacoes',
        ]
        labels = {
            'veiculo': 'Veículo',
            'tipo': 'Tipo de manutenção',
            'descricao': 'Descrição',
            'data_manutencao': 'Data da manutenção',
            'data_proxima_manutencao': 'Data prevista da próxima manutenção',
            'observacoes': 'Observações',
        }
        widgets = {
            'veiculo': forms.HiddenInput(),
            'descricao': forms.Textarea(attrs={'rows': 5, 'style': 'width: 100%; box-sizing: border-box;'}),
            'data_manutencao': forms.DateInput(format=HTML5_DATE_FORMAT, attrs={'type': 'date'}),
            'data_proxima_manutencao': forms.DateInput(format=HTML5_DATE_FORMAT, attrs={'type': 'date'}),
            'observacoes': forms.Textarea(attrs={'rows': 5, 'style': 'width: 100%; box-sizing: border-box;'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields['veiculo'].required = True
        self.fields['data_manutencao'].input_formats = [HTML5_DATE_FORMAT]
        self.fields['data_proxima_manutencao'].input_formats = [HTML5_DATE_FORMAT]

        if not self.is_bound and not getattr(self.instance, 'pk', None):
            hoje = date.today()
            self.initial.setdefault('data_manutencao', hoje.strftime(HTML5_DATE_FORMAT))
            self.initial.setdefault('data_proxima_manutencao', add_months(hoje, 6).strftime(HTML5_DATE_FORMAT))
