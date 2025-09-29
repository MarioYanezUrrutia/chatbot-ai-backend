# backend/api/views.py
import json
import os
import logging
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.utils import timezone
from .models import Cliente, Conversacion, Mensaje, TipoHabitacion, PreguntaFrecuente, Categoria # Importamos nuestros modelos
from django.db.models import Q 
import requests

# Configuración básica de logging para ver lo que pasa
logger = logging.getLogger(__name__ )

# --- CONFIGURACIÓN DE WHATSAPP (¡IMPORTANTE!) ---
# Estas variables deberían venir de las variables de entorno para producción
# Por ahora, las definimos aquí para que sea más fácil de entender.
# En un entorno real, usarías algo como os.environ.get('WHATSAPP_VERIFY_TOKEN')
#Las siguientes variables son con el segundo valor por defecto, lo que por seguridad no es recomendable, por eso quedan comentadas
# WHATSAPP_VERIFY_TOKEN = os.environ.get('WHATSAPP_VERIFY_TOKEN', 'TU_TOKEN_DE_VERIFICACION_SECRETO')
# WHATSAPP_ACCESS_TOKEN = os.environ.get('WHATSAPP_ACCESS_TOKEN', 'TU_TOKEN_DE_ACCESO_TEMPORAL_DE_META')
# WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', 'TU_ID_DE_NUMERO_DE_TELEFONO_DE_META')
WHATSAPP_VERIFY_TOKEN = os.environ['WHATSAPP_VERIFY_TOKEN']
WHATSAPP_ACCESS_TOKEN = os.environ['WHATSAPP_ACCESS_TOKEN']
WHATSAPP_PHONE_NUMBER_ID = os.environ['WHATSAPP_PHONE_NUMBER_ID']

# URL base de la API de WhatsApp Cloud
WHATSAPP_API_URL = "https://graph.facebook.com/v19.0/" # Versión actual de la API

@csrf_exempt # Deshabilita la protección CSRF para esta vista (necesario para webhooks externos )
def whatsapp_webhook(request):
    """
    Vista para manejar las peticiones del webhook de WhatsApp.
    Recibe peticiones GET para verificación y POST para mensajes.
    """
    if request.method == 'GET':
        # --- VERIFICACIÓN DEL WEBHOOK (Esta parte ya funciona bien) ---
        mode = request.GET.get('hub.mode')
        token = request.GET.get('hub.verify_token')
        challenge = request.GET.get('hub.challenge')

        if mode == 'subscribe' and token == WHATSAPP_VERIFY_TOKEN:
            logger.info("Webhook verificado exitosamente!")
            return HttpResponse(challenge, status=200)
        else:
            logger.warning("Fallo la verificación del webhook. Token o modo incorrecto.")
            return HttpResponse("Fallo la verificación", status=403)

    elif request.method == 'POST':
        # --- PROCESAMIENTO DE MENSAJES ENTRANTES ---
        try:
            data = json.loads(request.body.decode('utf-8'))
            logger.info(f"Datos recibidos del webhook: {json.dumps(data, indent=2)}")

            if 'object' in data and data['object'] == 'whatsapp_business_account':
                for entry in data['entry']:
                    for change in entry['changes']:
                        if change['field'] == 'messages':

                            # --- INICIO DEL ÚNICO BLOQUE LÓGICO ---

                            # 1. ¿Es un mensaje nuevo de un usuario?
                            if 'messages' in change['value']:
                                for message in change['value']['messages']:
                                    if message['type'] == 'text':
                                        from_number = message['from']
                                        message_body = message['text']['body']
                                        logger.info(f"Mensaje de {from_number}: {message_body}")

                                        # --- Lógica para guardar el mensaje y responder ---
                                        # (Movimos todo el código de la BD aquí dentro)

                                        # 1. Buscar o crear el cliente
                                        cliente, created = Cliente.objects.get_or_create(
                                            telefono=from_number,
                                            defaults={'nombre': f'Cliente_{from_number}'}
                                        )
                                        if created:
                                            logger.info(f"Nuevo cliente registrado: {cliente.telefono}")

                                        # 2. Buscar o crear una conversación activa
                                        conversacion, created_conv = Conversacion.objects.get_or_create(
                                            cliente=cliente,
                                            activo=True,
                                            defaults={'inicio_conversacion': timezone.now()}
                                        )
                                        if not created_conv and hasattr(conversacion, 'ultima_interaccion'):
                                            conversacion.ultima_interaccion = timezone.now()
                                            conversacion.save()

                                        # 3. Guardar el mensaje del cliente
                                        Mensaje.objects.create(
                                            conversacion=conversacion,
                                            remitente='cliente',
                                            contenido=message_body
                                        )
                                        logger.info(f"Mensaje del cliente guardado: {message_body}")

                                        # 4. Lógica del Agente de IA
                                        # respuesta_agente = f"¡Hola! Recibí tu mensaje: '{message_body}'. Soy el asistente virtual de Moteles Prats. ¿En qué puedo ayudarte hoy?"
                                        # =================================================================
                                        # PASO 4: LLAMAR AL "CEREBRO" PARA OBTENER LA RESPUESTA
                                        # =================================================================
                                        respuesta_agente = obtener_respuesta_del_agente(message_body)
                                        
                                        # 5. Enviar la respuesta a WhatsApp
                                        send_whatsapp_message(from_number, respuesta_agente)

                                        # 6. Guardar la respuesta del agente
                                        Mensaje.objects.create(
                                            conversacion=conversacion,
                                            remitente='agente',
                                            contenido=respuesta_agente
                                        )
                                        logger.info(f"Respuesta del agente enviada y guardada: {respuesta_agente}")

                                    else:
                                        logger.info(f"Tipo de mensaje no soportado: {message['type']}")

                            # 2. ¿Es una actualización de estado?
                            elif 'statuses' in change['value']:
                                for status in change['value']['statuses']:
                                    logger.info(f"Actualización de estado recibida: El mensaje {status['id']} ahora está '{status['status']}'")
                            
                            # --- FIN DEL ÚNICO BLOQUE LÓGICO ---

            return HttpResponse("OK", status=200)

        except Exception as e:
            logger.error(f"Error inesperado en el webhook: {e}", exc_info=True)
            return HttpResponse("Error interno del servidor", status=500)
            
    return HttpResponse("Método no permitido", status=405)


