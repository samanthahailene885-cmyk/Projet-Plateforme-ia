from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, ButtonHolder, Submit
from .models import Employee
from authentication.models import User


class EmployeeForm(forms.ModelForm):
    """
    Formulaire de création/mise à jour d'employé
    """
    first_name = forms.CharField(label='Prénom', required=True)
    last_name = forms.CharField(label='Nom', required=True)
    email = forms.EmailField(label='Email', required=True)
    phone = forms.CharField(label='Téléphone', required=False)
    username = forms.CharField(label='Nom d\'utilisateur', required=True)
    password = forms.CharField(
        label='Mot de passe',
        widget=forms.PasswordInput(),
        required=False
    )
    
    class Meta:
        model = Employee
        fields = ['position', 'hire_date', 'status', 'department', 'salary']
        widgets = {
            'hire_date': forms.DateInput(attrs={'type': 'date'}),
            'salary': forms.NumberInput(attrs={'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('username'),
            Field('first_name'),
            Field('last_name'),
            Field('email'),
            Field('phone'),
            Field('position'),
            Field('hire_date'),
            Field('status'),
            Field('department'),
            Field('salary'),
            Field('password'),
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary')
            )
        )
        
        # Si c'est une mise à jour, le mot de passe n'est pas requis
        if self.instance and self.instance.pk:
            self.fields['password'].required = False
            self.fields['username'].widget.attrs['readonly'] = True
    
    def save(self, commit=True):
        employee = super().save(commit=False)
        
        # Créer ou mettre à jour l'utilisateur associé
        user_data = {
            'first_name': self.cleaned_data['first_name'],
            'last_name': self.cleaned_data['last_name'],
            'email': self.cleaned_data['email'],
            'phone': self.cleaned_data['phone'],
        }
        
        if self.instance and self.instance.pk:
            # Mise à jour
            user = self.instance.user
            for key, value in user_data.items():
                setattr(user, key, value)
            
            password = self.cleaned_data.get('password')
            if password:
                user.set_password(password)
            user.save()
        else:
            # Création
            user = User.objects.create_user(
                username=self.cleaned_data['username'],
                email=self.cleaned_data['email'],
                password=self.cleaned_data['password'] or User.objects.make_random_password(),
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                phone=self.cleaned_data['phone'],
                role='employee'
            )
            employee.user = user
        
        if commit:
            employee.save()
        return employee


class EmployeeSearchForm(forms.Form):
    """
    Formulaire de recherche d'employés
    """
    search = forms.CharField(
        label='Rechercher',
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Nom, email, poste...'})
    )
    position = forms.ChoiceField(
        label='Poste',
        required=False,
        choices=[('', 'Tous')] + Employee.POSITION_CHOICES
    )
    status = forms.ChoiceField(
        label='Statut',
        required=False,
        choices=[('', 'Tous')] + Employee.STATUS_CHOICES
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('search'),
            Field('position'),
            Field('status'),
            ButtonHolder(
                Submit('submit', 'Filtrer', css_class='btn btn-primary')
            )
        )
