import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import type { components as Servidor } from "@/api/generado/servidor";
import type { Rol } from "@/api/sesion";
import { errorConflictoEstado, errorValidacion, obra as obraBase, tokenCsrf, usuarioActual } from "@/pruebas/cuerpos";
import { renderizarAplicacion } from "@/pruebas/render";
import { servidorPruebas } from "@/pruebas/servidor";

// TKT-012b · fila B3 · TC-69 a TC-72 (CA-14, CA-15, CA-4). La pantalla se prueba montada en `/obras` dentro de la
// aplicación completa, con MSW como servidor, igual que `PantallaObras.test.tsx` (que no se toca: su prueba de la
// línea 529 fija que los lectores ven exactamente Código, Nombre y Estado). Las respuestas se construyen con los
// tipos generados del OpenAPI (`satisfies`). El comportamiento de Suspender, Reactivar, Cerrar y Eliminar es de B4:
// aquí solo se prueba que la fila los ofrece o no.

type Esquemas = Servidor["schemas"];
type Obra = Esquemas["Obra"];
type ObraCambios = Esquemas["ObraCambios"];
type EstadoObra = Esquemas["EstadoObra"];

const ORIGEN = globalThis.location.origin;
const RUTA_SESION = "/api/v1/sesion";
const RUTA_CSRF = "/api/v1/sesion/csrf";
const RUTA_OBRAS = "/api/v1/obras";
const RUTA_PANTALLA = "/obras";

const TIPO_CONTRATO = "PRECIO_ALZADO_MAXIMO_GARANTIZADO";
const ENCABEZADO_ACCIONES = "Acciones";
// (asumido) El título del diálogo de edición no lo fija ninguna spec: se acepta «Editar obra» o «Edición de obra».
const TITULO_EDICION = /editar|edici[oó]n/i;
const TITULO_ALTA = "Alta de obra";

const ID_PLANEACION = "9a1f2b3c-4d5e-4f60-8a71-b2c3d4e5f607";
const ID_ACTIVA = "5d6e7f80-91a2-4b3c-84d5-e6f708192031";
const ID_SUSPENDIDA = "6e7f8091-a2b3-4c4d-95e6-f70819203142";
const ID_CERRADA = "7f8091a2-b3c4-4d5e-a6f7-081920314253";

const ROLES_QUE_OPERAN: Rol[] = ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL"];
const ROLES_SIN_ESCRITURA: Rol[] = ["RESIDENTE", "COMPRAS", "ALMACEN", "ADMINISTRACION"];
const ESTADOS: EstadoObra[] = ["PLANEACION", "ACTIVA", "SUSPENDIDA", "CERRADA"];
const ESTADOS_EDITABLES: EstadoObra[] = ["PLANEACION", "ACTIVA", "SUSPENDIDA"];

/** CA-14 (con D-DIS-1): lo que ofrece la fila del Director de Proyectos y de la Dirección General, en este orden. */
const ACCIONES_ESPERADAS: Readonly<Record<EstadoObra, readonly string[]>> = {
  PLANEACION: ["Editar", "Eliminar", "Cerrar"],
  ACTIVA: ["Editar", "Suspender", "Cerrar"],
  SUSPENDIDA: ["Editar", "Reactivar", "Cerrar"],
  CERRADA: [],
};

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

function dobleSesion(roles: Rol[]) {
  return http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(usuarioActual(roles)));
}

function dobleCsrf() {
  return http.get(`${ORIGEN}${RUTA_CSRF}`, () => HttpResponse.json(tokenCsrf()));
}

/** GET /obras. `obras` es la lista viva del servidor: una edición la modifica y la siguiente petición la ve. */
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

