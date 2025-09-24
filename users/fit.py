# users/fit.py
from django import forms


class FitForm(forms.Form):
    expression = forms.CharField(widget=forms.Textarea(attrs={'rows': 4, 'class': 'form-control'}))
    expression_clean = forms.CharField(widget=forms.HiddenInput(), required=False)
    data = forms.CharField(widget=forms.HiddenInput(), required=False)
    active_page = forms.IntegerField(widget=forms.HiddenInput(), initial=0)

    def clean(self):
        cleaned_data = super().clean()
        # Utiliser la version nettoyée si elle existe, sinon utiliser l'expression normale
        if cleaned_data.get('expression_clean'):
            cleaned_data['expression'] = cleaned_data['expression_clean']
        return cleaned_data
