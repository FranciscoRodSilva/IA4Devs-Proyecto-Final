import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import type { components as Servidor } from "@/api/generado/servidor";
import type { Rol } from "@/api/sesion";
import { errorConflictoEstado, errorPermiso, errorValidacion, proveedor as proveedorBase, tokenCsrf, usuarioActual } from "@/pruebas/cuerpos";
import { renderizarAplicacion } from "@/pruebas/render";
import { servidorPruebas } from "@/pruebas/servidor";

// TKT-032a · fila F6 · TC-F18 a TC-F22 (CA-2, CA-3, CA-4, CA-R4; M-4). El alta de proveedores se prueba montada en su ruta
// `/compras/proveedores` dentro de la aplicación completa, con MSW como servidor, igual que la lista (F5) y que el alta de
// obras (TKT-012a): la prueba no importa ningún módulo nuevo y cada caso falla por el comportamiento ausente (hoy el botón
// «+» se pinta pero no abre ningún formulario). Las respuestas se construyen con los tipos generados (`satisfies`).
//
// Nombres accesibles que esta fila fija (el desarrollador los conserva; salen del boceto de `docs/08-wireframes.md` §2c):
//   botón            «Dar de alta un proveedor»            diálogo  «Alta de proveedor»        botón del diálogo  «Guardar»
//   campos de texto  «Nombre», «RFC», «Tope de consignación» (el rótulo puede seguir con «(opcional)»)
//   desplegables     «Día de corte», «Día de pago»          con las siete opciones por su nombre: lunes … domingo
// El conflicto en línea es la `region` (`<section aria-labelledby>`) de `ConflictoEnLinea`, ya probada en TKT-008c.

type Esquemas = Servidor["schemas"];
type Proveedor = Esquemas["Proveedor"];
type ProveedorNuevo = Esquemas["ProveedorNuevo"];

const ORIGEN = globalThis.location.origin;
const RUTA_SESION = "/api/v1/sesion";
const RUTA_CSRF = "/api/v1/sesion/csrf";
const RUTA_PROVEEDORES = "/api/v1/proveedores";
const RUTA_PANTALLA = "/compras/proveedores";

const ROL_QUE_OPERA: Rol = "COMPRAS";
const ETIQUETA_ALTA = "Dar de alta un proveedor";
const TITULO_FORMULARIO = "Alta de proveedor";
const MENSAJE_SIN_PERMISO = "Tu rol no permite esta operación.";
const MENSAJE_NOMBRE_VACIO = "Escribe el nombre del proveedor.";
const MENSAJE_RFC_MALFORMADO = /Escribe el RFC con su forma/;
const MENSAJE_TOPE_INVALIDO = /Escribe el tope como un número/;

const ID_ACEROS = "1a2b3c4d-5e6f-4a7b-8c9d-0e1f2a3b4c5d";
const ID_COPANEL = "9c2e5a41-7b3d-4f68-a1c9-3d5e7f9b1a24";
const ID_NUEVO = "4c5d6e7f-8091-4a2b-b3c4-d5e6f7081920";

// Un proveedor que no existe todavía: nombre y RFC con la forma del contrato (3 letras, 6 dígitos, 3 alfanuméricos).
const NOMBRE_NUEVO = "Tablaroca del Norte";
const RFC_NUEVO = "TNO050607QX1";

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

/** ACTIVO, corte martes y pago viernes. */
function aceros(): Proveedor {
  return proveedor({ id: ID_ACEROS, nombre: "Aceros del Bajío", rfc: "ABA040312KT7", tope_consignacion: null, dia_corte: 2, dia_pago: 5 });
}

/** ACTIVO, corte jueves y pago sábado: el proveedor cuyo RFC se intenta repetir. */
function copanel(): Proveedor {
  return proveedor({ id: ID_COPANEL });
}

function dobleSesion(roles: Rol[]) {
  return http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(usuarioActual(roles)));
}

function dobleCsrf() {
  return http.get(`${ORIGEN}${RUTA_CSRF}`, () => HttpResponse.json(tokenCsrf()));
}

