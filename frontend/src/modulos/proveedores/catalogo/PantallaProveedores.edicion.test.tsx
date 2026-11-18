import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import type { components as Servidor } from "@/api/generado/servidor";
import type { Rol } from "@/api/sesion";
import {
  errorConcurrencia,
  errorNoEncontrado,
  errorPermiso,
  errorValidacion,
  proveedor as proveedorBase,
  tokenCsrf,
  usuarioActual,
} from "@/pruebas/cuerpos";
import { renderizarAplicacion } from "@/pruebas/render";
import { servidorPruebas } from "@/pruebas/servidor";

// TKT-032a · fila F7 · TC-F23 a TC-F26 (CA-5; D-7, D-9). La edición de proveedores se prueba montada en su ruta
// `/compras/proveedores` dentro de la aplicación completa, con MSW como servidor, igual que la lista (F5) y el alta (F6):
// la prueba no importa ningún módulo nuevo. Las respuestas se construyen con los tipos generados (`satisfies`).
//
// Nombres accesibles que esta fila fija (el desarrollador los conserva; salen del boceto de `docs/08-wireframes.md` §2c):
//   botón de fila    «Editar <nombre del proveedor>»        diálogo  «Editar proveedor»        botón del diálogo  «Guardar»
//   campos de texto  «Nombre», «RFC» (solo lectura), «Tope de consignación» (el rótulo puede seguir con «(opcional)»)
//   desplegables     «Día de corte», «Día de pago»          con las siete opciones por su nombre: lunes … domingo
//   filtro de lista  «Estado» con la opción «Todos»
// (asumido) El rótulo del tope en la edición es el mismo que en el alta; el boceto no los distingue.
// (asumido) Un `404` al guardar se avisa en un `role="alert"` y la lista se recarga; el aviso trae el mensaje del servidor
// y su referencia. Un `409` CONCURRENCIA cierra el formulario y se avisa en la cabecera de la pantalla.

type Esquemas = Servidor["schemas"];
type Proveedor = Esquemas["Proveedor"];
type ProveedorCambios = Esquemas["ProveedorCambios"];

const ORIGEN = globalThis.location.origin;
const RUTA_SESION = "/api/v1/sesion";
const RUTA_CSRF = "/api/v1/sesion/csrf";
const RUTA_PROVEEDORES = "/api/v1/proveedores";
const RUTA_PANTALLA = "/compras/proveedores";

const ROL_QUE_OPERA: Rol = "COMPRAS";
const TITULO_EDICION = "Editar proveedor";
const TITULO_ALTA = "Alta de proveedor";
const MENSAJE_SIN_PERMISO = "Tu rol no permite esta operación.";

const ID_ACEROS = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d";
const ID_COPANEL = "9c2e5a41-7b3d-4f68-a1c9-3d5e7f9b1a24";
const ID_PINTURAS = "2b3c4d5e-6f70-4b8c-9d0e-1f2a3b4c5d6e";
const ID_FERRETERA = "3c4d5e6f-7081-4c9d-8e1f-2a3b4c5d6e7f";

const NOMBRE_NUEVO = "CoPanel S.A. de C.V.";
const MENSAJE_CONCURRENCIA = "Otra operación está modificando este proveedor en este momento. Vuelve a intentarlo.";
const CORRELACION_CONCURRENCIA = "d4e5f6a7-b8c9-4012-8d3e-f4a5b6c7d8e9";

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

/** ACTIVO, corte martes y pago viernes, sin tope. */
function aceros(): Proveedor {
  return proveedor({ id: ID_ACEROS, nombre: "Aceros del Bajío", rfc: "ABA040312KT7", tope_consignacion: null, dia_corte: 2, dia_pago: 5 });
}

/** ACTIVO, corte jueves, pago sábado y tope «300000.0000»: la forma con que el servidor devuelve el tope. */
function copanel(): Proveedor {
  return proveedor({ id: ID_COPANEL });
}

/** DESACTIVADO: ofrece Editar y Dar de baja (D-7). */
function pinturas(): Proveedor {
  return proveedor({
    id: ID_PINTURAS,
    nombre: "Pinturas del Norte",
    rfc: "PNO990101AB2",
    tope_consignacion: null,
    estado: "DESACTIVADO",
  });
}

/** BAJA: no ofrece ninguna acción (CA-7). */
function ferretera(): Proveedor {
  return proveedor({
    id: ID_FERRETERA,
    nombre: "Ferretera Vieja",
    rfc: "FVI870605XY9",
    tope_consignacion: null,
    dia_corte: 2,
    estado: "BAJA",
  });
}

function dobleSesion(roles: Rol[]) {
  return http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(usuarioActual(roles)));
}

