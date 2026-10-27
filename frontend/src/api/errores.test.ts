import { describe, expect, test } from "vitest";
import type { components } from "./generado/contrato-error.provisional.ts";
import { normalizarError } from "./errores";

// Los cuerpos cumplen los esquemas del borrador por compilación (`satisfies` contra los tipos generados):
// si el borrador cambia, `npm run typecheck` lo dice. Todas las cifras son cadena.
type Esquemas = components["schemas"];

const correlacion_id = "7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e";
const sinCabeceras = () => new Headers();

const acciones = [
  { clave: "VER_SOLICITUD_AUTORIZACION", metodo: "GET", ruta: "/api/v1/solicitudes-autorizacion/3f1d2c4b-6a7e-4b8c-9d0e-1a2b3c4d5e6f" },
  { clave: "REPROGRAMAR", metodo: "PATCH", ruta: "/api/v1/ordenes-compra/9c8b7a6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d/renglones" },
  { clave: "SOLICITAR_AUTORIZACION", metodo: "POST", ruta: "/api/v1/solicitudes-autorizacion" },
] satisfies Esquemas["Accion"][];

const errorReglaNegocio = {
  tipo: "REGLA_NEGOCIO",
  regla: "RN-03",
  mensaje: "La requisición excede lo presupuestado.",
  detalle: {
    obra: "AP-058-25 · Union Square F2",
    tipo_partida: "MUROS",
    presupuestado: "12345678901234.5650",
    consumido: "12345.6700",
    consumido_desglose: { requisiciones_vivas: "1000.0000", comprometido: "2345.6700", ejercido: "9000.0000", total: "12345.6700" },
    disponible: "500.0000",
    solicitado: "3500.0000",
    excedente: "3000.0000",
    causa: "EXCEDE_IMPORTE",
  },
  acciones,
  correlacion_id,
} satisfies Esquemas["ErrorReglaNegocio"];

const errorConflictoEstado = {
  tipo: "CONFLICTO",
  codigo: "ORDEN_YA_CERRADA",
  mensaje: "La orden de compra ya está cerrada.",
  detalle: { folio_orden: "OC-0042" },
  acciones: [acciones[0]],
  correlacion_id,
} satisfies Esquemas["ErrorConflictoEstado"];

const errorConcurrencia = {
  tipo: "CONCURRENCIA",
  codigo: "BLOQUEO_VENCIDO",
  mensaje: "Otra operación tiene bloqueado el presupuesto. Reintenta.",
  detalle: { espera_maxima_ms: 3000 },
  acciones: [{ clave: "REINTENTAR", metodo: "POST", ruta: "/api/v1/requisiciones" }],
  correlacion_id,
} satisfies Esquemas["ErrorConcurrencia"];

const errorValidacion = {
  tipo: "VALIDACION",
  mensaje: "La petición tiene errores de forma.",
  errores: [
    { campo: "renglones[1].cantidad", codigo: "NO_POSITIVO", mensaje: "La cantidad debe ser mayor que cero." },
    { campo: "fecha_requerida", codigo: "OBLIGATORIO", mensaje: "La fecha es obligatoria.", regla: "RN-03" },
  ],
  correlacion_id,
} satisfies Esquemas["ErrorValidacion"];

const errorPermiso = {
  tipo: "PERMISO",
  motivo: "ROL_INSUFICIENTE",
  mensaje: "Tu rol no permite esta operación.",
  roles_requeridos: ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL"],
  correlacion_id,
} satisfies Esquemas["ErrorPermiso"];

const errorSesion = {
  tipo: "SESION",
  motivo: "SESION_CADUCADA",
  mensaje: "La sesión caducó.",
  correlacion_id,
} satisfies Esquemas["ErrorSesion"];