/** GET /proveedores con lo mínimo del contrato que estas pruebas necesitan: por omisión solo los ACTIVO, en una página. */
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

/** POST /proveedores. Guarda cada cuerpo recibido, tal como viajó (texto) y ya leído, y responde lo que decide la prueba. */
function dobleAlta(responder: (cuerpo: ProveedorNuevo) => Response) {
  const cuerpos: ProveedorNuevo[] = [];
  const crudos: string[] = [];
  const handler = http.post(`${ORIGEN}${RUTA_PROVEEDORES}`, async ({ request }) => {
    const crudo = await request.text();
    const cuerpo = JSON.parse(crudo) as ProveedorNuevo;
    crudos.push(crudo);
    cuerpos.push(cuerpo);
    return responder(cuerpo);
  });
  return { handler, cuerpos, crudos };
}

/** Un alta que el servidor acepta: el proveedor nuevo entra al catálogo vivo y la siguiente lista lo ve. */
function altaQueAcepta(existentes: Proveedor[]) {
  return dobleAlta((cuerpo) => {
    const creado = proveedor({
      id: ID_NUEVO,
      nombre: cuerpo.nombre,
      rfc: cuerpo.rfc,
      tope_consignacion: cuerpo.tope_consignacion ?? null,
      dia_corte: cuerpo.dia_corte,
      dia_pago: cuerpo.dia_pago,
      estado: "ACTIVO",
    });
    existentes.push(creado);
    existentes.sort((a, b) => a.nombre.localeCompare(b.nombre, "es"));
    return HttpResponse.json(creado satisfies Proveedor, { status: 201, headers: { Location: `${RUTA_PROVEEDORES}/${ID_NUEVO}` } });
  });
}

interface OpcionesPantalla {
  proveedores?: Proveedor[];
  alta?: ReturnType<typeof dobleAlta>;
}

/** Monta la aplicación en `/compras/proveedores` con la sesión del rol, espera la sesión y la tabla, y devuelve la lista doblada. */
async function abrirPantallaConTabla(roles: Rol[], { proveedores = [aceros(), copanel()], alta }: OpcionesPantalla = {}) {
  const lista = dobleLista(proveedores);
  servidorPruebas.use(dobleSesion(roles), dobleCsrf(), lista.handler);
  if (alta !== undefined) servidorPruebas.use(alta.handler);
  const aplicacion = renderizarAplicacion(RUTA_PANTALLA);
  await screen.findByText(/Rosa Villanueva/);
  await screen.findByRole("table");
  return { ...aplicacion, lista };
}

type Usuario = ReturnType<typeof renderizarAplicacion>["usuario"];

async function abrirFormulario(usuario: Usuario) {
  await usuario.click(screen.getByRole("button", { name: ETIQUETA_ALTA }));
  return screen.findByRole("dialog", { name: TITULO_FORMULARIO });
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

/** Captura lo mínimo del alta: nombre y RFC. Los días y el tope se quedan como los propone el formulario. */
async function capturarNombreYRfc(usuario: Usuario, controles: Controles, nombre = NOMBRE_NUEVO, rfc = RFC_NUEVO) {
  await usuario.type(controles.nombre, nombre);
  await usuario.type(controles.rfc, rfc);
}

const sinFormulario = () => expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

/** Las celdas de una fila de la tabla, en orden, como texto. */
function celdasDe(fila: HTMLElement): string[] {
  return within(fila)
    .getAllByRole("cell")
    .map((celda) => celda.textContent ?? "");
}

describe("TKT-032a · TC-F18 · el botón + abre el formulario de alta (CA-2)", () => {
  test("hdu004_esc01 · TC-F18 · el botón + abre «Alta de proveedor» con el foco en el nombre, que es el primer campo", async () => {
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA]);
    // Antes de pulsar no hay formulario.
    sinFormulario();

    const dialogo = await abrirFormulario(usuario);

    const { nombre } = campos(dialogo);
    await waitFor(() => expect(nombre).toHaveFocus());
    expect(within(dialogo).getAllByRole("textbox").at(0)).toBe(nombre);
  });

  test("hdu004_esc01 · TC-F18 · el formulario nace con nombre, RFC y tope vacíos, y con jueves y sábado precargados (RN-17)", async () => {
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA]);

    const dialogo = await abrirFormulario(usuario);
    const controles = campos(dialogo);

    expect(controles.nombre).toHaveValue("");
    expect(controles.rfc).toHaveValue("");
    expect(controles.tope).toHaveValue("");
    expect(controles.corte).toHaveDisplayValue("jueves");
    expect(controles.pago).toHaveDisplayValue("sábado");
    // Los desplegables ofrecen la semana completa por su nombre.
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
});

