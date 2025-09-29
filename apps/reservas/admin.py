# apps/reservas/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils import timezone
from .models import ReservaWhatsApp, FuncionarioHotel, ProcesoReserva, Habitacion, EstadoConversacion
from apps.api.models import Reserva

# ELIMINAR TODAS LAS VERIFICACIONES DE SISTEMA - CAUSAN CONFLICTOS

@admin.action(description='Marcar como llegada confirmada')
def confirmar_llegada(modeladmin, request, queryset):
    """Acción para confirmar llegada de múltiples reservas"""
    count = queryset.filter(
        estado__in=['pendiente', 'confirmada']
    ).update(
        estado='llegada_confirmada',
        fecha_hora_llegada=timezone.now()
    )
    modeladmin.message_user(request, f"{count} reservas marcadas como llegada confirmada.")

@admin.action(description='Marcar como completadas')
def completar_reservas(modeladmin, request, queryset):
    """Acción para completar múltiples reservas"""
    count = queryset.filter(
        estado__in=['llegada_confirmada', 'en_proceso']
    ).update(estado='completada')
    modeladmin.message_user(request, f"{count} reservas marcadas como completadas.")

@admin.action(description='Cancelar reservas seleccionadas')
def cancelar_reservas(modeladmin, request, queryset):
    """Acción para cancelar múltiples reservas"""
    count = queryset.filter(
        estado__in=['pendiente', 'confirmada']
    ).update(estado='cancelada')
    modeladmin.message_user(request, f"{count} reservas canceladas.")

@admin.register(ReservaWhatsApp)
class ReservaWhatsAppAdmin(admin.ModelAdmin):
    """Administración avanzada para reservas de WhatsApp"""
    
    list_display = (
        'reserva_id',
        'cliente_info',
        'habitacion_info',
        'fecha_hora_reserva',
        'estado_coloreado',
        'precio_total'
    )
    
    list_filter = (
        'estado',
        'tipo_reserva',
        'fecha_reserva',
        'fecha_creacion',
        'habitacion__nombre_habitacion'
    )
    
    search_fields = (
        'cliente__telefono',
        'cliente__nombre_cliente',
        'nombre_contacto',
        'habitacion__nombre_habitacion',
        'reserva_id'
    )
    
    readonly_fields = (
        'reserva_id',
        'fecha_creacion',
        'fecha_modificacion',
        'duracion_calculada',
        'conversacion_id'
    )
    
    actions = [confirmar_llegada, completar_reservas, cancelar_reservas]
    
    date_hierarchy = 'fecha_reserva'
    
    ordering = ['-fecha_creacion']
    
    fieldsets = (
        ('Información Básica', {
            'fields': (
                'reserva_id',
                'cliente',
                'nombre_contacto',
                'habitacion',
                'estado'
            )
        }),
        ('Detalles de la Reserva', {
            'fields': (
                'tipo_reserva',
                'fecha_reserva',
                'hora_inicio',
                'hora_fin',
                'numero_personas',
                'observaciones'
            )
        }),
        ('Información de Precios', {
            'fields': (
                'precio_por_hora',
                'horas_reservadas',
                'precio_total',
                'duracion_calculada'
            )
        }),
        ('Seguimiento', {
            'fields': (
                'fecha_hora_llegada',
                'confirmada_por_funcionario',
                'conversacion_id'
            )
        }),
        ('Metadatos', {
            'classes': ('collapse',),
            'fields': (
                'fecha_creacion',
                'fecha_modificacion',
                'activo',
                'paso_actual',
                'datos_temporales'
            )
        })
    )

    def cliente_info(self, obj):
        """Muestra información del cliente"""
        if obj.cliente:
            nombre = obj.nombre_contacto or obj.cliente.nombre_cliente or "Sin nombre"
            return f"{nombre}\n{obj.cliente.telefono}"
        return "Cliente desconocido"
    cliente_info.short_description = "Cliente"

    def habitacion_info(self, obj):
        """Muestra información de la habitación"""
        if obj.habitacion:
            return f"{obj.habitacion.nombre_habitacion}\n${obj.habitacion.precio_por_hora:,.0f}/hora"
        return "Sin habitación"
    habitacion_info.short_description = "Habitación"

    def fecha_hora_reserva(self, obj):
        """Muestra fecha y hora de la reserva"""
        return f"{obj.fecha_reserva}\n{obj.hora_inicio} - {obj.hora_fin}"
    fecha_hora_reserva.short_description = "Fecha y Hora"

    def estado_coloreado(self, obj):
        """Muestra el estado con colores"""
        colores = {
            'pendiente': '#ffc107',      # Amarillo
            'confirmada': '#17a2b8',     # Azul
            'en_proceso': '#28a745',     # Verde
            'llegada_confirmada': '#007bff',  # Azul oscuro
            'completada': '#6c757d',     # Gris
            'cancelada': '#dc3545',      # Rojo
            'no_show': '#fd7e14'         # Naranja
        }
        color = colores.get(obj.estado, '#6c757d')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_estado_display()
        )
    estado_coloreado.short_description = "Estado"

    def duracion_calculada(self, obj):
        """Muestra la duración calculada de la reserva"""
        return f"{obj.duracion_horas:.1f} horas"
    duracion_calculada.short_description = "Duración"

    def get_queryset(self, request):
        """Optimiza las consultas con select_related"""
        return super().get_queryset(request).select_related('cliente', 'habitacion')

