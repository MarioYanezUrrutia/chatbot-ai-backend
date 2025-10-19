# backend/api/bot_logic.py
"""
Motor de Lógica Centralizado para Bot de Motel Pratsy
Usado por WhatsApp (views.py) y Web Chat (views_web_chat.py)
"""

import logging
import os
from django.db.models import Q
from django.utils import timezone
from google import genai

logger = logging.getLogger(__name__)

# Configuración de Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GENAI_SDK_AVAILABLE = True

try:
    from google import genai
    GENAI_SDK_AVAILABLE = True
    logger.info("✅ Google GenAI SDK importado correctamente")
except ImportError as e:
    genai = None
    GENAI_SDK_AVAILABLE = False
    logger.error(f"❌ No se pudo importar Google GenAI SDK: {e}")


class BotLogicEngine:
    """Motor de lógica centralizado para WhatsApp y Web"""
    
    # ========================================
    # 1. PROCESAMIENTO CON IA - GEMINI
    # ========================================
    
    @staticmethod
    def procesar_respuesta_con_ia(respuesta_bd, mensaje_usuario, historial):
        """
        Procesa la respuesta de la BD a través de Gemini para hacerla más amigable
        
        Args:
            respuesta_bd (str): Respuesta técnica de la base de datos
            mensaje_usuario (str): Pregunta original del usuario
            historial (list): Lista de diccionarios con 'remitente' y 'contenido'
        
        Returns:
            str: Respuesta reformulada por la IA o respuesta original si falla
        """
        logger.info("🤖 Procesando respuesta con IA (Gemini)...")
        
        if not GEMINI_API_KEY:
            logger.warning("⚠️ No hay API Key de Gemini - Devolviendo respuesta original")
            return respuesta_bd
        
        if not GENAI_SDK_AVAILABLE:
            logger.warning("⚠️ SDK de Gemini no disponible - Devolviendo respuesta original")
            return respuesta_bd
        
        try:
            # Crear cliente Gemini
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            # Modelos disponibles (del más reciente al más antiguo)
            MODELOS_DISPONIBLES = [
                "models/gemini-2.0-flash-exp",
                "models/gemini-1.5-flash",
                "models/gemini-1.5-pro",
            ]
            
            # Construir contexto del historial
            historial_context = ""
            for msg in historial[-4:]:  # Últimos 4 mensajes
                remitente = msg.get('remitente', 'cliente')
                contenido = msg.get('contenido', '')
                role = "Cliente" if remitente == "cliente" else "Asistente"
                historial_context += f"{role}: {contenido}\n"
            
            # Prompt optimizado
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
                            logger.info(f"✅ Respuesta reformulada exitosamente con {modelo}")
                            return texto_respuesta.strip()
                        
                except Exception as e:
                    logger.warning(f"⚠️ Error con modelo {modelo}: {e}")
                    continue
            
            # Si ningún modelo funcionó
            logger.warning("⚠️ Ningún modelo funcionó - Usando respuesta original")
            return respuesta_bd
                
        except Exception as e:
            logger.error(f"❌ Error general procesando con IA: {e}")
            return respuesta_bd
    
    @staticmethod
    def procesar_pregunta_desconocida_con_ia(mensaje_usuario, historial):
        """
        Procesa preguntas desconocidas con IA para dar una respuesta empática
        
        Args:
            mensaje_usuario (str): Pregunta del usuario
            historial (list): Lista de diccionarios con 'remitente' y 'contenido'
        
        Returns:
            str: Respuesta empática generada por IA
        """
        logger.info("🤖 Procesando pregunta desconocida con IA...")
        
        # Respuesta por defecto
        respuesta_default = "Disculpa, no tengo información específica sobre eso en este momento. ¿Podrías reformular tu pregunta o consultar sobre nuestros servicios principales como reservas, precios u horarios?"
        
        if not GEMINI_API_KEY or not GENAI_SDK_AVAILABLE:
            logger.warning("⚠️ No hay API Key o SDK no disponible - Usando respuesta por defecto")
            return respuesta_default
        
        try:
            # Crear cliente Gemini
            client = genai.Client(api_key=GEMINI_API_KEY)
            
            MODELOS_DISPONIBLES = [
                "models/gemini-2.0-flash-exp",
                "models/gemini-1.5-flash",
                "models/gemini-1.5-pro",
            ]
            
            # Construir contexto
            historial_context = ""
            for msg in historial[-4:]:
                remitente = msg.get('remitente', 'cliente')
                contenido = msg.get('contenido', '')
                role = "Cliente" if remitente == "cliente" else "Asistente"
                historial_context += f"{role}: {contenido}\n"
            
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
            
            # Intentar con cada modelo
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
                            logger.info(f"✅ Respuesta desconocida generada con {modelo}")
                            return texto_respuesta.strip()
                            
                except Exception as e:
                    logger.warning(f"⚠️ Error con modelo {modelo}: {e}")
                    continue
            
            return respuesta_default
                
        except Exception as e:
            logger.error(f"❌ Error procesando pregunta desconocida: {e}")
            return respuesta_default
    
    # ========================================
    # 2. DETECCIÓN DE INTENCIONES
    # ========================================
    
    @staticmethod
    def detectar_intencion_reserva(mensaje):
        """
        Detecta si el usuario quiere hacer una reserva
        
        Args:
            mensaje (str): Mensaje del usuario
        
        Returns:
            bool: True si detecta intención de reserva
        """
        mensaje_lower = mensaje.lower().strip()
        
        # Palabras y frases clave para detectar reservas
        palabras_reserva = [
            'reserva', 'reservar', 'reservación', 'reservacion', 'booking',
            'agendar', 'apartar', 'separar', 'ocupar',
            'quiero reservar', 'hacer una reserva', 'realizar reserva',
            'reserva por favor', 'me gustaria reservar', 'me gustaría reservar',
            'deseo reservar', 'puedo reservar', 'como reservo',
            'necesito reservar', 'quisiera reservar', 'quiero hacer una reserva',
            'para reservar', 'hacer reserva', 'una reserva',
            'quiero una habitacion', 'quiero una habitación',
            'necesito una habitacion', 'necesito una habitación',
            'disponibilidad para reservar', 'reservar habitacion',
            'reservar habitación', 'reservar pieza', 'reservar cuarto'
        ]
        
        # Verificar si alguna palabra/frase clave está en el mensaje
        for palabra in palabras_reserva:
            if palabra in mensaje_lower:
                logger.info(f"🎯 Intención de reserva detectada con: '{palabra}'")
                return True
        
        return False
    
    @staticmethod
    def detectar_saludo_inicial(mensaje, cantidad_mensajes_previos=0):
        """
        Detecta si es un saludo inicial
        
        Args:
            mensaje (str): Mensaje del usuario
            cantidad_mensajes_previos (int): Cantidad de mensajes previos en la conversación
        
        Returns:
            bool: True si es un saludo inicial
        """
        mensaje_limpio = mensaje.lower().strip()
        palabras = set(mensaje_limpio.split())
        
        PALABRAS_DE_SALUDO = {
            'hola', 'buenas', 'hello', 'hi', 'hey', 'buenos', 'buen', 
            'saludos', 'holis', 'holaa', 'info', 'informacion', 
            'información', 'empezar', 'ayuda', 'start'
        }
        
        # Es saludo si:
        # 1. Tiene palabras de saludo Y es una de las primeras interacciones
        # 2. O es SOLO una palabra de saludo
        es_saludo = (
            (palabras.intersection(PALABRAS_DE_SALUDO) and cantidad_mensajes_previos <= 1) or
            mensaje_limpio in PALABRAS_DE_SALUDO
        )
        
        if es_saludo:
            logger.info("👋 Saludo inicial detectado")
        
        return es_saludo
    
    # ========================================
    # 3. BÚSQUEDA EN BASE DE DATOS
    # ========================================
    
    @staticmethod
    def buscar_en_faqs(mensaje_usuario, excluir_saludo=True):
        """
        Busca en Preguntas Frecuentes usando sistema de puntaje
        
        Args:
            mensaje_usuario (str): Mensaje del usuario
            excluir_saludo (bool): Si debe excluir preguntas de saludo inicial
        
        Returns:
            PreguntaFrecuente o None
        """
        from .models import PreguntaFrecuente
        
        logger.info("🔍 Buscando en Preguntas Frecuentes...")
        
        mensaje_limpio = mensaje_usuario.lower().strip()
        palabras_busqueda = [p for p in mensaje_limpio.split() if len(p) >= 3]
        
        if not palabras_busqueda:
            logger.info("No hay palabras válidas para búsqueda (mínimo 3 caracteres)")
            return None
        
        # Obtener preguntas activas
        preguntas_activas = PreguntaFrecuente.objects.filter(activo=True)
        
        if excluir_saludo:
            preguntas_activas = preguntas_activas.exclude(es_saludo_inicial=True)
        
        logger.info(f"Total preguntas activas: {preguntas_activas.count()}")
        logger.info(f"Palabras a buscar: {palabras_busqueda}")
        
        # ============================================
        # NIVEL 1: BÚSQUEDA EXACTA EN PALABRAS_CLAVE
        # ============================================
        logger.info("--- NIVEL 1: Buscando en palabras_clave ---")
        
        for pregunta in preguntas_activas:
            if not pregunta.palabras_clave:
                continue
            
            # Normalizar palabras clave
            palabras_clave_lista = [
                pk.strip().lower() 
                for pk in pregunta.palabras_clave.split(',')
                if pk.strip()
            ]
            
            # Verificar coincidencias
            for palabra_usuario in palabras_busqueda:
                for palabra_clave in palabras_clave_lista:
                    if (palabra_usuario == palabra_clave or 
                        palabra_usuario in palabra_clave or 
                        palabra_clave in palabra_usuario):
                        
                        logger.info(f"✅ MATCH EXACTO en palabras_clave:")
                        logger.info(f"   Usuario: '{palabra_usuario}' -> Clave: '{palabra_clave}'")
                        logger.info(f"   Pregunta: {pregunta.pregunta_corta_boton}")
                        return pregunta
        
        logger.info("No se encontró coincidencia exacta en palabras_clave")
        
        # ============================================
        # NIVEL 2: BÚSQUEDA CON PUNTAJE EN PREGUNTA_LARGA
        # ============================================
        logger.info("--- NIVEL 2: Buscando en pregunta_larga con puntaje ---")
        
        mejor_pregunta = None
        mejor_puntaje = 0
        umbral_minimo = 2  # Mínimo puntaje para considerar válido
        
        for pregunta in preguntas_activas:
            if not pregunta.pregunta_larga:
                continue
            
            puntaje = 0
            pregunta_larga_lower = pregunta.pregunta_larga.lower()
            palabras_pregunta = pregunta_larga_lower.split()
            
            # Calcular puntaje por cada palabra del usuario
            for palabra_usuario in palabras_busqueda:
                if palabra_usuario in pregunta_larga_lower:
                    posicion = pregunta_larga_lower.find(palabra_usuario)
                    
                    # Bonificación por posición temprana
                    if posicion < 30:
                        puntaje += 3
                    else:
                        puntaje += 2
                    
                    # Bonificación si es palabra completa
                    if palabra_usuario in palabras_pregunta:
                        puntaje += 1
            
            # Actualizar mejor candidato
            if puntaje > mejor_puntaje:
                mejor_puntaje = puntaje
                mejor_pregunta = pregunta
        
        # Validar umbral
        if mejor_pregunta and mejor_puntaje >= umbral_minimo:
            logger.info(f"✅ MATCH POR PUNTAJE (puntaje: {mejor_puntaje})")
            logger.info(f"   Pregunta: {mejor_pregunta.pregunta_corta_boton}")
            return mejor_pregunta
        else:
            logger.info(f"❌ No se alcanzó umbral mínimo (mejor: {mejor_puntaje}, requerido: {umbral_minimo})")
            return None
    
    @staticmethod
    def buscar_en_base_conocimiento(mensaje_usuario):
        """
        Busca en Base de Conocimiento
        
        Args:
            mensaje_usuario (str): Mensaje del usuario
        
        Returns:
            BaseConocimiento o None
        """
        from .models import BaseConocimiento
        
        logger.info("📚 Buscando en Base de Conocimiento...")
        
        mensaje_limpio = mensaje_usuario.lower().strip()
        
        try:
            resultado = BaseConocimiento.objects.filter(
                Q(respuesta__icontains=mensaje_limpio) | 
                Q(palabras_clave__icontains=mensaje_limpio),
                activo=True
            ).first()
            
            if resultado:
                logger.info("✅ Información de Base de Conocimiento encontrada")
            
            return resultado
            
        except Exception as e:
            logger.error(f"❌ Error buscando en Base de Conocimiento: {e}")
            return None
    
    @staticmethod
    def buscar_tipo_habitacion(mensaje_usuario):
        """
        Busca en Tipos de Habitación
        
        Args:
            mensaje_usuario (str): Mensaje del usuario
        
        Returns:
            TipoHabitacion o None
        """
        from .models import TipoHabitacion
        
        logger.info("🏨 Buscando en Tipos de Habitación...")
        
        mensaje_limpio = mensaje_usuario.lower().strip()
        palabras = set(mensaje_limpio.split())
        
        try:
            q_habitaciones = Q()
            for palabra in palabras:
                q_habitaciones |= Q(palabras_clave__icontains=palabra)
            
            resultado = TipoHabitacion.objects.filter(
                q_habitaciones, 
                activo=True
            ).first()
            
            if resultado:
                logger.info(f"✅ Tipo de habitación encontrado: {resultado.nombre_tipo_habitacion}")
            
            return resultado
            
        except Exception as e:
            logger.error(f"❌ Error buscando tipos de habitación: {e}")
            return None
    
    # ========================================
    # 4. GUARDAR PREGUNTA DESCONOCIDA
    # ========================================
    
    @staticmethod
    def guardar_pregunta_desconocida(mensaje_usuario, cliente):
        """
        Guarda una pregunta desconocida en la BD
        
        Args:
            mensaje_usuario (str): Mensaje del usuario
            cliente (Cliente): Objeto Cliente
        """
        from .models import PreguntaDesconocida
        
        try:
            if not PreguntaDesconocida.objects.filter(
                cliente=cliente,
                texto_pregunta=mensaje_usuario
            ).exists():
                PreguntaDesconocida.objects.create(
                    cliente=cliente,
                    texto_pregunta=mensaje_usuario,
                    fecha_recibida=timezone.now()
                )
                logger.info("💾 Pregunta desconocida guardada")
        except Exception as e:
            logger.error(f"❌ Error guardando pregunta desconocida: {e}")