import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import type { Accion } from "@/api/errores";
import type { components as Servidor } from "@/api/generado/servidor";
import type { Rol } from "@/api/sesion";
import { errorConflictoEstado, obra as obraBase, tokenCsrf, usuarioActual } from "@/pruebas/cuerpos";
import { renderizarAplicacion } from "@/pruebas/render";
import { servidorPruebas } from "@/pruebas/servidor";

// TKT-012b · fila B4 · TC-73 a TC-79 (CA-5, CA-14, CA-16, CA-17; HDU-001 esc. 20). La pantalla se prueba montada en
// `/obras` dentro de la aplicación completa, con MSW como servidor, igual que `PantallaObras.acciones.test.tsx` (que no
// se toca). Las respuestas se construyen con los tipos generados del OpenAPI (`satisfies`). Las claves de acción del
// 409 `OBRA_CON_HISTORIAL` son las del contrato (`docs/api/openapi.yaml`, `eliminar_obra`): `SUSPENDER_OBRA` y `CERRAR_OBRA`.
//
// TC-73b (suspender, reactivar y cerrar contra un 409 ESTADO_NO_PERMITE_OPERACION) lo añadió el orquestador a petición
// propia: amplía la tabla de TC del diseño (línea 129) y se registra en `impl.md`.
//
// (asumido) Ninguna spec fija el texto del título de los diálogos ni el de su botón de confirmar. Se exige lo mínimo:
// el título de cada motivo nombra el verbo; la pregunta de eliminar nombra «eliminar» y el código de la obra; y el
// botón de confirmar es el único del diálogo que no es «Cancelar».

type Esquemas = Servidor["schemas"];
type Obra = Esquemas["Obra"];
type EstadoObra = Esquemas["EstadoObra"];

const ORIGEN = globalThis.location.origin;
const RUTA_SESION = "/api/v1/sesion";
const RUTA_CSRF = "/api/v1/sesion/csrf";
const RUTA_OBRAS = "/api/v1/obras";
const RUTA_PANTALLA = "/obras";

const ENCABEZADO_ACCIONES = "Acciones";
const MENSAJE_MOTIVO_OBLIGATORIO = "El motivo es obligatorio.";
const MOTIVO = "Falta de pago del cliente";
const REGION_CONFLICTO = "No se puede completar";

const ID_PLANEACION = "9a1f2b3c-4d5e-4f60-8a71-b2c3d4e5f607";
const ID_ACTIVA = "5d6e7f80-91a2-4b3c-84d5-e6f708192031";
const ID_SUSPENDIDA = "6e7f8091-a2b3-4c4d-95e6-f70819203142";
const ID_CERRADA = "7f8091a2-b3c4-4d5e-a6f7-081920314253";
const ID_OTRA_PLANEACION = "8091a2b3-c4d5-4e6f-b708-192031425364";

const CODIGO_POR_ESTADO: Readonly<Record<EstadoObra, string>> = {
  PLANEACION: "AP-058-25",
  ACTIVA: "AP-061-25",
  SUSPENDIDA: "AP-062-25",
  CERRADA: "AP-063-25",
};
const ID_POR_ESTADO: Readonly<Record<EstadoObra, string>> = {
  PLANEACION: ID_PLANEACION,
  ACTIVA: ID_ACTIVA,
  SUSPENDIDA: ID_SUSPENDIDA,
  CERRADA: ID_CERRADA,
};
const ETIQUETA_ESTADO: Readonly<Record<EstadoObra, string>> = {
  PLANEACION: "Planeación",
  ACTIVA: "Activa",
  SUSPENDIDA: "Suspendida",
  CERRADA: "Cerrada",
};

/** Lo que ofrece la fila del Director de Proyectos tras la transición (CA-14). */
const ACCIONES_POR_ESTADO: Readonly<Record<EstadoObra, readonly string[]>> = {
  PLANEACION: ["Editar", "Eliminar", "Cerrar"],
  ACTIVA: ["Editar", "Suspender", "Cerrar"],
  SUSPENDIDA: ["Editar", "Reactivar", "Cerrar"],
  CERRADA: [],
};

type RutaTransicion = "suspension" | "reactivacion" | "cierre";
interface Transicion {
  verbo: "Suspender" | "Reactivar" | "Cerrar";
  ruta: RutaTransicion;
  desde: EstadoObra;
  hacia: EstadoObra;
  titulo: RegExp;
}
const SUSPENDER: Transicion = { verbo: "Suspender", ruta: "suspension", desde: "ACTIVA", hacia: "SUSPENDIDA", titulo: /suspender/i };
const REACTIVAR: Transicion = { verbo: "Reactivar", ruta: "reactivacion", desde: "SUSPENDIDA", hacia: "ACTIVA", titulo: /reactivar/i };
const CERRAR_DESDE: readonly Transicion[] = (["PLANEACION", "ACTIVA", "SUSPENDIDA"] as const).map((desde) => ({
  verbo: "Cerrar",
  ruta: "cierre",
  desde,
  hacia: "CERRADA",
  titulo: /cerrar/i,
}));
const TRANSICIONES: readonly Transicion[] = [SUSPENDER, REACTIVAR, ...CERRAR_DESDE];

