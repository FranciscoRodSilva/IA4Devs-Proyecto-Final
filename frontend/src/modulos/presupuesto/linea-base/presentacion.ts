import type { ErrorApi } from "@/api/errores";
import type { components } from "@/api/generado/servidor";
import { formatearImporte } from "@/compartido/dinero/dinero";

type PresupuestoControl = components["schemas"]["PresupuestoControl"];

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

/** Importe desde la cadena del servidor con `decimal.js`; lo que no es un decimal plano nunca se pinta crudo. */
export function importe(valor: string): string {
  return formatearImporte(valor) ?? "No disponible";
}

/** Quien capturó o actualizó por última vez un tope y cuándo, o `null` si aún no se captura. */
export function autorYFecha(
  fila: PresupuestoControl,
): { nombre: string; instante: string; fecha: string | null } | null {
  const autor = fila.actualizado_por ?? fila.capturado_por ?? null;
  const instante = fila.actualizado_en ?? fila.capturado_en ?? null;
  if (autor === null || instante === null) return null;
  return { nombre: autor.nombre, instante, fecha: formatearFecha(instante) };
}

/** D-5. El texto de un rechazo de validación junto al campo del tope. */
export function mensajeDeValidacionTope(error: Extract<ErrorApi, { tipo: "VALIDACION" }>): string {
  const deTope = error.errores.find((detalle) => detalle.campo === "importe_tope") ?? error.errores[0];
  return deTope?.mensaje ?? error.mensaje;
}

/** D-5. El texto de un rechazo junto al campo de su fila. Se decide por `tipo`, nunca por el mensaje. */
export function mensajeDeFila(error: ErrorApi): string {
  switch (error.tipo) {
    case "VALIDACION":
      return mensajeDeValidacionTope(error);
    case "REGLA_NEGOCIO":
    case "CONFLICTO":
    case "CONCURRENCIA":
      return error.mensaje;
    default:
      return mensajeDeRechazo(error);
  }
}
