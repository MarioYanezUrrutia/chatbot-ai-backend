# backend/api/views.py
import json
import os
import logging
from openai import OpenAI
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from .models import (
    Cliente, Conversacion, Mensaje, TipoHabitacion,
    PreguntaFrecuente, Reserva, BaseConocimiento, PreguntaDesconocida
 )
from django.conf import settings
import google.generativeai as genai # Importamos la librería de Gemini
from django.db.models import Q 
import requests

# --- CONFIGURACIÓN ---
logger = logging.getLogger(__name__)

# --- NUEVA CONFIGURACIÓN PARA GEMINI CON DIAGNÓSTICO ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
print("="*60)
if GEMINI_API_KEY and len(GEMINI_API_KEY) > 10:
    # Imprimimos solo una parte de la clave por seguridad
    print(f"✅ DIAGNÓSTICO: Clave de API de Gemini encontrada y cargada.")
    print(f"   - La clave empieza con: {GEMINI_API_KEY[:5]}...")
    print(f"   - La clave termina con: ...{GEMINI_API_KEY[-4:]}")
    genai.configure(api_key=GEMINI_API_KEY)
    logger.info("✅ Configuración de Google Gemini válida")
else:
    print("❌ DIAGNÓSTICO: NO se encontró o es inválida la API Key de Gemini.")
    print("   - Asegúrate de que la variable GEMINI_API_KEY esté en tu archivo .env")
    logger.warning("⚠️ No se encontró API Key de Gemini. La funcionalidad de IA estará deshabilitada.")
print("="*60)

WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN')
WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN')
WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID')
WHATSAPP_API_URL = "https://graph.facebook.com/v19.0/"

# --- FUNCIÓN DE VALIDACIÓN DE CONFIGURACIÓN ---
def validar_configuracion_whatsapp():
    """Valida que todas las variables de WhatsApp estén configuradas"""
    missing = []
    if not WHATSAPP_ACCESS_TOKEN:
        missing.append('WHATSAPP_ACCESS_TOKEN')
    if not WHATSAPP_PHONE_NUMBER_ID:
        missing.append('WHATSAPP_PHONE_NUMBER_ID')
    if not WHATSAPP_VERIFY_TOKEN:
        missing.append('WHATSAPP_VERIFY_TOKEN')
    
    if missing:
        logger.error(f"❌ Variables de WhatsApp faltantes: {', '.join(missing)}")
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
    
    # Validar configuración antes de enviar
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

    try:
        response = requests.post(url, headers=headers, json=final_payload, timeout=30)
        
        # Log detallado de la respuesta
        logger.info(f"📥 Respuesta WhatsApp - Status: {response.status_code}")
        logger.info(f"   Response: {response.text}")
        
        if response.status_code == 200:
            logger.info(f"✅ Mensaje enviado exitosamente a {to_number}")
            return True
        else:
            # Manejar errores específicos
            try:
                error_data = response.json()
                error_code = error_data.get('error', {}).get('code')
                error_message = error_data.get('error', {}).get('message', 'Sin mensaje de error')
                
                if error_code == 10:  # OAuth Error
                    logger.error("🚨 ERROR DE AUTENTICACIÓN WHATSAPP:")
                    logger.error("   - El token de acceso puede haber expirado")
                    logger.error("   - Verifica que el Phone Number ID sea correcto")
                    logger.error("   - Los tokens temporales duran solo 24 horas")
                    logger.error("   - Ve a Facebook Developers > WhatsApp > API Setup")
                    logger.error(f"   - Error completo: {error_message}")
                elif error_code == 131026:  # Message undeliverable
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
        preguntas_menu = PreguntaFrecuente.objects.filter(activo=True).order_by('pregunta_frecuenta_id')[:3]
        logger.info(f"📊 Preguntas frecuentes encontradas: {preguntas_menu.count()}")
        
        if not preguntas_menu:
            logger.info("⚠️ No hay preguntas frecuentes disponibles - Usando mensaje de texto simple")
            return crear_respuesta_texto("¡Hola! Soy Pratsy, tu asistente virtual. ¿En qué puedo ayudarte hoy?")

        # Validar que las preguntas tengan los datos necesarios
        botones = []
        for p in preguntas_menu:
            logger.info(f"🔹 Procesando pregunta ID {p.pregunta_frecuenta_id}: '{p.pregunta_corta_boton}'")
            if p.pregunta_corta_boton and len(p.pregunta_corta_boton.strip()) > 0:
                # WhatsApp limita los títulos de botones a 20 caracteres
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

        # Texto del cuerpo - debe ser claro y no muy largo
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