describe("TKT-032a · TC-F19 · alta con los valores por omisión (CA-2)", () => {
  test("hdu004_esc02 · TC-F19 · el cuerpo lleva dia_corte 4 y dia_pago 6 como enteros y tope null; el formulario se cierra y la lista se vuelve a pedir con el proveedor nuevo", async () => {
    const existentes = [aceros(), copanel()];
    const alta = altaQueAcepta(existentes);
    const { usuario, lista } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: existentes, alta });
    expect(lista.pedidas).toHaveLength(1);

    const dialogo = await abrirFormulario(usuario);
    const controles = campos(dialogo);
    await capturarNombreYRfc(usuario, controles);
    await usuario.click(controles.guardar);

    await waitFor(sinFormulario);
    expect(alta.cuerpos).toEqual([
      { nombre: NOMBRE_NUEVO, rfc: RFC_NUEVO, tope_consignacion: null, dia_corte: 4, dia_pago: 6 } satisfies ProveedorNuevo,
    ]);
    // Enteros de verdad, no «4» ni «6»: el contrato los declara `integer`.
    const [enviado] = alta.cuerpos;
    expect(typeof enviado?.dia_corte).toBe("number");
    expect(typeof enviado?.dia_pago).toBe("number");
    expect(alta.crudos.at(0)).toContain('"dia_corte":4');
    expect(alta.crudos.at(0)).toContain('"dia_pago":6');

    // La lista se volvió a pedir y el proveedor nuevo aparece ACTIVO con jueves y sábado.
    await waitFor(() => expect(lista.pedidas).toHaveLength(2));
    const fila = await screen.findByRole("row", { name: new RegExp(`^${NOMBRE_NUEVO}`) });
    expect(celdasDe(fila).slice(0, 5)).toEqual([NOMBRE_NUEVO, RFC_NUEVO, "Activo", "jueves", "sábado"]);
  });

  test("hdu004_esc02 · TC-F19 · un RFC en minúsculas y con espacios se envía recortado y en mayúsculas", async () => {
    const existentes = [aceros(), copanel()];
    const alta = altaQueAcepta(existentes);
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: existentes, alta });

    const dialogo = await abrirFormulario(usuario);
    const controles = campos(dialogo);
    await capturarNombreYRfc(usuario, controles, `  ${NOMBRE_NUEVO}  `, ` ${RFC_NUEVO.toLowerCase()} `);
    await usuario.click(controles.guardar);

    await waitFor(sinFormulario);
    expect(alta.cuerpos.at(0)?.nombre).toBe(NOMBRE_NUEVO);
    expect(alta.cuerpos.at(0)?.rfc).toBe(RFC_NUEVO);
  });
});

