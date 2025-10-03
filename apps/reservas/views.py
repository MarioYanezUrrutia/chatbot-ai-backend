import json
import os
import logging
from openai import OpenAI
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.conf import settings
from django.db.models import Q 
import requests
from datetime import datetime, date, time, timedelta
import google as genai
import asyncio
# Importar modelos de la nueva app 'reservas'
from apps.reservas.models import Habitacion, FuncionarioHotel, EstadoConversacion
from .models import Cliente, Conversacion, Mensaje, TipoHabitacion, PreguntaFrecuente, BaseConocimiento, PreguntaDesconocida, Reserva


# --- CONFIGURACIÓN ---
logger = logging.getLogger(__name__)

# --- CONFIGURACIÓN PARA GEMINI ---
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
print("="*60)
if GEMINI_API_KEY and len(GEMINI_API_KEY) > 10:
    print(f"✅ DIAGNÓSTICO: Clave de API de Gemini encontrada y cargada.")
    print(f"   - La clave empieza con: {GEMINI_API_KEY[:5]}...")
    print(f"   - La clave termina con: ...{GEMINI_API_KEY[-4:]}")
    # genai.configure(api_key=GEMINI_API_KEY)
    logger.info("✅ Configuración de Google Gemini válida")
else:
    print("❌ DIAGNÓSTICO: NO se encontró o es inválida la API Key de Gemini.")
    print("   - Asegúrate de que la variable GEMINI_API_KEY esté en tu archivo .env")
    logger.warning("⚠️ No se encontró API Key de Gemini. La funcionalidad de IA estará deshabilitada.")
print("="*60)

# === 2. IMPORTACIÓN DEL SDK (CÓDIGO NUEVO QUE AGREGAMOS) ===
# IMPORTAR EL NUEVO SDK DE GOOGLE GENAI
try:
    GENAI_SDK_AVAILABLE = True
    logger.info("✅ Google GenAI SDK (nuevo) importado correctamente")
except ImportError as e:
    genai = None
    GENAI_SDK_AVAILABLE = False
    logger.error(f"❌ No se pudo importar Google GenAI SDK: {e}")
    logger.info("💡 Para instalar: pip install google-genai")

WHATSAPP_VERIFY_TOKEN = os.environ.get("WHATSAPP_VERIFY_TOKEN")
WHATSAPP_ACCESS_TOKEN = os.environ.get("WHATSAPP_ACCESS_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_API_URL = "https://graph.facebook.com/v19.0/"

# --- FUNCIÓN DE VALIDACIÓN DE CONFIGURACIÓN ---
def validar_configuracion_whatsapp():
    """Valida que todas las variables de WhatsApp estén configuradas"""
    missing = []
    if not WHATSAPP_ACCESS_TOKEN:
        missing.append("WHATSAPP_ACCESS_TOKEN")
    if not WHATSAPP_PHONE_NUMBER_ID:
        missing.append("WHATSAPP_PHONE_NUMBER_ID")
    if not WHATSAPP_VERIFY_TOKEN:
        missing.append("WHATSAPP_VERIFY_TOKEN")
    
    if missing:
        logger.error(f"❌ Variables de WhatsApp faltantes: {", ".join(missing)}")
        return False
    
    logger.info("✅ Configuración de WhatsApp válida")
    return True

# --- FUNCIÓN DE PRUEBA DE CONEXIÓN ---
def test_whatsapp_connection():
    """Función de prueba para validar la conexión con WhatsApp API"""
    if not validar_configuracion_whatsapp():
        return False
        
    url = f"{WHATSAPP_API_URL}{WHATSAPP_PHONE_NUMBER_ID}"
    headers = {"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            logger.info("✅ Conexión con WhatsApp API exitosa")
            return True
        else:
            logger.error(f"❌ Error de conexión WhatsApp: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Error probando conexión WhatsApp: {e}")
        return False

# --- FUNCIÓN DE ENVÍO DE MENSAJES MEJORADA ---
def send_whatsapp_message(to_number, message_payload):
    """Envía mensaje con mejor manejo de errores de autenticación"""
    
    if not validar_configuracion_whatsapp():
        return False
    
    headers = {
        "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json"
    }
    url = f"{WHATSAPP_API_URL}{WHATSAPP_PHONE_NUMBER_ID}/messages"
    base_payload = {"messaging_product": "whatsapp", "to": to_number}
    final_payload = {**base_payload, **message_payload}
    
    logger.info(f"📤 Enviando mensaje a WhatsApp:")
    logger.info(f"   URL: {url}")
    logger.info(f"   Phone Number ID: {WHATSAPP_PHONE_NUMBER_ID}")
    logger.info(f"   To: {to_number}")
    logger.info(f"   Payload: {json.dumps(final_payload, indent=2, ensure_ascii=False)}")

    # AGREGAR ESTA LÍNEA ANTES DE ENVIAR:
    debug_whatsapp_payload(final_payload, to_number)

    try:
        response = requests.post(url, headers=headers, json=final_payload, timeout=30)
        
        logger.info(f"📥 Respuesta WhatsApp - Status: {response.status_code}")
        logger.info(f"   Response: {response.text}")
        
        if response.status_code == 200:
            logger.info(f"✅ Mensaje enviado exitosamente a {to_number}")
            return True
        else:
            try:
                error_data = response.json()
                error_code = error_data.get("error", {}).get("code")
                error_message = error_data.get("error", {}).get("message", "Sin mensaje de error")
                
                if error_code == 10:
                    logger.error("🚨 ERROR DE AUTENTICACIÓN WHATSAPP:")
                    logger.error("   - El token de acceso puede haber expirado")
                    logger.error("   - Verifica que el Phone Number ID sea correcto")
                    logger.error("   - Los tokens temporales duran solo 24 horas")
                    logger.error("   - Ve a Facebook Developers > WhatsApp > API Setup")
                    logger.error(f"   - Error completo: {error_message}")
                elif error_code == 131026:
                    logger.error(f"🚨 NÚMERO NO VÁLIDO: {to_number} no puede recibir mensajes")
                    logger.error("   - Verifica que el número esté en formato internacional")
                    logger.error("   - Para desarrollo, el número debe estar agregado a tu app")
                else:
                    logger.error(f"❌ Error WhatsApp código {error_code}: {error_message}")
                    
            except json.JSONDecodeError:
                logger.error(f"❌ Error WhatsApp sin formato JSON: {response.text}")
            
            return False
        
    except requests.exceptions.Timeout:
        logger.error("⏰ Timeout enviando mensaje a WhatsApp")
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"🌐 Error de conexión con WhatsApp: {e}")
        return False
    except Exception as e:
        logger.error(f"💥 Error inesperado enviando mensaje: {e}")
        return False

# --- FUNCIÓN AUXILIAR PARA CREAR RESPUESTA DE TEXTO SIMPLE ---
def crear_respuesta_texto(texto):
    """Crea una respuesta de texto simple y segura"""
    return {
        "type": "text",
        "text": {
            "body": texto
        }
    }

# --- FUNCIÓN AUXILIAR PARA CREAR RESPUESTA CON BOTONES ---
def crear_respuesta_botones():
    """Crea una respuesta con botones interactivos de preguntas frecuentes"""
    try:
        logger.info("🔍 Buscando preguntas frecuentes para crear botones...")
        preguntas_menu = PreguntaFrecuente.objects.filter(activo=True).order_by("pregunta_frecuenta_id")[:3]
        logger.info(f"📊 Preguntas frecuentes encontradas: {preguntas_menu.count()}")
        
        if not preguntas_menu:
            logger.info("⚠️ No hay preguntas frecuentes disponibles - Usando mensaje de texto simple")
            return crear_respuesta_texto("¡Hola! Soy Pratsy, tu asistente virtual. ¿En qué puedo ayudarte hoy?")

        botones = []
        for p in preguntas_menu:
            logger.info(f"🔹 Procesando pregunta ID {p.pregunta_frecuenta_id}: \'{p.pregunta_corta_boton}\'")
            if p.pregunta_corta_boton and len(p.pregunta_corta_boton.strip()) > 0:
                titulo_boton = p.pregunta_corta_boton[:20] if len(p.pregunta_corta_boton) > 20 else p.pregunta_corta_boton
                boton = {
                    "type": "reply",
                    "reply": {
                        "id": f"faq_{p.pregunta_frecuenta_id}",
                        "title": titulo_boton.strip()
                    }
                }
                botones.append(boton)
                logger.info(f"✅ Botón creado: {json.dumps(boton, ensure_ascii=False)}")
            else:
                logger.warning(f"⚠️ Pregunta ID {p.pregunta_frecuenta_id} no tiene pregunta_corta_boton válida")
        
        if not botones:
            logger.info("⚠️ No se pudieron crear botones válidos - Usando mensaje de texto simple")
            return crear_respuesta_texto("¡Hola! Soy Pratsy, tu asistente virtual. ¿En qué puedo ayudarte hoy?")

        texto_cuerpo = "¡Hola! Soy Pratsy 🤖\n\nSelecciona una opción:"
        
        respuesta_botones = {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": texto_cuerpo
                },
                "action": {
                    "buttons": botones
                }
            }
        }
        
        logger.info(f"🎯 Respuesta con botones creada exitosamente con {len(botones)} botones")
        return respuesta_botones
        
    except Exception as e:
        logger.error(f"❌ Error al crear respuesta con botones: {e}")
        logger.info("🔄 Fallback a mensaje de texto simple")
        return crear_respuesta_texto("¡Hola! Soy Pratsy, tu asistente virtual. ¿En qué puedo ayudarte hoy?")