function dobleCsrf() {
  return http.get(`${ORIGEN}${RUTA_CSRF}`, () => HttpResponse.json(tokenCsrf()));
}

/** GET /proveedores: lee el arreglo en cada petición, así que una edición aceptada se ve en la siguiente lista. */
function dobleLista(proveedores: Proveedor[]) {
  const pedidas: URL[] = [];
  const handler = http.get(`${ORIGEN}${RUTA_PROVEEDORES}`, ({ request }) => {
    const url = new URL(request.url);
    pedidas.push(url);
    const estados = url.searchParams.getAll("estado");
    const coincidentes = proveedores.filter((candidato) => (estados.length === 0 ? candidato.estado === "ACTIVO" : estados.includes(candidato.estado)));
    return HttpResponse.json({
      elementos: coincidentes,
      paginacion: { pagina: 1, tamano_pagina: 50, total: coincidentes.length },
    } satisfies Esquemas["ListaProveedores"]);
  });
  return { handler, pedidas };
}

interface EdicionRecibida {
  proveedorId: string;
  /** El cuerpo tal como viajó (texto): ahí se ve si un entero salió como «5» o un tope como número. */
  crudo: string;
  cuerpo: ProveedorCambios;
}

/** PATCH /proveedores/{proveedor_id}. Guarda cada petición tal como llegó y responde lo que decide la prueba. */
function dobleEdicion(responder: (recibida: EdicionRecibida) => Response) {
  const recibidas: EdicionRecibida[] = [];
  const handler = http.patch(`${ORIGEN}${RUTA_PROVEEDORES}/:proveedorId`, async ({ request, params }) => {
    const crudo = await request.text();
    const recibida: EdicionRecibida = {
      proveedorId: String(params.proveedorId),
      crudo,
      cuerpo: JSON.parse(crudo) as ProveedorCambios,
    };
    recibidas.push(recibida);
    return responder(recibida);
  });
  return { handler, recibidas };
}

/** Una edición que el servidor acepta: aplica solo lo que llegó y la siguiente lista ve el proveedor cambiado. */
function edicionQueAcepta(existentes: Proveedor[]) {
  return dobleEdicion(({ proveedorId, cuerpo }) => {
    const indice = existentes.findIndex((candidato) => candidato.id === proveedorId);
    const actual = existentes[indice];
    if (actual === undefined) {
      return HttpResponse.json(errorNoEncontrado("proveedor", "El proveedor no existe."), { status: 404 });
    }
    const actualizado = proveedor({
      ...actual,
      nombre: cuerpo.nombre ?? actual.nombre,
      tope_consignacion: cuerpo.tope_consignacion === undefined ? (actual.tope_consignacion ?? null) : cuerpo.tope_consignacion,
      dia_corte: cuerpo.dia_corte ?? actual.dia_corte,
      dia_pago: cuerpo.dia_pago ?? actual.dia_pago,
    });
    existentes[indice] = actualizado;
    existentes.sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
    return HttpResponse.json(actualizado satisfies Proveedor);
  });
}

interface OpcionesPantalla {
  proveedores?: Proveedor[];
  edicion?: ReturnType<typeof dobleEdicion>;
}

/** Monta la aplicación en `/compras/proveedores` con la sesión del rol, espera la sesión y la tabla, y devuelve la lista doblada. */
async function abrirPantallaConTabla(roles: Rol[], { proveedores = [aceros(), copanel()], edicion }: OpcionesPantalla = {}) {
  const lista = dobleLista(proveedores);
  servidorPruebas.use(dobleSesion(roles), dobleCsrf(), lista.handler);
  if (edicion !== undefined) servidorPruebas.use(edicion.handler);
  const aplicacion = renderizarAplicacion(RUTA_PANTALLA);
  await screen.findByText(/Rosa Villanueva/);
  await screen.findByRole("table");
  return { ...aplicacion, lista };
}

type Usuario = ReturnType<typeof renderizarAplicacion>["usuario"];

async function abrirEdicion(usuario: Usuario, nombreDelProveedor: string) {
  await usuario.click(screen.getByRole("button", { name: `Editar ${nombreDelProveedor}` }));
  return screen.findByRole("dialog", { name: TITULO_EDICION });
}

/** Los controles del formulario, por su etiqueta visible: rol y nombre, nunca clases ni estructura. */
function campos(dialogo: HTMLElement) {
  const dentro = within(dialogo);
  return {
    nombre: dentro.getByRole("textbox", { name: /^Nombre$/ }),
    rfc: dentro.getByRole("textbox", { name: /^RFC$/ }),
    tope: dentro.getByRole("textbox", { name: /^Tope de consignación/ }),
    corte: dentro.getByRole("combobox", { name: /^Día de corte/ }),
    pago: dentro.getByRole("combobox", { name: /^Día de pago/ }),
    guardar: dentro.getByRole("button", { name: "Guardar" }),
  };
}