/** Para el título de los casos: «Suspender desde ACTIVA». */
const rotuloDe = (transicion: Transicion) => `${transicion.verbo} desde ${transicion.desde}`;

// Los tiempos se controlan con el reloj simulado que avanza solo: `usuario` de userEvent lo exige y ninguna prueba hace `sleep`.
beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
afterEach(() => {
  vi.useRealTimers();
});

function obraEn(estado: EstadoObra, cambios: Partial<Obra> = {}): Obra {
  return obraBase({
    id: ID_POR_ESTADO[estado],
    codigo: CODIGO_POR_ESTADO[estado],
    nombre: `Obra ${CODIGO_POR_ESTADO[estado]}`,
    estado,
    creado_en: "2026-11-10T15:00:00Z",
    ...cambios,
  });
}

/** Una segunda obra en PLANEACION, para que ninguna prueba pase por actuar siempre sobre la primera fila. */
function otraPlaneacion(): Obra {
  return obraEn("PLANEACION", { id: ID_OTRA_PLANEACION, codigo: "AP-059-25", nombre: "Obra AP-059-25" });
}

/** La obra que la prueba opera, precedida de una obra testigo cerrada: una pantalla que actuara sobre la primera fila fallaría. */
function obrasConTestigo(objetivo: Obra): Obra[] {
  return [obraEn("CERRADA"), objetivo];
}

function dobleSesion(roles: Rol[]) {
  return http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(usuarioActual(roles)));
}

function dobleCsrf() {
  return http.get(`${ORIGEN}${RUTA_CSRF}`, () => HttpResponse.json(tokenCsrf()));
}

/** GET /obras. `obras` es la lista viva del servidor: una operación la modifica y la siguiente petición la ve. */
function dobleLista(obras: Obra[]) {
  const pedidas: URL[] = [];
  const handler = http.get(`${ORIGEN}${RUTA_OBRAS}`, ({ request }) => {
    pedidas.push(new URL(request.url));
    return HttpResponse.json({
      elementos: obras,
      paginacion: { pagina: 1, tamano_pagina: 200, total: obras.length },
    } satisfies Esquemas["ListaObras"]);
  });
  return { handler, pedidas };
}

/** POST /obras/{obra_id}/{suspension|reactivacion|cierre}. Aplica el estado nuevo a la lista viva y responde la obra. */
function dobleTransicion(obras: Obra[], ruta: RutaTransicion, hacia: EstadoObra) {
  const recibidas: { obraId: string; cuerpo: Esquemas["Motivo"] }[] = [];
  const handler = http.post(`${ORIGEN}${RUTA_OBRAS}/:obraId/${ruta}`, async ({ request, params }) => {
    const cuerpo = (await request.json()) as Esquemas["Motivo"];
    const obraId = String(params.obraId);
    recibidas.push({ obraId, cuerpo });
    const indice = obras.findIndex((candidata) => candidata.id === obraId);
    const actual = obras[indice];
    if (actual === undefined) return HttpResponse.json({}, { status: 404 });
    const actualizada = { ...actual, estado: hacia } satisfies Obra;
    obras[indice] = actualizada;
    return HttpResponse.json(actualizada);
  });
  return { handler, recibidas };
}

/** DELETE /obras/{obra_id}. Por omisión borra de la lista viva y responde 204; una prueba puede dar otra respuesta. */
function dobleBaja(obras: Obra[], responder?: () => Response) {
  const recibidas: string[] = [];
  const handler = http.delete(`${ORIGEN}${RUTA_OBRAS}/:obraId`, ({ params }) => {
    const obraId = String(params.obraId);
    recibidas.push(obraId);
    if (responder !== undefined) return responder();
    const indice = obras.findIndex((candidata) => candidata.id === obraId);
    if (indice >= 0) obras.splice(indice, 1);
    return new HttpResponse(null, { status: 204 });
  });
  return { handler, recibidas };
}