# --- FUNCIÓN PARA PROCESAR RESPUESTA CON IA ---
def procesar_respuesta_con_ia(respuesta_bd, mensaje_usuario, conversacion):
    """
    Procesa la respuesta de la BD a través de la IA para hacerla más amigable
    USANDO EL NUEVO GOOGLE GENAI SDK (2024)
    """
    logger.info("🤖 Procesando respuesta con IA para hacerla más amigable...")
    
    if not GEMINI_API_KEY:
        logger.warning("⚠️ No hay API Key de Gemini - Devolviendo respuesta original")
        return respuesta_bd
    
    if not GENAI_SDK_AVAILABLE:
        logger.warning("⚠️ SDK de Gemini no disponible - Devolviendo respuesta original")
        return respuesta_bd
    
    try:
        # CONFIGURACIÓN PARA EL NUEVO SDK
        if GENAI_SDK_AVAILABLE == True:
            logger.info("🔧 Configurando nuevo Google GenAI SDK...")
            
            # Crear cliente con el nuevo SDK
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            # Modelos disponibles en el nuevo SDK (según documentación oficial)
            MODELOS_DISPONIBLES = [
                "models/gemini-2.0-flash-exp",    # Más reciente (experimental)
                "models/gemini-1.5-flash",        # Recomendado para uso general
                "models/gemini-1.5-pro",          # Para tareas complejas
            ]
            
        elif GENAI_SDK_AVAILABLE == "deprecated":
            logger.info("🔧 Configurando SDK deprecado como fallback...")
            
            # Configurar SDK deprecado
            # genai_old.configure(api_key=GEMINI_API_KEY)
            
            # Modelos disponibles en SDK deprecado
            MODELOS_DISPONIBLES = [
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-pro"
            ]
        
        # Obtenemos historial limitado para contexto
        historial_mensajes = Mensaje.objects.filter(
            conversacion=conversacion
        ).order_by("-timestamp")[:4]
        
        historial_context = ""
        for msg in reversed(historial_mensajes):
            role = "Cliente" if msg.remitente == "cliente" else "Asistente"
            historial_context += f"{role}: {msg.contenido}\n"
        
        prompt = f"""
Eres Pratsy, un asistente virtual amigable y profesional de un motel. Tu trabajo es tomar la información técnica de la base de datos y presentarla de manera cálida, cordial y servicial, como si fueras un humano atento.

CONTEXTO DE LA CONVERSACIÓN:
{historial_context}

PREGUNTA DEL USUARIO: {mensaje_usuario}

RESPUESTA TÉCNICA DE LA BASE DE DATOS: {respuesta_bd}

INSTRUCCIONES:
1. Reformula la respuesta técnica de manera amigable y conversacional
2. Mantén toda la información importante
3. Usa un tono cálido y profesional
4. Hazlo sentir como una conversación con una persona real
5. Sé conciso pero completo
6. Usa emojis apropiados si mejora la experiencia
7. Si es información sobre precios, horarios o servicios, sé claro y directo

Reformula la respuesta:
"""
        
        logger.info(f"📤 Enviando a Gemini para reformular respuesta")
        
        # INTENTAR CON CADA MODELO HASTA QUE UNO FUNCIONE
        response = None
        modelo_usado = None
        
        for modelo in MODELOS_DISPONIBLES:
            try:
                logger.info(f"🔄 Intentando con modelo: {modelo}")
                
                if GENAI_SDK_AVAILABLE == True:
                    # NUEVO SDK
                    response = client.models.generate_content(
                        model=modelo,
                        contents=prompt,
                        config={
                            "max_output_tokens": 500,
                            "temperature": 0.7,
                        }
                    )                
                if response:
                    modelo_usado = modelo
                    logger.info(f"✅ Modelo {modelo} funcionó correctamente")
                    break
                    
            except Exception as e:
                logger.warning(f"⚠️ Error con modelo {modelo}: {e}")
                continue
        
        # PROCESAR RESPUESTA
        if response:
            try:
                # Obtener texto de la respuesta según el SDK
                if GENAI_SDK_AVAILABLE == True:
                    texto_respuesta = response.text if hasattr(response, 'text') else str(response)
                else:
                    texto_respuesta = response.text
                
                if texto_respuesta and texto_respuesta.strip():
                    logger.info(f"✅ Respuesta reformulada exitosamente con {modelo_usado}")
                    return texto_respuesta.strip()
                else:
                    logger.warning("⚠️ Respuesta vacía de IA")
                    return respuesta_bd
                    
            except Exception as e:
                logger.error(f"❌ Error extrayendo texto de respuesta: {e}")
                return respuesta_bd
        else:
            logger.warning("⚠️ Ningún modelo funcionó - Usando respuesta original")
            return respuesta_bd
            
    except Exception as e:
        logger.error(f"❌ Error general procesando con IA: {e}")
        logger.info("🔄 Fallback: Devolviendo respuesta original de BD")
        return respuesta_bd

def procesar_pregunta_desconocida_con_ia(mensaje_usuario, conversacion):
    """
    Procesa preguntas desconocidas con IA para dar una respuesta empática
    USANDO EL NUEVO GOOGLE GENAI SDK (2024)
    """
    logger.info("🤖 Procesando pregunta desconocida con IA...")
    
    # Respuesta por defecto si la IA no funciona
    respuesta_default = "Disculpa, no tengo información específica sobre eso en este momento. ¿Podrías reformular tu pregunta o consultar sobre nuestros servicios principales como reservas, precios u horarios?"
    
    if not GEMINI_API_KEY or not GENAI_SDK_AVAILABLE:
        logger.warning("⚠️ No hay API Key o SDK no disponible - Usando respuesta por defecto")
        return respuesta_default
    
    try:
        # CONFIGURACIÓN SEGÚN EL SDK DISPONIBLE
        if GENAI_SDK_AVAILABLE == True:
            client = genai.Client(api_key=GEMINI_API_KEY)
            MODELOS_DISPONIBLES = [
                "models/gemini-2.0-flash-exp",
                "models/gemini-1.5-flash",
                "models/gemini-1.5-pro",
            ]
        
        # Historial para contexto
        historial_mensajes = Mensaje.objects.filter(
            conversacion=conversacion
        ).order_by("-timestamp")[:4]
        
        historial_context = ""
        for msg in reversed(historial_mensajes):
            role = "Cliente" if msg.remitente == "cliente" else "Asistente"
            historial_context += f"{role}: {msg.contenido}\n"
        
        prompt = f"""
Eres Pratsy, un asistente virtual amigable de un motel. Un cliente te hizo una pregunta que no está en tu base de conocimiento.

CONTEXTO DE LA CONVERSACIÓN:
{historial_context}

PREGUNTA DEL CLIENTE: {mensaje_usuario}

INSTRUCCIONES:
1. Reconoce amablemente que no tienes esa información específica
2. Si la pregunta es general (no técnica del motel), ofrece ayuda básica si puedes
3. Si es técnica del motel, disculpate y sugiere alternativas
4. Siempre mantén un tono empático y profesional
5. Ofrece ayuda con los servicios principales del motel
6. Sé conciso pero cálido
7. No inventes información que no tengas

Responde de manera empática:
"""
        
        logger.info(f"📤 Enviando pregunta desconocida a Gemini")
        
        # INTENTAR CON CADA MODELO
        for modelo in MODELOS_DISPONIBLES:
            try:
                if GENAI_SDK_AVAILABLE == True:
                    response = client.models.generate_content(
                        model=modelo,
                        contents=prompt,
                        config={
                            "max_output_tokens": 500,
                            "temperature": 0.7,
                        }
                    )
                    texto_respuesta = response.text if hasattr(response, 'text') else str(response)                
                if texto_respuesta and texto_respuesta.strip():
                    logger.info(f"✅ Respuesta de pregunta desconocida generada con {modelo}")
                    return texto_respuesta.strip()
                    
            except Exception as e:
                logger.warning(f"⚠️ Error con modelo {modelo}: {e}")
                continue
        
        # Si llegamos aquí, ningún modelo funcionó
        logger.warning("⚠️ Ningún modelo funcionó para pregunta desconocida")
        return respuesta_default
            
    except Exception as e:
        logger.error(f"❌ Error procesando pregunta desconocida con IA: {e}")
        return respuesta_default

# --- LÓGICA DE RESERVAS --- 
def es_funcionario(telefono: str) -> bool:
    """Verifica si un número pertenece a un funcionario del hotel."""
    return FuncionarioHotel.objects.filter(telefono=telefono, activo=True).exists()

def procesar_mensaje_funcionario(telefono: str, mensaje: str) -> dict:
    """Procesa mensajes de funcionarios para la gestión de reservas."""
    mensaje_lower = mensaje.lower().strip()

    if mensaje_lower == "reservas prats":
        reservas_pendientes = Reserva.objects.filter(estado__in=["pendiente", "confirmada"]).order_by("fecha", "fecha_hora_inicio")

        if not reservas_pendientes.exists():
            return crear_respuesta_texto("No hay reservas pendientes en este momento.")

    botones = []
    mensaje_texto = "📋 *Reservas Pendientes:*"

    for reserva in reservas_pendientes:
        mensaje_texto += f"🆔 *#{reserva.reserva_id}* - {reserva.cliente.nombre_cliente if reserva.cliente else 'Cliente'}\n"
        mensaje_texto += f"📅 {reserva.fecha.strftime("%d/%m/%Y")} {reserva.fecha_hora_inicio.strftime("%H:%M")}"
        mensaje_texto += f"🏠 {reserva.habitacion.nombre_habitacion}"
        mensaje_texto += f"📱 {reserva.cliente.telefono if reserva.cliente else 'N/A'}\n"
        # mensaje_texto += f"💰 ${reserva.precio_total:,}\n"
        # mensaje_texto += f"📊 Estado: {reserva.get_estado_display()}\n"
        duracion_horas = (reserva.fecha_hora_fin - reserva.fecha_hora_inicio).total_seconds() / 3600
        precio_total = reserva.habitacion.precio_por_hora * duracion_horas if reserva.habitacion else 0
        mensaje_texto += f"💰 ${precio_total:,.0f}\n"
        mensaje_texto += f"📊 Estado: {reserva.estado}\n\n"

        if reserva.estado == "confirmada":
            botones.append({
                "type": "reply",
                "reply": {
                    "id": f"llegada_{reserva.reserva_id}",
                    "title": f"✅ Llegada #{reserva.reserva_id}"
                }
            })
        elif reserva.estado == "pendiente":
                botones.append({
                "type": "reply",
                "reply": {
                    "id": f"confirmar_{reserva.reserva_id}",
                    "title": f"👍 Confirmar #{reserva.reserva_id}"
                }
            })

        if botones:
            return {
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {
                        "text": mensaje_texto
                    },
                    "action": {
                        "buttons": botones
                    }
                }
            }
        else:
            return crear_respuesta_texto(mensaje_texto)

    # Procesar botones de acción de funcionario
    if mensaje_lower.startswith("llegada_"):
        reserva_id = mensaje_lower.replace("llegada_", "")
        return marcar_llegada(reserva_id)
    elif mensaje_lower.startswith("confirmar_"):
        reserva_id = mensaje_lower.replace("confirmar_", "")
        return confirmar_reserva(reserva_id)

    return crear_respuesta_texto("Comando no reconocido. Usa \"Reservas Prats\" para ver las reservas pendientes.")

def marcar_llegada(reserva_id: str) -> dict:
    """Marca una reserva como llegada confirmada."""
    try:
        reserva = Reserva.objects.get(reserva_id=int(reserva_id))
        reserva.estado = "llegada_confirmada"
        reserva.fecha_llegada = timezone.now()
        reserva.save()
        return crear_respuesta_texto(
            f"✅ *Llegada Confirmada*\n\n"
            f"Reserva #{reserva_id} marcada como llegada confirmada.\n"
            f"Cliente: {reserva.cliente.nombre_cliente if reserva.cliente else 'Cliente'}\n"
            f"Habitación: {reserva.habitacion.nombre_habitacion if reserva.habitacion else 'Habitación'}"
        )
    except Reserva.DoesNotExist:
        return crear_respuesta_texto(f"❌ No se encontró la reserva #{reserva_id}")
    except Exception as e:
        logger.error(f"Error al marcar llegada de reserva {reserva_id}: {e}")
        return crear_respuesta_texto(f"❌ Error al procesar la llegada de la reserva #{reserva_id}.")

def confirmar_reserva(reserva_id: str) -> dict:
    """Confirma una reserva pendiente."""
    try:
        reserva = Reserva.objects.get(reserva_id=int(reserva_id))
        reserva.estado = "confirmada"
        reserva.save()
        return crear_respuesta_texto(
            f"👍 *Reserva Confirmada*\n\n"
            f"Reserva #{reserva_id} de {reserva.cliente.nombre_cliente if reserva.cliente else 'Cliente'} ha sido confirmada.\n"
            f"Se ha notificado al cliente."
        )
    except Reserva.DoesNotExist:
        return crear_respuesta_texto(f"❌ No se encontró la reserva #{reserva_id}")
    except Exception as e:
        logger.error(f"Error al confirmar reserva {reserva_id}: {e}")
        return crear_respuesta_texto(f"❌ Error al confirmar la reserva #{reserva_id}.")

