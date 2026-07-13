import io
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from procesador.models import SesionProcesamiento


def crear_imagen_valida(nombre='test.jpg', formato='JPEG'):
    img = Image.new('RGB', (100, 100), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format=formato)
    buffer.seek(0)
    content_type = 'image/jpeg' if formato == 'JPEG' else 'image/png'
    return SimpleUploadedFile(nombre, buffer.read(), content_type=content_type)


class InicioViewTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_inicio_retrieve_ok(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Restaurador IA')
        self.assertContains(response, 'Colorear')
        self.assertContains(response, 'Restaurar')
        self.assertContains(response, 'Ambos')

    def test_inicio_muestra_formulario(self):
        response = self.client.get('/')
        self.assertContains(response, 'input type="file"')
        self.assertContains(response, 'input type="radio"')


class ProcesarViewTest(TestCase):

    def setUp(self):
        self.client = Client()

    @override_settings(HUGGINGFACE_API_TOKEN='test-token')
    @patch('procesador.views.guardar_imagen')
    @patch('procesador.views.SERVICIOS')
    def test_procesar_post_exitoso(self, mock_servicios, mock_guardar):
        mock_resultado = MagicMock()
        mock_resultado.exito = True
        mock_resultado.datos = b'imagen_procesada'
        mock_colorear_mock = MagicMock(return_value=mock_resultado)
        mock_servicios.get.return_value = mock_colorear_mock
        mock_guardar.return_value = 'test_resultado.jpg'

        imagen = crear_imagen_valida()
        response = self.client.post('/procesar/', {
            'imagen': imagen,
            'preset': 'colorear',
        }, follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(SesionProcesamiento.objects.count(), 1)
        sesion = SesionProcesamiento.objects.first()
        self.assertEqual(sesion.estado, 'completado')
        self.assertEqual(sesion.preset, 'colorear')

    def test_procesar_get_redirect(self):
        response = self.client.get('/procesar/')
        self.assertEqual(response.status_code, 302)

    def test_procesar_post_sin_imagen(self):
        response = self.client.post('/procesar/', {
            'preset': 'colorear',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(SesionProcesamiento.objects.count(), 0)

    @override_settings(HUGGINGFACE_API_TOKEN='test-token')
    @patch('procesador.views.guardar_imagen')
    @patch('procesador.views.SERVICIOS')
    def test_procesar_post_error_api(self, mock_servicios, mock_guardar):
        mock_guardar.return_value = 'test_orig.jpg'
        mock_resultado = MagicMock()
        mock_resultado.exito = False
        mock_resultado.es_reintento = False
        mock_resultado.error = 'Token invalido'
        mock_colorear_mock = MagicMock(return_value=mock_resultado)
        mock_servicios.get.return_value = mock_colorear_mock

        imagen = crear_imagen_valida()
        response = self.client.post('/procesar/', {
            'imagen': imagen,
            'preset': 'colorear',
        }, follow=True)

        sesion = SesionProcesamiento.objects.first()
        self.assertEqual(sesion.estado, 'error')
        self.assertIn('Token', sesion.error_mensaje)


class ResultadoViewTest(TestCase):

    def setUp(self):
        self.client = Client()

    def test_resultado_con_sesion_completada(self):
        sesion = SesionProcesamiento.objects.create(
            imagen_original='test_orig.jpg',
            imagen_resultado='test_res.jpg',
            preset='colorear',
            estado='completado',
        )
        response = self.client.get(f'/resultado/{sesion.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'test_orig.jpg')
        self.assertContains(response, 'test_res.jpg')

    def test_resultado_con_error(self):
        sesion = SesionProcesamiento.objects.create(
            imagen_original='test.jpg',
            preset='colorear',
            estado='error',
            error_mensaje='Error de conexion',
        )
        response = self.client.get(f'/resultado/{sesion.id}/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Error de conexion')

    def test_resultado_sesion_no_existe(self):
        response = self.client.get('/resultado/9999/')
        self.assertEqual(response.status_code, 404)
