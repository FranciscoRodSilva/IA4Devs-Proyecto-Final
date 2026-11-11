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

/** Un 404 del contrato. El `mensaje` es el que la pantalla pinta tal cual (TKT-018a, D-8). */
export function errorNoEncontrado(recurso: string, mensaje: string): Errores["ErrorNoEncontrado"] {
  return {
    tipo: "NO_ENCONTRADO",
    recurso,
    mensaje,
    correlacion_id: CORRELACION_ID,
  } satisfies Errores["ErrorNoEncontrado"];
}

// Línea base (TKT-018a). Los tipos de partida llevan los nombres de la migración `v0008`, en mayúsculas, y sus
// `id` van en el orden de esa migración. Los importes son cadenas con la escala del servidor y suman la venta:
// 30,000 + 18,500 + 6,600 + 7,400 = 62,500.
const ID_OBRA = "6a0d3f58-1c7b-4e29-9f44-7b2c8e5a1d90";
const ID_LINEA_BASE = "e3b5c847-4a6f-4d9c-bf05-7e2a9b4d1f8d";
const TIPOS_PARTIDA = [
  { id: "00000000-0000-4000-8000-000000000001", clave: "MUROS", nombre: "MUROS" },
  { id: "00000000-0000-4000-8000-000000000002", clave: "PLAFONES_Y_CAJILLOS", nombre: "PLAFONES Y CAJILLOS" },
  { id: "00000000-0000-4000-8000-000000000003", clave: "ENCHAPES", nombre: "ENCHAPES" },
  { id: "00000000-0000-4000-8000-000000000004", clave: "GENERALES", nombre: "GENERALES" },
] as const satisfies readonly Esquemas["TipoPartida"][];
const VENTA_POR_TIPO = ["30000.0000", "18500.0000", "6600.0000", "7400.0000"] as const;

/** Una línea base en BORRADOR, versión 1, de la obra AP-058-25, con venta de 62,500 en sus cuatro tipos de partida. */
export function lineaBase(cambios: Partial<Esquemas["LineaBase"]> = {}): Esquemas["LineaBase"] {
  return {
    id: ID_LINEA_BASE,
    obra_id: ID_OBRA,
    version: 1,
    estado: "BORRADOR",
    importe_venta: "62500.0000",
    congelada_en: null,
    congelada_por: null,
    motivo: null,
    por_tipo_partida: TIPOS_PARTIDA.map((tipo_partida, indice) => ({
      tipo_partida,
      importe_venta: VENTA_POR_TIPO[indice] ?? "0.0000",
    })),
    ...cambios,
  } satisfies Esquemas["LineaBase"];
}

type ClaveTipoPartida = (typeof TIPOS_PARTIDA)[number]["clave"];
const SUGERIDO_POR_TIPO = ["28000.0000", "17500.0000", "6000.0000", "7000.0000"] as const;

/**
 * Una fila del presupuesto de control (TKT-018a, fila B2) de una línea base CONGELADA, sin tope capturado: la venta es la
 * del desglose de `lineaBase()` y el sugerido, uno menor por tipo. Con `importe_tope`, `capturado_por` y `capturado_en`
 * en `cambios` se obtiene una fila ya capturada. Los importes son cadenas con escala 4, como los manda el servidor.
 */
export function filaControl(
  clave: ClaveTipoPartida,
  cambios: Partial<Esquemas["PresupuestoControl"]> = {},
): Esquemas["PresupuestoControl"] {
  const indice = TIPOS_PARTIDA.findIndex((candidato) => candidato.clave === clave);
  const tipo_partida = TIPOS_PARTIDA[indice] ?? TIPOS_PARTIDA[0];
  return {
    tipo_partida,
    importe_venta: VENTA_POR_TIPO[indice] ?? "0.0000",
    importe_sugerido: SUGERIDO_POR_TIPO[indice] ?? "0.0000",
    importe_tope: null,
    capturado_por: null,
    capturado_en: null,
    actualizado_por: null,
    actualizado_en: null,
    motivo_ultimo_cambio: null,
    ...cambios,
  } satisfies Esquemas["PresupuestoControl"];
}

/** Las cuatro filas del presupuesto de control sin ningún tope, en el orden de `tipo_partida.id` de la migración `v0008`. */
export function controlSinTopes(): Esquemas["PresupuestoControl"][] {
  return TIPOS_PARTIDA.map((tipo) => filaControl(tipo.clave));
}