describe("TKT-032a · TC-F20 · alta con tope, corte y pago distintos (CA-2, CA-R4; M-4)", () => {
  // «99999999999999.9999» es el mayor tope que admite el contrato (14 enteros y 4 decimales): pasado por `Number` se
  // convierte en 100000000000000 y pierde los decimales. «300000.00» conserva sus dos ceros solo si viaja como cadena.
  test.each(["300000.00", "99999999999999.9999"])(
    "hdu004_esc02 · TC-F20 · el tope %s viaja como cadena idéntica, sin pasar por número, y los días elegidos como enteros",
    async (tope) => {
      const existentes = [aceros(), copanel()];
      const alta = altaQueAcepta(existentes);
      const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: existentes, alta });

      const dialogo = await abrirFormulario(usuario);
      const controles = campos(dialogo);
      await capturarNombreYRfc(usuario, controles);
      await usuario.type(controles.tope, tope);
      await usuario.selectOptions(controles.corte, "martes");
      await usuario.selectOptions(controles.pago, "viernes");
      await usuario.click(controles.guardar);

      await waitFor(sinFormulario);
      expect(alta.cuerpos).toEqual([
        { nombre: NOMBRE_NUEVO, rfc: RFC_NUEVO, tope_consignacion: tope, dia_corte: 2, dia_pago: 5 } satisfies ProveedorNuevo,
      ]);
      // M-4: el cuerpo crudo y su tipo. Un tope que pasó por `Number` sale como número JSON y falla aquí.
      expect(typeof alta.cuerpos.at(0)?.tope_consignacion).toBe("string");
      expect(alta.crudos.at(0)).toContain(`"tope_consignacion":"${tope}"`);
      expect(typeof alta.cuerpos.at(0)?.dia_corte).toBe("number");
      expect(typeof alta.cuerpos.at(0)?.dia_pago).toBe("number");
    },
  );

  test("hdu004_esc02 · TC-F20 · el proveedor con tope y días distintos aparece en la lista con su corte y su pago", async () => {
    const existentes = [aceros(), copanel()];
    const alta = altaQueAcepta(existentes);
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { proveedores: existentes, alta });

    const dialogo = await abrirFormulario(usuario);
    const controles = campos(dialogo);
    await capturarNombreYRfc(usuario, controles);
    await usuario.type(controles.tope, "300000.00");
    await usuario.selectOptions(controles.corte, "lunes");
    await usuario.selectOptions(controles.pago, "domingo");
    await usuario.click(controles.guardar);

    await waitFor(sinFormulario);
    const fila = await screen.findByRole("row", { name: new RegExp(`^${NOMBRE_NUEVO}`) });
    expect(celdasDe(fila).slice(0, 5)).toEqual([NOMBRE_NUEVO, RFC_NUEVO, "Activo", "lunes", "domingo"]);
  });
});

