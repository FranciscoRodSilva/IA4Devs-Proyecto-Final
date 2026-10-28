import type { components as Provisional } from "@/api/generado/contrato-error.provisional";
import type { components as Servidor } from "@/api/generado/servidor";
import type { Rol, UsuarioActual } from "@/api/sesion";

// Fábricas de cuerpos de respuesta con nombre del dominio. Cada una cumple por compilación el esquema generado
// (`satisfies`): si el contrato cambia, `npm run typecheck` lo dice. Los identificadores son constantes fijas.
type Errores = Provisional["schemas"];
type Esquemas = Servidor["schemas"];

const CORRELACION_ID = "7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e";
const ID_USUARIO = "0b6f1c3e-2d4a-4e5f-8a7b-9c0d1e2f3a4b";

export function usuarioActual(roles: Rol[], cambios: Partial<UsuarioActual> = {}): UsuarioActual {
  return {
    id: ID_USUARIO,
    nombre: "Rosa Villanueva",
    email: "rosa@cimenta.test",
    roles,
    sesion: { expira_en: "2026-10-27T02:00:00Z", expira_por_inactividad_en: "2026-10-26T22:00:00Z" },
    ...cambios,
  } satisfies Esquemas["UsuarioActual"];
}

export function tokenCsrf(token = "token-de-prueba"): Esquemas["TokenCsrf"] {
  return { token } satisfies Esquemas["TokenCsrf"];
}

export function errorSesion(motivo: Errores["ErrorSesion"]["motivo"]): Errores["ErrorSesion"] {
  return {
    tipo: "SESION",
    motivo,
    mensaje: "La sesión no es válida.",
    correlacion_id: CORRELACION_ID,
  } satisfies Errores["ErrorSesion"];
}

export function errorLimiteIntentos(reintentar_en_s: number): Errores["ErrorLimiteIntentos"] {
  return {
    tipo: "LIMITE_INTENTOS",
    mensaje: "Demasiados intentos.",
    reintentar_en_s,
    correlacion_id: CORRELACION_ID,
  } satisfies Errores["ErrorLimiteIntentos"];
}

export function errorValidacion(errores: Errores["ErrorValidacion"]["errores"]): Errores["ErrorValidacion"] {
  return {
    tipo: "VALIDACION",
    mensaje: "La petición no es válida.",
    errores,
    correlacion_id: CORRELACION_ID,
  } satisfies Errores["ErrorValidacion"];
}

export function errorPermiso(motivo: Errores["ErrorPermiso"]["motivo"]): Errores["ErrorPermiso"] {
  return {
    tipo: "PERMISO",
    motivo,
    mensaje: "No tienes permiso para esta operación.",
    roles_requeridos: ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL"],
    correlacion_id: CORRELACION_ID,
  } satisfies Errores["ErrorPermiso"];
}

// Cuerpos de bloqueo (409). Las cifras de `errorRn03ExcedeImporte` son las de CA-8 esc. 1: 45,000 presupuestados,
// 33,000 consumidos (6,000 + 9,000 + 18,000), 12,000 disponibles, 15,000 solicitados y 3,000 de excedente.
const ID_REQUISICION = "3d9a7c10-6b2e-4f41-8a95-0c7d2e5b9f13";
const ID_SOLICITUD = "5e2b8d41-7c3f-4a60-9b18-1d4e6f8a0c27";
const ID_ORDEN = "8f1c4a72-3b5d-4e96-a0c8-2e6b9d1f4a35";
const ID_INSUMO_PLACA = "a4d7e103-9c2b-4f58-b6e1-3a8c5d0f7b49";
const ID_INSUMO_PERFIL = "b9e2f514-0d3c-4a69-8c72-4b9d6e1a8c5a";
const ID_RENGLON_PASTA = "c1f3a625-1e4d-4b7a-9d83-5c0e7f2b9d6b";
const ID_RENGLON_CINTA = "d2a4b736-2f5e-4c8b-ae94-6d1f8a3c0e7c";

type Accion = Errores["Accion"];
type DetalleRn03 = Errores["DetalleExcedePresupuesto"];

export interface CambiosRn03 extends Partial<Omit<Errores["ErrorReglaNegocio"], "detalle">> {
  /** Las claves del detalle que se pisan o se añaden; las que el esquema no conoce viajan igual. */
  detalle?: Partial<DetalleRn03> & Record<string, unknown>;
}

function accionVerSolicitud(): Accion {
  return {
    clave: "VER_SOLICITUD_AUTORIZACION",
    metodo: "GET",
    ruta: `/api/v1/solicitudes-autorizacion/${ID_SOLICITUD}`,
  } satisfies Accion;
}

/** RN-03 por importe: CA-8 esc. 1. */
export function errorRn03ExcedeImporte(cambios: CambiosRn03 = {}): Errores["ErrorReglaNegocio"] {
  const { detalle: cambiosDetalle, ...resto } = cambios;
  const detalle: Errores["ErrorReglaNegocio"]["detalle"] = {
    obra: "AP-058-25 · Union Square F2",
    tipo_partida: "MUROS",
    presupuestado: "45000.0000",
    consumido: "33000.0000",
    consumido_desglose: {
      requisiciones_vivas: "6000.0000",
      comprometido: "9000.0000",
      ejercido: "18000.0000",
      total: "33000.0000",
    },
    disponible: "12000.0000",
    solicitado: "15000.0000",
    excedente: "3000.0000",
    causa: "EXCEDE_IMPORTE",
    requisicion_id: ID_REQUISICION,
    folio: "REQ-1042",
    solicitud_autorizacion_id: ID_SOLICITUD,
    ...cambiosDetalle,
  } satisfies DetalleRn03 & Record<string, unknown>;
  return {
    tipo: "REGLA_NEGOCIO",
    regla: "RN-03",
    mensaje: "El importe solicitado excede lo disponible del tipo de partida MUROS.",
    acciones: [accionVerSolicitud()],
    correlacion_id: CORRELACION_ID,
    ...resto,
    detalle,
  } satisfies Errores["ErrorReglaNegocio"];
}

