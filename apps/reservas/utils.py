# apps/reservas/utils.py
"""
Utilidades para el sistema de reservas vía WhatsApp
"""
import json
import logging
from datetime import datetime, timedelta, time
from django.utils import timezone
from django.db.models import Q
from .models import ReservaWhatsApp, FuncionarioHotel, ProcesoReserva, EstadoReserva
from apps.api.models import Habitacion, Cliente, Conversacion

logger = logging.getLogger(__name__)


class ReservaManager:
    """Clase para manejar la lógica de reservas vía WhatsApp"""
    
    PASOS_RESERVA = {
        'inicio': 'Inicio del proceso de reserva',
        'fecha': 'Selección de fecha',
        'hora_inicio': 'Selección de hora de inicio',
        'duracion': 'Selección de duración',
        'habitacion': 'Selección de habitación',
        'confirmacion': 'Confirmación de datos',
        'completado': 'Reserva completada'
    }
    
    @classmethod
    def iniciar_proceso_reserva(cls, cliente, conversacion_id):
        """Inicia un nuevo proceso de reserva para un cliente"""
        try:
            # Verificar si ya hay un proceso activo
            proceso_activo = ProcesoReserva.objects.filter(
                cliente=cliente,
                completado=False,
                cancelado=False
            ).first()
            
            if proceso_activo:
                logger.info(f"Cliente {cliente.telefono} ya tiene un proceso de reserva activo")
                return proceso_activo
            
            # Crear nuevo proceso
            proceso = ProcesoReserva.objects.create(
                cliente=cliente,
                conversacion_id=str(conversacion_id),
                paso_actual='inicio',
                datos_temporales={}
            )
            
            logger.info(f"Proceso de reserva iniciado para cliente {cliente.telefono}: {proceso.proceso_id}")
            return proceso
            
        except Exception as e:
            logger.error(f"Error iniciando proceso de reserva: {e}")
            return None
    
    @classmethod
    def obtener_proceso_activo(cls, cliente):
        """Obtiene el proceso de reserva activo de un cliente"""
        return ProcesoReserva.objects.filter(
            cliente=cliente,
            completado=False,
            cancelado=False
        ).first()
    
    @classmethod
    def procesar_paso_reserva(cls, proceso, mensaje_usuario):
        """Procesa un paso del proceso de reserva"""
        try:
            paso_actual = proceso.paso_actual
            logger.info(f"Procesando paso '{paso_actual}' para proceso {proceso.proceso_id}")
            
            if paso_actual == 'inicio':
                return cls._procesar_inicio(proceso)
            elif paso_actual == 'fecha':
                return cls._procesar_fecha(proceso, mensaje_usuario)
            elif paso_actual == 'hora_inicio':
                return cls._procesar_hora_inicio(proceso, mensaje_usuario)
            elif paso_actual == 'duracion':
                return cls._procesar_duracion(proceso, mensaje_usuario)
            elif paso_actual == 'habitacion':
                return cls._procesar_habitacion(proceso, mensaje_usuario)
            elif paso_actual == 'confirmacion':
                return cls._procesar_confirmacion(proceso, mensaje_usuario)
            else:
                logger.warning(f"Paso desconocido: {paso_actual}")
                return cls._crear_respuesta_error("Ha ocurrido un error en el proceso de reserva.")
                
        except Exception as e:
            logger.error(f"Error procesando paso de reserva: {e}")
            return cls._crear_respuesta_error("Ha ocurrido un error procesando tu reserva. Por favor intenta nuevamente.")
    
    @classmethod
    def _procesar_inicio(cls, proceso):
        """Procesa el inicio del proceso de reserva"""
        proceso.actualizar_paso('fecha')
        
        return {
            "type": "text",
            "text": {
                "body": "¡Perfecto! Te ayudo a hacer tu reserva 📅\n\n"
                       "Para comenzar, ¿para qué fecha necesitas la reserva?\n\n"
                       "Por favor escribe la fecha en formato DD/MM/AAAA\n"
                       "Ejemplo: 25/12/2024"
            }
        }
    
    @classmethod
    def _procesar_fecha(cls, proceso, mensaje_usuario):
        """Procesa la selección de fecha"""
        try:
            # Intentar parsear la fecha
            fecha_str = mensaje_usuario.strip()
            
            # Formatos aceptados
            formatos = ['%d/%m/%Y', '%d-%m-%Y', '%d/%m/%y', '%d-%m-%y']
            fecha_reserva = None
            
            for formato in formatos:
                try:
                    fecha_reserva = datetime.strptime(fecha_str, formato).date()
                    break
                except ValueError:
                    continue
            
            if not fecha_reserva:
                return {
                    "type": "text",
                    "text": {
                        "body": "❌ No pude entender la fecha.\n\n"
                               "Por favor escribe la fecha en formato DD/MM/AAAA\n"
                               "Ejemplo: 25/12/2024"
                    }
                }
            
            # Validar que la fecha no sea en el pasado
            if fecha_reserva < timezone.now().date():
                return {
                    "type": "text",
                    "text": {
                        "body": "❌ La fecha no puede ser en el pasado.\n\n"
                               "Por favor selecciona una fecha a partir de hoy."
                    }
                }
            
            # Validar que no sea más de 30 días en el futuro
            if fecha_reserva > (timezone.now().date() + timedelta(days=30)):
                return {
                    "type": "text",
                    "text": {
                        "body": "❌ Solo puedes hacer reservas con hasta 30 días de anticipación.\n\n"
                               "Por favor selecciona una fecha más cercana."
                    }
                }
            
            # Guardar la fecha y avanzar al siguiente paso
            proceso.guardar_dato('fecha_reserva', fecha_reserva.isoformat())
            proceso.actualizar_paso('hora_inicio')
            
            fecha_formateada = fecha_reserva.strftime('%d/%m/%Y')
            
            return {
                "type": "text",
                "text": {
                    "body": f"✅ Fecha seleccionada: {fecha_formateada}\n\n"
                           "Ahora, ¿a qué hora necesitas la habitación?\n\n"
                           "Por favor escribe la hora en formato HH:MM\n"
                           "Ejemplo: 14:30 o 20:00"
                }
            }
            
        except Exception as e:
            logger.error(f"Error procesando fecha: {e}")
            return cls._crear_respuesta_error("Error procesando la fecha. Intenta nuevamente.")
    
    @classmethod
    def _procesar_hora_inicio(cls, proceso, mensaje_usuario):
        """Procesa la selección de hora de inicio"""
        try:
            hora_str = mensaje_usuario.strip()
            
            # Intentar parsear la hora
            formatos_hora = ['%H:%M', '%H.%M', '%H %M', '%H']
            hora_inicio = None
            
            for formato in formatos_hora:
                try:
                    if formato == '%H':
                        # Si solo se proporciona la hora, agregar :00
                        hora_inicio = datetime.strptime(hora_str + ':00', '%H:%M').time()
                    else:
                        hora_inicio = datetime.strptime(hora_str, formato).time()
                    break
                except ValueError:
                    continue
            
            if not hora_inicio:
                return {
                    "type": "text",
                    "text": {
                        "body": "❌ No pude entender la hora.\n\n"
                               "Por favor escribe la hora en formato HH:MM\n"
                               "Ejemplo: 14:30 o 20:00"
                    }
                }
            
            # Validar horario de operación (ejemplo: 6:00 AM a 11:59 PM)
            hora_apertura = time(6, 0)
            hora_cierre = time(23, 59)
            
            if not (hora_apertura <= hora_inicio <= hora_cierre):
                return {
                    "type": "text",
                    "text": {
                        "body": "❌ Nuestro horario de atención es de 6:00 AM a 11:59 PM.\n\n"
                               "Por favor selecciona una hora dentro de este horario."
                    }
                }
            
            # Guardar la hora y avanzar al siguiente paso
            proceso.guardar_dato('hora_inicio', hora_inicio.isoformat())
            proceso.actualizar_paso('duracion')
            
            hora_formateada = hora_inicio.strftime('%H:%M')
            
            # Crear botones para duración
            return {
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {
                        "text": f"✅ Hora de inicio: {hora_formateada}\n\n"
                               "¿Por cuántas horas necesitas la habitación?"
                    },
                    "action": {
                        "buttons": [
                            {
                                "type": "reply",
                                "reply": {
                                    "id": "duracion_2",
                                    "title": "2 horas"
                                }
                            },
                            {
                                "type": "reply",
                                "reply": {
                                    "id": "duracion_3",
                                    "title": "3 horas"
                                }
                            },
                            {
                                "type": "reply",
                                "reply": {
                                    "id": "duracion_4",
                                    "title": "4 horas"
                                }
                            }
                        ]
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error procesando hora de inicio: {e}")
            return cls._crear_respuesta_error("Error procesando la hora. Intenta nuevamente.")
    
    @classmethod
    def _procesar_duracion(cls, proceso, mensaje_usuario):
        """Procesa la selección de duración"""
        try:
            # Verificar si es un botón de duración
            if mensaje_usuario.startswith("duracion_"):
                duracion = int(mensaje_usuario.split("_")[1])
            else:
                # Intentar parsear como número
                try:
                    duracion = int(mensaje_usuario.strip())
                except ValueError:
                    return {
                        "type": "text",
                        "text": {
                            "body": "❌ Por favor indica el número de horas (ejemplo: 2, 3, 4)."
                        }
                    }
            
            # Validar duración
            if duracion < 1 or duracion > 12:
                return {
                    "type": "text",
                    "text": {
                        "body": "❌ La duración debe ser entre 1 y 12 horas.\n\n"
                               "Por favor selecciona una duración válida."
                    }
                }
            
            # Calcular hora de fin
            hora_inicio_str = proceso.obtener_dato('hora_inicio')
            hora_inicio = datetime.strptime(hora_inicio_str, '%H:%M:%S').time()
            
            # Crear datetime para cálculos
            fecha_base = datetime.combine(datetime.today(), hora_inicio)
            hora_fin = (fecha_base + timedelta(hours=duracion)).time()
            
            # Validar que no exceda el horario de cierre
            if hora_fin > time(23, 59):
                return {
                    "type": "text",
                    "text": {
                        "body": f"❌ Con {duracion} horas desde las {hora_inicio.strftime('%H:%M')}, "
                               f"la reserva terminaría a las {hora_fin.strftime('%H:%M')}.\n\n"
                               "Nuestro horario de atención termina a las 23:59.\n"
                               "Por favor selecciona menos horas o una hora de inicio más temprana."
                    }
                }
            
            # Guardar duración y hora fin
            proceso.guardar_dato('duracion_horas', duracion)
            proceso.guardar_dato('hora_fin', hora_fin.isoformat())
            proceso.actualizar_paso('habitacion')
            
            # Obtener habitaciones disponibles
            habitaciones_disponibles = cls._obtener_habitaciones_disponibles(proceso)
            
            if not habitaciones_disponibles:
                return {
                    "type": "text",
                    "text": {
                        "body": "😔 Lo siento, no hay habitaciones disponibles para la fecha y horario seleccionados.\n\n"
                               "¿Te gustaría probar con otra fecha u horario?"
                    }
                }
            
            # Crear botones de habitaciones
            botones = []
            for hab in habitaciones_disponibles[:3]:  # Máximo 3 botones
                precio_total = hab.precio_por_hora * duracion
                botones.append({
                    "type": "reply",
                    "reply": {
                        "id": f"hab_{hab.habitacion_id}",
                        "title": f"{hab.nombre_habitacion}"
                    }
                })
            
            return {
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {
                        "text": f"✅ Duración: {duracion} horas\n"
                               f"⏰ Horario: {hora_inicio.strftime('%H:%M')} - {hora_fin.strftime('%H:%M')}\n\n"
                               "Habitaciones disponibles:"
                    },
                    "action": {
                        "buttons": botones
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error procesando duración: {e}")
            return cls._crear_respuesta_error("Error procesando la duración. Intenta nuevamente.")
    
    @classmethod
    def _procesar_habitacion(cls, proceso, mensaje_usuario):
        """Procesa la selección de habitación"""
        try:
            # Verificar si es un botón de habitación
            if mensaje_usuario.startswith("hab_"):
                habitacion_id = int(mensaje_usuario.split("_")[1])
            else:
                return {
                    "type": "text",
                    "text": {
                        "body": "❌ Por favor selecciona una habitación usando los botones."
                    }
                }
            
            # Obtener la habitación
            try:
                habitacion = Habitacion.objects.get(habitacion_id=habitacion_id)
            except Habitacion.DoesNotExist:
                return cls._crear_respuesta_error("Habitación no encontrada.")
            
            # Verificar disponibilidad nuevamente
            if not cls._verificar_disponibilidad_habitacion(proceso, habitacion):
                return {
                    "type": "text",
                    "text": {
                        "body": "😔 Lo siento, esa habitación ya no está disponible.\n\n"
                               "Por favor selecciona otra habitación."
                    }
                }
            
            # Calcular precio total
            duracion = proceso.obtener_dato('duracion_horas')
            precio_total = habitacion.precio_por_hora * duracion
            
            # Guardar selección de habitación
            proceso.guardar_dato('habitacion_id', habitacion_id)
            proceso.guardar_dato('precio_total', float(precio_total))
            proceso.actualizar_paso('confirmacion')
            
            # Preparar resumen para confirmación
            fecha_reserva = datetime.fromisoformat(proceso.obtener_dato('fecha_reserva')).date()
            hora_inicio = datetime.fromisoformat(proceso.obtener_dato('hora_inicio')).time()
            hora_fin = datetime.fromisoformat(proceso.obtener_dato('hora_fin')).time()
            
            resumen = f"""✅ Resumen de tu reserva:

📅 Fecha: {fecha_reserva.strftime('%d/%m/%Y')}
⏰ Horario: {hora_inicio.strftime('%H:%M')} - {hora_fin.strftime('%H:%M')}
🏠 Habitación: {habitacion.nombre_habitacion}
⏱️ Duración: {duracion} horas
💰 Precio total: ${precio_total:,.0f}

¿Confirmas tu reserva?"""
            
            return {
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {
                        "text": resumen
                    },
                    "action": {
                        "buttons": [
                            {
                                "type": "reply",
                                "reply": {
                                    "id": "confirmar_si",
                                    "title": "✅ Sí, confirmar"
                                }
                            },
                            {
                                "type": "reply",
                                "reply": {
                                    "id": "confirmar_no",
                                    "title": "❌ Cancelar"
                                }
                            }
                        ]
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Error procesando habitación: {e}")
            return cls._crear_respuesta_error("Error procesando la habitación. Intenta nuevamente.")
    
    @classmethod
    def _procesar_confirmacion(cls, proceso, mensaje_usuario):
        """Procesa la confirmación final de la reserva"""
        try:
            if mensaje_usuario == "confirmar_si":
                # Crear la reserva
                reserva = cls._crear_reserva_desde_proceso(proceso)
                
                if reserva:
                    proceso.reserva_creada = reserva
                    proceso.finalizar(exitoso=True)
                    
                    return {
                        "type": "text",
                        "text": {
                            "body": f"🎉 ¡Reserva confirmada exitosamente!\n\n"
                                   f"📋 Número de reserva: #{reserva.reserva_id}\n"
                                   f"📅 Fecha: {reserva.fecha_reserva.strftime('%d/%m/%Y')}\n"
                                   f"⏰ Horario: {reserva.hora_inicio.strftime('%H:%M')} - {reserva.hora_fin.strftime('%H:%M')}\n"
                                   f"🏠 Habitación: {reserva.habitacion.nombre_habitacion}\n"
                                   f"💰 Total: ${reserva.precio_total:,.0f}\n\n"
                                   "Te esperamos en la fecha y hora indicadas. "
                                   "¡Gracias por elegirnos! 😊"
                        }
                    }
                else:
                    return cls._crear_respuesta_error("Error creando la reserva. Por favor intenta nuevamente.")
                    
            elif mensaje_usuario == "confirmar_no":
                proceso.finalizar(exitoso=False)
                
                return {
                    "type": "text",
                    "text": {
                        "body": "❌ Reserva cancelada.\n\n"
                               "Si cambias de opinión, puedes iniciar una nueva reserva "
                               "escribiendo 'reserva'. ¡Estaremos aquí para ayudarte! 😊"
                    }
                }
            else:
                return {
                    "type": "text",
                    "text": {
                        "body": "Por favor usa los botones para confirmar o cancelar tu reserva."
                    }
                }
                
        except Exception as e:
            logger.error(f"Error procesando confirmación: {e}")
            return cls._crear_respuesta_error("Error procesando la confirmación. Intenta nuevamente.")
    
    @classmethod
    def _obtener_habitaciones_disponibles(cls, proceso):
        """Obtiene las habitaciones disponibles para la fecha y horario seleccionados"""
        try:
            fecha_reserva = datetime.fromisoformat(proceso.obtener_dato('fecha_reserva')).date()
            hora_inicio = datetime.fromisoformat(proceso.obtener_dato('hora_inicio')).time()
            hora_fin = datetime.fromisoformat(proceso.obtener_dato('hora_fin')).time()
            
            # Obtener todas las habitaciones activas
            habitaciones = Habitacion.objects.filter(activo=True, disponible=True)
            
            habitaciones_disponibles = []
            
            for habitacion in habitaciones:
                if cls._verificar_disponibilidad_habitacion_especifica(
                    habitacion, fecha_reserva, hora_inicio, hora_fin
                ):
                    habitaciones_disponibles.append(habitacion)
            
            return habitaciones_disponibles
            
        except Exception as e:
            logger.error(f"Error obteniendo habitaciones disponibles: {e}")
            return []
    
    @classmethod
    def _verificar_disponibilidad_habitacion(cls, proceso, habitacion):
        """Verifica si una habitación específica está disponible"""
        try:
            fecha_reserva = datetime.fromisoformat(proceso.obtener_dato('fecha_reserva')).date()
            hora_inicio = datetime.fromisoformat(proceso.obtener_dato('hora_inicio')).time()
            hora_fin = datetime.fromisoformat(proceso.obtener_dato('hora_fin')).time()
            
            return cls._verificar_disponibilidad_habitacion_especifica(
                habitacion, fecha_reserva, hora_inicio, hora_fin
            )
            
        except Exception as e:
            logger.error(f"Error verificando disponibilidad: {e}")
            return False
    
    @classmethod
    def _verificar_disponibilidad_habitacion_especifica(cls, habitacion, fecha, hora_inicio, hora_fin):
        """Verifica disponibilidad de una habitación específica en fecha y horario dados"""
        try:
            # Buscar reservas que se solapen con el horario solicitado
            reservas_solapadas = ReservaWhatsApp.objects.filter(
                habitacion=habitacion,
                fecha_reserva=fecha,
                estado__in=[EstadoReserva.PENDIENTE, EstadoReserva.CONFIRMADA, EstadoReserva.EN_PROCESO],
                activo=True
            ).filter(
                Q(hora_inicio__lt=hora_fin) & Q(hora_fin__gt=hora_inicio)
            )
            
            return not reservas_solapadas.exists()
            
        except Exception as e:
            logger.error(f"Error verificando disponibilidad específica: {e}")
            return False
    
    @classmethod
    def _crear_reserva_desde_proceso(cls, proceso):
        """Crea una reserva a partir de un proceso completado"""
        try:
            # Obtener datos del proceso
            fecha_reserva = datetime.fromisoformat(proceso.obtener_dato('fecha_reserva')).date()
            hora_inicio = datetime.fromisoformat(proceso.obtener_dato('hora_inicio')).time()
            hora_fin = datetime.fromisoformat(proceso.obtener_dato('hora_fin')).time()
            habitacion_id = proceso.obtener_dato('habitacion_id')
            duracion_horas = proceso.obtener_dato('duracion_horas')
            precio_total = proceso.obtener_dato('precio_total')
            
            # Obtener habitación
            habitacion = Habitacion.objects.get(habitacion_id=habitacion_id)
            
            # Crear la reserva
            reserva = ReservaWhatsApp.objects.create(
                cliente=proceso.cliente,
                habitacion=habitacion,
                fecha_reserva=fecha_reserva,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                numero_personas=2,  # Default
                precio_total=precio_total,
                precio_por_hora=habitacion.precio_por_hora,
                horas_reservadas=duracion_horas,
                conversacion_id=proceso.conversacion_id,
                estado=EstadoReserva.PENDIENTE
            )
            
            logger.info(f"Reserva creada exitosamente: {reserva.reserva_id}")
            return reserva
            
        except Exception as e:
            logger.error(f"Error creando reserva desde proceso: {e}")
            return None
    
    @classmethod
    def _crear_respuesta_error(cls, mensaje):
        """Crea una respuesta de error estándar"""
        return {
            "type": "text",
            "text": {
                "body": mensaje
            }
        }
    
    @classmethod
    def cancelar_proceso(cls, cliente):
        """Cancela el proceso de reserva activo de un cliente"""
        try:
            proceso = cls.obtener_proceso_activo(cliente)
            if proceso:
                proceso.finalizar(exitoso=False)
                return True
            return False
        except Exception as e:
            logger.error(f"Error cancelando proceso: {e}")
            return False


class FuncionarioManager:
    """Clase para manejar la lógica de funcionarios del hotel"""
    
    @classmethod
    def es_funcionario(cls, telefono):
        """Verifica si un número pertenece a un funcionario"""
        return FuncionarioHotel.es_funcionario(telefono)
    
    @classmethod
    def obtener_funcionario(cls, telefono):
        """Obtiene un funcionario por su teléfono"""
        return FuncionarioHotel.obtener_funcionario(telefono)
    
    @classmethod
    def obtener_reservas_pendientes(cls):
        """Obtiene las reservas pendientes de llegada"""
        return ReservaWhatsApp.objects.filter(
            estado__in=[EstadoReserva.PENDIENTE, EstadoReserva.CONFIRMADA],
            activo=True,
            fecha_reserva__gte=timezone.now().date()
        ).select_related('cliente', 'habitacion').order_by('fecha_reserva', 'hora_inicio')
    
    @classmethod
    def crear_mensaje_reservas_pendientes(cls):
        """Crea un mensaje con las reservas pendientes para funcionarios"""
        reservas = cls.obtener_reservas_pendientes()
        
        if not reservas:
            return {
                "type": "text",
                "text": {
                    "body": "📋 No hay reservas pendientes de llegada en este momento."
                }
            }
        
        mensaje = "📋 *RESERVAS PENDIENTES DE LLEGADA*\n\n"
        
        for reserva in reservas[:10]:  # Máximo 10 reservas
            cliente_nombre = reserva.nombre_contacto or reserva.cliente.nombre_cliente or "Sin nombre"
            mensaje += f"🔹 *Reserva #{reserva.reserva_id}*\n"
            mensaje += f"👤 {cliente_nombre}\n"
            mensaje += f"📱 {reserva.cliente.telefono}\n"
            mensaje += f"📅 {reserva.fecha_reserva.strftime('%d/%m/%Y')}\n"
            mensaje += f"⏰ {reserva.hora_inicio.strftime('%H:%M')} - {reserva.hora_fin.strftime('%H:%M')}\n"
            mensaje += f"🏠 {reserva.habitacion.nombre_habitacion}\n"
            mensaje += f"💰 ${reserva.precio_total:,.0f}\n\n"
        
        if len(reservas) > 10:
            mensaje += f"... y {len(reservas) - 10} reservas más.\n\n"
        
        mensaje += "Para confirmar llegada, responde:\n"
        mensaje += "*LLEGADA #[número_reserva]*\n"
        mensaje += "Ejemplo: LLEGADA #123"
        
        return {
            "type": "text",
            "text": {
                "body": mensaje
            }
        }
    
    @classmethod
    def procesar_confirmacion_llegada(cls, funcionario, mensaje_usuario):
        """Procesa la confirmación de llegada de una reserva"""
        try:
            # Buscar patrón "LLEGADA #123" o similar
            mensaje_upper = mensaje_usuario.upper().strip()
            
            if not mensaje_upper.startswith('LLEGADA'):
                return None
            
            # Extraer número de reserva
            import re
            match = re.search(r'#(\d+)', mensaje_upper)
            
            if not match:
                return {
                    "type": "text",
                    "text": {
                        "body": "❌ Formato incorrecto.\n\n"
                               "Usa: LLEGADA #[número_reserva]\n"
                               "Ejemplo: LLEGADA #123"
                    }
                }
            
            reserva_id = int(match.group(1))
            
            # Buscar la reserva
            try:
                reserva = ReservaWhatsApp.objects.get(
                    reserva_id=reserva_id,
                    estado__in=[EstadoReserva.PENDIENTE, EstadoReserva.CONFIRMADA],
                    activo=True
                )
            except ReservaWhatsApp.DoesNotExist:
                return {
                    "type": "text",
                    "text": {
                        "body": f"❌ No se encontró la reserva #{reserva_id} o ya fue procesada."
                    }
                }
            
            # Confirmar llegada
            reserva.marcar_llegada(funcionario.telefono)
            
            cliente_nombre = reserva.nombre_contacto or reserva.cliente.nombre_cliente or "Sin nombre"
            
            return {
                "type": "text",
                "text": {
                    "body": f"✅ *LLEGADA CONFIRMADA*\n\n"
                           f"🔹 Reserva #{reserva.reserva_id}\n"
                           f"👤 {cliente_nombre}\n"
                           f"📱 {reserva.cliente.telefono}\n"
                           f"🏠 {reserva.habitacion.nombre_habitacion}\n"
                           f"💰 ${reserva.precio_total:,.0f}\n\n"
                           f"⏰ Confirmado: {timezone.now().strftime('%d/%m/%Y %H:%M')}\n"
                           f"👨‍💼 Por: {funcionario.nombre}"
                }
            }
            
        except Exception as e:
            logger.error(f"Error procesando confirmación de llegada: {e}")
            return {
                "type": "text",
                "text": {
                    "body": "❌ Error procesando la confirmación. Intenta nuevamente."
                }
            }

