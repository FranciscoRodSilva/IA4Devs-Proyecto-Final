import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import type { components as Servidor } from "@/api/generado/servidor";
import type { Rol } from "@/api/sesion";
import { enteroNoNegativo } from "@/compartido/dinero/dinero";
import { proveedor as proveedorBase, tokenCsrf, usuarioActual } from "@/pruebas/cuerpos";
import { renderizarAplicacion } from "@/pruebas/render";
import { servidorPruebas } from "@/pruebas/servidor";

// TKT-032a · fila F5 · TC-F09 a TC-F16 (CA-1, CA-6, CA-7, CA-9). La pantalla se prueba montada en su ruta
// `/compras/proveedores` dentro de la aplicación completa, con MSW como servidor: así la prueba no importa ningún módulo
// nuevo y cada caso falla por el comportamiento ausente (hoy la ruta pinta el marcador «Esta sección aún no está disponible»).
// Las respuestas se construyen con los tipos generados del OpenAPI (`satisfies`).
//
// El doble del servidor aplica lo que el contrato dice de `GET /proveedores`: sin `estado` solo trae los ACTIVO, filtra por
// `q` en nombre y RFC, y pagina con `pagina` y `tamano_pagina`. Así «Activos por omisión» no depende de la pantalla: la
// prueba comprueba lo que la pantalla ENVÍA (`estado=ACTIVO` explícito), no lo que el doble decide por ella.
// La caché de TanStack (`staleTime` de 30 s) sirve sin pedir de nuevo una consulta ya hecha: las pruebas piden de nuevo
// solo claves nuevas y, para volver a una ya vista, comprueban lo que se ve y no la petición.

type Esquemas = Servidor["schemas"];
type Proveedor = Esquemas["Proveedor"];

const ORIGEN = globalThis.location.origin;
const RUTA_SESION = "/api/v1/sesion";
const RUTA_CSRF = "/api/v1/sesion/csrf";
const RUTA_LISTA = "/api/v1/proveedores";
const RUTA_PANTALLA = "/compras/proveedores";

const ETIQUETA_ALTA = "Dar de alta un proveedor";
const ETIQUETA_CARGANDO = "Cargando los proveedores";
const TEXTO_VACIO = /No hay proveedores con este filtro/;
const INVITACION_ALTA = /Da de alta el primer proveedor con el botón \+\./;
const CORRELACION_ID = "7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e";
const TAMANO_PAGINA = 50;

const ID_ACEROS = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d";
const ID_COPANEL = "9c2e5a41-7b3d-4f68-a1c9-3d5e7f9b1a24";
const ID_FERRETERA = "2b3c4d5e-6f70-4b8c-9d0e-1f2a3b4c5d6e";
const ID_PINTURAS = "3c4d5e6f-7081-4c9d-8e1f-2a3b4c5d6e7f";

const ROL_QUE_OPERA: Rol = "COMPRAS";
const ROLES_QUE_SOLO_LEEN: Rol[] = ["DIRECCION_GENERAL", "DIRECTOR_PROYECTOS", "RESIDENTE", "ALMACEN", "ADMINISTRACION"];

/** `dia_corte` y `dia_pago` van de 1 (lunes) a 7 (domingo), ISO 8601; la pantalla los muestra por su nombre. */
const DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"] as const;

// Los tiempos se controlan con el reloj simulado que avanza solo: `usuario` de userEvent lo exige y ninguna prueba hace `sleep`.
beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
afterEach(() => {
  vi.useRealTimers();
});

/** Una promesa cuyo desenlace decide la prueba: así «cargando» se observa sin esperar por tiempo. */
function diferido() {
  let resolver!: () => void;
  const promesa = new Promise<void>((resolve) => {
    resolver = resolve;
  });
  return { promesa, resolver };
}

function proveedor(cambios: Partial<Proveedor> = {}): Proveedor {
  return proveedorBase({ creado_en: "2026-11-17T15:00:00Z", ...cambios });
}

/** ACTIVO, corte martes y pago viernes: distinto de CoPanel para que cambiar corte por pago o una fila por otra se note. */
function aceros(): Proveedor {
  return proveedor({ id: ID_ACEROS, nombre: "Aceros del Bajío", rfc: "ABA040312KT7", tope_consignacion: null, dia_corte: 2, dia_pago: 5 });
}

