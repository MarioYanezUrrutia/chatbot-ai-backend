# backend/api/urls.py
from django.shortcuts import render
from django.urls import path
from .views import webhook_whatsapp  # Correcto: import relativo
from .views_web_chat import WebChatView, PreguntasFrecuentesView
from django.http import HttpResponse
from django.conf import settings
import os

# Vista simple para servir el chat HTML
# def chat_view(request):
#     return HttpResponse("""
#     <!DOCTYPE html>
#     <html>
#     <head><title>Chat Pratsy</title></head>
#     <body>
#         <h1>Chat temporalmente no disponible</h1>
#         <p>El archivo HTML del chat debe configurarse aquí.</p>
#     </body>
#     </html>
#     """)
def chat_view(request):
    return render(request, 'chat/avatar-chat-page.html')

urlpatterns = [
    path('whatsapp/', webhook_whatsapp, name='whatsapp_webhook'),
    path('web-chat/', WebChatView.as_view(), name='web_chat'),
    path('preguntas-frecuentes/', PreguntasFrecuentesView.as_view(), name='preguntas_frecuentes'),
    path('chat/', chat_view, name='chat_page'),
]