# --- "CEREBRO" DEL BOT ---
def obtener_respuesta_del_agente(mensaje_usuario: str, cliente: Cliente, conversacion: Conversacion):
    """
    El "cerebro" del bot con logs de depuración detallados y con la lógica para guardar preguntas desconocidas..
    """
    logger.info(f"\n--- INICIO PROCESAMIENTO CEREBRO ---")
    logger.info(f"💬 Mensaje original del usuario: '{mensaje_usuario}'")
    
    mensaje_limpio = mensaje_usuario.lower().strip()
    palabras = set(mensaje_limpio.split())

    # --- NUEVO: DETECCIÓN DE SALUDO INICIAL ---
    PALABRAS_DE_SALUDO = {'hola', 'buenas', 'info', 'informacion', 'empezar', 'ayuda', 'start'}
    if palabras.intersection(PALABRAS_DE_SALUDO):
        logger.info("👋 Detectado saludo inicial. Buscando mensaje de bienvenida configurado...")
        # Busca la pregunta marcada como saludo inicial
        saludo_configurado = PreguntaFrecuente.objects.filter(es_saludo_inicial=True, activo=True).first()
        if saludo_configurado:
            # Usa la respuesta de esa pregunta como cuerpo y muestra los botones
            texto_cuerpo = saludo_configurado.respuesta
            botones = []
            preguntas_menu = PreguntaFrecuente.objects.filter(activo=True).exclude(pk=saludo_configurado.pk).order_by('pregunta_frecuenta_id')[:3]
            for p in preguntas_menu:
                botones.append({"type": "reply", "reply": {"id": f"faq_{p.pregunta_frecuenta_id}", "title": p.pregunta_corta_boton}})
            
            return {
                "type": "interactive",
                "interactive": {
                    "type": "button",
                    "body": {"text": texto_cuerpo},
                    "action": {"buttons": botones}
                }
            }

    # --- CAPA 1: BÚSQUEDA EN LA BASE DE DATOS ---
    logger.info("🧠 CAPA 1: Buscando respuesta en la Base de Datos...")
    try:
        # ... (lógica de búsqueda en BD) ...
        q_preguntas = Q()
        for palabra in palabras:
            q_preguntas |= Q(palabras_clave__icontains=palabra) | Q(pregunta_larga__icontains=palabra)
        pregunta_coincidente = PreguntaFrecuente.objects.filter(q_preguntas, activo=True).first()
        if pregunta_coincidente:
            logger.info(f"✔️ ÉXITO CAPA 1: Encontrada PreguntaFrecuente ID {pregunta_coincidente.pregunta_frecuenta_id}.")
            logger.info("--- FIN PROCESAMIENTO CEREBRO ---\n")
            return crear_respuesta_texto(pregunta_coincidente.respuesta)

        # ... (lógica de búsqueda de habitación) ...
        logger.info("   - No se encontró en Preguntas Frecuentes. Buscando en Tipos de Habitación...")
        q_habitaciones = Q()
        for palabra in palabras:
            q_habitaciones |= Q(palabras_clave__icontains=palabra)
        habitacion_coincidente = TipoHabitacion.objects.filter(q_habitaciones, activo=True).first()
        if habitacion_coincidente:
            logger.info(f"✔️ ÉXITO CAPA 1: Encontrado TipoHabitacion '{habitacion_coincidente.nombre_tipo_habitacion}'.")
            logger.info("--- FIN PROCESAMIENTO CEREBRO ---\n")
            # ... (código para crear la respuesta de la habitación) ...
            respuesta_texto = (f"¡Te cuento sobre la {habitacion_coincidente.nombre_tipo_habitacion}!\n\n"
                             f"{habitacion_coincidente.descripcion}\n\n"
                             f"💰 Precio por noche: ${habitacion_coincidente.precio_por_noche:,.0f} CLP")
            return crear_respuesta_texto(respuesta_texto)

        logger.info("   - No se encontró respuesta en la Base de Datos.")

    except Exception as e:
        logger.error(f"❌ Error en búsqueda de base de datos: {e}")

    # --- CAPA 2: INTENTO DE CONEXIÓN CON GOOGLE GEMINI ---
    logger.info("🧠 CAPA 2: Intentando contactar a la IA (Google Gemini)...")
    if GEMINI_API_KEY:
        logger.info("🤖 Consultando a Google Gemini con historial...")
        try:
            model = genai.GenerativeModel('gemini-1.5-flash-latest')
            # --- LÓGICA DE HISTORIAL ---
            # Obtenemos los últimos 6 mensajes (3 turnos de conversación)
            historial_mensajes = Mensaje.objects.filter(
                conversacion=conversacion
            ).order_by('-timestamp')[:6]
            
            # Reconstruimos el historial en el formato que Gemini espera
            historial_gemini = []
            for msg in reversed(historial_mensajes): # Invertimos para tener el orden cronológico
                role = 'user' if msg.remitente == 'cliente' else 'model'
                historial_gemini.append({'role': role, 'parts': [msg.contenido]})
            
            # Iniciamos una sesión de chat con el historial
            chat_session = model.start_chat(history=historial_gemini)

            prompt = (
                "Eres Pratsy, un asistente de motel amigable. Tu objetivo es ayudar al usuario. "
                "Usa el historial de la conversación para dar una respuesta coherente y relevante. "
                "No respondas preguntas técnicas que competen a información directa del Hotel"
                "Sé breve y directo. La pregunta actual del usuario es: "
                f"'{mensaje_usuario}'"
            )
            logger.info(f"   - Enviando a Gemini el siguiente prompt: '{prompt}'")
            
            respuesta_ia = model.generate_content(prompt)
            
            logger.info(f"✔️ ÉXITO CAPA 2: Respuesta recibida de Gemini.")
            logger.info(f"   - Texto de la IA: '{respuesta_ia.text}'")
            logger.info("--- FIN PROCESAMIENTO CEREBRO ---\n")
            return crear_respuesta_texto(respuesta_ia.text)
            
        except Exception as e:
            logger.error(f"❌ ERROR CAPA 2: La llamada a Gemini falló.")
            logger.error(f"   - Motivo del error: {e}")
            # Si falla, simplemente continúa al respaldo
    else:
        logger.warning("   - Saltando IA: No hay API Key de Gemini configurada.")

    # --- CAPA 3: RESPUESTA DE RESPALDO ---
    logger.info("🧠 CAPA 3: Ejecutando respuesta de respaldo (botones).")
    # ... (lógica para guardar pregunta desconocida y crear botones) ...
    try:
        if not PreguntaDesconocida.objects.filter(cliente=cliente, texto_pregunta=mensaje_usuario).exists():
            PreguntaDesconocida.objects.create(texto_pregunta=mensaje_usuario, cliente=cliente)
            logger.info(f"   - Pregunta desconocida guardada para revisión.")
    except Exception as e:
        logger.error(f"   - Error guardando pregunta desconocida: {e}")
    
    logger.info("--- FIN PROCESAMIENTO CEREBRO ---\n")
    return crear_respuesta_botones()

    # --- VISTA PRINCIPAL DEL WEBHOOK ---