# def send_whatsapp_message(to_number, message_body):
#     """
#     Función para enviar un mensaje de texto a través de la API de WhatsApp Cloud.
#     """
#     headers = {
#         "Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}",
#         "Content-Type": "application/json",
#     }
#     payload = {
#         "messaging_product": "whatsapp",
#         "to": to_number,
#         "type": "text",
#         "text": {"body": message_body},
#     }
#     url = f"{WHATSAPP_API_URL}{WHATSAPP_PHONE_NUMBER_ID}/messages"

#     try:
#         response = requests.post(url, headers=headers, json=payload)
#         response.raise_for_status() # Lanza una excepción para códigos de estado HTTP de error
#         logger.info(f"Mensaje enviado a {to_number}: {response.json()}")
#         return True
#     except requests.exceptions.RequestException as e:
#         logger.error(f"Error al enviar mensaje a WhatsApp: {e}")
#         if hasattr(e, 'response') and e.response is not None:
#             logger.error(f"Respuesta de error de WhatsApp: {e.response.text}")
#         return False
    
def obtener_respuesta_del_agente(mensaje_usuario: str) -> str:
    """
    El "cerebro" del bot.
    Analiza el mensaje del usuario y busca una respuesta en la base de datos.
    """
    mensaje_limpio = mensaje_usuario.lower().strip()
    # palabras = set(mensaje_limpio.split()) # Usamos un set para búsquedas eficientes

    # # 1. Buscar coincidencias en Preguntas Frecuentes
    # # Construimos una consulta que busca si alguna de las palabras clave está en el mensaje
    # q_objects = Q()
    # for palabra in palabras:
    #     q_objects |= Q(palabras_clave__icontains=palabra)
    
    # pregunta_coincidente = PreguntaFrecuente.objects.filter(q_objects).first()
    # if pregunta_coincidente:
    #     return pregunta_coincidente.respuesta

    # # 2. Buscar coincidencias en Tipos de Habitación
    # q_objects = Q()
    # for palabra in palabras:
    #     q_objects |= Q(palabras_clave__icontains=palabra)

    # habitacion_coincidente = TipoHabitacion.objects.filter(q_objects).first()
    # if habitacion_coincidente:
    #     respuesta = (
    #         f"¡Claro! Aquí tienes la información sobre la {habitacion_coincidente.nombre_tipo_habitacion}:\n\n"
    #         f"*{habitacion_coincidente.descripcion}*\n\n"
    #         f"El precio por noche es de ${habitacion_coincidente.precio_por_noche:,.0f} CLP."
    #     )
    #     return respuesta

    # # 3. Respuesta por defecto si no se encuentra nada
    # return (
    #     "¡Hola! Gracias por tu mensaje. Soy el asistente virtual de Gráfica GyG. "
    #     "Puedes preguntarme sobre nuestros precios, horarios o cualquier consulta de tu interés. "
    #     "¿En qué puedo ayudarte?"
    # )

