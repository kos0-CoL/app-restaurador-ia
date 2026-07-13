from django.db import models


class SesionProcesamiento(models.Model):
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('procesando', 'Procesando'),
        ('cargando', 'Cargando modelo'),
        ('completado', 'Completado'),
        ('error', 'Error'),
        ('abortado', 'Abortado'),
    ]

    imagen_original = models.CharField(max_length=255)
    imagen_resultado = models.CharField(max_length=255, blank=True, default='')
    preset = models.CharField(max_length=20)
    estado = models.CharField(max_length=20, choices=ESTADOS, default='pendiente')
    error_mensaje = models.TextField(blank=True, default='')
    intentos_api = models.IntegerField(default=0)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-creado']

    def __str__(self):
        return f"Sesion {self.id} - {self.preset} - {self.estado}"
