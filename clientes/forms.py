from django import forms
from .models import Cliente

class ClienteForm(forms.ModelForm):
    class Meta:
        model = Cliente
        fields = ['nome', 'cpf', 'email', 'telefone', 'cep', 'endereco', 'numero', 'bairro', 'cidade', 'estado']
        # Rótulos com acentuação correta: é o que o leitor de tela lê em voz alta
        labels = {
            'nome': 'Nome',
            'cpf': 'CPF',
            'email': 'E-mail',
            'telefone': 'Telefone',
            'cep': 'CEP',
            'endereco': 'Endereço (rua/avenida)',
            'numero': 'Número',
            'bairro': 'Bairro',
            'cidade': 'Cidade',
            'estado': 'Estado (UF)',
        }
        # autocomplete permite ao navegador preencher dados pessoais (WCAG 1.3.5)
        # inputmode abre o teclado numérico no celular
        widgets = {
            'nome': forms.TextInput(attrs={'autocomplete': 'name'}),
            'cpf': forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'off'}),
            'email': forms.EmailInput(attrs={'autocomplete': 'email'}),
            'telefone': forms.TextInput(attrs={'type': 'tel', 'autocomplete': 'tel'}),
            'cep': forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'postal-code'}),
            'endereco': forms.TextInput(attrs={'autocomplete': 'address-line1'}),
            'numero': forms.TextInput(attrs={'autocomplete': 'address-line2'}),
            'bairro': forms.TextInput(attrs={'autocomplete': 'address-level3'}),
            'cidade': forms.TextInput(attrs={'autocomplete': 'address-level2'}),
            'estado': forms.TextInput(attrs={'autocomplete': 'address-level1'}),
        }
        help_texts = {
            'cep': 'Ao sair do campo, o endereço é preenchido automaticamente.',
        }