def send_whatsapp_message(to_number, message_payload):
    """
    Función MEJORADA para enviar mensajes. Ahora acepta un 'payload' completo.
    Esto nos permite enviar texto, botones, imágenes, etc.
    """
    headers = {"Authorization": f"Bearer {WHATSAPP_ACCESS_TOKEN}"}
    url = f"{WHATSAPP_API_URL}{WHATSAPP_PHONE_NUMBER_ID}/messages"
    
    # El payload base siempre es el mismo
    base_payload = {
        "messaging_product": "whatsapp",
        "to": to_number,
    }
    # Combinamos el payload base con el específico (texto, botones, etc.)
    final_payload = {**base_payload, **message_payload}

    try:
        response = requests.post(url, headers=headers, json=final_payload)
        response.raise_for_status()
        logger.info(f"Mensaje enviado a {to_number}: {response.json()}")
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al enviar mensaje a WhatsApp: {e.response.text if e.response else e}")
        return False

def obtener_respuesta_del_agente(mensaje_usuario: str, cliente: Cliente):
    """
    El "cerebro" MEJORADO del bot.
    Analiza la intención y devuelve un payload de mensaje para WhatsApp.
    """
    mensaje_limpio = mensaje_usuario.lower().strip()
    palabras = set(mensaje_limpio.split())

    # --- Búsqueda de Intención por Categoría ---
    q_objects = Q()
    for palabra in palabras:
        q_objects |= Q(palabras_clave__icontains=palabra)
    
    categoria_coincidente = Categoria.objects.filter(q_objects).first()

    # --- Lógica de Respuesta Basada en la Intención ---

    # 1. Si la intención es sobre PRECIOS
    if categoria_coincidente and categoria_coincidente.nombre == "Precios":
        habitaciones = TipoHabitacion.objects.all()
        if not habitaciones:
            return {"type": "text", "text": {"body": "Actualmente no tengo información sobre las habitaciones. Por favor, contacta con recepción."}}
        
        respuesta_texto = "¡Claro! Aquí tienes nuestros tipos de habitación y precios:\n\n"
        for hab in habitaciones:
            respuesta_texto += f"*{hab.nombre}* - ${hab.precio_por_noche:,.0f} CLP por noche.\n_{hab.descripcion}_\n\n"
        
        return {"type": "text", "text": {"body": respuesta_texto}}

    # 2. Si la intención es sobre RESERVAS
    if categoria_coincidente and categoria_coincidente.nombre == "Reservas":
        # Aquí iría la lógica compleja de disponibilidad que dejamos para el futuro.
        # Por ahora, iniciamos el flujo de reserva.
        return {"type": "text", "text": {"body": "¡Perfecto! Para hacer una reserva, necesitaré saber la fecha de check-in y la cantidad de noches. ¿Cuándo te gustaría visitarnos?"}}

    # 3. Si es una Pregunta Frecuente (Horarios, Ubicación, etc.)
    pregunta_coincidente = PreguntaFrecuente.objects.filter(categoria=categoria_coincidente).first()
    if pregunta_coincidente:
        return {"type": "text", "text": {"body": pregunta_coincidente.respuesta_completa}}