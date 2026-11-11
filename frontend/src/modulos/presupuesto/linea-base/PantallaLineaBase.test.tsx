import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import type { components as Servidor } from "@/api/generado/servidor";
import type { Rol } from "@/api/sesion";
import { type ClaveSeccion, seccion } from "@/app/navegacion/secciones";
import {
  controlSinTopes,
  errorCongeladoBloqueoVencido,
  errorExplosionNoCalculable,
  errorLineaBaseEnOtroEstado,
  errorNoEncontrado,
  errorPermiso,
  errorRn01SegundaVigente,
  errorValidacion,
  ID_LINEA_BASE_VIGENTE,
  lineaBase,
  obra,
  tokenCsrf,
  usuarioActual,
} from "@/pruebas/cuerpos";
import { renderizarAplicacion } from "@/pruebas/render";
import { servidorPruebas } from "@/pruebas/servidor";

// TKT-018a · fila A3 · TC-05 a TC-09 (CA-1, CA-2, CA-5, CA-12, CA-13). La pantalla se prueba montada en su ruta
// `/obras/:obraId/linea-base` dentro de la aplicación completa, con MSW como servidor: la prueba no importa ningún
// módulo de producción nuevo y cada caso falla por el comportamiento ausente (hoy la ruta no existe).
// Las respuestas se construyen con los tipos generados del OpenAPI (`satisfies` en las fábricas de `cuerpos.ts`).
//
// Alcance de la fila:
// - El formulario de congelado es de A4: para el Director de Proyectos, TC-06 no afirma aquí ni el campo
//   «Motivo (obligatorio)» ni el botón «Congelar línea base»; A4 los añade.
// - La tabla del presupuesto de control es de la entrega b. Desde la fila B2 la vista CONGELADA la monta y pide
//   `presupuesto-control`: las pruebas que muestran una CONGELADA reciben el doble `control` (sin cambiar ninguna
//   aserción) y las que muestran un BORRADOR siguen sin él. Cualquier petición sin doble hace fallar la prueba
//   (ver `sinAtender`).

type Esquemas = Servidor["schemas"];
type Obra = Esquemas["Obra"];
type LineaBase = Esquemas["LineaBase"];

const ORIGEN = globalThis.location.origin;
const RUTA_SESION = "/api/v1/sesion";
const RUTA_CSRF = "/api/v1/sesion/csrf";

const ID_OBRA = lineaBase().obra_id;
const ID_LINEA_BASE = lineaBase().id;
const ID_OTRA_OBRA = "1f2e3d4c-5b6a-4978-8a9b-0c1d2e3f4a5b";
const ID_LINEA_BASE_BORRADOR_NUEVO = "2a3b4c5d-6e7f-4801-9a2b-3c4d5e6f7081";
const ID_QUIEN_CONGELO = "3b4c5d6e-7f80-4912-ab3c-4d5e6f708192";
const CORRELACION_500 = "9d8c7b6a-5f4e-4d3c-8b2a-1f0e9d8c7b6a";

const TITULO = "Línea base · AP-058-25 · Union Square F2";
const TEXTO_CARGANDO = "Cargando la línea base";
const TEXTO_VACIO = "Esta obra todavía no tiene línea base.";
const TEXTO_VACIO_EXPLICACION = "La importación del presupuesto llegará en una próxima entrega (TKT-018b).";
const TEXTO_CONGELA_PRIMERO = /Congela primero la línea base para capturar el presupuesto de control/;
const TEXTO_ERROR = "No se pudo cargar la línea base.";
const TEXTO_SIN_PERMISO = "No tienes permiso para esta sección";
// Distinto, a propósito, del literal de `errorPermiso` («No tienes permiso para esta operación.»).
const MENSAJE_403 = "Tu rol no permite esta operación.";
const CONGELADA_EN = "2026-10-15T17:30:00Z";
const MOTIVO_CONGELADO = "Contrato firmado el 13-oct-2026";

const DESGLOSE = [
  ["MUROS", "$30,000.00"],
  ["PLAFONES Y CAJILLOS", "$18,500.00"],
  ["ENCHAPES", "$6,600.00"],
  ["GENERALES", "$7,400.00"],
] as const;

const ROLES_CON_ACCESO: Rol[] = ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL", "COMPRAS"];
const ROLES_SIN_ACCESO: Rol[] = ["RESIDENTE", "ALMACEN", "ADMINISTRACION"];

// Los tiempos se controlan con el reloj simulado que avanza solo: `usuario` de userEvent lo exige y ninguna prueba hace `sleep`.
beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
afterEach(() => {
  vi.useRealTimers();
});

// `onUnhandledRequest: "error"` hace fallar la petición, no la prueba. Aquí además la prueba falla: toda petición
// que ningún doble atiende queda anotada y se comprueba al terminar. Así «ninguna petición a presupuesto-control»
// se sostiene en cada caso, también en los que no la vigilan con un doble.
const sinAtender: string[] = [];
function anotarSinAtender({ request }: { request: Request }) {
  sinAtender.push(`${request.method} ${new URL(request.url).pathname}`);
}
beforeEach(() => {
  sinAtender.length = 0;
  servidorPruebas.events.on("request:unhandled", anotarSinAtender);
});
afterEach(() => {
  servidorPruebas.events.removeListener("request:unhandled", anotarSinAtender);
  expect(sinAtender).toEqual([]);
});

/** Una promesa cuyo desenlace decide la prueba: así «cargando» se observa sin esperar por tiempo. */
function diferido() {
  let resolver!: () => void;
  const promesa = new Promise<void>((resolve) => {
    resolver = resolve;
  });
  return { promesa, resolver };
}

function rutaPantalla(obraId: string) {
  return `/obras/${obraId}/linea-base`;
}

function congelada(cambios: Partial<LineaBase> = {}): LineaBase {
  return lineaBase({
    estado: "CONGELADA",
    congelada_en: CONGELADA_EN,
    congelada_por: { id: ID_QUIEN_CONGELO, nombre: "J. Ramírez" },
    motivo: MOTIVO_CONGELADO,
    ...cambios,
  });
}

function obraActiva(): Obra {
  return obra({ estado: "ACTIVA", linea_base_vigente_id: ID_LINEA_BASE });
}

type Responder = () => Response | Promise<Response>;

interface OpcionesPantalla {
  obraId?: string;
  obra?: Obra;
  lineas?: LineaBase[];
  /** Sustituyen a la respuesta 200 con `obra` y `lineas`: para los rechazos y para retrasar la respuesta. */
  responderObra?: Responder;
  responderLineas?: Responder;
  /** Dobla `presupuesto-control` solo para contar sus peticiones; responde vacío, como el servidor en BORRADOR. */
  vigilarControl?: boolean;
  /** Dobla `presupuesto-control` con estas filas (fila B2): para las pruebas que muestran una CONGELADA, que ya lo pide. */
  control?: Esquemas["PresupuestoControl"][];
}

/**
 * Monta la aplicación en la pantalla de la obra con la sesión del rol y espera a que la sesión cargue.
 * Cada doble anota el identificador de la ruta de cada petición que recibe: sirve de contador y de testigo de la obra pedida.
 */
async function abrirPantalla(roles: Rol[], opciones: OpcionesPantalla = {}) {
  const { obraId = ID_OBRA, obra: datosObra = obra(), lineas = [lineaBase()], vigilarControl = false } = opciones;
  const responderObra = opciones.responderObra ?? (() => HttpResponse.json(datosObra));
  const responderLineas = opciones.responderLineas ?? (() => HttpResponse.json(lineas));
  const pedidas = { obra: [] as string[], lineas: [] as string[], control: [] as string[] };

  servidorPruebas.use(
    http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(usuarioActual(roles))),
    http.get(`${ORIGEN}${RUTA_CSRF}`, () => HttpResponse.json(tokenCsrf())),
    http.get(`${ORIGEN}/api/v1/obras/:obraId`, async ({ params }) => {
      pedidas.obra.push(String(params.obraId));
      return responderObra();
    }),
    http.get(`${ORIGEN}/api/v1/obras/:obraId/lineas-base`, async ({ params }) => {
      pedidas.lineas.push(String(params.obraId));
      return responderLineas();
    }),
  );
  if (vigilarControl || opciones.control !== undefined) {
    servidorPruebas.use(
      http.get(`${ORIGEN}/api/v1/lineas-base/:lineaBaseId/presupuesto-control`, ({ params }) => {
        pedidas.control.push(String(params.lineaBaseId));
        return HttpResponse.json(opciones.control ?? ([] satisfies Esquemas["PresupuestoControl"][]));
      }),
    );
  }

  const aplicacion = renderizarAplicacion(rutaPantalla(obraId));
  await screen.findByText(/Rosa Villanueva/);
  return { ...aplicacion, pedidas };
}

