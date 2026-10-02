from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, ButtonHolder, Submit
from .models import Project
from employees.models import Employee


class ProjectForm(forms.ModelForm):
    """
    Formulaire de création/mise à jour de projet
    """
    assigned_employees = forms.ModelMultipleChoiceField(
        queryset=Employee.objects.select_related('user').all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label='Employés assignés'
    )
    
    class Meta:
        model = Project
        fields = ['name', 'description', 'client', 'start_date', 'end_date', 
                  'status', 'priority', 'progress', 'budget', 'assigned_employees']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'budget': forms.NumberInput(attrs={'step': '0.01'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('name'),
            Field('client'),
            Field('description'),
            Field('start_date'),
            Field('end_date'),
            Field('status'),
            Field('priority'),
            Field('progress'),
            Field('budget'),
            Field('assigned_employees'),
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary')
            )
        )


class ProjectSearchForm(forms.Form):
    """
    Formulaire de recherche de projets
    """
    search = forms.CharField(
        label='Rechercher',
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Nom, client...'})
    )
    status = forms.ChoiceField(
        label='Statut',
        required=False,
        choices=[('', 'Tous'), ('late', 'En retard')] + list(Project.STATUS_CHOICES)
    )
    priority = forms.ChoiceField(
        label='Priorité',
        required=False,
        choices=[('', 'Toutes')] + Project.PRIORITY_CHOICES
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('search'),
            Field('status'),
            Field('priority'),
            ButtonHolder(
                Submit('submit', 'Filtrer', css_class='btn btn-primary')
            )
        )