# FUNCIÓN CORREGIDA PARA EL PROCESO DE RESERVA - FIX DEFINITIVO DEL ERROR DE FECHA
def iniciar_proceso_reserva(cliente) -> dict:
    """
    Inicia el proceso de reserva para un cliente
    FIX DEFINITIVO DEL ERROR DE DATETIME
    """
    logger.info("🗓️ Iniciando proceso de reserva...")
    
    try:
        estado_conv, created = EstadoConversacion.objects.get_or_create(
            cliente=cliente,
            defaults={
                "paso_actual": "esperando_fecha",
                "datos_reserva": {},
                "tipo": "reserva"
            }
        )
        if not created:
            estado_conv.paso_actual = "esperando_fecha"
            estado_conv.datos_reserva = {}
            estado_conv.tipo = "reserva"
            estado_conv.save()

        # === FIX DEFINITIVO DEL ERROR DE DATETIME ===
        logger.info("📅 Calculando fechas con múltiples métodos de fallback...")
        
        hoy = None
        metodo_usado = None
        
        # MÉTODO 1: timezone de Django (más confiable en aplicaciones Django)
        try:
            hoy = timezone.now().date()
            metodo_usado = "timezone.now()"
            logger.info(f"✅ Fecha obtenida con {metodo_usado}: {hoy}")
        except Exception as e1:
            logger.warning(f"⚠️ Error con timezone.now(): {e1}")
            
            # MÉTODO 2: datetime estándar con import explícito
            try:
                hoy = datetime.now().date()
                metodo_usado = "datetime.now()"
                logger.info(f"✅ Fecha obtenida con {metodo_usado}: {hoy}")
            except Exception as e2:
                logger.warning(f"⚠️ Error con datetime importado: {e2}")
                
                # MÉTODO 3: datetime con import de módulo completo
                try:
                    hoy = datetime.now().date()
                    metodo_usado = "datetime.now() (módulo completo)"
                    logger.info(f"✅ Fecha obtenida con {metodo_usado}: {hoy}")
                except Exception as e3:
                    logger.error(f"❌ Error con todos los métodos de fecha: {e1}, {e2}, {e3}")
                    
                    # MÉTODO 4: Fecha de emergencia funcional
                    try:
                        hoy = datetime.today()
                        metodo_usado = "date.today()"
                        logger.info(f"✅ Fecha obtenida con {metodo_usado}: {hoy}")
                    except Exception as e4:
                        logger.error(f"❌ Error crítico: {e4}")
                        
                        # ÚLTIMO RECURSO: Clase de fecha personalizada
                        class FechaSencilla:
                            def __init__(self):
                                # Usar fecha fija pero realista
                                self.year = 2024
                                self.month = 9
                                self.day = 26
                            
                            def strftime(self, formato):
                                if formato == '%Y-%m-%d':
                                    return f"{self.year}-{self.month:02d}-{self.day:02d}"
                                elif formato == '%d/%m':
                                    return f"{self.day:02d}/{self.month:02d}"
                                return f"{self.day:02d}/{self.month:02d}/{self.year}"
                            
                            def __add__(self, delta):
                                nuevo_dia = self.day + getattr(delta, 'days', 1)
                                nueva_fecha = FechaSencilla()
                                nueva_fecha.day = nuevo_dia
                                return nueva_fecha
                            
                            def __str__(self):
                                return self.strftime('%Y-%m-%d')
                        
                        hoy = FechaSencilla()
                        metodo_usado = "FechaSencilla (emergencia)"
                        logger.warning(f"⚠️ Usando {metodo_usado}")
        
        # Calcular fechas futuras
        try:
            if hasattr(hoy, '__add__'):
                mañana = hoy + timedelta(days=1)
                pasado_mañana = hoy + timedelta(days=2)
            else:
                # Para la clase personalizada
                mañana = hoy + type('', (), {'days': 1})()
                pasado_mañana = hoy + type('', (), {'days': 2})()
            
            logger.info(f"✅ Fechas calculadas - Hoy: {hoy}, Mañana: {mañana}, Pasado: {pasado_mañana}")
            
        except Exception as e:
            logger.error(f"❌ Error calculando fechas futuras: {e}")
            # Usar la misma fecha para todas
            mañana = hoy
            pasado_mañana = hoy
        
        # Crear botones con manejo ultra-robusto de errores
        try:
            botones_fecha = []
            
            # Botón para hoy
            try:
                id_hoy = f"fecha_{hoy.strftime('%Y-%m-%d')}"
                titulo_hoy = f"📅 Hoy {hoy.strftime('%d/%m')}"
            except:
                id_hoy = "fecha_hoy"
                titulo_hoy = "📅 Hoy"
            
            botones_fecha.append({
                "type": "reply",
                "reply": {
                    "id": id_hoy,
                    "title": titulo_hoy
                }
            })
            
            # Botón para mañana
            try:
                id_mañana = f"fecha_{mañana.strftime('%Y-%m-%d')}"
                titulo_mañana = f"📅 Mañana {mañana.strftime('%d/%m')}"
            except:
                id_mañana = "fecha_manana"
                titulo_mañana = "📅 Mañana"
            
            botones_fecha.append({
                "type": "reply",
                "reply": {
                    "id": id_mañana,
                    "title": titulo_mañana
                }
            })
            
            # Botón para pasado mañana
            try:
                id_pasado = f"fecha_{pasado_mañana.strftime('%Y-%m-%d')}"
                titulo_pasado = f"📅 {pasado_mañana.strftime('%d/%m')}"
            except:
                id_pasado = "fecha_pasado"
                titulo_pasado = "📅 Pasado mañana"
            
            botones_fecha.append({
                "type": "reply",
                "reply": {
                    "id": id_pasado,
                    "title": titulo_pasado
                }
            })
            
            logger.info(f"✅ Botones de fecha creados exitosamente ({len(botones_fecha)} botones)")
            
        except Exception as e:
            logger.error(f"❌ Error crítico creando botones: {e}")
            # Botones ultra-básicos como último recurso
            botones_fecha = [
                {
                    "type": "reply",
                    "reply": {
                        "id": "fecha_1",
                        "title": "📅 Hoy"
                    }
                },
                {
                    "type": "reply",
                    "reply": {
                        "id": "fecha_2",
                        "title": "📅 Mañana"
                    }
                }
            ]
            logger.warning("⚠️ Usando botones ultra-básicos de emergencia")

        texto_mensaje = (
            "🗓️ *Proceso de Reserva Iniciado*\n\n"
            "Para realizar su reserva, necesito algunos datos.\n\n"
            "Seleccione la fecha que desea reservar:"
        )

        return crear_respuesta_botones_ultra_segura(texto_mensaje, botones_fecha)
        
    except Exception as e:
        logger.error(f"💥 Error crítico en iniciar_proceso_reserva: {e}")
        # Respuesta de emergencia absolutamente básica
        return crear_respuesta_texto_segura(
            "🗓️ *Reservas*\n\n"
            "Para reservar, por favor escriba:\n"
            "• 'hoy' para reservar hoy\n"
            "• 'mañana' para mañana\n"
            "• Una fecha específica (ej: 27/09)"
        )

def crear_respuesta_con_boton_reserva(texto, botones_adicionales=None):
    """Crea respuesta que SIEMPRE incluye botón de reserva"""
    try:
        botones = botones_adicionales or []
        
        # Verificar si ya existe botón de reserva
        ids_existentes = []
        for btn in botones:
            try:
                id_boton = btn.get("reply", {}).get("id", "")
                ids_existentes.append(id_boton)
            except:
                continue
        
        # Agregar botón de reserva si no existe
        if "hacer_reserva" not in ids_existentes:
            botones.append({
                "type": "reply",
                "reply": {
                    "id": "hacer_reserva",
                    "title": "📅 Reservar"
                }
            })
        
        # Limitar botones
        botones = botones[:3]
        
        if len(botones) > 0:
            return crear_respuesta_botones_ultra_segura(texto, botones)
        else:
            return crear_respuesta_texto_segura(texto)
            
    except Exception as e:
        logger.error(f"❌ Error en crear_respuesta_con_boton_reserva: {e}")
        return crear_respuesta_texto_segura(texto)

# 2. SALUDO INICIAL CORREGIDO (4 BOTONES)
def crear_respuesta_botones_saludo():
    """Crea respuesta de saludo inicial con 4 botones"""
    try:
        logger.info("👋 Creando respuesta de saludo inicial con 4 botones...")
        
        # Buscar preguntas frecuentes para botones (que NO sean saludo inicial)
        preguntas_menu = PreguntaFrecuente.objects.filter(
            activo=True,
            es_saludo_inicial=False
        ).order_by("pregunta_frecuenta_id")[:3]  # Solo 3 porque agregamos reserva
        
        botones = []
        
        # Agregar botones de preguntas frecuentes
        for p in preguntas_menu:
            if p.pregunta_corta_boton:
                botones.append({
                    "type": "reply",
                    "reply": {
                        "id": f"faq_{p.pregunta_frecuenta_id}",
                        "title": p.pregunta_corta_boton.strip()[:20]
                    }
                })
        
        # Completar hasta 4 botones
        if len(botones) < 3:
            botones.append({
                "type": "reply",
                "reply": {
                    "id": "info_general",
                    "title": "ℹ️ Información"
                }
            })
        
        # SIEMPRE agregar botón de reserva (será el 4to)
        botones.append({
            "type": "reply",
            "reply": {
                "id": "hacer_reserva",
                "title": "📅 Reservar"
            }
        })
        
        # Limitar a 3 (WhatsApp no soporta 4, usaremos los 3 más importantes)
        # Priorizar: 1 FAQ + Info + Reserva
        if len(botones) > 3:
            botones_finales = []
            # Tomar 1 FAQ si existe
            if any(btn["reply"]["id"].startswith("faq_") for btn in botones):
                faq_btn = next(btn for btn in botones if btn["reply"]["id"].startswith("faq_"))
                botones_finales.append(faq_btn)
            
            # Agregar info y reserva
            botones_finales.extend([
                {"type": "reply", "reply": {"id": "info_general", "title": "ℹ️ Info"}},
                {"type": "reply", "reply": {"id": "hacer_reserva", "title": "📅 Reservar"}}
            ])
            botones = botones_finales[:3]
        
        # Buscar saludo en BD
        saludo_bd = PreguntaFrecuente.objects.filter(
            es_saludo_inicial=True,
            activo=True
        ).first()
        
        if saludo_bd and saludo_bd.respuesta:
            texto_saludo = saludo_bd.respuesta
        else:
            texto_saludo = "¡Hola! Soy Pratsy 🤖, tu asistente virtual del Motel."
        
        texto_completo = texto_saludo + "\n\n¿En qué puedo ayudarte hoy?"
        
        return crear_respuesta_botones_ultra_segura(texto_completo, botones)
        
    except Exception as e:
        logger.error(f"❌ Error creando saludo: {e}")
        return crear_respuesta_texto_segura("¡Hola! Soy Pratsy, tu asistente virtual. ¿En qué puedo ayudarte hoy?")

