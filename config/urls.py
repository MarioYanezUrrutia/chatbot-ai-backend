# config/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

# Vista para la página de inicio
def home_view(request):
    return HttpResponse("""
    <h1>Pratsy Bot - Motel Assistant</h1>
    <p><a href="/admin/">Panel de Administración</a></p>
    <p><a href="/api/chat/">Chat Web</a></p>
    <p><a href="/api/whatsapp/">Webhook WhatsApp</a></p>
    """)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home_view, name='home'),
    path('api/', include('apps.api.urls')),  # Incluir URLs de tu app
    # path('api/', include('apps.reservas.urls')), # Si decides crear una API REST para el frontend
]

# Servir archivos estáticos en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)