/** ACTIVO, corte jueves y pago sábado (los valores por omisión de la fábrica). */
function copanel(): Proveedor {
  return proveedor({ id: ID_COPANEL });
}

function ferretera(): Proveedor {
  return proveedor({ id: ID_FERRETERA, nombre: "Ferretera Vieja", rfc: "FVI870605XY9", estado: "BAJA", dia_corte: 2, dia_pago: 6 });
}

function pinturas(): Proveedor {
  return proveedor({ id: ID_PINTURAS, nombre: "Pinturas del Norte", rfc: "PNO990101AB2", estado: "DESACTIVADO" });
}

/** Los cuatro proveedores, uno por estado y dos ACTIVO, en el orden por nombre que manda el servidor. */
function proveedoresDeLosTresEstados(): Proveedor[] {
  return [aceros(), copanel(), ferretera(), pinturas()];
}

/**
 * `cantidad` proveedores con nombre «Proveedor 001», «Proveedor 002»…, ya en el orden por nombre. Son ACTIVO salvo que
 * `cambios` diga otra cosa; `desde` desplaza la numeración para poder mezclar grupos sin repetir nombre ni identificador.
 */
function catalogo(cantidad: number, cambios: Partial<Proveedor> = {}, desde = 0): Proveedor[] {
  return Array.from({ length: cantidad }, (_, indice) => {
    const posicion = desde + indice + 1;
    const numero = String(posicion).padStart(3, "0");
    return proveedor({
      id: `00000000-0000-4000-8000-${String(posicion).padStart(12, "0")}`,
      nombre: `Proveedor ${numero}`,
      rfc: `PRV010101${numero}`,
      ...cambios,
    });
  });
}

function dobleSesion(roles: Rol[]) {
  return http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(usuarioActual(roles)));
}

function dobleCsrf() {
  return http.get(`${ORIGEN}${RUTA_CSRF}`, () => HttpResponse.json(tokenCsrf()));
}

/** El catálogo vivo del servidor: la prueba lo cambia entre dos peticiones y la siguiente lo ve. */
interface Almacen {
  proveedores: Proveedor[];
}

/** GET /proveedores con la semántica del contrato: `estado` repetible (por omisión ACTIVO), `q`, `pagina` y `tamano_pagina`. */
function dobleLista(almacen: Almacen, opciones: { espera?: Promise<void> } = {}) {
  const pedidas: URL[] = [];
  const contador = { respondidas: 0 };
  const handler = http.get(`${ORIGEN}${RUTA_LISTA}`, async ({ request }) => {
    const url = new URL(request.url);
    pedidas.push(url);
    if (opciones.espera !== undefined) await opciones.espera;
    const estados = url.searchParams.getAll("estado");
    const q = (url.searchParams.get("q") ?? "").toLowerCase();
    const pagina = enteroNoNegativo(url.searchParams.get("pagina")) ?? 1;
    const tamano = enteroNoNegativo(url.searchParams.get("tamano_pagina")) ?? TAMANO_PAGINA;
    const coincidentes = almacen.proveedores.filter(
      (candidato) =>
        (estados.length === 0 ? candidato.estado === "ACTIVO" : estados.includes(candidato.estado)) &&
        (q === "" || candidato.nombre.toLowerCase().includes(q) || candidato.rfc.toLowerCase().includes(q)),
    );
    const elementos = coincidentes.slice((pagina - 1) * tamano, pagina * tamano);
    contador.respondidas += 1;
    return HttpResponse.json({
      elementos,
      paginacion: { pagina, tamano_pagina: tamano, total: coincidentes.length },
    } satisfies Esquemas["ListaProveedores"]);
  });
  return { handler, pedidas, contador };
}

type Lista = ReturnType<typeof dobleLista>;

function dobleListaConFallo() {
  return http.get(`${ORIGEN}${RUTA_LISTA}`, () =>
    HttpResponse.json({ mensaje: "Error interno del servidor.", correlacion_id: CORRELACION_ID }, { status: 500 }),
  );
}

interface OpcionesPantalla {
  proveedores?: Proveedor[];
  espera?: Promise<void>;
}

