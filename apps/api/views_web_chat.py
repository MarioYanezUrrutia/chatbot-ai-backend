# backend/api/views_web_chat.py
import json
import os
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
# import google.generativeai as genai
from django.db.models import Q
from .models import (
    Cliente, Conversacion, Mensaje, TipoHabitacion,
    PreguntaFrecuente, PreguntaDesconocida
)

logger = logging.getLogger(__name__)

# Configuración de Gemini (reutilizar la existente)
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
# if GEMINI_API_KEY:
#     genai.configure(api_key=GEMINI_API_KEY)

# --- FUNCIÓN PARA PROCESAR RESPUESTA CON IA (REUTILIZADA) ---
def procesar_respuesta_con_ia_web(respuesta_bd, mensaje_usuario, historial_conversacion):
    """
    Procesa la respuesta de la BD a través de la IA para hacerla más amigable
    Adaptada para el chat web
    """
    logger.info("🤖 Procesando respuesta web con IA...")
    
    if not GEMINI_API_KEY:
        logger.warning("⚠️ No hay API Key de Gemini - Devolviendo respuesta original")
        return respuesta_bd
    
    try:
        # model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Construir contexto del historial
        historial_context = ""
        for msg in historial_conversacion[-4:]:  # Últimos 4 mensajes
            role = 'Cliente' if msg['remitente'] == 'cliente' else 'Pratsy'
            historial_context += f"{role}: {msg['contenido']}\n"
        
        prompt = f"""
Eres Pratsy, un asistente virtual amigable y profesional de un motel. Estás conversando por chat web con un cliente.

CONTEXTO DE LA CONVERSACIÓN:
{historial_context}

PREGUNTA DEL CLIENTE: {mensaje_usuario}
RESPUESTA TÉCNICA DE LA BASE DE DATOS: {respuesta_bd}

INSTRUCCIONES:
1. Reformula la respuesta técnica de manera amigable y conversacional
2. Mantén toda la información importante
3. Usa un tono cálido y profesional para chat web
4. Hazlo sentir como una conversación natural
5. Sé conciso pero completo
6. Puedes usar emojis apropiados para mejorar la experiencia
7. Si es información sobre precios, horarios o servicios, sé claro y directo

Reformula la respuesta:
"""
        
        # respuesta_ia = model.generate_content(prompt)
        
        # if respuesta_ia and respuesta_ia.text:
        #     logger.info("✅ Respuesta web reformulada exitosamente por IA")
        #     return respuesta_ia.text.strip()
        # else:
        #     logger.warning("⚠️ IA no devolvió respuesta válida - Usando respuesta original")
        #     return respuesta_bd
            
    except Exception as e:
        logger.error(f"❌ Error procesando con IA: {e}")
        return respuesta_bd

# --- FUNCIÓN PARA PROCESAR PREGUNTA DESCONOCIDA CON IA (ADAPTADA) ---
def procesar_pregunta_desconocida_con_ia_web(mensaje_usuario, historial_conversacion):
    """
    Procesa preguntas desconocidas con IA para el chat web
    """
    logger.info("🤖 Procesando pregunta desconocida web con IA...")
    
    if not GEMINI_API_KEY:
        return "Lo siento, no tengo información específica sobre eso. ¿Podrías reformular tu pregunta o consultar sobre nuestros servicios principales?"
    
    try:
        # model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Construir contexto del historial
        historial_context = ""
        for msg in historial_conversacion[-4:]:
            role = 'Cliente' if msg['remitente'] == 'cliente' else 'Pratsy'
            historial_context += f"{role}: {msg['contenido']}\n"
        
        prompt = f"""
Eres Pratsy, un asistente virtual amigable de un motel. Un cliente te hizo una pregunta por chat web que no está en tu base de conocimiento.

CONTEXTO DE LA CONVERSACIÓN:
{historial_context}

PREGUNTA DEL CLIENTE: {mensaje_usuario}

INSTRUCCIONES:
1. Reconoce amablemente que no tienes esa información específica
2. Si la pregunta es general, ofrece ayuda básica si puedes
3. Si es técnica del motel, disculpate y sugiere alternativas
4. Mantén un tono empático y profesional para chat web
5. Ofrece ayuda con los servicios principales del motel
6. Sé conciso pero cálido
7. Puedes usar emojis apropiados
8. No inventes información que no tengas

Responde de manera empática:
"""
        
        # respuesta_ia = model.generate_content(prompt)
        
        # if respuesta_ia and respuesta_ia.text:
        #     return respuesta_ia.text.strip()
        # else:
        #     return "Lo siento, no tengo información específica sobre eso. ¿Podrías reformular tu pregunta o consultar sobre nuestros servicios principales?"
            
    except Exception as e:
        logger.error(f"❌ Error procesando pregunta desconocida con IA: {e}")
        return "Disculpa, en este momento no puedo ayudarte con esa consulta específica. ¿Te gustaría conocer sobre nuestros servicios principales?"

