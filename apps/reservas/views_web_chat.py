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
from google import genai
from django.db.models import Q
from .models import (
    Cliente, Conversacion, Mensaje, TipoHabitacion,
    PreguntaFrecuente, PreguntaDesconocida
)

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

# --- FUNCIÓN PARA PROCESAR RESPUESTA CON IA (REUTILIZADA) ---
def procesar_respuesta_con_ia_web(respuesta_bd, mensaje_usuario, historial_conversacion):
    """
    Procesa la respuesta de la BD a través de la IA para hacerla más amigable
    ADAPTADO DEL CÓDIGO FUNCIONAL DE views.py
    """
    logger.info("🤖 Procesando respuesta web con IA...")
    
    if not GEMINI_API_KEY:
        logger.warning("⚠️ No hay API Key de Gemini - Devolviendo respuesta original")
        return respuesta_bd
    
    # Verificar si el SDK está disponible
    try:
        import google.generativeai as genai
        SDK_DISPONIBLE = True
    except ImportError:
        logger.warning("⚠️ SDK de Gemini no disponible")
        return respuesta_bd
    
    try:
        # Configurar cliente con el nuevo SDK
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Modelos disponibles (del más reciente al más antiguo)
        MODELOS_DISPONIBLES = [
            "models/gemini-2.0-flash-exp",
            "models/gemini-1.5-flash",
            "models/gemini-1.5-pro",
        ]
        
        # Construir contexto del historial
        historial_context = ""
        for msg in historial_conversacion[-4:]:  # Últimos 4 mensajes
            role = 'Cliente' if msg.get('remitente') == 'cliente' else 'Pratsy'
            historial_context += f"{role}: {msg.get('contenido', '')}\n"
        
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
        
        # Intentar con cada modelo hasta que uno funcione
        for modelo in MODELOS_DISPONIBLES:
            try:
                logger.info(f"🔄 Intentando con modelo: {modelo}")
                
                response = client.models.generate_content(
                    model=modelo,
                    contents=prompt,
                    config={
                        "max_output_tokens": 500,
                        "temperature": 0.7,
                    }
                )
                
                if response:
                    texto_respuesta = response.text if hasattr(response, 'text') else str(response)
                    
                    if texto_respuesta and texto_respuesta.strip():
                        logger.info(f"✅ Respuesta web reformulada exitosamente con {modelo}")
                        return texto_respuesta.strip()
                    
            except Exception as e:
                logger.warning(f"⚠️ Error con modelo {modelo}: {e}")
                continue
        
        # Si ningún modelo funcionó, devolver respuesta original
        logger.warning("⚠️ Ningún modelo funcionó - Usando respuesta original")
        return respuesta_bd
            
    except Exception as e:
        logger.error(f"❌ Error procesando con IA: {e}")
        return respuesta_bd

def procesar_pregunta_desconocida_con_ia_web(mensaje_usuario, historial_conversacion):
    """
    Procesa preguntas desconocidas con IA para el chat web
    ADAPTADO DEL CÓDIGO FUNCIONAL DE views.py
    """
    logger.info("🤖 Procesando pregunta desconocida web con IA...")
    
    # Respuesta por defecto
    respuesta_default = "Lo siento, no tengo información específica sobre eso. ¿Podrías reformular tu pregunta o consultar sobre nuestros servicios principales?"
    
    if not GEMINI_API_KEY:
        return respuesta_default
    
    try:
        import google.generativeai as genai
    except ImportError:
        return respuesta_default
    
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        
        MODELOS_DISPONIBLES = [
            "models/gemini-2.0-flash-exp",
            "models/gemini-1.5-flash",
            "models/gemini-1.5-pro",
        ]
        
        # Construir contexto
        historial_context = ""
        for msg in historial_conversacion[-4:]:
            role = 'Cliente' if msg.get('remitente') == 'cliente' else 'Pratsy'
            historial_context += f"{role}: {msg.get('contenido', '')}\n"
        
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
        
        for modelo in MODELOS_DISPONIBLES:
            try:
                response = client.models.generate_content(
                    model=modelo,
                    contents=prompt,
                    config={
                        "max_output_tokens": 500,
                        "temperature": 0.7,
                    }
                )
                
                if response:
                    texto_respuesta = response.text if hasattr(response, 'text') else str(response)
                    if texto_respuesta and texto_respuesta.strip():
                        return texto_respuesta.strip()
                        
            except Exception as e:
                logger.warning(f"⚠️ Error con modelo {modelo}: {e}")
                continue
        
        return respuesta_default
            
    except Exception as e:
        logger.error(f"❌ Error procesando pregunta desconocida: {e}")
        return respuesta_default

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
        