/** El contenido de la pantalla, sin la cabecera ni el menú del armazón. */
function principal() {
  return screen.getByRole("main");
}

function titulo() {
  return screen.findByRole("heading", { level: 1, name: TITULO });
}

/** El valor que acompaña a un rótulo de la lista de datos de la cabecera (`dt` y su `dd`). */
function valorDe(rotulo: string): string {
  const termino = within(principal()).getByText(rotulo, { selector: "dt" });
  return termino.nextElementSibling?.textContent.trim() ?? "";
}

function tablaDesglose() {
  return within(principal()).getByRole("table", { name: "Desglose por tipo de partida" });
}

/** Cada tipo de partida tiene su fila en el desglose, con su importe. */
function esperarDesglose(filas: readonly (readonly [string, string])[]) {
  const tabla = tablaDesglose();
  for (const [nombre, importe] of filas) {
    const fila = within(tabla).getByRole("row", { name: new RegExp(`^${nombre}\\b`) });
    expect(within(fila).getByText(importe)).toBeInTheDocument();
  }
}

/** Los campos de texto que no pertenecen a una tabla (la del presupuesto de control, de la entrega b, sí tendrá). */
function camposFueraDeTablas() {
  return within(principal())
    .queryAllByRole("textbox")
    .filter((campo) => campo.closest("table") === null);
}

function esperarSinCifras() {
  expect(principal()).not.toHaveTextContent("$");
}

