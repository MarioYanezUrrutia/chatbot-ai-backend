# apps/api/serializers.py
from rest_framework import serializers
from .models import Reserva, Habitacion, Cliente

class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = ['cliente_id', 'nombre_cliente', 'telefono', 'email']

class HabitacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Habitacion
        fields = ['habitacion_id', 'nombre_habitacion', 'precio_por_hora', 'capacidad', 'disponible']

class ReservaSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source='cliente.nombre_cliente', read_only=True)
    habitacion_nombre = serializers.CharField(source='habitacion.nombre_habitacion', read_only=True)
    cliente_telefono = serializers.CharField(source='cliente.telefono', read_only=True)
    
    class Meta:
        model = Reserva
        fields = [
            'reserva_id', 
            'cliente', 
            'cliente_nombre',
            'cliente_telefono',
            'habitacion', 
            'habitacion_nombre',
            'fecha',
            'fecha_hora_inicio', 
            'fecha_hora_fin', 
            'estado', 
            'fecha_creacion',
            'fecha_llegada',
            'telefono',
            'duracion',
            'precio_total',
            'origen'
        ]
        read_only_fields = ['reserva_id', 'fecha', 'fecha_creacion']

class ReservaCreateSerializer(serializers.ModelSerializer):
    """Serializer específico para crear reservas desde el frontend"""
    nombre_cliente = serializers.CharField(write_only=True)
    
    class Meta:
        model = Reserva
        fields = [
            'nombre_cliente',
            'telefono',
            'habitacion',
            'fecha_hora_inicio',
            'fecha_hora_fin',
            'duracion',
            'precio_total',
            'origen'
        ]
    
    def create(self, validated_data):
        nombre_cliente = validated_data.pop('nombre_cliente')
        telefono = validated_data.get('telefono')
        
        # Obtener o crear cliente
        cliente, created = Cliente.objects.get_or_create(
            telefono=telefono,
            defaults={'nombre_cliente': nombre_cliente}
        )
        
        validated_data['cliente'] = cliente
        validated_data['estado'] = 'pendiente'
        
        return Reserva.objects.create(**validated_data)

class EstadisticasSerializer(serializers.Serializer):
    """Serializer para las estadísticas del dashboard"""
    total_reservas = serializers.IntegerField()
    reservas_hoy = serializers.IntegerField()
    ingresos_mes = serializers.DecimalField(max_digits=10, decimal_places=2)
    clientes_nuevos = serializers.IntegerField()
    reservas_por_estado = serializers.DictField()
    reservas_por_origen = serializers.DictField()