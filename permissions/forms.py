from django import forms
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Field, ButtonHolder, Submit
from .models import PermissionRequest

ALLOWED_ATTACHMENT_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}
MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024


class PermissionRequestForm(forms.ModelForm):
    other_reason = forms.CharField(
        label='Autre motif (précisez)',
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'perm-input',
            'placeholder': 'Précisez votre motif (si autre)',
        })
    )

    class Meta:
        model = PermissionRequest
        fields = ['type', 'start_date', 'end_date', 'reason_choice', 'description', 'attachment']
        widgets = {
            'type': forms.Select(attrs={'class': 'perm-input'}),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'perm-input',
                'placeholder': 'Sélectionner une date',
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'perm-input',
                'placeholder': 'Sélectionner une date',
            }),
            'reason_choice': forms.Select(attrs={'class': 'perm-input'}),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'perm-input perm-textarea',
                'placeholder': 'Expliquez brièvement votre demande...',
            }),
            'attachment': forms.FileInput(attrs={
                'class': 'perm-file-input',
                'accept': '.pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png',
            }),
        }
        labels = {
            'type': 'Type de demande',
            'start_date': 'Date de début',
            'end_date': 'Date de fin',
            'reason_choice': 'Motif',
            'description': 'Description',
            'attachment': 'Justificatif',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['reason_choice'].choices = [('', 'Sélectionner un motif')] + list(
            PermissionRequest.REASON_CHOICES
        )
        self.fields['reason_choice'].required = True
        self.fields['description'].required = False
        self.fields['attachment'].required = False

    def clean_attachment(self):
        file = self.cleaned_data.get('attachment')
        if not file:
            return file
        name = (file.name or '').lower()
        ext = name[name.rfind('.'):] if '.' in name else ''
        if ext not in ALLOWED_ATTACHMENT_EXTENSIONS:
            raise forms.ValidationError('Le justificatif doit être un fichier PDF, JPG ou PNG.')
        if file.size and file.size > MAX_ATTACHMENT_SIZE:
            raise forms.ValidationError('Le justificatif ne doit pas dépasser 5 Mo.')
        return file

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        reason_choice = cleaned_data.get('reason_choice')
        other_reason = (cleaned_data.get('other_reason') or '').strip()

        if start_date and end_date:
            if end_date < start_date:
                raise forms.ValidationError('La date de fin doit être après la date de début.')

            from django.utils import timezone
            delta = start_date - timezone.now().date()
            if delta.days < 3:
                raise forms.ValidationError(
                    'Votre demande doit être soumise au moins 3 jours avant la date de début.'
                )

        if reason_choice == 'other' and not other_reason:
            self.add_error('other_reason', 'Précisez votre motif.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        reason_choice = self.cleaned_data.get('reason_choice')
        other_reason = (self.cleaned_data.get('other_reason') or '').strip()
        if reason_choice == 'other':
            instance.reason = other_reason
        else:
            instance.reason = instance.get_reason_choice_display()
        if commit:
            instance.save()
        return instance


class PermissionApprovalForm(forms.ModelForm):
    class Meta:
        model = PermissionRequest
        fields = ['status', 'admin_comment']
        widgets = {
            'admin_comment': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].choices = [
            ('approved', 'Approuvée'),
            ('rejected', 'Refusée'),
        ]
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Field('status'),
            Field('admin_comment'),
            ButtonHolder(
                Submit('submit', 'Enregistrer la décision', css_class='btn btn-primary')
            )
        )


class PermissionSearchForm(forms.Form):
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