/** RN-03 por volumen: CA-8 esc. 2. Un insumo está presupuestado en la partida y el otro no. */
export function errorRn03PorVolumen(): Errores["ErrorReglaNegocio"] {
  return {
    tipo: "REGLA_NEGOCIO",
    regla: "RN-03",
    mensaje: "La cantidad solicitada excede la presupuestada de uno o más insumos.",
    detalle: {
      obra: "AP-058-25 · Union Square F2",
      tipo_partida: "MUROS",
      disponible: "0.0000",
      solicitado: "1500.0000",
      excedente: "1500.0000",
      causa: "EXCEDE_VOLUMEN",
      insumos: [
        {
          insumo_id: ID_INSUMO_PLACA,
          insumo: "Placa de yeso de 12.7 mm",
          unidad: "PZA",
          presupuestado_en_partida: true,
          cantidad_presupuestada: "100.0000",
          cantidad_consumida: "90.0000",
          cantidad_disponible: "10.0000",
          cantidad_solicitada: "25.0000",
          excedente: "15.0000",
        },
        {
          insumo_id: ID_INSUMO_PERFIL,
          insumo: "Perfil de acero galvanizado",
          unidad: "ML",
          presupuestado_en_partida: false,
          cantidad_presupuestada: "0.0000",
          cantidad_consumida: "0.0000",
          cantidad_disponible: "0.0000",
          cantidad_solicitada: "12.0000",
          excedente: "12.0000",
        },
      ],
      requisicion_id: ID_REQUISICION,
    } satisfies DetalleRn03,
    acciones: [],
    correlacion_id: CORRELACION_ID,
  } satisfies Errores["ErrorReglaNegocio"];
}

/** RN-07: CA-8 esc. 3. Los renglones no llevan `unidad` (es opcional en el esquema). */
export function errorRn07ExcedeOrdenado(): Errores["ErrorReglaNegocio"] {
  return {
    tipo: "REGLA_NEGOCIO",
    regla: "RN-07",
    mensaje: "La cantidad entrante excede el saldo pendiente de la orden de compra.",
    detalle: {
      orden_compra_id: ID_ORDEN,
      folio_orden: "OC-2026-0118",
      renglones: [
        {
          orden_compra_renglon_id: ID_RENGLON_PASTA,
          insumo: "Pasta para juntas",
          cantidad_ordenada: "40.0000",
          cantidad_recibida: "30.0000",
          saldo_pendiente: "10.0000",
          cantidad_entrante: "15.0000",
          excedente: "5.0000",
        },
        {
          orden_compra_renglon_id: ID_RENGLON_CINTA,
          insumo: "Cinta de papel",
          cantidad_ordenada: "24.0000",
          cantidad_recibida: "18.0000",
          saldo_pendiente: "6.0000",
          cantidad_entrante: "9.0000",
          excedente: "3.0000",
        },
      ],
    } satisfies Errores["DetalleExcedeOrdenado"],
    acciones: [{ clave: "SOLICITAR_AUTORIZACION", metodo: "POST", ruta: "/api/v1/solicitudes-autorizacion" } satisfies Accion],
    correlacion_id: CORRELACION_ID,
  } satisfies Errores["ErrorReglaNegocio"];
}

/** Un 409 que no viola ninguna regla RN: CA-9 esc. 1. */
export function errorConflictoEstado(
  codigo: Errores["ErrorConflictoEstado"]["codigo"],
  cambios: Partial<Errores["ErrorConflictoEstado"]> = {},
): Errores["ErrorConflictoEstado"] {
  return {
    tipo: "CONFLICTO",
    codigo,
    mensaje: "La requisición ya no admite esta operación en su estado actual.",
    detalle: { folio: "REQ-1042", estado: "CANCELADA" },
    acciones: [],
    correlacion_id: CORRELACION_ID,
    ...cambios,
  } satisfies Errores["ErrorConflictoEstado"];
}

/** Venció el bloqueo o el tiempo de ejecución: CA-9 esc. 2. Como llega del servidor; `Retry-After` lo añade `normalizarError`. */
export function errorConcurrencia(cambios: Partial<Errores["ErrorConcurrencia"]> = {}): Errores["ErrorConcurrencia"] {
  return {
    tipo: "CONCURRENCIA",
    codigo: "BLOQUEO_VENCIDO",
    mensaje: "Otra operación tenía tomado el presupuesto y no se guardó nada.",
    detalle: { espera_maxima_ms: 5000 },
    acciones: [
      { clave: "REINTENTAR", metodo: "POST", ruta: `/api/v1/requisiciones/${ID_REQUISICION}/envio` } satisfies Accion,
    ],
    correlacion_id: CORRELACION_ID,
    ...cambios,
  } satisfies Errores["ErrorConcurrencia"];
}
