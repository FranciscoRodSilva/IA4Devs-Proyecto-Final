import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import type { Accion, ErrorConflictoEstado } from "@/api/errores";
import type { components as Servidor } from "@/api/generado/servidor";
import type { Rol } from "@/api/sesion";
import {
  errorConcurrencia,
  errorNoEncontrado,
  errorPermiso,
  proveedor as proveedorBase,
  tokenCsrf,
  usuarioActual,
} from "@/pruebas/cuerpos";
import { renderizarAplicacion } from "@/pruebas/render";
import { servidorPruebas } from "@/pruebas/servidor";

// TKT-032a · fila F8 · TC-F27 a TC-F36 (CA-6, CA-7, CA-8, CA-9, CA-10; D-6, D-7, D-8; mutantes M-6 y M-7). Desactivar,
// dar de baja y los rechazos de estado se prueban montados en `/compras/proveedores` dentro de la aplicación completa,
// con MSW como servidor, igual que la lista (F5), el alta (F6) y la edición (F7): la prueba no importa ningún módulo
// nuevo. Las respuestas se construyen con los tipos generados (`satisfies`); los dos 409 del catálogo
// que `pruebas/cuerpos.ts` no trae se arman aquí con el contrato completo, con la forma que manda
// `backend/cimenta/proveedores/aplicacion/proveedores.py` (`_rechazo_ordenes_pendientes`, `desactivar_proveedor`).
//
// Nombres accesibles que esta fila fija (el desarrollador los conserva; salen del boceto de `docs/08-wireframes.md` §2c):
//   botón de fila     «Desactivar <nombre>»  y  «Dar de baja <nombre>»        (ya pintados por la fila F5)
//   diálogo de motivo «Desactivar a <nombre>»  y  «Dar de baja a <nombre>»    campo «Motivo»   botón «Cancelar»
//   botón de confirmar de la baja: «Confirmar baja» (design.md, «Cómo se pinta cada rechazo»)
//   bloqueo           región «No se puede completar» (`PantallaBloqueo`), con la tabla «Órdenes pendientes»,
//                     el botón «Desactivar el proveedor» (solo si el servidor lo manda en `acciones[]`) y «Cerrar»;
//                     el valor de ESTADO_NO_PERMITE_OPERACION con el rótulo «Estado actual»
//   aviso sobre la tabla del 403, el 404, el 500 y la red: `role="alert"` con el `mensaje` y, si la hay, «Referencia: <id>»
// (asumido) El botón de confirmar de «Desactivar» no tiene nombre fijado por el boceto: se toma como el único botón del
// diálogo que no es «Cancelar», como hacen las pruebas de obras.
// (asumido) Tras un 403, un 404, un 500 o un error de red el diálogo de motivo se cierra y el aviso queda en la página
// (el diálogo es modal: con él abierto el aviso quedaría fuera del árbol de accesibilidad).
// (asumido) «Reintentar» del bloqueo por CONCURRENCIA reabre la captura de motivo de la misma operación y del mismo
// proveedor (design.md, tabla de rechazos); la prueba no fija si el motivo tecleado antes se conserva.

type Esquemas = Servidor["schemas"];
type Proveedor = Esquemas["Proveedor"];
type EstadoProveedor = Esquemas["EstadoProveedor"];
type Motivo = Esquemas["Motivo"];

const ORIGEN = globalThis.location.origin;
const RUTA_SESION = "/api/v1/sesion";
const RUTA_CSRF = "/api/v1/sesion/csrf";
const RUTA_PROVEEDORES = "/api/v1/proveedores";
const RUTA_PANTALLA = "/compras/proveedores";

const ROL_QUE_OPERA: Rol = "COMPRAS";
const REGION_BLOQUEO = "No se puede completar";
const REGION_ESPERA = "Inténtalo de nuevo";
const MENSAJE_MOTIVO_OBLIGATORIO = "El motivo es obligatorio.";
const MENSAJE_SIN_PERMISO = "Tu rol no permite esta operación.";
const MENSAJE_NO_EXISTE = "El proveedor ya no existe en el catálogo.";
const MENSAJE_INTERNO = "Error interno del servidor.";
const MOTIVO = "Entregas tardías en las últimas tres obras";

const ID_ACEROS = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d";
const ID_COPANEL = "9c2e5a41-7b3d-4f68-a1c9-3d5e7f9b1a24";
const CORRELACION_BLOQUEO = "c3d4e5f6-a7b8-4901-b2c3-d4e5f6a7b8c9";
const CORRELACION_500 = "a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d";

// Los tiempos se controlan con el reloj simulado que avanza solo: `usuario` de userEvent lo exige y ninguna prueba hace `sleep`.
beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
afterEach(() => {
  vi.useRealTimers();
});

function proveedor(cambios: Partial<Proveedor> = {}): Proveedor {
  return proveedorBase({ creado_en: "2026-11-17T15:00:00Z", ...cambios });
}

/** ACTIVO y primero de la lista: el testigo que una pantalla que actuara sobre la primera fila confundiría con el objetivo. */
function aceros(): Proveedor {
  return proveedor({ id: ID_ACEROS, nombre: "Aceros del Bajío", rfc: "ABA040312KT7", tope_consignacion: null, dia_corte: 2, dia_pago: 5 });
}

/** El proveedor que se opera: segundo de la lista, para que «la fila anterior» sea Aceros (M-7). */
function copanel(estado: EstadoProveedor = "ACTIVO"): Proveedor {
  return proveedor({ id: ID_COPANEL, estado });
}

type Operacion = {
  /** Segmento de la ruta del contrato: `POST /proveedores/{id}/<ruta>`. */
  ruta: "desactivacion" | "baja";
  verbo: "Desactivar" | "Dar de baja";
  titulo: (nombre: string) => string;
  /** El estado que el servidor deja al aceptar. */
  hacia: EstadoProveedor;
  /** El mensaje del 409 ESTADO_NO_PERMITE_OPERACION que arma el backend cuando el proveedor ya está en BAJA. */
  mensajeEstadoNoPermite: string;
};
const DESACTIVAR: Operacion = {
  ruta: "desactivacion",
  verbo: "Desactivar",
  titulo: (nombre) => `Desactivar a ${nombre}`,
  hacia: "DESACTIVADO",
  mensajeEstadoNoPermite: "El proveedor no está activo: su estado es BAJA.",
};
const DAR_DE_BAJA: Operacion = {
  ruta: "baja",
  verbo: "Dar de baja",
  titulo: (nombre) => `Dar de baja a ${nombre}`,
  hacia: "BAJA",
  mensajeEstadoNoPermite: "El proveedor ya está dado de baja: su estado es BAJA.",
};
const OPERACIONES = [
  [DESACTIVAR.verbo, DESACTIVAR],
  [DAR_DE_BAJA.verbo, DAR_DE_BAJA],
] as const;