/** Monta la aplicación en `/compras/proveedores` con la sesión del rol, espera a que la sesión cargue y devuelve la lista doblada. */
async function abrirPantalla(roles: Rol[], { proveedores = [aceros(), copanel()], espera }: OpcionesPantalla = {}) {
  const almacen: Almacen = { proveedores };
  const lista = dobleLista(almacen, { espera });
  servidorPruebas.use(dobleSesion(roles), dobleCsrf(), lista.handler);
  const aplicacion = renderizarAplicacion(RUTA_PANTALLA);
  await screen.findByText(/Rosa Villanueva/);
  return { ...aplicacion, lista, almacen };
}

/** Pantalla con proveedores ya pintados (espera a la tabla). */
async function abrirPantallaConTabla(roles: Rol[], opciones: OpcionesPantalla = {}) {
  const pantalla = await abrirPantalla(roles, opciones);
  await screen.findByRole("table");
  return pantalla;
}

/** Espera a que el servidor haya respondido `respondidas` veces y a que el esqueleto ya no esté: la vista es la definitiva. */
async function esperarRespuesta(lista: Lista, respondidas: number) {
  await waitFor(() => expect(lista.contador.respondidas).toBeGreaterThanOrEqual(respondidas));
  await waitFor(() => expect(screen.queryByRole("status", { name: ETIQUETA_CARGANDO })).not.toBeInTheDocument());
}

type Usuario = ReturnType<typeof renderizarAplicacion>["usuario"];

/** Los controles de la barra y del pie de la lista, por su rol y su nombre visible. */
const controles = {
  get estado() {
    return screen.getByRole("combobox", { name: "Estado" });
  },
  get busqueda() {
    return screen.getByRole("searchbox");
  },
  get buscar() {
    return screen.getByRole("button", { name: "Buscar" });
  },
  get anterior() {
    return screen.getByRole("button", { name: "Anterior" });
  },
  get siguiente() {
    return screen.getByRole("button", { name: "Siguiente" });
  },
};

async function elegirEstado(usuario: Usuario, opcion: string) {
  await usuario.selectOptions(controles.estado, opcion);
}

/** Las filas de datos de una tabla: todas menos la del encabezado. */
function filasDeDatos(tabla: HTMLElement) {
  return within(tabla)
    .getAllByRole("row")
    .filter((fila) => within(fila).queryAllByRole("columnheader").length === 0);
}

function celdasDe(fila: HTMLElement): string[] {
  return within(fila)
    .getAllByRole("cell")
    .map((celda) => celda.textContent ?? "");
}

/** Los nombres de la primera columna, en el orden en que se pintan. */
function nombresPintados(): string[] {
  return filasDeDatos(screen.getByRole("table")).map((fila) => celdasDe(fila).at(0) ?? "");
}

function filaDe(nombre: string): HTMLElement {
  return within(screen.getByRole("table")).getByRole("row", { name: new RegExp(`^${nombre}`) });
}

function estadosPedidos(url: URL | undefined): string[] {
  return [...(url?.searchParams.getAll("estado") ?? [])].sort();
}

describe("TKT-032a · TC-F09 · la lista del catálogo (CA-1)", () => {
  test("hdu004_esc02 · TC-F09 · la lista trae nombre, RFC, estado, corte y pago de cada proveedor, en el orden que manda el servidor", async () => {
    await abrirPantallaConTabla([ROL_QUE_OPERA]);

    const tabla = screen.getByRole("table");
    for (const columna of ["Nombre", "RFC", "Estado", "Corte", "Pago"]) {
      expect(within(tabla).getByRole("columnheader", { name: columna })).toBeInTheDocument();
    }
    expect(nombresPintados()).toEqual(["Aceros del Bajío", "CoPanel"]);
    expect(celdasDe(filaDe("Aceros del Bajío")).slice(0, 5)).toEqual(["Aceros del Bajío", "ABA040312KT7", "Activo", "martes", "viernes"]);
    expect(celdasDe(filaDe("CoPanel")).slice(0, 5)).toEqual(["CoPanel", "XAXX010101000", "Activo", "jueves", "sábado"]);
    // Ya no es el marcador de la sección.
    expect(screen.queryByText("Esta sección aún no está disponible.")).not.toBeInTheDocument();
  });

  test.each([1, 2, 3, 4, 5, 6, 7])(
    "hdu004_esc02 · TC-F09 · el día %i se muestra por su nombre, el corte en su columna y el pago en la suya",
    async (dia) => {
      // El pago es el día siguiente al corte: si la pantalla cruzara las columnas o mostrara el número, no coincidiría.
      const diaPago = (dia % 7) + 1;
      await abrirPantallaConTabla(["DIRECCION_GENERAL"], {
        proveedores: [proveedor({ id: ID_COPANEL, dia_corte: dia, dia_pago: diaPago })],
      });

      const celdas = celdasDe(filaDe("CoPanel"));
      expect(celdas.at(3)).toBe(DIAS[dia - 1]);
      expect(celdas.at(4)).toBe(DIAS[diaPago - 1]);
    },
  );
});

