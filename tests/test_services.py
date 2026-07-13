from unittest.mock import patch, MagicMock
from django.test import TestCase, override_settings
from procesador.services import llamar_api_hf, ResultadoAPI


MOCK_SPACES = {
    'colorear': 'https://leonelhs-deoldify.hf.space',
    'restaurar': 'https://sczhou-codeformer.hf.space',
}


@override_settings(GRADIO_SPACES=MOCK_SPACES)
@override_settings(HUGGINGFACE_API_TOKEN='test-token-123')
@override_settings(HF_MAX_RETRIES=3)
@override_settings(HF_RETRY_BASE_WAIT=5)
class LlamarApiHfTest(TestCase):

    @patch('procesador.services._gradio_download')
    @patch('procesador.services._gradio_predict')
    @patch('procesador.services._gradio_upload')
    def test_exito_colorear(self, mock_upload, mock_predict, mock_download):
        mock_upload.return_value = '/tmp/gradio/test/uploaded.jpg'
        mock_predict.return_value = {
            'path': '/tmp/gradio/test/result.webp',
            'url': 'https://example.com/result.webp',
        }
        mock_download.return_value = b'imagen_procesada_bytes'

        resultado = llamar_api_hf(b'imagen_original', 'colorear')

        self.assertTrue(resultado.exito)
        self.assertEqual(resultado.datos, b'imagen_procesada_bytes')
        mock_upload.assert_called_once()
        mock_predict.assert_called_once()
        mock_download.assert_called_once()

    @patch('procesador.services._gradio_download')
    @patch('procesador.services._gradio_predict')
    @patch('procesador.services._gradio_upload')
    def test_exito_restaurar(self, mock_upload, mock_predict, mock_download):
        mock_upload.return_value = '/tmp/gradio/test/uploaded.jpg'
        mock_predict.return_value = {
            'path': '/tmp/gradio/test/result.png',
            'url': 'https://example.com/result.png',
        }
        mock_download.return_bytes = b'restaurado_bytes'

        resultado = llamar_api_hf(b'imagen_original', 'restaurar')

        self.assertTrue(resultado.exito)
        # Verificar que se pasan los parametros correctos de CodeFormer
        call_kwargs = mock_predict.call_args
        self.assertEqual(call_kwargs[1]['api_name'], 'inference')
        self.assertEqual(call_kwargs[1]['extra_params'], [True, True, True, 2, 0.5])

    @patch('procesador.services.time.sleep')
    @patch('procesador.services._gradio_download')
    @patch('procesador.services._gradio_predict')
    @patch('procesador.services._gradio_upload')
    def test_cold_start_503_reintenta(
        self, mock_upload, mock_predict, mock_download, mock_sleep
    ):
        # Simular 2 cold starts seguidos de exito
        mock_upload.return_value = '/tmp/gradio/test/uploaded.jpg'
        mock_predict.side_effect = [
            RuntimeError('Space en modo cold start (503)'),
            RuntimeError('Space en modo cold start (503)'),
            {'path': '/tmp/gradio/test/result.webp', 'url': 'https://example.com/result.webp'},
        ]
        mock_download.return_value = b'resultado_final'

        resultado = llamar_api_hf(b'imagen', 'colorear')

        self.assertTrue(resultado.exito)
        self.assertEqual(resultado.datos, b'resultado_final')
        self.assertEqual(mock_predict.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch('procesador.services.time.sleep')
    @patch('procesador.services._gradio_download')
    @patch('procesador.services._gradio_predict')
    @patch('procesador.services._gradio_upload')
    def test_cold_start_max_reintentos(
        self, mock_upload, mock_predict, mock_download, mock_sleep
    ):
        mock_upload.return_value = '/tmp/gradio/test/uploaded.jpg'
        mock_predict.side_effect = RuntimeError('Space en modo cold start (503)')

        resultado = llamar_api_hf(b'imagen', 'colorear')

        self.assertFalse(resultado.exito)
        self.assertIn('encendiendo', resultado.error)
        self.assertEqual(mock_predict.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch('procesador.services.time.sleep')
    @patch('procesador.services._gradio_download')
    @patch('procesador.services._gradio_predict')
    @patch('procesador.services._gradio_upload')
    def test_connection_error_reintenta(
        self, mock_upload, mock_predict, mock_download, mock_sleep
    ):
        import requests
        mock_upload.return_value = '/tmp/gradio/test/uploaded.jpg'
        mock_predict.side_effect = requests.exceptions.ConnectionError('No route')

        resultado = llamar_api_hf(b'imagen', 'colorear')

        self.assertFalse(resultado.exito)
        self.assertIn('conexion', resultado.error)
        self.assertEqual(mock_predict.call_count, 3)

    @patch('procesador.services._gradio_upload')
    def test_timeout_no_reintenta(self, mock_upload):
        import requests
        mock_upload.side_effect = requests.exceptions.ReadTimeout()

        resultado = llamar_api_hf(b'imagen', 'colorear')

        self.assertFalse(resultado.exito)
        self.assertIn('tiempo limite', resultado.error)

    @patch('procesador.services._gradio_upload')
    def test_upload_falla_runtime_error(self, mock_upload):
        mock_upload.side_effect = RuntimeError('Error subiendo imagen al Space: 500')

        resultado = llamar_api_hf(b'imagen', 'colorear')

        self.assertFalse(resultado.exito)
        self.assertIn('Error subiendo imagen', resultado.error)

    @override_settings(HUGGINGFACE_API_TOKEN='')
    def test_token_no_configurado(self):
        with self.assertRaises(ValueError):
            llamar_api_hf(b'imagen', 'colorear')

    def test_modelo_desconocido(self):
        resultado = llamar_api_hf(b'imagen', 'modelo_falso')
        self.assertFalse(resultado.exito)
        self.assertIn('desconocido', resultado.error)

    @patch('procesador.services._gradio_download')
    @patch('procesador.services._gradio_predict')
    @patch('procesador.services._gradio_upload')
    def test_api_name_correcto_colorear(
        self, mock_upload, mock_predict, mock_download
    ):
        mock_upload.return_value = '/tmp/test.jpg'
        mock_predict.return_value = {'url': 'https://example.com/r.webp'}
        mock_download.return_value = b'ok'

        llamar_api_hf(b'img', 'colorear')

        call_kwargs = mock_predict.call_args
        self.assertEqual(call_kwargs[1]['api_name'], 'predict')
        self.assertIsNone(call_kwargs[1]['extra_params'])

    @patch('procesador.services._gradio_download')
    @patch('procesador.services._gradio_predict')
    @patch('procesador.services._gradio_upload')
    def test_api_name_correcto_restaurar(
        self, mock_upload, mock_predict, mock_download
    ):
        mock_upload.return_value = '/tmp/test.jpg'
        mock_predict.return_value = {'url': 'https://example.com/r.png'}
        mock_download.return_value = b'ok'

        llamar_api_hf(b'img', 'restaurar')

        call_kwargs = mock_predict.call_args
        self.assertEqual(call_kwargs[1]['api_name'], 'inference')
        self.assertEqual(call_kwargs[1]['extra_params'], [True, True, True, 2, 0.5])
