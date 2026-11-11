import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import type { components as Servidor } from "@/api/generado/servidor";
import type { Rol } from "@/api/sesion";
import {
  errorConflictoEstado,
  errorPermiso,
  errorValidacion,
  lineaBase,
  obra as obraBase,
  tokenCsrf,
  usuarioActual,
} from "@/pruebas/cuerpos";
import { renderizarAplicacion } from "@/pruebas/render";
import { servidorPruebas } from "@/pruebas/servidor";

// TKT-012a · fila B4 · TC-F06 a TC-F11 (CA-9 a CA-12). La pantalla se prueba montada en su ruta `/obras` dentro de la
// aplicación completa, con MSW como servidor: así la prueba no importa ningún módulo nuevo y cada caso falla por el
// comportamiento ausente (hoy la ruta pinta el marcador «Esta sección aún no está disponible»).
// Las respuestas se construyen con los tipos generados del OpenAPI (`satisfies`).

type Esquemas = Servidor["schemas"];
type Obra = Esquemas["Obra"];
type ObraNueva = Esquemas["ObraNueva"];

const ORIGEN = globalThis.location.origin;
const RUTA_SESION = "/api/v1/sesion";
const RUTA_CSRF = "/api/v1/sesion/csrf";
const RUTA_OBRAS = "/api/v1/obras";
const RUTA_PANTALLA = "/obras";

const ETIQUETA_ALTA = "Dar de alta una obra";
const TITULO_FORMULARIO = "Alta de obra";
const TIPO_CONTRATO = "PRECIO_ALZADO_MAXIMO_GARANTIZADO";
const MENSAJE_SIN_PERMISO = "Tu rol no permite esta operación.";
const CORRELACION_ID = "7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e";
const ID_OBRA_EXISTENTE = "9a1f2b3c-4d5e-4f60-8a71-b2c3d4e5f607";
const ID_OBRA_NUEVA = "4c5d6e7f-8091-4a2b-b3c4-d5e6f7081920";
const ID_OBRA_TERCERA = "5d6e7f80-91a2-4b3c-84d5-e6f708192031";

const ROLES_QUE_DAN_DE_ALTA: Rol[] = ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL"];
const ROLES_QUE_SOLO_LEEN: Rol[] = ["RESIDENTE", "COMPRAS", "ALMACEN", "ADMINISTRACION"];

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

function obra(cambios: Partial<Obra> = {}): Obra {
  return obraBase({ id: ID_OBRA_EXISTENTE, creado_en: "2026-11-10T15:00:00Z", ...cambios });
}

function obraTercera(): Obra {
  return obra({ id: ID_OBRA_TERCERA, codigo: "AP-061-25", nombre: "Torre Reforma Norte", estado: "ACTIVA" });
}

function dobleSesion(roles: Rol[]) {
  return http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(usuarioActual(roles)));
}

function dobleCsrf() {
  return http.get(`${ORIGEN}${RUTA_CSRF}`, () => HttpResponse.json(tokenCsrf()));
}

/** GET /obras. `obras` es la lista viva del servidor: un alta la modifica y la siguiente petición la ve. */
function dobleLista(obras: Obra[], opciones: { total?: number; espera?: Promise<void> } = {}) {
  const pedidas: URL[] = [];
  const handler = http.get(`${ORIGEN}${RUTA_OBRAS}`, async ({ request }) => {
    pedidas.push(new URL(request.url));
    if (opciones.espera !== undefined) await opciones.espera;
    return HttpResponse.json({
      elementos: obras,
      paginacion: { pagina: 1, tamano_pagina: 200, total: opciones.total ?? obras.length },
    } satisfies Esquemas["ListaObras"]);
  });
  return { handler, pedidas };
}

function dobleListaConFallo() {
  return http.get(`${ORIGEN}${RUTA_OBRAS}`, () =>
    HttpResponse.json({ mensaje: "Error interno del servidor.", correlacion_id: CORRELACION_ID }, { status: 500 }),
  );
}