type Controles = ReturnType<typeof campos>;

/** Reemplaza el contenido de un campo de texto. */
async function reescribir(usuario: Usuario, campo: HTMLElement, texto: string) {
  await usuario.clear(campo);
  await usuario.type(campo, texto);
}

const sinFormulario = () => expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

/** Las celdas de una fila de la tabla, en orden, como texto. */
function celdasDe(fila: HTMLElement): string[] {
  return within(fila)
    .getAllByRole("cell")
    .map((celda) => celda.textContent ?? "");
}

describe("TKT-032a · TC-F23 · «Editar» abre el formulario con los valores del proveedor y el RFC de solo lectura (CA-5)", () => {
  test("tkt032a_edicion · TC-F23 · el botón de fila abre «Editar proveedor», no el alta, con el foco en el nombre", async () => {
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA]);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    const dialogo = await abrirEdicion(usuario, "CoPanel");

    expect(screen.queryByRole("dialog", { name: TITULO_ALTA })).not.toBeInTheDocument();
    const { nombre } = campos(dialogo);
    await waitFor(() => expect(nombre).toHaveFocus());
    expect(within(dialogo).getAllByRole("textbox").at(0)).toBe(nombre);
  });

  test("tkt032a_edicion · TC-F23 · el formulario nace con el nombre, el tope sin cambiar de forma y los días por su nombre", async () => {
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA]);

    const dialogo = await abrirEdicion(usuario, "CoPanel");
    const controles = campos(dialogo);

    expect(controles.nombre).toHaveValue("CoPanel");
    // El tope es dinero: se muestra con la forma que llegó, «300000.0000», sin pasar por número («300000»).
    expect(controles.tope).toHaveValue("300000.0000");
    expect(controles.corte).toHaveDisplayValue("jueves");
    expect(controles.pago).toHaveDisplayValue("sábado");
    expect(within(controles.corte).getAllByRole("option").map((opcion) => opcion.textContent)).toEqual([
      "lunes",
      "martes",
      "miércoles",
      "jueves",
      "viernes",
      "sábado",
      "domingo",
    ]);
  });

  test("tkt032a_edicion · TC-F23 · un proveedor sin tope abre con el tope vacío y sus propios días", async () => {
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA]);

    const dialogo = await abrirEdicion(usuario, "Aceros del Bajío");
    const controles = campos(dialogo);

    expect(controles.nombre).toHaveValue("Aceros del Bajío");
    expect(controles.tope).toHaveValue("");
    expect(controles.corte).toHaveDisplayValue("martes");
    expect(controles.pago).toHaveDisplayValue("viernes");
  });

  test("tkt032a_edicion · TC-F23 · el RFC se ve con su valor pero es de solo lectura: teclear no lo cambia", async () => {
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA]);
    const dialogo = await abrirEdicion(usuario, "CoPanel");
    const { rfc } = campos(dialogo);

    expect(rfc).toHaveValue("XAXX010101000");
    expect(rfc).toHaveAttribute("readonly");
    await usuario.type(rfc, "ZZZ");
    expect(rfc).toHaveValue("XAXX010101000");
    // Los demás campos de texto siguen siendo editables.
    const { nombre, tope } = campos(dialogo);
    expect(nombre).not.toHaveAttribute("readonly");
    expect(tope).not.toHaveAttribute("readonly");
  });
});

