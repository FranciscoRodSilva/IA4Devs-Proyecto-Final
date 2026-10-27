import type { components } from "@/api/generado/contrato-error.provisional";
import { enteroNoNegativo } from "@/compartido/dinero/dinero";

type Esquemas = components["schemas"];
export type Accion = Esquemas["Accion"];
export type ErrorReglaNegocio = Esquemas["ErrorReglaNegocio"];
export type ErrorConflictoEstado = Esquemas["ErrorConflictoEstado"];
export type ErrorConcurrencia = Esquemas["ErrorConcurrencia"] & { reintentar_tras_s: number | null };
export type ErrorValidacion = Esquemas["ErrorValidacion"];
export type ErrorPermiso = Esquemas["ErrorPermiso"];
export type ErrorSesion = Esquemas["ErrorSesion"];
export type ErrorLimiteIntentos = Esquemas["ErrorLimiteIntentos"];
export type ErrorNoEncontrado = Esquemas["ErrorNoEncontrado"];
/** Fuera del contrato: 500, cuerpo que no es JSON, `tipo` desconocido o que no casa con su código. */
export type ErrorGenerico = { tipo: "GENERICO"; estado: number; mensaje: string | null; correlacion_id: string | null };
/** La petición no llegó al servidor. Distinto de cualquier tipo del contrato y de un 401 (CA-4 esc. 3). */
export type ErrorRed = { tipo: "RED" };

/** La entrada de la pantalla de bloqueo: solo los 409 (CA-9 esc. 4). */
export type ErrorBloqueo = ErrorReglaNegocio | ErrorConflictoEstado | ErrorConcurrencia;
export type ErrorApi =
  | ErrorBloqueo | ErrorValidacion | ErrorPermiso | ErrorSesion | ErrorLimiteIntentos | ErrorNoEncontrado
  | ErrorGenerico | ErrorRed;

export const ESTADO_DE_TIPO = {
  REGLA_NEGOCIO: 409, CONFLICTO: 409, CONCURRENCIA: 409, VALIDACION: 422,
  PERMISO: 403, SESION: 401, LIMITE_INTENTOS: 429, NO_ENCONTRADO: 404,
} as const;

type TipoContrato = keyof typeof ESTADO_DE_TIPO;

/** Objeto no nulo y no arreglo. */
export function esObjeto(valor: unknown): valor is Record<string, unknown> {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

function esTipoContrato(valor: unknown): valor is TipoContrato {
  // Object.hasOwn y no `in`: `"toString" in ESTADO_DE_TIPO` sería verdadero.
  return typeof valor === "string" && Object.hasOwn(ESTADO_DE_TIPO, valor);
}

function cadenaONull(valor: unknown): string | null {
  return typeof valor === "string" ? valor : null;
}

/** M3 · CA-4. Un cuerpo es del contrato si y solo si es un objeto con `tipo` en ESTADO_DE_TIPO, ese tipo
 *  corresponde al código de estado recibido y `mensaje` es cadena; entonces se devuelve tal cual llegó
 *  (las acciones conservan orden y ruta), y CONCURRENCIA añade `reintentar_tras_s` =
 *  enteroNoNegativo(cabeceras.get("Retry-After")). Todo lo demás es GENERICO con `mensaje` y
 *  `correlacion_id` solo si son cadenas del cuerpo. No valida el resto de la forma con ningún esquema
 *  escrito a mano (CA-13 esc. 4): la forma la garantizan los tipos generados y TKT-061. Nunca lanza. */
export function normalizarError(estado: number, cuerpo: unknown, cabeceras: Headers): ErrorApi {
  const mensaje = esObjeto(cuerpo) ? cadenaONull(cuerpo.mensaje) : null;
  const correlacion_id = esObjeto(cuerpo) ? cadenaONull(cuerpo.correlacion_id) : null;

  if (!esObjeto(cuerpo) || !esTipoContrato(cuerpo.tipo) || ESTADO_DE_TIPO[cuerpo.tipo] !== estado || mensaje === null) {
    return { tipo: "GENERICO", estado, mensaje, correlacion_id };
  }

  // Dos aserciones, concentradas aquí: el discriminador y el código de estado ya se comprobaron arriba.
  if (cuerpo.tipo === "CONCURRENCIA") {
    const reintentar_tras_s = enteroNoNegativo(cabeceras.get("Retry-After"));
    return { ...(cuerpo as unknown as Omit<ErrorConcurrencia, "reintentar_tras_s">), reintentar_tras_s };
  }
  return cuerpo as unknown as ErrorApi;
}
