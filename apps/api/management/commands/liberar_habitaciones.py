# Crear archivo: management/commands/liberar_habitaciones.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.api.models import Reserva
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Libera habitaciones cuando las reservas han terminado'
    
    def handle(self, *args, **options):
        ahora = timezone.now()
        
        # Buscar reservas que ya terminaron
        reservas_terminadas = Reserva.objects.filter(
            estado="llegada_confirmada",
            fecha_hora_fin__lte=ahora
        )
        
        count = 0
        for reserva in reservas_terminadas:
            try:
                # Cambiar estado a completada
                reserva.estado = "completada"
                reserva.save()
                
                # La habitación ya está disponible por defecto,
                # solo cambiamos el estado de la reserva
                
                logger.info(f"✅ Reserva #{reserva.reserva_id} completada automáticamente")
                count += 1
                
            except Exception as e:
                logger.error(f"❌ Error liberando reserva #{reserva.reserva_id}: {e}")
        
        self.stdout.write(
            self.style.SUCCESS(f'✅ {count} habitaciones liberadas automáticamente')
        )


# Función para liberar habitaciones vencidas (para llamar desde el código)
def liberar_habitaciones_vencidas():
    """Función para liberar habitaciones desde el código - llamada en cada saludo."""
    from django.utils import timezone
    
    ahora = timezone.now()
    reservas_terminadas = Reserva.objects.filter(
        estado="llegada_confirmada",
        fecha_hora_fin__lte=ahora
    )
    
    count = 0
    for reserva in reservas_terminadas:
        try:
            reserva.estado = "completada"
            reserva.save()
            count += 1
            logger.info(f"🏠 Habitación liberada - Reserva #{reserva.reserva_id} completada")
        except Exception as e:
            logger.error(f"❌ Error liberando reserva #{reserva.reserva_id}: {e}")
    
    return count


# Comando de gestión para ejecutar manualmente si es necesario
# Crear archivo: management/commands/liberar_habitaciones.py