describe("TKT-032a · TC-F10 · los cuatro estados de la lista (CA-1)", () => {
  test("tkt032a_lista · TC-F10 · cargando: un esqueleto con su etiqueta, no un contenido vacío", async () => {
    const compuerta = diferido();
    const { lista } = await abrirPantalla([ROL_QUE_OPERA], { espera: compuerta.promesa });

    await waitFor(() => expect(lista.pedidas).toHaveLength(1));
    const esqueleto = screen.getByRole("status", { name: ETIQUETA_CARGANDO });
    expect(esqueleto).toHaveAttribute("aria-busy", "true");
    expect(screen.queryByText(TEXTO_VACIO)).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();

    compuerta.resolver();
    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: ETIQUETA_CARGANDO })).not.toBeInTheDocument();
  });

  test("tkt032a_lista · TC-F10 · vacío para Compras con el filtro por omisión: el texto y la invitación al +", async () => {
    await abrirPantalla([ROL_QUE_OPERA], { proveedores: [] });

    expect(await screen.findByText(TEXTO_VACIO)).toBeInTheDocument();
    expect(screen.getByText(INVITACION_ALTA)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: ETIQUETA_ALTA }).length).toBeGreaterThan(0);
  });

  test.each(ROLES_QUE_SOLO_LEEN)("tkt032a_lista · TC-F10 · vacío para %s: el texto, sin invitación ni botón +", async (rol) => {
    await abrirPantalla([rol], { proveedores: [] });

    expect(await screen.findByText(TEXTO_VACIO)).toBeInTheDocument();
    expect(screen.queryByText(INVITACION_ALTA)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: ETIQUETA_ALTA })).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  test("tkt032a_lista · TC-F10 · vacío para Compras con otro filtro: el texto, sin la invitación al +", async () => {
    // Un solo proveedor ACTIVO: con «Desactivados» la lista queda vacía y la invitación de «primer proveedor» sería falsa.
    const { usuario, lista } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: [copanel()] });
    expect(screen.queryByText(TEXTO_VACIO)).not.toBeInTheDocument();

    await elegirEstado(usuario, "Desactivados");
    await esperarRespuesta(lista, 2);

    expect(await screen.findByText(TEXTO_VACIO)).toBeInTheDocument();
    expect(screen.queryByText(INVITACION_ALTA)).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    // La barra sigue a la vista: se puede volver a otro filtro.
    expect(screen.getByRole("combobox", { name: "Estado" })).toBeInTheDocument();
  });

  test("tkt032a_lista · TC-F10 · error: el aviso lleva el correlacion_id y «Reintentar» vuelve a pedir la lista", async () => {
    servidorPruebas.use(dobleSesion([ROL_QUE_OPERA]), dobleCsrf(), dobleListaConFallo());
    const { usuario } = renderizarAplicacion(RUTA_PANTALLA);
    await screen.findByText(/Rosa Villanueva/);

    expect(await screen.findByText(new RegExp(CORRELACION_ID))).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText(TEXTO_VACIO)).not.toBeInTheDocument();
    expect(screen.queryByText(INVITACION_ALTA)).not.toBeInTheDocument();

    const recuperada = dobleLista({ proveedores: [copanel()] });
    servidorPruebas.use(recuperada.handler);
    await usuario.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByRole("cell", { name: "CoPanel" })).toBeInTheDocument();
    expect(recuperada.pedidas).toHaveLength(1);
    expect(screen.queryByText(new RegExp(CORRELACION_ID))).not.toBeInTheDocument();
  });

  test("tkt032a_lista · TC-F10 · con proveedores: la tabla, sin esqueleto ni texto de vacío", async () => {
    await abrirPantallaConTabla(["DIRECCION_GENERAL"]);

    expect(screen.queryByRole("status", { name: ETIQUETA_CARGANDO })).not.toBeInTheDocument();
    expect(screen.queryByText(TEXTO_VACIO)).not.toBeInTheDocument();
    expect(filasDeDatos(screen.getByRole("table"))).toHaveLength(2);
  });
});