function dobleSesion(roles: Rol[]) {
  return http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(usuarioActual(roles)));
}

function dobleCsrf() {
  return http.get(`${ORIGEN}${RUTA_CSRF}`, () => HttpResponse.json(tokenCsrf()));
}

/** GET /proveedores: lee el arreglo vivo en cada petición, así que un cambio de estado aceptado se ve en la siguiente lista. */
function dobleLista(existentes: Proveedor[]) {
  const pedidas: URL[] = [];
  const handler = http.get(`${ORIGEN}${RUTA_PROVEEDORES}`, ({ request }) => {
    const url = new URL(request.url);
    pedidas.push(url);
    const estados = url.searchParams.getAll("estado");
    const coincidentes = existentes.filter((candidato) => (estados.length === 0 ? candidato.estado === "ACTIVO" : estados.includes(candidato.estado)));
    return HttpResponse.json({
      elementos: coincidentes,
      paginacion: { pagina: 1, tamano_pagina: 50, total: coincidentes.length },
    } satisfies Esquemas["ListaProveedores"]);
  });
  return { handler, pedidas };
}

interface Recibida {
  proveedorId: string;
  /** El cuerpo tal como viajó (texto): ahí se ve que es `{ "motivo": … }` y nada más. */
  crudo: string;
  cuerpo: Motivo;
}

/** El servidor acepta: pasa al proveedor al estado de la operación en la lista viva y responde el proveedor. */
function aceptar(existentes: Proveedor[], operacion: Operacion, proveedorId: string): Response {
  const indice = existentes.findIndex((candidato) => candidato.id === proveedorId);
  const actual = existentes[indice];
  if (actual === undefined) return HttpResponse.json(errorNoEncontrado("proveedor", MENSAJE_NO_EXISTE), { status: 404 });
  const actualizado = proveedor({ ...actual, estado: operacion.hacia });
  existentes[indice] = actualizado;
  return HttpResponse.json(actualizado satisfies Proveedor);
}

/** El proveedor desapareció del servidor: lo quita de la lista viva. */
function quitar(existentes: Proveedor[], proveedorId: string) {
  const indice = existentes.findIndex((candidato) => candidato.id === proveedorId);
  if (indice >= 0) existentes.splice(indice, 1);
}

/** El proveedor ya cambió de estado por otra vía: la siguiente lista lo trae así. */
function cambiarEstado(existentes: Proveedor[], proveedorId: string, estado: EstadoProveedor) {
  const indice = existentes.findIndex((candidato) => candidato.id === proveedorId);
  const actual = existentes[indice];
  if (actual !== undefined) existentes[indice] = proveedor({ ...actual, estado });
}

type Responder = (recibida: Recibida, intento: number) => Response;

/** POST /proveedores/{proveedor_id}/{desactivacion|baja}. Guarda cada petición tal como llegó y responde lo que decide la prueba. */
function dobleOperacion(existentes: Proveedor[], operacion: Operacion, responder?: Responder) {
  const recibidas: Recibida[] = [];
  const handler = http.post(`${ORIGEN}${RUTA_PROVEEDORES}/:proveedorId/${operacion.ruta}`, async ({ request, params }) => {
    const crudo = await request.text();
    const recibida: Recibida = { proveedorId: String(params.proveedorId), crudo, cuerpo: JSON.parse(crudo) as Motivo };
    recibidas.push(recibida);
    return responder === undefined ? aceptar(existentes, operacion, recibida.proveedorId) : responder(recibida, recibidas.length);
  });
  return { handler, recibidas };
}

const ORDENES_PENDIENTES = [
  { id: "5c4b3a29-1807-4f6e-9d5c-4b3a29180716", folio: "OC-AP05825-0017", estado: "PARCIAL" },
  { id: "6d5c4b3a-2918-4a7f-8e6d-5c4b3a291807", folio: "OC-AP05825-0021", estado: "ABIERTA" },
] as const;

type VarianteOrdenes = "ACTIVO" | "ACTIVO_SIN_ACCIONES" | "DESACTIVADO";

/**
 * El 409 PROVEEDOR_CON_ORDENES_ABIERTAS de `dar_baja_proveedor`, con el contrato completo y la forma exacta del backend:
 * `detalle.ordenes` con `id`, `folio` y `estado`; con el proveedor ACTIVO manda la acción `DESACTIVAR_PROVEEDOR` hacia la
 * desactivación de ESE proveedor; con el proveedor DESACTIVADO manda `acciones: []`. `ACTIVO_SIN_ACCIONES` es el mismo
 * rechazo de un ACTIVO pero sin acciones: lo que una pantalla que cablea el botón (M-6) ofrecería de más.
 */
function errorOrdenesAbiertas(sujeto: Proveedor, variante: VarianteOrdenes): ErrorConflictoEstado {
  const conAccion = variante === "ACTIVO";
  const acciones: Accion[] = conAccion
    ? [{ clave: "DESACTIVAR_PROVEEDOR", metodo: "POST", ruta: `${RUTA_PROVEEDORES}/${sujeto.id}/desactivacion` }]
    : [];
  return {
    tipo: "CONFLICTO",
    codigo: "PROVEEDOR_CON_ORDENES_ABIERTAS",
    mensaje:
      variante === "DESACTIVADO"
        ? `${sujeto.nombre} tiene 2 órdenes pendientes de recibir y ya está desactivado; la baja procede cuando esas órdenes se reciban completas o se cancelen.`
        : `${sujeto.nombre} tiene 2 órdenes pendientes de recibir; se puede desactivar para órdenes nuevas conservando las existentes.`,
    detalle: { ordenes: ORDENES_PENDIENTES.map((orden) => ({ ...orden })) },
    acciones,
    correlacion_id: CORRELACION_BLOQUEO,
  } satisfies ErrorConflictoEstado;
}

/** El 409 ESTADO_NO_PERMITE_OPERACION de `desactivar_proveedor` y `dar_baja_proveedor`: `detalle.estado_actual` y sin acciones. */
function errorEstadoNoPermite(mensaje: string, estadoActual: EstadoProveedor): ErrorConflictoEstado {
  return {
    tipo: "CONFLICTO",
    codigo: "ESTADO_NO_PERMITE_OPERACION",
    mensaje,
    detalle: { estado_actual: estadoActual },
    acciones: [],
    correlacion_id: CORRELACION_BLOQUEO,
  } satisfies ErrorConflictoEstado;
}

interface OpcionesPantalla {
  proveedores?: Proveedor[];
  operaciones?: ReturnType<typeof dobleOperacion>[];
  roles?: Rol[];
}