# --- CEREBRO DEL BOT PARA WEB ---
def obtener_respuesta_agente_web(mensaje_usuario, session_id, historial_conversacion):
    """
    Cerebro del bot adaptado para chat web
    """
    logger.info(f"\n--- PROCESAMIENTO CEREBRO WEB ---")
    logger.info(f"💬 Mensaje: '{mensaje_usuario}' | Sesión: {session_id}")
    
    mensaje_limpio = mensaje_usuario.lower().strip()
    palabras = set(mensaje_limpio.split())

    # 1. DETECCIÓN DE SALUDO INICIAL
    PALABRAS_DE_SALUDO = {'hola', 'buenas', 'info', 'informacion', 'empezar', 'ayuda', 'start', 'hey', 'buenos'}
    if palabras.intersection(PALABRAS_DE_SALUDO) and len(historial_conversacion) <= 1:
        logger.info("👋 Detectado saludo inicial web")
        
        saludo_configurado = PreguntaFrecuente.objects.filter(
            es_saludo_inicial=True, 
            activo=True
        ).first()
        
        if saludo_configurado:
            respuesta_amigable = procesar_respuesta_con_ia_web(
                saludo_configurado.respuesta, 
                mensaje_usuario, 
                historial_conversacion
            )
            
            # Obtener botones de preguntas frecuentes
            preguntas_menu = PreguntaFrecuente.objects.filter(
                activo=True
            ).exclude(
                es_saludo_inicial=True
            ).order_by('pregunta_frecuenta_id')[:5]
            
            botones = []
            for p in preguntas_menu:
                if p.pregunta_corta_boton:
                    botones.append({
                        'id': f'faq_{p.pregunta_frecuenta_id}',
                        'texto': p.pregunta_corta_boton,
                        'pregunta_completa': p.pregunta_larga
                    })
            
            return {
                'respuesta': respuesta_amigable,
                'tipo': 'saludo',
                'botones': botones,
                'avatar_habla': True
            }

    # 2. BÚSQUEDA EN BASE DE DATOS
    logger.info("🧠 Buscando en BD...")
    try:
        # Búsqueda en Preguntas Frecuentes
        q_preguntas = Q()
        for palabra in palabras:
            q_preguntas |= Q(palabras_clave__icontains=palabra) | Q(pregunta_larga__icontains=palabra)
        
        pregunta_coincidente = PreguntaFrecuente.objects.filter(
            q_preguntas, 
            activo=True
        ).exclude(
            es_saludo_inicial=True
        ).first()
        
        if pregunta_coincidente:
            logger.info(f"✅ Encontrada FAQ: {pregunta_coincidente.pregunta_corta_boton}")
            
            respuesta_amigable = procesar_respuesta_con_ia_web(
                pregunta_coincidente.respuesta,
                mensaje_usuario,
                historial_conversacion
            )
            
            return {
                'respuesta': respuesta_amigable,
                'tipo': 'faq',
                'avatar_habla': True
            }

        # Búsqueda en Tipos de Habitación
        q_habitaciones = Q()
        for palabra in palabras:
            q_habitaciones |= Q(palabras_clave__icontains=palabra)
        
        habitacion_coincidente = TipoHabitacion.objects.filter(
            q_habitaciones, 
            activo=True
        ).first()
        
        if habitacion_coincidente:
            logger.info(f"✅ Encontrada habitación: {habitacion_coincidente.nombre_tipo_habitacion}")
            
            respuesta_habitacion = (
                f"Te cuento sobre la {habitacion_coincidente.nombre_tipo_habitacion}:\n\n"
                f"{habitacion_coincidente.descripcion}\n\n"
                f"💰 Precio por noche: ${habitacion_coincidente.precio_por_noche:,.0f} CLP"
            )
            
            respuesta_amigable = procesar_respuesta_con_ia_web(
                respuesta_habitacion,
                mensaje_usuario,
                historial_conversacion
            )
            
            return {
                'respuesta': respuesta_amigable,
                'tipo': 'habitacion',
                'avatar_habla': True
            }

    except Exception as e:
        logger.error(f"❌ Error en búsqueda BD: {e}")

    # 3. NO ENCONTRADA: GUARDAR Y RESPONDER CON IA
    logger.info("❓ No encontrada - procesando con IA")
    
    try:
        # Crear cliente temporal para web (usando session_id)
        cliente, _ = Cliente.objects.get_or_create(
            telefono=f"web_{session_id}",
            defaults={'nombre_cliente': f'Cliente Web {session_id}'}
        )
        
        # Guardar pregunta desconocida
        if not PreguntaDesconocida.objects.filter(
            cliente=cliente, 
            texto_pregunta=mensaje_usuario
        ).exists():
            PreguntaDesconocida.objects.create(
                texto_pregunta=mensaje_usuario, 
                cliente=cliente
            )
    except Exception as e:
        logger.error(f"❌ Error guardando pregunta desconocida: {e}")
    
    respuesta_desconocida = procesar_pregunta_desconocida_con_ia_web(mensaje_usuario, historial_conversacion)
    
    return {
        'respuesta': respuesta_desconocida,
        'tipo': 'desconocida',
        'avatar_habla': True
    }