describe("TKT-032a · TC-F11 · el filtro por estado (CA-1, M-5)", () => {
  test("tkt032a_lista · TC-F11 · por omisión pide los ACTIVO de forma explícita, página 1 y 50 por página, y el filtro dice «Activos»", async () => {
    const { lista } = await abrirPantallaConTabla(["DIRECCION_GENERAL"], { proveedores: proveedoresDeLosTresEstados() });

    expect(lista.pedidas).toHaveLength(1);
    const [primera] = lista.pedidas;
    // M-5: si la pantalla dejara de enviar `estado=ACTIVO` el servidor lo asumiría, pero el contrato del cliente es enviarlo.
    expect(primera?.searchParams.getAll("estado")).toEqual(["ACTIVO"]);
    expect(primera?.searchParams.get("pagina")).toBe("1");
    expect(primera?.searchParams.get("tamano_pagina")).toBe("50");
    expect(primera?.searchParams.has("q")).toBe(false);
    expect(screen.getByRole("combobox", { name: "Estado" })).toHaveDisplayValue("Activos");
    expect(nombresPintados()).toEqual(["Aceros del Bajío", "CoPanel"]);
  });

  test.each<[string, string[], string[]]>([
    ["Desactivados", ["DESACTIVADO"], ["Pinturas del Norte"]],
    ["Dados de baja", ["BAJA"], ["Ferretera Vieja"]],
    ["Todos", ["ACTIVO", "BAJA", "DESACTIVADO"], ["Aceros del Bajío", "CoPanel", "Ferretera Vieja", "Pinturas del Norte"]],
  ])("tkt032a_lista · TC-F11 · elegir «%s» vuelve a pedir con esos estados y muestra lo que el servidor devolvió", async (opcion, estados, nombres) => {
    const { usuario, lista } = await abrirPantallaConTabla(["DIRECCION_GENERAL"], { proveedores: proveedoresDeLosTresEstados() });

    await elegirEstado(usuario, opcion);
    await esperarRespuesta(lista, 2);

    expect(lista.pedidas).toHaveLength(2);
    const ultima = lista.pedidas.at(-1);
    expect(estadosPedidos(ultima)).toEqual(estados);
    expect(ultima?.searchParams.get("pagina")).toBe("1");
    expect(screen.getByRole("combobox", { name: "Estado" })).toHaveDisplayValue(opcion);
    expect(nombresPintados()).toEqual(nombres);
  });

  test("tkt032a_lista · TC-F11 · cambiar el filtro desde la página 2 vuelve a la página 1, aunque el filtro nuevo también tenga página 2", async () => {
    // 60 desactivados: la página 2 del filtro nuevo SÍ tiene datos, así que una pantalla que conservara la página 2 la pediría.
    const proveedores = [...catalogo(120), ...catalogo(60, { estado: "DESACTIVADO" }, 200)];
    const { usuario, lista } = await abrirPantallaConTabla(["DIRECCION_GENERAL"], { proveedores });
    await usuario.click(controles.siguiente);
    await esperarRespuesta(lista, 2);
    expect(lista.pedidas.at(-1)?.searchParams.get("pagina")).toBe("2");

    await elegirEstado(usuario, "Desactivados");
    await esperarRespuesta(lista, 3);

    const delFiltroNuevo = lista.pedidas.filter((url) => estadosPedidos(url).join() === "DESACTIVADO");
    expect(delFiltroNuevo.map((url) => url.searchParams.get("pagina"))).toEqual(["1"]);
    expect(nombresPintados().at(0)).toBe("Proveedor 201");
    expect(screen.getByText("Página 1 de 2")).toBeInTheDocument();
  });

  test("tkt032a_lista · TC-F11 · volver a «Activos» muestra de nuevo solo los ACTIVO", async () => {
    const { usuario, lista } = await abrirPantallaConTabla(["DIRECCION_GENERAL"], { proveedores: proveedoresDeLosTresEstados() });
    await elegirEstado(usuario, "Todos");
    await esperarRespuesta(lista, 2);
    expect(nombresPintados()).toHaveLength(4);

    await elegirEstado(usuario, "Activos");

    await waitFor(() => expect(nombresPintados()).toEqual(["Aceros del Bajío", "CoPanel"]));
    expect(screen.getByRole("combobox", { name: "Estado" })).toHaveDisplayValue("Activos");
  });
});