/** Monta la aplicación en `/compras/proveedores` con la sesión del rol, espera la sesión y la tabla, y devuelve la lista doblada. */
async function abrirPantallaConTabla({ proveedores = [aceros(), copanel()], operaciones = [], roles = [ROL_QUE_OPERA] }: OpcionesPantalla = {}) {
  const lista = dobleLista(proveedores);
  servidorPruebas.use(dobleSesion(roles), dobleCsrf(), lista.handler, ...operaciones.map((operacion) => operacion.handler));
  const aplicacion = renderizarAplicacion(RUTA_PANTALLA);
  await screen.findByText(/Rosa Villanueva/);
  await screen.findByRole("table");
  return { ...aplicacion, lista };
}

type Usuario = ReturnType<typeof renderizarAplicacion>["usuario"];

/** La fila de un proveedor: la tabla de la pantalla y la del bloqueo conviven, así que se busca por el nombre de la fila. */
function filaDe(nombre: string, opciones: { hidden?: boolean } = {}) {
  return screen.getByRole("row", { name: new RegExp(`^${nombre}`), ...opciones });
}

function celdasDe(nombre: string): string[] {
  return within(filaDe(nombre, { hidden: true }))
    .getAllByRole("cell", { hidden: true })
    .map((celda) => celda.textContent.trim());
}

/** Los botones de una fila por su verbo («Editar», «Desactivar», «Dar de baja»): el `aria-label` sin el nombre del proveedor. */
function accionesDe(nombre: string): string[] {
  return within(filaDe(nombre))
    .queryAllByRole("button")
    .map((boton) => (boton.getAttribute("aria-label") ?? boton.textContent).replace(` ${nombre}`, "").trim());
}

async function filtrar(usuario: Usuario, etiqueta: "Activos" | "Desactivados" | "Dados de baja" | "Todos") {
  await usuario.selectOptions(screen.getByRole("combobox", { name: "Estado" }), etiqueta);
}

async function pulsarEnFila(usuario: Usuario, operacion: Operacion, nombre: string) {
  await usuario.click(screen.getByRole("button", { name: `${operacion.verbo} ${nombre}` }));
}

async function abrirMotivo(usuario: Usuario, operacion: Operacion, nombre: string) {
  await pulsarEnFila(usuario, operacion, nombre);
  return screen.findByRole("dialog", { name: operacion.titulo(nombre) });
}

function campoMotivo(dialogo: HTMLElement) {
  return within(dialogo).getByRole("textbox", { name: "Motivo" });
}

/** El botón de confirmar: el único del diálogo que no es «Cancelar». */
function botonConfirmar(dialogo: HTMLElement): HTMLElement {
  const botones = within(dialogo)
    .getAllByRole("button")
    .filter((boton) => boton.textContent.trim() !== "Cancelar");
  expect(botones).toHaveLength(1);
  const [confirmar] = botones;
  if (confirmar === undefined) throw new Error("El diálogo no tiene botón de confirmar.");
  return confirmar;
}

/** Abre el motivo de la operación sobre un proveedor, escribe el motivo y confirma. */
async function operarConMotivo(usuario: Usuario, operacion: Operacion, nombre: string, motivo: string = MOTIVO) {
  const dialogo = await abrirMotivo(usuario, operacion, nombre);
  await usuario.type(campoMotivo(dialogo), motivo);
  await usuario.click(botonConfirmar(dialogo));
  return dialogo;
}

async function esperarSinDialogo() {
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
}

function nombresDeBotones(region: HTMLElement): string[] {
  return within(region)
    .queryAllByRole("button")
    .map((boton) => boton.textContent.trim());
}

/** El valor de un rótulo del detalle de un rechazo (`dt` y su `dd`), dentro de su región. */
function valorEn(region: HTMLElement, rotulo: string): string {
  const termino = within(region).getByText(rotulo, { selector: "dt" });
  return termino.nextElementSibling?.textContent.trim() ?? "";
}

/** El bloqueo `409`: la región del contrato, con su tratamiento propio y sin diálogo ni alerta de error. */
async function esperarBloqueo(nombre: string = REGION_BLOQUEO) {
  const bloqueo = await screen.findByRole("region", { name: nombre });
  expect(bloqueo).toHaveAttribute("data-estado", "bloqueado");
  return bloqueo;
}

describe("TKT-032a · TC-F27 · desactivar con motivo (CA-6, HDU-004 esc. 12)", () => {
  test("hdu004_esc12 · TC-F27 · «Desactivar CoPanel» pide el motivo y, al confirmar, envía POST …/desactivacion con { motivo } al proveedor de la fila", async () => {
    const existentes = [aceros(), copanel()];
    const desactivacion = dobleOperacion(existentes, DESACTIVAR);
    const { usuario } = await abrirPantallaConTabla({ proveedores: existentes, operaciones: [desactivacion] });

    const dialogo = await abrirMotivo(usuario, DESACTIVAR, "CoPanel");
    // Abrir el motivo no envía nada: la petición sale al confirmar.
    expect(desactivacion.recibidas).toHaveLength(0);
    await usuario.type(campoMotivo(dialogo), MOTIVO);
    await usuario.click(botonConfirmar(dialogo));

    await esperarSinDialogo();
    // Cuerpo crudo: exactamente { "motivo": … }, para el proveedor de la fila y no para la primera.
    expect(desactivacion.recibidas).toEqual([
      { proveedorId: ID_COPANEL, crudo: JSON.stringify({ motivo: MOTIVO }), cuerpo: { motivo: MOTIVO } },
    ]);
  });

  test("hdu004_esc12 · TC-F27 · la lista se vuelve a pedir: el proveedor sale del filtro por omisión y aparece «Desactivado» al filtrar «Desactivados»", async () => {
    const existentes = [aceros(), copanel()];
    const desactivacion = dobleOperacion(existentes, DESACTIVAR);
    const { usuario, lista } = await abrirPantallaConTabla({ proveedores: existentes, operaciones: [desactivacion] });
    expect(lista.pedidas).toHaveLength(1);
    expect(accionesDe("CoPanel")).toEqual(["Editar", "Desactivar", "Dar de baja"]);

    await operarConMotivo(usuario, DESACTIVAR, "CoPanel");

    await esperarSinDialogo();
    await waitFor(() => expect(lista.pedidas).toHaveLength(2));
    await waitFor(() => expect(screen.queryByRole("row", { name: /^CoPanel/ })).not.toBeInTheDocument());
    // El testigo no cambia, y no hay rechazo alguno.
    expect(celdasDe("Aceros del Bajío")).toContain("Activo");
    expect(screen.queryByRole("region", { name: REGION_BLOQUEO })).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();

    await filtrar(usuario, "Desactivados");
    await screen.findByRole("row", { name: /^CoPanel/ });
    expect(celdasDe("CoPanel")).toContain("Desactivado");
    // D-7: un desactivado ya no ofrece «Desactivar», pero sí «Editar» y «Dar de baja».
    expect(accionesDe("CoPanel")).toEqual(["Editar", "Dar de baja"]);
  });
});