# 3. PROCESO DE RESERVA CORREGIDO (ESPECIALMENTE PASO DE DURACIÓN)
def procesar_paso_reserva(cliente: Cliente, mensaje: str) -> dict:
    """Procesa cada paso del proceso de reserva - CORREGIDO PARA DURACIÓN"""
    try:
        estado_conv = EstadoConversacion.objects.get(cliente=cliente, tipo="reserva")
    except EstadoConversacion.DoesNotExist:
        return iniciar_proceso_reserva(cliente)

    paso = estado_conv.paso_actual
    datos_reserva = estado_conv.datos_reserva

    if paso == "esperando_fecha":
        # Manejar selección por botón de fecha
        if mensaje.startswith("fecha_"):
            try:
                # Extraer fecha del ID del botón (formato: fecha_YYYY-MM-DD) 
                fecha_str = mensaje.replace("fecha_", "")
                fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date()
                
                # Validar que la fecha no sea del pasado (excepto hoy)
                if fecha_obj < date.today():
                    return crear_respuesta_texto_segura("❌ No se pueden hacer reservas para fechas pasadas.")
                
                # Guardar fecha seleccionada
                datos_reserva["fecha"] = fecha_str  # Formato ISO para la BD
                estado_conv.datos_reserva = datos_reserva
                estado_conv.paso_actual = "esperando_hora"
                estado_conv.save()

                # Pedir hora de forma manual (sin botones)
                fecha_formateada = fecha_obj.strftime("%d/%m/%Y")
                texto_hora = (
                    f"✅ Fecha seleccionada: {fecha_formateada}\n\n"
                    "Ahora indique la hora de inicio (formato: HH:MM, ejemplo: 14:30):"
                )

                return crear_respuesta_texto_segura(texto_hora)
                
            except ValueError:
                return crear_respuesta_texto_segura("❌ Formato de fecha inválido. Intente nuevamente.")
        
        # Manejar entrada manual de fecha (mantener compatibilidad)
        else:
            try:
                # Tu código existente para procesar fecha manual
                fecha_obj = datetime.strptime(mensaje.strip(), "%d/%m/%Y").date()
                if fecha_obj < datetime.date.today():
                    return crear_respuesta_texto_segura("❌ No se pueden hacer reservas para fechas pasadas.")
                    
                datos_reserva["fecha"] = fecha_obj.isoformat()
                estado_conv.datos_reserva = datos_reserva
                estado_conv.paso_actual = "esperando_hora"
                estado_conv.save()
                
                return crear_respuesta_texto_segura(
                    f"✅ Fecha registrada: {fecha_obj.strftime('%d/%m/%Y')}\n\n"
                    "Ahora indique la hora de inicio (formato: HH:MM, ejemplo: 14:30):"
                )
            except ValueError:
                return crear_respuesta_texto_segura(
                    "❌ Formato de fecha inválido. Use DD/MM/AAAA (ejemplo: 25/12/2024) o seleccione uno de los botones."
                )
    elif paso == "esperando_hora":
        try:
            hora_obj = datetime.strptime(mensaje.strip(), "%H:%M").time()
            datos_reserva["hora_inicio"] = hora_obj.strftime("%H:%M")
            estado_conv.datos_reserva = datos_reserva
            estado_conv.paso_actual = "esperando_duracion"
            estado_conv.save()
            
            # CORREGIDO: Solo 3 opciones de duración, sin caracteres especiales
            botones_duracion = [
                {"type": "reply", "reply": {"id": "duracion_2", "title": "2 horas"}},
                {"type": "reply", "reply": {"id": "duracion_4", "title": "4 horas"}},
                {"type": "reply", "reply": {"id": "duracion_8", "title": "8 horas"}}
            ]
            
            texto_duracion = f"✅ Hora seleccionada: {mensaje}\n\nSeleccione la duración de su reserva:"
            
            # USAR FUNCIÓN SEGURA
            return crear_respuesta_botones_ultra_segura(texto_duracion, botones_duracion)
            
        except ValueError:
            return crear_respuesta_texto_segura(
                "❌ Formato de hora inválido.\n\n"
                "Por favor, use el formato HH:MM (ejemplo: 14:30):"
            )

    elif paso == "esperando_duracion":
        if mensaje.startswith("duracion_"):
            try:
                duracion = int(mensaje.replace("duracion_", ""))
                datos_reserva["duracion"] = duracion
                estado_conv.datos_reserva = datos_reserva
                estado_conv.paso_actual = "esperando_habitacion"
                estado_conv.save()

                habitaciones_disponibles = Habitacion.objects.filter(disponible=True)[:3]
                
                if not habitaciones_disponibles.exists():
                    return crear_respuesta_texto_segura("Lo sentimos, no hay habitaciones disponibles en este momento.")

                botones_habitaciones = []
                texto_habitaciones = f"✅ Duración seleccionada: {duracion} horas\n\nHabitaciones disponibles:\n\n"
                
                for hab in habitaciones_disponibles:
                    texto_habitaciones += f"• {hab.nombre_habitacion} - ${hab.precio_por_hora:,}/hora\n"
                    
                    # Nombre corto para botón
                    nombre_corto = hab.nombre_habitacion
                    if len(nombre_corto) > 18:
                        nombre_corto = nombre_corto[:15] + "..."
                    
                    botones_habitaciones.append({
                        "type": "reply", 
                        "reply": {
                            "id": f"hab_{hab.habitacion_id}", 
                            "title": nombre_corto
                        }
                    })
                
                texto_habitaciones += "\nSeleccione una habitación:"
                
                return crear_respuesta_botones_ultra_segura(texto_habitaciones, botones_habitaciones)
                
            except ValueError:
                return crear_respuesta_texto_segura("❌ Error procesando duración. Intente nuevamente.")
        else:
            # Si no seleccionó duración, mostrar opciones nuevamente
            botones_duracion = [
                {"type": "reply", "reply": {"id": "duracion_2", "title": "2 horas"}},
                {"type": "reply", "reply": {"id": "duracion_4", "title": "4 horas"}},
                {"type": "reply", "reply": {"id": "duracion_8", "title": "8 horas"}}
            ]
            return crear_respuesta_botones_ultra_segura(
                "Por favor, seleccione la duración usando los botones:",
                botones_duracion
            )

    elif paso == "esperando_habitacion":
        if mensaje.startswith("hab_"):
            try:
                habitacion_id = int(mensaje.replace("hab_", ""))
                habitacion = Habitacion.objects.get(habitacion_id=habitacion_id, disponible=True)
                
                datos_reserva["habitacion_id"] = habitacion.habitacion_id
                datos_reserva["habitacion_nombre"] = habitacion.nombre_habitacion
                datos_reserva["precio_por_hora"] = str(habitacion.precio_por_hora)
                estado_conv.datos_reserva = datos_reserva
                estado_conv.paso_actual = "esperando_confirmacion"
                estado_conv.save()

                # Calcular totales
                precio_total = habitacion.precio_por_hora * datos_reserva["duracion"]
                hora_inicio_dt = datetime.strptime(datos_reserva["hora_inicio"], "%H:%M")
                hora_fin_dt = hora_inicio_dt + timedelta(hours=datos_reserva["duracion"])
                
                # Resumen SIN caracteres especiales problemáticos
                resumen_texto = f"RESUMEN DE RESERVA\n\n"
                resumen_texto += f"Fecha: {datetime.fromisoformat(datos_reserva['fecha']).strftime('%d/%m/%Y')}\n"
                resumen_texto += f"Horario: {datos_reserva['hora_inicio']} - {hora_fin_dt.strftime('%H:%M')}\n"
                resumen_texto += f"Duracion: {datos_reserva['duracion']} horas\n"
                resumen_texto += f"Habitacion: {habitacion.nombre_habitacion}\n"
                resumen_texto += f"Total: ${precio_total:,}\n\n"
                resumen_texto += "¿Confirma esta reserva?"

                botones_confirmacion = [
                    {"type": "reply", "reply": {"id": "confirmar_si", "title": "✅ Si, Confirmar"}},
                    {"type": "reply", "reply": {"id": "confirmar_no", "title": "❌ No, Cancelar"}}
                ]
                
                return crear_respuesta_botones_ultra_segura(resumen_texto, botones_confirmacion)
                
            except (ValueError, Habitacion.DoesNotExist) as e:
                logger.error(f"Error seleccionando habitación: {e}")
                return crear_respuesta_texto_segura("❌ Habitación no válida. Por favor, seleccione una de la lista.")
        else:
            return crear_respuesta_texto_segura("Por favor, use los botones para seleccionar una habitación.")

    elif paso == "esperando_confirmacion":
        if mensaje == "confirmar_si":
            return crear_reserva_final(cliente, estado_conv)
        elif mensaje == "confirmar_no":
            estado_conv.delete()
            return crear_respuesta_texto_segura(
                "❌ Reserva cancelada.\n\n"
                "Si desea realizar una nueva reserva, escriba 'reserva'."
            )
        else:
            return crear_respuesta_texto_segura("Por favor, confirme o cancele usando los botones.")

    return crear_respuesta_texto_segura("Error en el proceso. Escriba 'reserva' para comenzar de nuevo.")

# 4. MODIFICAR obtener_respuesta_del_agente PARA INCLUIR BOTÓN RESERVA CONSTANTE
# Agregar esta lógica al final de obtener_respuesta_del_agente, antes del return final:

def agregar_boton_reserva_si_corresponde(respuesta, mensaje_usuario):
    """Agrega botón de reserva a respuestas que no lo tienen"""
    # Si ya es una respuesta con botones, verificar si tiene botón de reserva
    if respuesta.get("type") == "interactive":
        botones_existentes = respuesta.get("interactive", {}).get("action", {}).get("buttons", [])
        ids_existentes = [btn.get("reply", {}).get("id", "") for btn in botones_existentes]
        
        # Si no tiene botón de reserva y hay espacio, agregarlo
        if "hacer_reserva" not in ids_existentes and len(botones_existentes) < 3:
            botones_existentes.append({
                "type": "reply",
                "reply": {
                    "id": "hacer_reserva",
                    "title": "📅 Reservar"
                }
            })
            respuesta["interactive"]["action"]["buttons"] = botones_existentes
    
    # Si es respuesta de texto simple y no es parte del proceso de reserva
    elif (respuesta.get("type") == "text" and 
          not any(palabra in mensaje_usuario.lower() for palabra in ["duracion_", "hab_", "confirmar_"])):
        
        # Convertir a respuesta con botón
        texto_original = respuesta["text"]["body"]
        boton_reserva = [{
            "type": "reply",
            "reply": {
                "id": "hacer_reserva", 
                "title": "📅 Reservar"
            }
        }]
        return crear_respuesta_botones_ultra_segura(texto_original, boton_reserva)
    
    return respuesta

