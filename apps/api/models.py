# backend/api/models.py
from django.db import models
from django.utils import timezone # Asegúrate de que timezone esté importado
from django.contrib.auth.models import User

class BaseModel(models.Model):
    """Modelo base que contiene campos comunes para todos los modelos"""
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class Cliente(BaseModel):
    cliente_id = models.AutoField(primary_key=True)
    nombre_cliente = models.CharField(max_length=100, blank=True, null=True)
    telefono = models.CharField(max_length=20, unique=True)
    ultima_interaccion = models.DateTimeField(auto_now=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'clientes' # Nombre de la tabla en plural

    def __str__(self):
        return f"Cliente: {self.nombre_cliente or self.telefono}"

class Conversacion(BaseModel):
    conversacion_id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True)
    inicio_conversacion = models.DateTimeField(auto_now_add=True)
    fin_conversacion = models.DateTimeField(blank=True, null=True)
    # activa = models.BooleanField(default=True)

    class Meta:
        db_table = 'conversaciones' # Nombre de la tabla en plural

    def __str__(self):
        return f"Conversación con {self.cliente.telefono} ({self.conversacion_id})"

class Mensaje(models.Model):
    mensaje_id = models.AutoField(primary_key=True)
    conversacion = models.ForeignKey(Conversacion, on_delete=models.SET_NULL, null=True)
    remitente = models.CharField(max_length=50) # 'cliente' o 'agente'
    contenido = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'mensajes' # Nombre de la tabla en plural
        ordering = ['timestamp'] # Ordenar mensajes por tiempo

    def __str__(self):
        return f"[{self.timestamp}] {self.remitente}: {self.contenido[:50]}..."

class TipoHabitacion(BaseModel):
    """Representa un tipo de habitación del motel."""
    tipo_habitacion_id = models.AutoField(primary_key=True)
    nombre_tipo_habitacion = models.CharField(max_length=100, unique=True, help_text="Ej: Suite Jacuzzi")
    descripcion = models.TextField(help_text="Una descripción atractiva de la habitación.")
    precio_por_noche = models.DecimalField(max_digits=8, decimal_places=2, help_text="Precio en CLP")
    palabras_clave = models.CharField(max_length=255, help_text="Palabras clave separadas por comas (ej: jacuzzi, cama king, premium)")

    class Meta:
        db_table = 'tipos_habitacion' # Nombre de la tabla en plural

    def __str__(self):
        return f"{self.nombre_tipo_habitacion} - ${self.precio_por_noche:,.0f}"
    
class Habitacion(BaseModel):
    habitacion_id = models.AutoField(primary_key=True)
    nombre_habitacion = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    precio_por_hora = models.DecimalField(max_digits=10, decimal_places=2)
    disponible = models.BooleanField(default=True)
    capacidad = models.IntegerField(default=2)

    class Meta:
        db_table = 'habitaciones' # Nombre de la tabla en plural

    def __str__(self):
        return self.nombre_habitacion
    
# class PreguntaFrecuente(BaseModel):
#     """Almacena preguntas y respuestas comunes (FAQ)."""
#     pregunta_frecuenta_id = models.AutoField(primary_key=True)
#     pregunta = models.CharField(max_length=255, unique=True, help_text="Ej: ¿Cuál es el horario de check-in?")
#     respuesta = models.TextField(help_text="La respuesta oficial a la pregunta.")
#     palabras_clave = models.CharField(max_length=255, help_text="Palabras clave separadas por comas (ej: horario, check-in, entrada, llegar)")
    
#     class Meta:
#         db_table = 'pregunta_frecuentes' # Nombre de la tabla en plural

#     def __str__(self):
#         return self.pregunta

class PreguntaFrecuente(BaseModel):
    """Almacena preguntas y respuestas comunes (FAQ)."""
    pregunta_frecuenta_id = models.AutoField(primary_key=True)
    # --- CAMBIO IMPORTANTE ---
    # Este será el texto del botón, limitado a 20 caracteres.
    pregunta_corta_boton = models.CharField(
        max_length=20, 
        unique=True, 
        help_text="Texto para el botón de WhatsApp (MÁXIMO 20 CARACTERES). Ej: 'Ver Horarios'"
    )
    pregunta_larga = models.CharField(
        max_length=255, 
        help_text="La pregunta completa que el bot usará para buscar. Ej: '¿Cuál es el horario de check-in?'"
    )
    respuesta = models.TextField(help_text="La respuesta oficial a la pregunta.")
    palabras_clave = models.CharField(max_length=255, help_text="Palabras clave separadas por comas (ej: horario, check-in, entrada, llegar)")
    es_saludo_inicial = models.BooleanField(
        default=False,
        help_text="Marcar si esta pregunta y sus botones deben usarse como el mensaje de bienvenida."
    )
    
    class Meta:
        db_table = 'preguntas_frecuente'

    def __str__(self):
        return self.pregunta_corta_boton

