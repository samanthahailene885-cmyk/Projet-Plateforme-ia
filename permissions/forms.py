from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, ButtonHolder, Submit
from .models import PermissionRequest


class PermissionRequestForm(forms.ModelForm):
    """
    Formulaire de demande de permission
    """
    class Meta:
        model = PermissionRequest
        fields = ['type', 'start_date', 'end_date', 'reason']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
            'reason': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('type'),
            Field('start_date'),
            Field('end_date'),
            Field('reason'),
            ButtonHolder(
                Submit('submit', 'Envoyer la demande', css_class='btn btn-primary')
            )
        )
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if end_date < start_date:
                raise forms.ValidationError('La date de fin doit être après la date de début.')
            
            from django.utils import timezone
            delta = start_date - timezone.now().date()
            if delta.days < 3:
                raise forms.ValidationError('La demande doit être faite au moins 3 jours avant la date de début.')
        
        return cleaned_data


class PermissionApprovalForm(forms.ModelForm):
    """
    Formulaire d'approbation/refus de permission (pour l'admin)
    """
    class Meta:
        model = PermissionRequest
        fields = ['status', 'admin_comment']
        widgets = {
            'admin_comment': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('status'),
            Field('admin_comment'),
            ButtonHolder(
                Submit('submit', 'Enregistrer la décision', css_class='btn btn-primary')
            )
        )


class PermissionSearchForm(forms.Form):
    """
    Formulaire de recherche de demandes de permission
    """
    status = forms.ChoiceField(
        label='Statut',
        required=False,
        choices=[('', 'Tous')] + PermissionRequest.STATUS_CHOICES
    )
    type = forms.ChoiceField(
        label='Type',
        required=False,
        choices=[('', 'Tous')] + PermissionRequest.TYPE_CHOICES
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('status'),
            Field('type'),
            ButtonHolder(
                Submit('submit', 'Filtrer', css_class='btn btn-primary')
            )
        )
