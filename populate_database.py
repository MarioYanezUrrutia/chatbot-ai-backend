# populate_database.py
import os
import django
from decimal import Decimal

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.api.models import Habitacion, TipoHabitacion, PreguntaFrecuente

def crear_habitaciones():
    """Crear las 6 habitaciones del motel"""
    
    # Primero crear los tipos de habitación
    tipo_estandar, created = TipoHabitacion.objects.get_or_create(
        nombre_tipo_habitacion="Estándar",
        defaults={
            'descripcion': "Habitación cómoda y acogedora para una experiencia íntima",
            'precio_por_noche': Decimal('100000.00'),
            'palabras_clave': "estándar, básica, cómoda, económica"
        }
    )
    
    tipo_suite, created = TipoHabitacion.objects.get_or_create(
        nombre_tipo_habitacion="Suite",
        defaults={
            'descripcion': "Suite espaciosa con amenities premium para una experiencia especial",
            'precio_por_noche': Decimal('140000.00'),
            'palabras_clave': "suite, premium, espaciosa, lujosa"
        }
    )
    
    tipo_vip, created = TipoHabitacion.objects.get_or_create(
        nombre_tipo_habitacion="VIP",
        defaults={
            'descripcion': "Habitación VIP de lujo con jacuzzi y amenities exclusivos",
            'precio_por_noche': Decimal('180000.00'),
            'palabras_clave': "vip, lujo, jacuzzi, exclusiva, premium"
        }
    )
    
    # Crear las 6 habitaciones (2 de cada tipo)
    habitaciones = [
        {
            'nombre_habitacion': 'Estándar 101',
            'descripcion': 'Habitación estándar con cama king size y baño privado',
            'precio_por_hora': Decimal('25000.00'),
            'capacidad': 2
        },
        {
            'nombre_habitacion': 'Estándar 102',
            'descripcion': 'Habitación estándar con cama queen size y TV cable',
            'precio_por_hora': Decimal('25000.00'),
            'capacidad': 2
        },
        {
            'nombre_habitacion': 'Suite 201',
            'descripcion': 'Suite con sala de estar y baño con jacuzzi',
            'precio_por_hora': Decimal('35000.00'),
            'capacidad': 2
        },
        {
            'nombre_habitacion': 'Suite 202',
            'descripcion': 'Suite romántica con decoración especial y amenities',
            'precio_por_hora': Decimal('35000.00'),
            'capacidad': 2
        },
        {
            'nombre_habitacion': 'VIP 301',
            'descripcion': 'Suite VIP con jacuzzi, sauna y bar privado',
            'precio_por_hora': Decimal('45000.00'),
            'capacidad': 2
        },
        {
            'nombre_habitacion': 'VIP 302',
            'descripcion': 'Suite VIP premium con terraza privada y vista',
            'precio_por_hora': Decimal('45000.00'),
            'capacidad': 2
        }
    ]
    
    for i, hab_data in enumerate(habitaciones):
        # Asignar tipo según el índice
        if i < 2:
            tipo = tipo_estandar
        elif i < 4:
            tipo = tipo_suite
        else:
            tipo = tipo_vip
            
        habitacion, created = Habitacion.objects.get_or_create(
            nombre_habitacion=hab_data['nombre_habitacion'],
            defaults={
                'descripcion': hab_data['descripcion'],
                'precio_por_hora': hab_data['precio_por_hora'],
                'capacidad': hab_data['capacidad']
            }
        )
        print(f"Habitación {'creada' if created else 'actualizada'}: {hab_data['nombre_habitacion']}")