describe("TKT-032a · TC-F28 · desactivar sin motivo (CA-6, rechazo)", () => {
  test.each([
    ["vacío", ""],
    ["solo espacios", "   "],
  ] as const)(
    "hdu004_esc12 · TC-F28 · rechazo: desactivar sin motivo (%s) no envía y el campo señala el error",
    async (_descripcion, escrito) => {
      const existentes = [aceros(), copanel()];
      const desactivacion = dobleOperacion(existentes, DESACTIVAR);
      const { usuario, lista } = await abrirPantallaConTabla({ proveedores: existentes, operaciones: [desactivacion] });
      const dialogo = await abrirMotivo(usuario, DESACTIVAR, "CoPanel");

      if (escrito !== "") await usuario.type(campoMotivo(dialogo), escrito);
      await usuario.click(botonConfirmar(dialogo));

      expect(await within(dialogo).findByText(MENSAJE_MOTIVO_OBLIGATORIO)).toBeInTheDocument();
      expect(campoMotivo(dialogo)).toHaveAttribute("aria-invalid", "true");
      // Nada sale: ni la petición ni una nueva consulta de la lista, y el diálogo sigue abierto para corregir.
      expect(desactivacion.recibidas).toHaveLength(0);
      expect(lista.pedidas).toHaveLength(1);
      expect(screen.getByRole("dialog", { name: DESACTIVAR.titulo("CoPanel") })).toBeInTheDocument();
      expect(celdasDe("CoPanel")).toContain("Activo");
    },
  );
});

describe("TKT-032a · cierre de la captura de motivo sin confirmar (CA-6, CA-7, borde)", () => {
  test.each(OPERACIONES)(
    "tkt032a_estado · cancelar · %s: «Cancelar» cierra la captura, no envía nada y, al reabrir, el motivo está vacío",
    async (_verbo, operacion) => {
      const existentes = [aceros(), copanel()];
      const doble = dobleOperacion(existentes, operacion);
      const { usuario, lista } = await abrirPantallaConTabla({ proveedores: existentes, operaciones: [doble] });
      const dialogo = await abrirMotivo(usuario, operacion, "CoPanel");
      await usuario.type(campoMotivo(dialogo), MOTIVO);
      expect(campoMotivo(dialogo)).toHaveValue(MOTIVO);

      await usuario.click(within(dialogo).getByRole("button", { name: "Cancelar" }));

      await esperarSinDialogo();
      expect(doble.recibidas).toHaveLength(0);
      expect(lista.pedidas).toHaveLength(1);
      expect(celdasDe("CoPanel")).toContain("Activo");
      const reabierto = await abrirMotivo(usuario, operacion, "CoPanel");
      expect(campoMotivo(reabierto)).toHaveValue("");
      expect(doble.recibidas).toHaveLength(0);
    },
  );
});

describe("TKT-032a · TC-F29 · dar de baja sin órdenes pendientes (CA-7, HDU-004 esc. 13)", () => {
  test.each([
    ["ACTIVO", "ACTIVO", "Activos"],
    ["DESACTIVADO", "DESACTIVADO", "Desactivados"],
  ] as const)(
    "hdu004_esc13 · TC-F29 · un proveedor %s se da de baja con motivo: envía POST …/baja con { motivo }, sale del filtro y, al filtrar «Dados de baja», su fila no lleva ninguna acción",
    async (_descripcion, estado, filtro) => {
      const existentes = [aceros(), copanel(estado)];
      const baja = dobleOperacion(existentes, DAR_DE_BAJA);
      const { usuario, lista } = await abrirPantallaConTabla({ proveedores: existentes, operaciones: [baja] });
      if (filtro !== "Activos") {
        await filtrar(usuario, filtro);
        await screen.findByRole("row", { name: /^CoPanel/ });
      }
      const antes = lista.pedidas.length;

      const dialogo = await abrirMotivo(usuario, DAR_DE_BAJA, "CoPanel");
      // El boceto: el botón de confirmar de la baja se llama «Confirmar baja».
      expect(botonConfirmar(dialogo)).toHaveAccessibleName("Confirmar baja");
      expect(baja.recibidas).toHaveLength(0);
      await usuario.type(campoMotivo(dialogo), MOTIVO);
      await usuario.click(botonConfirmar(dialogo));

      await esperarSinDialogo();
      expect(baja.recibidas).toEqual([
        { proveedorId: ID_COPANEL, crudo: JSON.stringify({ motivo: MOTIVO }), cuerpo: { motivo: MOTIVO } },
      ]);
      // La lista se vuelve a pedir: el estado nuevo es el del servidor y el proveedor ya no está en el filtro anterior.
      await waitFor(() => expect(lista.pedidas).toHaveLength(antes + 1));
      await waitFor(() => expect(screen.queryByRole("row", { name: /^CoPanel/ })).not.toBeInTheDocument());
      expect(screen.queryByRole("region", { name: REGION_BLOQUEO })).not.toBeInTheDocument();

      await filtrar(usuario, "Dados de baja");
      await screen.findByRole("row", { name: /^CoPanel/ });
      expect(celdasDe("CoPanel")).toContain("Baja");
      // CA-7: sobre una baja no se ofrece ninguna acción más.
      expect(within(filaDe("CoPanel")).queryAllByRole("button")).toHaveLength(0);
    },
  );
});

describe("TKT-032a · TC-F30 · dar de baja sin motivo (CA-7, rechazo)", () => {
  test.each([
    ["vacío", ""],
    ["solo espacios", "   "],
  ] as const)(
    "hdu004_esc13 · TC-F30 · rechazo: dar de baja sin motivo (%s) no envía y el campo señala el error",
    async (_descripcion, escrito) => {
      const existentes = [aceros(), copanel()];
      const baja = dobleOperacion(existentes, DAR_DE_BAJA);
      const { usuario, lista } = await abrirPantallaConTabla({ proveedores: existentes, operaciones: [baja] });
      const dialogo = await abrirMotivo(usuario, DAR_DE_BAJA, "CoPanel");

      if (escrito !== "") await usuario.type(campoMotivo(dialogo), escrito);
      await usuario.click(botonConfirmar(dialogo));

      expect(await within(dialogo).findByText(MENSAJE_MOTIVO_OBLIGATORIO)).toBeInTheDocument();
      expect(campoMotivo(dialogo)).toHaveAttribute("aria-invalid", "true");
      expect(baja.recibidas).toHaveLength(0);
      expect(lista.pedidas).toHaveLength(1);
      expect(screen.getByRole("dialog", { name: DAR_DE_BAJA.titulo("CoPanel") })).toBeInTheDocument();
      expect(celdasDe("CoPanel")).toContain("Activo");
    },
  );
});