describe("TKT-032a · TC-F12 · la búsqueda por nombre o RFC (CA-1)", () => {
  test("hdu004_esc02 · TC-F12 · escribir no pide nada; «Buscar» pide q con el estado vigente y muestra lo que coincide", async () => {
    const { usuario, lista } = await abrirPantallaConTabla(["DIRECCION_GENERAL"]);

    await usuario.type(controles.busqueda, "copanel");
    // Sin temporizador: la búsqueda se aplica al pulsar «Buscar» o Enter, no al teclear.
    expect(lista.pedidas).toHaveLength(1);

    await usuario.click(controles.buscar);
    await esperarRespuesta(lista, 2);

    const ultima = lista.pedidas.at(-1);
    expect(ultima?.searchParams.get("q")).toBe("copanel");
    expect(estadosPedidos(ultima)).toEqual(["ACTIVO"]);
    expect(ultima?.searchParams.get("pagina")).toBe("1");
    expect(nombresPintados()).toEqual(["CoPanel"]);
  });

  test("hdu004_esc02 · TC-F12 · Enter aplica la búsqueda igual que «Buscar» y también encuentra por RFC", async () => {
    const { usuario, lista } = await abrirPantallaConTabla(["DIRECCION_GENERAL"]);

    await usuario.type(controles.busqueda, "xaxx{Enter}");
    await esperarRespuesta(lista, 2);

    expect(lista.pedidas.at(-1)?.searchParams.get("q")).toBe("xaxx");
    expect(nombresPintados()).toEqual(["CoPanel"]);
  });

  test("tkt032a_lista · TC-F12 · buscar desde la página 2 vuelve a la página 1, aunque la búsqueda también tenga página 2", async () => {
    // «Proveedor 0» coincide con 99 de los 120: la página 2 de la búsqueda SÍ tiene datos, así que una pantalla que
    // conservara la página 2 la pediría.
    const { usuario, lista } = await abrirPantallaConTabla(["DIRECCION_GENERAL"], { proveedores: catalogo(120) });
    await usuario.click(controles.siguiente);
    await esperarRespuesta(lista, 2);
    expect(screen.getByText("Página 2 de 3")).toBeInTheDocument();

    await usuario.type(controles.busqueda, "Proveedor 0");
    await usuario.click(controles.buscar);
    await esperarRespuesta(lista, 3);

    const delaBusqueda = lista.pedidas.filter((url) => url.searchParams.get("q") === "Proveedor 0");
    expect(delaBusqueda.map((url) => url.searchParams.get("pagina"))).toEqual(["1"]);
    expect(estadosPedidos(delaBusqueda.at(0))).toEqual(["ACTIVO"]);
    expect(nombresPintados()).toHaveLength(50);
    expect(nombresPintados().at(0)).toBe("Proveedor 001");
    expect(screen.getByText("Página 1 de 2")).toBeInTheDocument();
  });

  test("tkt032a_lista · TC-F12 · vaciar la búsqueda quita q y devuelve la lista completa", async () => {
    const { usuario, lista } = await abrirPantallaConTabla(["DIRECCION_GENERAL"]);
    await usuario.type(controles.busqueda, "copanel");
    await usuario.click(controles.buscar);
    await esperarRespuesta(lista, 2);
    expect(nombresPintados()).toEqual(["CoPanel"]);

    await usuario.clear(controles.busqueda);
    await usuario.click(controles.buscar);

    await waitFor(() => expect(nombresPintados()).toEqual(["Aceros del Bajío", "CoPanel"]));
    // Ninguna petición lleva `q` vacío: o lleva texto o no lleva `q`.
    expect(lista.pedidas.every((url) => url.searchParams.get("q") !== "")).toBe(true);
  });

  test("tkt032a_lista · TC-F12 · una búsqueda de solo espacios no pide q", async () => {
    const { usuario, lista } = await abrirPantallaConTabla(["DIRECCION_GENERAL"]);

    await usuario.type(controles.busqueda, "   ");
    await usuario.click(controles.buscar);

    await waitFor(() => expect(nombresPintados()).toEqual(["Aceros del Bajío", "CoPanel"]));
    expect(lista.pedidas.every((url) => !url.searchParams.has("q"))).toBe(true);
  });
});