const errorLimiteIntentos = {
  tipo: "LIMITE_INTENTOS",
  mensaje: "Demasiados intentos. Espera antes de volver a intentar.",
  reintentar_en_s: 120,
  correlacion_id,
} satisfies Esquemas["ErrorLimiteIntentos"];

const errorNoEncontrado = {
  tipo: "NO_ENCONTRADO",
  recurso: "requisicion",
  mensaje: "La requisición no existe.",
  correlacion_id,
} satisfies Esquemas["ErrorNoEncontrado"];

describe("TKT-008 · normalización del error", () => {
  const cabecerasConRetryAfter = () => new Headers({ "Retry-After": "2" });

  // Un caso por tipo del contrato: la respuesta que llega, lo que entrega el cliente y los campos propios del tipo.
  const casosPorTipo = [
    {
      estado: 409, cuerpo: errorReglaNegocio, cabeceras: sinCabeceras(), esperado: errorReglaNegocio,
      propios: {
        regla: "RN-03",
        detalle: { disponible: "500.0000", solicitado: "3500.0000", excedente: "3000.0000", presupuestado: "12345678901234.5650" },
        acciones,
      },
    },
    {
      estado: 409, cuerpo: errorConflictoEstado, cabeceras: sinCabeceras(), esperado: errorConflictoEstado,
      propios: { codigo: "ORDEN_YA_CERRADA", detalle: { folio_orden: "OC-0042" }, acciones: [acciones[0]] },
    },
    {
      estado: 409, cuerpo: errorConcurrencia, cabeceras: cabecerasConRetryAfter(),
      esperado: { ...errorConcurrencia, reintentar_tras_s: 2 },
      propios: { codigo: "BLOQUEO_VENCIDO", detalle: { espera_maxima_ms: 3000 }, reintentar_tras_s: 2 },
    },
    {
      estado: 422, cuerpo: errorValidacion, cabeceras: sinCabeceras(), esperado: errorValidacion,
      propios: { errores: errorValidacion.errores },
    },
    {
      estado: 403, cuerpo: errorPermiso, cabeceras: sinCabeceras(), esperado: errorPermiso,
      propios: { motivo: "ROL_INSUFICIENTE", roles_requeridos: ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL"] },
    },
    { estado: 401, cuerpo: errorSesion, cabeceras: sinCabeceras(), esperado: errorSesion, propios: { motivo: "SESION_CADUCADA" } },
    {
      estado: 429, cuerpo: errorLimiteIntentos, cabeceras: sinCabeceras(), esperado: errorLimiteIntentos,
      propios: { reintentar_en_s: 120 },
    },
    {
      estado: 404, cuerpo: errorNoEncontrado, cabeceras: sinCabeceras(), esperado: errorNoEncontrado,
      propios: { recurso: "requisicion" },
    },
  ];

  test.each(casosPorTipo)("tkt008_ca04_esc01 · $cuerpo.tipo con sus campos", ({ estado, cuerpo, cabeceras, esperado, propios }) => {
    const resultado = normalizarError(estado, cuerpo, cabeceras);

    // El resultado conserva todo tal cual llegó, y los campos propios de cada tipo se dicen por su nombre (CA-4 esc. 1).
    expect(resultado.tipo).toBe(cuerpo.tipo);
    expect(resultado).toEqual(esperado);
    expect(resultado).toMatchObject(propios);
  });

  test("tkt008_ca04_esc01 · CONCURRENCIA sin Retry-After dice la espera como desconocida, no como cero", () => {
    expect(normalizarError(409, errorConcurrencia, sinCabeceras())).toMatchObject({ reintentar_tras_s: null });
  });

  test("tkt008_ca04_esc02 · fuera del contrato", () => {
    const sinDatos = { tipo: "GENERICO", mensaje: null, correlacion_id: null };

    // 500 con mensaje y correlación, sin tipo: conserva ambos y el estado.
    expect(normalizarError(500, { mensaje: "Error interno.", correlacion_id }, sinCabeceras())).toEqual({
      tipo: "GENERICO",
      estado: 500,
      mensaje: "Error interno.",
      correlacion_id,
    });

    // Cuerpo que no es JSON (llega como texto) y cuerpos sin forma de contrato.
    expect(normalizarError(502, "<html>", sinCabeceras())).toEqual({ ...sinDatos, estado: 502 });
    expect(normalizarError(500, { detail: "x" }, sinCabeceras())).toEqual({ ...sinDatos, estado: 500 });
    expect(normalizarError(500, null, sinCabeceras())).toEqual({ ...sinDatos, estado: 500 });
    expect(normalizarError(500, undefined, sinCabeceras())).toEqual({ ...sinDatos, estado: 500 });
    expect(normalizarError(500, [errorSesion], sinCabeceras())).toEqual({ ...sinDatos, estado: 500 });
    expect(normalizarError(500, 42, sinCabeceras())).toEqual({ ...sinDatos, estado: 500 });

    // El cuerpo por omisión de FastAPI (HTTPValidationError) no es del contrato: nunca VALIDACION (hallazgo M-1).
    const httpValidationError = { detail: [{ loc: ["body", "email"], msg: "x", type: "value_error" }] };
    const validacionFastApi = normalizarError(422, httpValidationError, sinCabeceras());
    expect(validacionFastApi).toEqual({ ...sinDatos, estado: 422 });
    expect(validacionFastApi.tipo).not.toBe("VALIDACION");

    // Un tipo del contrato con el código de estado equivocado no se acepta: no inventa el tipo.
    expect(normalizarError(500, { tipo: "SESION", mensaje: "x" }, sinCabeceras())).toEqual({
      tipo: "GENERICO",
      estado: 500,
      mensaje: "x",
      correlacion_id: null,
    });
    expect(normalizarError(422, errorReglaNegocio, sinCabeceras()).tipo).toBe("GENERICO");
    expect(normalizarError(409, errorSesion, sinCabeceras()).tipo).toBe("GENERICO");

    // Un tipo válido sin `mensaje` de cadena tampoco es del contrato.
    expect(normalizarError(401, { tipo: "SESION", motivo: "SIN_SESION", correlacion_id }, sinCabeceras()).tipo).toBe("GENERICO");

    // `mensaje` y `correlacion_id` solo si son cadenas.
    expect(normalizarError(500, { mensaje: 7, correlacion_id: { id: 1 } }, sinCabeceras())).toEqual({ ...sinDatos, estado: 500 });
  });

  test("tkt008_ca04_esc02 · tipo desconocido", () => {
    const resultado = normalizarError(409, { tipo: "OTRO", mensaje: "No es del contrato.", correlacion_id }, sinCabeceras());

    expect(resultado.tipo).toBe("GENERICO");
    expect(resultado).toEqual({ tipo: "GENERICO", estado: 409, mensaje: "No es del contrato.", correlacion_id });
  });

  test("tkt008_ca04_esc04 · acciones intactas", () => {
    const resultado = normalizarError(409, errorReglaNegocio, sinCabeceras());
    const recibidas = "acciones" in resultado ? resultado.acciones : null;

    expect(recibidas).toStrictEqual(acciones);
    expect(recibidas?.map((accion) => accion.clave)).toEqual(["VER_SOLICITUD_AUTORIZACION", "REPROGRAMAR", "SOLICITAR_AUTORIZACION"]);
    expect(recibidas?.map((accion) => accion.metodo)).toEqual(["GET", "PATCH", "POST"]);
    expect(recibidas?.map((accion) => accion.ruta)).toEqual([
      "/api/v1/solicitudes-autorizacion/3f1d2c4b-6a7e-4b8c-9d0e-1a2b3c4d5e6f",
      "/api/v1/ordenes-compra/9c8b7a6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d/renglones",
      "/api/v1/solicitudes-autorizacion",
    ]);
  });
});