# --- VISTA API PARA CHAT WEB ---
@method_decorator(csrf_exempt, name='dispatch')
class WebChatView(View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            mensaje = data.get('mensaje', '').strip()
            session_id = data.get('session_id', 'anonymous')
            
            if not mensaje:
                return JsonResponse({
                    'error': 'Mensaje vacío'
                }, status=400)
            
            # Obtener historial de la sesión (simulado con últimos mensajes de BD)
            try:
                cliente = Cliente.objects.get(telefono=f"web_{session_id}")
                conversacion, _ = Conversacion.objects.get_or_create(
                    cliente=cliente,
                    activo=True
                )
                
                # Obtener historial reciente
                mensajes_recientes = Mensaje.objects.filter(
                    conversacion=conversacion
                ).order_by('-timestamp')[:10]
                
                historial = []
                for msg in reversed(mensajes_recientes):
                    historial.append({
                        'remitente': msg.remitente,
                        'contenido': msg.contenido,
                        'timestamp': msg.timestamp.isoformat()
                    })
            except Cliente.DoesNotExist:
                historial = []
                conversacion = None
            
            # Procesar mensaje con el cerebro del bot
            resultado = obtener_respuesta_agente_web(mensaje, session_id, historial)
            
            # Guardar mensajes en BD si hay conversación activa
            if conversacion:
                # Guardar mensaje del cliente
                Mensaje.objects.create(
                    conversacion=conversacion,
                    remitente='cliente',
                    contenido=mensaje
                )
                
                # Guardar respuesta del agente
                Mensaje.objects.create(
                    conversacion=conversacion,
                    remitente='agente',
                    contenido=resultado['respuesta']
                )
            
            logger.info(f"✅ Respuesta web generada para sesión {session_id}")
            
            return JsonResponse({
                'success': True,
                'data': resultado
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'error': 'JSON inválido'
            }, status=400)
        except Exception as e:
            logger.error(f"💥 Error en chat web: {e}")
            return JsonResponse({
                'error': 'Error interno del servidor'
            }, status=500)

# --- VISTA PARA OBTENER PREGUNTAS FRECUENTES ---
class PreguntasFrecuentesView(View):
    def get(self, request):
        try:
            preguntas = PreguntaFrecuente.objects.filter(
                activo=True
            ).exclude(
                es_saludo_inicial=True
            ).order_by('pregunta_frecuenta_id')[:10]
            
            datos = []
            for p in preguntas:
                datos.append({
                    'id': p.pregunta_frecuenta_id,
                    'pregunta_corta': p.pregunta_corta_boton,
                    'pregunta_larga': p.pregunta_larga,
                    'respuesta': p.respuesta
                })
            
            return JsonResponse({
                'success': True,
                'preguntas': datos
            })
        except Exception as e:
            logger.error(f"Error obteniendo FAQs: {e}")
            return JsonResponse({
                'error': 'Error obteniendo preguntas frecuentes'
            }, status=500)
        
