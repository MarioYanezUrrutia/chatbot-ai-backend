# En el archivo: apps/api/admin.py
from django.contrib import admin, messages
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django import forms
from django.utils.html import format_html
from .models import (
    Cliente, Conversacion, Mensaje, TipoHabitacion, Habitacion, PreguntaFrecuente, Reserva, 
    BaseConocimiento, Persona, Rol, UserProfile, UserRol, PreguntaDesconocida
)
from django.contrib.auth.models import User

# --- ACCIONES PERSONALIZADAS PARA EL ADMIN ---
@admin.action(description='Marcar seleccionados como revisados')
def marcar_como_revisado(modeladmin, request, queryset):
    queryset.update(revisada=True)
    messages.success(request, f"{queryset.count()} preguntas marcadas como revisadas.")

@admin.action(description='Eliminar seleccionadas permanentemente')
def eliminar_preguntas_desconocidas(modeladmin, request, queryset):
    count = queryset.count()
    queryset.delete()
    messages.success(request, f"{count} preguntas eliminadas permanentemente.")

# --- FORMULARIO PARA CONVERTIR PREGUNTA ---
class ConvertirPreguntaForm(forms.Form):
    pregunta_larga = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'cols': 60}), 
        required=True,
        label="Pregunta completa",
        help_text="La pregunta completa que el bot usará para buscar"
    )
    pregunta_corta_boton = forms.CharField(
        max_length=20, 
        required=True,
        label="Texto del botón",
        help_text="MÁXIMO 20 caracteres para el botón de WhatsApp"
    )
    respuesta = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5, 'cols': 60}), 
        required=True,
        label="Respuesta",
        help_text="La respuesta que dará el bot"
    )
    palabras_clave = forms.CharField(
        max_length=255, 
        required=True,
        label="Palabras clave",
        help_text="Palabras clave separadas por comas (ej: horario, precio, reserva)"
    )
    es_saludo_inicial = forms.BooleanField(
        required=False,
        label="¿Es mensaje de saludo?",
        help_text="Marcar SOLO si esta debe ser la respuesta de bienvenida principal"
    )

    def clean_pregunta_corta_boton(self):
        texto = self.cleaned_data['pregunta_corta_boton']
        if len(texto) > 20:
            raise forms.ValidationError("El texto del botón no puede superar los 20 caracteres.")
        return texto

