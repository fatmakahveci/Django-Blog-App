from django import forms

from .models import Comment


class CommentForm(forms.ModelForm):
    website = forms.CharField(required=False, label='Leave this field empty')

    class Meta:
        model = Comment
        fields = ['name', 'body']
        labels = {'name': 'Your name', 'body': 'Your comment'}
        widgets = {
            'name': forms.TextInput(attrs={'autocomplete': 'name', 'placeholder': 'What should we call you?'}),
            'body': forms.Textarea(attrs={'rows': 4, 'placeholder': 'What do you think? (At least 10 characters)'}),
        }

    def clean_website(self):
        if self.cleaned_data.get('website'):
            raise forms.ValidationError('We could not verify your submission.')
        return ''
