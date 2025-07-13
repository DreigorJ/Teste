from django import forms
from .models import Produto, Categoria, Estoque, CompraRecorrente, Metrica

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column

class CustomUserCreationForm(UserCreationForm):
    nome = forms.CharField(max_length=150, label="Nome completo")
    email = forms.EmailField(max_length=254, help_text="Obrigatório. Informe um email válido.", label="Email")

    class Meta:
        model = User
        fields = ("username", "nome", "email", "password1", "password2")
        labels = {
            "username": "Login",
        }

    def save(self, commit=True):
        user = super().save(commit=False)
        # Salva nome completo em first_name (ou pode juntar em outro campo)
        user.first_name = self.cleaned_data["nome"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

class EstoqueForm(forms.ModelForm):
    usuarios = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),  # será definido no __init__
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Usuários com acesso"
    )

    class Meta:
        model = Estoque
        fields = ['nome', 'usuarios']

    def __init__(self, *args, **kwargs):
        usuario_atual = kwargs.pop('usuario_atual', None)
        super().__init__(*args, **kwargs)
        self.usuario_atual = usuario_atual
        if usuario_atual is not None:
            # Inclui apenas outros usuários na lista editável
            self.fields['usuarios'].queryset = User.objects.exclude(pk=usuario_atual.pk)
        else:
            self.fields['usuarios'].queryset = User.objects.all()

class ProdutoForm(forms.ModelForm):

    criar_compra_recorrente = forms.BooleanField(
        required=False, label="Adicionar Compra Recorrente"
    )
    cota_minima = forms.IntegerField(
        required=False, min_value=0, label="Cota Mínima",
        help_text="Quantidade mínima para gerar alerta (0 = sem alerta)"
    )
    checar_periodicamente = forms.BooleanField(
        required=False, initial=True, label="Checar Periodicamente",
        help_text="Verificar se está abaixo da cota mínima"
    )

    class Meta:
        model = Produto
        fields = ['nome', 'categoria', 'marca', 'dataValidade', 'preco', 'metrica', 'unidades']
        widgets = {
            'dataValidade': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        estoque = kwargs.pop('estoque', None)
        super().__init__(*args, **kwargs)

        if estoque:
            self.fields['categoria'].queryset = Categoria.objects.filter(estoque=estoque)
        else:
            self.fields['categoria'].queryset = Categoria.objects.none()
        self.fields['unidades'].min_value = 0
        self.fields['unidades'].help_text = "Quantidade inicial do produto no estoque."
        self.helper = FormHelper()
        self.helper.template_pack = "bootstrap5"
        self.helper.layout = Layout(
            'nome',
            'categoria',
            'marca',
            'dataValidade',
            'preco',
            Row(
                Column('unidades', css_class='col-md-6'),
                Column('metrica', css_class='col-md-6'),
                css_class='row'
            ),
        )
        self.fields['metrica'].queryset = Metrica.objects.all().order_by('-fixa', 'nome')

class CategoriaForm(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ['nome']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nome da categoria'}),
        }