/** POST /obras. Guarda cada cuerpo recibido y responde lo que decide la prueba. */
function dobleAlta(responder: (cuerpo: ObraNueva) => Response) {
  const cuerpos: ObraNueva[] = [];
  const handler = http.post(`${ORIGEN}${RUTA_OBRAS}`, async ({ request }) => {
    const cuerpo = (await request.json()) as ObraNueva;
    cuerpos.push(cuerpo);
    return responder(cuerpo);
  });
  return { handler, cuerpos };
}

interface OpcionesPantalla {
  obras?: Obra[];
  total?: number;
  alta?: ReturnType<typeof dobleAlta>;
}

/** Monta la aplicación en `/obras` con la sesión del rol, espera a que la sesión cargue y devuelve la lista y el alta dobladas. */
async function abrirPantalla(roles: Rol[], { obras = [obra()], total, alta }: OpcionesPantalla = {}) {
  const lista = dobleLista(obras, { total });
  servidorPruebas.use(dobleSesion(roles), dobleCsrf(), lista.handler);
  if (alta !== undefined) servidorPruebas.use(alta.handler);
  const aplicacion = renderizarAplicacion(RUTA_PANTALLA);
  await screen.findByText(/Rosa Villanueva/);
  return { ...aplicacion, lista };
}