describe("TKT-032a · TC-F24 · cambia el nombre y el día de pago (CA-5)", () => {
  test("tkt032a_edicion · TC-F24 · el PATCH al proveedor lleva SOLO nombre y dia_pago, este último como entero, sin rfc ni tope ni dia_corte", async () => {
    const existentes = [aceros(), copanel()];
    const edicion = edicionQueAcepta(existentes);
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: existentes, edicion });

    const dialogo = await abrirEdicion(usuario, "CoPanel");
    const controles = campos(dialogo);
    await reescribir(usuario, controles.nombre, NOMBRE_NUEVO);
    await usuario.selectOptions(controles.pago, "viernes");
    await usuario.click(controles.guardar);

    await waitFor(sinFormulario);
    expect(edicion.recibidas).toHaveLength(1);
    const [recibida] = edicion.recibidas;
    expect(recibida?.proveedorId).toBe(ID_COPANEL);
    expect(recibida?.cuerpo).toEqual({ nombre: NOMBRE_NUEVO, dia_pago: 5 } satisfies ProveedorCambios);
    // Exactamente esas dos claves: ni rfc, ni tope_consignacion, ni dia_corte, aunque el formulario los tuviera.
    expect(Object.keys(recibida?.cuerpo ?? {}).sort()).toEqual(["dia_pago", "nombre"]);
    // Entero de verdad, no «5»: el contrato lo declara `integer`.
    expect(typeof recibida?.cuerpo.dia_pago).toBe("number");
    expect(recibida?.crudo).toContain('"dia_pago":5');
    expect(recibida?.crudo).not.toContain("rfc");
    expect(recibida?.crudo).not.toContain("tope_consignacion");
    expect(recibida?.crudo).not.toContain("dia_corte");
  });

  test("tkt032a_edicion · TC-F24 · el formulario se cierra y la lista se vuelve a pedir y muestra los datos nuevos", async () => {
    const existentes = [aceros(), copanel()];
    const edicion = edicionQueAcepta(existentes);
    const { usuario, lista } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: existentes, edicion });
    expect(lista.pedidas).toHaveLength(1);

    const dialogo = await abrirEdicion(usuario, "CoPanel");
    const controles = campos(dialogo);
    await reescribir(usuario, controles.nombre, NOMBRE_NUEVO);
    await usuario.selectOptions(controles.pago, "viernes");
    await usuario.click(controles.guardar);

    await waitFor(sinFormulario);
    await waitFor(() => expect(lista.pedidas).toHaveLength(2));
    const fila = await screen.findByRole("row", { name: new RegExp(`^${NOMBRE_NUEVO.replaceAll(".", "\\.")}`) });
    // Mismo RFC, mismo estado y mismo corte; el pago pasó de sábado a viernes.
    expect(celdasDe(fila).slice(0, 5)).toEqual([NOMBRE_NUEVO, "XAXX010101000", "Activo", "jueves", "viernes"]);
    // El nombre viejo ya no aparece como celda.
    expect(screen.queryByRole("cell", { name: "CoPanel" })).not.toBeInTheDocument();
  });

  test("tkt032a_edicion · TC-F24 · cambiar solo el día de corte envía solo dia_corte, como entero", async () => {
    const existentes = [aceros(), copanel()];
    const edicion = edicionQueAcepta(existentes);
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: existentes, edicion });

    const dialogo = await abrirEdicion(usuario, "CoPanel");
    const controles = campos(dialogo);
    await usuario.selectOptions(controles.corte, "martes");
    await usuario.click(controles.guardar);

    await waitFor(sinFormulario);
    expect(edicion.recibidas.at(0)?.cuerpo).toEqual({ dia_corte: 2 } satisfies ProveedorCambios);
    expect(edicion.recibidas.at(0)?.crudo).toContain('"dia_corte":2');
  });

  test("tkt032a_edicion · TC-F24 · un nombre con espacios alrededor se envía recortado", async () => {
    const existentes = [aceros(), copanel()];
    const edicion = edicionQueAcepta(existentes);
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: existentes, edicion });

    const dialogo = await abrirEdicion(usuario, "CoPanel");
    await reescribir(usuario, campos(dialogo).nombre, `  ${NOMBRE_NUEVO}  `);
    await usuario.click(campos(dialogo).guardar);

    await waitFor(sinFormulario);
    expect(edicion.recibidas.at(0)?.cuerpo).toEqual({ nombre: NOMBRE_NUEVO } satisfies ProveedorCambios);
  });
});

