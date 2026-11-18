import { QueryClient } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { describe, expect, test, vi } from "vitest";
import { crearClienteApi, FalloApi } from "@/api/cliente";
import type { components as Provisional } from "@/api/generado/contrato-error.provisional";
import type { components } from "@/api/generado/servidor";
import {
  errorConcurrencia,
  errorConflictoEstado,
  errorNoEncontrado,
  errorPermiso,
  errorValidacion,
  tokenCsrf,
} from "@/pruebas/cuerpos";
import { servidorPruebas } from "@/pruebas/servidor";
import {
  actualizarProveedor,
  claves,
  crearProveedor,
  darDeBajaProveedor,
  desactivarProveedor,
  proveedoresOptions,
} from "./proveedores.consultas";

// TKT-032a · fila F4 · TC-F07 y TC-F08 (parte de las consultas) · CA-1 · CA-R4. La lista pide siempre el estado
// (por omisión ACTIVO, D-5) y la búsqueda solo si no está vacía; las cuatro mutaciones hablan el contrato del
// borrador: método, ruta y cuerpo exactos, con el token CSRF. El servidor se sustituye con MSW, que intercepta la
// petición real. Las mutaciones devuelven el resultado tal cual (ok/error) y nunca lanzan: la invalidación de
// `claves.proveedores` la hace quien las llama tras confirmar (patrón de obras), y aquí se comprueba que la clave
// de la lista cuelga de ese prefijo para que una sola invalidación la alcance.

type Esquemas = components["schemas"];
type Proveedor = Esquemas["Proveedor"];
type Accion = Provisional["schemas"]["Accion"];

const ORIGEN = globalThis.location.origin;
const TOKEN = "token-de-prueba";
const RUTA_LISTA = "/api/v1/proveedores";
const PROVEEDOR_ID = "9c2e5a41-7b3d-4f68-a1c9-3d5e7f9b1a24";
const RUTA_PROVEEDOR = `${RUTA_LISTA}/${PROVEEDOR_ID}`;
const MOTIVO = "Dejó de surtir en tiempo";

function proveedor(cambios: Partial<Proveedor> = {}): Proveedor {
  return {
    id: PROVEEDOR_ID,
    nombre: "CoPanel",
    rfc: "XAXX010101000",
    tope_consignacion: "300000.0000",
    dia_corte: 4,
    dia_pago: 6,
    estado: "ACTIVO",
    creado_en: "2026-11-17T15:00:00Z",
    ...cambios,
  } satisfies Proveedor;
}

function lista(elementos: Proveedor[] = [proveedor()], total = elementos.length): Esquemas["ListaProveedores"] {
  return { elementos, paginacion: { pagina: 1, tamano_pagina: 50, total } } satisfies Esquemas["ListaProveedores"];
}

function crearCliente() {
  return crearClienteApi({ baseUrl: ORIGEN, alTerminarSesion: vi.fn<() => void>(), alDenegarPermiso: vi.fn<() => void>() });
}

function crearQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { retry: false, gcTime: Infinity } } });
}

interface PeticionDeLista {
  url: URL;
  csrf: string | null;
}

/** El doble de `GET /proveedores`: anota la URL con su cadena de consulta tal como salió. */
function dobleDeLista(respuesta: () => Response = () => HttpResponse.json(lista())): { recibidas: PeticionDeLista[] } {
  const recibidas: PeticionDeLista[] = [];
  servidorPruebas.use(
    http.get(`${ORIGEN}${RUTA_LISTA}`, ({ request }) => {
      recibidas.push({ url: new URL(request.url), csrf: request.headers.get("X-CSRF-Token") });
      return respuesta();
    }),
  );
  return { recibidas };
}

async function pedirLista(parametros: Parameters<typeof proveedoresOptions>[1]): Promise<URL> {
  const { recibidas } = dobleDeLista();
  await crearQueryClient().fetchQuery(proveedoresOptions(crearCliente(), parametros));
  expect(recibidas).toHaveLength(1);
  const [peticion] = recibidas;
  if (peticion === undefined) throw new Error("la lista no pidió nada");
  return peticion.url;
}