/** PATCH /obras/{obra_id}. Guarda el identificador y el cuerpo de cada petición y responde lo que decide la prueba. */
function dobleEdicion(responder: (cuerpo: ObraCambios, obraId: string) => Response) {
  const recibidas: { obraId: string; cuerpo: ObraCambios }[] = [];
  const handler = http.patch(`${ORIGEN}${RUTA_OBRAS}/:obraId`, async ({ request, params }) => {
    const cuerpo = (await request.json()) as ObraCambios;
    const obraId = String(params.obraId);
    recibidas.push({ obraId, cuerpo });
    return responder(cuerpo, obraId);
  });
  return { handler, recibidas };
}

interface OpcionesPantalla {
  obras: Obra[];
  edicion?: ReturnType<typeof dobleEdicion>;
}

/** Monta la aplicación en `/obras` con la sesión del rol y espera a la sesión y a la tabla. */
async function abrirPantallaConTabla(roles: Rol[], { obras, edicion }: OpcionesPantalla) {
  const lista = dobleLista(obras);
  servidorPruebas.use(dobleSesion(roles), dobleCsrf(), lista.handler);
  if (edicion !== undefined) servidorPruebas.use(edicion.handler);
  const aplicacion = renderizarAplicacion(RUTA_PANTALLA);
  await screen.findByText(/Rosa Villanueva/);
  await screen.findByRole("table");
  return { ...aplicacion, lista };
}

function filaDe(codigo: string) {
  return within(screen.getByRole("table")).getByRole("row", { name: new RegExp(codigo) });
}

/** Las acciones de una fila, por el primer vocablo de su nombre accesible («Editar» o «Editar AP-058-25» dan lo mismo). */
function accionesDe(fila: HTMLElement): string[] {
  return within(fila)
    .queryAllByRole("button")
    .map((boton) => (boton.getAttribute("aria-label") ?? boton.textContent).trim().split(/\s+/)[0] ?? "");
}

async function abrirEdicion(usuario: ReturnType<typeof renderizarAplicacion>["usuario"], codigo: string) {
  await usuario.click(within(filaDe(codigo)).getByRole("button", { name: /^Editar\b/ }));
  return screen.findByRole("dialog", { name: TITULO_EDICION });
}

/** Los controles del formulario de edición, por su etiqueta visible: rol y nombre, nunca clases ni estructura. */
function campos(dialogo: HTMLElement) {
  const dentro = within(dialogo);
  return {
    codigo: dentro.getByRole("textbox", { name: /código/i }),
    nombre: dentro.getByRole("textbox", { name: /nombre/i }),
    domicilio: dentro.getByRole("textbox", { name: /domicilio/i }),
    tipoContrato: dentro.getByRole("combobox", { name: /tipo de contrato/i }),
    retencion: dentro.getByRole("textbox", { name: /retenci[oó]n/i }),
    fondo: dentro.getByRole("textbox", { name: /fondo de garant[ií]a/i }),
    umbral: dentro.getByRole("textbox", { name: /umbral/i }),
    iva: dentro.getByRole("checkbox", { name: /IVA acreditable/i }),
    guardar: dentro.getByRole("button", { name: "Guardar" }),
  };
}

/** El valor de un rótulo del detalle de un rechazo (`dt` y su `dd`), dentro de su región. */
function valorEn(region: HTMLElement, rotulo: string): string {
  const termino = within(region).getByText(rotulo, { selector: "dt" });
  return termino.nextElementSibling?.textContent.trim() ?? "";
}