/** El 409 `OBRA_CON_HISTORIAL` de `eliminar_obra`: el detalle y las acciones son los que declara el contrato. */
function respuestaConHistorial(obraId: string, claves: readonly string[]): Response {
  const todas: Readonly<Record<string, Accion>> = {
    SUSPENDER_OBRA: { clave: "SUSPENDER_OBRA", metodo: "POST", ruta: `${RUTA_OBRAS}/${obraId}/suspension` },
    CERRAR_OBRA: { clave: "CERRAR_OBRA", metodo: "POST", ruta: `${RUTA_OBRAS}/${obraId}/cierre` },
    ARCHIVAR_OBRA: { clave: "ARCHIVAR_OBRA", metodo: "POST", ruta: `${RUTA_OBRAS}/${obraId}/archivo` },
  };
  const acciones = claves.map((clave) => todas[clave]).filter((accion): accion is Accion => accion !== undefined);
  return HttpResponse.json(
    errorConflictoEstado("OBRA_CON_HISTORIAL", {
      mensaje: "La obra AP-059-25 tiene historial y no se puede eliminar.",
      detalle: { linea_base_congelada: true, lineas_base: 7, importaciones: 5, movimientos: 42 },
      acciones,
    }),
    { status: 409 },
  );
}

/** Monta la aplicación en `/obras` con la sesión del rol y espera a la sesión y a la tabla. */
async function abrirPantallaConTabla(obras: Obra[], ...manejadores: ReturnType<typeof http.post>[]) {
  const lista = dobleLista(obras);
  servidorPruebas.use(dobleSesion(["DIRECTOR_PROYECTOS"]), dobleCsrf(), lista.handler, ...manejadores);
  const aplicacion = renderizarAplicacion(RUTA_PANTALLA);
  await screen.findByText(/Rosa Villanueva/);
  await screen.findByRole("table");
  return { ...aplicacion, lista };
}

type Usuario = ReturnType<typeof renderizarAplicacion>["usuario"];

function filaDe(codigo: string) {
  return within(screen.getByRole("table")).getByRole("row", { name: new RegExp(codigo) });
}

/** Las acciones de una fila, por el primer vocablo de su nombre accesible («Editar» o «Editar AP-058-25» dan lo mismo). */
function accionesDe(fila: HTMLElement): string[] {
  return within(fila)
    .queryAllByRole("button")
    .map((boton) => (boton.getAttribute("aria-label") ?? boton.textContent).trim().split(/\s+/)[0] ?? "");
}

/** El texto de las celdas de una fila, también con un diálogo modal abierto (deja la tabla fuera del árbol de accesibilidad). */
function celdasDe(codigo: string): string[] {
  const fila = within(screen.getByRole("table", { hidden: true })).getByRole("row", { name: new RegExp(codigo), hidden: true });
  return within(fila)
    .getAllByRole("cell", { hidden: true })
    .map((celda) => celda.textContent.trim());
}

async function pulsarEnFila(usuario: Usuario, codigo: string, verbo: string) {
  await usuario.click(within(filaDe(codigo)).getByRole("button", { name: new RegExp(`^${verbo}\\b`) }));
}

function campoMotivo(dialogo: HTMLElement) {
  return within(dialogo).getByRole("textbox", { name: "Motivo" });
}

function botonCancelar(dialogo: HTMLElement) {
  return within(dialogo).getByRole("button", { name: "Cancelar" });
}

/** El botón de confirmar: el único del diálogo que no es «Cancelar». Su rótulo lo elige la pantalla. */
function botonConfirmar(dialogo: HTMLElement): HTMLElement {
  const botones = within(dialogo)
    .getAllByRole("button")
    .filter((boton) => boton.textContent.trim() !== "Cancelar");
  expect(botones).toHaveLength(1);
  const [confirmar] = botones;
  if (confirmar === undefined) throw new Error("El diálogo no tiene botón de confirmar.");
  return confirmar;
}

/** POST de una transición que el servidor rechaza porque otra pestaña ya cambió el estado (409 ESTADO_NO_PERMITE_OPERACION). */
function dobleTransicionRechazada(obras: Obra[], ruta: RutaTransicion, estadoReal: EstadoObra) {
  const recibidas: { obraId: string; cuerpo: Esquemas["Motivo"] }[] = [];
  const handler = http.post(`${ORIGEN}${RUTA_OBRAS}/:obraId/${ruta}`, async ({ request, params }) => {
    const cuerpo = (await request.json()) as Esquemas["Motivo"];
    const obraId = String(params.obraId);
    recibidas.push({ obraId, cuerpo });
    const indice = obras.findIndex((candidata) => candidata.id === obraId);
    const actual = obras[indice];
    if (actual === undefined) return HttpResponse.json({}, { status: 404 });
    // La otra pestaña ya la cambió: desde ahora la lista del servidor trae el estado real.
    obras[indice] = { ...actual, estado: estadoReal } satisfies Obra;
    return HttpResponse.json(
      errorConflictoEstado("ESTADO_NO_PERMITE_OPERACION", {
        mensaje: `La obra ${actual.codigo} está en ${estadoReal} y no admite esta operación.`,
        detalle: { estado: estadoReal, operaciones_admitidas: [] },
        acciones: [],
      }),
      { status: 409 },
    );
  });
  return { handler, recibidas };
}

