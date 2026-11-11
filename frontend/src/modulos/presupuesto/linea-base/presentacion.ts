import type { ErrorApi } from "@/api/errores";

const FORMATO_FECHA = new Intl.DateTimeFormat("es-MX", { dateStyle: "medium" });

/** D-8. El texto de un rechazo que no se pinta como bloqueo. Se decide por `tipo`, nunca por el mensaje:
 *  el `403` conserva el mensaje del servidor (y su pista de recarga) con la referencia de correlación. */
export function mensajeDeRechazo(error: ErrorApi): string {
  switch (error.tipo) {
    case "PERMISO":
      return `${error.mensaje} Referencia: ${error.correlacion_id}`;
    case "RED":
      return "Sin conexión con el servidor.";
    case "GENERICO":
      return error.correlacion_id === null
        ? "No se pudo completar la operación."
        : `No se pudo completar la operación. Referencia: ${error.correlacion_id}`;
    default:
      return error.mensaje;
  }
}

/** La fecha de un instante ISO en formato medio de `es-MX`, o `null` si la cadena no es una fecha válida. */
export function formatearFecha(iso: string): string | null {
  const instante = new Date(iso);
  return Number.isNaN(instante.getTime()) ? null : FORMATO_FECHA.format(instante);
}