def crear_preguntas_frecuentes():
    """Crear las preguntas frecuentes según el listado"""
    
    preguntas_respuestas = [
        # Pregunta 1: Saludo inicial (hola)
        {
            'pregunta_corta_boton': 'Hola',
            'pregunta_larga': '¡Hola! Soy Pratsy, tu asistente virtual del Motel Pratsy. ¿En qué puedo ayudarte hoy?',
            'respuesta': '¡Hola! Soy Pratsy, tu asistente virtual del Motel Pratsy. ¿En qué puedo ayudarte hoy?',
            'palabras_clave': 'hola, saludo, inicio, empezar, bienvenida',
            'es_saludo_inicial': True
        },
        # Pregunta 2: Precios
        {
            'pregunta_corta_boton': 'Ver Precios',
            'pregunta_larga': '¿Cuáles son los precios?',
            'respuesta': 'Nuestros precios son: Habitación estándar $25,000/hora, Suite $35,000/hora, VIP $45,000/hora',
            'palabras_clave': 'precios, costo, tarifas, valor, cuanto cuesta, dinero',
            'es_saludo_inicial': False
        },
        # Pregunta 3: Ubicación
        {
            'pregunta_corta_boton': 'Ver Ubicación',
            'pregunta_larga': '¿Dónde están ubicados?',
            'respuesta': 'Estamos ubicados en Arturo Prats 408, Santiago Centro',
            'palabras_clave': 'ubicación, dirección, donde, localización, mapa, como llegar',
            'es_saludo_inicial': False
        },
        # Resto de preguntas
        {
            'pregunta_corta_boton': 'Horarios Atención',
            'pregunta_larga': '¿Atienden todos los días?',
            'respuesta': 'Sí, atendemos 24/7 los 365 días del año',
            'palabras_clave': 'horario, atención, días, abierto, funcionamiento, horario atención',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Estacionamiento',
            'pregunta_larga': '¿Tiene estacionamiento para autos?',
            'respuesta': 'Sí, contamos con estacionamiento privado y seguro',
            'palabras_clave': 'estacionamiento, parking, auto, vehiculo, aparcamiento',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Requisitos Ingreso',
            'pregunta_larga': '¿Qué requisitos necesito para entrar?',
            'respuesta': 'Carnet de identidad, pasaporte o alguna identificación oficial',
            'palabras_clave': 'requisitos, documento, identificación, carnet, pasaporte, ingreso',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Tríos',
            'pregunta_larga': '¿Aceptan tríos?',
            'respuesta': 'Sí, aceptamos tríos o grupos',
            'palabras_clave': 'tríos, grupos, múltiples personas, compañía, acompañantes',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Parejas Homosexuales',
            'pregunta_larga': '¿Aceptan parejas homosexuales?',
            'respuesta': 'Sí, somos un hotel gay friendly',
            'palabras_clave': 'homosexual, gay, lgbt, diversidad, inclusivo, parejas mismo sexo',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Mascotas',
            'pregunta_larga': '¿Aceptan mascotas?',
            'respuesta': 'No, por políticas de higiene no aceptamos mascotas',
            'palabras_clave': 'mascotas, perros, gatos, animales, mascota',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Ingreso Separado',
            'pregunta_larga': '¿Puede entrar una persona y luego la otra?',
            'respuesta': 'Sí se puede, tenemos ingreso discreto y separado',
            'palabras_clave': 'ingreso separado, entrada individual, discreción, privacidad',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Fumar',
            'pregunta_larga': '¿Se puede fumar?',
            'respuesta': 'La ley dice que no, pero te pasamos ceniceros',
            'palabras_clave': 'fumar, cigarrillo, tabaco, cenicero, humo',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Comidas',
            'pregunta_larga': '¿Tiene carta de comidas?',
            'respuesta': 'No, pero tenemos servicio de room service con opciones básicas',
            'palabras_clave': 'comida, alimentación, carta, menu, restaurante, comida habitación',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Bebestibles',
            'pregunta_larga': '¿Tiene carta de bebestibles?',
            'respuesta': 'Sí, tenemos variedad de bebidas alcohólicas y no alcohólicas',
            'palabras_clave': 'bebidas, bebestibles, alcohol, tragos, bebida, bar',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Juguetes Sexuales',
            'pregunta_larga': '¿Venden juguetes sexuales?',
            'respuesta': 'Algunos sí, contamos con una selección discreta',
            'palabras_clave': 'juguetes sexuales, adultos, erótico, sensual, productos',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Dama Compañía',
            'pregunta_larga': '¿Tienen dama de compañía?',
            'respuesta': 'No, somos un establecimiento serio que respeta la ley',
            'palabras_clave': 'dama compañía, acompañante, escort, servicio acompañamiento',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Una Hora',
            'pregunta_larga': '¿Puedo ir por una hora?',
            'respuesta': 'Claro, ud paga la estadía mínima de 3 horas, y puede estar solo 1',
            'palabras_clave': 'una hora, tiempo mínimo, estadía corta, hora, tiempo',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Menores Edad',
            'pregunta_larga': '¿Pueden ingresar menores de 18 años?',
            'respuesta': 'No, solo personas con más de 18 años',
            'palabras_clave': 'menores, edad, 18 años, adolescentes, jóvenes',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Dirección',
            'pregunta_larga': '¿Dónde se encuentran?',
            'respuesta': 'Arturo Prat 408, Santiago Centro',
            'palabras_clave': 'dirección, ubicación, donde, localización, mapa',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Fotos Habitaciones',
            'pregunta_larga': '¿Me puede mostrar fotos de las habitaciones?',
            'respuesta': 'Puede verlas en la página web.',
            'palabras_clave': 'fotos, imágenes, habitaciones, galería, fotografía, ver fotos',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Ir Solo',
            'pregunta_larga': '¿Puedo ir solo o sola?',
            'respuesta': 'Sí, puedes venir solo/a si lo deseas',
            'palabras_clave': 'solo, sola, individual, una persona, individualmente',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Jacuzzi',
            'pregunta_larga': '¿Tienen habitación con jacuzzi?',
            'respuesta': 'Sí, nuestras suites VIP incluyen jacuzzi',
            'palabras_clave': 'jacuzzi, tina, hidromasaje, bañera, burbujas',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Calefacción',
            'pregunta_larga': '¿Las habitaciones tienen calefacción?',
            'respuesta': 'Sí, tienen aire acondicionado y calefacción',
            'palabras_clave': 'calefacción, aire acondicionado, temperatura, clima, frío, calor',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Fotos Videos',
            'pregunta_larga': '¿Dónde puedo ver fotos y videos de las habitaciones?',
            'respuesta': 'Puede revisarlas en la página web.',
            'palabras_clave': 'fotos, videos, multimedia, galería, imágenes, video tour',
            'es_saludo_inicial': False
        },
        {
            'pregunta_corta_boton': 'Ciudad',
            'pregunta_larga': '¿En qué ciudad están?',
            'respuesta': 'Santiago',
            'palabras_clave': 'ciudad, santiago, comuna, región, ubicación geográfica',
            'es_saludo_inicial': False
        }
    ]
    
    for i, pregunta_data in enumerate(preguntas_respuestas):
        pregunta, created = PreguntaFrecuente.objects.get_or_create(
            pregunta_corta_boton=pregunta_data['pregunta_corta_boton'],
            defaults={
                'pregunta_larga': pregunta_data['pregunta_larga'],
                'respuesta': pregunta_data['respuesta'],
                'palabras_clave': pregunta_data['palabras_clave'],
                'es_saludo_inicial': pregunta_data['es_saludo_inicial']
            }
        )
        print(f"Pregunta {'creada' if created else 'actualizada'}: {pregunta_data['pregunta_corta_boton']}")

def main():
    """Función principal para poblar la base de datos"""
    print("Iniciando población de la base de datos...")
    
    print("\nCreando habitaciones...")
    crear_habitaciones()
    
    print("\nCreando preguntas frecuentes...")
    crear_preguntas_frecuentes()
    
    print("\n¡Base de datos poblada exitosamente!")

if __name__ == "__main__":
    main()