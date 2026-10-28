from decimal import Decimal
def   calcular_ensayo(  valor : float ,   otro:Decimal )->Decimal:
    """Ensayo intencionado: float en firma y Decimal(0.1)."""
    resultado = Decimal(0.1)  +   otro
    return   resultado