def crear_reserva_final(cliente: Cliente, estado_conv: EstadoConversacion) -> dict:
    """Crea la reserva final en la base de datos y finaliza el estado de conversación."""
    datos = estado_conv.datos_reserva
    try:
        habitacion = Habitacion.objects.get(habitacion_id=datos["habitacion_id"])
        precio_total = habitacion.precio_por_hora * datos["duracion"]
       
        hora_inicio_dt = datetime.strptime(datos["hora_inicio"], "%H:%M")
        hora_fin_dt = hora_inicio_dt + timedelta(hours=datos["duracion"])

        reserva = Reserva.objects.create(
            cliente=cliente,
            # nombre=cliente.nombre_cliente, # Usar el nombre del cliente de la BD
            telefono=cliente.telefono,
            fecha=datetime.fromisoformat(datos["fecha"]),
            # hora_inicio=hora_inicio_dt.time(),
            # hora_fin=hora_fin_dt.time(),
            fecha_hora_inicio=timezone.make_aware(datetime.combine(
                datetime.fromisoformat(datos["fecha"]), 
                hora_inicio_dt.time()
            )),
            fecha_hora_fin=timezone.make_aware(datetime.combine(
                datetime.fromisoformat(datos["fecha"]), 
                hora_fin_dt.time()
            )),
            duracion=datos["duracion"],
            habitacion=habitacion,
            precio_total=precio_total,
            estado="pendiente", # Estado inicial de la reserva
            origen="whatsapp"
        )
        estado_conv.delete() # Eliminar estado de conversación después de crear la reserva

        mensaje_confirmacion = f"🎉 *¡Reserva Creada Exitosamente!*\n\n"
        mensaje_confirmacion += f"🆔 *Número de Reserva:* #{reserva.reserva_id}\n"
        mensaje_confirmacion += f"👤 *Nombre:* {reserva.cliente.nombre_cliente}\n"
        mensaje_confirmacion += f"📅 *Fecha:* {reserva.fecha_hora_inicio.strftime('%d/%m/%Y')}\n"
        mensaje_confirmacion += f"🕐 *Horario:* {reserva.fecha_hora_inicio.strftime('%H:%M')} - {reserva.fecha_hora_fin.strftime('%H:%M')}\n"
        mensaje_confirmacion += f"🏠 *Habitación:* {reserva.habitacion.nombre_habitacion}\n"
        mensaje_confirmacion += f"💰 *Total:* ${precio_total:,.0f}\n\n"
        mensaje_confirmacion += "📋 *Estado:* Pendiente de confirmación\n\n"
        mensaje_confirmacion += "Nos pondremos en contacto con usted para confirmar su reserva.\n\n"
        mensaje_confirmacion += "¡Gracias por elegir Motel Pratsy! 🏨"
        
        return crear_respuesta_texto(mensaje_confirmacion)

    except Habitacion.DoesNotExist:
        logger.error(f"Error al crear reserva: Habitación ID {datos['habitacion_id']} no encontrada.")
        return crear_respuesta_texto("❌ Error al finalizar la reserva. La habitación seleccionada no es válida.")
    except Exception as e:
        logger.error(f"Error inesperado al crear reserva: {e}", exc_info=True)
        return crear_respuesta_texto("❌ Ha ocurrido un error inesperado al procesar su reserva. Por favor, intente de nuevo más tarde.")

def crear_respuesta_botones_segura(texto_cuerpo, botones):
    """Crea respuesta con botones validando el formato para WhatsApp"""
    try:
        # Validar que no hay más de 3 botones (límite de WhatsApp)
        if len(botones) > 3:
            botones = botones[:3]
            logger.warning("⚠️ Limitando botones a 3 (máximo de WhatsApp)")
        
        # Validar formato de cada botón
        botones_validos = []
        for boton in botones:
            if (boton.get("type") == "reply" and 
                boton.get("reply", {}).get("id") and 
                boton.get("reply", {}).get("title")):
                
                # Limpiar y validar título (máximo 20 caracteres)
                titulo = str(boton["reply"]["title"]).strip()[:20]
                id_boton = str(boton["reply"]["id"]).strip()
                
                if titulo and id_boton:
                    botones_validos.append({
                        "type": "reply",
                        "reply": {
                            "id": id_boton,
                            "title": titulo
                        }
                    })
        
        if not botones_validos:
            logger.warning("⚠️ No hay botones válidos - Usando texto simple")
            return crear_respuesta_texto(texto_cuerpo)
        
        # Validar texto del cuerpo (máximo 1024 caracteres)
        texto_limpio = str(texto_cuerpo).strip()[:1024]
        
        respuesta = {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": texto_limpio
                },
                "action": {
                    "buttons": botones_validos
                }
            }
        }
        
        logger.info(f"✅ Respuesta con {len(botones_validos)} botones creada correctamente")
        return respuesta
        
    except Exception as e:
        logger.error(f"❌ Error creando respuesta con botones: {e}")
        return crear_respuesta_texto(texto_cuerpo)
    
# Función para liberar habitaciones vencidas (para llamar desde el código)
def liberar_habitaciones_vencidas():
    """Función para liberar habitaciones desde el código - llamada en cada saludo."""    
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
    
# --- "CEREBRO" DEL BOT MEJORADO ---
def obtener_respuesta_del_agente(mensaje_usuario: str, cliente: Cliente, conversacion: Conversacion):
    """Cerebro del bot con detección de saludo corregida - adaptado desde web chat"""
    logger.info(f"\n--- INICIO PROCESAMIENTO CEREBRO WHATSAPP ---")
    logger.info(f"💬 Mensaje del usuario: '{mensaje_usuario}'")
    logger.info(f"Debug date type: {type(date)}")
    # logger.info(f"Debug date.today type: {type(date.today)}")
    
    mensaje_limpio = mensaje_usuario.lower().strip()
    
    # --- 1. VERIFICAR SI ES UN FUNCIONARIO ---
    # Verificar si es funcionario registrado con palabra clave
    if mensaje_limpio == "kabymur" and es_funcionario(cliente.telefono):
        logger.info("👨‍💼 Funcionario autenticado correctamente")
        return activar_modo_funcionario(cliente.telefono)
    
    # Si ya está en modo funcionario (verificar sesión activa)
    if esta_en_modo_funcionario(cliente.telefono):
        logger.info("👨‍💼 Procesando comando de funcionario autenticado")
        return procesar_mensaje_funcionario_mejorado(cliente.telefono, mensaje_usuario)
    
    # --- 2. VERIFICAR SI HAY PROCESO DE RESERVA ACTIVO ---
    try:
        estado_conv = EstadoConversacion.objects.get(cliente=cliente, tipo="reserva")
        logger.info(f"📝 Proceso de reserva activo - Paso: {estado_conv.paso_actual}")
        return procesar_paso_reserva(cliente, mensaje_usuario)
    except EstadoConversacion.DoesNotExist:
        pass
    
    # --- 3. DETECTAR SALUDO INICIAL ---
    palabras = set(mensaje_limpio.split())
    PALABRAS_DE_SALUDO = {'hola', 'buenas', 'hello', 'hi', 'hey', 'buenos', 'buen', 'saludos', 'holis', 'holaa'}
    
    # Obtener historial para verificar si es conversación nueva
    mensajes_anteriores = Mensaje.objects.filter(
        conversacion=conversacion,
        remitente='cliente'
    ).count()

    if (palabras.intersection(PALABRAS_DE_SALUDO) and mensajes_anteriores <= 1) or mensaje_limpio in PALABRAS_DE_SALUDO:
        logger.info("👋 Saludo inicial detectado en WhatsApp")
        
        # Liberar habitaciones vencidas en cada saludo
        try:
            habitaciones_liberadas = liberar_habitaciones_vencidas()
            if habitaciones_liberadas > 0:
                logger.info(f"🏠 {habitaciones_liberadas} habitaciones liberadas automáticamente")
        except Exception as e:
            logger.error(f"❌ Error liberando habitaciones: {e}")
        
        # Buscar saludo configurado en BD
        saludo_configurado = PreguntaFrecuente.objects.filter(
            es_saludo_inicial=True, 
            activo=True
        ).first()
        
        if saludo_configurado:
            # Procesar respuesta de saludo con IA
            respuesta_saludo = procesar_respuesta_con_ia(
                saludo_configurado.respuesta, 
                mensaje_usuario, 
                conversacion
            )
            
            # Obtener preguntas frecuentes para botones (que NO sean saludo inicial)
            preguntas_menu = PreguntaFrecuente.objects.filter(
                activo=True,
                es_saludo_inicial=False
            ).order_by('pregunta_frecuenta_id')[:2]  # Solo 2 porque agregamos botón de reserva
            
            botones = []
            for p in preguntas_menu:
                if p.pregunta_corta_boton:
                    botones.append({
                        "type": "reply",
                        "reply": {
                            "id": f"faq_{p.pregunta_frecuenta_id}",
                            "title": p.pregunta_corta_boton.strip()[:20]
                        }
                    })
            
            # Agregar botón de reserva
            botones.append({
                "type": "reply",
                "reply": {
                    "id": "hacer_reserva",
                    "title": "📅 Reservar"
                }
            })
            
            # Crear respuesta con botones
            if botones:
                texto_completo = respuesta_saludo + "\n\n¿En qué puedo ayudarte?"
                return crear_respuesta_botones_ultra_segura(texto_completo, botones)
            else:
                return crear_respuesta_texto_segura(respuesta_saludo)
        else:
            # Saludo por defecto si no hay configurado en BD
            botones_default = [
                {"type": "reply", "reply": {"id": "info_general", "title": "ℹ️ Información"}},
                {"type": "reply", "reply": {"id": "hacer_reserva", "title": "📅 Reservar"}}
            ]
            texto_default = "¡Hola! Soy Pratsy 🤖, tu asistente virtual del Motel.\n\n¿En qué puedo ayudarte?"
            return crear_respuesta_botones_ultra_segura(texto_default, botones_default)
    
    # --- 3.5. DETECTAR CONSULTA DE DISPONIBILIDAD ---
    if detectar_consulta_disponibilidad(mensaje_usuario):
        logger.info("🏠 Consulta de disponibilidad detectada")
        return consultar_disponibilidad_habitaciones()
    
    # --- 4. PROCESAR BOTONES PRESIONADOS ---
    if mensaje_usuario.startswith("faq_"):
        try:
            faq_id = int(mensaje_usuario.replace("faq_", ""))
            pregunta = PreguntaFrecuente.objects.get(
                pregunta_frecuenta_id=faq_id, 
                activo=True
            )
            logger.info(f"🔘 Botón FAQ presionado: {pregunta.pregunta_corta_boton}")
            respuesta_final = procesar_respuesta_con_ia(pregunta.respuesta, mensaje_usuario, conversacion)
            return crear_respuesta_texto_segura(respuesta_final)
        except (ValueError, PreguntaFrecuente.DoesNotExist):
            logger.error(f"❌ FAQ ID inválido: {mensaje_usuario}")
    
    elif mensaje_usuario == "hacer_reserva":
        logger.info("📅 Botón de reserva presionado")
        return iniciar_proceso_reserva(cliente)
    
    elif mensaje_usuario == "info_general":
        logger.info("ℹ️ Botón de información presionado")
        return crear_respuesta_texto_segura(
            "Somos Motel Pratsy 🏨\n\n"
            "Ofrecemos habitaciones cómodas y privadas para tu descanso.\n\n"
            "¿Te gustaría hacer una reserva o tienes alguna pregunta específica?"
        )
    
    elif mensaje_usuario in ["iniciar_reserva", "si_reserva", "confirmar_reserva_si"]:
        return iniciar_proceso_reserva(cliente)
    
    elif mensaje_usuario in ["no_reservar", "confirmar_reserva_no"]:
        return crear_respuesta_texto_segura(
            "¡Perfecto! Si cambias de opinión, escríbeme 'reserva' y te ayudo.\n\n"
            "¿Hay algo más en lo que pueda asistirte?"
        )
    
    # --- 5. BÚSQUEDA EN PREGUNTAS FRECUENTES ---
    logger.info("🔍 Buscando en Preguntas Frecuentes...")
    try:
        palabras_busqueda = mensaje_limpio.split()
        q_preguntas = Q()
        
        # Buscar por palabras clave
        for palabra in palabras_busqueda:
            if len(palabra) >= 3:
                q_preguntas |= (
                    Q(palabras_clave__icontains=palabra) | 
                    Q(pregunta_larga__icontains=palabra) |
                    Q(pregunta_corta_boton__icontains=palabra) |
                    Q(respuesta__icontains=palabra)
                )
        
        pregunta_frecuente = PreguntaFrecuente.objects.filter(
            q_preguntas, 
            activo=True
        ).exclude(
            es_saludo_inicial=True  # Excluir saludos de esta búsqueda
        ).first()

        if pregunta_frecuente:
            logger.info(f"✅ Pregunta frecuente encontrada: {pregunta_frecuente.pregunta_corta_boton}")
            respuesta_bd = pregunta_frecuente.respuesta
            respuesta_final = procesar_respuesta_con_ia(respuesta_bd, mensaje_usuario, conversacion)
            return crear_respuesta_texto_segura(respuesta_final)

    except Exception as e:
        logger.error(f"❌ Error buscando en preguntas frecuentes: {e}")

    # --- 6. BÚSQUEDA EN BASE DE CONOCIMIENTO ---
    logger.info("📚 Buscando en Base de Conocimiento...")
    try:
        base_conocimiento = BaseConocimiento.objects.filter(
            Q(respuesta__icontains=mensaje_limpio) | 
            Q(palabras_clave__icontains=mensaje_limpio),
            activo=True
        ).first()

        if base_conocimiento:
            logger.info("✅ Información de Base de Conocimiento encontrada")
            respuesta_final = procesar_respuesta_con_ia(base_conocimiento.respuesta, mensaje_usuario, conversacion)
            return crear_respuesta_texto_segura(respuesta_final)

    except Exception as e:
        logger.error(f"❌ Error buscando en BD de conocimiento: {e}")

    # --- 7. PROCESAR COMO PREGUNTA DESCONOCIDA ---
    logger.info("❓ Pregunta no encontrada. Procesando como desconocida...")
    try:
        PreguntaDesconocida.objects.create(
            cliente=cliente,
            texto_pregunta=mensaje_usuario,
            fecha_recibida=timezone.now()
        )
    except Exception as e:
        logger.error(f"❌ Error guardando pregunta desconocida: {e}")
    
    respuesta_desconocida = procesar_pregunta_desconocida_con_ia(mensaje_usuario, conversacion)
    
    # Ofrecer ayuda con botones
    botones_ayuda = [
        {"type": "reply", "reply": {"id": "hacer_reserva", "title": "📅 Reservar"}},
        {"type": "reply", "reply": {"id": "info_general", "title": "ℹ️ Info"}}
    ]
    
    texto_con_ayuda = respuesta_desconocida + "\n\n¿Te gustaría hacer una reserva o necesitas más información?"
    
    logger.info("--- FIN PROCESAMIENTO CEREBRO WHATSAPP ---\n")
    return crear_respuesta_botones_ultra_segura(texto_con_ayuda, botones_ayuda)