class Reserva(models.Model):
    reserva_id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True)
    habitacion = models.ForeignKey(Habitacion, on_delete=models.SET_NULL, null=True)
    fecha = models.DateTimeField(auto_now_add=True)
    fecha_hora_inicio = models.DateTimeField()
    fecha_hora_fin = models.DateTimeField()
    estado = models.CharField(max_length=50, default='pendiente') # 'pendiente', 'confirmada', 'cancelada', 'completada', 'llegada_confirmada'
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_llegada = models.DateTimeField(null=True, blank=True)  # NUEVO CAMPO
    telefono = models.CharField(max_length=20, blank=True, null=True)
    duracion = models.IntegerField(help_text="Duración en horas")
    precio_total = models.DecimalField(max_digits=10, decimal_places=2)
    origen = models.CharField(max_length=20, default='web', choices=[
        ('web', 'Web'),
        ('whatsapp', 'WhatsApp'),
        ('telefono', 'Teléfono'),
    ])
    
    class Meta:
        db_table = 'reservas'

    def __str__(self):
        return f"Reserva de {self.habitacion.nombre_habitacion if self.habitacion else 'Habitación'} por {self.cliente.nombre_cliente if self.cliente else 'Cliente'}"

class BaseConocimiento(BaseModel):
    base_conocimiento_id = models.AutoField(primary_key=True)
    pregunta = models.TextField(unique=True)
    respuesta = models.TextField()
    palabras_clave = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        db_table = 'bases_conocimiento' # Nombre de la tabla en plural

    def __str__(self):
        return self.pregunta[:75] + "..." if len(self.pregunta) > 75 else self.pregunta
    
class PreguntaDesconocida(models.Model):
    """Almacena preguntas que el bot no pudo responder para revisión humana."""
    pregunta_desconocida_id = models.AutoField(primary_key=True)
    texto_pregunta = models.TextField(verbose_name="Texto de la Pregunta del Usuario")
    # CAMPO CLIENTE - ASEGÚRATE QUE ESTÉ EXACTAMENTE ASÍ
    cliente = models.ForeignKey(
        'Cliente',  # Usar string si Cliente está en el mismo archivo
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        verbose_name="Cliente Asociado"
    )
    
    fecha_recibida = models.DateTimeField(auto_now_add=True)
    revisada = models.BooleanField(
        default=False, 
        help_text="Marcar cuando la pregunta haya sido gestionada."
    )
    
    class Meta:
        db_table = 'preguntas_desconocida'
        verbose_name = "Pregunta Desconocida"
        verbose_name_plural = "Preguntas Desconocidas"
        ordering = ['-fecha_recibida']
        
    def __str__(self):
        return f"'{self.texto_pregunta[:50]}...' (Recibida: {self.fecha_recibida.strftime('%d-%m-%Y')})"
    
class Persona(BaseModel):
    """Modelo para personas"""
    persona_id = models.AutoField(primary_key=True)
    primer_nombre = models.CharField(max_length=30)
    segundo_nombre = models.CharField(max_length=30, blank=True, null=True)
    apellido_paterno = models.CharField(max_length=30)
    apellido_materno = models.CharField(max_length=30, blank=True, null=True)
    documento_identidad = models.CharField(max_length=15, unique=True)
    dv = models.CharField(max_length=1, verbose_name="Dígito Verificador")
    mail = models.EmailField(unique=True)
    cod_tel_pais = models.CharField(max_length=5, blank=True, null=True)
    cod_telefono = models.CharField(max_length=5, blank=True, null=True)
    telefono_persona = models.CharField(max_length=15, blank=True, null=True)
    cod_tel_pais_wp = models.CharField(max_length=5, blank=True, null=True)
    cod_tel_wp = models.CharField(max_length=5, blank=True, null=True)
    whatsapp_persona = models.CharField(max_length=15, blank=True, null=True)
    fecha_nacimiento = models.DateField(blank=True, null=True)

    class Meta:
        db_table = 'personas'
        verbose_name = 'Persona'
        verbose_name_plural = 'Personas'

    def __str__(self):
        return f"{self.primer_nombre} {self.apellido_paterno} {self.apellido_materno}"

    def nombre_completo(self):
        return f"{self.primer_nombre} {self.segundo_nombre or ''} {self.apellido_paterno} {self.apellido_materno or ''}".strip()

class Rol(BaseModel):
    """Modelo para roles de usuario"""
    rol_id = models.AutoField(primary_key=True)
    nombre_rol = models.CharField(max_length=50)
    codigo_rol = models.CharField(max_length=10, unique=True)
    descripcion_rol = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'roles'
        verbose_name = 'Rol'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.nombre_rol

class UserProfile(BaseModel):
    """Modelo para perfiles de usuario"""
    user_profile_id = models.AutoField(primary_key=True)
    persona = models.OneToOneField(Persona, on_delete=models.SET_NULL, null=True, related_name='perfil')
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, related_name='perfil')
    
    class Meta:
        db_table = 'users_profile'
        verbose_name = 'Perfil de Usuario'
        verbose_name_plural = 'Perfiles de Usuario'

    def __str__(self):
        if self.user:
            return f"Perfil de {self.user.username}"
        return "Perfil sin usuario asignado"

class UserRol(BaseModel):
    """Modelo para relación muchos a muchos entre UserProfile y Rol"""
    user_rol_id = models.AutoField(primary_key=True)
    user_profile = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, related_name='roles')
    rol = models.ForeignKey(Rol, on_delete=models.SET_NULL, null=True)

    class Meta:
        db_table = 'users_roles'
        verbose_name = 'Rol de Usuario'
        verbose_name_plural = 'Roles de Usuario'
        unique_together = ('user_profile', 'rol')

    def __str__(self):
        return f"{self.user_profile} - {self.rol}"