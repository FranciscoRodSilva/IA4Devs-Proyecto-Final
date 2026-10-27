import DecimalBase from "decimal.js";

/** Precisión holgada para totales de presentación; el redondeo de presentación es ROUND_HALF_UP (PA-T5). */
export const Decimal = DecimalBase.clone({ precision: 40, rounding: DecimalBase.ROUND_HALF_UP });
export type Decimal = InstanceType<typeof Decimal>;

const DECIMAL_PLANO = /^-?\d+(\.\d+)?$/;
const ENTERO_NO_NEGATIVO = /^\d{1,9}$/;
const FORMATO_IMPORTE = new Intl.NumberFormat("es-MX", {
  style: "currency", currency: "MXN", minimumFractionDigits: 2, maximumFractionDigits: 2,
});
const FORMATO_CANTIDAD = new Intl.NumberFormat("es-MX", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Cadena decimal plana del API → Decimal; cualquier otra forma (exponente, Infinity, NaN, hexadecimal, vacío) → null. */
export function aDecimal(valor: string): Decimal | null {
  return DECIMAL_PLANO.test(valor) ? new Decimal(valor) : null;
}

function aDosDecimales(valor: string | Decimal): Intl.StringNumericLiteral | null {
  const d = typeof valor === "string" ? aDecimal(valor) : valor;
  if (d === null || !d.isFinite()) return null;
  const redondeado = d.toDecimalPlaces(2, Decimal.ROUND_HALF_UP);
  // Un valor que redondea a cero se presenta sin signo: "-0.00" no es un importe.
  return (redondeado.isZero() ? "0.00" : redondeado.toFixed(2)) as Intl.StringNumericLiteral;
}

/** "1234.5650" → "$1,234.57". Redondea solo aquí; Intl recibe la cadena ya redondeada, nunca un number. */
export function formatearImporte(valor: string | Decimal): string | null {
  const texto = aDosDecimales(valor);
  return texto === null ? null : FORMATO_IMPORTE.format(texto);
}

/** "100.0000", "PZA" → "100.00 PZA". */
export function formatearCantidad(valor: string | Decimal, unidad?: string): string | null {
  const texto = aDosDecimales(valor);
  if (texto === null) return null;
  const cifra = FORMATO_CANTIDAD.format(texto);
  return unidad === undefined ? cifra : `${cifra} ${unidad}`;
}

/** Cabecera Retry-After en segundos → entero; cualquier otra forma → null. Vive aquí porque este
 *  módulo es el único exento de la prohibición de conversiones numéricas (PA-T11). */
export function enteroNoNegativo(texto: string | null): number | null {
  return texto !== null && ENTERO_NO_NEGATIVO.test(texto) ? new Decimal(texto).toNumber() : null;
}
