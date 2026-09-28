from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm, SetPasswordMixin, UserCreationForm

User = get_user_model()

ROTULOS = {
    'username': 'Usuário',
    'first_name': 'Nome',
    'email': 'E-mail',
    'is_active': 'Ativo',
}
WIDGETS = {
    'username': forms.TextInput(attrs={'autocomplete': 'off'}),
    'first_name': forms.TextInput(attrs={'autocomplete': 'off'}),
    'email': forms.EmailInput(attrs={'autocomplete': 'off'}),
}
AJUDA_USUARIO = 'Nome usado para entrar no sistema. Letras, números e @ . + - _ (até 150 caracteres).'


class LoginForm(AuthenticationForm):
    error_messages = {
        'invalid_login': 'Usuário ou senha incorretos. Verifique e tente novamente.',
        'inactive': 'Este usuário está desativado.',
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Usuário'
        self.fields['password'].label = 'Senha'


class AdministradorMixin(forms.Form):
    """Campo "Administrador" que liga/desliga is_superuser e is_staff juntos."""

    administrador = forms.BooleanField(
        label='Administrador',
        required=False,
        help_text='Administradores podem cadastrar, editar e excluir usuários.',
    )

    def aplicar_perfil(self, usuario):
        usuario.is_superuser = usuario.is_staff = self.cleaned_data['administrador']


class UsuarioCriarForm(AdministradorMixin, UserCreationForm):
    password1, password2 = SetPasswordMixin.create_password_fields(label1='Senha', label2='Confirmação da senha')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ['username', 'first_name', 'email']
        labels = ROTULOS
        widgets = WIDGETS
        help_texts = {'username': AJUDA_USUARIO}

    field_order = ['username', 'first_name', 'email', 'administrador', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password2'].help_text = 'Digite a mesma senha novamente.'

    def save(self, commit=True):
        usuario = super().save(commit=False)
        self.aplicar_perfil(usuario)
        if commit:
            usuario.save()
        return usuario


class UsuarioEditarForm(AdministradorMixin, SetPasswordMixin, forms.ModelForm):
    """Edição de usuário. A senha só muda se os campos de nova senha forem preenchidos."""

    password1, password2 = SetPasswordMixin.create_password_fields(
        label1='Nova senha', label2='Confirmação da nova senha'
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'email', 'is_active']
        labels = ROTULOS
        widgets = WIDGETS
        help_texts = {
            'username': AJUDA_USUARIO,
            'is_active': 'Usuários desativados não conseguem entrar no sistema.',
        }

    field_order = ['username', 'first_name', 'email', 'administrador', 'is_active', 'password1', 'password2']

    def __init__(self, *args, editando_a_si_mesmo=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['administrador'].initial = self.instance.is_superuser
        self.fields['password1'].required = self.fields['password2'].required = False
        self.fields['password1'].help_text = 'Deixe em branco para manter a senha atual.'
        self.fields['password2'].help_text = 'Digite a mesma senha novamente.'
        if editando_a_si_mesmo:
            # Evita que o administrador perca o próprio acesso à manutenção de usuários
            for nome in ('administrador', 'is_active'):
                self.fields[nome].disabled = True
            self.fields['administrador'].help_text = 'Você não pode remover o seu próprio perfil de administrador.'
            self.fields['is_active'].help_text = 'Você não pode desativar o seu próprio usuário.'

    def clean(self):
        if self.cleaned_data.get('password1') and not self.cleaned_data.get('password2'):
            self.add_error('password2', 'Confirme a nova senha.')
        self.validate_passwords()
        return super().clean()

    def _post_clean(self):
        super()._post_clean()
        self.validate_password_for_user(self.instance)

    @property
    def senha_alterada(self):
        return bool(self.cleaned_data.get('password1'))

    def save(self, commit=True):
        usuario = super().save(commit=False)
        self.aplicar_perfil(usuario)
        if self.senha_alterada:
            usuario.set_password(self.cleaned_data['password1'])
        if commit:
            usuario.save()
        return usuario


class AlterarSenhaForm(PasswordChangeForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['old_password'].label = 'Senha atual'
        self.fields['new_password1'].label = 'Nova senha'
        self.fields['new_password2'].label = 'Confirmação da nova senha'
        self.fields['new_password2'].help_text = 'Digite a mesma senha novamente.'