describe("TKT-032a · proveedoresOptions · GET /proveedores (TC-F07, CA-1)", () => {
  test("hdu004_esc02 · TC-F07 · sin parámetros pide solo los ACTIVO, la página 1 y 50 por página, sin búsqueda", async () => {
    const url = await pedirLista({});

    expect(url.searchParams.getAll("estado")).toEqual(["ACTIVO"]);
    expect(url.searchParams.has("q")).toBe(false);
    expect(url.searchParams.get("pagina")).toBe("1");
    expect(url.searchParams.get("tamano_pagina")).toBe("50");
  });

  test("hdu004_esc02 · TC-F07 · el filtro por omisión envía estado=ACTIVO siempre, y una búsqueda vacía no envía q", async () => {
    const url = await pedirLista({ estados: ["ACTIVO"], q: "", pagina: 1 });

    expect(url.searchParams.getAll("estado")).toEqual(["ACTIVO"]);
    expect(url.searchParams.has("q")).toBe(false);
    expect(url.search).toContain("estado=ACTIVO");
  });

  test("hdu004_esc02 · TC-F07 · una búsqueda con texto envía q, y la página pedida viaja con el tamaño de 50", async () => {
    const url = await pedirLista({ estados: ["ACTIVO"], q: "CoPanel", pagina: 2 });

    expect(url.searchParams.get("q")).toBe("CoPanel");
    expect(url.searchParams.get("pagina")).toBe("2");
    expect(url.searchParams.get("tamano_pagina")).toBe("50");
    expect(url.searchParams.getAll("estado")).toEqual(["ACTIVO"]);
  });

  test("hdu004_esc02 · TC-F07 · la búsqueda con espacios y acentos llega íntegra", async () => {
    const url = await pedirLista({ estados: ["ACTIVO"], q: "Aceros del Bajío", pagina: 1 });

    expect(url.searchParams.get("q")).toBe("Aceros del Bajío");
  });

  test("hdu004_esc12 · TC-F07 · «Todos» repite el parámetro con los tres estados, en ese orden", async () => {
    const url = await pedirLista({ estados: ["ACTIVO", "DESACTIVADO", "BAJA"], q: "", pagina: 1 });

    expect(url.searchParams.getAll("estado")).toEqual(["ACTIVO", "DESACTIVADO", "BAJA"]);
    expect(url.search).toContain("estado=ACTIVO&estado=DESACTIVADO&estado=BAJA");
  });

  test.each([
    [["DESACTIVADO"] as const],
    [["BAJA"] as const],
  ])("hdu004_esc12 · TC-F07 · el filtro %j envía solo ese estado y no el ACTIVO por omisión", async (estados) => {
    const url = await pedirLista({ estados, q: "", pagina: 1 });

    expect(url.searchParams.getAll("estado")).toEqual([...estados]);
  });

  test("hdu004_esc02 · TC-F07 · la lista devuelve las filas y la paginación tal como las mandó el servidor", async () => {
    const servida = lista([proveedor(), proveedor({ id: "b1d3f5a7-2c4e-4a68-9b0d-1e3f5a7c9b2d", nombre: "Aceros del Bajío" })], 120);
    dobleDeLista(() => HttpResponse.json(servida));

    const resultado = await crearQueryClient().fetchQuery(proveedoresOptions(crearCliente(), { pagina: 1 }));

    expect(resultado).toEqual(servida);
    expect(resultado.paginacion.total).toBe(120);
  });

  test("hdu004_esc02 · TC-F07 · el tope de la lista llega como cadena, sin perder exactitud", async () => {
    dobleDeLista(() => HttpResponse.json(lista([proveedor({ tope_consignacion: "99999999999999.9999" })])));

    const resultado = await crearQueryClient().fetchQuery(proveedoresOptions(crearCliente(), {}));

    expect(resultado.elementos[0]?.tope_consignacion).toBe("99999999999999.9999");
  });

  test("tkt032a_lista · TC-F07 · rechazo: un 422 de la búsqueda hace fallar la consulta con el error del contrato, sin perderlo", async () => {
    dobleDeLista(() =>
      HttpResponse.json(errorValidacion([{ campo: "q", codigo: "VALOR_NO_PERMITIDO", mensaje: "La búsqueda no es válida." }]), {
        status: 422,
      }),
    );

    const fallo = await crearQueryClient()
      .fetchQuery(proveedoresOptions(crearCliente(), { q: "a\u0000b" }))
      .then(
        () => null,
        (causa: unknown) => causa,
      );

    expect(fallo).toBeInstanceOf(FalloApi);
    expect(fallo instanceof FalloApi ? fallo.error : null).toMatchObject({ tipo: "VALIDACION" });
  });

  test("tkt032a_lista · TC-F07 · rechazo: un 500 con cuerpo que no es JSON hace fallar la consulta como error genérico", async () => {
    dobleDeLista(() => new HttpResponse("<html>Bad gateway</html>", { status: 500, headers: { "Content-Type": "text/html" } }));

    const fallo = await crearQueryClient()
      .fetchQuery(proveedoresOptions(crearCliente(), {}))
      .then(
        () => null,
        (causa: unknown) => causa,
      );

    expect(fallo).toBeInstanceOf(FalloApi);
    expect(fallo instanceof FalloApi ? fallo.error : null).toMatchObject({ tipo: "GENERICO", estado: 500 });
  });
});