def crear_respuesta_texto_segura(texto):
    """Crea una respuesta de texto validada para WhatsApp"""
    try:
        # Limpiar el texto
        texto_limpio = str(texto).strip()
        
        # Remover caracteres problemáticos
        caracteres_problematicos = ['\u2019', '\u201c', '\u201d', '\u2013', '\u2014']
        for char in caracteres_problematicos:
            texto_limpio = texto_limpio.replace(char, '')
        
        # Limitar longitud (máximo 4096 caracteres para WhatsApp)
        if len(texto_limpio) > 4000:
            texto_limpio = texto_limpio[:3997] + "..."
        
        # Validar que no esté vacío
        if not texto_limpio:
            texto_limpio = "Lo siento, no pude procesar tu mensaje correctamente."
        
        return {
            "type": "text",
            "text": {
                "body": texto_limpio
            }
        }
    except Exception as e:
        logger.error(f"❌ Error creando respuesta de texto segura: {e}")
        return {
            "type": "text",
            "text": {
                "body": "Error interno. Por favor intenta nuevamente."
            }
        }

# 3. FUNCIÓN CORREGIDA PARA BOTONES SEGUROS
def crear_respuesta_botones_ultra_segura(texto_cuerpo, botones):
    """Versión ultra segura para crear botones de WhatsApp"""
    try:
        # Limpiar texto del cuerpo
        texto_limpio = str(texto_cuerpo).strip()
        
        # Remover caracteres especiales problemáticos
        texto_limpio = texto_limpio.replace('\u2019', "'")  # Comilla curva
        texto_limpio = texto_limpio.replace('\u201c', '"')  # Comilla doble izq
        texto_limpio = texto_limpio.replace('\u201d', '"')  # Comilla doble der
        texto_limpio = texto_limpio.replace('\u2013', '-')  # En dash
        texto_limpio = texto_limpio.replace('\u2014', '-')  # Em dash
        
        # Limitar longitud del texto (máximo 1024 para botones interactivos)
        if len(texto_limpio) > 900:
            texto_limpio = texto_limpio[:897] + "..."
        
        # Validar y limpiar botones
        botones_validos = []
        
        for i, boton in enumerate(botones[:3]):  # Máximo 3 botones
            try:
                if (boton.get("type") == "reply" and 
                    boton.get("reply", {}).get("id") and 
                    boton.get("reply", {}).get("title")):
                    
                    # Limpiar ID del botón
                    id_boton = str(boton["reply"]["id"]).strip()[:50]  # Máximo 50 chars
                    id_boton = ''.join(c for c in id_boton if c.isalnum() or c in ['_', '-'])
                    
                    # Limpiar título del botón
                    titulo = str(boton["reply"]["title"]).strip()
                    titulo = titulo.replace('\u2019', "'")
                    titulo = titulo.replace('\u201c', '"')
                    titulo = titulo.replace('\u201d', '"')
                    
                    # Limitar longitud del título (máximo 20 caracteres)
                    if len(titulo) > 20:
                        titulo = titulo[:17] + "..."
                    
                    # Validar que no esté vacío después de limpiar
                    if titulo and id_boton:
                        botones_validos.append({
                            "type": "reply",
                            "reply": {
                                "id": id_boton,
                                "title": titulo
                            }
                        })
                        
            except Exception as boton_error:
                logger.error(f"❌ Error procesando botón {i}: {boton_error}")
                continue
        
        # Si no hay botones válidos, usar texto simple
        if not botones_validos:
            logger.warning("⚠️ No se pudieron crear botones válidos - Usando texto simple")
            return crear_respuesta_texto_segura(texto_limpio)
        
        # Crear respuesta final
        respuesta = {
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {
                    "text": texto_limpio
                },
                "action": {
                    "buttons": botones_validos
                }
            }
        }
        
        # Log para debugging
        logger.info(f"✅ Respuesta con botones creada:")
        logger.info(f"   - Texto: {len(texto_limpio)} caracteres")
        logger.info(f"   - Botones: {len(botones_validos)}")
        for i, btn in enumerate(botones_validos):
            logger.info(f"     {i+1}. ID: '{btn['reply']['id']}', Título: '{btn['reply']['title']}'")
        
        return respuesta
        
    except Exception as e:
        logger.error(f"❌ Error creando respuesta con botones: {e}")
        return crear_respuesta_texto_segura(texto_cuerpo)
    
# 3. FUNCIÓN CORREGIDA PARA BOTONES SEGUROS
def crear_respuesta_botones():
    """Crea una respuesta con botones interactivos de preguntas frecuentes - VERSIÓN CORREGIDA"""
    try:
        logger.info("🔍 Buscando preguntas frecuentes para crear botones...")
        preguntas_menu = PreguntaFrecuente.objects.filter(
            activo=True
        ).exclude(
            es_saludo_inicial=True
        ).order_by("pregunta_frecuenta_id")[:3]
        
        logger.info(f"📊 Preguntas frecuentes encontradas: {preguntas_menu.count()}")
        
        if not preguntas_menu.exists():
            logger.info("⚠️ No hay preguntas frecuentes disponibles")
            return crear_respuesta_texto_segura("¡Hola! Soy Pratsy, tu asistente virtual. ¿En qué puedo ayudarte hoy?")

        botones = []
        for p in preguntas_menu:
            logger.info(f"🔹 Procesando pregunta ID {p.pregunta_frecuenta_id}: '{p.pregunta_corta_boton}'")
            
            if p.pregunta_corta_boton and len(p.pregunta_corta_boton.strip()) > 0:
                botones.append({
                    "type": "reply",
                    "reply": {
                        "id": f"faq_{p.pregunta_frecuenta_id}",
                        "title": p.pregunta_corta_boton.strip()
                    }
                })
        
        # Agregar botón de reserva
        botones.append({
            "type": "reply",
            "reply": {
                "id": "hacer_reserva",
                "title": "Hacer Reserva"
            }
        })

        texto_cuerpo = "¡Hola! Soy Pratsy 🤖\n\nSelecciona una opción:"
        
        return crear_respuesta_botones_ultra_segura(texto_cuerpo, botones)
        
    except Exception as e:
        logger.error(f"❌ Error al crear respuesta con botones: {e}")
        return crear_respuesta_texto_segura("¡Hola! Soy Pratsy, tu asistente virtual. ¿En qué puedo ayudarte hoy?")
    
# 5. DEBUGGING PARA WHATSAPP
def debug_whatsapp_payload(payload, to_number):
    """Función para debuggear payloads de WhatsApp antes de enviar"""
    logger.info("🔍 DEBUGGING WHATSAPP PAYLOAD:")
    logger.info(f"   Destinatario: {to_number}")
    logger.info(f"   Tipo: {payload.get('type')}")
    
    if payload.get('type') == 'text':
        texto = payload.get('text', {}).get('body', '')
        logger.info(f"   Texto length: {len(texto)}")
        logger.info(f"   Texto preview: {texto[:100]}...")
        
        # Buscar caracteres problemáticos
        problematicos = []
        for i, char in enumerate(texto):
            if ord(char) > 127:  # Caracteres no ASCII
                problematicos.append(f"'{char}' (pos: {i}, ord: {ord(char)})")
        
        if problematicos:
            logger.warning(f"   ⚠️ Caracteres no ASCII encontrados: {problematicos[:5]}")
    
    elif payload.get('type') == 'interactive':
        interactive = payload.get('interactive', {})
        body_text = interactive.get('body', {}).get('text', '')
        buttons = interactive.get('action', {}).get('buttons', [])
        
        logger.info(f"   Body length: {len(body_text)}")
        logger.info(f"   Botones: {len(buttons)}")
        
        for i, btn in enumerate(buttons):
            btn_id = btn.get('reply', {}).get('id', '')
            btn_title = btn.get('reply', {}).get('title', '')
            logger.info(f"     Botón {i+1}: ID='{btn_id}', Title='{btn_title}' ({len(btn_title)} chars)")
    
    # Serializar para verificar JSON válido
    try:
        json_str = json.dumps(payload, ensure_ascii=False, indent=2)
        logger.info("   ✅ JSON válido")
    except Exception as json_error:
        logger.error(f"   ❌ Error en JSON: {json_error}")