describe("TKT-012b · TC-69 · la fila ofrece las acciones que proceden según estado y rol (CA-14)", () => {
  const casos = ROLES_QUE_OPERAN.flatMap((rol) => ESTADOS.map((estado) => [rol, estado] as const));

  test.each(casos)("tkt012b_ca14 · TC-69 · %s con la obra en %s: la fila ofrece lo de CA-14, en su orden", async (rol, estado) => {
    await abrirPantallaConTabla([rol], { obras: [obraEn(estado)] });

    const tabla = screen.getByRole("table");
    expect(within(tabla).getByRole("columnheader", { name: ENCABEZADO_ACCIONES })).toBeInTheDocument();
    expect(accionesDe(filaDe(CODIGO_POR_ESTADO[estado]))).toEqual(ACCIONES_ESPERADAS[estado]);
  });

  test("tkt012b_ca14 · TC-69 · con las cuatro obras en la lista, cada fila ofrece lo suyo y no lo de otra", async () => {
    await abrirPantallaConTabla(["DIRECTOR_PROYECTOS"], { obras: ESTADOS.map((estado) => obraEn(estado)) });

    for (const estado of ESTADOS) {
      expect(accionesDe(filaDe(CODIGO_POR_ESTADO[estado]))).toEqual(ACCIONES_ESPERADAS[estado]);
    }
  });

  test.each(ROLES_SIN_ESCRITURA)(
    "tkt012b_ca14 · TC-69 · rechazo: %s ve la lista, sin columna «Acciones» ni ningún botón de acción en ninguna fila",
    async (rol) => {
      await abrirPantallaConTabla([rol], { obras: ESTADOS.map((estado) => obraEn(estado)) });

      const tabla = screen.getByRole("table");
      // La lista sí se ve: el rechazo es de las acciones, no de la pantalla.
      for (const estado of ESTADOS) {
        expect(within(tabla).getByRole("cell", { name: CODIGO_POR_ESTADO[estado] })).toBeInTheDocument();
      }
      expect(within(tabla).queryByRole("columnheader", { name: ENCABEZADO_ACCIONES })).not.toBeInTheDocument();
      expect(within(tabla).queryAllByRole("button")).toHaveLength(0);
      expect(screen.queryByRole("button", { name: /^(Editar|Eliminar|Suspender|Reactivar|Cerrar)\b/ })).not.toBeInTheDocument();
    },
  );
});

