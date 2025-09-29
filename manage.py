#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

# --- INICIO DEL PARCHE DE CODIFICACIÓN ---
import sys
import os

# 1. Forzar la codificación de la consola (buena práctica)
if sys.stdout.encoding != 'utf-8' and sys.stdout.isatty():
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8' and sys.stderr.isatty():
    sys.stderr.reconfigure(encoding='utf-8')

# 2. El "Monkey-Patch" para la librería requests/certifi en Windows
# Esto soluciona el error 'ascii' codec al hacer peticiones HTTPS.
try:
    import certifi
    
    # Guardamos la función original
    original_where = certifi.where
    
    # Definimos nuestra nueva función "wrapper"
    def patched_where():
        try:
            # Intentamos llamar a la función original
            return original_where()
        except UnicodeDecodeError:
            # Si falla con el error de codificación, usamos una ruta alternativa
            # que no depende de la codificación del sistema.
            # Esto es un poco más lento, pero es un respaldo seguro.
            import importlib.resources
            return str(importlib.resources.files("certifi").joinpath("cacert.pem"))

    # Reemplazamos la función original por nuestra versión parcheada
    certifi.where = patched_where
    print("INFO: Se ha aplicado el parche de codificación para 'certifi'.")

except ImportError:
    # Si certifi no está instalado, no hacemos nada.
    pass
# --- FIN DEL PARCHE DE CODIFICACIÓN ---

def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)

if __name__ == '__main__':
    main()