describe("TKT-032a · TC-F21 · el RFC ya existe (CA-3, rechazo; H-1, D-9)", () => {
  function rfcDuplicado() {
    return dobleAlta(() =>
      HttpResponse.json(
        errorConflictoEstado("RFC_DUPLICADO", {
          mensaje: "Ya existe un proveedor con el RFC XAXX010101000.",
          detalle: { proveedor_existente: "CoPanel · XAXX010101000", proveedor_existente_id: ID_COPANEL },
          acciones: [],
        }),
        { status: 409 },
      ),
    );
  }

  test("hdu004_esc03 · TC-F21 · el formulario sigue abierto con lo capturado y el conflicto en línea nombra al proveedor existente; la lista no se vuelve a pedir", async () => {
    const alta = rfcDuplicado();
    const { usuario, lista } = await abrirPantallaConTabla([ROL_QUE_OPERA], { alta });
    const dialogo = await abrirFormulario(usuario);
    const controles = campos(dialogo);

    await capturarNombreYRfc(usuario, controles, "CoPanel Sucursal", "XAXX010101000");
    await usuario.click(controles.guardar);

    // El conflicto se pinta dentro del formulario, con el proveedor existente (nombre · RFC) y el mensaje del servidor.
    const conflicto = await within(dialogo).findByRole("region");
    expect(within(conflicto).getByText("No se puede completar")).toBeInTheDocument();
    expect(within(conflicto).getByText("Ya existe un proveedor con el RFC XAXX010101000.")).toBeInTheDocument();
    expect(within(conflicto).getByText("Proveedor existente", { selector: "dt" })).toBeInTheDocument();
    expect(within(conflicto).getByText("CoPanel · XAXX010101000", { selector: "dd" })).toBeInTheDocument();
    // Ni el identificador interno ni la clave cruda del detalle llegan a la vista.
    expect(dialogo).not.toHaveTextContent(ID_COPANEL);
    expect(within(dialogo).queryByText("proveedor_existente")).not.toBeInTheDocument();
    expect(within(dialogo).queryByText("proveedor_existente_id")).not.toBeInTheDocument();

    // El formulario no se cerró y conserva lo capturado.
    expect(screen.getByRole("dialog", { name: TITULO_FORMULARIO })).toBeInTheDocument();
    expect(controles.nombre).toHaveValue("CoPanel Sucursal");
    expect(controles.rfc).toHaveValue("XAXX010101000");
    expect(controles.corte).toHaveDisplayValue("jueves");
    expect(controles.pago).toHaveDisplayValue("sábado");
    expect(alta.cuerpos).toHaveLength(1);
    // Ninguna petición de lista más.
    expect(lista.pedidas).toHaveLength(1);
  });

  test("hdu004_esc03 · TC-F21 · ningún botón de acción: el servidor manda acciones [] y el cliente no cablea «ver al proveedor» (H-1)", async () => {
    const alta = rfcDuplicado();
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { alta });
    const dialogo = await abrirFormulario(usuario);
    await capturarNombreYRfc(usuario, campos(dialogo), "CoPanel Sucursal", "XAXX010101000");
    await usuario.click(campos(dialogo).guardar);

    const conflicto = await within(dialogo).findByRole("region");
    expect(within(conflicto).queryAllByRole("button")).toHaveLength(0);
    expect(within(dialogo).queryByRole("button", { name: /^Ver (al |el )?proveedor/i })).not.toBeInTheDocument();
    expect(within(dialogo).queryByRole("link")).not.toBeInTheDocument();
  });

  test("hdu004_esc03 · TC-F21 · no aparece ninguna fila nueva: la tabla conserva sus dos proveedores", async () => {
    const alta = rfcDuplicado();
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { alta });
    const dialogo = await abrirFormulario(usuario);
    await capturarNombreYRfc(usuario, campos(dialogo), "CoPanel Sucursal", "XAXX010101000");
    await usuario.click(campos(dialogo).guardar);
    await within(dialogo).findByRole("region");

    // `hidden`: con el diálogo abierto el resto de la página queda fuera del árbol de accesibilidad.
    expect(screen.queryByRole("cell", { name: "CoPanel Sucursal", hidden: true })).not.toBeInTheDocument();
    const filas = screen.getAllByRole("row", { hidden: true });
    expect(filas).toHaveLength(3);
  });

  test("hdu004_esc03 · TC-F21 · el RFC no se marca como error de forma: es un dato que ya existe, no un 422 (D-9)", async () => {
    const alta = rfcDuplicado();
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { alta });
    const dialogo = await abrirFormulario(usuario);
    const controles = campos(dialogo);
    await capturarNombreYRfc(usuario, controles, "CoPanel Sucursal", "XAXX010101000");
    await usuario.click(controles.guardar);
    await within(dialogo).findByRole("region");

    expect(controles.rfc).not.toHaveAttribute("aria-invalid", "true");
    expect(controles.nombre).not.toHaveAttribute("aria-invalid", "true");
  });
});