describe("TKT-012b · TC-70 · Editar abre el formulario con la obra y guarda sin recargar (CA-15)", () => {
  test.each(ESTADOS_EDITABLES)(
    "tkt012b_ca15 · TC-70 · obra %s: el formulario se abre con los valores de la obra, y el código y el tipo de contrato solo de lectura",
    async (estado) => {
      const existente = obraEn(estado, {
        domicilio: "Av. Constituyentes 120, Querétaro",
        retencion_destajo_pct: "0.150000",
        fondo_garantia_pct: "0.055000",
        umbral_alerta_pct: "0.800000",
        iva_acreditable: true,
      });
      const { usuario } = await abrirPantallaConTabla(["DIRECTOR_PROYECTOS"], { obras: [existente] });

      const dialogo = await abrirEdicion(usuario, existente.codigo);

      const controles = campos(dialogo);
      expect(controles.nombre).toHaveValue(existente.nombre);
      expect(controles.domicilio).toHaveValue("Av. Constituyentes 120, Querétaro");
      // Las fracciones del servidor se muestran como se teclean, sin pérdida: 5.5, no 5.50000 ni 0.055.
      expect(controles.retencion).toHaveValue("15");
      expect(controles.fondo).toHaveValue("5.5");
      expect(controles.umbral).toHaveValue("80");
      expect(controles.iva).toBeChecked();
      // Solo lectura: se ven con su valor y no se pueden editar.
      expect(controles.codigo).toHaveValue(existente.codigo);
      expect(controles.codigo).toHaveAttribute("readonly");
      expect(controles.tipoContrato).toHaveValue(TIPO_CONTRATO);
      expect(controles.tipoContrato).toBeDisabled();
      // No es el formulario del alta.
      expect(screen.queryByRole("dialog", { name: TITULO_ALTA })).not.toBeInTheDocument();
    },
  );

  test("tkt012b_ca15 · TC-70 · una obra sin umbral abre con el umbral vacío", async () => {
    const existente = obraEn("ACTIVA", { umbral_alerta_pct: null, iva_acreditable: false });
    const { usuario } = await abrirPantallaConTabla(["DIRECTOR_PROYECTOS"], { obras: [existente] });

    const dialogo = await abrirEdicion(usuario, existente.codigo);

    expect(campos(dialogo).umbral).toHaveValue("");
    expect(campos(dialogo).iva).not.toBeChecked();
  });

  test("tkt012b_ca15 · TC-70 · guardar envía solo los campos editables a la obra de la fila, cierra el formulario y la lista muestra el nombre nuevo sin recargar", async () => {
    const primera = obraEn("PLANEACION");
    const segunda = obraEn("ACTIVA", { umbral_alerta_pct: "0.800000", fondo_garantia_pct: "0.050000", iva_acreditable: true });
    const obras = [primera, segunda];
    const edicion = dobleEdicion((cuerpo, obraId) => {
      const actualizada = { ...segunda, nombre: cuerpo.nombre ?? segunda.nombre } satisfies Obra;
      obras[obras.findIndex((candidata) => candidata.id === obraId)] = actualizada;
      return HttpResponse.json(actualizada);
    });
    const { usuario, lista, router } = await abrirPantallaConTabla(["DIRECTOR_PROYECTOS"], { obras, edicion });
    expect(lista.pedidas).toHaveLength(1);

    // Se edita la segunda fila: con la primera, un botón que editara siempre la primera obra pasaría.
    const dialogo = await abrirEdicion(usuario, segunda.codigo);
    const controles = campos(dialogo);
    await usuario.clear(controles.nombre);
    await usuario.type(controles.nombre, "Torre Reforma Norte Fase 2");
    await usuario.click(controles.guardar);

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(edicion.recibidas).toEqual([
      {
        obraId: segunda.id,
        cuerpo: {
          nombre: "Torre Reforma Norte Fase 2",
          domicilio: segunda.domicilio,
          retencion_destajo_pct: "0.150000",
          fondo_garantia_pct: "0.050000",
          umbral_alerta_pct: "0.800000",
          iva_acreditable: true,
        } satisfies ObraCambios,
      },
    ]);
    // El código, el tipo de contrato y el estado no viajan (CA-2): lo de solo lectura no sale del formulario.
    const [enviada] = edicion.recibidas;
    expect(enviada?.cuerpo).not.toHaveProperty("codigo");
    expect(enviada?.cuerpo).not.toHaveProperty("tipo_contrato");
    expect(enviada?.cuerpo).not.toHaveProperty("estado");

    // La lista se volvió a pedir, sin recargar la página, y muestra el nombre nuevo solo en la fila editada.
    await waitFor(() => expect(lista.pedidas).toHaveLength(2));
    expect(await screen.findByRole("cell", { name: "Torre Reforma Norte Fase 2" })).toBeInTheDocument();
    expect(screen.queryByRole("cell", { name: segunda.nombre })).not.toBeInTheDocument();
    expect(within(filaDe(primera.codigo)).getByRole("cell", { name: primera.nombre })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe(RUTA_PANTALLA);
  });
});

describe("TKT-012b · TC-71 · un 422 al editar cae junto a su campo (CA-15, rechazo)", () => {
  test("tkt012b_ca15 · TC-71 · el mensaje del servidor se pinta junto al campo, el formulario sigue abierto con lo escrito y la lista no se vuelve a pedir", async () => {
    const mensaje = "La retención debe estar entre 0 y 100 %.";
    const edicion = dobleEdicion(() =>
      HttpResponse.json(errorValidacion([{ campo: "retencion_destajo_pct", codigo: "FUERA_DE_RANGO", mensaje }]), { status: 422 }),
    );
    const existente = obraEn("ACTIVA");
    const { usuario, lista } = await abrirPantallaConTabla(["DIRECTOR_PROYECTOS"], { obras: [existente], edicion });
    const dialogo = await abrirEdicion(usuario, existente.codigo);
    const controles = campos(dialogo);

    await usuario.clear(controles.retencion);
    await usuario.type(controles.retencion, "120");
    await usuario.click(controles.guardar);

    expect(await within(dialogo).findByText(mensaje)).toBeInTheDocument();
    expect(controles.retencion).toHaveAttribute("aria-invalid", "true");
    expect(controles.retencion).toHaveAccessibleDescription(mensaje);
    expect(controles.fondo).not.toHaveAttribute("aria-invalid", "true");
    // El cliente no evalúa el rango: envió 120 % como fracción y fue el servidor quien lo rechazó.
    expect(edicion.recibidas).toHaveLength(1);
    expect(edicion.recibidas.at(0)?.cuerpo.retencion_destajo_pct).toBe("1.200000");
    // No es una pantalla aparte ni un bloqueo: sigue el mismo formulario, con lo escrito.
    expect(screen.getByRole("dialog", { name: TITULO_EDICION })).toBeInTheDocument();
    expect(controles.retencion).toHaveValue("120");
    expect(controles.nombre).toHaveValue(existente.nombre);
    expect(within(dialogo).queryByRole("region")).not.toBeInTheDocument();
    expect(lista.pedidas).toHaveLength(1);
  });
});

describe("TKT-012b · TC-72 · editar una obra que otra pestaña cerró (CA-4, rechazo)", () => {
  test("tkt012b_ca04 · TC-72 · el 409 ESTADO_NO_PERMITE_OPERACION se pinta en línea con su mensaje y el estado, como conflicto y no como error", async () => {
    const mensaje = "La obra AP-061-25 está en CERRADA y no admite esta operación.";
    const edicion = dobleEdicion(() =>
      HttpResponse.json(
        errorConflictoEstado("ESTADO_NO_PERMITE_OPERACION", { mensaje, detalle: { estado: "CERRADA" }, acciones: [] }),
        { status: 409 },
      ),
    );
    // La lista de esta pestaña aún la tiene ACTIVA: la otra pestaña la cerró después de cargarse.
    const existente = obraEn("ACTIVA");
    const { usuario, lista } = await abrirPantallaConTabla(["DIRECTOR_PROYECTOS"], { obras: [existente], edicion });
    const dialogo = await abrirEdicion(usuario, existente.codigo);
    const controles = campos(dialogo);

    await usuario.clear(controles.nombre);
    await usuario.type(controles.nombre, "Nombre que ya no se puede guardar");
    await usuario.click(controles.guardar);

    // El contrato completo: tratamiento de conflicto con su código, el mensaje del servidor y el estado del detalle.
    const conflicto = await within(dialogo).findByRole("region", { name: "No se puede completar" });
    expect(conflicto).toHaveAttribute("data-estado", "bloqueado");
    expect(within(conflicto).getByText("ESTADO_NO_PERMITE_OPERACION")).toBeInTheDocument();
    expect(within(conflicto).getByText(mensaje)).toBeInTheDocument();
    expect(valorEn(conflicto, "Estado")).toBe("CERRADA");
    // No es un error ni una regla de negocio, y el servidor no ofreció acciones.
    expect(within(dialogo).queryByRole("alert")).not.toBeInTheDocument();
    expect(within(dialogo).queryByText("Operación bloqueada")).not.toBeInTheDocument();
    expect(within(conflicto).queryAllByRole("button")).toHaveLength(0);
    // El formulario sigue abierto con lo escrito, la petición salió una vez y la lista no cambia.
    expect(screen.getByRole("dialog", { name: TITULO_EDICION })).toBeInTheDocument();
    expect(controles.nombre).toHaveValue("Nombre que ya no se puede guardar");
    expect(edicion.recibidas).toHaveLength(1);
    expect(lista.pedidas).toHaveLength(1);
    // El diálogo es modal y deja la tabla fuera del árbol de accesibilidad: se consulta con `hidden`, dentro de la tabla.
    const celdas = within(screen.getByRole("table", { hidden: true })).getAllByRole("cell", { hidden: true });
    expect(celdas.map((celda) => celda.textContent)).toContain(existente.nombre);
    expect(celdas.map((celda) => celda.textContent)).not.toContain("Nombre que ya no se puede guardar");
  });
});