describe("TKT-032a · TC-F13 · la paginación (CA-1)", () => {
  test("tkt032a_lista · TC-F13 · 120 proveedores a 50 por página: «Página 1 de 3», 50 filas, Anterior inhabilitado y Siguiente pide la 2", async () => {
    const { usuario, lista } = await abrirPantallaConTabla(["DIRECCION_GENERAL"], { proveedores: catalogo(120) });

    expect(screen.getByText("Página 1 de 3")).toBeInTheDocument();
    expect(filasDeDatos(screen.getByRole("table"))).toHaveLength(50);
    expect(nombresPintados().at(0)).toBe("Proveedor 001");
    expect(nombresPintados().at(-1)).toBe("Proveedor 050");
    expect(controles.anterior).toBeDisabled();
    expect(controles.siguiente).toBeEnabled();

    await usuario.click(controles.siguiente);
    await esperarRespuesta(lista, 2);

    const ultima = lista.pedidas.at(-1);
    expect(ultima?.searchParams.get("pagina")).toBe("2");
    expect(ultima?.searchParams.get("tamano_pagina")).toBe("50");
    expect(screen.getByText("Página 2 de 3")).toBeInTheDocument();
    expect(nombresPintados().at(0)).toBe("Proveedor 051");
    expect(controles.anterior).toBeEnabled();
    expect(controles.siguiente).toBeEnabled();
  });

  test("tkt032a_lista · TC-F13 · en la última página Siguiente está inhabilitado y Anterior regresa a la anterior", async () => {
    const { usuario, lista } = await abrirPantallaConTabla(["DIRECCION_GENERAL"], { proveedores: catalogo(120) });
    await usuario.click(controles.siguiente);
    await esperarRespuesta(lista, 2);
    await usuario.click(controles.siguiente);
    await esperarRespuesta(lista, 3);

    expect(lista.pedidas.at(-1)?.searchParams.get("pagina")).toBe("3");
    expect(screen.getByText("Página 3 de 3")).toBeInTheDocument();
    expect(filasDeDatos(screen.getByRole("table"))).toHaveLength(20);
    expect(controles.siguiente).toBeDisabled();
    expect(controles.anterior).toBeEnabled();

    await usuario.click(controles.anterior);

    expect(await screen.findByText("Página 2 de 3")).toBeInTheDocument();
    expect(nombresPintados().at(0)).toBe("Proveedor 051");
  });

  test("tkt032a_lista · TC-F13 · una sola página: «Página 1 de 1» con los dos botones inhabilitados", async () => {
    await abrirPantallaConTabla(["DIRECCION_GENERAL"]);

    expect(screen.getByText("Página 1 de 1")).toBeInTheDocument();
    expect(controles.anterior).toBeDisabled();
    expect(controles.siguiente).toBeDisabled();
  });

  test("tkt032a_lista · TC-F13 · si la página pedida llega vacía con total mayor que cero, la pantalla vuelve a una página con datos y no pinta «vacío»", async () => {
    // 51 proveedores: la página 2 tiene una sola fila. Mientras la persona la pide, esa fila sale del filtro (otro usuario la
    // desactivó): el servidor responde página vacía con total 50.
    const { usuario, lista, almacen } = await abrirPantallaConTabla(["DIRECCION_GENERAL"], { proveedores: catalogo(51) });
    expect(screen.getByText("Página 1 de 2")).toBeInTheDocument();
    almacen.proveedores = catalogo(50);

    await usuario.click(controles.siguiente);
    await waitFor(() => expect(lista.pedidas.some((url) => url.searchParams.get("pagina") === "2")).toBe(true));
    await esperarRespuesta(lista, 2);

    await waitFor(() => {
      expect(screen.getByRole("cell", { name: "Proveedor 001" })).toBeInTheDocument();
      expect(screen.queryByText(TEXTO_VACIO)).not.toBeInTheDocument();
    });
    expect(screen.getByText(/^Página 1 de /)).toBeInTheDocument();
    expect(controles.anterior).toBeDisabled();
  });
});