/** El valor de un rótulo del detalle de un rechazo (`dt` y su `dd`), dentro de su región. */
function valorEn(region: HTMLElement, rotulo: string): string {
  const termino = within(region).getByText(rotulo, { selector: "dt" });
  return termino.nextElementSibling?.textContent.trim() ?? "";
}

async function esperarSinDialogo() {
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
}

function nombresDeBotones(region: HTMLElement): string[] {
  return within(region)
    .queryAllByRole("button")
    .map((boton) => boton.textContent.trim());
}

describe("TKT-012b · TC-73 · suspender con motivo (CA-17)", () => {
  test("tkt012b_ca17 · TC-73 · suspender con motivo: envía el motivo a la obra de la fila, la lista se vuelve a pedir y la fila pasa a «Suspendida» con «Reactivar»", async () => {
    const objetivo = obraEn("ACTIVA");
    const obras = obrasConTestigo(objetivo);
    const transicion = dobleTransicion(obras, "suspension", "SUSPENDIDA");
    const { usuario, lista } = await abrirPantallaConTabla(obras, transicion.handler);
    expect(lista.pedidas).toHaveLength(1);
    expect(accionesDe(filaDe(objetivo.codigo))).toEqual(ACCIONES_POR_ESTADO.ACTIVA);

    await pulsarEnFila(usuario, objetivo.codigo, "Suspender");
    const dialogo = await screen.findByRole("dialog", { name: SUSPENDER.titulo });
    // Abrir el motivo no envía nada: la petición sale al confirmar.
    expect(transicion.recibidas).toHaveLength(0);
    await usuario.type(campoMotivo(dialogo), MOTIVO);
    await usuario.click(botonConfirmar(dialogo));

    await esperarSinDialogo();
    expect(transicion.recibidas).toEqual([{ obraId: objetivo.id, cuerpo: { motivo: MOTIVO } }]);
    // La lista se invalida y se vuelve a pedir: el estado nuevo es el del servidor, no una edición local.
    await waitFor(() => expect(lista.pedidas).toHaveLength(2));
    await waitFor(() => expect(celdasDe(objetivo.codigo)).toContain(ETIQUETA_ESTADO.SUSPENDIDA));
    expect(accionesDe(filaDe(objetivo.codigo))).toEqual(ACCIONES_POR_ESTADO.SUSPENDIDA);
    // La obra testigo no cambió.
    expect(celdasDe("AP-063-25")).toContain(ETIQUETA_ESTADO.CERRADA);
    expect(accionesDe(filaDe("AP-063-25"))).toEqual([]);
  });
});

describe("TKT-012b · TC-74 · transición sin motivo (CA-17, rechazo)", () => {
  const casos = TRANSICIONES.flatMap((transicion) =>
    [
      ["vacío", ""],
      ["solo espacios", "   "],
    ].map(([descripcion, escrito]) => [rotuloDe(transicion), descripcion, escrito, transicion] as const),
  );

  test.each(casos)(
    "tkt012b_ca17 · TC-74 · rechazo: %s sin motivo (%s) no envía y el campo señala el error",
    async (_rotulo, _descripcion, escrito, transicion) => {
      const objetivo = obraEn(transicion.desde);
      const obras = obrasConTestigo(objetivo);
      const manejador = dobleTransicion(obras, transicion.ruta, transicion.hacia);
      const { usuario, lista } = await abrirPantallaConTabla(obras, manejador.handler);
      await pulsarEnFila(usuario, objetivo.codigo, transicion.verbo);
      const dialogo = await screen.findByRole("dialog", { name: transicion.titulo });

      if (escrito !== "") await usuario.type(campoMotivo(dialogo), escrito);
      await usuario.click(botonConfirmar(dialogo));

      expect(await within(dialogo).findByText(MENSAJE_MOTIVO_OBLIGATORIO)).toBeInTheDocument();
      expect(campoMotivo(dialogo)).toHaveAttribute("aria-invalid", "true");
      // Nada sale: ni la petición ni una nueva consulta de la lista, y el diálogo sigue abierto para corregir.
      expect(manejador.recibidas).toHaveLength(0);
      expect(lista.pedidas).toHaveLength(1);
      expect(screen.getByRole("dialog", { name: transicion.titulo })).toBeInTheDocument();
      expect(celdasDe(objetivo.codigo)).toContain(ETIQUETA_ESTADO[transicion.desde]);
    },
  );
});

