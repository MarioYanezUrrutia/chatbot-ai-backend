# En el archivo: apps/api/admin.py
from django.contrib import admin, messages
from django.shortcuts import render, redirect
from django.urls import path
from django import forms
from .models import (
    Cliente, Conversacion, Mensaje, TipoHabitacion, Habitacion, PreguntaFrecuente, Reserva, 
    BaseConocimiento, Persona, Rol, UserProfile, UserRol, PreguntaDesconocida
)
from django.contrib.auth.models import User # Importa el modelo User de Django

# --- Acción personalizada para el admin ---
# Esto añade la opción "Marcar como revisado" en el admin de Preguntas Desconocidas
@admin.action(description='Marcar seleccionados como revisados')
def marcar_como_revisado(modeladmin, request, queryset):
    queryset.update(revisada=True)

# --- Clases para personalizar la vista en el admin ---
class ConvertirPreguntaForm(forms.Form):
    pregunta_larga = forms.CharField(widget=forms.Textarea, required=True)
    pregunta_corta_boton = forms.CharField(max_length=20, required=True)
    respuesta = forms.CharField(widget=forms.Textarea, required=True)
    palabras_clave = forms.CharField(max_length=255, required=True)

class PreguntaDesconocidaAdmin(admin.ModelAdmin):
    """Personaliza cómo se ven las Preguntas Desconocidas en el admin."""
    list_display = ('texto_pregunta', 'cliente', 'fecha_recibida', 'revisada')
    list_filter = ('revisada', 'fecha_recibida')
    search_fields = ('texto_pregunta', 'cliente__telefono')
    actions = [marcar_como_revisado]
    # Hacemos que ciertos campos no se puedan editar directamente desde la lista
    readonly_fields = ('texto_pregunta', 'cliente', 'fecha_recibida')

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:pregunta_id>/convertir/',
                self.admin_site.admin_view(self.proceso_convertir),
                name='convertir-pregunta',
            ),
        ]
        return custom_urls + urls

    def proceso_convertir(self, request, pregunta_id, *args, **kwargs):
        pregunta_desconocida = self.get_object(request, pregunta_id)

        if request.method == 'POST':
            form = ConvertirPreguntaForm(request.POST)
            if form.is_valid():
                # Crear la nueva Pregunta Frecuente
                PreguntaFrecuente.objects.create(
                    pregunta_larga=form.cleaned_data['pregunta_larga'],
                    pregunta_corta_boton=form.cleaned_data['pregunta_corta_boton'],
                    respuesta=form.cleaned_data['respuesta'],
                    palabras_clave=form.cleaned_data['palabras_clave'],
                    activo=True
                )
                # Marcar la pregunta desconocida como revisada y eliminarla
                pregunta_desconocida.delete()
                self.message_user(request, "Pregunta convertida y eliminada exitosamente.", messages.SUCCESS)
                return redirect("..")
        else:
            form = ConvertirPreguntaForm(initial={'pregunta_larga': pregunta_desconocida.texto_pregunta})

        context = self.admin_site.each_context(request)
        context['opts'] = self.model._meta
        context['form'] = form
        context['title'] = f"Convertir Pregunta: '{pregunta_desconocida.texto_pregunta[:30]}...'"
        context['pregunta'] = pregunta_desconocida
        return render(request, 'admin/convertir_pregunta.html', context)

    @admin.action(description='Convertir seleccionada a Pregunta Frecuente')
    def convertir_a_pregunta_frecuente(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Por favor, selecciona solo una pregunta para convertir.", messages.ERROR)
            return
        selected = queryset.first()
        return redirect(f'{selected.pk}/convertir/')

    @admin.action(description='Eliminar seleccionadas permanentemente')
    def eliminar_seleccionados(self, request, queryset):
        queryset.delete()
        self.message_user(request, f"{queryset.count()} preguntas eliminadas exitosamente.", messages.SUCCESS)


class PreguntaFrecuenteAdmin(admin.ModelAdmin):
    """Personaliza cómo se ven las Preguntas Frecuentes en el admin."""
    list_display = ('pregunta_corta_boton', 'pregunta_larga', 'es_saludo_inicial', 'activo')
    search_fields = ('pregunta_larga', 'palabras_clave', 'respuesta')
    list_filter = ('activo', 'es_saludo_inicial')
    # Ordena los campos en el formulario de edición
    fieldsets = (
        (None, {
            'fields': ('pregunta_corta_boton', 'pregunta_larga', 'respuesta', 'palabras_clave')
        }),
        ('Configuración Avanzada', {
            'classes': ('collapse',),
            'fields': ('activo', 'es_saludo_inicial'),
        }),
    )

# --- Registrando cada modelo en el sitio de administración ---
# La forma más simple es admin.site.register(NombreDelModelo)
# Para los modelos que personalizamos, usamos la clase Admin correspondiente.

admin.site.register(Cliente)
admin.site.register(Conversacion)
admin.site.register(Mensaje)
admin.site.register(TipoHabitacion)
admin.site.register(Habitacion)
admin.site.register(PreguntaFrecuente, PreguntaFrecuenteAdmin) # Usamos la clase personalizada
admin.site.register(Reserva)
admin.site.register(BaseConocimiento)
admin.site.register(Persona)
admin.site.register(Rol)
admin.site.register(UserProfile)
admin.site.register(UserRol)
admin.site.register(PreguntaDesconocida, PreguntaDesconocidaAdmin) # Usamos la clase personalizada
