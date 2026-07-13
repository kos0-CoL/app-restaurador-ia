from django import forms
from django.conf import settings


PRESET_CHOICES = [
    ('colorear', 'Colorear'),
    ('restaurar', 'Restaurar'),
    ('ambos', 'Ambos'),
]


class ImageUploadForm(forms.Form):
    imagen = forms.ImageField(
        label='Selecciona una imagen',
        help_text='Formatos aceptados: JPEG, PNG. Maximo 10 MB.',
    )
    preset = forms.ChoiceField(
        choices=PRESET_CHOICES,
        label='Tipo de mejora',
        widget=forms.RadioSelect,
    )

    def clean_imagen(self):
        imagen = self.cleaned_data['imagen']
        max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if imagen.size > max_size:
            raise forms.ValidationError(
                f'La imagen supera los {settings.MAX_UPLOAD_SIZE_MB} MB.'
            )
        if imagen.content_type not in settings.ALLOWED_IMAGE_TYPES:
            raise forms.ValidationError(
                'Formato no soportado. Use JPEG o PNG.'
            )
        return imagen