describe("TKT-012b · TC-75 · reactivar y cerrar con motivo (CA-14, CA-17)", () => {
  test("tkt012b_ca17 · TC-75 · reactivar con motivo: la fila pasa a «Activa» y ofrece «Suspender» en lugar de «Reactivar»", async () => {
    const objetivo = obraEn("SUSPENDIDA");
    const obras = obrasConTestigo(objetivo);
    const transicion = dobleTransicion(obras, "reactivacion", "ACTIVA");
    const { usuario, lista } = await abrirPantallaConTabla(obras, transicion.handler);

    await pulsarEnFila(usuario, objetivo.codigo, "Reactivar");
    const dialogo = await screen.findByRole("dialog", { name: REACTIVAR.titulo });
    await usuario.type(campoMotivo(dialogo), "El cliente liquidó el adeudo");
    await usuario.click(botonConfirmar(dialogo));

    await esperarSinDialogo();
    expect(transicion.recibidas).toEqual([{ obraId: objetivo.id, cuerpo: { motivo: "El cliente liquidó el adeudo" } }]);
    await waitFor(() => expect(lista.pedidas).toHaveLength(2));
    await waitFor(() => expect(celdasDe(objetivo.codigo)).toContain(ETIQUETA_ESTADO.ACTIVA));
    expect(accionesDe(filaDe(objetivo.codigo))).toEqual(ACCIONES_POR_ESTADO.ACTIVA);
  });

  test.each(CERRAR_DESDE.map((transicion) => transicion.desde))(
    "tkt012b_ca14 · TC-75 · cerrar con motivo desde %s: la fila pasa a «Cerrada» y ya no ofrece ninguna acción",
    async (desde) => {
      const objetivo = obraEn(desde);
      const obras = obrasConTestigo(objetivo);
      const transicion = dobleTransicion(obras, "cierre", "CERRADA");
      const { usuario, lista } = await abrirPantallaConTabla(obras, transicion.handler);
      expect(accionesDe(filaDe(objetivo.codigo))).toEqual(ACCIONES_POR_ESTADO[desde]);

      await pulsarEnFila(usuario, objetivo.codigo, "Cerrar");
      const dialogo = await screen.findByRole("dialog", { name: /cerrar/i });
      await usuario.type(campoMotivo(dialogo), "Obra terminada y entregada");
      await usuario.click(botonConfirmar(dialogo));

      await esperarSinDialogo();
      expect(transicion.recibidas).toEqual([{ obraId: objetivo.id, cuerpo: { motivo: "Obra terminada y entregada" } }]);
      await waitFor(() => expect(lista.pedidas).toHaveLength(2));
      await waitFor(() => expect(celdasDe(objetivo.codigo)).toContain(ETIQUETA_ESTADO.CERRADA));
      expect(accionesDe(filaDe(objetivo.codigo))).toEqual([]);
      // La columna sigue ahí: la decide el rol, no el estado de las filas.
      expect(within(screen.getByRole("table")).getByRole("columnheader", { name: ENCABEZADO_ACCIONES })).toBeInTheDocument();
    },
  );
});

