# apps/reservas/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import RegexValidator
from apps.api.models import Cliente, Habitacion


class EstadoReserva(models.TextChoices):
    """Estados posibles de una reserva"""
    PENDIENTE = 'pendiente', 'Pendiente'
    CONFIRMADA = 'confirmada', 'Confirmada'
    EN_PROCESO = 'en_proceso', 'En Proceso'
    LLEGADA_CONFIRMADA = 'llegada_confirmada', 'Llegada Confirmada'
    COMPLETADA = 'completada', 'Completada'
    CANCELADA = 'cancelada', 'Cancelada'
    NO_SHOW = 'no_show', 'No Show'


class TipoReserva(models.TextChoices):
    """Tipos de reserva disponibles"""
    POR_HORAS = 'por_horas', 'Por Horas'
    NOCHE_COMPLETA = 'noche_completa', 'Noche Completa'


class ReservaWhatsApp(models.Model):
    """
    Modelo principal para las reservas realizadas vía WhatsApp
    Extiende la funcionalidad del modelo Reserva existente
    """
    reserva_id = models.AutoField(primary_key=True)
    
    # Relaciones
    cliente = models.ForeignKey(
        Cliente, 
        on_delete=models.PROTECT,
        related_name='reservas_whatsapp',
        help_text="Cliente que realiza la reserva"
    )
    habitacion = models.ForeignKey(
        Habitacion,
        on_delete=models.PROTECT,
        related_name='reservas_whatsapp',
        help_text="Habitación reservada"
    )
    
    # Información de la reserva
    tipo_reserva = models.CharField(
        max_length=20,
        choices=TipoReserva.choices,
        default=TipoReserva.POR_HORAS,
        help_text="Tipo de reserva solicitada"
    )
    
    fecha_reserva = models.DateField(
        help_text="Fecha para la cual se hace la reserva"
    )
    hora_inicio = models.TimeField(
        help_text="Hora de inicio de la reserva"
    )
    hora_fin = models.TimeField(
        help_text="Hora de fin de la reserva"
    )
    
    # Información adicional
    numero_personas = models.PositiveSmallIntegerField(
        default=2,
        help_text="Número de personas para la reserva"
    )
    observaciones = models.TextField(
        blank=True,
        null=True,
        help_text="Observaciones adicionales del cliente"
    )
    
    # Estado y seguimiento
    estado = models.CharField(
        max_length=20,
        choices=EstadoReserva.choices,
        default=EstadoReserva.PENDIENTE,
        help_text="Estado actual de la reserva"
    )
    
    # Información de contacto adicional
    nombre_contacto = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Nombre del contacto principal"
    )
    
    # Precios y pagos
    precio_total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Precio total de la reserva"
    )
    precio_por_hora = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Precio por hora aplicado"
    )
    horas_reservadas = models.PositiveSmallIntegerField(
        help_text="Número de horas reservadas"
    )
    
    # Información de llegada
    fecha_hora_llegada = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Fecha y hora de llegada confirmada"
    )
    confirmada_por_funcionario = models.CharField(
        max_length=20,
        blank=True,
        null=True,
        help_text="Teléfono del funcionario que confirmó la llegada"
    )
    
    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    activo = models.BooleanField(default=True)
    
    # Información del proceso de reserva
    conversacion_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="ID de la conversación donde se realizó la reserva"
    )
    paso_actual = models.CharField(
        max_length=50,
        default='inicio',
        help_text="Paso actual en el proceso de reserva"
    )
    datos_temporales = models.JSONField(
        default=dict,
        blank=True,
        help_text="Datos temporales durante el proceso de reserva"
    )

    class Meta:
        db_table = 'reservas_whatsapp'
        verbose_name = 'Reserva WhatsApp'
        verbose_name_plural = 'Reservas WhatsApp'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f"Reserva {self.reserva_id} - {self.cliente.telefono} - {self.fecha_reserva} {self.hora_inicio}"

    @property
    def duracion_horas(self):
        """Calcula la duración en horas de la reserva"""
        if self.hora_inicio and self.hora_fin:
            inicio = timezone.datetime.combine(timezone.datetime.today(), self.hora_inicio)
            fin = timezone.datetime.combine(timezone.datetime.today(), self.hora_fin)
            if fin < inicio:  # La reserva cruza medianoche
                fin += timezone.timedelta(days=1)
            duracion = fin - inicio
            return duracion.total_seconds() / 3600
        return 0

    @property
    def esta_activa(self):
        """Determina si la reserva está activa (pendiente o confirmada)"""
        return self.estado in [EstadoReserva.PENDIENTE, EstadoReserva.CONFIRMADA, EstadoReserva.EN_PROCESO]

    def marcar_llegada(self, funcionario_telefono):
        """Marca la llegada del cliente"""
        self.estado = EstadoReserva.LLEGADA_CONFIRMADA
        self.fecha_hora_llegada = timezone.now()
        self.confirmada_por_funcionario = funcionario_telefono
        self.save()

    def completar_reserva(self):
        """Marca la reserva como completada"""
        self.estado = EstadoReserva.COMPLETADA
        self.save()

    def cancelar_reserva(self, motivo=None):
        """Cancela la reserva"""
        self.estado = EstadoReserva.CANCELADA
        if motivo:
            self.observaciones = f"{self.observaciones or ''}\nCancelada: {motivo}".strip()
        self.save()