/** Pantalla con obras ya pintadas (espera a la tabla). */
async function abrirPantallaConTabla(roles: Rol[], opciones: OpcionesPantalla = {}) {
  const pantalla = await abrirPantalla(roles, opciones);
  await screen.findByRole("table");
  return pantalla;
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

async function capturarObra(usuario: Usuario, dialogo: HTMLElement, codigo = "AP-012-26") {
  const { codigo: campoCodigo, nombre, domicilio } = campos(dialogo);
  await usuario.type(campoCodigo, codigo);
  await usuario.type(nombre, "Plaza Jurica Etapa 2");
  await usuario.type(domicilio, "Blvd. Bernardo Quintana 4100, Querétaro");
}

const sinFormulario = () => expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

describe("TKT-012a · TC-F06 · los cuatro estados de la lista de obras (CA-12)", () => {
  test("tkt012a_ca12 · TC-F06 · cargando: un esqueleto con aria-busy, no un contenido vacío", async () => {
    const compuerta = diferido();
    const lista = dobleLista([obra()], { espera: compuerta.promesa });
    servidorPruebas.use(dobleSesion(["DIRECTOR_PROYECTOS"]), dobleCsrf(), lista.handler);
    renderizarAplicacion(RUTA_PANTALLA);
    await screen.findByText(/Rosa Villanueva/);

    await waitFor(() => expect(lista.pedidas).toHaveLength(1));
    expect(document.querySelector('[aria-busy="true"]')).not.toBeNull();
    expect(screen.queryByText("No hay obras")).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();

    compuerta.resolver();
    expect(await screen.findByRole("table")).toBeInTheDocument();
    expect(document.querySelector('[aria-busy="true"]')).toBeNull();
  });

  test.each(ROLES_QUE_DAN_DE_ALTA)("tkt012a_ca12 · TC-F06 · vacío para %s: «No hay obras» y la acción de dar de alta", async (rol) => {
    await abrirPantalla([rol], { obras: [] });

    expect(await screen.findByText("No hay obras")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: ETIQUETA_ALTA }).length).toBeGreaterThan(0);
  });

  test.each(ROLES_QUE_SOLO_LEEN)("tkt012a_ca12 · TC-F06 · vacío para %s: «No hay obras» sin acción de dar de alta", async (rol) => {
    await abrirPantalla([rol], { obras: [] });

    expect(await screen.findByText("No hay obras")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: ETIQUETA_ALTA })).not.toBeInTheDocument();
  });

  test("tkt012a_ca12 · TC-F06 · con obras: tabla con código, nombre y estado, y sin nota si están todas", async () => {
    const { lista } = await abrirPantallaConTabla(["DIRECTOR_PROYECTOS"], { obras: [obra(), obraTercera()] });

    const tabla = screen.getByRole("table");
    expect(within(tabla).getByRole("columnheader", { name: "Código" })).toBeInTheDocument();
    expect(within(tabla).getByRole("columnheader", { name: "Nombre" })).toBeInTheDocument();
    expect(within(tabla).getByRole("columnheader", { name: "Estado" })).toBeInTheDocument();

    const primera = within(tabla).getByRole("row", { name: /AP-058-25/ });
    expect(within(primera).getByRole("cell", { name: "AP-058-25" })).toBeInTheDocument();
    expect(within(primera).getByRole("cell", { name: "Union Square F2" })).toBeInTheDocument();
    expect(within(primera).getByText(/planeaci[oó]n/i)).toBeInTheDocument();
    const segunda = within(tabla).getByRole("row", { name: /AP-061-25/ });
    expect(within(segunda).getByRole("cell", { name: "Torre Reforma Norte" })).toBeInTheDocument();
    expect(within(segunda).getByText(/activa/i)).toBeInTheDocument();

    expect(screen.queryByText(/Mostrando/)).not.toBeInTheDocument();
    // La pantalla pide la lista completa en una sola página (diseño: pagina 1, tamano_pagina 200).
    const [pedida] = lista.pedidas;
    expect(pedida?.searchParams.get("pagina")).toBe("1");
    expect(pedida?.searchParams.get("tamano_pagina")).toBe("200");
  });

  test("tkt012a_ca12 · TC-F06 · con obras y más de las que caben: la nota «Mostrando N de T obras»", async () => {
    await abrirPantallaConTabla(["DIRECTOR_PROYECTOS"], { obras: [obra(), obraTercera()], total: 5 });

    expect(screen.getByText("Mostrando 2 de 5 obras")).toBeInTheDocument();
  });

  test("tkt012a_ca12 · TC-F06 · error: el aviso lleva el correlacion_id y «Reintentar» vuelve a pedir la lista", async () => {
    servidorPruebas.use(dobleSesion(["DIRECTOR_PROYECTOS"]), dobleCsrf(), dobleListaConFallo());
    const { usuario } = renderizarAplicacion(RUTA_PANTALLA);
    await screen.findByText(/Rosa Villanueva/);

    expect(await screen.findByText(new RegExp(CORRELACION_ID))).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByText("No hay obras")).not.toBeInTheDocument();

    const recuperada = dobleLista([obra()]);
    servidorPruebas.use(recuperada.handler);
    await usuario.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByRole("cell", { name: "AP-058-25" })).toBeInTheDocument();
    expect(recuperada.pedidas).toHaveLength(1);
    expect(screen.queryByText(new RegExp(CORRELACION_ID))).not.toBeInTheDocument();
  });
});

describe("TKT-012a · TC-F07 · el botón + abre el formulario (CA-9)", () => {
  test.each(ROLES_QUE_DAN_DE_ALTA)("hdu001_esc01 · TC-F07 · el botón + abre el formulario con el foco en el código (%s)", async (rol) => {
    const { usuario } = await abrirPantallaConTabla([rol]);

    const dialogo = await abrirFormulario(usuario);

    const { codigo } = campos(dialogo);
    await waitFor(() => expect(codigo).toHaveFocus());
    // El código es el primer campo del formulario.
    const controles = within(dialogo).getAllByRole("textbox");
    expect(controles.at(0)).toBe(codigo);
  });
});