@admin.register(FuncionarioHotel)
class FuncionarioHotelAdmin(admin.ModelAdmin):
    """Administración para funcionarios del hotel"""
    
    list_display = (
        'nombre',
        'telefono',
        'cargo',
        'permisos_resumen',
        'activo',
        'fecha_creacion'
    )
    
    list_filter = (
        'activo',
        'puede_confirmar_llegadas',
        'puede_cancelar_reservas',
        'puede_modificar_reservas',
        'fecha_creacion'
    )
    
    search_fields = ('nombre', 'telefono', 'cargo')
    
    fieldsets = (
        ('Información Personal', {
            'fields': ('nombre', 'telefono', 'cargo')
        }),
        ('Permisos', {
            'fields': (
                'puede_confirmar_llegadas',
                'puede_cancelar_reservas',
                'puede_modificar_reservas'
            )
        }),
        ('Estado', {
            'fields': ('activo',)
        })
    )

    def permisos_resumen(self, obj):
        """Muestra un resumen de los permisos del funcionario"""
        permisos = []
        if obj.puede_confirmar_llegadas:
            permisos.append("✅ Llegadas")
        if obj.puede_cancelar_reservas:
            permisos.append("❌ Cancelar")
        if obj.puede_modificar_reservas:
            permisos.append("✏️ Modificar")
        
        return " | ".join(permisos) if permisos else "Sin permisos"
    permisos_resumen.short_description = "Permisos"

@admin.register(ProcesoReserva)
class ProcesoReservaAdmin(admin.ModelAdmin):
    """Administración para procesos de reserva"""
    
    list_display = (
        'proceso_id',
        'cliente_telefono',
        'paso_actual',
        'estado_proceso',
        'fecha_inicio',
        'reserva_asociada'
    )
    
    list_filter = (
        'completado',
        'cancelado',
        'paso_actual',
        'fecha_inicio'
    )
    
    search_fields = (
        'cliente__telefono',
        'conversacion_id',
        'proceso_id'
    )
    
    readonly_fields = (
        'proceso_id',
        'fecha_inicio',
        'fecha_modificacion',
        'fecha_finalizacion'
    )

    def cliente_telefono(self, obj):
        """Muestra el teléfono del cliente"""
        return obj.cliente.telefono if obj.cliente else "Sin cliente"
    cliente_telefono.short_description = "Cliente"

    def estado_proceso(self, obj):
        """Muestra el estado del proceso con colores"""
        if obj.completado:
            return format_html('<span style="color: #28a745; font-weight: bold;">✅ Completado</span>')
        elif obj.cancelado:
            return format_html('<span style="color: #dc3545; font-weight: bold;">❌ Cancelado</span>')
        else:
            return format_html('<span style="color: #ffc107; font-weight: bold;">⏳ En Proceso</span>')
    estado_proceso.short_description = "Estado"

    def reserva_asociada(self, obj):
        """Muestra la reserva asociada si existe"""
        if obj.reserva_creada:
            url = reverse('admin:reservas_reservawhatsapp_change', args=[obj.reserva_creada.pk])
            return format_html('<a href="{}">Reserva #{}</a>', url, obj.reserva_creada.reserva_id)
        return "Sin reserva"
    reserva_asociada.short_description = "Reserva"

# REGISTRO SIMPLE SIN COMPLICACIONES
@admin.register(Habitacion)
class HabitacionAdmin(admin.ModelAdmin):
    list_display = ("nombre_habitacion", "precio_por_hora", "disponible", "capacidad")
    list_filter = ("disponible",)
    search_fields = ("nombre_habitacion", "descripcion")

# Solo registrar Reserva si no está ya registrado en api/admin.py
# COMENTAR ESTA PARTE SI YA ESTÁ REGISTRADO EN apps/api/admin.py
"""
@admin.register(Reserva)
class ReservaAdmin(admin.ModelAdmin):
    list_display = ("reserva_id", "cliente", "habitacion", "fecha", "fecha_hora_inicio", "fecha_hora_fin", "estado", "fecha_creacion")
    list_filter = ("estado", "fecha")
    search_fields = ("habitacion__nombre_habitacion", "cliente__nombre_cliente", "cliente__telefono")
    date_hierarchy = "fecha"
"""

@admin.register(EstadoConversacion)
class EstadoConversacionAdmin(admin.ModelAdmin):
    list_display = ("estado_conversacion_id", "cliente", "tipo", "paso_actual", "created_at", "updated_at")
    list_filter = ("tipo", "paso_actual", "created_at", "updated_at")
    search_fields = ("cliente__nombre_cliente", "cliente__telefono", "tipo", "paso_actual")
    readonly_fields = ("created_at", "updated_at", "datos_reserva")

    def cliente_info_display(self, obj):
        """Muestra información del cliente"""
        if obj.cliente:
            nombre = getattr(obj.cliente, 'nombre_cliente', 'Sin nombre')
            telefono = getattr(obj.cliente, 'telefono', 'Sin teléfono')
            return f"{nombre} ({telefono})"
        return "Cliente no asignado"
    cliente_info_display.short_description = "Información del Cliente"

    