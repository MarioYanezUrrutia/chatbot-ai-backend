#!/usr/bin/env python3
"""
Script para resetear conversaciones de WhatsApp cuando se quedan pegadas
Ejecutar desde la raíz del proyecto: python reset_whatsapp_conversation.py
"""

import os
import sys
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.api.models import Cliente
from apps.reservas.models import EstadoConversacion, ProcesoReserva


def reset_client_conversation(telefono):
    """Resetea la conversación de un cliente específico"""
    try:
        # Buscar cliente por teléfono
        cliente = Cliente.objects.get(telefono=telefono)
        print(f"✅ Cliente encontrado: {cliente.nombre_cliente or 'Sin nombre'} ({telefono})")
        
        # Eliminar estados de conversación
        estados_eliminados = EstadoConversacion.objects.filter(cliente=cliente).delete()
        print(f"   - Estados de conversación eliminados: {estados_eliminados[0]}")
        
        # Eliminar procesos de reserva activos
        procesos_eliminados = ProcesoReserva.objects.filter(
            cliente=cliente,
            completado=False,
            cancelado=False
        ).delete()
        print(f"   - Procesos de reserva activos eliminados: {procesos_eliminados[0]}")
        
        print(f"🎉 Conversación de {telefono} reseteada exitosamente")
        return True
        
    except Cliente.DoesNotExist:
        print(f"❌ Cliente con teléfono {telefono} no encontrado")
        return False
    except Exception as e:
        print(f"❌ Error reseteando conversación de {telefono}: {e}")
        return False


def reset_all_conversations():
    """Resetea TODAS las conversaciones activas"""
    try:
        print("⚠️  RESETEANDO TODAS LAS CONVERSACIONES...")
        
        # Contar antes de eliminar
        total_estados = EstadoConversacion.objects.count()
        total_procesos_activos = ProcesoReserva.objects.filter(
            completado=False,
            cancelado=False
        ).count()
        
        print(f"   - Estados de conversación encontrados: {total_estados}")
        print(f"   - Procesos de reserva activos: {total_procesos_activos}")
        
        # Eliminar todos los estados de conversación
        EstadoConversacion.objects.all().delete()
        
        # Cancelar todos los procesos de reserva activos
        ProcesoReserva.objects.filter(
            completado=False,
            cancelado=False
        ).update(cancelado=True)
        
        print(f"🎉 TODAS las conversaciones han sido reseteadas")
        print(f"   - {total_estados} estados eliminados")
        print(f"   - {total_procesos_activos} procesos cancelados")
        
        return True
        
    except Exception as e:
        print(f"❌ Error reseteando todas las conversaciones: {e}")
        return False


def list_active_conversations():
    """Lista todas las conversaciones activas"""
    try:
        print("📋 CONVERSACIONES ACTIVAS:")
        print("-" * 50)
        
        # Estados de conversación
        estados = EstadoConversacion.objects.select_related('cliente').all()
        if estados:
            print(f"Estados de Conversación ({estados.count()}):")
            for estado in estados:
                cliente_info = f"{estado.cliente.nombre_cliente or 'Sin nombre'} ({estado.cliente.telefono})"
                print(f"  - {cliente_info}")
                print(f"    Tipo: {estado.tipo}, Paso: {estado.paso_actual}")
                print(f"    Actualizado: {estado.updated_at}")
                print()
        else:
            print("  No hay estados de conversación activos")
        
        # Procesos de reserva activos
        procesos = ProcesoReserva.objects.filter(
            completado=False,
            cancelado=False
        ).select_related('cliente')
        
        if procesos:
            print(f"Procesos de Reserva Activos ({procesos.count()}):")
            for proceso in procesos:
                cliente_info = f"{proceso.cliente.nombre_cliente or 'Sin nombre'} ({proceso.cliente.telefono})"
                print(f"  - {cliente_info}")
                print(f"    Paso: {proceso.paso_actual}")
                print(f"    Iniciado: {proceso.fecha_inicio}")
                print()
        else:
            print("  No hay procesos de reserva activos")
        
    except Exception as e:
        print(f"❌ Error listando conversaciones: {e}")


def main():
    """Función principal del script"""
    print("🤖 SCRIPT DE RESETEO DE CONVERSACIONES WHATSAPP")
    print("=" * 50)
    
    if len(sys.argv) == 1:
        # Modo interactivo
        print("Opciones disponibles:")
        print("1. Resetear conversación de un cliente específico")
        print("2. Resetear TODAS las conversaciones")
        print("3. Listar conversaciones activas")
        print("4. Salir")
        
        while True:
            try:
                opcion = input("\nSelecciona una opción (1-4): ").strip()
                
                if opcion == "1":
                    telefono = input("Ingresa el número de teléfono: ").strip()
                    if telefono:
                        reset_client_conversation(telefono)
                    else:
                        print("❌ Número de teléfono requerido")
                
                elif opcion == "2":
                    confirmacion = input("⚠️  ¿Estás seguro de resetear TODAS las conversaciones? (si/no): ").strip().lower()
                    if confirmacion in ['si', 'sí', 's', 'yes', 'y']:
                        reset_all_conversations()
                    else:
                        print("❌ Operación cancelada")
                
                elif opcion == "3":
                    list_active_conversations()
                
                elif opcion == "4":
                    print("👋 ¡Hasta luego!")
                    break
                
                else:
                    print("❌ Opción inválida. Selecciona 1-4.")
                    
            except KeyboardInterrupt:
                print("\n👋 ¡Hasta luego!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    else:
        # Modo comando directo
        comando = sys.argv[1].lower()
        
        if comando == "list":
            list_active_conversations()
        
        elif comando == "reset-all":
            reset_all_conversations()
        
        elif comando == "reset-client" and len(sys.argv) > 2:
            telefono = sys.argv[2]
            reset_client_conversation(telefono)
        
        else:
            print("❌ Uso:")
            print("  python reset_whatsapp_conversation.py                    # Modo interactivo")
            print("  python reset_whatsapp_conversation.py list               # Listar conversaciones")
            print("  python reset_whatsapp_conversation.py reset-all          # Resetear todas")
            print("  python reset_whatsapp_conversation.py reset-client 56123456789  # Resetear cliente específico")


if __name__ == "__main__":
    main()