describe("TKT-032a · TC-F22 · el rechazo de forma, junto a su campo (CA-4, rechazo)", () => {
  const MENSAJES = {
    nombre: "El nombre admite hasta 200 caracteres.",
    rfc: "El RFC no tiene un formato válido.",
    tope_consignacion: "El tope admite hasta 14 enteros y 4 decimales.",
    dia_corte: "El día de corte debe estar entre 1 y 7.",
    dia_pago: "El día de pago debe estar entre 1 y 7.",
  } as const;

  type CampoServidor = keyof typeof MENSAJES;
  const CONTROL_DE: Readonly<Record<CampoServidor, (controles: Controles) => HTMLElement>> = {
    nombre: (controles) => controles.nombre,
    rfc: (controles) => controles.rfc,
    tope_consignacion: (controles) => controles.tope,
    dia_corte: (controles) => controles.corte,
    dia_pago: (controles) => controles.pago,
  };
  const CAMPOS_DEL_SERVIDOR = Object.keys(MENSAJES) as CampoServidor[];

  test.each(CAMPOS_DEL_SERVIDOR)(
    "tkt032a_alta · TC-F22 · un 422 en %s se pinta junto a su campo con aria-invalid, el formulario sigue abierto y lo capturado se conserva",
    async (campo) => {
      const mensaje = MENSAJES[campo];
      const alta = dobleAlta(() =>
        HttpResponse.json(errorValidacion([{ campo, codigo: "FORMATO", mensaje }]), { status: 422 }),
      );
      const { usuario, lista } = await abrirPantallaConTabla([ROL_QUE_OPERA], { alta });
      const dialogo = await abrirFormulario(usuario);
      const controles = campos(dialogo);
      await capturarNombreYRfc(usuario, controles);
      await usuario.type(controles.tope, "300000.00");
      await usuario.click(controles.guardar);

      expect(await within(dialogo).findByText(mensaje)).toBeInTheDocument();
      const afectado = CONTROL_DE[campo](controles);
      expect(afectado).toHaveAttribute("aria-invalid", "true");
      expect(afectado).toHaveAccessibleDescription(mensaje);
      // Solo ese campo queda marcado.
      for (const otro of CAMPOS_DEL_SERVIDOR.filter((candidato) => candidato !== campo)) {
        expect(CONTROL_DE[otro](controles)).not.toHaveAttribute("aria-invalid", "true");
      }
      // El cliente envió el cuerpo y fue el servidor quien lo rechazó; el formulario conserva lo capturado y sigue abierto.
      expect(alta.cuerpos).toHaveLength(1);
      expect(controles.nombre).toHaveValue(NOMBRE_NUEVO);
      expect(controles.rfc).toHaveValue(RFC_NUEVO);
      expect(controles.tope).toHaveValue("300000.00");
      expect(screen.getByRole("dialog", { name: TITULO_FORMULARIO })).toBeInTheDocument();
      // No es un bloqueo de negocio ni vuelve a pedirse la lista.
      expect(within(dialogo).queryByRole("region")).not.toBeInTheDocument();
      expect(lista.pedidas).toHaveLength(1);
    },
  );

  test("tkt032a_alta · TC-F22 · un nombre vacío se rechaza antes de enviar, junto a su campo, y no sale ninguna petición", async () => {
    const alta = dobleAlta(() => HttpResponse.json(proveedor(), { status: 201 }));
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { alta });
    const dialogo = await abrirFormulario(usuario);
    const controles = campos(dialogo);
    await usuario.type(controles.rfc, RFC_NUEVO);
    await usuario.click(controles.guardar);

    expect(await within(dialogo).findByText(MENSAJE_NOMBRE_VACIO)).toBeInTheDocument();
    expect(controles.nombre).toHaveAttribute("aria-invalid", "true");
    expect(controles.nombre).toHaveAccessibleDescription(MENSAJE_NOMBRE_VACIO);
    expect(controles.rfc).not.toHaveAttribute("aria-invalid", "true");
    expect(alta.cuerpos).toHaveLength(0);
    expect(screen.getByRole("dialog", { name: TITULO_FORMULARIO })).toBeInTheDocument();
  });

  test("tkt032a_alta · TC-F22 · un nombre de solo espacios cuenta como vacío: no se envía", async () => {
    const alta = dobleAlta(() => HttpResponse.json(proveedor(), { status: 201 }));
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { alta });
    const dialogo = await abrirFormulario(usuario);
    const controles = campos(dialogo);
    await usuario.type(controles.nombre, "     ");
    await usuario.type(controles.rfc, RFC_NUEVO);
    await usuario.click(controles.guardar);

    expect(await within(dialogo).findByText(MENSAJE_NOMBRE_VACIO)).toBeInTheDocument();
    expect(alta.cuerpos).toHaveLength(0);
  });

  test("tkt032a_alta · TC-F22 · un RFC mal formado se rechaza antes de enviar, junto a su campo, y no sale ninguna petición", async () => {
    const alta = dobleAlta(() => HttpResponse.json(proveedor(), { status: 201 }));
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { alta });
    const dialogo = await abrirFormulario(usuario);
    const controles = campos(dialogo);
    await usuario.type(controles.nombre, NOMBRE_NUEVO);
    await usuario.type(controles.rfc, "XX123");
    await usuario.click(controles.guardar);

    expect(await within(dialogo).findByText(MENSAJE_RFC_MALFORMADO)).toBeInTheDocument();
    expect(controles.rfc).toHaveAttribute("aria-invalid", "true");
    expect(controles.nombre).not.toHaveAttribute("aria-invalid", "true");
    expect(alta.cuerpos).toHaveLength(0);
    expect(screen.getByRole("dialog", { name: TITULO_FORMULARIO })).toBeInTheDocument();
  });

  test("tkt032a_alta · TC-F22 · un tope que no es decimal plano («1e3») se rechaza antes de enviar y no sale ninguna petición (CA-R4)", async () => {
    const alta = dobleAlta(() => HttpResponse.json(proveedor(), { status: 201 }));
    const { usuario } = await abrirPantallaConTabla([ROL_QUE_OPERA], { alta });
    const dialogo = await abrirFormulario(usuario);
    const controles = campos(dialogo);
    await capturarNombreYRfc(usuario, controles);
    await usuario.type(controles.tope, "1e3");
    await usuario.click(controles.guardar);

    expect(await within(dialogo).findByText(MENSAJE_TOPE_INVALIDO)).toBeInTheDocument();
    expect(controles.tope).toHaveAttribute("aria-invalid", "true");
    expect(alta.cuerpos).toHaveLength(0);
  });
});