describe("TKT-012b · TC-76 · eliminar una obra sin historial (CA-5)", () => {
  test("tkt012b_ca05 · TC-76 · la pregunta lleva el código de la obra de la fila y al confirmar la obra sale de la lista", async () => {
    const primera = obraEn("PLANEACION");
    const objetivo = otraPlaneacion();
    const obras = [primera, objetivo];
    const baja = dobleBaja(obras);
    const { usuario, lista } = await abrirPantallaConTabla(obras, baja.handler);

    await pulsarEnFila(usuario, objetivo.codigo, "Eliminar");
    const dialogo = await screen.findByRole("dialog", { name: new RegExp(objetivo.codigo) });
    // La pregunta nombra la acción y la obra de esa fila, no la primera.
    expect(dialogo).toHaveAccessibleName(/eliminar/i);
    expect(dialogo).not.toHaveAccessibleName(new RegExp(primera.codigo));
    // Preguntar no es enviar.
    expect(baja.recibidas).toHaveLength(0);
    await usuario.click(botonConfirmar(dialogo));

    await esperarSinDialogo();
    expect(baja.recibidas).toEqual([objetivo.id]);
    await waitFor(() => expect(lista.pedidas).toHaveLength(2));
    await waitFor(() => expect(within(screen.getByRole("table")).queryByRole("cell", { name: objetivo.codigo })).not.toBeInTheDocument());
    // La otra obra sigue y no hay rechazo alguno.
    expect(within(screen.getByRole("table")).getByRole("cell", { name: primera.codigo })).toBeInTheDocument();
    expect(screen.queryByRole("region", { name: REGION_CONFLICTO })).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("TKT-012b · TC-77 · eliminar con historial muestra el bloqueo (CA-16, HDU-001 esc. 20, rechazo)", () => {
  test("tkt012b_ca16 · hdu001_esc20 · TC-77 · el 409 OBRA_CON_HISTORIAL se pinta como conflicto con su mensaje, su detalle y solo las acciones del contrato; la obra sigue en la lista", async () => {
    const objetivo = otraPlaneacion();
    const obras = [obraEn("PLANEACION"), objetivo];
    const baja = dobleBaja(obras, () => respuestaConHistorial(objetivo.id, ["SUSPENDER_OBRA", "CERRAR_OBRA"]));
    const { usuario } = await abrirPantallaConTabla(obras, baja.handler);

    await pulsarEnFila(usuario, objetivo.codigo, "Eliminar");
    const dialogo = await screen.findByRole("dialog", { name: new RegExp(objetivo.codigo) });
    await usuario.click(botonConfirmar(dialogo));

    // El contrato completo: tratamiento de conflicto con su código, el mensaje del servidor, el detalle y las acciones.
    const bloqueo = await screen.findByRole("region", { name: REGION_CONFLICTO });
    expect(bloqueo).toHaveAttribute("data-estado", "bloqueado");
    expect(within(bloqueo).getByText("OBRA_CON_HISTORIAL")).toBeInTheDocument();
    expect(within(bloqueo).getByText("La obra AP-059-25 tiene historial y no se puede eliminar.")).toBeInTheDocument();
    // El detalle llega tal como lo envió el servidor: líneas base, importaciones y movimientos.
    expect(within(bloqueo).getByText("7")).toBeInTheDocument();
    expect(within(bloqueo).getByText("5")).toBeInTheDocument();
    expect(within(bloqueo).getByText("42")).toBeInTheDocument();
    // Las acciones son las del contrato, rotuladas, y en su orden: sin «Cerrar» propio del bloqueo ni claves crudas.
    expect(nombresDeBotones(bloqueo)).toEqual(["Suspender", "Cerrar"]);
    // No es un error ni una pantalla aparte: ninguna alerta, ningún diálogo, y la petición salió una sola vez.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText("Operación bloqueada")).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(baja.recibidas).toEqual([objetivo.id]);
    // La obra sigue en la lista, con el mismo estado y las mismas acciones.
    expect(within(screen.getByRole("table")).getByRole("cell", { name: objetivo.codigo })).toBeInTheDocument();
    expect(accionesDe(filaDe(objetivo.codigo))).toEqual(ACCIONES_POR_ESTADO.PLANEACION);
  });

  // Derivado de design.md, «Reglas de la pantalla» (Eliminar): pulsar una acción del bloqueo abre el motivo y envía
  // sobre la obra de esa fila. No figura como TC propio en la tabla del diseño; si el orquestador lo considera
  // ampliación de alcance de B4, se retira este caso.
  test("tkt012b_ca16 · TC-77 · pulsar «Cerrar» del bloqueo abre el motivo y cierra la obra de la fila que se intentó eliminar", async () => {
    const objetivo = otraPlaneacion();
    const obras = [obraEn("PLANEACION"), objetivo];
    const baja = dobleBaja(obras, () => respuestaConHistorial(objetivo.id, ["CERRAR_OBRA"]));
    const cierre = dobleTransicion(obras, "cierre", "CERRADA");
    const { usuario } = await abrirPantallaConTabla(obras, baja.handler, cierre.handler);
    await pulsarEnFila(usuario, objetivo.codigo, "Eliminar");
    await usuario.click(botonConfirmar(await screen.findByRole("dialog", { name: new RegExp(objetivo.codigo) })));
    const bloqueo = await screen.findByRole("region", { name: REGION_CONFLICTO });

    await usuario.click(within(bloqueo).getByRole("button", { name: "Cerrar" }));
    const motivo = await screen.findByRole("dialog", { name: /cerrar/i });
    expect(cierre.recibidas).toHaveLength(0);
    await usuario.type(campoMotivo(motivo), "Obra con historial: se cierra");
    await usuario.click(botonConfirmar(motivo));

    await esperarSinDialogo();
    expect(cierre.recibidas).toEqual([{ obraId: objetivo.id, cuerpo: { motivo: "Obra con historial: se cierra" } }]);
    await waitFor(() => expect(celdasDe(objetivo.codigo)).toContain(ETIQUETA_ESTADO.CERRADA));
    expect(accionesDe(filaDe(objetivo.codigo))).toEqual([]);
  });
});

describe("TKT-012b · TC-78 · las acciones del bloqueo son las del contrato, no cableadas (CA-16, rechazo)", () => {
  const variantes = [
    ["solo CERRAR_OBRA", ["CERRAR_OBRA"], ["Cerrar"]],
    ["solo SUSPENDER_OBRA", ["SUSPENDER_OBRA"], ["Suspender"]],
    ["en el orden que manda el servidor", ["CERRAR_OBRA", "SUSPENDER_OBRA"], ["Cerrar", "Suspender"]],
    ["ninguna (obra CERRADA)", [], []],
  ] as const;

  test.each(variantes)(
    "tkt012b_ca16 · TC-78 · con un mock que devuelve %s, el bloqueo ofrece exactamente esas acciones",
    async (_descripcion, claves, esperados) => {
      const objetivo = otraPlaneacion();
      const obras = [obraEn("PLANEACION"), objetivo];
      const baja = dobleBaja(obras, () => respuestaConHistorial(objetivo.id, claves));
      const { usuario } = await abrirPantallaConTabla(obras, baja.handler);

      await pulsarEnFila(usuario, objetivo.codigo, "Eliminar");
      await usuario.click(botonConfirmar(await screen.findByRole("dialog", { name: new RegExp(objetivo.codigo) })));

      const bloqueo = await screen.findByRole("region", { name: REGION_CONFLICTO });
      expect(nombresDeBotones(bloqueo)).toEqual(esperados);
      expect(within(bloqueo).getByText("OBRA_CON_HISTORIAL")).toBeInTheDocument();
    },
  );

  // Derivado de design.md, «Reglas de la pantalla» (Eliminar): «una clave desconocida no se pinta como botón».
  // Hoy `BotonesAcciones` rotula una clave sin rótulo con la clave misma, así que la pantalla tiene que filtrarla.
  test("tkt012b_ca16 · TC-78 · una clave que el cliente no sabe ejecutar no se pinta como botón", async () => {
    const objetivo = otraPlaneacion();
    const obras = [obraEn("PLANEACION"), objetivo];
    const baja = dobleBaja(obras, () => respuestaConHistorial(objetivo.id, ["CERRAR_OBRA", "ARCHIVAR_OBRA"]));
    const { usuario } = await abrirPantallaConTabla(obras, baja.handler);

    await pulsarEnFila(usuario, objetivo.codigo, "Eliminar");
    await usuario.click(botonConfirmar(await screen.findByRole("dialog", { name: new RegExp(objetivo.codigo) })));

    const bloqueo = await screen.findByRole("region", { name: REGION_CONFLICTO });
    expect(nombresDeBotones(bloqueo)).toEqual(["Cerrar"]);
    expect(within(bloqueo).queryByRole("button", { name: /ARCHIVAR_OBRA/ })).not.toBeInTheDocument();
  });
});

describe("TKT-012b · TC-79 · cancelar no envía nada (CA-17, rechazo)", () => {
  test("tkt012b_ca17 · TC-79 · rechazo: cancelar la confirmación de eliminar cierra el diálogo, no envía el DELETE y la obra sigue", async () => {
    const objetivo = otraPlaneacion();
    const obras = [obraEn("PLANEACION"), objetivo];
    const baja = dobleBaja(obras);
    const { usuario, lista } = await abrirPantallaConTabla(obras, baja.handler);

    await pulsarEnFila(usuario, objetivo.codigo, "Eliminar");
    const dialogo = await screen.findByRole("dialog", { name: new RegExp(objetivo.codigo) });
    await usuario.click(botonCancelar(dialogo));

    await esperarSinDialogo();
    expect(baja.recibidas).toHaveLength(0);
    expect(lista.pedidas).toHaveLength(1);
    expect(screen.queryByRole("region", { name: REGION_CONFLICTO })).not.toBeInTheDocument();
    expect(accionesDe(filaDe(objetivo.codigo))).toEqual(ACCIONES_POR_ESTADO.PLANEACION);
  });

  test("tkt012b_ca17 · TC-79 · rechazo: Escape en la confirmación de eliminar cancela como el botón", async () => {
    const objetivo = otraPlaneacion();
    const obras = [obraEn("PLANEACION"), objetivo];
    const baja = dobleBaja(obras);
    const { usuario, lista } = await abrirPantallaConTabla(obras, baja.handler);

    await pulsarEnFila(usuario, objetivo.codigo, "Eliminar");
    await screen.findByRole("dialog", { name: new RegExp(objetivo.codigo) });
    await usuario.keyboard("{Escape}");

    await esperarSinDialogo();
    expect(baja.recibidas).toHaveLength(0);
    expect(lista.pedidas).toHaveLength(1);
    expect(within(screen.getByRole("table")).getByRole("cell", { name: objetivo.codigo })).toBeInTheDocument();
  });

  test.each(
    TRANSICIONES.filter((transicion) => transicion.verbo !== "Cerrar" || transicion.desde === "ACTIVA").map(
      (transicion) => [rotuloDe(transicion), transicion] as const,
    ),
  )(
    "tkt012b_ca17 · TC-79 · rechazo: cancelar el motivo de %s no envía, no cambia la fila y al volver a abrir el campo está vacío",
    async (_rotulo, transicion) => {
      const objetivo = obraEn(transicion.desde);
      const obras = obrasConTestigo(objetivo);
      const manejador = dobleTransicion(obras, transicion.ruta, transicion.hacia);
      const { usuario, lista } = await abrirPantallaConTabla(obras, manejador.handler);

      await pulsarEnFila(usuario, objetivo.codigo, transicion.verbo);
      const dialogo = await screen.findByRole("dialog", { name: transicion.titulo });
      await usuario.type(campoMotivo(dialogo), "Un motivo que no se llegará a enviar");
      await usuario.click(botonCancelar(dialogo));

      await esperarSinDialogo();
      expect(manejador.recibidas).toHaveLength(0);
      expect(lista.pedidas).toHaveLength(1);
      expect(celdasDe(objetivo.codigo)).toContain(ETIQUETA_ESTADO[transicion.desde]);
      expect(accionesDe(filaDe(objetivo.codigo))).toEqual(ACCIONES_POR_ESTADO[transicion.desde]);

      await pulsarEnFila(usuario, objetivo.codigo, transicion.verbo);
      const reabierto = await screen.findByRole("dialog", { name: transicion.titulo });
      expect(campoMotivo(reabierto)).toHaveValue("");
    },
  );
});

describe("TKT-012b · TC-73b · otra pestaña ya cambió el estado (CA-17, CA-4, rechazo; añadido por el orquestador)", () => {
  // La lista de esta pestaña muestra `desde`; el servidor ya tiene `real`.
  const casos = [
    ["Suspender", SUSPENDER, "CERRADA"],
    ["Reactivar", REACTIVAR, "ACTIVA"],
    ["Cerrar", CERRAR_DESDE[1], "CERRADA"],
  ] as const;

  test.each(casos)(
    "tkt012b_ca17 · tkt012b_ca04 · TC-73b · %s con un 409 ESTADO_NO_PERMITE_OPERACION: el aviso va en línea dentro del diálogo con el estado actual, el motivo se conserva y al cerrar la lista se refresca",
    async (_verbo, transicion, real) => {
      const objetivo = obraEn(transicion.desde);
      const obras = obrasConTestigo(objetivo);
      const rechazada = dobleTransicionRechazada(obras, transicion.ruta, real);
      const { usuario, lista } = await abrirPantallaConTabla(obras, rechazada.handler);
      expect(celdasDe(objetivo.codigo)).toContain(ETIQUETA_ESTADO[transicion.desde]);

      await pulsarEnFila(usuario, objetivo.codigo, transicion.verbo);
      const dialogo = await screen.findByRole("dialog", { name: transicion.titulo });
      const motivo = "Lo decidimos en la junta de obra";
      await usuario.type(campoMotivo(dialogo), motivo);
      await usuario.click(botonConfirmar(dialogo));

      // El contrato completo, en línea y dentro del diálogo: tratamiento de conflicto con su código, el mensaje del
      // servidor y el estado actual del detalle.
      const conflicto = await within(dialogo).findByRole("region", { name: REGION_CONFLICTO });
      expect(conflicto).toHaveAttribute("data-estado", "bloqueado");
      expect(within(conflicto).getByText("ESTADO_NO_PERMITE_OPERACION")).toBeInTheDocument();
      expect(within(conflicto).getByText(`La obra ${objetivo.codigo} está en ${real} y no admite esta operación.`)).toBeInTheDocument();
      expect(valorEn(conflicto, "Estado")).toBe(real);
      // No es un error ni una regla de negocio: ninguna alerta en la página (el diálogo modal oculta el resto) y el servidor no ofreció acciones.
      expect(screen.queryByRole("alert", { hidden: true })).not.toBeInTheDocument();
      expect(screen.queryByText("Operación bloqueada")).not.toBeInTheDocument();
      expect(within(conflicto).queryAllByRole("button")).toHaveLength(0);
      // El diálogo sigue abierto con lo tecleado, y la petición salió una sola vez.
      expect(screen.getByRole("dialog", { name: transicion.titulo })).toBeInTheDocument();
      expect(campoMotivo(dialogo)).toHaveValue(motivo);
      expect(rechazada.recibidas).toEqual([{ obraId: objetivo.id, cuerpo: { motivo } }]);

      // Al cerrar el diálogo la lista se vuelve a pedir y la fila muestra el estado real, con las acciones que le corresponden.
      await usuario.click(botonCancelar(dialogo));
      await esperarSinDialogo();
      await waitFor(() => expect(lista.pedidas).toHaveLength(2));
      await waitFor(() => expect(celdasDe(objetivo.codigo)).toContain(ETIQUETA_ESTADO[real]));
      expect(accionesDe(filaDe(objetivo.codigo))).toEqual(ACCIONES_POR_ESTADO[real]);
      // Cancelar no envía una segunda petición.
      expect(rechazada.recibidas).toHaveLength(1);
    },
  );
});