describe("TKT-032a · TC-F31 · baja con órdenes pendientes, proveedor ACTIVO (CA-8, HDU-004 esc. 12, rechazo)", () => {
  /** Da de baja a CoPanel (segundo de la lista) y devuelve el 409 con sus órdenes y la acción del contrato. */
  async function intentarBajaConOrdenes(variante: VarianteOrdenes = "ACTIVO") {
    const existentes = [aceros(), copanel(variante === "DESACTIVADO" ? "DESACTIVADO" : "ACTIVO")];
    const rechazo = errorOrdenesAbiertas(copanel(), variante);
    const baja = dobleOperacion(existentes, DAR_DE_BAJA, () => HttpResponse.json(rechazo, { status: 409 }));
    const pantalla = await abrirPantallaConTabla({ proveedores: existentes, operaciones: [baja] });
    if (variante === "DESACTIVADO") {
      await filtrar(pantalla.usuario, "Desactivados");
      await screen.findByRole("row", { name: /^CoPanel/ });
    }
    await operarConMotivo(pantalla.usuario, DAR_DE_BAJA, "CoPanel");
    return { ...pantalla, baja };
  }

  test("hdu004_esc12 · TC-F31 · el 409 se pinta como bloqueo con su código, el mensaje del servidor, las órdenes (folio y estado) y la acción tomada de acciones[]", async () => {
    const { baja } = await intentarBajaConOrdenes();

    const bloqueo = await esperarBloqueo();
    expect(within(bloqueo).getByText("PROVEEDOR_CON_ORDENES_ABIERTAS")).toBeInTheDocument();
    expect(
      within(bloqueo).getByText(
        "CoPanel tiene 2 órdenes pendientes de recibir; se puede desactivar para órdenes nuevas conservando las existentes.",
      ),
    ).toBeInTheDocument();
    // Las órdenes, en su tabla, con su folio y su estado y sin identificadores internos.
    const tabla = within(bloqueo).getByRole("table", { name: "Órdenes pendientes" });
    expect(within(tabla).getAllByRole("columnheader").map((encabezado) => encabezado.textContent.trim())).toEqual(["Folio", "Estado"]);
    const filas = within(tabla).getAllByRole("row").slice(1);
    expect(filas.map((fila) => within(fila).getAllByRole("cell").map((celda) => celda.textContent.trim()))).toEqual([
      ["OC-AP05825-0017", "PARCIAL"],
      ["OC-AP05825-0021", "ABIERTA"],
    ]);
    expect(within(bloqueo).queryByText(ORDENES_PENDIENTES[0].id)).not.toBeInTheDocument();
    // La acción viene del contrato, rotulada y antes de «Cerrar»; la clave cruda no se pinta.
    expect(nombresDeBotones(bloqueo)).toEqual(["Desactivar el proveedor", "Cerrar"]);
    expect(within(bloqueo).queryByText("DESACTIVAR_PROVEEDOR")).not.toBeInTheDocument();
    expect(within(bloqueo).getByText(`Referencia: ${CORRELACION_BLOQUEO}`)).toBeInTheDocument();
    // No es un error: ni alerta, ni cabecera de bloqueo de regla, ni diálogo. La petición salió una sola vez, para CoPanel.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText("Operación bloqueada")).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(baja.recibidas).toEqual([
      { proveedorId: ID_COPANEL, crudo: JSON.stringify({ motivo: MOTIVO }), cuerpo: { motivo: MOTIVO } },
    ]);
  });

  test("hdu004_esc12 · TC-F31 · el proveedor sigue ACTIVO en la lista, con sus acciones, y «Cerrar» quita el bloqueo sin enviar nada", async () => {
    const { usuario, baja } = await intentarBajaConOrdenes();
    const bloqueo = await esperarBloqueo();

    expect(celdasDe("CoPanel")).toContain("Activo");
    expect(accionesDe("CoPanel")).toEqual(["Editar", "Desactivar", "Dar de baja"]);
    expect(celdasDe("Aceros del Bajío")).toContain("Activo");

    await usuario.click(within(bloqueo).getByRole("button", { name: "Cerrar" }));

    await waitFor(() => expect(screen.queryByRole("region", { name: REGION_BLOQUEO })).not.toBeInTheDocument());
    expect(baja.recibidas).toHaveLength(1);
    expect(celdasDe("CoPanel")).toContain("Activo");
  });
});