describe("TKT-032a · TC-F24 · el tope de consignación es dinero: viaja como cadena (CA-5, CA-R4; M-4)", () => {
  // «99999999999999.9999» es el mayor tope que admite el contrato (14 enteros y 4 decimales): pasado por `Number` se
  // convierte en 100000000000000 y pierde los decimales. «450000.50» conserva el cero final solo si viaja como cadena.
  test.each(["450000.50", "99999999999999.9999"])(
    "tkt032a_edicion · TC-F24 · si se cambia el tope a %s, el PATCH lleva solo tope_consignacion y como cadena idéntica",
    async (tope) => {
      const existentes = [aceros(), copanel()];
      const edicion = edicionQueAcepta(existentes);
      const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: existentes, edicion });

      const dialogo = await abrirEdicion(usuario, "CoPanel");
      const controles = campos(dialogo);
      await reescribir(usuario, controles.tope, tope);
      await usuario.click(controles.guardar);

      await waitFor(sinFormulario);
      expect(edicion.recibidas).toHaveLength(1);
      expect(edicion.recibidas.at(0)?.cuerpo).toEqual({ tope_consignacion: tope } satisfies ProveedorCambios);
      // M-4: el cuerpo crudo y su tipo. Un tope que pasó por `Number` sale como número JSON y falla aquí.
      expect(typeof edicion.recibidas.at(0)?.cuerpo.tope_consignacion).toBe("string");
      expect(edicion.recibidas.at(0)?.crudo).toContain(`"tope_consignacion":"${tope}"`);
    },
  );

  test("tkt032a_edicion · TC-F24 · si se vacía el tope, el PATCH lleva tope_consignacion null (borra el tope) y nada más", async () => {
    const existentes = [aceros(), copanel()];
    const edicion = edicionQueAcepta(existentes);
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: existentes, edicion });

    const dialogo = await abrirEdicion(usuario, "CoPanel");
    const controles = campos(dialogo);
    await usuario.clear(controles.tope);
    await usuario.click(controles.guardar);

    await waitFor(sinFormulario);
    expect(edicion.recibidas).toHaveLength(1);
    expect(edicion.recibidas.at(0)?.cuerpo).toEqual({ tope_consignacion: null } satisfies ProveedorCambios);
    expect(edicion.recibidas.at(0)?.crudo).toContain('"tope_consignacion":null');
  });

  test("tkt032a_edicion · TC-F24 · poner tope a un proveedor que no lo tenía envía el tope como cadena", async () => {
    const existentes = [aceros(), copanel()];
    const edicion = edicionQueAcepta(existentes);
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: existentes, edicion });

    const dialogo = await abrirEdicion(usuario, "Aceros del Bajío");
    await usuario.type(campos(dialogo).tope, "120000.00");
    await usuario.click(campos(dialogo).guardar);

    await waitFor(sinFormulario);
    expect(edicion.recibidas.at(0)?.proveedorId).toBe(ID_ACEROS);
    expect(edicion.recibidas.at(0)?.cuerpo).toEqual({ tope_consignacion: "120000.00" } satisfies ProveedorCambios);
    expect(edicion.recibidas.at(0)?.crudo).toContain('"tope_consignacion":"120000.00"');
  });
});

describe("TKT-032a · TC-F25 · guardar sin cambios no envía nada (CA-5, borde)", () => {
  async function guardarSinCambios(proveedores: Proveedor[], nombreDelProveedor: string, tocar?: (usuario: Usuario, controles: Controles) => Promise<void>) {
    const edicion = edicionQueAcepta(proveedores);
    const { usuario, lista } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores, edicion });
    const dialogo = await abrirEdicion(usuario, nombreDelProveedor);
    const controles = campos(dialogo);
    if (tocar !== undefined) await tocar(usuario, controles);
    await usuario.click(controles.guardar);
    await waitFor(sinFormulario);
    return { edicion, lista };
  }

  test("tkt032a_edicion · TC-F25 · guardar sin tocar nada cierra el formulario y no envía ningún PATCH", async () => {
    const { edicion } = await guardarSinCambios([aceros(), copanel()], "CoPanel");

    expect(edicion.recibidas).toHaveLength(0);
  });

  test("tkt032a_edicion · TC-F25 · un proveedor sin tope, guardado sin tocar, no envía PATCH: el tope vacío no es un cambio", async () => {
    const { edicion } = await guardarSinCambios([aceros(), copanel()], "Aceros del Bajío");

    expect(edicion.recibidas).toHaveLength(0);
  });

  test("tkt032a_edicion · TC-F25 · reescribir el tope con el mismo importe en otra escala («300000» por «300000.0000») no es un cambio", async () => {
    const { edicion } = await guardarSinCambios([aceros(), copanel()], "CoPanel", (usuario, controles) => reescribir(usuario, controles.tope, "300000"));

    expect(edicion.recibidas).toHaveLength(0);
  });

  test("tkt032a_edicion · TC-F25 · espacios añadidos alrededor del nombre no son un cambio: se recortan y no hay PATCH", async () => {
    const { edicion } = await guardarSinCambios([aceros(), copanel()], "CoPanel", (usuario, controles) => reescribir(usuario, controles.nombre, "  CoPanel  "));

    expect(edicion.recibidas).toHaveLength(0);
  });

  test("tkt032a_edicion · TC-F25 · cambiar un valor y devolverlo al original tampoco envía PATCH", async () => {
    const { edicion } = await guardarSinCambios([aceros(), copanel()], "CoPanel", async (usuario, controles) => {
      await usuario.selectOptions(controles.pago, "viernes");
      await usuario.selectOptions(controles.pago, "sábado");
    });

    expect(edicion.recibidas).toHaveLength(0);
  });
});