# --- ADMIN PERSONALIZADO PARA PREGUNTAS DESCONOCIDAS ---
class PreguntaDesconocidaAdmin(admin.ModelAdmin):
    """Administración mejorada para Preguntas Desconocidas con nuevas funcionalidades"""
    
    list_display = ('texto_pregunta_truncado', 'cliente_info', 'fecha_recibida', 'revisada', 'acciones_personalizadas')
    list_filter = ('revisada', 'fecha_recibida')
    # CORREGIDO: Agregar campos de búsqueda correctos
    search_fields = ('texto_pregunta', 'cliente__nombre_cliente', 'cliente__telefono')
    actions = [marcar_como_revisado, eliminar_preguntas_desconocidas]
    readonly_fields = ('texto_pregunta', 'fecha_recibida')
    ordering = ['-fecha_recibida']
    
    def get_queryset(self, request):
        """Optimizar consultas con select_related/prefetch_related"""
        queryset = super().get_queryset(request)
        # CORREGIDO: Usar la relación correcta según tu modelo
        return queryset.select_related('cliente')
    
    def texto_pregunta_truncado(self, obj):
        """Muestra los primeros 60 caracteres de la pregunta"""
        if len(obj.texto_pregunta) > 60:
            return f"{obj.texto_pregunta[:60]}..."
        return obj.texto_pregunta
    texto_pregunta_truncado.short_description = "Pregunta"
    
    def cliente_info(self, obj):
        """Muestra información del cliente - CORREGIDO"""
        try:
            # CORREGIDO: Usar la relación directa 'cliente' según tu modelo
            if obj.cliente:
                nombre = getattr(obj.cliente, 'nombre_cliente', None) or "Sin nombre"
                telefono = getattr(obj.cliente, 'telefono', 'Sin teléfono')
                return f"{nombre} ({telefono})"
            else:
                return "Cliente no asignado"
                    
        except Exception as e:
            return f"Error: {str(e)}"
    cliente_info.short_description = "Cliente"
    
    def acciones_personalizadas(self, obj):
        """Muestra botones de acción personalizados"""
        convertir_url = reverse('admin:convertir-pregunta', args=[obj.pregunta_desconocida_id])
        eliminar_url = reverse('admin:eliminar-pregunta-individual', args=[obj.pregunta_desconocida_id])
        
        html = f'''
        <div style="display: flex; gap: 5px;">
            <a href="{convertir_url}" class="button" style="background: #417690; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px; font-size: 12px;">
                📝 Convertir a FAQ
            </a>
            <a href="{eliminar_url}" class="button" style="background: #ba2121; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px; font-size: 12px;" 
               onclick="return confirm('¿Estás seguro de que quieres eliminar esta pregunta permanentemente?')">
                🗑️ Eliminar
            </a>
        </div>
        '''
        return format_html(html)
    acciones_personalizadas.short_description = "Acciones"
    acciones_personalizadas.allow_tags = True

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:pregunta_id>/convertir/',
                self.admin_site.admin_view(self.vista_convertir_pregunta),
                name='convertir-pregunta',
            ),
            path(
                '<int:pregunta_id>/eliminar/',
                self.admin_site.admin_view(self.vista_eliminar_pregunta),
                name='eliminar-pregunta-individual',
            ),
        ]
        return custom_urls + urls

    def vista_convertir_pregunta(self, request, pregunta_id, *args, **kwargs):
        """Vista para convertir una pregunta desconocida en pregunta frecuente - CORREGIDO"""
        try:
            pregunta_desconocida = PreguntaDesconocida.objects.get(pregunta_desconocida_id=pregunta_id)
        except PreguntaDesconocida.DoesNotExist:
            messages.error(request, "La pregunta desconocida no existe.")
            return redirect("..")

        if request.method == 'POST':
            form = ConvertirPreguntaForm(request.POST)
            if form.is_valid():
                try:
                    # Verificar si ya existe una pregunta de saludo si se marca como tal
                    if form.cleaned_data['es_saludo_inicial']:
                        saludo_existente = PreguntaFrecuente.objects.filter(es_saludo_inicial=True, activo=True).first()
                        if saludo_existente:
                            messages.warning(
                                request, 
                                f"Ya existe una pregunta marcada como saludo inicial: '{saludo_existente.pregunta_corta_boton}'. "
                                f"Se deshabilitará automáticamente para usar la nueva."
                            )
                            saludo_existente.es_saludo_inicial = False
                            saludo_existente.save()
                    
                    # CORREGIDO: No especificar el ID, dejar que Django lo genere automáticamente
                    nueva_faq = PreguntaFrecuente.objects.create(
                        pregunta_larga=form.cleaned_data['pregunta_larga'],
                        pregunta_corta_boton=form.cleaned_data['pregunta_corta_boton'],
                        respuesta=form.cleaned_data['respuesta'],
                        palabras_clave=form.cleaned_data['palabras_clave'],
                        es_saludo_inicial=form.cleaned_data['es_saludo_inicial'],
                        activo=True
                        # NO especificar pregunta_frecuenta_id - Django lo generará automáticamente
                    )
                    
                    # Eliminar la pregunta desconocida
                    pregunta_desconocida.delete()
                    
                    messages.success(
                        request, 
                        f"✅ Pregunta convertida exitosamente a FAQ con ID {nueva_faq.pregunta_frecuenta_id} y eliminada de preguntas desconocidas."
                    )
                    return redirect("..")
                    
                except Exception as e:
                    messages.error(request, f"❌ Error al convertir la pregunta: {str(e)}")
        else:
            # Pre-llenar el formulario con la pregunta original
            form = ConvertirPreguntaForm(initial={
                'pregunta_larga': pregunta_desconocida.texto_pregunta,
                'pregunta_corta_boton': pregunta_desconocida.texto_pregunta[:20] if len(pregunta_desconocida.texto_pregunta) <= 20 else pregunta_desconocida.texto_pregunta[:17] + "..."
            })

        # Preparar contexto para el template
        context = self.admin_site.each_context(request)
        context.update({
            'opts': self.model._meta,
            'form': form,
            'title': f"Convertir Pregunta Desconocida a FAQ",
            'subtitle': f"'{pregunta_desconocida.texto_pregunta[:50]}...'",
            'pregunta': pregunta_desconocida,
            'original_url': request.META.get('HTTP_REFERER', '../'),
        })
        
        return render(request, 'admin/convertir_pregunta.html', context)

    def vista_eliminar_pregunta(self, request, pregunta_id, *args, **kwargs):
        """Vista para eliminar una pregunta desconocida individual"""
        try:
            pregunta_desconocida = PreguntaDesconocida.objects.get(pregunta_desconocida_id=pregunta_id)
            texto_pregunta = pregunta_desconocida.texto_pregunta[:50]
            pregunta_desconocida.delete()
            
            messages.success(
                request, 
                f"🗑️ Pregunta eliminada permanentemente: '{texto_pregunta}...'"
            )
        except PreguntaDesconocida.DoesNotExist:
            messages.error(request, "❌ La pregunta desconocida no existe.")
        
        return redirect("..")