def consultar_disponibilidad_habitaciones(fecha=None) -> dict:
    """Consulta la disponibilidad de habitaciones para una fecha específica o general."""
    try:
        # Si no se especifica fecha, usar hoy
        if not fecha:
            fecha = date.today()
        elif isinstance(fecha, str):
            fecha = datetime.strptime(fecha, "%Y-%m-%d").date()
        
        # Obtener todas las habitaciones
        habitaciones_totales = Habitacion.objects.filter(disponible=True)
        total_habitaciones = habitaciones_totales.count()
        
        if total_habitaciones == 0:
            return crear_respuesta_texto("❌ No hay habitaciones configuradas en el sistema.")
        
        # Buscar reservas para la fecha específica
        inicio_dia = timezone.make_aware(datetime.combine(fecha, time.min))
        fin_dia = timezone.make_aware(datetime.combine(fecha, time.max))
        
        reservas_del_dia = Reserva.objects.filter(
            fecha_hora_inicio__date=fecha,
            estado__in=["pendiente", "confirmada", "llegada_confirmada"]
        )
        
        # Habitaciones ocupadas
        habitaciones_ocupadas = reservas_del_dia.values_list('habitacion_id', flat=True).distinct()
        habitaciones_disponibles = habitaciones_totales.exclude(habitacion_id__in=habitaciones_ocupadas)
        
        # Generar respuesta
        fecha_formateada = fecha.strftime("%d/%m/%Y")
        
        if habitaciones_disponibles.exists():
            mensaje = f"✅ *Disponibilidad para {fecha_formateada}*\n\n"
            mensaje += f"🏠 *Habitaciones disponibles:* {habitaciones_disponibles.count()} de {total_habitaciones}\n\n"
            
            for hab in habitaciones_disponibles[:5]:  # Mostrar máximo 5
                mensaje += f"• *{hab.nombre_habitacion}*\n"
                mensaje += f"  💰 ${hab.precio_por_hora:,}/hora\n"
                mensaje += f"  👥 Capacidad: {hab.capacidad} personas\n\n"
            
            if habitaciones_disponibles.count() > 5:
                mensaje += f"... y {habitaciones_disponibles.count() - 5} habitaciones más.\n\n"
            
            mensaje += "¿Le gustaría hacer una reserva? 📅"
            
            # Agregar botón de reserva
            return crear_respuesta_con_boton_reserva(mensaje)
        else:
            mensaje = f"❌ *Sin disponibilidad para {fecha_formateada}*\n\n"
            mensaje += f"Todas nuestras {total_habitaciones} habitaciones están ocupadas.\n\n"
            mensaje += "¿Le gustaría consultar otra fecha? 📅"
            
            return crear_respuesta_texto(mensaje)
            
    except Exception as e:
        logger.error(f"Error consultando disponibilidad: {e}")
        return crear_respuesta_texto("❌ Error consultando disponibilidad. Intente más tarde.")

def detectar_consulta_disponibilidad(mensaje: str) -> bool:
    """Detecta si un mensaje es una consulta sobre disponibilidad de habitaciones."""
    mensaje_lower = mensaje.lower().strip()
    
    # Palabras clave para detectar consultas de disponibilidad
    palabras_disponibilidad = [
        'disponible', 'disponibilidad', 'libre', 'libres', 'ocupado', 'ocupados',
        'habitacion', 'habitaciones', 'cuarto', 'cuartos', 'pieza', 'piezas',
        'hay', 'tienen', 'teneis', 'queda', 'quedan', 'existe', 'existen'
    ]
    
    # Frases comunes
    frases_disponibilidad = [
        'tienen habitaciones',
        'hay cuartos',
        'habitaciones disponibles',
        'cuartos libres',
        'hay disponibilidad',
        'tienen disponible',
        'que habitaciones tienen',
        'cuantas habitaciones',
        'hay piezas'
    ]
    
    # Verificar frases completas primero
    for frase in frases_disponibilidad:
        if frase in mensaje_lower:
            return True
    
    # Verificar combinaciones de palabras
    palabras_mensaje = mensaje_lower.split()
    coincidencias = sum(1 for palabra in palabras_disponibilidad if palabra in mensaje_lower)
    
    # Si tiene 2 o más palabras clave relacionadas, probablemente es consulta de disponibilidad
    return coincidencias >= 2

def mostrar_todas_las_reservas_funcionario() -> dict:
    """Muestra todas las reservas pendientes y confirmadas."""
    try:
        reservas = Reserva.objects.filter(
            estado__in=["pendiente", "confirmada"],
            fecha_hora_inicio__date__gte=date.today()
        ).order_by("fecha_hora_inicio")[:10]  # Máximo 10
        
        if not reservas.exists():
            return crear_respuesta_texto("No hay reservas pendientes.")
        
        mensaje = f"📋 *TODAS LAS RESERVAS* ({reservas.count()})\n\n"
        
        for reserva in reservas:
            fecha_str = reserva.fecha_hora_inicio.strftime("%d/%m %H:%M")
            cliente = reserva.cliente.nombre_cliente if reserva.cliente else "Cliente"
            habitacion = reserva.habitacion.nombre_habitacion if reserva.habitacion else "Hab"
            
            mensaje += f"#{reserva.reserva_id} - {cliente}\n"
            mensaje += f"📅 {fecha_str} - 🏠 {habitacion} - 📊 {reserva.estado}\n\n"
        
        mensaje += "💬 Escribe el # de reserva para gestionarla."
        
        return crear_respuesta_texto(mensaje)
        
    except Exception as e:
        logger.error(f"Error mostrando todas las reservas: {e}")
        return crear_respuesta_texto("❌ Error cargando reservas.")
    
def activar_modo_funcionario(telefono: str) -> dict:
    """Activa el modo funcionario y muestra las primeras 3 reservas."""
    try:
        funcionario = FuncionarioHotel.objects.get(telefono=telefono, activo=True)
        # Crear o actualizar sesión de funcionario (podrías usar una tabla o cache)
        # Por simplicidad, usaremos EstadoConversacion
        cliente = Cliente.objects.get(telefono=telefono)
        
        estado_funcionario, created = EstadoConversacion.objects.get_or_create(
            cliente=cliente,
            tipo="funcionario",
            defaults={
                "paso_actual": "menu_principal",
                "datos_reserva": {}
            }
        )
        estado_funcionario.paso_actual = "menu_principal"
        estado_funcionario.save()
        
        # Mostrar menú principal con primeras 3 reservas
        return mostrar_menu_funcionario()
        
    except FuncionarioHotel.DoesNotExist:
        return crear_respuesta_texto("❌ No tienes permisos de funcionario.")

def esta_en_modo_funcionario(telefono: str) -> bool:
    """Verifica si el funcionario tiene una sesión activa."""
    try:
        cliente = Cliente.objects.get(telefono=telefono)
        return EstadoConversacion.objects.filter(
            cliente=cliente,
            tipo="funcionario"
        ).exists()
    except:
        return False

def mostrar_menu_funcionario() -> dict:
    """Muestra el menú principal del funcionario con las primeras 3 reservas."""
    try:
        # Obtener las primeras 3 reservas pendientes/confirmadas de hoy en adelante
        reservas = Reserva.objects.filter(
            estado__in=["pendiente", "confirmada"],
            fecha_hora_inicio__date__gte=date.today()
        ).order_by("fecha_hora_inicio")[:3]
        
        mensaje = "👨‍💼 *PANEL DE FUNCIONARIO ACTIVADO*\n\n"
        mensaje += "📋 *PRIMERAS 3 RESERVAS:*\n\n"
        
        botones = []
        
        if reservas.exists():
            for i, reserva in enumerate(reservas, 1):
                fecha_str = reserva.fecha_hora_inicio.strftime("%d/%m %H:%M")
                cliente_nombre = reserva.cliente.nombre_cliente if reserva.cliente else "Cliente"
                habitacion = reserva.habitacion.nombre_habitacion if reserva.habitacion else "Hab"
                
                mensaje += f"{i}. *#{reserva.reserva_id}* - {cliente_nombre}\n"
                mensaje += f"   📅 {fecha_str} - 🏠 {habitacion}\n"
                mensaje += f"   📱 {reserva.telefono or 'N/A'} - 📊 {reserva.estado}\n\n"
                
                # Botones para esta reserva
                if reserva.estado == "pendiente":
                    botones.append({
                        "type": "reply",
                        "reply": {
                            "id": f"confirmar_{reserva.reserva_id}",
                            "title": f"✅ Confirmar #{reserva.reserva_id}"
                        }
                    })
                elif reserva.estado == "confirmada":
                    botones.append({
                        "type": "reply",
                        "reply": {
                            "id": f"llegada_{reserva.reserva_id}",
                            "title": f"🚪 Llegó #{reserva.reserva_id}"
                        }
                    })
        else:
            mensaje += "No hay reservas pendientes.\n\n"
        
        # Agregar opción manual
        mensaje += "💬 *COMANDOS:*\n"
        mensaje += "• Escribe el # de reserva para buscarla\n"
        mensaje += "• 'TODAS' para ver todas las reservas\n"
        mensaje += "• 'SALIR' para salir del modo funcionario"
        
        if botones:
            return crear_respuesta_botones_ultra_segura(mensaje, botones[:3])
        else:
            return crear_respuesta_texto(mensaje)
            
    except Exception as e:
        logger.error(f"Error mostrando menú funcionario: {e}")
        return crear_respuesta_texto("❌ Error accediendo al panel de funcionario.")

def procesar_mensaje_funcionario_mejorado(telefono: str, mensaje: str) -> dict:
    """Procesa comandos del funcionario autenticado."""
    try:
        mensaje_clean = mensaje.lower().strip()
        
        # Comando SALIR
        if mensaje_clean == "salir":
            return salir_modo_funcionario(telefono)
        
        # Comando TODAS (ver todas las reservas)
        if mensaje_clean == "todas":
            return mostrar_todas_las_reservas_funcionario()
        
        # Comando para confirmar reserva
        if mensaje.startswith("confirmar_"):
            reserva_id = mensaje.replace("confirmar_", "")
            return confirmar_reserva_funcionario(reserva_id, telefono)
        
        # Comando para marcar llegada
        if mensaje.startswith("llegada_"):
            reserva_id = mensaje.replace("llegada_", "")
            return marcar_llegada_funcionario(reserva_id, telefono)
        
        # Búsqueda manual por número de reserva
        if mensaje_clean.isdigit():
            return buscar_reserva_manual(mensaje_clean)
        
        # Si no reconoce el comando, mostrar menú
        return mostrar_menu_funcionario()
        
    except Exception as e:
        logger.error(f"Error procesando comando funcionario: {e}")
        return crear_respuesta_texto("❌ Error procesando comando. Intenta de nuevo.")

def salir_modo_funcionario(telefono: str) -> dict:
    """Sale del modo funcionario."""
    try:
        cliente = Cliente.objects.get(telefono=telefono)
        EstadoConversacion.objects.filter(cliente=cliente, tipo="funcionario").delete()
        
        return crear_respuesta_texto("👋 Has salido del modo funcionario. ¡Hasta luego!")
        
    except Exception as e:
        logger.error(f"Error saliendo del modo funcionario: {e}")
        return crear_respuesta_texto("❌ Error saliendo del modo funcionario.")


