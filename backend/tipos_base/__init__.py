"""Tipos numéricos base de CIMENTA (TKT-004). Regla 1 y 2 de CLAUDE.md.

Paquete fuera de `cimenta/`: lo importan todos los módulos y solo alcanza la biblioteca estándar.
"""

from tipos_base.numericos import Cantidad, Dinero, Porcentaje, Rendimiento, sumar

__all__ = ["Cantidad", "Dinero", "Porcentaje", "Rendimiento", "sumar"]
