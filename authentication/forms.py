from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, ButtonHolder, Submit, Row, Column, HTML

User = get_user_model()


class CustomUserCreationForm(UserCreationForm):
    """
    Formulaire d'inscription personnalisé
    """
    email = forms.EmailField(required=True, label='Adresse e-mail')
    first_name = forms.CharField(required=True, label='Prénom')
    last_name = forms.CharField(required=True, label='Nom')
    
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'username', 'password1', 'password2')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'placeholder': 'Choisissez un identifiant'})
        self.fields['email'].widget.attrs.update({'placeholder': 'exemple@email.com'})
        self.fields['first_name'].widget.attrs.update({'placeholder': 'Votre prénom'})
        self.fields['last_name'].widget.attrs.update({'placeholder': 'Votre nom'})
        self.fields['password1'].help_text = 'Au moins 8 caractères, évitez un mot de passe trop simple.'
        self.fields['password2'].label = 'Confirmer le mot de passe'

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            HTML('<p class="text-uppercase text-muted small fw-semibold mb-2">Informations personnelles</p>'),
            Row(
                Column('first_name', css_class='col-md-6 mb-3'),
                Column('last_name', css_class='col-md-6 mb-3'),
            ),
            Field('email', css_class='mb-3'),
            Field('username', css_class='mb-3'),
            HTML('<p class="text-uppercase text-muted small fw-semibold mb-2 mt-2">Sécurité du compte</p>'),
            Field('password1', css_class='mb-3'),
            Field('password2', css_class='mb-3'),
            ButtonHolder(
                Submit('submit', 'Créer mon compte', css_class='btn btn-primary w-100 mt-2')
            )
        )
    
    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.role = 'employee'
        if commit:
            user.save()
        return user


class CustomAuthenticationForm(AuthenticationForm):
    """
    Formulaire de connexion personnalisé
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = 'Adresse e-mail'
        self.fields['username'].widget.attrs.update({
            'placeholder': 'Adresse e-mail',
            'autocomplete': 'username',
            'autocapitalize': 'none',
            'spellcheck': 'false',
            'autofocus': True,
            'class': 'rac-input',
        })
        self.fields['password'].widget.attrs.update({
            'placeholder': 'Mot de passe',
            'autocomplete': 'current-password',
            'class': 'rac-input',
        })

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Field('username', css_class='mb-3'),
            Field('password', css_class='mb-3'),
            ButtonHolder(
                Submit('submit', 'Se connecter', css_class='btn btn-primary w-100 mt-2')
            )
        )


class UserProfileForm(forms.ModelForm):
    """
    Formulaire de mise à jour du profil utilisateur
    """
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'phone', 'photo', 'birth_date', 'gender', 'address', 'bio')
        labels = {
            'first_name': 'Prénom',
            'last_name': 'Nom',
            'email': 'Adresse e-mail',
            'phone': 'Téléphone',
            'photo': 'Photo de profil',
            'birth_date': 'Date de naissance',
            'gender': 'Genre',
            'address': 'Adresse',
            'bio': 'Présentation',
        }
        widgets = {
            'first_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Votre prénom',
                'autocomplete': 'given-name',
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Votre nom',
                'autocomplete': 'family-name',
            }),
            'email': forms.EmailInput(attrs={
                'class': 'form-control',
                'placeholder': 'prenom@entreprise.com',
                'autocomplete': 'email',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+223 00 00 00 00',
                'autocomplete': 'tel',
            }),
            'photo': forms.FileInput(attrs={
                'class': 'photo-input',
                'accept': 'image/*',
            }),
            'birth_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date',
                'autocomplete': 'bday',
            }),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Ville, quartier ou adresse professionnelle',
                'autocomplete': 'street-address',
            }),
            'bio': forms.Textarea(attrs={
                'class': 'form-control field-bio',
                'rows': 4,
                'placeholder': 'Quelques lignes sur votre rôle et vos spécialités.',
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['gender'].choices = [('', 'Non renseigné')] + [
            choice for choice in self.fields['gender'].choices if choice[0]
        ]
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column('first_name', css_class='col-md-6 mb-3'),
                Column('last_name', css_class='col-md-6 mb-3'),
            ),
            Field('email', css_class='mb-3'),
            Field('phone', css_class='mb-3'),
            Field('photo', css_class='mb-3'),
            Row(
                Column('birth_date', css_class='col-md-6 mb-3'),
                Column('gender', css_class='col-md-6 mb-3'),
            ),
            Field('address', css_class='mb-3'),
            Field('bio', css_class='mb-3'),
            ButtonHolder(
                Submit('submit', 'Mettre à jour', css_class='btn btn-primary')
            )
        )