def confirmar_reserva_funcionario(reserva_id: str, telefono_funcionario: str) -> dict:
    """Confirma una reserva y envía notificación al cliente."""
    try:
        reserva = Reserva.objects.get(reserva_id=int(reserva_id))
        reserva.estado = "confirmada"
        reserva.save()
        
        # TODO: Aquí enviarías notificación al cliente
        # send_whatsapp_message(reserva.telefono, {mensaje de confirmación})
        
        mensaje_funcionario = f"✅ *Reserva #{reserva_id} CONFIRMADA*\n\n"
        mensaje_funcionario += f"Cliente: {reserva.cliente.nombre_cliente if reserva.cliente else 'Cliente'}\n"
        mensaje_funcionario += f"Habitación: {reserva.habitacion.nombre_habitacion if reserva.habitacion else 'Habitación'}\n"
        mensaje_funcionario += f"📱 Se enviará notificación al cliente: {reserva.telefono}\n\n"
        mensaje_funcionario += "¿Otro comando?"
        
        return crear_respuesta_texto(mensaje_funcionario)
        
    except Reserva.DoesNotExist:
        return crear_respuesta_texto(f"❌ No se encontró la reserva #{reserva_id}")
    except Exception as e:
        logger.error(f"Error confirmando reserva {reserva_id}: {e}")
        return crear_respuesta_texto(f"❌ Error confirmando la reserva.")


def marcar_llegada_funcionario(reserva_id: str, telefono_funcionario: str) -> dict:
    """Marca la llegada de un cliente y libera la habitación al terminar."""
    try:
        reserva = Reserva.objects.get(reserva_id=int(reserva_id))
        
        if reserva.estado != "confirmada":
            return crear_respuesta_texto(f"❌ La reserva #{reserva_id} debe estar confirmada primero.")
        
        reserva.estado = "llegada_confirmada"
        reserva.fecha_llegada = timezone.now()
        reserva.save()
        
        # Programar liberación automática de habitación (ver función siguiente)
        tiempo_liberacion = reserva.fecha_hora_fin
        
        mensaje = f"🚪 *LLEGADA CONFIRMADA #{reserva_id}*\n\n"
        mensaje += f"Cliente: {reserva.cliente.nombre_cliente if reserva.cliente else 'Cliente'}\n"
        mensaje += f"Habitación: {reserva.habitacion.nombre_habitacion if reserva.habitacion else 'Habitación'}\n"
        mensaje += f"⏰ Se liberará automáticamente: {tiempo_liberacion.strftime('%H:%M')}\n\n"
        mensaje += "¿Otro comando?"
        
        return crear_respuesta_texto(mensaje)
        
    except Reserva.DoesNotExist:
        return crear_respuesta_texto(f"❌ No se encontró la reserva #{reserva_id}")
    except Exception as e:
        logger.error(f"Error marcando llegada {reserva_id}: {e}")
        return crear_respuesta_texto(f"❌ Error marcando llegada.")


def buscar_reserva_manual(numero_reserva: str) -> dict:
    """Busca una reserva específica por número."""
    try:
        reserva = Reserva.objects.get(reserva_id=int(numero_reserva))
        
        fecha_str = reserva.fecha_hora_inicio.strftime("%d/%m/%Y %H:%M")
        fecha_fin_str = reserva.fecha_hora_fin.strftime("%H:%M")
        
        mensaje = f"🔍 *RESERVA #{numero_reserva}*\n\n"
        mensaje += f"👤 Cliente: {reserva.cliente.nombre_cliente if reserva.cliente else 'Cliente'}\n"
        mensaje += f"📱 Teléfono: {reserva.telefono or 'N/A'}\n"
        mensaje += f"📅 Fecha: {fecha_str} - {fecha_fin_str}\n"
        mensaje += f"🏠 Habitación: {reserva.habitacion.nombre_habitacion if reserva.habitacion else 'Habitación'}\n"
        mensaje += f"💰 Total: ${reserva.precio_total:,.0f}\n"
        mensaje += f"📊 Estado: *{reserva.estado.upper()}*\n\n"
        
        botones = []
        if reserva.estado == "pendiente":
            botones.append({
                "type": "reply",
                "reply": {
                    "id": f"confirmar_{reserva.reserva_id}",
                    "title": "✅ Confirmar"
                }
            })
        elif reserva.estado == "confirmada":
            botones.append({
                "type": "reply",
                "reply": {
                    "id": f"llegada_{reserva.reserva_id}",
                    "title": "🚪 Marcar llegada"
                }
            })
        
        if botones:
            return crear_respuesta_botones_ultra_segura(mensaje, botones)
        else:
            return crear_respuesta_texto(mensaje)
            
    except Reserva.DoesNotExist:
        return crear_respuesta_texto(f"❌ No se encontró la reserva #{numero_reserva}")
    except Exception as e:
        logger.error(f"Error buscando reserva {numero_reserva}: {e}")
        return crear_respuesta_texto("❌ Error buscando la reserva.")

def debug_configuracion_completa():
    """
    Función para verificar TODA la configuración
    LLAMAR UNA VEZ PARA DEBUGGING COMPLETO
    """
    logger.info("🔍 ===== DEBUGGING CONFIGURACIÓN COMPLETA =====")
    
    # 1. Verificar importaciones y SDK
    logger.info(f"1. SDK Disponible: {GENAI_SDK_AVAILABLE}")
    
    # 2. Verificar API Key
    api_key_status = "Sí" if GEMINI_API_KEY else "No"
    logger.info(f"2. GEMINI_API_KEY: {api_key_status}")
    
    # 3. Test de datetime
    logger.info("3. Testing métodos de fecha...")
    try:
        fecha_tz = timezone.now()
        logger.info(f"   ✅ timezone.now(): {fecha_tz}")
    except Exception as e:
        logger.error(f"   ❌ timezone.now(): {e}")
    try:
        fecha_dt = datetime.now()
        logger.info(f"   ✅ datetime.now(): {fecha_dt}")
    except Exception as e:
        logger.error(f"   ❌ datetime.now(): {e}")
    
    # 4. Test de modelos de IA (si disponible)
    if GENAI_SDK_AVAILABLE == True and GEMINI_API_KEY:
        logger.info("4. Testing nuevo Google GenAI SDK...")
        try:
            client = genai.Client(api_key=GEMINI_API_KEY)
            logger.info("   ✅ Cliente creado correctamente")
        except Exception as e:
            logger.error(f"   ❌ Error creando cliente: {e}")
        
    logger.info("🔍 ===== FIN DEBUGGING =====")
        
# --- WEBHOOK DE WHATSAPP ---
@csrf_exempt
def webhook_whatsapp(request):
    """
    Maneja las solicitudes del webhook de WhatsApp.
    Verifica el token de verificación y procesa los mensajes entrantes.
    """
    if request.method == "GET":
        mode = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        if mode == "subscribe" and token == WHATSAPP_VERIFY_TOKEN:
            logger.info("✅ Webhook verificado exitosamente")
            return HttpResponse(challenge, status=200)
        else:
            logger.warning("❌ Falló la verificación del webhook")
            return HttpResponse("Fallo la verificación", status=403)

    elif request.method == "POST":
        # Verificar conexión al inicio de cada request
        if not test_whatsapp_connection():
            logger.error("🚨 FALLO DE CONEXIÓN CON WHATSAPP - Revisa tu configuración")
        
        try:
            data = json.loads(request.body.decode("utf-8"))
            logger.info(f"📨 Webhook recibido: {json.dumps(data, indent=2)}")

            if "object" in data and data["object"] == "whatsapp_business_account":
                for entry in data["entry"]:
                    for change in entry["changes"]:
                        # Procesar mensajes entrantes
                        if "value" in change and "messages" in change["value"]:
                            for message in change["value"]["messages"]:
                                try:
                                    from_number = message["from"]
                                    
                                    # Crear o obtener cliente
                                    cliente, created = Cliente.objects.get_or_create(
                                        telefono=from_number,
                                        defaults={
                                            "nombre_cliente": f"Cliente {from_number}",
                                            "fecha_registro": timezone.now()
                                        }
                                    )
                                    if created:
                                        logger.info(f"👤 Nuevo cliente creado: {from_number}")
                                    
                                    # Crear o obtener conversación
                                    conversacion, _ = Conversacion.objects.get_or_create(
                                        cliente=cliente,
                                        activo=True # Asegurarse de que la conversación esté activa
                                    )
                                    
                                    # Procesar el mensaje según su tipo
                                    tipo_mensaje = message.get("type")
                                    mensaje_usuario = ""
                                    id_boton_presionado = None

                                    if tipo_mensaje == "text":
                                        mensaje_usuario = message["text"]["body"]
                                        logger.info(f"📝 Mensaje de texto recibido: {mensaje_usuario}")
                                        
                                    elif tipo_mensaje == "interactive" and "button_reply" in message["interactive"]:
                                        id_boton_presionado = message["interactive"]["button_reply"]["id"]
                                        mensaje_usuario = id_boton_presionado # Usar el ID del botón como mensaje para el agente
                                        logger.info(f"🔘 Botón presionado: {id_boton_presionado}")
                                    
                                    # Solo procesar si hay un mensaje válido (texto o botón)
                                    if mensaje_usuario:
                                        # Guardar mensaje del cliente
                                        Mensaje.objects.create(
                                            conversacion=conversacion,
                                            remitente="cliente",
                                            contenido=mensaje_usuario
                                        )
                                        
                                        # Obtener respuesta del agente
                                        payload_respuesta = obtener_respuesta_del_agente(
                                            mensaje_usuario, cliente, conversacion
                                        )
                                        
                                        # Intentar enviar respuesta
                                        mensaje_enviado = send_whatsapp_message(from_number, payload_respuesta)
                                        
                                        if mensaje_enviado:
                                            # Guardar la respuesta del agente si se envió exitosamente
                                            try:
                                                if payload_respuesta.get("type") == "text":
                                                    texto_respuesta = payload_respuesta["text"]["body"]
                                                elif payload_respuesta.get("type") == "interactive":
                                                    texto_respuesta = payload_respuesta["interactive"]["body"]["text"]
                                                else:
                                                    texto_respuesta = "Respuesta con formato especial"
                                                
                                                Mensaje.objects.create(
                                                    conversacion=conversacion,
                                                    remitente="agente",
                                                    contenido=texto_respuesta
                                                )
                                                logger.info(f"💾 Respuesta guardada en BD")
                                            except Exception as e:
                                                logger.error(f"❌ Error guardando respuesta del agente: {e}")
                                        else:
                                            logger.error(f"❌ No se pudo enviar respuesta a {from_number}")
                                            logger.error("🔧 Verifica la configuración de WhatsApp API")
                                
                                except Exception as e:
                                    logger.error(f"💥 Error procesando mensaje individual: {e}")

                        # Procesar actualizaciones de estado
                        elif "value" in change and "statuses" in change["value"]:
                            for status in change["value"]["statuses"]:
                                logger.info(f"📊 Actualización de estado: Mensaje {status["id"]} ahora está \'{status["status"]}\'")

            return HttpResponse("OK", status=200)
            
        except json.JSONDecodeError as e:
            logger.error(f"📝 Error decodificando JSON: {e}")
            return HttpResponse("JSON inválido", status=400)
        except Exception as e:
            logger.error(f"💥 Error inesperado en el webhook: {e}", exc_info=True)
            return HttpResponse("Error interno del servidor", status=500)
            
    return HttpResponse("Método no permitido", status=405)