describe("TKT-012a · TC-F08 · quien no da de alta no ve el botón (CA-9, rechazo)", () => {
  test.each(ROLES_QUE_SOLO_LEEN)("hdu001_esc01 · TC-F08 · %s ve la lista y no ve el botón +", async (rol) => {
    await abrirPantallaConTabla([rol]);

    expect(screen.getByRole("cell", { name: "AP-058-25" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Union Square F2" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: ETIQUETA_ALTA })).not.toBeInTheDocument();
  });
});

describe("TKT-012a · TC-F09 · alta desde la pantalla (CA-10)", () => {
  test("hdu001_esc02 · TC-F09 · alta desde la pantalla: 15 y 5 precargados, porcentajes como cadenas exactas, el formulario se cierra y la lista se vuelve a pedir", async () => {
    const existentes = [obra()];
    const alta = dobleAlta((cuerpo) => {
      const creada = obra({
        id: ID_OBRA_NUEVA,
        codigo: cuerpo.codigo,
        nombre: cuerpo.nombre,
        domicilio: cuerpo.domicilio,
        retencion_destajo_pct: cuerpo.retencion_destajo_pct,
        fondo_garantia_pct: cuerpo.fondo_garantia_pct,
        iva_acreditable: cuerpo.iva_acreditable,
        umbral_alerta_pct: cuerpo.umbral_alerta_pct ?? null,
        estado: "PLANEACION",
      });
      existentes.push(creada);
      return HttpResponse.json(creada satisfies Obra, { status: 201, headers: { Location: `${RUTA_OBRAS}/${ID_OBRA_NUEVA}` } });
    });
    const { usuario, lista } = await abrirPantallaConTabla(["DIRECTOR_PROYECTOS"], { obras: existentes, alta });
    expect(lista.pedidas).toHaveLength(1);

    const dialogo = await abrirFormulario(usuario);
    const controles = campos(dialogo);

    // Valores sugeridos y editables: 15 y 5; el umbral vacío; el tipo preseleccionado con su único valor.
    expect(controles.retencion).toHaveValue("15");
    expect(controles.fondo).toHaveValue("5");
    expect(controles.umbral).toHaveValue("");
    expect(controles.tipoContrato).toHaveValue(TIPO_CONTRATO);
    expect(controles.iva).not.toBeChecked();

    await capturarObra(usuario, dialogo);
    await usuario.click(controles.iva);
    await usuario.click(controles.guardar);

    await waitFor(sinFormulario);
    expect(alta.cuerpos).toEqual([
      {
        codigo: "AP-012-26",
        nombre: "Plaza Jurica Etapa 2",
        domicilio: "Blvd. Bernardo Quintana 4100, Querétaro",
        tipo_contrato: TIPO_CONTRATO,
        retencion_destajo_pct: "0.150000",
        fondo_garantia_pct: "0.050000",
        umbral_alerta_pct: null,
        iva_acreditable: true,
      } satisfies ObraNueva,
    ]);

    // La lista se volvió a pedir y la obra nueva aparece en estado PLANEACION.
    await waitFor(() => expect(lista.pedidas).toHaveLength(2));
    const fila = await screen.findByRole("row", { name: /AP-012-26/ });
    expect(within(fila).getByRole("cell", { name: "Plaza Jurica Etapa 2" })).toBeInTheDocument();
    expect(within(fila).getByText(/planeaci[oó]n/i)).toBeInTheDocument();
  });
});

describe("TKT-012a · TC-F10 · el código ya existe (CA-11, rechazo)", () => {
  function duplicado() {
    return dobleAlta(() =>
      HttpResponse.json(
        errorConflictoEstado("CODIGO_OBRA_DUPLICADO", {
          mensaje: "Ya existe una obra con el código AP-058-25.",
          detalle: { obra_existente_id: ID_OBRA_EXISTENTE, obra_existente: "AP-058-25 · Union Square F2" },
          acciones: [{ clave: "VER_OBRA", metodo: "GET", ruta: `${RUTA_OBRAS}/${ID_OBRA_EXISTENTE}` }],
        }),
        { status: 409 },
      ),
    );
  }

  test("hdu001_esc03 · TC-F10 · el formulario sigue abierto con lo capturado y el conflicto en línea con la obra existente; la lista no se vuelve a pedir", async () => {
    const alta = duplicado();
    const { usuario, lista } = await abrirPantallaConTabla(["DIRECTOR_PROYECTOS"], { alta });
    const dialogo = await abrirFormulario(usuario);
    const controles = campos(dialogo);

    await usuario.clear(controles.codigo);
    await capturarObra(usuario, dialogo, "AP-058-25");
    await usuario.click(controles.guardar);

    // El conflicto se pinta dentro del formulario: código y nombre de la obra existente, y la acción; nunca su UUID.
    const conflicto = await within(dialogo).findByRole("region");
    expect(within(conflicto).getByText("AP-058-25 · Union Square F2")).toBeInTheDocument();
    expect(within(conflicto).getByRole("button", { name: "Ver la obra" })).toBeInTheDocument();
    expect(dialogo).not.toHaveTextContent(ID_OBRA_EXISTENTE);

    // El formulario no se cerró y conserva lo capturado.
    expect(screen.getByRole("dialog", { name: TITULO_FORMULARIO })).toBeInTheDocument();
    expect(controles.codigo).toHaveValue("AP-058-25");
    expect(controles.nombre).toHaveValue("Plaza Jurica Etapa 2");
    expect(controles.domicilio).toHaveValue("Blvd. Bernardo Quintana 4100, Querétaro");
    expect(alta.cuerpos).toHaveLength(1);
    // Ninguna obra nueva y ninguna petición de lista más.
    expect(lista.pedidas).toHaveLength(1);
  });

  test("hdu001_esc03 · TC-F10 · la acción «Ver la obra» cierra el formulario y deja la lista a la vista, sin ficha (D-7)", async () => {
    const alta = duplicado();
    const { usuario, router } = await abrirPantallaConTabla(["DIRECTOR_PROYECTOS"], { alta });
    const dialogo = await abrirFormulario(usuario);
    await capturarObra(usuario, dialogo, "AP-058-25");
    await usuario.click(campos(dialogo).guardar);
    await usuario.click(await within(dialogo).findByRole("button", { name: "Ver la obra" }));

    await waitFor(sinFormulario);
    expect(router.state.location.pathname).toBe(RUTA_PANTALLA);
    const tabla = screen.getByRole("table");
    // Sigue la única obra de antes: no apareció ninguna nueva.
    expect(within(tabla).getAllByRole("row")).toHaveLength(2);
    expect(within(tabla).getByRole("cell", { name: "AP-058-25" })).toBeInTheDocument();
  });
});

describe("TKT-012a · TC-F11 · rechazos del servidor junto a su campo (CA-11, rechazo)", () => {
  test("tkt012a_ca11 · TC-F11 · un 422 en retencion_destajo_pct se pinta junto a su campo y lo capturado se conserva", async () => {
    const mensaje = "La retención debe estar entre 0 y 100 %.";
    const alta = dobleAlta(() =>
      HttpResponse.json(errorValidacion([{ campo: "retencion_destajo_pct", codigo: "FUERA_DE_RANGO", mensaje }]), { status: 422 }),
    );
    const { usuario, lista } = await abrirPantallaConTabla(["DIRECTOR_PROYECTOS"], { alta });
    const dialogo = await abrirFormulario(usuario);
    const controles = campos(dialogo);
    await capturarObra(usuario, dialogo);
    await usuario.clear(controles.retencion);
    await usuario.type(controles.retencion, "120");
    await usuario.click(controles.guardar);

    expect(await within(dialogo).findByText(mensaje)).toBeInTheDocument();
    expect(controles.retencion).toHaveAttribute("aria-invalid", "true");
    expect(controles.retencion).toHaveAccessibleDescription(mensaje);
    expect(controles.fondo).not.toHaveAttribute("aria-invalid", "true");
    // El cliente no evalúa el rango: envió 120 % como fracción y fue el servidor quien lo rechazó.
    expect(alta.cuerpos.at(0)?.retencion_destajo_pct).toBe("1.200000");
    expect(controles.codigo).toHaveValue("AP-012-26");
    expect(controles.retencion).toHaveValue("120");
    expect(screen.getByRole("dialog", { name: TITULO_FORMULARIO })).toBeInTheDocument();
    expect(lista.pedidas).toHaveLength(1);
  });

  test("hdu001_esc03 · TC-F11 · un 403 muestra «Tu rol no permite esta operación.» sin cifras ni tratamiento de bloqueo (D-6)", async () => {
    const alta = dobleAlta(() =>
      HttpResponse.json({ ...errorPermiso("ROL_INSUFICIENTE"), mensaje: MENSAJE_SIN_PERMISO }, { status: 403 }),
    );
    const { usuario } = await abrirPantallaConTabla(["DIRECTOR_PROYECTOS"], { alta });
    const dialogo = await abrirFormulario(usuario);
    await capturarObra(usuario, dialogo);
    await usuario.click(campos(dialogo).guardar);

    expect(await within(dialogo).findByText(new RegExp(MENSAJE_SIN_PERMISO))).toBeInTheDocument();
    // No es un bloqueo de negocio: ni cabecera de bloqueo, ni cifras, ni acciones.
    expect(within(dialogo).queryByRole("region")).not.toBeInTheDocument();
    expect(within(dialogo).queryByText("Operación bloqueada")).not.toBeInTheDocument();
    expect(within(dialogo).queryByText("No se puede completar")).not.toBeInTheDocument();
    expect(within(dialogo).queryByText(/disponible|excedente|presupuestado/i)).not.toBeInTheDocument();
    expect(within(dialogo).queryByRole("button", { name: "Ver la obra" })).not.toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: TITULO_FORMULARIO })).toBeInTheDocument();
  });

  test("tkt012a_ca11 · TC-F11 · un porcentaje con formato inválido se rechaza en el cliente junto a su campo y no sale ninguna petición", async () => {
    const alta = dobleAlta(() => HttpResponse.json(obra(), { status: 201 }));
    const { usuario } = await abrirPantallaConTabla(["DIRECTOR_PROYECTOS"], { alta });
    const dialogo = await abrirFormulario(usuario);
    const controles = campos(dialogo);
    await capturarObra(usuario, dialogo);
    await usuario.clear(controles.retencion);
    await usuario.type(controles.retencion, "abc");
    await usuario.click(controles.guardar);

    expect(await within(dialogo).findByText("Escribe un porcentaje, como 15")).toBeInTheDocument();
    expect(controles.retencion).toHaveAttribute("aria-invalid", "true");
    expect(alta.cuerpos).toHaveLength(0);
    expect(screen.getByRole("dialog", { name: TITULO_FORMULARIO })).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------------------------------------------
// TKT-018a · fila A5 · TC-17 (CA-1). La lista de obras gana la columna «Línea base» para quien tiene la sección
// `LINEA_BASE` (Director de Proyectos, Dirección General y Compras). Los seis roles abren la lista (`OBRAS` es de
// todos), así que el camino feliz y el rechazo se prueban en esta misma pantalla.
// ---------------------------------------------------------------------------------------------------------------

const ROLES_CON_LINEA_BASE: Rol[] = ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL", "COMPRAS"];
const ROLES_SIN_LINEA_BASE: Rol[] = ["RESIDENTE", "ALMACEN", "ADMINISTRACION"];

function rutaLineaBase(obraId: string) {
  return `/obras/${obraId}/linea-base`;
}

/** Los dobles de la pantalla de línea base: anotan el identificador de la obra de cada petición que reciben. */
function dobleLineaBaseDeObra(obras: Obra[]) {
  const pedidas = { obra: [] as string[], lineas: [] as string[] };
  const handlers = [
    http.get(`${ORIGEN}${RUTA_OBRAS}/:obraId`, ({ params }) => {
      const obraId = String(params.obraId);
      pedidas.obra.push(obraId);
      const encontrada = obras.find((candidata) => candidata.id === obraId);
      return encontrada === undefined ? new HttpResponse(null, { status: 404 }) : HttpResponse.json(encontrada);
    }),
    http.get(`${ORIGEN}${RUTA_OBRAS}/:obraId/lineas-base`, ({ params }) => {
      const obraId = String(params.obraId);
      pedidas.lineas.push(obraId);
      return HttpResponse.json([lineaBase({ obra_id: obraId })] satisfies Esquemas["LineaBase"][]);
    }),
  ];
  return { handlers, pedidas };
}

describe("TKT-018a · TC-17 · enlace a la línea base desde la lista de obras (CA-1)", () => {
  test.each(ROLES_CON_LINEA_BASE)(
    "tkt018a_ca01 · enlace desde la lista · TC-17 · %s ve la columna «Línea base» y, en cada fila, el enlace «Línea base de {código}» a la pantalla de esa obra",
    async (rol) => {
      await abrirPantallaConTabla([rol], { obras: [obra(), obraTercera()] });

      const tabla = screen.getByRole("table");
      expect(within(tabla).getByRole("columnheader", { name: "Línea base" })).toBeInTheDocument();
      const primera = within(tabla).getByRole("row", { name: /AP-058-25/ });
      expect(within(primera).getByRole("link", { name: "Línea base de AP-058-25" })).toHaveAttribute(
        "href",
        rutaLineaBase(ID_OBRA_EXISTENTE),
      );
      const segunda = within(tabla).getByRole("row", { name: /AP-061-25/ });
      expect(within(segunda).getByRole("link", { name: "Línea base de AP-061-25" })).toHaveAttribute(
        "href",
        rutaLineaBase(ID_OBRA_TERCERA),
      );
      // Un enlace por obra, ni uno más.
      expect(within(tabla).getAllByRole("link", { name: /^Línea base de / })).toHaveLength(2);
    },
  );

  test.each(ROLES_CON_LINEA_BASE)(
    "tkt018a_ca01 · enlace desde la lista · TC-17 · %s pulsa el enlace de una obra: la ruta cambia y se pide la línea base de esa obra, no de otra",
    async (rol) => {
      const obras = [obra(), obraTercera()];
      const destino = dobleLineaBaseDeObra(obras);
      servidorPruebas.use(...destino.handlers);
      const { usuario, router } = await abrirPantallaConTabla([rol], { obras });

      // Se pulsa el de la segunda fila: con el de la primera, un enlace que apuntara siempre a la primera obra pasaría.
      await usuario.click(screen.getByRole("link", { name: "Línea base de AP-061-25" }));

      await waitFor(() => expect(router.state.location.pathname).toBe(rutaLineaBase(ID_OBRA_TERCERA)));
      await waitFor(() => expect(destino.pedidas.lineas).toEqual([ID_OBRA_TERCERA]));
      expect(destino.pedidas.obra).toEqual([ID_OBRA_TERCERA]);
      // Ya no está la lista: la pantalla es la de la obra elegida.
      expect(screen.queryByRole("heading", { level: 1, name: "Obras" })).not.toBeInTheDocument();
      expect(screen.queryByRole("heading", { level: 1, name: "No tienes permiso para esta sección" })).not.toBeInTheDocument();
    },
  );

  test.each(ROLES_SIN_LINEA_BASE)(
    "tkt018a_ca01 · enlace desde la lista · TC-17 · %s ve la lista sin la columna ni ningún enlace «Línea base de …»",
    async (rol) => {
      await abrirPantallaConTabla([rol], { obras: [obra(), obraTercera()] });

      const tabla = screen.getByRole("table");
      // La lista sí se ve: el rechazo es del enlace, no de la pantalla.
      expect(within(tabla).getByRole("cell", { name: "AP-058-25" })).toBeInTheDocument();
      expect(within(tabla).getByRole("cell", { name: "AP-061-25" })).toBeInTheDocument();
      expect(within(tabla).getAllByRole("columnheader").map((columna) => columna.textContent)).toEqual(["Código", "Nombre", "Estado"]);
      expect(screen.queryByRole("link", { name: /Línea base de / })).not.toBeInTheDocument();
      expect(within(tabla).queryByRole("link")).not.toBeInTheDocument();
    },
  );
});