describe("TKT-032a · TC-F26 · el rechazo de la edición (CA-5, rechazo)", () => {
  const MENSAJES = {
    nombre: "El nombre admite hasta 200 caracteres.",
    tope_consignacion: "El tope admite hasta 14 enteros y 4 decimales.",
    dia_corte: "El día de corte debe estar entre 1 y 7.",
    dia_pago: "El día de pago debe estar entre 1 y 7.",
  } as const;

  type CampoServidor = keyof typeof MENSAJES;
  const CONTROL_DE: Readonly<Record<CampoServidor, (controles: Controles) => HTMLElement>> = {
    nombre: (controles) => controles.nombre,
    tope_consignacion: (controles) => controles.tope,
    dia_corte: (controles) => controles.corte,
    dia_pago: (controles) => controles.pago,
  };
  const CAMPOS_DEL_SERVIDOR = Object.keys(MENSAJES) as CampoServidor[];

  test.each(CAMPOS_DEL_SERVIDOR)(
    "tkt032a_edicion · TC-F26 · un 422 en %s se pinta junto a su campo con aria-invalid, el formulario sigue abierto y lo capturado se conserva",
    async (campo) => {
      const mensaje = MENSAJES[campo];
      const edicion = dobleEdicion(() => HttpResponse.json(errorValidacion([{ campo, codigo: "FORMATO", mensaje }]), { status: 422 }));
      const { usuario, lista } = await abrirPantallaConTabla([ROL_QUE_OPERA], { edicion });
      const dialogo = await abrirEdicion(usuario, "CoPanel");
      const controles = campos(dialogo);
      await reescribir(usuario, controles.nombre, "CoPanel Matriz");
      await usuario.click(controles.guardar);

      expect(await within(dialogo).findByText(mensaje)).toBeInTheDocument();
      const afectado = CONTROL_DE[campo](controles);
      expect(afectado).toHaveAttribute("aria-invalid", "true");
      expect(afectado).toHaveAccessibleDescription(mensaje);
      // Solo ese campo queda marcado.
      for (const otro of CAMPOS_DEL_SERVIDOR.filter((candidato) => candidato !== campo)) {
        expect(CONTROL_DE[otro](controles)).not.toHaveAttribute("aria-invalid", "true");
      }
      // El cliente envió el PATCH y fue el servidor quien lo rechazó; el formulario conserva lo capturado y sigue abierto.
      expect(edicion.recibidas).toHaveLength(1);
      expect(controles.nombre).toHaveValue("CoPanel Matriz");
      expect(controles.rfc).toHaveValue("XAXX010101000");
      expect(controles.tope).toHaveValue("300000.0000");
      expect(screen.getByRole("dialog", { name: TITULO_EDICION })).toBeInTheDocument();
      // No es un bloqueo de negocio ni vuelve a pedirse la lista.
      expect(within(dialogo).queryByRole("region")).not.toBeInTheDocument();
      expect(lista.pedidas).toHaveLength(1);
    },
  );

  test("tkt032a_edicion · TC-F26 · un nombre vacío se rechaza antes de enviar, junto a su campo, y no sale ningún PATCH", async () => {
    const edicion = edicionQueAcepta([aceros(), copanel()]);
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { edicion });
    const dialogo = await abrirEdicion(usuario, "CoPanel");
    const controles = campos(dialogo);
    await usuario.clear(controles.nombre);
    await usuario.click(controles.guardar);

    expect(await within(dialogo).findByText("Escribe el nombre del proveedor.")).toBeInTheDocument();
    expect(controles.nombre).toHaveAttribute("aria-invalid", "true");
    expect(edicion.recibidas).toHaveLength(0);
    expect(screen.getByRole("dialog", { name: TITULO_EDICION })).toBeInTheDocument();
  });

  test("tkt032a_edicion · TC-F26 · un 404 avisa con el mensaje del servidor y su referencia, y la lista se vuelve a pedir sin el proveedor desaparecido", async () => {
    const existentes = [aceros(), copanel()];
    const rechazo = errorNoEncontrado("proveedor", "El proveedor ya no existe en el catálogo.");
    const edicion = dobleEdicion(() => {
      // El proveedor desapareció entre la lista y el guardado: la siguiente lista ya no lo trae.
      existentes.splice(
        existentes.findIndex((candidato) => candidato.id === ID_COPANEL),
        1,
      );
      return HttpResponse.json(rechazo, { status: 404 });
    });
    const { usuario, lista } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: existentes, edicion });
    expect(lista.pedidas).toHaveLength(1);
    const dialogo = await abrirEdicion(usuario, "CoPanel");
    await reescribir(usuario, campos(dialogo).nombre, NOMBRE_NUEVO);
    await usuario.click(campos(dialogo).guardar);

    // El aviso trae el mensaje del servidor y su referencia; no es un bloqueo de negocio.
    const aviso = await screen.findByRole("alert");
    expect(within(aviso).getByText(rechazo.mensaje)).toBeInTheDocument();
    expect(within(aviso).getByText(`Referencia: ${rechazo.correlacion_id}`)).toBeInTheDocument();
    expect(screen.queryByText("Operación bloqueada")).not.toBeInTheDocument();
    expect(screen.queryByText("No se puede completar")).not.toBeInTheDocument();
    expect(edicion.recibidas).toHaveLength(1);

    // La lista se recarga (`CA-5`: «lo avisa y recarga la lista») y el proveedor desaparecido ya no está.
    await waitFor(() => expect(lista.pedidas).toHaveLength(2));
    await waitFor(() => expect(screen.queryByRole("row", { name: /^CoPanel/, hidden: true })).not.toBeInTheDocument());
    expect(screen.getByRole("row", { name: /^Aceros del Bajío/, hidden: true })).toBeInTheDocument();
  });

  test("tkt032a_edicion · TC-F26 · un 403 pinta el mensaje del servidor en el formulario, sin cifras ni tratamiento de bloqueo, y el formulario sigue abierto", async () => {
    const edicion = dobleEdicion(() =>
      HttpResponse.json({ ...errorPermiso("ROL_INSUFICIENTE"), mensaje: MENSAJE_SIN_PERMISO }, { status: 403 }),
    );
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { edicion });
    const dialogo = await abrirEdicion(usuario, "CoPanel");
    const controles = campos(dialogo);
    await reescribir(usuario, controles.nombre, NOMBRE_NUEVO);
    await usuario.click(controles.guardar);

    expect(await within(dialogo).findByText(new RegExp(MENSAJE_SIN_PERMISO))).toBeInTheDocument();
    // No es un bloqueo de negocio: ni cabecera de bloqueo, ni cifras, ni acciones.
    expect(within(dialogo).queryByRole("region")).not.toBeInTheDocument();
    expect(within(dialogo).queryByText("Operación bloqueada")).not.toBeInTheDocument();
    expect(within(dialogo).queryByText("No se puede completar")).not.toBeInTheDocument();
    expect(within(dialogo).queryByText(/disponible|excedente|presupuestado/i)).not.toBeInTheDocument();
    // El formulario sigue abierto y conserva lo capturado.
    expect(screen.getByRole("dialog", { name: TITULO_EDICION })).toBeInTheDocument();
    expect(controles.nombre).toHaveValue(NOMBRE_NUEVO);
    expect(edicion.recibidas).toHaveLength(1);
  });

  test("tkt032a_edicion · TC-F26 · un 409 CONCURRENCIA del PATCH cierra la edición y avisa en la cabecera con el mensaje del servidor y su referencia", async () => {
    const rechazo = errorConcurrencia({
      codigo: "BLOQUEO_VENCIDO",
      mensaje: MENSAJE_CONCURRENCIA,
      detalle: { espera_maxima_ms: 5000 },
      acciones: [{ clave: "REINTENTAR", metodo: "PATCH", ruta: `${RUTA_PROVEEDORES}/${ID_COPANEL}` }],
      correlacion_id: CORRELACION_CONCURRENCIA,
    });
    const edicion = dobleEdicion(() => HttpResponse.json(rechazo, { status: 409 }));
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { edicion });
    const dialogo = await abrirEdicion(usuario, "CoPanel");
    const controles = campos(dialogo);
    await reescribir(usuario, controles.nombre, NOMBRE_NUEVO);
    await usuario.click(controles.guardar);

    // El formulario se cierra y el aviso queda en la cabecera de la pantalla, con el mensaje y la referencia del servidor.
    await waitFor(sinFormulario);
    const aviso = await screen.findByRole("alert");
    expect(within(aviso).getByText(MENSAJE_CONCURRENCIA)).toBeInTheDocument();
    expect(within(aviso).getByText(`Referencia: ${CORRELACION_CONCURRENCIA}`)).toBeInTheDocument();
    // No es una espera con «Reintentar» ni un bloqueo de regla: la edición no ofrece reintento.
    expect(screen.queryByRole("region", { name: "Inténtalo de nuevo" })).not.toBeInTheDocument();
    expect(screen.queryByText("Operación bloqueada")).not.toBeInTheDocument();
    expect(screen.queryByText("No se puede completar")).not.toBeInTheDocument();
    expect(edicion.recibidas).toHaveLength(1);
  });
});

