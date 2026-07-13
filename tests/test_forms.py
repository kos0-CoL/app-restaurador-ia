import io
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from procesador.forms import ImageUploadForm


def crear_imagen_valida(nombre='test.jpg', formato='JPEG', ancho=100, alto=100):
    """Crea una imagen valida para tests usando Pillow."""
    img = Image.new('RGB', (ancho, alto), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format=formato)
    buffer.seek(0)
    content_type = 'image/jpeg' if formato == 'JPEG' else 'image/png'
    return SimpleUploadedFile(nombre, buffer.read(), content_type=content_type)


class ImageUploadFormTest(TestCase):

    def test_form_valido_con_jpeg(self):
        form = ImageUploadForm(
            data={'preset': 'colorear'},
            files={'imagen': crear_imagen_valida()}
        )
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_valido_con_png(self):
        imagen = crear_imagen_valida(nombre='test.png', formato='PNG')
        form = ImageUploadForm(data={'preset': 'restaurar'}, files={'imagen': imagen})
        self.assertTrue(form.is_valid(), form.errors)

    def test_form_rechaza_formato_no_soportado(self):
        imagen = crear_imagen_valida(nombre='test.bmp', formato='BMP')
        form = ImageUploadForm(data={'preset': 'colorear'}, files={'imagen': imagen})
        self.assertFalse(form.is_valid())
        self.assertIn('imagen', form.errors)

    def test_form_rechaza_preset_invalido(self):
        form = ImageUploadForm(
            data={'preset': 'invalido'},
            files={'imagen': crear_imagen_valida()}
        )
        self.assertFalse(form.is_valid())
        self.assertIn('preset', form.errors)

    def test_form_rechaza_sin_imagen(self):
        form = ImageUploadForm(data={'preset': 'colorear'})
        self.assertFalse(form.is_valid())
        self.assertIn('imagen', form.errors)
