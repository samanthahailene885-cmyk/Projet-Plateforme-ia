from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, ButtonHolder, Submit
from .models import Attendance


class AttendanceForm(forms.ModelForm):
    """
    Formulaire de création/mise à jour de présence
    """
    class Meta:
        model = Attendance
        fields = ['employee', 'date', 'status', 'check_in_time', 'check_out_time', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'check_in_time': forms.TimeInput(attrs={'type': 'time'}),
            'check_out_time': forms.TimeInput(attrs={'type': 'time'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('employee'),
            Field('date'),
            Field('status'),
            Field('check_in_time'),
            Field('check_out_time'),
            Field('notes'),
            ButtonHolder(
                Submit('submit', 'Enregistrer', css_class='btn btn-primary')
            )
        )


class AttendanceSearchForm(forms.Form):
    """
    Formulaire de recherche de présences
    """
    date_from = forms.DateField(
        label='Du',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    date_to = forms.DateField(
        label='Au',
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    status = forms.ChoiceField(
        label='Statut',
        required=False,
        choices=[('', 'Tous')] + Attendance.STATUS_CHOICES
    )
    employee = forms.ModelChoiceField(
        queryset=None,
        required=False,
        empty_label='Tous les employés',
        label='Employé'
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from employees.models import Employee
        self.fields['employee'].queryset = Employee.objects.select_related('user').all()
        
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('date_from'),
            Field('date_to'),
            Field('status'),
            Field('employee'),
            ButtonHolder(
                Submit('submit', 'Filtrer', css_class='btn btn-primary')
            )
        )