describe("TKT-032a · proveedoresOptions · la clave de caché (TC-F07, CA-1)", () => {
  const api = crearCliente();

  test("tkt032a_lista · TC-F07 · la clave cuelga del prefijo de los proveedores y lleva estados, búsqueda, página y tamaño", () => {
    const { queryKey } = proveedoresOptions(api, { estados: ["ACTIVO", "BAJA"], q: "a", pagina: 3 });

    expect(queryKey).toEqual([...claves.proveedores, "lista", { estados: ["ACTIVO", "BAJA"], q: "a", pagina: 3, tamano_pagina: 50 }]);
  });

  test("tkt032a_lista · TC-F07 · cada dependencia de la consulta cambia la clave: otra página, otra búsqueda u otro estado no sirven datos ajenos", () => {
    const base = proveedoresOptions(api, { estados: ["ACTIVO"], q: "", pagina: 1 }).queryKey;
    const otraPagina = proveedoresOptions(api, { estados: ["ACTIVO"], q: "", pagina: 2 }).queryKey;
    const otraBusqueda = proveedoresOptions(api, { estados: ["ACTIVO"], q: "Co", pagina: 1 }).queryKey;
    const otroEstado = proveedoresOptions(api, { estados: ["DESACTIVADO"], q: "", pagina: 1 }).queryKey;
    const todos = proveedoresOptions(api, { estados: ["ACTIVO", "DESACTIVADO", "BAJA"], q: "", pagina: 1 }).queryKey;
    const igualALaBase = proveedoresOptions(api, { estados: ["ACTIVO"], q: "", pagina: 1 }).queryKey;

    const hashes = [base, otraPagina, otraBusqueda, otroEstado, todos].map((clave) => JSON.stringify(clave));
    expect(new Set(hashes).size).toBe(hashes.length);
    // Y los mismos parámetros dan la misma clave: es lo que hace que la caché se reutilice.
    expect(igualALaBase).toEqual(base);
  });

  test("tkt032a_lista · TC-F07 · invalidar claves.proveedores alcanza cualquier página de la lista y deja en paz a las demás cachés", async () => {
    dobleDeLista();
    const queryClient = crearQueryClient();
    const cliente = crearCliente();
    const primera = proveedoresOptions(cliente, { estados: ["ACTIVO"], q: "", pagina: 1 });
    const segunda = proveedoresOptions(cliente, { estados: ["BAJA"], q: "Co", pagina: 2 });
    await queryClient.fetchQuery(primera);
    await queryClient.fetchQuery(segunda);
    queryClient.setQueryData(["obras", "lista"], { sin: "tocar" });
    expect(queryClient.getQueryState(primera.queryKey)?.isInvalidated).toBe(false);

    await queryClient.invalidateQueries({ queryKey: claves.proveedores, refetchType: "none" });

    expect(queryClient.getQueryState(primera.queryKey)?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(segunda.queryKey)?.isInvalidated).toBe(true);
    expect(queryClient.getQueryState(["obras", "lista"])?.isInvalidated).toBe(false);
  });
});

interface Peticion {
  metodo: string;
  ruta: string;
  csrf: string | null;
  cuerpo: string;
}

