import { http, HttpResponse } from "msw";
import { describe, expect, test, vi } from "vitest";
import { crearClienteApi } from "@/api/cliente";
import type { components as Provisional } from "@/api/generado/contrato-error.provisional";
import type { components } from "@/api/generado/servidor";
import { errorConflictoEstado, errorValidacion, obra, tokenCsrf } from "@/pruebas/cuerpos";
import { servidorPruebas } from "@/pruebas/servidor";
import { cerrarObra, editarObra, eliminarObra, reactivarObra, suspenderObra } from "./obras.consultas";

// TKT-012b · fila B2 · CA-17 · CA-15 · TC-67. Las cinco mutaciones de la obra hablan el contrato del borrador:
// método, ruta y cuerpo. El servidor se sustituye con MSW, que intercepta la petición real con sus cabeceras.
// Como `crearObra`, devuelven el resultado tal cual (ok/error): la invalidación de `claves.obras` la hace
// quien las llama tras confirmar.

type Esquemas = components["schemas"];
type Accion = Provisional["schemas"]["Accion"];

const ORIGEN = globalThis.location.origin;
const TOKEN = "token-de-prueba";
const OBRA_ID = obra().id;
const RUTA_OBRA = `/api/v1/obras/${OBRA_ID}`;
const MOTIVO = "Falta de acceso al predio por obra vecina";

interface Peticion {
  metodo: string;
  ruta: string;
  csrf: string | null;
  cuerpo: string;
}

function crearCliente() {
  return crearClienteApi({ baseUrl: ORIGEN, alTerminarSesion: vi.fn<() => void>(), alDenegarPermiso: vi.fn<() => void>() });
}

/** El doble del token CSRF y de la ruta de la obra; anota cada petición de la mutación con el cuerpo tal como salió. */
function dobles(
  metodo: "patch" | "delete" | "post",
  ruta: string,
  respuesta: () => Response,
): { recibidas: Peticion[] } {
  const recibidas: Peticion[] = [];
  servidorPruebas.use(
    http.get(`${ORIGEN}/api/v1/sesion/csrf`, () => HttpResponse.json(tokenCsrf(TOKEN))),
    http[metodo](`${ORIGEN}${ruta}`, async ({ request }) => {
      recibidas.push({
        metodo: request.method,
        ruta: new URL(request.url).pathname,
        csrf: request.headers.get("X-CSRF-Token"),
        cuerpo: await request.text(),
      });
      return respuesta();
    }),
  );
  return { recibidas };
}

const obraAceptada = (cambios: Partial<Esquemas["Obra"]> = {}) => () => HttpResponse.json(obra(cambios));

/** Doble que anota cualquier petición, sea cual sea: para probar que no sale ninguna. */
function dobleQueNoDebeRecibirNada(): { recibidas: string[] } {
  const recibidas: string[] = [];
  servidorPruebas.use(
    http.all(`${ORIGEN}/*`, ({ request }) => {
      recibidas.push(`${request.method} ${new URL(request.url).pathname}`);
      return HttpResponse.json(obra());
    }),
  );
  return { recibidas };
}