describe("TKT-032a · cierre sin guardar y aviso de cabecera (CA-5, borde)", () => {
  test("tkt032a_edicion · cierre · teclear en «Editar proveedor», pulsar Escape y reabrir: valores originales y ningún PATCH", async () => {
    const existentes = [aceros(), copanel()];
    const edicion = edicionQueAcepta(existentes);
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: existentes, edicion });
    const dialogo = await abrirEdicion(usuario, "CoPanel");
    const controles = campos(dialogo);
    await reescribir(usuario, controles.nombre, NOMBRE_NUEVO);
    await reescribir(usuario, controles.tope, "1.00");
    await usuario.selectOptions(controles.pago, "lunes");

    await usuario.keyboard("{Escape}");

    await waitFor(sinFormulario);
    expect(edicion.recibidas).toHaveLength(0);
    const reabierto = campos(await abrirEdicion(usuario, "CoPanel"));
    expect(reabierto.nombre).toHaveValue("CoPanel");
    expect(reabierto.tope).toHaveValue("300000.0000");
    expect(reabierto.pago).toHaveDisplayValue("sábado");
    expect(edicion.recibidas).toHaveLength(0);
  });

  test("tkt032a_edicion · aviso · un aviso de cabecera visible desaparece al abrir «Editar» otra vez", async () => {
    const rechazo = errorConcurrencia({
      codigo: "BLOQUEO_VENCIDO",
      mensaje: MENSAJE_CONCURRENCIA,
      detalle: { espera_maxima_ms: 5000 },
      acciones: [{ clave: "REINTENTAR", metodo: "PATCH", ruta: `${RUTA_PROVEEDORES}/${ID_COPANEL}` }],
      correlacion_id: CORRELACION_CONCURRENCIA,
    });
    const edicion = dobleEdicion(() => HttpResponse.json(rechazo, { status: 409 }));
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { edicion });
    const primero = await abrirEdicion(usuario, "CoPanel");
    await reescribir(usuario, campos(primero).nombre, NOMBRE_NUEVO);
    await usuario.click(campos(primero).guardar);
    await waitFor(sinFormulario);
    expect(await screen.findByRole("alert")).toHaveTextContent(MENSAJE_CONCURRENCIA);

    await abrirEdicion(usuario, "Aceros del Bajío");

    // Con el diálogo abierto el resto de la página queda fuera del árbol de accesibilidad: se busca también ahí.
    expect(screen.queryByRole("alert", { hidden: true })).not.toBeInTheDocument();
    expect(screen.queryByText(MENSAJE_CONCURRENCIA, { exact: false })).not.toBeInTheDocument();
  });
});