@csrf_exempt
def whatsapp_webhook(request):
    if request.method == 'GET':
        # Lógica de verificación
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')
        
        if mode == 'subscribe' and token == WHATSAPP_VERIFY_TOKEN:
            logger.info("✅ Verificación de webhook exitosa")
            return HttpResponse(challenge, status=200)
        else:
            logger.warning("❌ Falló la verificación del webhook")
            return HttpResponse("Fallo la verificación", status=403)

    elif request.method == 'POST':
        # Verificar conexión al inicio de cada request
        if not test_whatsapp_connection():
            logger.error("🚨 FALLO DE CONEXIÓN CON WHATSAPP - Revisa tu configuración")
            # Aún procesamos el webhook pero sabemos que el envío fallará
        
        try:
            data = json.loads(request.body.decode('utf-8'))
            logger.info(f"📨 Webhook recibido: {json.dumps(data, indent=2)}")

            if 'object' in data and data['object'] == 'whatsapp_business_account':
                for entry in data['entry']:
                    for change in entry['changes']:
                        # Procesar mensajes entrantes
                        if 'value' in change and 'messages' in change['value']:
                            for message in change['value']['messages']:
                                try:
                                    from_number = message['from']
                                    
                                    # Crear o obtener cliente
                                    cliente, created = Cliente.objects.get_or_create(
                                        telefono=from_number,
                                        defaults={'nombre_cliente': f'Cliente {from_number}'}
                                    )
                                    if created:
                                        logger.info(f"👤 Nuevo cliente creado: {from_number}")
                                    
                                    # Crear o obtener conversación
                                    conversacion, _ = Conversacion.objects.get_or_create(
                                        cliente=cliente,
                                        activo=True
                                    )
                                    
                                    # Procesar el mensaje según su tipo
                                    tipo_mensaje = message.get('type')
                                    mensaje_usuario = ""

                                    if tipo_mensaje == 'text':
                                        mensaje_usuario = message['text']['body']
                                        logger.info(f"📝 Mensaje de texto recibido: {mensaje_usuario}")
                                        
                                    elif tipo_mensaje == 'interactive' and 'button_reply' in message['interactive']:
                                        id_boton = message['interactive']['button_reply']['id']
                                        logger.info(f"🔘 Botón presionado: {id_boton}")
                                        if id_boton.startswith('faq_'):
                                            try:
                                                faq_id = int(id_boton.split('_')[1])
                                                logger.info(f"🔍 Buscando pregunta frecuente con ID: {faq_id}")
                                                pregunta = PreguntaFrecuente.objects.get(
                                                    pregunta_frecuenta_id=faq_id,
                                                    activo=True
                                                )
                                                # Usar directamente la respuesta de la FAQ, no la pregunta
                                                mensaje_usuario = f"Información sobre: {pregunta.pregunta_corta_boton}"
                                                logger.info(f"✅ FAQ encontrada: {pregunta.pregunta_corta_boton}")
                                                
                                                # Crear respuesta directamente con la FAQ
                                                payload_respuesta = crear_respuesta_texto(pregunta.respuesta)
                                                
                                                # Enviar la respuesta directamente sin pasar por obtener_respuesta_del_agente
                                                mensaje_enviado = send_whatsapp_message(from_number, payload_respuesta)
                                                
                                                if mensaje_enviado:
                                                    # Guardar ambos mensajes
                                                    Mensaje.objects.create(
                                                        conversacion=conversacion,
                                                        remitente='cliente',
                                                        contenido=mensaje_usuario
                                                    )
                                                    Mensaje.objects.create(
                                                        conversacion=conversacion,
                                                        remitente='agente',
                                                        contenido=pregunta.respuesta
                                                    )
                                                    logger.info(f"💾 Respuesta FAQ guardada en BD")
                                                
                                                # Saltar el procesamiento normal
                                                continue
                                                
                                            except (ValueError, PreguntaFrecuente.DoesNotExist) as e:
                                                logger.error(f"❌ Error procesando botón FAQ: {e}")
                                                mensaje_usuario = "Información sobre servicios"
                                    
                                    # Solo procesar si hay un mensaje válido
                                    if mensaje_usuario:
                                        # Guardar mensaje del cliente
                                        Mensaje.objects.create(
                                            conversacion=conversacion,
                                            remitente='cliente',
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
                                                if payload_respuesta.get('type') == 'text':
                                                    texto_respuesta = payload_respuesta['text']['body']
                                                elif payload_respuesta.get('type') == 'interactive':
                                                    texto_respuesta = payload_respuesta['interactive']['body']['text']
                                                else:
                                                    texto_respuesta = "Respuesta con formato especial"
                                                
                                                Mensaje.objects.create(
                                                    conversacion=conversacion,
                                                    remitente='agente',
                                                    contenido=texto_respuesta
                                                )
                                                logger.info(f"💾 Respuesta guardada en BD")
                                            except Exception as e:
                                                logger.error(f"❌ Error guardando respuesta del agente: {e}")
                                        else:
                                            # Solo log del fallo - no intentar reenvío
                                            logger.error(f"❌ No se pudo enviar respuesta a {from_number}")
                                            logger.error("🔧 Verifica la configuración de WhatsApp API")
                                
                                except Exception as e:
                                    logger.error(f"💥 Error procesando mensaje individual: {e}")
                                    # Continuar con el siguiente mensaje

                        # Procesar actualizaciones de estado
                        elif 'value' in change and 'statuses' in change['value']:
                            for status in change['value']['statuses']:
                                logger.info(f"📊 Actualización de estado: Mensaje {status['id']} ahora está '{status['status']}'")

            return HttpResponse("OK", status=200)
            
        except json.JSONDecodeError as e:
            logger.error(f"📝 Error decodificando JSON: {e}")
            return HttpResponse("JSON inválido", status=400)
        except Exception as e:
            logger.error(f"💥 Error inesperado en el webhook: {e}", exc_info=True)
            return HttpResponse("Error interno del servidor", status=500)
            
    return HttpResponse("Método no permitido", status=405)