describe("TKT-012b · editarObra · PATCH /obras/{obra_id} (CA-15, TC-67)", () => {
  test("tkt012b_ca15 · TC-67 · envía PATCH a la ruta de la obra con solo los campos cambiados y el token CSRF", async () => {
    const { recibidas } = dobles("patch", RUTA_OBRA, obraAceptada({ nombre: "Union Square Fase 2" }));

    const resultado = await editarObra(crearCliente(), OBRA_ID, { nombre: "Union Square Fase 2" });

    expect(resultado).toEqual({ ok: true, datos: obra({ nombre: "Union Square Fase 2" }) });
    expect(recibidas).toHaveLength(1);
    expect(recibidas[0]?.metodo).toBe("PATCH");
    expect(recibidas[0]?.ruta).toBe(RUTA_OBRA);
    expect(recibidas[0]?.csrf).toBe(TOKEN);
    // Lo que no se toca no viaja: la clave no está, no basta con que valga undefined.
    expect(JSON.parse(recibidas[0]?.cuerpo ?? "")).toEqual({ nombre: "Union Square Fase 2" });
  });

  test("tkt012b_ca15 · TC-67 · los porcentajes viajan como fracción en cadena, sin pasar por number", async () => {
    const { recibidas } = dobles("patch", RUTA_OBRA, obraAceptada());

    await editarObra(crearCliente(), OBRA_ID, { retencion_destajo_pct: "0.125000", fondo_garantia_pct: "0.050000" });

    expect(JSON.parse(recibidas[0]?.cuerpo ?? "")).toEqual({ retencion_destajo_pct: "0.125000", fondo_garantia_pct: "0.050000" });
    expect(recibidas[0]?.cuerpo).toContain('"0.125000"');
  });

  test("tkt012b_ca15 · TC-67 · umbral_alerta_pct en null viaja como null: así se borra el umbral", async () => {
    const { recibidas } = dobles("patch", RUTA_OBRA, obraAceptada({ umbral_alerta_pct: null }));

    await editarObra(crearCliente(), OBRA_ID, { umbral_alerta_pct: null });

    expect(JSON.parse(recibidas[0]?.cuerpo ?? "")).toEqual({ umbral_alerta_pct: null });
  });

  test("tkt012b_ca15 · TC-67 · un cuerpo sin umbral_alerta_pct no lo menciona: ausente es no tocarlo", async () => {
    const { recibidas } = dobles("patch", RUTA_OBRA, obraAceptada());

    await editarObra(crearCliente(), OBRA_ID, { domicilio: "Av. Universidad 300, Querétaro", iva_acreditable: false });

    const cuerpo: unknown = JSON.parse(recibidas[0]?.cuerpo ?? "");
    expect(cuerpo).toEqual({ domicilio: "Av. Universidad 300, Querétaro", iva_acreditable: false });
    expect(cuerpo).not.toHaveProperty("umbral_alerta_pct");
  });

  test("tkt012b_ca15 · TC-67 · rechazo: un 422 vuelve como error de validación con su campo, sin lanzar", async () => {
    dobles("patch", RUTA_OBRA, () =>
      HttpResponse.json(
        errorValidacion([{ campo: "retencion_destajo_pct", codigo: "FUERA_DE_RANGO", mensaje: "Debe estar entre 0 y 1." }]),
        { status: 422 },
      ),
    );

    const resultado = await editarObra(crearCliente(), OBRA_ID, { retencion_destajo_pct: "1.500000" });

    expect(resultado).toEqual({
      ok: false,
      error: expect.objectContaining({
        tipo: "VALIDACION",
        errores: [{ campo: "retencion_destajo_pct", codigo: "FUERA_DE_RANGO", mensaje: "Debe estar entre 0 y 1." }],
      }),
    });
  });

  test("tkt012b_ca15 · TC-67 · rechazo: el 409 de la obra CERRADA vuelve con su código y el estado, sin lanzar", async () => {
    dobles("patch", RUTA_OBRA, () =>
      HttpResponse.json(
        errorConflictoEstado("ESTADO_NO_PERMITE_OPERACION", {
          mensaje: "La obra AP-058-25 está en CERRADA y no admite esta operación.",
          detalle: { estado: "CERRADA" },
        }),
        { status: 409 },
      ),
    );

    const resultado = await editarObra(crearCliente(), OBRA_ID, { nombre: "Otro nombre" });

    expect(resultado).toEqual({
      ok: false,
      error: expect.objectContaining({
        tipo: "CONFLICTO",
        codigo: "ESTADO_NO_PERMITE_OPERACION",
        detalle: { estado: "CERRADA" },
      }),
    });
  });
});

describe("TKT-012b · eliminarObra · DELETE /obras/{obra_id} (CA-16, TC-67)", () => {
  test("tkt012b_ca16 · TC-67 · envía DELETE a la ruta de la obra, sin cuerpo y con el token CSRF; el 204 es éxito", async () => {
    const { recibidas } = dobles("delete", RUTA_OBRA, () => new HttpResponse(null, { status: 204 }));

    const resultado = await eliminarObra(crearCliente(), OBRA_ID);

    expect(resultado.ok).toBe(true);
    expect(recibidas).toHaveLength(1);
    expect(recibidas[0]?.metodo).toBe("DELETE");
    expect(recibidas[0]?.ruta).toBe(RUTA_OBRA);
    expect(recibidas[0]?.csrf).toBe(TOKEN);
    expect(recibidas[0]?.cuerpo).toBe("");
  });

  test("tkt012b_ca16 · TC-67 · rechazo: el 409 OBRA_CON_HISTORIAL conserva mensaje, detalle y las acciones del contrato", async () => {
    const acciones: Accion[] = [
      { clave: "SUSPENDER_OBRA", metodo: "POST", ruta: `${RUTA_OBRA}/suspension` },
      { clave: "CERRAR_OBRA", metodo: "POST", ruta: `${RUTA_OBRA}/cierre` },
    ];
    dobles("delete", RUTA_OBRA, () =>
      HttpResponse.json(
        errorConflictoEstado("OBRA_CON_HISTORIAL", {
          mensaje: "La obra AP-058-25 tiene historial y no se elimina.",
          detalle: { linea_base_congelada: true },
          acciones,
        }),
        { status: 409 },
      ),
    );

    const resultado = await eliminarObra(crearCliente(), OBRA_ID);

    expect(resultado).toEqual({
      ok: false,
      error: expect.objectContaining({
        tipo: "CONFLICTO",
        codigo: "OBRA_CON_HISTORIAL",
        mensaje: "La obra AP-058-25 tiene historial y no se elimina.",
        detalle: { linea_base_congelada: true },
        acciones,
      }),
    });
  });
});