describe("TKT-032a · un 403 del alta se pinta en el formulario sin cerrarlo (CA-9, D-6; rechazo)", () => {
  test("tkt032a_alta · un 403 muestra «Tu rol no permite esta operación.» sin cifras ni tratamiento de bloqueo, y el formulario sigue abierto", async () => {
    const alta = dobleAlta(() =>
      HttpResponse.json({ ...errorPermiso("ROL_INSUFICIENTE"), mensaje: MENSAJE_SIN_PERMISO }, { status: 403 }),
    );
    const { usuario, lista } = await abrirPantallaConTabla([ROL_QUE_OPERA], { alta });
    const dialogo = await abrirFormulario(usuario);
    const controles = campos(dialogo);
    await capturarNombreYRfc(usuario, controles);
    await usuario.click(controles.guardar);

    expect(await within(dialogo).findByText(new RegExp(MENSAJE_SIN_PERMISO))).toBeInTheDocument();
    // No es un bloqueo de negocio: ni cabecera de bloqueo, ni cifras, ni acciones.
    expect(within(dialogo).queryByRole("region")).not.toBeInTheDocument();
    expect(within(dialogo).queryByText("Operación bloqueada")).not.toBeInTheDocument();
    expect(within(dialogo).queryByText("No se puede completar")).not.toBeInTheDocument();
    expect(within(dialogo).queryByText(/disponible|excedente|presupuestado/i)).not.toBeInTheDocument();
    // El formulario sigue abierto, conserva lo capturado y no pide la lista de nuevo.
    expect(screen.getByRole("dialog", { name: TITULO_FORMULARIO })).toBeInTheDocument();
    expect(controles.nombre).toHaveValue(NOMBRE_NUEVO);
    expect(controles.rfc).toHaveValue(RFC_NUEVO);
    expect(alta.cuerpos).toHaveLength(1);
    expect(lista.pedidas).toHaveLength(1);
  });
});