describe("TKT-018a · TC-05 · estados de la pantalla de línea base (CA-12)", () => {
  test("tkt018a_ca12 · estados · TC-05 · cargando: un esqueleto con aria-busy mientras el servidor no responde", async () => {
    const compuerta = diferido();
    const { pedidas } = await abrirPantalla(["DIRECTOR_PROYECTOS"], {
      responderObra: async () => {
        await compuerta.promesa;
        return HttpResponse.json(obra());
      },
      responderLineas: async () => {
        await compuerta.promesa;
        return HttpResponse.json([lineaBase()]);
      },
    });

    const esqueleto = await screen.findByRole("status", { name: TEXTO_CARGANDO });
    expect(esqueleto).toHaveAttribute("aria-busy", "true");
    await waitFor(() => expect(pedidas.lineas).toHaveLength(1));
    // Cargando no es vacío: ni el texto del vacío ni cifras.
    expect(screen.queryByText(TEXTO_VACIO)).not.toBeInTheDocument();
    esperarSinCifras();

    compuerta.resolver();
    expect(await titulo()).toBeInTheDocument();
    expect(screen.queryByRole("status", { name: TEXTO_CARGANDO })).not.toBeInTheDocument();
  });

  test("tkt018a_ca12 · estados · TC-05 · sin línea base: los dos textos del vacío y ningún botón", async () => {
    await abrirPantalla(["DIRECTOR_PROYECTOS"], { lineas: [] });

    expect(await screen.findByText(TEXTO_VACIO)).toBeInTheDocument();
    expect(screen.getByText(TEXTO_VACIO_EXPLICACION)).toBeInTheDocument();
    // Nada que simule importar ni congelar.
    expect(within(principal()).queryAllByRole("button")).toHaveLength(0);
    expect(camposFueraDeTablas()).toHaveLength(0);
    esperarSinCifras();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  test("tkt018a_ca12 · estados · TC-05 · la obra no existe (404): «La obra no existe», sin tratamiento de error", async () => {
    const noExiste = () => HttpResponse.json(errorNoEncontrado("obra", "La obra no existe."), { status: 404 });
    await abrirPantalla(["DIRECTOR_PROYECTOS"], { obraId: ID_OTRA_OBRA, responderObra: noExiste, responderLineas: noExiste });

    expect(await screen.findByRole("heading", { level: 1, name: "La obra no existe" })).toBeInTheDocument();
    expect(screen.queryByText(TEXTO_ERROR)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reintentar" })).not.toBeInTheDocument();
    expect(screen.queryByText(TEXTO_VACIO)).not.toBeInTheDocument();
    esperarSinCifras();
  });

  test("tkt018a_ca12 · estados · TC-05 · el identificador de la ruta no es un UUID (422): «La obra no existe»", async () => {
    const invalido = () =>
      HttpResponse.json(
        errorValidacion([{ campo: "obra_id", codigo: "FORMATO", mensaje: "El identificador no es un UUID válido." }]),
        { status: 422 },
      );
    const { pedidas } = await abrirPantalla(["DIRECTOR_PROYECTOS"], {
      obraId: "abc",
      responderObra: invalido,
      responderLineas: invalido,
    });

    expect(await screen.findByRole("heading", { level: 1, name: "La obra no existe" })).toBeInTheDocument();
    // El cliente no decide que «abc» no es un UUID: lo pregunta y es el servidor quien lo rechaza.
    expect(pedidas.obra).toEqual(["abc"]);
    expect(screen.queryByText(TEXTO_ERROR)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reintentar" })).not.toBeInTheDocument();
  });

  test("tkt018a_ca12 · estados · TC-05 · error 500: la referencia de correlación y «Reintentar», que vuelve a pedir las dos consultas", async () => {
    let caido = true;
    const fallo = () => HttpResponse.json({ mensaje: "Error interno del servidor.", correlacion_id: CORRELACION_500 }, { status: 500 });
    const { usuario, pedidas } = await abrirPantalla(["DIRECTOR_PROYECTOS"], {
      responderObra: () => (caido ? fallo() : HttpResponse.json(obra())),
      responderLineas: () => (caido ? fallo() : HttpResponse.json([lineaBase()])),
    });

    const aviso = await screen.findByRole("alert");
    expect(aviso).toHaveTextContent(TEXTO_ERROR);
    expect(aviso).toHaveTextContent(`Referencia: ${CORRELACION_500}`);
    // Un error no es ni el vacío ni una obra inexistente.
    expect(screen.queryByText(TEXTO_VACIO)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "La obra no existe" })).not.toBeInTheDocument();
    expect(pedidas.obra).toHaveLength(1);
    expect(pedidas.lineas).toHaveLength(1);

    caido = false;
    await usuario.click(within(aviso).getByRole("button", { name: "Reintentar" }));

    expect(await titulo()).toBeInTheDocument();
    expect(pedidas.obra).toHaveLength(2);
    expect(pedidas.lineas).toHaveLength(2);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(principal()).not.toHaveTextContent(CORRELACION_500);
  });

  // El diseño dice «error de cualquiera de las dos consultas»: basta con que falle una, aunque la obra haya llegado.
  test("tkt018a_ca12 · estados · TC-05 · la obra llega y las líneas base fallan con 500: el aviso con la referencia y «Reintentar»", async () => {
    const { pedidas } = await abrirPantalla(["DIRECTOR_PROYECTOS"], {
      responderLineas: () =>
        HttpResponse.json({ mensaje: "Error interno del servidor.", correlacion_id: CORRELACION_500 }, { status: 500 }),
    });

    const aviso = await screen.findByRole("alert");
    expect(aviso).toHaveTextContent(TEXTO_ERROR);
    expect(aviso).toHaveTextContent(`Referencia: ${CORRELACION_500}`);
    expect(within(aviso).getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
    expect(pedidas.obra).toHaveLength(1);
    // Ni el vacío, ni una obra inexistente, ni una vista a medias con cifras.
    expect(screen.queryByText(TEXTO_VACIO)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "La obra no existe" })).not.toBeInTheDocument();
    esperarSinCifras();
  });

  test("tkt018a_ca12 · estados · TC-05 · la obra llega y las líneas base responden 404: «La obra no existe»", async () => {
    const { pedidas } = await abrirPantalla(["DIRECTOR_PROYECTOS"], {
      responderLineas: () => HttpResponse.json(errorNoEncontrado("obra", "La obra no existe."), { status: 404 }),
    });

    expect(await screen.findByRole("heading", { level: 1, name: "La obra no existe" })).toBeInTheDocument();
    expect(pedidas.obra).toHaveLength(1);
    expect(screen.queryByText(TEXTO_ERROR)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reintentar" })).not.toBeInTheDocument();
    expect(screen.queryByText(TEXTO_VACIO)).not.toBeInTheDocument();
    esperarSinCifras();
  });

  // Añadido del tester: el plan no lo enumera en TC-05, pero «sin permiso» es uno de los estados de la fila
  // `PantallaLineaBase.tsx` del diseño y la segunda mitad de CA-1 (rechazo): el 403 lo pone el servidor aunque
  // la cortesía de navegación deje pasar al rol.
  test("tkt018a_ca12 · estados · TC-05 · 403 del servidor: el aviso de sin permiso, sin cifras y sin tratamiento de error", async () => {
    const denegado = () => HttpResponse.json({ ...errorPermiso("ROL_INSUFICIENTE"), mensaje: MENSAJE_403 }, { status: 403 });
    await abrirPantalla(["DIRECTOR_PROYECTOS"], { responderObra: denegado, responderLineas: denegado });

    expect(await screen.findByRole("heading", { level: 1, name: TEXTO_SIN_PERMISO })).toBeInTheDocument();
    expect(screen.queryByText(TEXTO_ERROR)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reintentar" })).not.toBeInTheDocument();
    expect(screen.queryByText(TEXTO_VACIO)).not.toBeInTheDocument();
    esperarSinCifras();
  });
});

describe("TKT-018a · TC-06 · línea base en BORRADOR (CA-2, CA-13)", () => {
  // El campo «Motivo (obligatorio)» y el botón «Congelar línea base» del Director de Proyectos son de la fila A4.
  test("hdu001_esc14 · borrador para el Director de Proyectos · TC-06 · estado, versión, venta y desglose, sin presupuesto de control", async () => {
    const { pedidas } = await abrirPantalla(["DIRECTOR_PROYECTOS"], {
      lineas: [lineaBase({ version: 3 })],
      vigilarControl: true,
    });

    expect(await titulo()).toBeInTheDocument();
    expect(valorDe("Estado")).toBe("BORRADOR");
    expect(valorDe("Versión")).toBe("3");
    expect(valorDe("Estado de la obra")).toBe("PLANEACION");
    expect(valorDe("Importe de venta")).toBe("$62,500.00");
    esperarDesglose(DESGLOSE);

    expect(screen.queryByRole("heading", { name: "Presupuesto de control" })).not.toBeInTheDocument();
    expect(screen.getByText(TEXTO_CONGELA_PRIMERO)).toBeInTheDocument();
    // Un borrador no tiene presupuesto de control: ni siquiera se pregunta.
    expect(pedidas.control).toHaveLength(0);
    // Ni fecha ni autor de un congelado que no ha ocurrido.
    expect(screen.queryByText(/Congelada el/)).not.toBeInTheDocument();
  });

  test("hdu001_esc14 · borrador para Dirección General · TC-06 · la misma vista, sin formulario de congelado", async () => {
    const { pedidas } = await abrirPantalla(["DIRECCION_GENERAL"], { vigilarControl: true });

    expect(await titulo()).toBeInTheDocument();
    expect(valorDe("Estado")).toBe("BORRADOR");
    expect(valorDe("Versión")).toBe("1");
    expect(valorDe("Importe de venta")).toBe("$62,500.00");
    esperarDesglose(DESGLOSE);
    expect(screen.getByText(TEXTO_CONGELA_PRIMERO)).toBeInTheDocument();

    // Solo el Director de Proyectos congela (CA-13).
    expect(camposFueraDeTablas()).toHaveLength(0);
    expect(within(principal()).queryByRole("button", { name: /Congelar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Presupuesto de control" })).not.toBeInTheDocument();
    expect(pedidas.control).toHaveLength(0);
  });

  // Añadido del tester (mutante M-7). El plan lo defiende en TC-22, que es de la entrega b; para que la fila A3
  // no quede sin defensa se comprueba aquí que la venta se formatea desde la cadena, sin pasar por `Number`.
  // El primer importe es el del plan; con `Number` da el mismo texto, así que por sí solo no mata el mutante:
  // lo matan los otros dos, que con `Number` saldrían «$100,000,000,000,000.00» y «$12,345,678,901,234.56».
  test.each([
    ["12345678901234.5678", "$12,345,678,901,234.57"],
    ["99999999999999.9949", "$99,999,999,999,999.99"],
    ["12345678901234.5650", "$12,345,678,901,234.57"],
  ])("tkt018a_ca02 · TC-06 · una venta de 18 dígitos (%s) se pinta sin pérdida de exactitud: %s", async (importe, esperado) => {
    const base = lineaBase();
    const [muros, ...demas] = base.por_tipo_partida;
    if (muros === undefined) throw new Error("La fábrica de línea base no trae tipos de partida.");
    await abrirPantalla(["DIRECTOR_PROYECTOS"], {
      lineas: [lineaBase({ importe_venta: importe, por_tipo_partida: [{ ...muros, importe_venta: importe }, ...demas] })],
      vigilarControl: true,
    });

    expect(await titulo()).toBeInTheDocument();
    expect(valorDe("Importe de venta")).toBe(esperado);
    esperarDesglose([["MUROS", esperado]]);
  });
});

describe("TKT-018a · TC-07 · línea base CONGELADA en solo lectura (CA-5)", () => {
  // Desde B2 la vista CONGELADA monta la tabla del control y la pide: estas pruebas reciben su doble (`control`).
  test.each(ROLES_CON_ACCESO)(
    "hdu001_esc18 · congelada en solo lectura · TC-07 · %s ve estado, versión, venta, fecha, autor y motivo, y ningún control de edición",
    async (rol) => {
      await abrirPantalla([rol], { obra: obraActiva(), lineas: [congelada({ version: 2 })], control: controlSinTopes() });

      expect(await titulo()).toBeInTheDocument();
      expect(valorDe("Estado")).toBe("CONGELADA");
      expect(valorDe("Versión")).toBe("2");
      expect(valorDe("Estado de la obra")).toBe("ACTIVA");
      expect(valorDe("Importe de venta")).toBe("$62,500.00");
      esperarDesglose(DESGLOSE);

      // La fecha se comprueba por el atributo `datetime`: el texto depende de la configuración regional.
      const fecha = within(principal()).getByText(/Congelada el/);
      expect(fecha).toHaveTextContent("J. Ramírez");
      expect(fecha.querySelector("time")).toHaveAttribute("datetime", CONGELADA_EN);
      expect(fecha.querySelector("time")?.textContent).toBe("15 oct 2026");
      expect(within(principal()).getByText(new RegExp(`Motivo: ${MOTIVO_CONGELADO}`))).toBeInTheDocument();

      // Nada editable sobre la línea base (RN-01).
      expect(camposFueraDeTablas()).toHaveLength(0);
      expect(within(principal()).queryByRole("button", { name: /Congelar|Modificar|Eliminar/i })).not.toBeInTheDocument();
      expect(screen.queryByText(TEXTO_CONGELA_PRIMERO)).not.toBeInTheDocument();
    },
  );

  test("hdu001_esc18 · congelada con fecha inválida · TC-07 · se pinta «Congelada por J. Ramírez» sin <time> y la pantalla no se cae", async () => {
    await abrirPantalla(["DIRECTOR_PROYECTOS"], {
      obra: obraActiva(),
      lineas: [congelada({ congelada_en: "no-es-fecha" })],
      control: controlSinTopes(),
    });

    expect(await titulo()).toBeInTheDocument();
    expect(within(principal()).getByText(/Congelada por J\. Ramírez/)).toBeInTheDocument();
    expect(principal().querySelector("time")).toBeNull();
  });

  test("hdu001_esc18 · congelada sin fecha, autor ni motivo · TC-07 · se pinta «Congelada» sin «el», sin «por» y sin «Motivo»", async () => {
    await abrirPantalla(["DIRECTOR_PROYECTOS"], {
      obra: obraActiva(),
      lineas: [congelada({ congelada_en: null, congelada_por: null, motivo: null })],
      control: controlSinTopes(),
    });

    expect(await titulo()).toBeInTheDocument();
    expect(within(principal()).getByText("Congelada")).toBeInTheDocument();
    expect(principal().querySelector("time")).toBeNull();
    expect(principal()).not.toHaveTextContent("Motivo:");
  });
});

describe("TKT-018a · TC-08 · COMPRAS no ve el borrador (CA-13, D-1)", () => {
  test("tkt018a_ca13 · COMPRAS no ve el borrador · TC-08 · con solo un BORRADOR ve el estado vacío y ninguna cifra", async () => {
    const { pedidas } = await abrirPantalla(["COMPRAS"], { vigilarControl: true });

    expect(await screen.findByText(TEXTO_VACIO)).toBeInTheDocument();
    expect(screen.getByText(TEXTO_VACIO_EXPLICACION)).toBeInTheDocument();
    // El servidor sí le devolvió el borrador: la pantalla lo pidió y no lo enseña.
    expect(pedidas.lineas).toHaveLength(1);
    esperarSinCifras();
    expect(principal()).not.toHaveTextContent("BORRADOR");
    expect(screen.queryByRole("table", { name: "Desglose por tipo de partida" })).not.toBeInTheDocument();
    expect(screen.queryByText(TEXTO_CONGELA_PRIMERO)).not.toBeInTheDocument();
    expect(within(principal()).queryAllByRole("button")).toHaveLength(0);
    expect(pedidas.control).toHaveLength(0);
  });

  test("tkt018a_ca13 · COMPRAS no ve el borrador · TC-08 · con una CONGELADA y un BORRADOR más nuevo ve la congelada, sin formulario", async () => {
    const borradorNuevo = lineaBase({ id: ID_LINEA_BASE_BORRADOR_NUEVO, version: 2, importe_venta: "99999.0000" });
    await abrirPantalla(["COMPRAS"], { obra: obraActiva(), lineas: [borradorNuevo, congelada()], control: controlSinTopes() });

    expect(await titulo()).toBeInTheDocument();
    expect(valorDe("Estado")).toBe("CONGELADA");
    expect(valorDe("Versión")).toBe("1");
    expect(valorDe("Importe de venta")).toBe("$62,500.00");
    expect(principal()).not.toHaveTextContent("$99,999.00");
    expect(principal()).not.toHaveTextContent("BORRADOR");
    expect(camposFueraDeTablas()).toHaveLength(0);
    expect(within(principal()).queryByRole("button", { name: /Congelar/i })).not.toBeInTheDocument();
  });
});

describe("TKT-018a · TC-09 · la obra de la ruta y quién entra (CA-1)", () => {
  test("tkt018a_ca01 · la obra de la ruta · TC-09 · las dos consultas piden la obra de la URL y no otra", async () => {
    const { pedidas, router } = await abrirPantalla(["DIRECTOR_PROYECTOS"], {
      obraId: ID_OTRA_OBRA,
      obra: obra({ id: ID_OTRA_OBRA }),
      lineas: [lineaBase({ obra_id: ID_OTRA_OBRA })],
    });

    expect(await titulo()).toBeInTheDocument();
    expect(router.state.location.pathname).toBe(rutaPantalla(ID_OTRA_OBRA));
    expect(pedidas.obra).toEqual([ID_OTRA_OBRA]);
    expect(pedidas.lineas).toEqual([ID_OTRA_OBRA]);
  });

  test.each(ROLES_SIN_ACCESO)(
    "tkt018a_ca01 · la obra de la ruta · TC-09 · %s abre la ruta a mano: «No tienes permiso para esta sección», sin peticiones ni cifras",
    async (rol) => {
      const { pedidas } = await abrirPantalla([rol], { vigilarControl: true });

      expect(await screen.findByRole("heading", { level: 1, name: TEXTO_SIN_PERMISO })).toBeInTheDocument();
      expect(pedidas.obra).toHaveLength(0);
      expect(pedidas.lineas).toHaveLength(0);
      expect(pedidas.control).toHaveLength(0);
      esperarSinCifras();
      expect(screen.queryByText(TEXTO_VACIO)).not.toBeInTheDocument();
    },
  );
});

// ---------------------------------------------------------------------------------------------------------------
// TKT-018a · fila A4 · TC-10 a TC-16 (CA-3, CA-4) y lo que A3 dejó de TC-06: `FormularioCongelado`, montado en la
// vista BORRADOR solo para el Director de Proyectos. Las pruebas no importan el componente: lo alcanzan por su
// etiqueta y su botón dentro de la pantalla, y cada una falla hoy porque el formulario no está en la vista.
//
// - La tabla del presupuesto de control es de la entrega b: tras congelar, la vista la monta y pide
//   `presupuesto-control` (TC-24, fila B2). Los dobles que congelan (`servidorQueCongela`) la sirven.
// - Un 403 hace que el cliente vuelva a pedir la sesión y descarte el token CSRF: los dobles de `abrirPantalla`
//   atienden esas peticiones de más y TC-16 las cuenta.
// ---------------------------------------------------------------------------------------------------------------

const RUTA_CONGELACION = `/api/v1/lineas-base/${ID_LINEA_BASE}/congelacion`;
const ETIQUETA_MOTIVO = "Motivo (obligatorio)";
const BOTON_CONGELAR = "Congelar línea base";
const TEXTO_MOTIVO_OBLIGATORIO = "El motivo es obligatorio.";
const CORRELACION_FABRICA = errorPermiso("ROL_INSUFICIENTE").correlacion_id;
// El mensaje con que el servidor rechaza un `motivo` con NUL (`MENSAJES[FORMATO]` de `servidor/manejadores.py`).
const MENSAJE_422_MOTIVO = "El valor no tiene el formato esperado.";

// Toda petición que sale, atendida o no: para contar las que provoca un 403 (sesión y token CSRF).
const vistas: string[] = [];
function anotarVista({ request }: { request: Request }) {
  vistas.push(`${request.method} ${new URL(request.url).pathname}`);
}
beforeEach(() => {
  vistas.length = 0;
  servidorPruebas.events.on("request:start", anotarVista);
});
afterEach(() => {
  servidorPruebas.events.removeListener("request:start", anotarVista);
});
function veces(peticion: string): number {
  return vistas.filter((vista) => vista === peticion).length;
}

interface Congelacion {
  lineaBaseId: string;
  cuerpo: unknown;
  csrf: string | null;
}

/**
 * La pantalla del Director de Proyectos con el doble del `POST …/congelacion`, que anota cada intento (línea base,
 * cuerpo y cabecera CSRF) y responde lo que decida la prueba según el número de intento. Espera al título.
 */
async function abrirParaCongelar(responder: (intento: number) => Response, opciones: OpcionesPantalla = {}) {
  const congelaciones: Congelacion[] = [];
  servidorPruebas.use(
    http.post(`${ORIGEN}/api/v1/lineas-base/:lineaBaseId/congelacion`, async ({ request, params }) => {
      const cuerpo: unknown = await request.json();
      congelaciones.push({ lineaBaseId: String(params.lineaBaseId), cuerpo, csrf: request.headers.get("X-CSRF-Token") });
      return responder(congelaciones.length);
    }),
  );
  const pantalla = await abrirPantalla(["DIRECTOR_PROYECTOS"], opciones);
  expect(await titulo()).toBeInTheDocument();
  return { ...pantalla, congelaciones };
}

/** Un servidor que empieza con la obra en PLANEACION y su BORRADOR, y que desde `congelar()` sirve la obra ACTIVA y la CONGELADA. */
function servidorQueCongela() {
  let hecho = false;
  const opciones: OpcionesPantalla = {
    responderObra: () => HttpResponse.json(hecho ? obraActiva() : obra()),
    responderLineas: () => HttpResponse.json([hecho ? congelada() : lineaBase()]),
    // Desde B2, una vez congelada la pantalla pide el control; mientras sea BORRADOR no debe pedirlo (lo cuenta `pedidas.control`).
    control: controlSinTopes(),
  };
  function congelar(): Response {
    hecho = true;
    return HttpResponse.json(congelada());
  }
  return { opciones, congelar };
}

function campoMotivo() {
  return within(principal()).getByRole("textbox", { name: ETIQUETA_MOTIVO });
}

function botonCongelar() {
  return within(principal()).getByRole("button", { name: BOTON_CONGELAR });
}

type Usuario = Awaited<ReturnType<typeof abrirPantalla>>["usuario"];

async function congelarCon(usuario: Usuario, motivo: string) {
  if (motivo !== "") await usuario.type(campoMotivo(), motivo);
  await usuario.click(botonCongelar());
}

/** El bloqueo o el conflicto que pinta el formulario, por el título de su región. */
function regionDe(nombre: string) {
  return within(principal()).findByRole("region", { name: nombre });
}

/** El valor de un rótulo del detalle de un rechazo (`dt` y su `dd`), dentro de su región. */
function valorEn(region: HTMLElement, rotulo: string): string {
  const termino = within(region).getByText(rotulo, { selector: "dt" });
  return termino.nextElementSibling?.textContent.trim() ?? "";
}

/** El estado de la línea base en la cabecera, también cuando un rechazo trae su propio «Estado» en el detalle. */
function estadoEnCabecera(rechazo?: HTMLElement): string {
  const terminos = within(principal())
    .getAllByText("Estado", { selector: "dt" })
    .filter((termino) => rechazo === undefined || !rechazo.contains(termino));
  expect(terminos).toHaveLength(1);
  return terminos[0]?.nextElementSibling?.textContent.trim() ?? "";
}

/** Ningún rechazo del congelado cambia lo que se ve de la línea base ni vuelve a pedirla (CA-4). */
function esperarQueSigueBorrador(pedidas: { obra: string[]; lineas: string[] }, rechazo?: HTMLElement) {
  expect(estadoEnCabecera(rechazo)).toBe("BORRADOR");
  expect(valorDe("Estado de la obra")).toBe("PLANEACION");
  expect(screen.queryByText(/Congelada el/)).not.toBeInTheDocument();
  expect(pedidas.obra).toHaveLength(1);
  expect(pedidas.lineas).toHaveLength(1);
}

function esperarSinBloqueo() {
  expect(within(principal()).queryByRole("region")).not.toBeInTheDocument();
  expect(principal().querySelector('[data-estado="bloqueado"]')).toBeNull();
}

describe("TKT-018a · TC-06 · el formulario de congelado del Director de Proyectos (CA-2, CA-13)", () => {
  test("hdu001_esc14 · borrador para el Director de Proyectos · TC-06 · el campo «Motivo (obligatorio)» vacío, el botón «Congelar línea base» y la advertencia del congelado", async () => {
    const { congelaciones, pedidas } = await abrirParaCongelar(() => HttpResponse.json(congelada()), { vigilarControl: true });

    expect(campoMotivo()).toHaveValue("");
    expect(botonCongelar()).toBeEnabled();
    // El texto del wireframe 4a: qué pasa al congelar.
    expect(within(principal()).getByText(/Al congelar, los conceptos y la explosión por tipo de partida se copian/)).toBeInTheDocument();
    expect(within(principal()).getByText(/La obra pasa a ACTIVA\./)).toBeInTheDocument();
    // El único campo de la pantalla es el motivo, y mostrarlo no envía nada.
    expect(camposFueraDeTablas()).toHaveLength(1);
    expect(screen.getByText(TEXTO_CONGELA_PRIMERO)).toBeInTheDocument();
    expect(congelaciones).toHaveLength(0);
    expect(pedidas.control).toHaveLength(0);
  });
});

describe("TKT-018a · TC-10 · congelar la línea base (CA-3)", () => {
  test("hdu001_esc14 · congelar con motivo · TC-10 · un POST con el motivo y el token CSRF; la pantalla pasa a CONGELADA y ACTIVA, sin campo ni botón", async () => {
    const servidor = servidorQueCongela();
    // Desde B2 la vista congelada pide el control: `servidor.opciones` lo dobla. La aserción de TC-24 vive en su propia prueba.
    const { usuario, congelaciones, pedidas } = await abrirParaCongelar(() => servidor.congelar(), servidor.opciones);

    await congelarCon(usuario, MOTIVO_CONGELADO);

    await waitFor(() => expect(valorDe("Estado")).toBe("CONGELADA"));
    expect(congelaciones).toHaveLength(1);
    expect(congelaciones[0]?.lineaBaseId).toBe(ID_LINEA_BASE);
    expect(congelaciones[0]?.cuerpo).toEqual({ motivo: MOTIVO_CONGELADO });
    expect(congelaciones[0]?.csrf).toBe(tokenCsrf().token);

    // La obra y la lista se vuelven a pedir una vez, y la pantalla enseña lo que el servidor sirve ahora.
    await waitFor(() => expect(valorDe("Estado de la obra")).toBe("ACTIVA"));
    expect(pedidas.obra).toHaveLength(2);
    expect(pedidas.lineas).toHaveLength(2);
    const fecha = within(principal()).getByText(/Congelada el/);
    expect(fecha).toHaveTextContent("J. Ramírez");
    expect(fecha.querySelector("time")).toHaveAttribute("datetime", CONGELADA_EN);
    expect(within(principal()).getByText(new RegExp(`Motivo: ${MOTIVO_CONGELADO}`))).toBeInTheDocument();

    // Modo lectura: ni campo, ni botón, ni el texto del borrador, ni rechazo alguno.
    expect(camposFueraDeTablas()).toHaveLength(0);
    expect(within(principal()).queryByRole("button", { name: /Congelar/i })).not.toBeInTheDocument();
    expect(screen.queryByText(TEXTO_CONGELA_PRIMERO)).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    esperarSinBloqueo();
  });
});

// Fila B2 · TC-24 · continuación de TC-10: al congelar aparece el presupuesto de control. El Director de Proyectos
// congela pero no captura (CA-13): ve las cuatro filas en lectura. La captura (TC-22, TC-23) está en
// `TablaPresupuestoControl.test.tsx`.
describe("TKT-018a · TC-24 · tras congelar aparece el presupuesto de control (CA-3)", () => {
  /** La tabla del control: la única de la pantalla con la columna «Tope de control». */
  function tablaControl(): HTMLElement {
    const tablas = within(principal())
      .queryAllByRole("table")
      .filter((tabla) => within(tabla).queryByRole("columnheader", { name: "Tope de control" }) !== null);
    const [tabla] = tablas;
    if (tablas.length !== 1 || tabla === undefined) throw new Error(`Se esperaba una tabla de control y hay ${tablas.length}.`);
    return tabla;
  }

  test("hdu001_esc14 · tras congelar aparece el control · TC-24 · «Presupuesto de control» con sus cuatro tipos, sin campos ni botones de captura", async () => {
    const servidor = servidorQueCongela();
    const { usuario, pedidas } = await abrirParaCongelar(() => servidor.congelar(), servidor.opciones);
    // En BORRADOR no hay presupuesto de control: ni encabezado ni petición.
    expect(screen.queryByRole("heading", { name: "Presupuesto de control" })).not.toBeInTheDocument();
    expect(pedidas.control).toHaveLength(0);

    await congelarCon(usuario, MOTIVO_CONGELADO);

    expect(await within(principal()).findByRole("heading", { level: 2, name: "Presupuesto de control" })).toBeInTheDocument();
    await waitFor(() => expect(within(tablaControl()).getAllByRole("row")).toHaveLength(5));
    // Pide el control de la línea base que se congeló, y solo después de congelar.
    expect(pedidas.control).toEqual([ID_LINEA_BASE]);

    // Las cuatro filas en el orden en que llegan (el de `tipo_partida.id`), cada una con su venta y «sin capturar».
    const filas = within(tablaControl()).getAllByRole("row").slice(1);
    const esperado = [
      ["MUROS", "$30,000.00"],
      ["PLAFONES Y CAJILLOS", "$18,500.00"],
      ["ENCHAPES", "$6,600.00"],
      ["GENERALES", "$7,400.00"],
    ] as const;
    esperado.forEach(([nombre, venta], indice) => {
      const fila = filas[indice];
      if (fila === undefined) throw new Error(`Falta la fila ${indice + 1} del presupuesto de control.`);
      expect(fila.textContent?.trim().startsWith(nombre)).toBe(true);
      expect(within(fila).getByText(venta)).toBeInTheDocument();
      expect(within(fila).getAllByText("sin capturar").length).toBeGreaterThan(0);
    });

    // El Director de Proyectos no captura: ni campos, ni «Guardar topes», ni «Recapturar».
    expect(within(principal()).queryAllByRole("textbox")).toHaveLength(0);
    expect(within(principal()).queryByRole("button", { name: /Guardar topes|Recapturar/ })).not.toBeInTheDocument();
    expect(within(principal()).queryByRole("button", { name: /Congelar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("TKT-018a · TC-11 y TC-12 · el motivo del congelado (CA-4)", () => {
  test.each([
    ["vacío", ""],
    ["solo espacios", "   "],
  ])(
    "hdu001_esc14 · motivo vacío o en blanco · TC-11 · %s: «El motivo es obligatorio.» junto al campo y cero POST",
    async (_caso, motivo) => {
      const { usuario, congelaciones, pedidas } = await abrirParaCongelar(() => HttpResponse.json(congelada()));

      await congelarCon(usuario, motivo);

      await waitFor(() => expect(campoMotivo()).toHaveAccessibleDescription(TEXTO_MOTIVO_OBLIGATORIO));
      expect(campoMotivo()).toHaveAttribute("aria-invalid", "true");
      expect(congelaciones).toHaveLength(0);
      expect(veces(`POST ${RUTA_CONGELACION}`)).toBe(0);
      esperarSinBloqueo();
      esperarQueSigueBorrador(pedidas);
    },
  );

  // Mutante M-1: si el 422 de `motivo` no llega al campo, cae aquí.
  test("hdu001_esc14 · 422 del servidor · TC-12 · el mensaje de `motivo` junto al campo con aria-invalid, sin bloqueo, y sigue BORRADOR", async () => {
    const rechazo = errorValidacion([{ campo: "motivo", codigo: "FORMATO", mensaje: MENSAJE_422_MOTIVO }]);
    const { usuario, congelaciones, pedidas } = await abrirParaCongelar(() => HttpResponse.json(rechazo, { status: 422 }));

    await congelarCon(usuario, MOTIVO_CONGELADO);

    await waitFor(() => expect(campoMotivo()).toHaveAccessibleDescription(MENSAJE_422_MOTIVO));
    expect(campoMotivo()).toHaveAttribute("aria-invalid", "true");
    // Lo escrito no se pierde y el mensaje va en el campo, no en una alerta ni en una pantalla de bloqueo.
    expect(campoMotivo()).toHaveValue(MOTIVO_CONGELADO);
    expect(within(principal()).getAllByText(MENSAJE_422_MOTIVO)).toHaveLength(1);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(principal()).not.toHaveTextContent(rechazo.mensaje);
    esperarSinBloqueo();
    expect(congelaciones).toHaveLength(1);
    esperarQueSigueBorrador(pedidas);
  });

  // Añadido del tester: la fila `FormularioCongelado.tsx` del diseño dice que los demás errores del 422 van, unidos, a la alerta.
  test("hdu001_esc14 · 422 del servidor · TC-12 · el error de otro campo va a la alerta y el de `motivo`, a su campo", async () => {
    const deOtroCampo = "El valor no está entre los permitidos.";
    const rechazo = errorValidacion([
      { campo: "motivo", codigo: "FORMATO", mensaje: MENSAJE_422_MOTIVO },
      { campo: "extra", codigo: "VALOR_NO_PERMITIDO", mensaje: deOtroCampo },
    ]);
    const { usuario, pedidas } = await abrirParaCongelar(() => HttpResponse.json(rechazo, { status: 422 }));

    await congelarCon(usuario, MOTIVO_CONGELADO);

    const alerta = await within(principal()).findByRole("alert");
    expect(alerta).toHaveTextContent(deOtroCampo);
    expect(alerta).not.toHaveTextContent(MENSAJE_422_MOTIVO);
    expect(campoMotivo()).toHaveAccessibleDescription(MENSAJE_422_MOTIVO);
    expect(campoMotivo()).toHaveAttribute("aria-invalid", "true");
    esperarSinBloqueo();
    esperarQueSigueBorrador(pedidas);
  });

  test("hdu001_esc14 · 422 sin errores de campo · TC-12 · el mensaje del servidor va a la alerta", async () => {
    const rechazo = errorValidacion([]);
    const { usuario } = await abrirParaCongelar(() => HttpResponse.json(rechazo, { status: 422 }));

    await congelarCon(usuario, MOTIVO_CONGELADO);

    expect(await within(principal()).findByRole("alert")).toHaveTextContent(rechazo.mensaje);
  });
});

describe("TKT-018a · TC-13 · segunda línea base vigente (CA-4, RN-01)", () => {
  test("hdu001_esc19 · segunda vigente · TC-13 · la pantalla de bloqueo con «Regla RN-01», el mensaje, la obra y la versión vigente, sin acciones; sigue BORRADOR", async () => {
    const rechazo = errorRn01SegundaVigente();
    const { usuario, congelaciones, pedidas } = await abrirParaCongelar(() => HttpResponse.json(rechazo, { status: 409 }));

    await congelarCon(usuario, MOTIVO_CONGELADO);

    const bloqueo = await regionDe("Operación bloqueada");
    expect(bloqueo).toHaveAttribute("data-estado", "bloqueado");
    expect(within(bloqueo).getByText("Regla RN-01")).toBeInTheDocument();
    expect(within(bloqueo).getByText(rechazo.mensaje)).toBeInTheDocument();
    expect(valorEn(bloqueo, "Obra")).toBe("AP-058-25 · Union Square F2");
    expect(valorEn(bloqueo, "Versión vigente")).toBe("1");
    expect(bloqueo).toHaveTextContent(`Referencia: ${rechazo.correlacion_id}`);
    // El servidor no ofrece ninguna acción: la única salida es cerrar. Y el identificador interno no se pinta.
    expect(within(bloqueo).getAllByRole("button").map((boton) => boton.textContent)).toEqual(["Cerrar"]);
    expect(principal()).not.toHaveTextContent(ID_LINEA_BASE_VIGENTE);
    // Un bloqueo no es un error: sin alerta.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(congelaciones).toHaveLength(1);
    esperarQueSigueBorrador(pedidas);
  });

  test("hdu001_esc19 · segunda vigente · TC-13 · «Cerrar» quita el bloqueo y deja el formulario con lo escrito, sin otro POST", async () => {
    const { usuario, congelaciones, pedidas } = await abrirParaCongelar(() =>
      HttpResponse.json(errorRn01SegundaVigente(), { status: 409 }),
    );
    await congelarCon(usuario, MOTIVO_CONGELADO);
    const bloqueo = await regionDe("Operación bloqueada");

    await usuario.click(within(bloqueo).getByRole("button", { name: "Cerrar" }));

    esperarSinBloqueo();
    expect(campoMotivo()).toHaveValue(MOTIVO_CONGELADO);
    expect(botonCongelar()).toBeEnabled();
    expect(congelaciones).toHaveLength(1);
    esperarQueSigueBorrador(pedidas);
  });
});

describe("TKT-018a · TC-14 · 409 de estado al congelar (CA-4)", () => {
  test("hdu001_esc14 · 409 de estado · TC-14 · ESTADO_NO_PERMITE_OPERACION con estado CONGELADA: el mensaje y «Estado CONGELADA» en línea, sin acciones", async () => {
    const rechazo = errorLineaBaseEnOtroEstado("CONGELADA");
    const { usuario, congelaciones, pedidas } = await abrirParaCongelar(() => HttpResponse.json(rechazo, { status: 409 }));

    await congelarCon(usuario, MOTIVO_CONGELADO);

    const conflicto = await regionDe("No se puede completar");
    expect(conflicto).toHaveAttribute("data-estado", "bloqueado");
    expect(within(conflicto).getByText("ESTADO_NO_PERMITE_OPERACION")).toBeInTheDocument();
    expect(within(conflicto).getByText(rechazo.mensaje)).toBeInTheDocument();
    expect(valorEn(conflicto, "Estado")).toBe("CONGELADA");
    expect(within(conflicto).queryAllByRole("button")).toHaveLength(0);
    // Un conflicto no viola ninguna regla RN ni es un error; el identificador interno no se pinta.
    expect(screen.queryByText(/Operación bloqueada/)).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(principal()).not.toHaveTextContent(ID_LINEA_BASE);
    expect(principal()).not.toHaveTextContent("linea_base_id");
    // El formulario sigue ahí con lo escrito, y la pantalla no se da por congelada por su cuenta.
    expect(campoMotivo()).toHaveValue(MOTIVO_CONGELADO);
    expect(congelaciones).toHaveLength(1);
    esperarQueSigueBorrador(pedidas, conflicto);
  });

  test("hdu001_esc14 · 409 de estado · TC-14 · la explosión no calculable: el mensaje y la tabla «Causas»", async () => {
    const rechazo = errorExplosionNoCalculable();
    const { usuario, pedidas } = await abrirParaCongelar(() => HttpResponse.json(rechazo, { status: 409 }));

    await congelarCon(usuario, MOTIVO_CONGELADO);

    const conflicto = await regionDe("No se puede completar");
    expect(within(conflicto).getByText(rechazo.mensaje)).toBeInTheDocument();
    expect(within(conflicto).getByText("ESTADO_NO_PERMITE_OPERACION")).toBeInTheDocument();
    const tabla = within(conflicto).getByRole("table", { name: "Causas" });
    expect(within(tabla).getAllByRole("columnheader").map((columna) => columna.textContent)).toEqual(["Concepto", "Causa", "Insumo"]);
    const filas = within(tabla).getAllByRole("row");
    expect(filas).toHaveLength(3);
    const [, primera] = filas;
    if (primera === undefined) throw new Error("Falta la fila de la primera causa");
    expect(within(primera).getAllByRole("cell").map((celda) => celda.textContent)).toEqual([
      "620040-A", "INSUMO_SIN_COSTO", "TAB-0127",
    ]);
    expect(filas[2]).toHaveTextContent("SUGERIDO_NEGATIVO");
    expect(within(conflicto).queryAllByRole("button")).toHaveLength(0);
    expect(principal()).not.toHaveTextContent(ID_LINEA_BASE);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    esperarQueSigueBorrador(pedidas, conflicto);
  });
});

describe("TKT-018a · TC-15 · concurrencia al congelar (CA-4)", () => {
  test("hdu001_esc14 · concurrencia · TC-15 · «Inténtalo de nuevo» con «Reintentar» deshabilitado durante el Retry-After; al pulsarlo, segundo POST con el mismo motivo", async () => {
    const servidor = servidorQueCongela();
    const rechazo = errorCongeladoBloqueoVencido();
    const { usuario, congelaciones, pedidas } = await abrirParaCongelar(
      (intento) => (intento === 1 ? HttpResponse.json(rechazo, { status: 409, headers: { "Retry-After": "3" } }) : servidor.congelar()),
      servidor.opciones,
    );

    await congelarCon(usuario, MOTIVO_CONGELADO);

    const conflicto = await regionDe("Inténtalo de nuevo");
    expect(within(conflicto).getByText(rechazo.mensaje)).toBeInTheDocument();
    expect(conflicto).not.toHaveTextContent("espera_maxima_ms");
    expect(screen.queryByText(/Operación bloqueada/)).not.toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    const reintentar = within(conflicto).getByRole("button", { name: "Reintentar" });
    expect(reintentar).toBeDisabled();
    esperarQueSigueBorrador(pedidas, conflicto);

    // La espera es la del servidor (3 s): a 1 s sigue cerrado y pasados los 3 s se abre. El reloj lo mueve la prueba.
    act(() => {
      vi.advanceTimersByTime(1_000);
    });
    expect(reintentar).toBeDisabled();
    expect(congelaciones).toHaveLength(1);
    act(() => {
      vi.advanceTimersByTime(3_000);
    });
    expect(reintentar).toBeEnabled();

    await usuario.click(reintentar);

    await waitFor(() => expect(congelaciones).toHaveLength(2));
    expect(congelaciones[1]?.lineaBaseId).toBe(ID_LINEA_BASE);
    expect(congelaciones[1]?.cuerpo).toEqual({ motivo: MOTIVO_CONGELADO });
    expect(congelaciones[1]?.csrf).toBe(tokenCsrf().token);
    // El reintento pasó: la pantalla queda congelada y el conflicto desaparece.
    await waitFor(() => expect(valorDe("Estado")).toBe("CONGELADA"));
    esperarSinBloqueo();
    expect(congelaciones).toHaveLength(2);
  });
});

describe("TKT-018a · TC-16 · 403 y 404 al congelar (CA-4, D-8)", () => {
  // Mutante M-10: el mensaje de la fábrica es distinto del literal de `errorPermiso`.
  test("hdu001_esc14 · 403 y 404 · TC-16 · 403: el mensaje del servidor y su referencia en la alerta, sin cifras; sigue BORRADOR", async () => {
    const rechazo = { ...errorPermiso("ROL_INSUFICIENTE"), mensaje: MENSAJE_403 };
    const { usuario, congelaciones, pedidas } = await abrirParaCongelar(() => HttpResponse.json(rechazo, { status: 403 }));

    await congelarCon(usuario, MOTIVO_CONGELADO);

    const alerta = await within(principal()).findByRole("alert");
    expect(alerta).toHaveTextContent(MENSAJE_403);
    expect(alerta).toHaveTextContent(`Referencia: ${CORRELACION_FABRICA}`);
    expect(alerta).not.toHaveTextContent(errorPermiso("ROL_INSUFICIENTE").mensaje);
    expect(alerta).not.toHaveTextContent("$");
    // Ni bloqueo, ni el aviso de sección sin permiso: la pantalla sigue ahí con su formulario.
    esperarSinBloqueo();
    expect(screen.queryByRole("heading", { name: TEXTO_SIN_PERMISO })).not.toBeInTheDocument();
    expect(await titulo()).toBeInTheDocument();
    expect(campoMotivo()).toHaveValue(MOTIVO_CONGELADO);
    expect(congelaciones).toHaveLength(1);
    esperarQueSigueBorrador(pedidas);
  });

  test("hdu001_esc14 · 403 y 404 · TC-16 · 403: la sesión se vuelve a pedir y el siguiente intento pide otro token CSRF, sin perder lo escrito", async () => {
    const rechazo = { ...errorPermiso("ROL_INSUFICIENTE"), mensaje: MENSAJE_403 };
    const { usuario, congelaciones } = await abrirParaCongelar(() => HttpResponse.json(rechazo, { status: 403 }));
    const sesionesAntes = veces(`GET ${RUTA_SESION}`);

    await congelarCon(usuario, MOTIVO_CONGELADO);
    await within(principal()).findByRole("alert");
    await waitFor(() => expect(veces(`GET ${RUTA_SESION}`)).toBe(sesionesAntes + 1));
    expect(veces(`GET ${RUTA_CSRF}`)).toBe(1);
    expect(campoMotivo()).toHaveValue(MOTIVO_CONGELADO);

    await usuario.click(botonCongelar());

    await waitFor(() => expect(congelaciones).toHaveLength(2));
    expect(veces(`GET ${RUTA_CSRF}`)).toBe(2);
    expect(congelaciones[1]?.cuerpo).toEqual({ motivo: MOTIVO_CONGELADO });
    expect(congelaciones[1]?.csrf).toBe(tokenCsrf().token);
    expect(await within(principal()).findByRole("alert")).toHaveTextContent(MENSAJE_403);
  });

  test("hdu001_esc14 · 403 y 404 · TC-16 · 404: «La línea base no existe.» en la alerta; sigue BORRADOR y no pasa a «La obra no existe»", async () => {
    const rechazo = errorNoEncontrado("linea_base", "La línea base no existe.");
    const { usuario, congelaciones, pedidas } = await abrirParaCongelar(() => HttpResponse.json(rechazo, { status: 404 }));

    await congelarCon(usuario, MOTIVO_CONGELADO);

    const alerta = await within(principal()).findByRole("alert");
    expect(alerta).toHaveTextContent("La línea base no existe.");
    expect(alerta).not.toHaveTextContent("$");
    // El 404 es del congelado, no de la carga: ni «La obra no existe» ni el error de carga con «Reintentar».
    expect(screen.queryByRole("heading", { name: "La obra no existe" })).not.toBeInTheDocument();
    expect(screen.queryByText(TEXTO_ERROR)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reintentar" })).not.toBeInTheDocument();
    esperarSinBloqueo();
    expect(campoMotivo()).toHaveValue(MOTIVO_CONGELADO);
    expect(congelaciones).toHaveLength(1);
    esperarQueSigueBorrador(pedidas);
  });

  test("hdu001_esc14 · 403 y 404 · TC-16 · 500: «No se pudo completar la operación. Referencia: …» en la alerta; sigue BORRADOR", async () => {
    const { usuario, pedidas } = await abrirParaCongelar(() =>
      HttpResponse.json({ mensaje: "Error interno del servidor.", correlacion_id: CORRELACION_500 }, { status: 500 }),
    );

    await congelarCon(usuario, MOTIVO_CONGELADO);

    expect(await within(principal()).findByRole("alert")).toHaveTextContent(
      `No se pudo completar la operación. Referencia: ${CORRELACION_500}`,
    );
    expect(principal()).not.toHaveTextContent("Error interno del servidor.");
    expect(campoMotivo()).toHaveValue(MOTIVO_CONGELADO);
    esperarQueSigueBorrador(pedidas);
  });
});

// Añadido del orquestador (desviación de A3): «Entradas hostiles» del diseño dice que una cifra que no es cadena
// decimal plana se pinta «No disponible»; hoy la pantalla pinta la cadena cruda del servidor.
describe("TKT-018a · importes mal formados del servidor (CA-2)", () => {
  test.each([["1e5"], ["abc"], ["Infinity"]])(
    "tkt018a_ca02 · un importe mal formado del servidor se pinta «No disponible» · %s",
    async (malFormado) => {
      const base = lineaBase();
      const [muros, ...demas] = base.por_tipo_partida;
      if (muros === undefined) throw new Error("La fábrica de línea base no trae tipos de partida.");
      await abrirPantalla(["DIRECCION_GENERAL"], {
        lineas: [lineaBase({ importe_venta: malFormado, por_tipo_partida: [{ ...muros, importe_venta: malFormado }, ...demas] })],
        vigilarControl: true,
      });

      expect(await titulo()).toBeInTheDocument();
      expect(valorDe("Importe de venta")).toBe("No disponible");
      const filaMuros = within(tablaDesglose()).getByRole("row", { name: /^MUROS\b/ });
      expect(within(filaMuros).getByText("No disponible")).toBeInTheDocument();
      // Ni la cadena cruda ni un número roto, y las demás cifras no se contagian.
      expect(principal()).not.toHaveTextContent(malFormado);
      expect(principal()).not.toHaveTextContent("NaN");
      esperarDesglose(DESGLOSE.slice(1));
    },
  );
});

// ---------------------------------------------------------------------------------------------------------------
// TKT-018a · fila A5 · TC-18 (CA-1, D-7). Las entradas «Línea base» y «Presupuesto de control» del menú siguen en
// su ruta y con su `h1`, pero en vez del marcador «Esta sección aún no está disponible» muestran `ElegirObra`, que
// remite a «Obras». Las pruebas no importan el componente: montan la aplicación en la ruta de la sección.
// `ElegirObra` no pide nada al servidor: aquí solo se doblan la sesión y el token, y `sinAtender` hace fallar la
// prueba si la pantalla pidiera una obra, una línea base o un presupuesto de control.
// ---------------------------------------------------------------------------------------------------------------

const SECCIONES_QUE_REMITEN: (keyof typeof RUTAS_DEL_MENU)[] = ["LINEA_BASE", "PRESUPUESTO_CONTROL"];
const RUTAS_DEL_MENU = { LINEA_BASE: "/obra/linea-base", PRESUPUESTO_CONTROL: "/obra/presupuesto-control" } as const;
// El punto final es opcional; el resto del texto, literal (D-7).
const TEXTO_ELIGE_OBRA = /^Elige la obra en «Obras»: su línea base y su presupuesto de control están en la misma pantalla\.?$/;
const ENLACE_OBRAS = "Ir a Obras";
const TEXTO_MARCADOR = "Esta sección aún no está disponible.";

const SECCION_POR_ROL_CON_ACCESO = SECCIONES_QUE_REMITEN.flatMap((clave) => ROLES_CON_ACCESO.map((rol) => [clave, rol] as const));
const SECCION_POR_ROL_SIN_ACCESO = SECCIONES_QUE_REMITEN.flatMap((clave) => ROLES_SIN_ACCESO.map((rol) => [clave, rol] as const));

/** Monta la aplicación en la ruta de menú de la sección, con la sesión del rol, y espera a que la sesión cargue. */
async function abrirSeccionDelMenu(clave: ClaveSeccion, roles: Rol[]) {
  servidorPruebas.use(
    http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(usuarioActual(roles))),
    http.get(`${ORIGEN}${RUTA_CSRF}`, () => HttpResponse.json(tokenCsrf())),
  );
  const aplicacion = renderizarAplicacion(seccion(clave).ruta);
  await screen.findByText(/Rosa Villanueva/);
  return aplicacion;
}

describe("TKT-018a · TC-18 · el menú remite a Obras (CA-1, D-7)", () => {
  test.each(SECCION_POR_ROL_CON_ACCESO)(
    "tkt018a_d7 · el menú remite a Obras · TC-18 · %s para %s: el título de la sección, el texto que remite a «Obras» y el enlace «Ir a Obras», sin el marcador",
    async (clave, rol) => {
      // La ruta del menú no cambia (D-7): la de `secciones.ts`, escrita aquí para que un cambio allí no pase inadvertido.
      expect(seccion(clave).ruta).toBe(RUTAS_DEL_MENU[clave]);
      const { router } = await abrirSeccionDelMenu(clave, [rol]);

      expect(await screen.findByRole("heading", { level: 1, name: seccion(clave).titulo })).toBeInTheDocument();
      expect(within(principal()).getByText(TEXTO_ELIGE_OBRA)).toBeInTheDocument();
      expect(within(principal()).getByRole("link", { name: ENLACE_OBRAS })).toHaveAttribute("href", "/obras");
      expect(screen.queryByText(TEXTO_MARCADOR)).not.toBeInTheDocument();

      // Sigue en su ruta, con un solo título, y no enseña nada de ninguna obra: ni cifras, ni tabla, ni controles.
      expect(router.state.location.pathname).toBe(seccion(clave).ruta);
      expect(within(principal()).getAllByRole("heading", { level: 1 })).toHaveLength(1);
      expect(within(principal()).queryByRole("table")).not.toBeInTheDocument();
      expect(within(principal()).queryAllByRole("button")).toHaveLength(0);
      expect(within(principal()).queryAllByRole("textbox")).toHaveLength(0);
      expect(screen.queryByRole("alert")).not.toBeInTheDocument();
      esperarSinCifras();
    },
  );

  test.each(SECCIONES_QUE_REMITEN)(
    "tkt018a_d7 · el menú remite a Obras · TC-18 · %s: «Ir a Obras» lleva a la lista de obras",
    async (clave) => {
      const listas: string[] = [];
      servidorPruebas.use(
        http.get(`${ORIGEN}/api/v1/obras`, ({ request }) => {
          listas.push(new URL(request.url).pathname);
          return HttpResponse.json({
            elementos: [obra()],
            paginacion: { pagina: 1, tamano_pagina: 200, total: 1 },
          } satisfies Esquemas["ListaObras"]);
        }),
      );
      const { usuario, router } = await abrirSeccionDelMenu(clave, ["DIRECTOR_PROYECTOS"]);
      await screen.findByRole("heading", { level: 1, name: seccion(clave).titulo });
      // Antes de pulsar, la sección no ha pedido la lista.
      expect(listas).toHaveLength(0);

      await usuario.click(within(principal()).getByRole("link", { name: ENLACE_OBRAS }));

      expect(await screen.findByRole("heading", { level: 1, name: "Obras" })).toBeInTheDocument();
      expect(router.state.location.pathname).toBe("/obras");
      expect(await screen.findByRole("cell", { name: "AP-058-25" })).toBeInTheDocument();
      expect(listas).toHaveLength(1);
    },
  );

  test.each(SECCION_POR_ROL_SIN_ACCESO)(
    "tkt018a_d7 · el menú remite a Obras · TC-18 · %s para %s, que no tiene la sección: «No tienes permiso para esta sección», sin texto ni enlace a Obras",
    async (clave, rol) => {
      const { router } = await abrirSeccionDelMenu(clave, [rol]);

      expect(await screen.findByRole("heading", { level: 1, name: TEXTO_SIN_PERMISO })).toBeInTheDocument();
      expect(router.state.location.pathname).toBe(seccion(clave).ruta);
      expect(screen.queryByRole("heading", { level: 1, name: seccion(clave).titulo })).not.toBeInTheDocument();
      expect(within(principal()).queryByText(TEXTO_ELIGE_OBRA)).not.toBeInTheDocument();
      expect(within(principal()).queryByRole("link", { name: ENLACE_OBRAS })).not.toBeInTheDocument();
      expect(screen.queryByText(TEXTO_MARCADOR)).not.toBeInTheDocument();
      esperarSinCifras();
    },
  );
});
