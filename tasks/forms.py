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
                  'priority', 'start_date', 'due_date', 'planned_date', 'estimated_hours', 'actual_hours', 'comments']
        labels = {
            'comments': 'Instructions',
            'planned_date': 'Jour de la todo list',
            'start_date': 'Date de début',
            'assigned_to': 'Assigner à',
            'description': 'Description',
        }
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex. Analyse du site actuel',
                'autocomplete': 'off',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Objectifs, livrable attendu, points d’attention…',
            }),
            'project': forms.Select(attrs={'class': 'form-select'}),
            'assigned_to': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'due_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'planned_date': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date'}),
            'estimated_hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.5',
                'min': '0',
                'placeholder': 'Ex. 4',
            }),
            'actual_hours': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.5',
                'min': '0',
                'placeholder': 'Ex. 2.5',
            }),
            'comments': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Consigne, brief ou précision pour la personne assignée…',
            }),
        }
    
    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields['priority'].choices = list(Task.PRIORITY_LABELS.items())
        for name in ('start_date', 'due_date', 'planned_date'):
            if name in self.fields:
                self.fields[name].input_formats = ['%Y-%m-%d']
        self.fields['project'].queryset = Project.objects.exclude(status='cancelled').order_by('name')
        self.fields['project'].empty_label = 'Choisir un projet'
        self.fields['assigned_to'].queryset = Employee.objects.select_related('user').exclude(
            status='inactive'
        ).order_by('user__first_name', 'user__last_name')
        self.fields['assigned_to'].empty_label = 'Choisir un employé'
        self.fields['assigned_to'].label_from_instance = lambda employee: employee.full_name

        if not self.fields['project'].queryset.exists():
            self.fields['project'].required = False
            self.fields['project'].empty_label = 'Aucun projet disponible'
        if not self.fields['assigned_to'].queryset.exists():
            self.fields['assigned_to'].required = False
            self.fields['assigned_to'].empty_label = 'Aucun employé disponible'

        if user and not user.is_admin():
            for name in ('project', 'assigned_to', 'priority', 'start_date', 'due_date', 'planned_date', 'estimated_hours'):
                self.fields.pop(name, None)
            self.fields['comments'].label = 'Remarque'
            self.fields['comments'].widget.attrs['placeholder'] = 'Décrivez une difficulté, un blocage ou une précision…'

        for field_name, field in self.fields.items():
            if self.errors.get(field_name):
                css = field.widget.attrs.get('class', '')
                if 'is-invalid' not in css:
                    field.widget.attrs['class'] = f'{css} is-invalid'.strip()

        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            *[Field(name) for name in self.fields],
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary')
            )
        )

    def clean(self):
        cleaned = super().clean()
        if self.user and self.user.is_admin():
            if not cleaned.get('project'):
                self.add_error('project', 'Choisissez le projet associé.')
            if not cleaned.get('assigned_to'):
                self.add_error('assigned_to', "Choisissez l'employé responsable.")
        start = cleaned.get('start_date')
        due = cleaned.get('due_date')
        if start and due and due < start:
            self.add_error('due_date', 'La date limite ne peut pas précéder la date de début.')
        return cleaned


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