class FuncionarioHotel(models.Model):
    """
    Modelo para almacenar los números de teléfono de los funcionarios del hotel
    que pueden administrar las reservas vía WhatsApp
    """
    funcionario_id = models.AutoField(primary_key=True)
    
    nombre = models.CharField(
        max_length=100,
        help_text="Nombre del funcionario"
    )
    telefono = models.CharField(
        max_length=20,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^\+?1?\d{9,15}$',
                message="El número de teléfono debe estar en formato internacional"
            )
        ],
        help_text="Número de teléfono en formato internacional (ej: +56912345678)"
    )
    cargo = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        help_text="Cargo del funcionario"
    )
    
    # Permisos
    puede_confirmar_llegadas = models.BooleanField(
        default=True,
        help_text="Puede confirmar llegadas de clientes"
    )
    puede_cancelar_reservas = models.BooleanField(
        default=False,
        help_text="Puede cancelar reservas"
    )
    puede_modificar_reservas = models.BooleanField(
        default=False,
        help_text="Puede modificar reservas existentes"
    )
    
    # Estado
    activo = models.BooleanField(
        default=True,
        help_text="Funcionario activo en el sistema"
    )
    
    # Metadatos
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'funcionarios_hotel'
        verbose_name = 'Funcionario del Hotel'
        verbose_name_plural = 'Funcionarios del Hotel'
        ordering = ['nombre']

    def __str__(self):
        return f"{self.nombre} ({self.telefono})"

    @classmethod
    def es_funcionario(cls, telefono):
        """Verifica si un número de teléfono pertenece a un funcionario activo"""
        return cls.objects.filter(telefono=telefono, activo=True).exists()

    @classmethod
    def obtener_funcionario(cls, telefono):
        """Obtiene un funcionario por su número de teléfono"""
        try:
            return cls.objects.get(telefono=telefono, activo=True)
        except cls.DoesNotExist:
            return None


class ProcesoReserva(models.Model):
    """
    Modelo para rastrear el proceso de reserva de un cliente
    Permite manejar reservas en múltiples pasos vía WhatsApp
    """
    proceso_id = models.AutoField(primary_key=True)
    
    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name='procesos_reserva'
    )
    
    # Estado del proceso
    paso_actual = models.CharField(
        max_length=50,
        default='inicio',
        help_text="Paso actual en el proceso de reserva"
    )
    
    # Datos temporales del proceso
    datos_temporales = models.JSONField(
        default=dict,
        help_text="Datos recopilados durante el proceso"
    )
    
    # Información de la conversación
    conversacion_id = models.CharField(
        max_length=50,
        help_text="ID de la conversación asociada"
    )
    
    # Estado
    completado = models.BooleanField(
        default=False,
        help_text="Proceso completado exitosamente"
    )
    cancelado = models.BooleanField(
        default=False,
        help_text="Proceso cancelado por el usuario"
    )
    
    # Reserva resultante
    reserva_creada = models.ForeignKey(
        ReservaWhatsApp,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Reserva creada al completar el proceso"
    )
    
    # Metadatos
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_modificacion = models.DateTimeField(auto_now=True)
    fecha_finalizacion = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha de finalización del proceso"
    )

    class Meta:
        db_table = 'procesos_reserva'
        verbose_name = 'Proceso de Reserva'
        verbose_name_plural = 'Procesos de Reserva'
        ordering = ['-fecha_inicio']

    def __str__(self):
        estado = "Completado" if self.completado else "Cancelado" if self.cancelado else "En Proceso"
        return f"Proceso {self.proceso_id} - {self.cliente.telefono} - {estado}"

    def finalizar(self, exitoso=True):
        """Finaliza el proceso de reserva"""
        self.completado = exitoso
        self.cancelado = not exitoso
        self.fecha_finalizacion = timezone.now()
        self.save()

    def actualizar_paso(self, nuevo_paso, datos_adicionales=None):
        """Actualiza el paso actual y los datos temporales"""
        self.paso_actual = nuevo_paso
        if datos_adicionales:
            self.datos_temporales.update(datos_adicionales)
        self.save()

    def obtener_dato(self, clave, default=None):
        """Obtiene un dato temporal específico"""
        return self.datos_temporales.get(clave, default)

    def guardar_dato(self, clave, valor):
        """Guarda un dato temporal"""
        self.datos_temporales[clave] = valor
        self.save()

