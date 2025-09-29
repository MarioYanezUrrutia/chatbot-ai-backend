# Script para crear funcionario - Ejecutar con: python manage.py shell < crear_funcionario.py

import os
import django

# Configurar Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.reservas.models import FuncionarioHotel

# Configuración del funcionario
TELEFONO_FUNCIONARIO = "56950148830"  # CAMBIA ESTE NÚMERO POR EL TUYO
NOMBRE_FUNCIONARIO = "Administrador Pratsy"  # CAMBIA EL NOMBRE

try:
    # Verificar si ya existe
    funcionario_existente = FuncionarioHotel.objects.filter(telefono=TELEFONO_FUNCIONARIO).first()
    
    if funcionario_existente:
        print(f"⚠️  El funcionario con teléfono {TELEFONO_FUNCIONARIO} ya existe:")
        print(f"   - Nombre: {funcionario_existente.nombre}")
        print(f"   - Activo: {funcionario_existente.activo}")
        
        # Actualizar si no está activo
        if not funcionario_existente.activo:
            funcionario_existente.activo = True
            funcionario_existente.save()
            print("✅ Funcionario reactivado")
        else:
            print("✅ Funcionario ya está activo")
    else:
        # Crear nuevo funcionario
        funcionario = FuncionarioHotel.objects.create(
            telefono=TELEFONO_FUNCIONARIO,
            nombre=NOMBRE_FUNCIONARIO,
            activo=True
        )
        print(f"✅ Funcionario creado exitosamente:")
        print(f"   - Teléfono: {funcionario.telefono}")
        print(f"   - Nombre: {funcionario.nombre}")
        print(f"   - Activo: {funcionario.activo}")
    
    # Mostrar todos los funcionarios
    print("\n📋 Funcionarios registrados:")
    funcionarios = FuncionarioHotel.objects.all()
    for f in funcionarios:
        estado = "🟢 Activo" if f.activo else "🔴 Inactivo"
        print(f"   - {f.nombre} ({f.telefono}) - {estado}")
    
    print(f"\n🔑 Para activar modo funcionario, envía: kabymur")
    print(f"   desde el número: {TELEFONO_FUNCIONARIO}")

except Exception as e:
    print(f"❌ Error: {e}")