/** El doble del token CSRF y de la ruta de la mutación; anota cada petición con el cuerpo tal como salió. */
function dobles(metodo: "post" | "patch", ruta: string, respuesta: () => Response): { recibidas: Peticion[] } {
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

const aceptada = (cambios: Partial<Proveedor> = {}, estado = 200) => () => HttpResponse.json(proveedor(cambios), { status: estado });

describe("TKT-032a · crearProveedor · POST /proveedores (TC-F08, CA-2, CA-R4)", () => {
  test("hdu004_esc02 · TC-F08 · envía POST a la ruta de la lista con el cuerpo exacto, los días como enteros y el token CSRF", async () => {
    const { recibidas } = dobles("post", RUTA_LISTA, aceptada({}, 201));

    const resultado = await crearProveedor(crearCliente(), {
      nombre: "CoPanel",
      rfc: "XAXX010101000",
      tope_consignacion: null,
      dia_corte: 4,
      dia_pago: 6,
    });

    expect(resultado).toEqual({ ok: true, datos: proveedor() });
    expect(recibidas).toHaveLength(1);
    expect(recibidas[0]?.metodo).toBe("POST");
    expect(recibidas[0]?.ruta).toBe(RUTA_LISTA);
    expect(recibidas[0]?.csrf).toBe(TOKEN);
    expect(JSON.parse(recibidas[0]?.cuerpo ?? "")).toStrictEqual({
      nombre: "CoPanel",
      rfc: "XAXX010101000",
      tope_consignacion: null,
      dia_corte: 4,
      dia_pago: 6,
    });
  });

  test("hdu004_esc02 · TC-F08 · CA-R4 · el tope máximo viaja idéntico y como cadena: nunca como número", async () => {
    const { recibidas } = dobles("post", RUTA_LISTA, aceptada({ tope_consignacion: "99999999999999.9999" }, 201));

    await crearProveedor(crearCliente(), {
      nombre: "CoPanel",
      rfc: "XAXX010101000",
      tope_consignacion: "99999999999999.9999",
      dia_corte: 2,
      dia_pago: 7,
    });

    const cuerpo: unknown = JSON.parse(recibidas[0]?.cuerpo ?? "");
    expect(cuerpo).toMatchObject({ tope_consignacion: "99999999999999.9999", dia_corte: 2, dia_pago: 7 });
    // Si el tope pasara por number, el cuerpo diría 100000000000000 y typeof sería «number».
    expect(typeof (cuerpo as Record<string, unknown>).tope_consignacion).toBe("string");
    expect(recibidas[0]?.cuerpo).toContain('"tope_consignacion":"99999999999999.9999"');
  });

  test("hdu004_esc03 · TC-F08 · rechazo: el 409 RFC_DUPLICADO vuelve con su código, el proveedor existente y sin acciones, sin lanzar", async () => {
    dobles("post", RUTA_LISTA, () =>
      HttpResponse.json(
        errorConflictoEstado("RFC_DUPLICADO", {
          mensaje: "Ya existe un proveedor con el RFC XAXX010101000.",
          detalle: { proveedor_existente_id: PROVEEDOR_ID, proveedor_existente: "CoPanel · XAXX010101000" },
          acciones: [],
        }),
        { status: 409 },
      ),
    );

    const resultado = await crearProveedor(crearCliente(), {
      nombre: "Otro nombre",
      rfc: "XAXX010101000",
      dia_corte: 4,
      dia_pago: 6,
    });

    expect(resultado).toEqual({
      ok: false,
      error: expect.objectContaining({
        tipo: "CONFLICTO",
        codigo: "RFC_DUPLICADO",
        mensaje: "Ya existe un proveedor con el RFC XAXX010101000.",
        detalle: { proveedor_existente_id: PROVEEDOR_ID, proveedor_existente: "CoPanel · XAXX010101000" },
        acciones: [],
      }),
    });
  });

  test.each(["nombre", "rfc", "tope_consignacion", "dia_corte", "dia_pago"])(
    "tkt032a_alta · TC-F08 · rechazo: un 422 en %s vuelve como error de validación con su campo, sin lanzar",
    async (campo) => {
      dobles("post", RUTA_LISTA, () =>
        HttpResponse.json(errorValidacion([{ campo, codigo: "FORMATO", mensaje: "No es válido." }]), { status: 422 }),
      );

      const resultado = await crearProveedor(crearCliente(), { nombre: "CoPanel", rfc: "XAXX010101000", dia_corte: 4, dia_pago: 6 });

      expect(resultado).toEqual({
        ok: false,
        error: expect.objectContaining({
          tipo: "VALIDACION",
          errores: [{ campo, codigo: "FORMATO", mensaje: "No es válido." }],
        }),
      });
    },
  );

  test("hdu004_esc02 · TC-F08 · rechazo: el 403 vuelve como error de permiso con el mensaje del servidor, sin lanzar", async () => {
    dobles("post", RUTA_LISTA, () =>
      HttpResponse.json({ ...errorPermiso("ROL_INSUFICIENTE"), mensaje: "Tu rol no permite esta operación." }, { status: 403 }),
    );

    const resultado = await crearProveedor(crearCliente(), { nombre: "CoPanel", rfc: "XAXX010101000", dia_corte: 4, dia_pago: 6 });

    expect(resultado).toEqual({
      ok: false,
      error: expect.objectContaining({ tipo: "PERMISO", motivo: "ROL_INSUFICIENTE", mensaje: "Tu rol no permite esta operación." }),
    });
  });

  test("hdu004_esc02 · TC-F08 · rechazo: sin conexión vuelve como error de red, sin lanzar", async () => {
    dobles("post", RUTA_LISTA, () => HttpResponse.error());

    const resultado = await crearProveedor(crearCliente(), { nombre: "CoPanel", rfc: "XAXX010101000", dia_corte: 4, dia_pago: 6 });

    expect(resultado).toEqual({ ok: false, error: { tipo: "RED" } });
  });
});

describe("TKT-032a · actualizarProveedor · PATCH /proveedores/{proveedor_id} (CA-5, CA-R4)", () => {
  test("tkt032a_edicion · envía PATCH a la ruta del proveedor con solo los campos cambiados y el token CSRF", async () => {
    const { recibidas } = dobles("patch", RUTA_PROVEEDOR, aceptada({ nombre: "CoPanel S.A.", dia_pago: 5 }));

    const resultado = await actualizarProveedor(crearCliente(), PROVEEDOR_ID, { nombre: "CoPanel S.A.", dia_pago: 5 });

    expect(resultado).toEqual({ ok: true, datos: proveedor({ nombre: "CoPanel S.A.", dia_pago: 5 }) });
    expect(recibidas).toHaveLength(1);
    expect(recibidas[0]?.metodo).toBe("PATCH");
    expect(recibidas[0]?.ruta).toBe(RUTA_PROVEEDOR);
    expect(recibidas[0]?.csrf).toBe(TOKEN);
    // Lo que no se toca no viaja: la clave no está, no basta con que valga undefined.
    expect(JSON.parse(recibidas[0]?.cuerpo ?? "")).toStrictEqual({ nombre: "CoPanel S.A.", dia_pago: 5 });
  });

  test("tkt032a_edicion · tope_consignacion en null viaja como null: así se borra el tope", async () => {
    const { recibidas } = dobles("patch", RUTA_PROVEEDOR, aceptada({ tope_consignacion: null }));

    await actualizarProveedor(crearCliente(), PROVEEDOR_ID, { tope_consignacion: null });

    expect(JSON.parse(recibidas[0]?.cuerpo ?? "")).toStrictEqual({ tope_consignacion: null });
  });

  test("tkt032a_edicion · CA-R4 · el tope viaja como cadena exacta, sin pasar por number", async () => {
    const { recibidas } = dobles("patch", RUTA_PROVEEDOR, aceptada({ tope_consignacion: "99999999999999.9999" }));

    await actualizarProveedor(crearCliente(), PROVEEDOR_ID, { tope_consignacion: "99999999999999.9999" });

    expect(recibidas[0]?.cuerpo).toContain('"tope_consignacion":"99999999999999.9999"');
    expect(typeof (JSON.parse(recibidas[0]?.cuerpo ?? "") as Record<string, unknown>).tope_consignacion).toBe("string");
  });

  test("tkt032a_edicion · rechazo: un 422 vuelve como error de validación con su campo, sin lanzar", async () => {
    dobles("patch", RUTA_PROVEEDOR, () =>
      HttpResponse.json(errorValidacion([{ campo: "nombre", codigo: "FORMATO", mensaje: "Escribe el nombre." }]), { status: 422 }),
    );

    const resultado = await actualizarProveedor(crearCliente(), PROVEEDOR_ID, { nombre: "" });

    expect(resultado).toEqual({
      ok: false,
      error: expect.objectContaining({ tipo: "VALIDACION", errores: [{ campo: "nombre", codigo: "FORMATO", mensaje: "Escribe el nombre." }] }),
    });
  });

  test("tkt032a_edicion · rechazo: el 404 del proveedor que ya no existe vuelve como no encontrado, sin lanzar", async () => {
    dobles("patch", RUTA_PROVEEDOR, () =>
      HttpResponse.json(errorNoEncontrado("proveedor", "El proveedor no existe."), { status: 404 }),
    );

    const resultado = await actualizarProveedor(crearCliente(), PROVEEDOR_ID, { nombre: "CoPanel S.A." });

    expect(resultado).toEqual({
      ok: false,
      error: expect.objectContaining({ tipo: "NO_ENCONTRADO", recurso: "proveedor", mensaje: "El proveedor no existe." }),
    });
  });
});

const TRANSICIONES = [
  ["hdu004_esc12", "desactivar", desactivarProveedor, "desactivacion", "DESACTIVADO"],
  ["hdu004_esc13", "dar de baja", darDeBajaProveedor, "baja", "BAJA"],
] as const;

describe("TKT-032a · desactivarProveedor y darDeBajaProveedor · POST con motivo (CA-6, CA-7)", () => {
  test.each(TRANSICIONES)(
    "%s · %s envía POST a la ruta de la operación con solo el motivo y el token CSRF",
    async (_escenario, _nombre, operacion, sufijo, estadoFinal) => {
      const { recibidas } = dobles("post", `${RUTA_PROVEEDOR}/${sufijo}`, aceptada({ estado: estadoFinal }));

      const resultado = await operacion(crearCliente(), PROVEEDOR_ID, MOTIVO);

      expect(resultado).toEqual({ ok: true, datos: proveedor({ estado: estadoFinal }) });
      expect(recibidas).toHaveLength(1);
      expect(recibidas[0]?.metodo).toBe("POST");
      expect(recibidas[0]?.ruta).toBe(`${RUTA_PROVEEDOR}/${sufijo}`);
      expect(recibidas[0]?.csrf).toBe(TOKEN);
      expect(JSON.parse(recibidas[0]?.cuerpo ?? "")).toStrictEqual({ motivo: MOTIVO });
    },
  );

  test.each(TRANSICIONES)(
    "%s · %s: el 409 ESTADO_NO_PERMITE_OPERACION vuelve con el estado actual, sin lanzar",
    async (_escenario, _nombre, operacion, sufijo) => {
      dobles("post", `${RUTA_PROVEEDOR}/${sufijo}`, () =>
        HttpResponse.json(
          errorConflictoEstado("ESTADO_NO_PERMITE_OPERACION", {
            mensaje: "El proveedor CoPanel está en BAJA y no admite esta operación.",
            detalle: { estado_actual: "BAJA" },
            acciones: [],
          }),
          { status: 409 },
        ),
      );

      const resultado = await operacion(crearCliente(), PROVEEDOR_ID, MOTIVO);

      expect(resultado).toEqual({
        ok: false,
        error: expect.objectContaining({
          tipo: "CONFLICTO",
          codigo: "ESTADO_NO_PERMITE_OPERACION",
          detalle: { estado_actual: "BAJA" },
          acciones: [],
        }),
      });
    },
  );

  test.each(TRANSICIONES)(
    "%s · %s: el 404 del proveedor que ya no existe vuelve como no encontrado, sin lanzar",
    async (_escenario, _nombre, operacion, sufijo) => {
      dobles("post", `${RUTA_PROVEEDOR}/${sufijo}`, () =>
        HttpResponse.json(errorNoEncontrado("proveedor", "El proveedor no existe."), { status: 404 }),
      );

      const resultado = await operacion(crearCliente(), PROVEEDOR_ID, MOTIVO);

      expect(resultado).toEqual({ ok: false, error: expect.objectContaining({ tipo: "NO_ENCONTRADO", recurso: "proveedor" }) });
    },
  );

  test.each(TRANSICIONES)(
    "%s · %s: el 403 vuelve con el mensaje del servidor, sin lanzar",
    async (_escenario, _nombre, operacion, sufijo) => {
      dobles("post", `${RUTA_PROVEEDOR}/${sufijo}`, () =>
        HttpResponse.json({ ...errorPermiso("ROL_INSUFICIENTE"), mensaje: "Tu rol no permite esta operación." }, { status: 403 }),
      );

      const resultado = await operacion(crearCliente(), PROVEEDOR_ID, MOTIVO);

      expect(resultado).toEqual({
        ok: false,
        error: expect.objectContaining({ tipo: "PERMISO", mensaje: "Tu rol no permite esta operación." }),
      });
    },
  );

  test.each(TRANSICIONES)(
    "%s · %s: el 409 CONCURRENCIA vuelve con su espera y su acción de reintentar, sin lanzar",
    async (_escenario, _nombre, operacion, sufijo) => {
      servidorPruebas.use(
        http.get(`${ORIGEN}/api/v1/sesion/csrf`, () => HttpResponse.json(tokenCsrf(TOKEN))),
        http.post(`${ORIGEN}${RUTA_PROVEEDOR}/${sufijo}`, () =>
          HttpResponse.json(errorConcurrencia(), { status: 409, headers: { "Retry-After": "5" } }),
        ),
      );

      const resultado = await operacion(crearCliente(), PROVEEDOR_ID, MOTIVO);

      expect(resultado).toEqual({
        ok: false,
        error: expect.objectContaining({ tipo: "CONCURRENCIA", codigo: "BLOQUEO_VENCIDO", reintentar_tras_s: 5 }),
      });
    },
  );
});

describe("TKT-032a · darDeBajaProveedor · el bloqueo por órdenes pendientes (CA-8, HDU-004 esc. 12)", () => {
  const ORDENES = [
    { id: "5c4b3a29-1807-4f6e-9d5c-4b3a29180716", folio: "OC-AP05825-0017", estado: "PARCIAL" },
    { id: "6d5c4b3a-2918-4a7f-8e6d-5c4b3a291827", folio: "OC-AP05825-0021", estado: "ABIERTA" },
  ];
  const DESACTIVAR: Accion = { clave: "DESACTIVAR_PROVEEDOR", metodo: "POST", ruta: `${RUTA_PROVEEDOR}/desactivacion` };

  test("hdu004_esc12 · el 409 PROVEEDOR_CON_ORDENES_ABIERTAS de un proveedor ACTIVO conserva mensaje, órdenes y la acción del contrato", async () => {
    const mensaje = "CoPanel tiene 2 órdenes pendientes de recibir; se puede desactivar para órdenes nuevas conservando las existentes.";
    dobles("post", `${RUTA_PROVEEDOR}/baja`, () =>
      HttpResponse.json(
        errorConflictoEstado("PROVEEDOR_CON_ORDENES_ABIERTAS", { mensaje, detalle: { ordenes: ORDENES }, acciones: [DESACTIVAR] }),
        { status: 409 },
      ),
    );

    const resultado = await darDeBajaProveedor(crearCliente(), PROVEEDOR_ID, MOTIVO);

    expect(resultado).toEqual({
      ok: false,
      error: expect.objectContaining({
        tipo: "CONFLICTO",
        codigo: "PROVEEDOR_CON_ORDENES_ABIERTAS",
        mensaje,
        detalle: { ordenes: ORDENES },
        acciones: [DESACTIVAR],
      }),
    });
  });

  test("hdu004_esc12 · rechazo: el 409 de un proveedor ya DESACTIVADO vuelve sin acciones: lo que el servidor no manda no existe", async () => {
    dobles("post", `${RUTA_PROVEEDOR}/baja`, () =>
      HttpResponse.json(
        errorConflictoEstado("PROVEEDOR_CON_ORDENES_ABIERTAS", {
          mensaje: "CoPanel tiene 2 órdenes pendientes de recibir y ya está desactivado; la baja procede cuando esas órdenes se reciban completas o se cancelen.",
          detalle: { ordenes: ORDENES },
          acciones: [],
        }),
        { status: 409 },
      ),
    );

    const resultado = await darDeBajaProveedor(crearCliente(), PROVEEDOR_ID, MOTIVO);

    expect(resultado).toEqual({
      ok: false,
      error: expect.objectContaining({ codigo: "PROVEEDOR_CON_ORDENES_ABIERTAS", detalle: { ordenes: ORDENES }, acciones: [] }),
    });
  });
});