describe("TKT-032a · D-7 · «Editar» se ofrece en ACTIVO y DESACTIVADO, no en BAJA (CA-5, CA-7)", () => {
  const TODOS = () => [aceros(), pinturas(), ferretera()];

  /** Pasa el filtro a «Todos» y espera a que lleguen las tres filas. */
  async function verTodos(usuario: Usuario) {
    await usuario.selectOptions(screen.getByRole("combobox", { name: "Estado" }), "Todos");
    await screen.findByRole("row", { name: /^Ferretera Vieja/ });
  }

  test.each([
    ["ACTIVO", "Aceros del Bajío", ID_ACEROS],
    ["DESACTIVADO", "Pinturas del Norte", ID_PINTURAS],
  ] as const)(
    "tkt032a_edicion · D-7 · un proveedor %s ofrece «Editar»: abre el mismo formulario y guarda solo lo cambiado",
    async (_estado, nombreDelProveedor, id) => {
      const existentes = TODOS();
      const edicion = edicionQueAcepta(existentes);
      const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: existentes, edicion });
      await verTodos(usuario);

      const dialogo = await abrirEdicion(usuario, nombreDelProveedor);
      const controles = campos(dialogo);
      expect(controles.nombre).toHaveValue(nombreDelProveedor);
      expect(controles.rfc).toHaveAttribute("readonly");
      await usuario.selectOptions(controles.pago, "lunes");
      await usuario.click(controles.guardar);

      await waitFor(sinFormulario);
      expect(edicion.recibidas).toHaveLength(1);
      expect(edicion.recibidas.at(0)?.proveedorId).toBe(id);
      expect(edicion.recibidas.at(0)?.cuerpo).toEqual({ dia_pago: 1 } satisfies ProveedorCambios);
    },
  );

  test("tkt032a_edicion · D-7 · rechazo: un proveedor en BAJA no ofrece «Editar» ni ningún otro botón", async () => {
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: TODOS() });
    await verTodos(usuario);

    expect(screen.queryByRole("button", { name: "Editar Ferretera Vieja" })).not.toBeInTheDocument();
    const fila = screen.getByRole("row", { name: /^Ferretera Vieja/ });
    expect(within(fila).queryAllByRole("button")).toHaveLength(0);
    // Los otros dos sí la ofrecen: el filtro «Todos» no la quita a nadie más.
    expect(screen.getByRole("button", { name: "Editar Aceros del Bajío" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Editar Pinturas del Norte" })).toBeInTheDocument();
  });
});