const TRANSICIONES = [
  ["suspender", suspenderObra, "suspension"],
  ["reactivar", reactivarObra, "reactivacion"],
  ["cerrar", cerrarObra, "cierre"],
] as const;

describe("TKT-012b · suspender, reactivar y cerrar · POST con motivo (CA-17, TC-67)", () => {
  test.each(TRANSICIONES)(
    "tkt012b_ca17 · TC-67 · %s envía POST a la ruta de la transición con el motivo y el token CSRF",
    async (_nombre, transicion, sufijo) => {
      const { recibidas } = dobles("post", `${RUTA_OBRA}/${sufijo}`, obraAceptada({ estado: "SUSPENDIDA" }));

      const resultado = await transicion(crearCliente(), OBRA_ID, MOTIVO);

      expect(resultado).toEqual({ ok: true, datos: obra({ estado: "SUSPENDIDA" }) });
      expect(recibidas).toHaveLength(1);
      expect(recibidas[0]?.metodo).toBe("POST");
      expect(recibidas[0]?.ruta).toBe(`${RUTA_OBRA}/${sufijo}`);
      expect(recibidas[0]?.csrf).toBe(TOKEN);
      expect(JSON.parse(recibidas[0]?.cuerpo ?? "")).toEqual({ motivo: MOTIVO });
    },
  );

  test.each(TRANSICIONES)(
    "tkt012b_ca17 · TC-67 · %s: el 409 ESTADO_NO_PERMITE_OPERACION vuelve con el estado actual, sin lanzar",
    async (_nombre, transicion, sufijo) => {
      dobles("post", `${RUTA_OBRA}/${sufijo}`, () =>
        HttpResponse.json(
          errorConflictoEstado("ESTADO_NO_PERMITE_OPERACION", {
            mensaje: "La obra AP-058-25 está en CERRADA y no admite esta operación.",
            detalle: { estado: "CERRADA", operaciones_admitidas: [] },
          }),
          { status: 409 },
        ),
      );

      const resultado = await transicion(crearCliente(), OBRA_ID, MOTIVO);

      expect(resultado).toEqual({
        ok: false,
        error: expect.objectContaining({
          tipo: "CONFLICTO",
          codigo: "ESTADO_NO_PERMITE_OPERACION",
          detalle: { estado: "CERRADA", operaciones_admitidas: [] },
        }),
      });
    },
  );
});

const MOTIVOS_AUSENTES: ReadonlyArray<readonly [descripcion: string, motivo: string]> = [
  ["vacío", ""],
  ["de solo espacios", "   "],
  ["de solo saltos de línea y tabuladores", "\n\t \n"],
];

const TRANSICION_Y_MOTIVO_AUSENTE = TRANSICIONES.flatMap(([nombre, transicion]) =>
  MOTIVOS_AUSENTES.map(([descripcion, motivo]) => [nombre, descripcion, transicion, motivo] as const),
);

describe("TKT-012b · suspender, reactivar y cerrar · sin motivo no sale (CA-17, TC-67, rechazo)", () => {
  test.each(TRANSICION_Y_MOTIVO_AUSENTE)(
    "tkt012b_ca17 · TC-67 · %s con el motivo %s no envía ninguna petición y devuelve error",
    async (_nombre, _descripcion, transicion, motivo) => {
      const { recibidas } = dobleQueNoDebeRecibirNada();

      const resultado = await transicion(crearCliente(), OBRA_ID, motivo);

      // Ni la mutación ni el token CSRF: la petición ni siquiera se arma.
      expect(recibidas).toEqual([]);
      expect(resultado.ok).toBe(false);
    },
  );
});
