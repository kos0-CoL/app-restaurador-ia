import os
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone

from procesador.models import SesionProcesamiento

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Elimina archivos temporales y resultados con mas de 24 horas'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias',
            type=int,
            default=1,
            help='Dias de retencion (default: 1)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Muestra que archivos se eliminarian sin borrar',
        )

    def handle(self, *args, **options):
        dias = options['dias']
        dry_run = options['dry_run']
        limite = timezone.now() - timedelta(days=dias)

        self.stdout.write(
            f'Buscando archivos anteriores a {limite.strftime("%Y-%m-%d %H:%M")} '
            f'({dias} dias)...'
        )

        sesiones = SesionProcesamiento.objects.filter(creado__lt=limite)
        eliminados = 0

        for sesion in sesiones:
            archivos = []
            if sesion.imagen_original:
                archivos.append(settings.MEDIA_ROOT / 'subidas' / sesion.imagen_original)
            if sesion.imagen_resultado:
                archivos.append(settings.MEDIA_ROOT / 'resultados' / sesion.imagen_resultado)

            for archivo in archivos:
                if archivo.exists():
                    if dry_run:
                        self.stdout.write(f'  [DRY-RUN] Eliminaria: {archivo}')
                    else:
                        os.remove(archivo)
                        self.stdout.write(f'  Eliminado: {archivo}')
                    eliminados += 1

            if not dry_run:
                sesion.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f'Completado: {eliminados} archivos '
                f'{"(dry-run)" if dry_run else "eliminados"}'
            )
        )
