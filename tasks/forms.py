from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, ButtonHolder, Submit
from .models import Task
from projects.models import Project
from employees.models import Employee


class TaskForm(forms.ModelForm):
    """
    Formulaire de création/mise à jour de tâche
    """
    class Meta:
        model = Task
        fields = ['title', 'description', 'project', 'assigned_to', 'status',
                  'priority', 'due_date', 'estimated_hours', 'actual_hours', 'comments']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Entrez le titre de la tâche'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Décrivez la tâche'}),
            'project': forms.Select(attrs={'class': 'form-select'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'estimated_hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'placeholder': '0'}),
            'actual_hours': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5', 'placeholder': '0'}),
            'comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ajoutez des commentaires'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Rendre le champ project optionnel s'il n'y a pas de projets
        if not self.fields['project'].queryset.exists():
            self.fields['project'].required = False
            self.fields['project'].empty_label = "Aucun projet disponible"
        # Rendre le champ assigned_to optionnel s'il n'y a pas d'employés
        if not self.fields['assigned_to'].queryset.exists():
            self.fields['assigned_to'].required = False
            self.fields['assigned_to'].empty_label = "Aucun employé disponible"
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('title'),
            Field('description'),
            Field('project'),
            Field('assigned_to'),
            Field('status'),
            Field('priority'),
            Field('due_date'),
            Field('estimated_hours'),
            Field('actual_hours'),
            Field('comments'),
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary')
            )
        )


class TaskSearchForm(forms.Form):
    """
    Formulaire de recherche de tâches
    """
    search = forms.CharField(
        label='Rechercher',
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'Titre, description...', 'class': 'form-control'})
    )
    project = forms.ModelChoiceField(
        queryset=Project.objects.all(),
        required=False,
        empty_label='Tous les projets',
        label='Projet',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    status = forms.ChoiceField(
        label='Statut',
        required=False,
        choices=[('', 'Tous')] + Task.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    priority = forms.ChoiceField(
        label='Priorité',
        required=False,
        choices=[('', 'Toutes')] + Task.PRIORITY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    assigned_to = forms.ModelChoiceField(
        queryset=Employee.objects.all(),
        required=False,
        empty_label='Tous les employés',
        label='Assigné à',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('search'),
            Field('project'),
            Field('status'),
            Field('priority'),
            Field('assigned_to'),
            ButtonHolder(
                Submit('submit', 'Filtrer', css_class='btn btn-primary')
            )
        )