describe("TKT-032a · TC-F32 · desde el bloqueo se desactiva al proveedor bloqueado, no a otro (CA-8, M-7)", () => {
  /** CoPanel, el bloqueado, es el SEGUNDO de la lista; Aceros, el primero, es el testigo. */
  async function llegarAlBloqueo() {
    const existentes = [aceros(), copanel()];
    const rechazo = errorOrdenesAbiertas(copanel(), "ACTIVO");
    const baja = dobleOperacion(existentes, DAR_DE_BAJA, () => HttpResponse.json(rechazo, { status: 409 }));
    const desactivacion = dobleOperacion(existentes, DESACTIVAR);
    const pantalla = await abrirPantallaConTabla({ proveedores: existentes, operaciones: [baja, desactivacion] });
    await operarConMotivo(pantalla.usuario, DAR_DE_BAJA, "CoPanel");
    const bloqueo = await esperarBloqueo();
    return { ...pantalla, bloqueo, baja, desactivacion };
  }

  test("hdu004_esc12 · TC-F32 · «Desactivar el proveedor» abre la captura de motivo de CoPanel, nombrándolo, y no envía nada todavía", async () => {
    const { usuario, bloqueo, desactivacion } = await llegarAlBloqueo();

    await usuario.click(within(bloqueo).getByRole("button", { name: "Desactivar el proveedor" }));

    const dialogo = await screen.findByRole("dialog", { name: DESACTIVAR.titulo("CoPanel") });
    // Nombra al proveedor bloqueado y no al de la primera fila.
    expect(dialogo).not.toHaveAccessibleName(/Aceros/);
    expect(screen.queryByRole("dialog", { name: DESACTIVAR.titulo("Aceros del Bajío") })).not.toBeInTheDocument();
    // Pulsar la acción pide el motivo; no desactiva por sí sola.
    expect(desactivacion.recibidas).toHaveLength(0);
    expect(campoMotivo(dialogo)).toHaveValue("");
  });

  test("tkt032a_estado · TC-F32 · comportamiento actual (no una decisión nueva): al abrir «Desactivar el proveedor» el bloqueo desaparece y no vuelve al cancelar la captura de motivo", async () => {
    const { usuario, bloqueo, desactivacion } = await llegarAlBloqueo();

    await usuario.click(within(bloqueo).getByRole("button", { name: "Desactivar el proveedor" }));
    const dialogo = await screen.findByRole("dialog", { name: DESACTIVAR.titulo("CoPanel") });
    // Con el diálogo abierto la página queda fuera del árbol de accesibilidad: el bloqueo se busca también ahí.
    expect(screen.queryByRole("region", { name: REGION_BLOQUEO, hidden: true })).not.toBeInTheDocument();

    await usuario.click(within(dialogo).getByRole("button", { name: "Cancelar" }));

    await esperarSinDialogo();
    expect(screen.queryByRole("region", { name: REGION_BLOQUEO, hidden: true })).not.toBeInTheDocument();
    expect(desactivacion.recibidas).toHaveLength(0);
    expect(celdasDe("CoPanel")).toContain("Activo");
  });

  test("hdu004_esc12 · TC-F32 · al confirmar, el POST …/desactivacion va al id de CoPanel con el motivo, el bloqueo se cierra y la lista se recarga sin él", async () => {
    const { usuario, bloqueo, lista, baja, desactivacion } = await llegarAlBloqueo();
    const antes = lista.pedidas.length;

    await usuario.click(within(bloqueo).getByRole("button", { name: "Desactivar el proveedor" }));
    const dialogo = await screen.findByRole("dialog", { name: DESACTIVAR.titulo("CoPanel") });
    const motivo = "Seguimos con sus órdenes abiertas, sin pedidos nuevos";
    await usuario.type(campoMotivo(dialogo), motivo);
    await usuario.click(botonConfirmar(dialogo));

    await esperarSinDialogo();
    // M-7: el proveedor objetivo se conserva. Ni una sola petición fue a Aceros, y la baja no se repitió.
    expect(desactivacion.recibidas).toEqual([
      { proveedorId: ID_COPANEL, crudo: JSON.stringify({ motivo }), cuerpo: { motivo } },
    ]);
    expect(baja.recibidas).toHaveLength(1);
    // El bloqueo se cierra y la lista se vuelve a pedir: CoPanel ya no está entre los activos y Aceros sí.
    await waitFor(() => expect(screen.queryByRole("region", { name: REGION_BLOQUEO })).not.toBeInTheDocument());
    await waitFor(() => expect(lista.pedidas).toHaveLength(antes + 1));
    await waitFor(() => expect(screen.queryByRole("row", { name: /^CoPanel/ })).not.toBeInTheDocument());
    expect(celdasDe("Aceros del Bajío")).toContain("Activo");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("TKT-032a · TC-F33 · baja con órdenes pendientes, proveedor DESACTIVADO (CA-8, rechazo)", () => {
  async function intentarBajaDeUnDesactivado(acciones: VarianteOrdenes) {
    const existentes = [aceros(), copanel("DESACTIVADO")];
    const rechazo = errorOrdenesAbiertas(copanel("DESACTIVADO"), acciones);
    const baja = dobleOperacion(existentes, DAR_DE_BAJA, () => HttpResponse.json(rechazo, { status: 409 }));
    const pantalla = await abrirPantallaConTabla({ proveedores: existentes, operaciones: [baja] });
    await filtrar(pantalla.usuario, "Desactivados");
    await screen.findByRole("row", { name: /^CoPanel/ });
    await operarConMotivo(pantalla.usuario, DAR_DE_BAJA, "CoPanel");
    return { ...pantalla, baja };
  }

  test("hdu004_esc12 · TC-F33 · el bloqueo lista las órdenes con el mensaje del servidor y NO ofrece desactivar: solo «Cerrar»", async () => {
    // El servidor, con el proveedor ya DESACTIVADO, no manda ninguna acción: la pantalla solo ofrece «Cerrar».
    await intentarBajaDeUnDesactivado("DESACTIVADO");
    const bloqueo = await esperarBloqueo();
    expect(within(bloqueo).getByText("PROVEEDOR_CON_ORDENES_ABIERTAS")).toBeInTheDocument();
    expect(
      within(bloqueo).getByText(
        "CoPanel tiene 2 órdenes pendientes de recibir y ya está desactivado; la baja procede cuando esas órdenes se reciban completas o se cancelen.",
      ),
    ).toBeInTheDocument();
    const tabla = within(bloqueo).getByRole("table", { name: "Órdenes pendientes" });
    expect(within(tabla).getByRole("cell", { name: "OC-AP05825-0017" })).toBeInTheDocument();
    expect(within(tabla).getByRole("cell", { name: "PARCIAL" })).toBeInTheDocument();
    expect(within(tabla).getByRole("cell", { name: "OC-AP05825-0021" })).toBeInTheDocument();
    expect(within(tabla).getByRole("cell", { name: "ABIERTA" })).toBeInTheDocument();
    expect(nombresDeBotones(bloqueo)).toEqual(["Cerrar"]);
    expect(screen.queryByRole("button", { name: "Desactivar el proveedor" })).not.toBeInTheDocument();
  });

  test("hdu004_esc12 · TC-F33 · «Cerrar» quita el bloqueo y el proveedor sigue DESACTIVADO, con «Editar» y «Dar de baja»", async () => {
    const { usuario, baja } = await intentarBajaDeUnDesactivado("DESACTIVADO");
    const bloqueo = await esperarBloqueo();

    await usuario.click(within(bloqueo).getByRole("button", { name: "Cerrar" }));

    await waitFor(() => expect(screen.queryByRole("region", { name: REGION_BLOQUEO })).not.toBeInTheDocument());
    expect(baja.recibidas).toHaveLength(1);
    expect(celdasDe("CoPanel")).toContain("Desactivado");
    expect(accionesDe("CoPanel")).toEqual(["Editar", "Dar de baja"]);
  });
});

describe("TKT-032a · TC-F34 · la pantalla no cablea la acción del bloqueo (CA-8, M-6, rechazo)", () => {
  test("hdu004_esc12 · TC-F34 · con PROVEEDOR_CON_ORDENES_ABIERTAS simulado SIN acciones y proveedor ACTIVO, no aparece «Desactivar el proveedor»", async () => {
    const existentes = [aceros(), copanel()];
    const rechazo = errorOrdenesAbiertas(copanel(), "ACTIVO_SIN_ACCIONES");
    const baja = dobleOperacion(existentes, DAR_DE_BAJA, () => HttpResponse.json(rechazo, { status: 409 }));
    const { usuario } = await abrirPantallaConTabla({ proveedores: existentes, operaciones: [baja] });

    await operarConMotivo(usuario, DAR_DE_BAJA, "CoPanel");

    // El proveedor está ACTIVO y el mensaje es el de un ACTIVO: solo falta lo que el servidor no mandó.
    expect(celdasDe("CoPanel")).toContain("Activo");
    const bloqueo = await esperarBloqueo();
    expect(within(bloqueo).getByText("PROVEEDOR_CON_ORDENES_ABIERTAS")).toBeInTheDocument();
    expect(within(bloqueo).getByRole("table", { name: "Órdenes pendientes" })).toBeInTheDocument();
    expect(nombresDeBotones(bloqueo)).toEqual(["Cerrar"]);
    expect(screen.queryByRole("button", { name: "Desactivar el proveedor" })).not.toBeInTheDocument();
  });
});

describe("TKT-032a · TC-F35 · otro usuario cambió el estado (CA-10, HDU-004 esc. 12, rechazo)", () => {
  /** La lista de esta pestaña tiene a CoPanel ACTIVO; en el servidor ya está en BAJA. */
  function operacionRechazada(existentes: Proveedor[], operacion: Operacion) {
    return dobleOperacion(existentes, operacion, () => {
      cambiarEstado(existentes, ID_COPANEL, "BAJA");
      return HttpResponse.json(errorEstadoNoPermite(operacion.mensajeEstadoNoPermite, "BAJA"), { status: 409 });
    });
  }

  test.each(OPERACIONES)(
    "hdu004_esc12 · TC-F35 · %s sobre la fila vieja: el 409 ESTADO_NO_PERMITE_OPERACION se pinta como bloqueo con el mensaje del servidor y «Estado actual» rotulado, no la clave cruda",
    async (_verbo, operacion) => {
      const existentes = [aceros(), copanel()];
      const rechazada = operacionRechazada(existentes, operacion);
      const { usuario } = await abrirPantallaConTabla({ proveedores: existentes, operaciones: [rechazada] });

      await operarConMotivo(usuario, operacion, "CoPanel");

      // El contrato completo: tratamiento de conflicto con su código, el mensaje del servidor y el estado actual del detalle.
      const bloqueo = await esperarBloqueo();
      expect(within(bloqueo).getByText("ESTADO_NO_PERMITE_OPERACION")).toBeInTheDocument();
      expect(within(bloqueo).getByText(operacion.mensajeEstadoNoPermite)).toBeInTheDocument();
      expect(valorEn(bloqueo, "Estado actual")).toBe("BAJA");
      expect(within(bloqueo).queryByText("estado_actual")).not.toBeInTheDocument();
      expect(within(bloqueo).getByText(`Referencia: ${CORRELACION_BLOQUEO}`)).toBeInTheDocument();
      // No es una regla ni un error, y el servidor no ofreció acciones: solo «Cerrar».
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      expect(screen.queryByText("Operación bloqueada")).not.toBeInTheDocument();
      expect(nombresDeBotones(bloqueo)).toEqual(["Cerrar"]);
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
      expect(rechazada.recibidas).toEqual([
        { proveedorId: ID_COPANEL, crudo: JSON.stringify({ motivo: MOTIVO }), cuerpo: { motivo: MOTIVO } },
      ]);
    },
  );

  test.each(OPERACIONES)(
    "hdu004_esc12 · TC-F35 · %s sobre la fila vieja: la lista se vuelve a pedir y la fila vuelve con su estado actual, «Baja» y sin acciones",
    async (_verbo, operacion) => {
      const existentes = [aceros(), copanel()];
      const rechazada = operacionRechazada(existentes, operacion);
      const { usuario, lista } = await abrirPantallaConTabla({ proveedores: existentes, operaciones: [rechazada] });
      expect(lista.pedidas).toHaveLength(1);

      await operarConMotivo(usuario, operacion, "CoPanel");

      await esperarBloqueo();
      await waitFor(() => expect(lista.pedidas).toHaveLength(2));
      // Con el estado actual (BAJA) CoPanel ya no pertenece al filtro por omisión…
      await waitFor(() => expect(screen.queryByRole("row", { name: /^CoPanel/ })).not.toBeInTheDocument());
      expect(celdasDe("Aceros del Bajío")).toContain("Activo");
      // …y con «Todos» vuelve como «Baja», sin ninguna acción.
      await filtrar(usuario, "Todos");
      await screen.findByRole("row", { name: /^CoPanel/ });
      expect(celdasDe("CoPanel")).toContain("Baja");
      expect(within(filaDe("CoPanel")).queryAllByRole("button")).toHaveLength(0);
      // No hubo una segunda petición de la operación.
      expect(rechazada.recibidas).toHaveLength(1);
    },
  );
});

describe("TKT-032a · TC-F36 · 403, 404, 500, red y espera de bloqueo (CA-9, CA-10, rechazo)", () => {
  /** Opera sobre CoPanel (segundo de la lista) con una respuesta del servidor que decide la prueba. */
  async function operarRechazada(operacion: Operacion, responder: (existentes: Proveedor[]) => Response) {
    const existentes = [aceros(), copanel()];
    const doble = dobleOperacion(existentes, operacion, () => responder(existentes));
    const pantalla = await abrirPantallaConTabla({ proveedores: existentes, operaciones: [doble] });
    await operarConMotivo(pantalla.usuario, operacion, "CoPanel");
    return { ...pantalla, existentes, doble };
  }

  /** El aviso sobre la tabla: una alerta, nunca el tratamiento de bloqueo. */
  async function esperarAviso() {
    const aviso = await screen.findByRole("alert");
    expect(screen.queryByRole("region", { name: REGION_BLOQUEO })).not.toBeInTheDocument();
    expect(screen.queryByText("Operación bloqueada")).not.toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    return aviso;
  }

  test.each(OPERACIONES)(
    "tkt032a_estado · TC-F36 · %s con un 403: pinta el mensaje del servidor sobre la tabla, sin cifras ni tratamiento de bloqueo, y el proveedor no cambia",
    async (_verbo, operacion) => {
      const rechazo = { ...errorPermiso("ROL_INSUFICIENTE"), mensaje: MENSAJE_SIN_PERMISO };
      const { doble } = await operarRechazada(operacion, () => HttpResponse.json(rechazo, { status: 403 }));

      const aviso = await esperarAviso();
      // Se pinta el mensaje del servidor y no uno propio (D-6).
      expect(within(aviso).getByText(MENSAJE_SIN_PERMISO)).toBeInTheDocument();
      expect(within(aviso).queryByText(/disponible|excedente|presupuestado/i)).not.toBeInTheDocument();
      expect(screen.queryByText("No tienes permiso para esta operación.")).not.toBeInTheDocument();
      expect(doble.recibidas).toHaveLength(1);
      expect(celdasDe("CoPanel")).toContain("Activo");
    },
  );

  test.each(OPERACIONES)(
    "tkt032a_estado · TC-F36 · %s con un 404: avisa con el mensaje del servidor y su referencia, y la lista se vuelve a pedir sin el proveedor desaparecido",
    async (_verbo, operacion) => {
      const rechazo = errorNoEncontrado("proveedor", MENSAJE_NO_EXISTE);
      const { lista, doble } = await operarRechazada(operacion, (existentes) => {
        // El proveedor desapareció entre la lista y la operación: la siguiente lista ya no lo trae.
        quitar(existentes, ID_COPANEL);
        return HttpResponse.json(rechazo, { status: 404 });
      });

      const aviso = await esperarAviso();
      expect(within(aviso).getByText(MENSAJE_NO_EXISTE)).toBeInTheDocument();
      expect(within(aviso).getByText(`Referencia: ${rechazo.correlacion_id}`)).toBeInTheDocument();
      expect(doble.recibidas).toHaveLength(1);
      // La lista se recarga y el proveedor desaparecido ya no está; el otro sigue.
      await waitFor(() => expect(lista.pedidas).toHaveLength(2));
      await waitFor(() => expect(screen.queryByRole("row", { name: /^CoPanel/ })).not.toBeInTheDocument());
      expect(celdasDe("Aceros del Bajío")).toContain("Activo");
    },
  );

  test.each(OPERACIONES)(
    "tkt032a_estado · TC-F36 · %s con un 500: avisa con el mensaje y la referencia del servidor y la pantalla no cae",
    async (_verbo, operacion) => {
      await operarRechazada(operacion, () =>
        HttpResponse.json({ mensaje: MENSAJE_INTERNO, correlacion_id: CORRELACION_500 }, { status: 500 }),
      );

      const aviso = await esperarAviso();
      expect(within(aviso).getByText(MENSAJE_INTERNO)).toBeInTheDocument();
      expect(within(aviso).getByText(`Referencia: ${CORRELACION_500}`)).toBeInTheDocument();
      // La pantalla sigue en pie: cabecera, tabla y las acciones de la fila.
      expect(screen.getByRole("heading", { name: "Proveedores" })).toBeInTheDocument();
      expect(celdasDe("CoPanel")).toContain("Activo");
      expect(accionesDe("CoPanel")).toEqual(["Editar", "Desactivar", "Dar de baja"]);
    },
  );

  test.each(OPERACIONES)(
    "tkt032a_estado · TC-F36 · %s con un error de red: muestra un aviso sin caer la pantalla y la fila conserva sus acciones",
    async (_verbo, operacion) => {
      await operarRechazada(operacion, () => HttpResponse.error());

      const aviso = await esperarAviso();
      expect(aviso).toHaveTextContent(/\S/);
      // Sin respuesta no hay referencia que pintar.
      expect(within(aviso).queryByText(/^Referencia:/)).not.toBeInTheDocument();
      expect(screen.getByRole("heading", { name: "Proveedores" })).toBeInTheDocument();
      expect(celdasDe("CoPanel")).toContain("Activo");
      expect(accionesDe("CoPanel")).toEqual(["Editar", "Desactivar", "Dar de baja"]);
    },
  );

  test.each(OPERACIONES)(
    "tkt032a_estado · TC-F36 · %s con un 409 CONCURRENCIA: «Reintentar» espera, y después reabre la captura de motivo de la misma operación y del mismo proveedor",
    async (_verbo, operacion) => {
      const existentes = [aceros(), copanel()];
      const rechazo = errorConcurrencia({
        codigo: "BLOQUEO_VENCIDO",
        mensaje: "Otra operación está modificando este proveedor en este momento. Vuelve a intentarlo.",
        detalle: { espera_maxima_ms: 5000 },
        acciones: [{ clave: "REINTENTAR", metodo: "POST", ruta: `${RUTA_PROVEEDORES}/${ID_COPANEL}/${operacion.ruta}` }],
        correlacion_id: CORRELACION_BLOQUEO,
      });
      const doble = dobleOperacion(existentes, operacion, ({ proveedorId }, intento) =>
        intento === 1
          ? HttpResponse.json(rechazo, { status: 409, headers: { "Retry-After": "1" } })
          : aceptar(existentes, operacion, proveedorId),
      );
      const { usuario, lista } = await abrirPantallaConTabla({ proveedores: existentes, operaciones: [doble] });

      await operarConMotivo(usuario, operacion, "CoPanel", "Primer intento");

      // Tratamiento propio de la espera, no el de una regla ni el de un error: su mensaje, su espera y su botón.
      const espera = await esperarBloqueo(REGION_ESPERA);
      expect(within(espera).getByText(rechazo.mensaje)).toBeInTheDocument();
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      expect(screen.queryByText("Operación bloqueada")).not.toBeInTheDocument();
      const reintentar = within(espera).getByRole("button", { name: "Reintentar" });
      expect(reintentar).toBeDisabled();
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1_500);
      });
      await waitFor(() => expect(reintentar).toBeEnabled());
      // Reintentar no repite la petición por sí solo: vuelve a pedir el motivo.
      expect(doble.recibidas).toHaveLength(1);

      await usuario.click(reintentar);
      const dialogo = await screen.findByRole("dialog", { name: operacion.titulo("CoPanel") });
      expect(screen.queryByRole("dialog", { name: operacion.titulo("Aceros del Bajío") })).not.toBeInTheDocument();
      expect(doble.recibidas).toHaveLength(1);
      await usuario.type(campoMotivo(dialogo), "Segundo intento");
      await usuario.click(botonConfirmar(dialogo));

      await esperarSinDialogo();
      expect(doble.recibidas.map((recibida) => ({ proveedorId: recibida.proveedorId, cuerpo: recibida.cuerpo }))).toEqual([
        { proveedorId: ID_COPANEL, cuerpo: { motivo: "Primer intento" } },
        { proveedorId: ID_COPANEL, cuerpo: { motivo: "Segundo intento" } },
      ]);
      await waitFor(() => expect(screen.queryByRole("region", { name: REGION_ESPERA })).not.toBeInTheDocument());
      await waitFor(() => expect(lista.pedidas.length).toBeGreaterThan(1));
      await waitFor(() => expect(screen.queryByRole("row", { name: /^CoPanel/ })).not.toBeInTheDocument());
      expect(celdasDe("Aceros del Bajío")).toContain("Activo");
    },
  );
});