describe("TKT-032a · TC-F14 · el estado se rotula con texto (CA-1, Should)", () => {
  test("hdu004_esc12 · TC-F14 · Activo, Desactivado y Baja se rotulan con un texto distinto en la columna Estado", async () => {
    const { usuario, lista } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: proveedoresDeLosTresEstados() });
    expect(celdasDe(filaDe("CoPanel")).at(2)).toBe("Activo");

    await elegirEstado(usuario, "Todos");
    await esperarRespuesta(lista, 2);

    const rotulos = ["CoPanel", "Pinturas del Norte", "Ferretera Vieja"].map((nombre) => celdasDe(filaDe(nombre)).at(2));
    expect(rotulos).toEqual(["Activo", "Desactivado", "Baja"]);
    expect(new Set(rotulos).size).toBe(3);
  });
});

/** Los nombres accesibles que Compras debe ver en la fila de cada estado, y los que no (M-1, M-2). */
const ACCIONES_POR_ESTADO: Array<[string, string, string[], string[]]> = [
  ["ACTIVO", "CoPanel", ["Editar", "Desactivar", "Dar de baja"], []],
  ["DESACTIVADO", "Pinturas del Norte", ["Editar", "Dar de baja"], ["Desactivar"]],
  ["BAJA", "Ferretera Vieja", [], ["Editar", "Desactivar", "Dar de baja"]],
];

describe("TKT-032a · TC-F15 · Compras ve el + y las acciones de cada fila según el estado (CA-6, CA-7, CA-9; M-1, M-2)", () => {
  test("tkt032a_rol · TC-F15 · Compras ve el botón + con su nombre accesible, una sola vez", async () => {
    await abrirPantallaConTabla([ROL_QUE_OPERA]);

    expect(screen.getAllByRole("button", { name: ETIQUETA_ALTA })).toHaveLength(1);
  });

  test.each(ACCIONES_POR_ESTADO)(
    "hdu004_esc12 · TC-F15 · una fila %s de Compras ofrece exactamente sus acciones, cada una con el nombre del proveedor",
    async (_estado, nombre, ofrecidas, vedadas) => {
      const { usuario, lista } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: proveedoresDeLosTresEstados() });
      await elegirEstado(usuario, "Todos");
      await esperarRespuesta(lista, 2);

      const fila = filaDe(nombre);
      for (const accion of ofrecidas) {
        expect(within(fila).getByRole("button", { name: `${accion} ${nombre}` })).toBeInTheDocument();
      }
      for (const accion of vedadas) {
        expect(within(fila).queryByRole("button", { name: `${accion} ${nombre}` })).not.toBeInTheDocument();
      }
      // «Ni más ni menos»: ningún otro botón en la fila.
      expect(within(fila).queryAllByRole("button")).toHaveLength(ofrecidas.length);
    },
  );

  test("hdu004_esc12 · TC-F15 · el botón de cada acción lleva el nombre de SU proveedor, no el de otra fila", async () => {
    await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: [aceros(), copanel()] });

    expect(within(filaDe("Aceros del Bajío")).getByRole("button", { name: "Editar Aceros del Bajío" })).toBeInTheDocument();
    expect(within(filaDe("Aceros del Bajío")).queryByRole("button", { name: "Editar CoPanel" })).not.toBeInTheDocument();
    expect(within(filaDe("CoPanel")).getByRole("button", { name: "Editar CoPanel" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Editar CoPanel" })).toBeInTheDocument();
  });
});

describe("TKT-032a · TC-F16 · quien no opera ve la lista y ninguna acción (CA-9, rechazo; M-3)", () => {
  test.each(ROLES_QUE_SOLO_LEEN)(
    "tkt032a_rol · TC-F16 · %s ve la lista con los tres estados y ni el botón + ni Editar, Desactivar o Dar de baja",
    async (rol) => {
      const { usuario, lista } = await abrirPantallaConTabla([rol], { proveedores: proveedoresDeLosTresEstados() });
      await elegirEstado(usuario, "Todos");
      await esperarRespuesta(lista, 2);

      // La lista sí se ve: el rechazo es de las acciones, no de la pantalla.
      expect(nombresPintados()).toEqual(["Aceros del Bajío", "CoPanel", "Ferretera Vieja", "Pinturas del Norte"]);
      expect(screen.queryByRole("button", { name: ETIQUETA_ALTA })).not.toBeInTheDocument();
      expect(screen.queryAllByRole("button", { name: /^(Editar|Desactivar|Dar de baja|Dar de alta)/ })).toHaveLength(0);
      // Ni siquiera como controles de la tabla.
      for (const fila of filasDeDatos(screen.getByRole("table"))) {
        expect(within(fila).queryAllByRole("button")).toHaveLength(0);
      }
    },
  );
});