# --- ADMIN MEJORADO PARA PREGUNTAS FRECUENTES ---
class PreguntaFrecuenteAdmin(admin.ModelAdmin):
    """Administración mejorada para Preguntas Frecuentes"""
    
    list_display = ('pregunta_corta_boton', 'pregunta_larga_truncada', 'es_saludo_inicial', 'activo', 'fecha_creacion')
    search_fields = ('pregunta_larga', 'palabras_clave', 'respuesta', 'pregunta_corta_boton')
    list_filter = ('activo', 'es_saludo_inicial', 'fecha_creacion')
    ordering = ['-fecha_creacion']
    
    def pregunta_larga_truncada(self, obj):
        """Muestra los primeros 50 caracteres de la pregunta larga"""
        if len(obj.pregunta_larga) > 50:
            return f"{obj.pregunta_larga[:50]}..."
        return obj.pregunta_larga
    pregunta_larga_truncada.short_description = "Pregunta Completa"
    
    # Organizar campos en el formulario de edición
    fieldsets = (
        ('Información Básica', {
            'fields': ('pregunta_corta_boton', 'pregunta_larga', 'respuesta', 'palabras_clave')
        }),
        ('Configuración Avanzada', {
            'classes': ('collapse',),
            'fields': ('activo', 'es_saludo_inicial'),
            'description': 'IMPORTANTE: Solo puede haber UNA pregunta marcada como saludo inicial activa.'
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Validar que solo haya un saludo inicial activo"""
        if obj.es_saludo_inicial and obj.activo:
            # Desactivar otros saludos iniciales
            otros_saludos = PreguntaFrecuente.objects.filter(
                es_saludo_inicial=True, 
                activo=True
            ).exclude(pregunta_frecuenta_id=obj.pregunta_frecuenta_id)
            
            if otros_saludos.exists():
                count = otros_saludos.count()
                otros_saludos.update(es_saludo_inicial=False)
                messages.warning(
                    request, 
                    f"Se deshabilitaron {count} preguntas que estaban marcadas como saludo inicial para activar esta."
                )
        
        super().save_model(request, obj, form, change)

# --- REGISTRAR MODELOS EN EL ADMIN ---
admin.site.register(Cliente)
admin.site.register(Conversacion)
admin.site.register(Mensaje)
admin.site.register(TipoHabitacion)
# admin.site.register(Habitacion)
admin.site.register(PreguntaFrecuente, PreguntaFrecuenteAdmin)
# admin.site.register(Reserva)
admin.site.register(BaseConocimiento)
admin.site.register(Persona)
admin.site.register(Rol)
admin.site.register(UserProfile)
admin.site.register(UserRol)
admin.site.register(PreguntaDesconocida, PreguntaDesconocidaAdmin)

# --- PERSONALIZACIÓN DEL SITIO DE ADMINISTRACIÓN ---
admin.site.site_header = "Administración Pratsy Bot"
admin.site.site_title = "Pratsy Admin"
admin.site.index_title = "Panel de Administración del Bot"