/** La obra AP-058-25 de la línea base de arriba, en PLANEACION y sin línea base vigente (TKT-018a, fila A3). */
export function obra(cambios: Partial<Esquemas["Obra"]> = {}): Esquemas["Obra"] {
  return {
    id: ID_OBRA,
    codigo: "AP-058-25",
    nombre: "Union Square F2",
    domicilio: "Av. Constituyentes 120, Querétaro",
    tipo_contrato: "PRECIO_ALZADO_MAXIMO_GARANTIZADO",
    retencion_destajo_pct: "0.150000",
    fondo_garantia_pct: "0.050000",
    iva_acreditable: true,
    umbral_alerta_pct: null,
    estado: "PLANEACION",
    linea_base_vigente_id: null,
    creado_en: "2026-10-12T15:00:00Z",
    ...cambios,
  } satisfies Esquemas["Obra"];
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

// Rechazos de la línea base (TKT-018a, TC-04). El `detalle` de cada uno es el que arma el backend en
// `presupuesto/aplicacion/congelado.py`, `causas_explosion.py` y `presupuesto_control.py`: los importes son cadenas
// con escala 4, `version_vigente` es un entero y los identificadores internos viajan aunque nunca se pinten.
export const ID_LINEA_BASE_VIGENTE = "8f7e6d5c-4b3a-4291-8f7e-6d5c4b3a2918";

/** RN-01: HDU-001 esc. 19. La obra ya tiene una línea base congelada; el servidor no ofrece ninguna acción. */
export function errorRn01SegundaVigente(): Errores["ErrorReglaNegocio"] {
  return {
    tipo: "REGLA_NEGOCIO",
    regla: "RN-01",
    mensaje:
      "La obra AP-058-25 ya tiene una línea base congelada; para sustituirla hay que crear una versión nueva que marque la anterior como SUPERSEDIDA.",
    detalle: {
      obra: "AP-058-25 · Union Square F2",
      linea_base_vigente_id: ID_LINEA_BASE_VIGENTE,
      version_vigente: 1,
    },
    acciones: [],
    correlacion_id: CORRELACION_ID,
  } satisfies Errores["ErrorReglaNegocio"];
}

/**
 * La explosión del borrador no se puede calcular al congelar (CA-4): dos causas con la forma de `detalle_de_causas`.
 * La primera es por concepto e insumo; la segunda, un sugerido negativo, es por tipo de partida y lleva `concepto`
 * y `clave_insumo` nulos, como los manda el servidor.
 */
export function errorExplosionNoCalculable(): Errores["ErrorConflictoEstado"] {
  return {
    tipo: "CONFLICTO",
    codigo: "ESTADO_NO_PERMITE_OPERACION",
    mensaje: "La explosión de insumos de la importación no se puede calcular.",
    detalle: {
      linea_base_id: ID_LINEA_BASE,
      causas: [
        { concepto: "620040-A", causa: "INSUMO_SIN_COSTO", clave_insumo: "TAB-0127", tipo_partida_id: null },
        { concepto: null, causa: "SUGERIDO_NEGATIVO", clave_insumo: null, tipo_partida_id: TIPOS_PARTIDA[0].id },
      ],
    },
    acciones: [],
    correlacion_id: CORRELACION_ID,
  } satisfies Errores["ErrorConflictoEstado"];
}

/** Tope mayor que la venta sin confirmar: HDU-001 esc. 17. `tipo_partida` y el `mensaje` traen la clave cruda. */
export function errorTopeSuperior(
  clave: (typeof TIPOS_PARTIDA)[number]["clave"],
  venta: string,
  tope: string,
): Errores["ErrorConflictoEstado"] {
  const tipo = TIPOS_PARTIDA.find((candidato) => candidato.clave === clave) ?? TIPOS_PARTIDA[0];
  return {
    tipo: "CONFLICTO",
    codigo: "TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR",
    mensaje: `El tope de ${clave} supera su importe de venta; implicaría vender por debajo del costo tope.`,
    detalle: { tipo_partida: clave, importe_venta: venta, importe_tope: tope },
    acciones: [
      {
        clave: "CONFIRMAR_TOPE_SUPERIOR",
        metodo: "PUT",
        ruta: `/api/v1/lineas-base/${ID_LINEA_BASE}/presupuesto-control/${tipo.id}`,
      } satisfies Accion,
    ],
    correlacion_id: CORRELACION_ID,
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

// Rechazos del congelado que no tenían fábrica (TKT-018a, TC-14 y TC-15). Mensajes, `detalle` y acciones son los de
// `presupuesto/aplicacion/congelado.py` y `traduccion_motor.py`.

/** La línea base ya no está en BORRADOR al congelar (CA-4): `_rechazar_si_no_se_congela`. El servidor no ofrece acciones. */
export function errorLineaBaseEnOtroEstado(
  estado: Exclude<Esquemas["LineaBase"]["estado"], "BORRADOR"> = "CONGELADA",
): Errores["ErrorConflictoEstado"] {
  return {
    tipo: "CONFLICTO",
    codigo: "ESTADO_NO_PERMITE_OPERACION",
    mensaje: `La línea base está en ${estado}; solo se congela una línea base en BORRADOR.`,
    detalle: { linea_base_id: ID_LINEA_BASE, estado },
    acciones: [],
    correlacion_id: CORRELACION_ID,
  } satisfies Errores["ErrorConflictoEstado"];
}

/** Venció el bloqueo de la obra al congelar (CA-4, SQLSTATE 55P03). Como llega del servidor; `Retry-After` va en la cabecera. */
export function errorCongeladoBloqueoVencido(): Errores["ErrorConcurrencia"] {
  return {
    tipo: "CONCURRENCIA",
    codigo: "BLOQUEO_VENCIDO",
    mensaje: "Otra operación está usando la línea base de esta obra en este momento. Vuelve a intentarlo.",
    detalle: { espera_maxima_ms: 5000 },
    acciones: [
      { clave: "REINTENTAR", metodo: "POST", ruta: `/api/v1/lineas-base/${ID_LINEA_BASE}/congelacion` } satisfies Accion,
    ],
    correlacion_id: CORRELACION_ID,
  } satisfies Errores["ErrorConcurrencia"];
}
