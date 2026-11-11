import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import type { components as Servidor } from "@/api/generado/servidor";
import type { Rol } from "@/api/sesion";
import {
  controlSinTopes,
  errorConcurrencia,
  errorPermiso,
  errorTopeSuperior,
  errorValidacion,
  filaControl,
  lineaBase,
  obra,
  tokenCsrf,
  usuarioActual,
} from "@/pruebas/cuerpos";
import { renderizarAplicacion } from "@/pruebas/render";
import { servidorPruebas } from "@/pruebas/servidor";
import { clavesLineaBase } from "./linea-base.consultas";

// TKT-018a · fila B2 · TC-22 a TC-29 (CA-6, CA-7, CA-9, CA-10, CA-11, CA-13, CA-R1). La tabla del presupuesto de control
// se prueba montada, como la monta la pantalla de la línea base CONGELADA, dentro de la aplicación completa en
// `/obras/:obraId/linea-base`. Ninguna prueba importa el componente: cada una falla hoy por el comportamiento ausente
// (la vista CONGELADA no pinta «Presupuesto de control»), no por un error de importación. Las recapturas (TC-30 a TC-34)
// son de la fila B3 y no están aquí.
// MSW es el servidor: las respuestas salen de las fábricas de `cuerpos.ts`, que cumplen los tipos generados del OpenAPI.

type Esquemas = Servidor["schemas"];
type PresupuestoControl = Esquemas["PresupuestoControl"];
type LineaBase = Esquemas["LineaBase"];

const ORIGEN = globalThis.location.origin;
const RUTA_SESION = "/api/v1/sesion";
const RUTA_CSRF = "/api/v1/sesion/csrf";

const ID_OBRA = lineaBase().obra_id;
const ID_LINEA_BASE = lineaBase().id;
const RUTA_PANTALLA = `/obras/${ID_OBRA}/linea-base`;
const RUTA_CONTROL = `/api/v1/lineas-base/${ID_LINEA_BASE}/presupuesto-control`;

const TITULO = "Línea base · AP-058-25 · Union Square F2";
const ID_QUIEN_CONGELO = "3b4c5d6e-7f80-4912-ab3c-4d5e6f708192";
const ID_M_TORRES = "4c5d6e7f-8091-4a23-bc4d-5e6f70819203";
const M_TORRES = { id: ID_M_TORRES, nombre: "M. Torres" };
const CAPTURADO_EN = "2026-11-11T16:00:00Z";
const CORRELACION_500 = "9d8c7b6a-5f4e-4d3c-8b2a-1f0e9d8c7b6a";
// Distinto, a propósito, del literal de `errorPermiso` («No tienes permiso para esta operación.»): así el mutante M-10 existe.
const MENSAJE_403 = "Tu rol no permite esta operación.";
const CORRELACION_FABRICA = errorPermiso("ROL_INSUFICIENTE").correlacion_id;
const MENSAJE_422_TOPE = "El importe del tope no es válido.";
const MENSAJE_IMPORTE_TOPE = "Escribe un importe sin signo ni comas, con hasta 14 enteros y 4 decimales, como 45000.00.";
const TEXTO_MOTIVO_OBLIGATORIO = "El motivo es obligatorio.";
const MOTIVO_TOPE = "Incluye andamiaje no presupuestado al cliente";

type ClaveTipoPartida = Esquemas["ClaveTipoPartida"];
const NOMBRE_DE: Record<ClaveTipoPartida, string> = {
  MUROS: "MUROS",
  PLAFONES_Y_CAJILLOS: "PLAFONES Y CAJILLOS",
  ENCHAPES: "ENCHAPES",
  GENERALES: "GENERALES",
};
const ID_DE: Record<ClaveTipoPartida, string> = {
  MUROS: filaControl("MUROS").tipo_partida.id,
  PLAFONES_Y_CAJILLOS: filaControl("PLAFONES_Y_CAJILLOS").tipo_partida.id,
  ENCHAPES: filaControl("ENCHAPES").tipo_partida.id,
  GENERALES: filaControl("GENERALES").tipo_partida.id,
};

// Los tiempos se controlan con el reloj simulado que avanza solo: `usuario` de userEvent lo exige y ninguna prueba hace `sleep`.
beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
afterEach(() => {
  vi.useRealTimers();
});

// `onUnhandledRequest: "error"` hace fallar la petición, no la prueba. Aquí además la prueba falla: toda petición que
// ningún doble atiende queda anotada y se comprueba al terminar.
const sinAtender: string[] = [];
function anotarSinAtender({ request }: { request: Request }) {
  sinAtender.push(`${request.method} ${new URL(request.url).pathname}`);
}
// Toda petición que sale, atendida o no: para contar las que provoca un 403 (sesión y token CSRF).
const vistas: string[] = [];
function anotarVista({ request }: { request: Request }) {
  vistas.push(`${request.method} ${new URL(request.url).pathname}`);
}
beforeEach(() => {
  sinAtender.length = 0;
  vistas.length = 0;
  servidorPruebas.events.on("request:unhandled", anotarSinAtender);
  servidorPruebas.events.on("request:start", anotarVista);
});
afterEach(() => {
  servidorPruebas.events.removeListener("request:unhandled", anotarSinAtender);
  servidorPruebas.events.removeListener("request:start", anotarVista);
  expect(sinAtender).toEqual([]);
});
function veces(peticion: string): number {
  return vistas.filter((vista) => vista === peticion).length;
}

function congelada(): LineaBase {
  return lineaBase({
    estado: "CONGELADA",
    congelada_en: "2026-10-15T17:30:00Z",
    congelada_por: { id: ID_QUIEN_CONGELO, nombre: "J. Ramírez" },
    motivo: "Contrato firmado el 13-oct-2026",
  });
}

interface Captura {
  tipoPartidaId: string;
  cuerpo: unknown;
  csrf: string | null;
}

function esCaptura(valor: unknown): valor is Esquemas["CapturaPresupuestoControl"] {
  return typeof valor === "object" && valor !== null && "importe_tope" in valor && typeof valor.importe_tope === "string";
}

function confirmaba(captura: Captura): boolean {
  return esCaptura(captura.cuerpo) && captura.cuerpo.confirmar_superior_a_venta;
}

/** El importe con la escala del servidor (4 decimales), construido sobre la cadena, sin convertirlo a número. */
function aEscala4(importe: string): string {
  const [enteros = "", decimales = ""] = importe.trim().split(".");
  return `${enteros}.${decimales.padEnd(4, "0")}`;
}

interface OpcionesTabla {
  /** Las filas del control que sirve el doble; por omisión, las cuatro sin tope. */
  filas?: PresupuestoControl[];
  /** Decide el `PUT` número `intento` (el primero es 1): una respuesta lo rechaza; `null` lo acepta y lo aplica a las filas. */
  rechazar?: (captura: Captura, intento: number) => Response | null;
  /** Sustituye a la respuesta 200 del `GET …/presupuesto-control`: para el error y para retrasarla. */
  responderControl?: () => Response | Promise<Response>;
  /** Por omisión espera a que la tabla pinte sus filas; las pruebas de cargando y de error lo desactivan. */
  esperarFilas?: boolean;
}

/**
 * Monta la aplicación en la pantalla de la obra con una línea base CONGELADA y la sesión del rol. El doble del control
 * sirve las filas, anota cada `GET` y cada `PUT` (tipo de partida, cuerpo y cabecera CSRF) y, si el `PUT` se acepta,
 * guarda la captura: el siguiente `GET` la devuelve, como el servidor.
 */
async function abrirTabla(roles: Rol[], opciones: OpcionesTabla = {}) {
  const filas = [...(opciones.filas ?? controlSinTopes())];
  const pedidas = { control: 0 };
  const capturas: Captura[] = [];

  servidorPruebas.use(
    http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(usuarioActual(roles))),
    http.get(`${ORIGEN}${RUTA_CSRF}`, () => HttpResponse.json(tokenCsrf())),
    http.get(`${ORIGEN}/api/v1/obras/:obraId`, () => HttpResponse.json(obra({ estado: "ACTIVA", linea_base_vigente_id: ID_LINEA_BASE }))),
    http.get(`${ORIGEN}/api/v1/obras/:obraId/lineas-base`, () => HttpResponse.json([congelada()])),
    http.get(`${ORIGEN}/api/v1/lineas-base/:lineaBaseId/presupuesto-control`, async () => {
      pedidas.control += 1;
      return opciones.responderControl === undefined ? HttpResponse.json(filas) : opciones.responderControl();
    }),
    http.put(`${ORIGEN}/api/v1/lineas-base/:lineaBaseId/presupuesto-control/:tipoPartidaId`, async ({ request, params }) => {
      const cuerpo: unknown = await request.json();
      const captura: Captura = {
        tipoPartidaId: String(params.tipoPartidaId),
        cuerpo,
        csrf: request.headers.get("X-CSRF-Token"),
      };
      capturas.push(captura);
      const rechazo = opciones.rechazar?.(captura, capturas.length) ?? null;
      if (rechazo !== null) return rechazo;

      const indice = filas.findIndex((fila) => fila.tipo_partida.id === captura.tipoPartidaId);
      const previa = filas[indice];
      if (previa === undefined || !esCaptura(cuerpo)) throw new Error("El doble recibió un PUT que no corresponde al control.");
      const guardada: PresupuestoControl =
        previa.importe_tope === null
          ? { ...previa, importe_tope: aEscala4(cuerpo.importe_tope), capturado_por: M_TORRES, capturado_en: CAPTURADO_EN }
          : {
              ...previa,
              importe_tope: aEscala4(cuerpo.importe_tope),
              actualizado_por: M_TORRES,
              actualizado_en: CAPTURADO_EN,
              motivo_ultimo_cambio: cuerpo.motivo ?? null,
            };
      filas[indice] = guardada;
      return HttpResponse.json(guardada);
    }),
  );

  const aplicacion = renderizarAplicacion(RUTA_PANTALLA);
  await screen.findByText(/Rosa Villanueva/);
  expect(await screen.findByRole("heading", { level: 1, name: TITULO })).toBeInTheDocument();
  if (opciones.esperarFilas ?? true) await waitFor(() => expect(filaDe("MUROS")).toBeInTheDocument());
  return { ...aplicacion, capturas, pedidas };
}

type Usuario = Awaited<ReturnType<typeof abrirTabla>>["usuario"];

/** El contenido de la pantalla, sin la cabecera ni el menú del armazón. */
function principal() {
  return screen.getByRole("main");
}

/** La tabla del presupuesto de control: la única de la pantalla con la columna «Tope de control». */
function tablaControl(): HTMLElement {
  const tablas = within(principal())
    .queryAllByRole("table")
    .filter((tabla) => within(tabla).queryByRole("columnheader", { name: "Tope de control" }) !== null);
  if (tablas.length !== 1) throw new Error(`Se esperaba una tabla de presupuesto de control y hay ${tablas.length}.`);
  const [tabla] = tablas;
  if (tabla === undefined) throw new Error("Falta la tabla del presupuesto de control.");
  return tabla;
}

/** La fila del tipo de partida en la tabla de control (no en el desglose de la línea base). */
function filaDe(clave: ClaveTipoPartida): HTMLElement {
  const nombre = NOMBRE_DE[clave];
  const fila = within(tablaControl())
    .getAllByRole("row")
    .find((candidata) => (candidata.textContent ?? "").trim().startsWith(nombre));
  if (fila === undefined) throw new Error(`Falta la fila de ${nombre} en el presupuesto de control.`);
  return fila;
}

function campoDe(clave: ClaveTipoPartida): HTMLElement {
  return within(filaDe(clave)).getByRole("textbox", { name: `Tope de ${NOMBRE_DE[clave]}` });
}

function botonGuardar() {
  return within(principal()).getByRole("button", { name: "Guardar topes" });
}

async function escribirTope(usuario: Usuario, clave: ClaveTipoPartida, valor: string) {
  await usuario.type(campoDe(clave), valor);
}

async function guardarTopes(usuario: Usuario) {
  await usuario.click(botonGuardar());
}

/** El resumen del guardado (`role="status"`); se espera por su texto, no por un tiempo. */
async function esperarResumen(texto: string) {
  await waitFor(() => expect(within(principal()).getByRole("status")).toHaveTextContent(texto));
}

function rechazo403() {
  return HttpResponse.json({ ...errorPermiso("ROL_INSUFICIENTE"), mensaje: MENSAJE_403 }, { status: 403 });
}

function filaCapturada(clave: ClaveTipoPartida, tope: string): PresupuestoControl {
  return filaControl(clave, { importe_tope: tope, capturado_por: M_TORRES, capturado_en: CAPTURADO_EN });
}

describe("TKT-018a · TC-22 · la tabla del presupuesto de control sin topes (CA-6, CA-R1)", () => {
  test("hdu001_esc15 · tabla sin topes · TC-22 · Dirección General ve el encabezado, cuatro filas con venta y sugerido, campos vacíos y «sin capturar»", async () => {
    const { pedidas, capturas } = await abrirTabla(["DIRECCION_GENERAL"]);

    expect(within(principal()).getByRole("heading", { level: 2, name: "Presupuesto de control" })).toBeInTheDocument();
    expect(
      within(tablaControl())
        .getAllByRole("columnheader")
        .map((columna) => columna.textContent),
    ).toEqual(["Tipo de partida", "Venta", "Sugerido", "Tope de control", "Capturado"]);

    const esperado: [ClaveTipoPartida, string, string][] = [
      ["MUROS", "$30,000.00", "$28,000.00"],
      ["PLAFONES_Y_CAJILLOS", "$18,500.00", "$17,500.00"],
      ["ENCHAPES", "$6,600.00", "$6,000.00"],
      ["GENERALES", "$7,400.00", "$7,000.00"],
    ];
    for (const [clave, venta, sugerido] of esperado) {
      const fila = filaDe(clave);
      expect(within(fila).getByText(venta)).toBeInTheDocument();
      expect(within(fila).getByText(sugerido)).toBeInTheDocument();
      // El campo nace vacío: el sugerido es una referencia, nunca el valor por omisión del tope.
      expect(campoDe(clave)).toHaveValue("");
      expect(within(fila).getByText("sin capturar")).toBeInTheDocument();
      expect(fila).not.toHaveTextContent("M. Torres");
    }
    expect(within(tablaControl()).getAllByRole("textbox")).toHaveLength(4);
    expect(botonGuardar()).toBeEnabled();
    // Pintar la tabla no captura nada: pide el control una vez y no envía ningún tope.
    expect(pedidas.control).toBe(1);
    expect(capturas).toHaveLength(0);
  });

  // Mutante M-7. Con `Number`, «99999999999999.9949» sale «$100,000,000,000,000.00» y «12345678901234.5650», «…4.56»;
  // el importe de 18 dígitos del plan por sí solo da el mismo texto con `Number` y no mata el mutante (ajuste de A3).
  test("hdu001_esc15 · tabla sin topes · TC-22 · borde: venta y sugerido de 18 dígitos se pintan sin pérdida de exactitud", async () => {
    await abrirTabla(["DIRECCION_GENERAL"], {
      filas: [
        filaControl("MUROS", { importe_venta: "99999999999999.9949", importe_sugerido: "12345678901234.5650" }),
        filaControl("PLAFONES_Y_CAJILLOS", { importe_venta: "12345678901234.5678" }),
        filaControl("ENCHAPES", { importe_venta: "12345678901234.5650", importe_sugerido: "99999999999999.9949" }),
        filaControl("GENERALES"),
      ],
    });

    const muros = filaDe("MUROS");
    expect(within(muros).getByText("$99,999,999,999,999.99")).toBeInTheDocument();
    expect(within(muros).getByText("$12,345,678,901,234.57")).toBeInTheDocument();
    expect(within(filaDe("PLAFONES_Y_CAJILLOS")).getByText("$12,345,678,901,234.57")).toBeInTheDocument();
    const enchapes = filaDe("ENCHAPES");
    expect(within(enchapes).getByText("$12,345,678,901,234.57")).toBeInTheDocument();
    expect(within(enchapes).getByText("$99,999,999,999,999.99")).toBeInTheDocument();
    expect(tablaControl()).not.toHaveTextContent("$100,000,000,000,000.00");
    expect(tablaControl()).not.toHaveTextContent("NaN");
  });
});

describe("TKT-018a · estados de la tabla del presupuesto de control", () => {
  // Añadido del tester: la fila `TablaPresupuestoControl.tsx` del diseño declara estos dos estados y el plan no los enumera.
  test("tkt018a_ca06 · cargando · TC-22 · un esqueleto con aria-busy mientras el servidor no responde, sin cifras ni campos", async () => {
    let soltar!: () => void;
    const compuerta = new Promise<void>((resolver) => {
      soltar = resolver;
    });
    const filas = controlSinTopes();
    await abrirTabla(["DIRECCION_GENERAL"], {
      esperarFilas: false,
      responderControl: async () => {
        await compuerta;
        return HttpResponse.json(filas);
      },
    });

    await waitFor(() => expect(principal().querySelector('[aria-busy="true"]')).not.toBeNull());
    expect(within(principal()).queryByRole("columnheader", { name: "Tope de control" })).not.toBeInTheDocument();
    expect(within(principal()).queryByRole("button", { name: "Guardar topes" })).not.toBeInTheDocument();

    soltar();
    await waitFor(() => expect(filaDe("MUROS")).toBeInTheDocument());
    expect(principal().querySelector('[aria-busy="true"]')).toBeNull();
  });

  test("tkt018a_ca06 · error · TC-22 · 500: la referencia de correlación y «Reintentar», que vuelve a pedir el control", async () => {
    let caido = true;
    const filas = controlSinTopes();
    const { usuario, pedidas } = await abrirTabla(["DIRECCION_GENERAL"], {
      esperarFilas: false,
      responderControl: () =>
        caido
          ? HttpResponse.json({ mensaje: "Error interno del servidor.", correlacion_id: CORRELACION_500 }, { status: 500 })
          : HttpResponse.json(filas),
    });

    const aviso = await within(principal()).findByRole("alert");
    expect(aviso).toHaveTextContent(`Referencia: ${CORRELACION_500}`);
    expect(pedidas.control).toBe(1);
    // Un error no es una tabla vacía: sin filas, sin campos y sin «Guardar topes».
    expect(within(principal()).queryByRole("columnheader", { name: "Tope de control" })).not.toBeInTheDocument();
    expect(within(principal()).queryByRole("button", { name: "Guardar topes" })).not.toBeInTheDocument();

    caido = false;
    await usuario.click(within(aviso).getByRole("button", { name: "Reintentar" }));

    await waitFor(() => expect(filaDe("MUROS")).toBeInTheDocument());
    expect(pedidas.control).toBe(2);
    expect(within(principal()).queryByRole("alert")).not.toBeInTheDocument();
  });
});

describe("TKT-018a · TC-23 · guardar topes (CA-6, CA-11)", () => {
  test("hdu001_esc15 · guardar topes · TC-23 · dos PUT en orden, con el cuerpo exacto y sin motivo; las filas guardadas muestran importe, autor y fecha", async () => {
    const { usuario, capturas, pedidas } = await abrirTabla(["DIRECCION_GENERAL"]);

    await escribirTope(usuario, "MUROS", "45000.00");
    await escribirTope(usuario, "PLAFONES_Y_CAJILLOS", " 38000.00 ");
    await guardarTopes(usuario);

    await esperarResumen("Se guardaron: MUROS, PLAFONES Y CAJILLOS.");
    // Exactamente dos PUT, en el orden de la tabla (el de `tipo_partida.id`), a la ruta de cada tipo y con el token CSRF.
    expect(capturas.map((captura) => captura.tipoPartidaId)).toEqual([ID_DE.MUROS, ID_DE.PLAFONES_Y_CAJILLOS]);
    expect(capturas[0]?.cuerpo).toEqual({ importe_tope: "45000.00", confirmar_superior_a_venta: false });
    expect(capturas[1]?.cuerpo).toEqual({ importe_tope: "38000.00", confirmar_superior_a_venta: false });
    expect(capturas.map((captura) => captura.csrf)).toEqual([tokenCsrf().token, tokenCsrf().token]);
    expect(veces(`PUT ${RUTA_CONTROL}/${ID_DE.MUROS}`)).toBe(1);
    expect(veces(`PUT ${RUTA_CONTROL}/${ID_DE.PLAFONES_Y_CAJILLOS}`)).toBe(1);

    // El control se vuelve a pedir y cada fila guardada enseña su captura.
    await waitFor(() => expect(pedidas.control).toBe(2));
    await waitFor(() => expect(filaDe("MUROS")).toHaveTextContent("$45,000.00"));
    for (const [clave, importe] of [
      ["MUROS", "$45,000.00"],
      ["PLAFONES_Y_CAJILLOS", "$38,000.00"],
    ] as const) {
      const fila = filaDe(clave);
      expect(within(fila).getByText(importe)).toBeInTheDocument();
      expect(fila).toHaveTextContent("M. Torres");
      expect(fila.querySelector("time")).toHaveAttribute("datetime", CAPTURADO_EN);
      expect(within(fila).queryByRole("textbox")).not.toBeInTheDocument();
    }
    // Las filas que no se capturaron siguen vacías, con su campo y «sin capturar».
    for (const clave of ["ENCHAPES", "GENERALES"] as const) {
      expect(campoDe(clave)).toHaveValue("");
      expect(within(filaDe(clave)).getByText("sin capturar")).toBeInTheDocument();
    }
    expect(within(principal()).getByRole("status")).not.toHaveTextContent("No se guardó");
  });

  // Mutante M-2: sin el filtro `importe_tope === null`, una fila ya capturada se reenvía desde el formulario.
  test("hdu001_esc15 · guardar topes · TC-23 · variante: una fila que ya llegó capturada no se envía", async () => {
    const filas = [
      filaCapturada("MUROS", "45000.0000"),
      filaControl("PLAFONES_Y_CAJILLOS"),
      filaControl("ENCHAPES"),
      filaControl("GENERALES"),
    ];
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], { filas });

    // La fila capturada se pinta en lectura: importe, autor y fecha, sin campo.
    expect(within(filaDe("MUROS")).getByText("$45,000.00")).toBeInTheDocument();
    expect(filaDe("MUROS")).toHaveTextContent("M. Torres");
    expect(within(filaDe("MUROS")).queryByRole("textbox")).not.toBeInTheDocument();

    await escribirTope(usuario, "PLAFONES_Y_CAJILLOS", "38000.00");
    await guardarTopes(usuario);

    await esperarResumen("Se guardaron: PLAFONES Y CAJILLOS.");
    expect(capturas).toHaveLength(1);
    expect(capturas[0]?.tipoPartidaId).toBe(ID_DE.PLAFONES_Y_CAJILLOS);
    expect(capturas[0]?.cuerpo).toEqual({ importe_tope: "38000.00", confirmar_superior_a_venta: false });
  });

  // Mutante M-2, la forma que de verdad lo distingue: el formulario conserva «45000.00» de MUROS tras guardarlo, y un
  // segundo guardado no debe reenviarlo (la fila ya tiene tope en el servidor).
  test("hdu001_esc15 · guardar topes · TC-23 · variante: un segundo guardado solo envía la fila nueva, no la que se guardó antes", async () => {
    const { usuario, capturas, pedidas } = await abrirTabla(["DIRECCION_GENERAL"]);
    await escribirTope(usuario, "MUROS", "45000.00");
    await guardarTopes(usuario);
    await esperarResumen("Se guardaron: MUROS.");
    await waitFor(() => expect(pedidas.control).toBe(2));
    await waitFor(() => expect(within(filaDe("MUROS")).queryByRole("textbox")).not.toBeInTheDocument());
    expect(capturas).toHaveLength(1);

    await escribirTope(usuario, "ENCHAPES", "6000.00");
    await guardarTopes(usuario);

    await esperarResumen("Se guardaron: ENCHAPES.");
    expect(capturas.map((captura) => captura.tipoPartidaId)).toEqual([ID_DE.MUROS, ID_DE.ENCHAPES]);
    expect(capturas[1]?.cuerpo).toEqual({ importe_tope: "6000.00", confirmar_superior_a_venta: false });
  });
});

describe("TKT-018a · TC-25 y TC-26 · tope superior a la venta (CA-7)", () => {
  /** El servidor rechaza el primer PUT con el 409 del tope superior y acepta el que trae la confirmación. */
  function exigirConfirmacion(clave: ClaveTipoPartida, venta: string, tope: string) {
    return (captura: Captura) =>
      confirmaba(captura) ? null : HttpResponse.json(errorTopeSuperior(clave, venta, tope), { status: 409 });
  }

  test("hdu001_esc17 · tope superior a la venta · TC-25 · el 409 abre el diálogo con el tipo de partida, la venta y el tope", async () => {
    const rechazo = errorTopeSuperior("GENERALES", "7400.0000", "8000.0000");
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], {
      rechazar: exigirConfirmacion("GENERALES", "7400.0000", "8000.0000"),
    });

    await escribirTope(usuario, "GENERALES", "8000.00");
    await guardarTopes(usuario);

    const dialogo = await screen.findByRole("dialog", { name: "Tope mayor que la venta · GENERALES" });
    expect(dialogo).toHaveTextContent("Venta $7,400.00");
    expect(dialogo).toHaveTextContent("Tope $8,000.00");
    expect(dialogo).toHaveTextContent(rechazo.mensaje);
    expect(within(dialogo).getByRole("button", { name: "Confirmar con motivo" })).toBeEnabled();
    expect(within(dialogo).getByRole("button", { name: "Corregir" })).toBeEnabled();
    // Un conflicto de negocio no es un error: sin alerta roja de la tabla. Y el primer PUT salió sin confirmación.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(capturas).toHaveLength(1);
    expect(capturas[0]?.cuerpo).toEqual({ importe_tope: "8000.00", confirmar_superior_a_venta: false });
  });

  test("hdu001_esc17 · tope superior a la venta · TC-25 · con PLAFONES Y CAJILLOS el título lleva el nombre y la descripción, la clave cruda del servidor", async () => {
    const { usuario } = await abrirTabla(["DIRECCION_GENERAL"], {
      rechazar: exigirConfirmacion("PLAFONES_Y_CAJILLOS", "18500.0000", "20000.0000"),
    });

    await escribirTope(usuario, "PLAFONES_Y_CAJILLOS", "20000.00");
    await guardarTopes(usuario);

    const dialogo = await screen.findByRole("dialog", { name: "Tope mayor que la venta · PLAFONES Y CAJILLOS" });
    expect(dialogo).toHaveTextContent("Venta $18,500.00");
    expect(dialogo).toHaveTextContent("Tope $20,000.00");
    // El texto del servidor se pinta tal cual, con la clave `PLAFONES_Y_CAJILLOS` (riesgo cosmético aceptado en el diseño).
    expect(dialogo).toHaveTextContent("El tope de PLAFONES_Y_CAJILLOS supera su importe de venta");
  });

  // Mutante M-3: si la confirmación reenvía con `confirmar_superior_a_venta: false`, el cuerpo exacto lo delata.
  test("hdu001_esc17 · tope superior a la venta · TC-25 · confirmar sin motivo no envía; con motivo, segundo PUT con el cuerpo exacto y la fila queda guardada", async () => {
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], {
      rechazar: exigirConfirmacion("GENERALES", "7400.0000", "8000.0000"),
    });
    await escribirTope(usuario, "GENERALES", "8000.00");
    await guardarTopes(usuario);
    const dialogo = await screen.findByRole("dialog", { name: "Tope mayor que la venta · GENERALES" });

    await usuario.click(within(dialogo).getByRole("button", { name: "Confirmar con motivo" }));

    const campoMotivo = within(dialogo).getByRole("textbox", { name: "Motivo" });
    await waitFor(() => expect(campoMotivo).toHaveAccessibleDescription(TEXTO_MOTIVO_OBLIGATORIO));
    expect(campoMotivo).toHaveAttribute("aria-invalid", "true");
    expect(capturas).toHaveLength(1);

    await usuario.type(campoMotivo, MOTIVO_TOPE);
    await usuario.click(within(dialogo).getByRole("button", { name: "Confirmar con motivo" }));

    await waitFor(() => expect(capturas).toHaveLength(2));
    expect(capturas[1]?.tipoPartidaId).toBe(ID_DE.GENERALES);
    expect(capturas[1]?.cuerpo).toEqual({
      importe_tope: "8000.00",
      motivo: MOTIVO_TOPE,
      confirmar_superior_a_venta: true,
    });
    expect(capturas[1]?.csrf).toBe(tokenCsrf().token);

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    // La fila queda guardada y el resumen la cuenta entre las guardadas, no entre las que no se guardaron.
    await esperarResumen("Se guardaron: GENERALES.");
    expect(within(principal()).getByRole("status")).not.toHaveTextContent("No se guardó");
    await waitFor(() => expect(within(filaDe("GENERALES")).getByText("$8,000.00")).toBeInTheDocument());
    expect(filaDe("GENERALES")).toHaveTextContent("M. Torres");
    expect(capturas).toHaveLength(2);
  });

  test("hdu001_esc17 · corregir · TC-26 · «Corregir» cierra el diálogo sin segundo PUT; el campo conserva «8000.00» con el mensaje del servidor y el resumen dice que no se guardó", async () => {
    const rechazo = errorTopeSuperior("GENERALES", "7400.0000", "8000.0000");
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], {
      rechazar: exigirConfirmacion("GENERALES", "7400.0000", "8000.0000"),
    });
    await escribirTope(usuario, "GENERALES", "8000.00");
    await guardarTopes(usuario);
    const dialogo = await screen.findByRole("dialog", { name: "Tope mayor que la venta · GENERALES" });

    await usuario.click(within(dialogo).getByRole("button", { name: "Corregir" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(capturas).toHaveLength(1);
    await waitFor(() => expect(campoDe("GENERALES")).toHaveAccessibleDescription(rechazo.mensaje));
    expect(campoDe("GENERALES")).toHaveValue("8000.00");
    expect(campoDe("GENERALES")).toHaveAttribute("aria-invalid", "true");
    await esperarResumen("No se guardó: GENERALES.");
    expect(within(principal()).getByRole("status")).not.toHaveTextContent("Se guardaron");
    // El tope no se guardó: la fila sigue sin capturar.
    expect(within(filaDe("GENERALES")).getByText("sin capturar")).toBeInTheDocument();
  });
});

describe("TKT-018a · TC-27 · quien no es Dirección General no captura (CA-9, CA-13)", () => {
  // Mutante M-6: si `puedeCapturar` incluyera al Director de Proyectos, esta prueba caería para ese rol.
  test.each<[string, Rol]>([
    ["el Director de Proyectos", "DIRECTOR_PROYECTOS"],
    ["Compras", "COMPRAS"],
  ])(
    "hdu001_esc23 · sin rol de Dirección General · TC-27 · %s ve la columna de tope en lectura: sin campos, sin «Guardar topes» y sin «Recapturar»",
    async (_nombre, rol) => {
      const filas = [
        filaCapturada("MUROS", "45000.0000"),
        filaControl("PLAFONES_Y_CAJILLOS"),
        filaControl("ENCHAPES"),
        filaControl("GENERALES"),
      ];
      const { capturas } = await abrirTabla([rol], { filas });

      // Lo que sí ve: la venta, el sugerido, el tope vigente con su autor y fecha, y «sin capturar».
      expect(within(principal()).getByRole("heading", { level: 2, name: "Presupuesto de control" })).toBeInTheDocument();
      expect(within(filaDe("MUROS")).getByText("$30,000.00")).toBeInTheDocument();
      expect(within(filaDe("MUROS")).getByText("$45,000.00")).toBeInTheDocument();
      expect(filaDe("MUROS")).toHaveTextContent("M. Torres");
      expect(filaDe("MUROS").querySelector("time")).toHaveAttribute("datetime", CAPTURADO_EN);
      expect(within(filaDe("ENCHAPES")).getAllByText("sin capturar").length).toBeGreaterThan(0);

      // Lo que no ve: ningún campo, ningún botón de captura ni de recaptura.
      expect(within(principal()).queryAllByRole("textbox")).toHaveLength(0);
      expect(within(tablaControl()).queryAllByRole("textbox")).toHaveLength(0);
      expect(within(principal()).queryByRole("button", { name: "Guardar topes" })).not.toBeInTheDocument();
      expect(within(principal()).queryByRole("button", { name: /Recapturar/ })).not.toBeInTheDocument();
      expect(within(tablaControl()).queryAllByRole("button")).toHaveLength(0);
      expect(capturas).toHaveLength(0);
    },
  );
});

describe("TKT-018a · TC-28 · tope mal formado en la tabla (CA-10)", () => {
  test.each([
    ["texto no numérico", "abc"],
    ["importe negativo", "-5"],
    ["más de cuatro decimales", "1.12345"],
    ["más de catorce dígitos enteros", "123456789012345"],
    ["notación científica", "1e5"],
  ])(
    "tkt018a_ca10 · tope mal formado en la tabla · TC-28 · %s (%s): el mensaje junto al campo con aria-invalid y cero PUT",
    async (_caso, entrada) => {
      const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"]);

      await escribirTope(usuario, "ENCHAPES", entrada);
      await guardarTopes(usuario);

      await waitFor(() => expect(campoDe("ENCHAPES")).toHaveAccessibleDescription(MENSAJE_IMPORTE_TOPE));
      expect(campoDe("ENCHAPES")).toHaveAttribute("aria-invalid", "true");
      expect(campoDe("ENCHAPES")).toHaveValue(entrada);
      expect(capturas).toHaveLength(0);
      expect(veces(`PUT ${RUTA_CONTROL}/${ID_DE.ENCHAPES}`)).toBe(0);
      // Las filas vacías no se marcan.
      expect(campoDe("MUROS")).not.toHaveAttribute("aria-invalid", "true");
    },
  );

  test("tkt018a_ca10 · tope mal formado en la tabla · TC-28 · con una fila válida y otra mal formada no sale ningún PUT", async () => {
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"]);

    await escribirTope(usuario, "MUROS", "45000.00");
    await escribirTope(usuario, "ENCHAPES", "1e5");
    await guardarTopes(usuario);

    await waitFor(() => expect(campoDe("ENCHAPES")).toHaveAccessibleDescription(MENSAJE_IMPORTE_TOPE));
    expect(campoDe("MUROS")).not.toHaveAttribute("aria-invalid", "true");
    expect(capturas).toHaveLength(0);
  });

  test("tkt018a_ca10 · tope mal formado en la tabla · TC-28 · un 422 del servidor sobre `importe_tope` se pinta en el campo de esa fila", async () => {
    const rechazo = errorValidacion([{ campo: "importe_tope", codigo: "FORMATO", mensaje: MENSAJE_422_TOPE }]);
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], {
      rechazar: () => HttpResponse.json(rechazo, { status: 422 }),
    });

    await escribirTope(usuario, "MUROS", "45000.00");
    await guardarTopes(usuario);

    await waitFor(() => expect(campoDe("MUROS")).toHaveAccessibleDescription(MENSAJE_422_TOPE));
    expect(campoDe("MUROS")).toHaveAttribute("aria-invalid", "true");
    expect(campoDe("MUROS")).toHaveValue("45000.00");
    expect(capturas).toHaveLength(1);
    // El mensaje va en el campo de su fila, no en una alerta ni en otra fila; el resumen dice que no se guardó.
    expect(campoDe("ENCHAPES")).not.toHaveAttribute("aria-invalid", "true");
    expect(within(principal()).queryByRole("alert")).not.toBeInTheDocument();
    await esperarResumen("No se guardó: MUROS.");
  });
});

describe("TKT-018a · TC-29 · éxito parcial al guardar topes (CA-11, CA-9)", () => {
  test("tkt018a_ca11 · éxito parcial · TC-29 · la segunda fila recibe 422: la primera y la tercera muestran su captura, la segunda conserva lo escrito con su mensaje y el resumen nombra ambas listas", async () => {
    const rechazo = errorValidacion([{ campo: "importe_tope", codigo: "FORMATO", mensaje: MENSAJE_422_TOPE }]);
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], {
      rechazar: (captura) =>
        captura.tipoPartidaId === ID_DE.PLAFONES_Y_CAJILLOS ? HttpResponse.json(rechazo, { status: 422 }) : null,
    });

    await escribirTope(usuario, "MUROS", "45000.00");
    await escribirTope(usuario, "PLAFONES_Y_CAJILLOS", "38000.00");
    await escribirTope(usuario, "ENCHAPES", "5000.00");
    await guardarTopes(usuario);

    await esperarResumen("Se guardaron: MUROS, ENCHAPES.");
    await esperarResumen("No se guardó: PLAFONES Y CAJILLOS.");
    // Un PUT por fila, en serie y en el orden de la tabla: el rechazo de la segunda no detiene la tercera.
    expect(capturas.map((captura) => captura.tipoPartidaId)).toEqual([ID_DE.MUROS, ID_DE.PLAFONES_Y_CAJILLOS, ID_DE.ENCHAPES]);

    await waitFor(() => expect(filaDe("MUROS")).toHaveTextContent("$45,000.00"));
    await waitFor(() => expect(filaDe("ENCHAPES")).toHaveTextContent("$5,000.00"));
    expect(filaDe("MUROS")).toHaveTextContent("M. Torres");
    expect(filaDe("ENCHAPES")).toHaveTextContent("M. Torres");
    // La rechazada conserva lo capturado y dice por qué.
    expect(campoDe("PLAFONES_Y_CAJILLOS")).toHaveValue("38000.00");
    expect(campoDe("PLAFONES_Y_CAJILLOS")).toHaveAccessibleDescription(MENSAJE_422_TOPE);
    expect(campoDe("PLAFONES_Y_CAJILLOS")).toHaveAttribute("aria-invalid", "true");
    expect(within(filaDe("PLAFONES_Y_CAJILLOS")).getByText("sin capturar")).toBeInTheDocument();
  });

  // El 403 invalida la sesión y descarta el token CSRF (`crear-aplicacion.tsx`, `cliente.ts`): el doble atiende un
  // `GET /sesion` y, antes del tercer PUT, un `GET /sesion/csrf` de más.
  test("tkt018a_ca11 · éxito parcial · TC-29 · la segunda fila recibe 403: su mensaje con la referencia, las otras se guardan y el cliente vuelve a pedir sesión y token", async () => {
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], {
      rechazar: (captura) => (captura.tipoPartidaId === ID_DE.PLAFONES_Y_CAJILLOS ? rechazo403() : null),
    });
    const sesionesAntes = veces(`GET ${RUTA_SESION}`);

    await escribirTope(usuario, "MUROS", "45000.00");
    await escribirTope(usuario, "PLAFONES_Y_CAJILLOS", "38000.00");
    await escribirTope(usuario, "ENCHAPES", "5000.00");
    await guardarTopes(usuario);

    await esperarResumen("Se guardaron: MUROS, ENCHAPES.");
    await esperarResumen("No se guardó: PLAFONES Y CAJILLOS.");
    expect(capturas.map((captura) => captura.tipoPartidaId)).toEqual([ID_DE.MUROS, ID_DE.PLAFONES_Y_CAJILLOS, ID_DE.ENCHAPES]);
    await waitFor(() => expect(filaDe("MUROS")).toHaveTextContent("$45,000.00"));
    await waitFor(() => expect(filaDe("ENCHAPES")).toHaveTextContent("$5,000.00"));

    // El mensaje es el del servidor (no el literal fijo de `errorPermiso`), con su referencia (D-8, mutante M-10).
    expect(campoDe("PLAFONES_Y_CAJILLOS")).toHaveAccessibleDescription(`${MENSAJE_403} Referencia: ${CORRELACION_FABRICA}`);
    expect(campoDe("PLAFONES_Y_CAJILLOS")).toHaveValue("38000.00");
    expect(campoDe("PLAFONES_Y_CAJILLOS")).toHaveAttribute("aria-invalid", "true");
    expect(within(filaDe("PLAFONES_Y_CAJILLOS")).getByText("sin capturar")).toBeInTheDocument();

    // Un token al primer PUT y otro, tras descartarlo, al tercero; y la sesión se vuelve a pedir una vez.
    await waitFor(() => expect(veces(`GET ${RUTA_SESION}`)).toBe(sesionesAntes + 1));
    expect(veces(`GET ${RUTA_CSRF}`)).toBe(2);
    expect(capturas.map((captura) => captura.csrf)).toEqual([tokenCsrf().token, tokenCsrf().token, tokenCsrf().token]);
  });
});

// TKT-018a · fila B3 · TC-30 a TC-34 (CA-7, CA-8, CA-9, CA-10): la recaptura de un tope ya capturado. Solo Dirección General
// la ve, solo en las filas con tope, y la hace un diálogo con dos campos («Tope nuevo» y «Motivo»). Como la tabla aún no
// tiene el botón «Recapturar», las pruebas montan la pantalla entera y fallan por el comportamiento ausente.
const FECHA_PREVIA = "2026-10-15T16:00:00Z";
const MOTIVO_RECAPTURA = "Ampliación de muros en nivel 9";
const MENSAJE_422_MOTIVO = "El motivo contiene caracteres no válidos.";
const TITULO_RECAPTURA = "Recapturar tope · MUROS";
const BOTON_RECAPTURAR_MUROS = "Recapturar MUROS";

/** MUROS con tope vigente de 45,000 capturado por M. Torres el 15-oct-2026 (CA-8); las otras tres, sin tope. */
function controlConMurosCapturado(): PresupuestoControl[] {
  return [
    filaControl("MUROS", { importe_tope: "45000.0000", capturado_por: M_TORRES, capturado_en: FECHA_PREVIA }),
    filaControl("PLAFONES_Y_CAJILLOS"),
    filaControl("ENCHAPES"),
    filaControl("GENERALES"),
  ];
}

/**
 * La fila de la tabla de control leída del DOM sin filtrar por accesibilidad: con el diálogo abierto, Radix oculta el
 * contenido (`aria-hidden`) y `getByRole` ya no lo ve, pero la fila sigue ahí y su texto es lo que la persona ve al cerrarlo.
 */
function filaTrasElDialogo(clave: ClaveTipoPartida): HTMLElement {
  const tabla = [...document.querySelectorAll<HTMLElement>("main table")].find((candidata) =>
    (candidata.textContent ?? "").includes("Tope de control"),
  );
  const fila = [...(tabla?.querySelectorAll<HTMLElement>("tr") ?? [])].find((candidata) =>
    (candidata.textContent ?? "").trim().startsWith(NOMBRE_DE[clave]),
  );
  if (fila === undefined) throw new Error(`Falta la fila de ${NOMBRE_DE[clave]} en el presupuesto de control.`);
  return fila;
}

/** Pulsa «Recapturar MUROS» en la tabla y espera el diálogo de la recaptura. */
async function abrirRecaptura(usuario: Usuario): Promise<HTMLElement> {
  await usuario.click(within(filaDe("MUROS")).getByRole("button", { name: BOTON_RECAPTURAR_MUROS }));
  return screen.findByRole("dialog", { name: TITULO_RECAPTURA });
}

async function escribirEnRecaptura(usuario: Usuario, dialogo: HTMLElement, tope: string, motivo?: string) {
  await usuario.type(within(dialogo).getByRole("textbox", { name: "Tope nuevo" }), tope);
  if (motivo !== undefined) await usuario.type(within(dialogo).getByRole("textbox", { name: /^Motivo/ }), motivo);
}

async function pulsarRecapturar(usuario: Usuario, dialogo: HTMLElement) {
  await usuario.click(within(dialogo).getByRole("button", { name: "Recapturar" }));
}

describe("TKT-018a · botón «Recapturar» (CA-8, CA-9, CA-13)", () => {
  test("hdu001_esc22 · recaptura · TC-30 · Dirección General ve «Recapturar {nombre}» solo en las filas con tope", async () => {
    const filas = [
      filaControl("MUROS", { importe_tope: "45000.0000", capturado_por: M_TORRES, capturado_en: FECHA_PREVIA }),
      filaControl("PLAFONES_Y_CAJILLOS"),
      filaControl("ENCHAPES", { importe_tope: "6000.0000", capturado_por: M_TORRES, capturado_en: FECHA_PREVIA }),
      filaControl("GENERALES"),
    ];
    const { capturas } = await abrirTabla(["DIRECCION_GENERAL"], { filas });

    expect(within(filaDe("MUROS")).getByRole("button", { name: "Recapturar MUROS" })).toBeEnabled();
    expect(within(filaDe("ENCHAPES")).getByRole("button", { name: "Recapturar ENCHAPES" })).toBeEnabled();
    // Sin tope no hay nada que recapturar: la fila tiene su campo y ningún botón.
    for (const clave of ["PLAFONES_Y_CAJILLOS", "GENERALES"] as const) {
      expect(within(filaDe(clave)).queryByRole("button")).not.toBeInTheDocument();
      expect(campoDe(clave)).toHaveValue("");
    }
    expect(within(tablaControl()).getAllByRole("button")).toHaveLength(2);
    // Mirar la tabla no captura nada.
    expect(capturas).toHaveLength(0);
  });
});

describe("TKT-018a · TC-30 · recaptura del tope (CA-8)", () => {
  // Mutante M-9: si el diálogo envía sin `motivo`, el cuerpo exacto lo delata.
  test("hdu001_esc22 · recaptura · TC-30 · el diálogo muestra el tope vigente con su autor y fecha; «50000.00» y el motivo salen en un PUT de cuerpo exacto y la fila enseña el tope nuevo", async () => {
    const { usuario, capturas, pedidas } = await abrirTabla(["DIRECCION_GENERAL"], { filas: controlConMurosCapturado() });

    const dialogo = await abrirRecaptura(usuario);
    expect(dialogo).toHaveTextContent("$45,000.00");
    expect(dialogo).toHaveTextContent("M. Torres");
    // La fecha se comprueba por su `datetime`, no por el texto: el texto depende de la zona horaria de quien corre la prueba.
    expect(dialogo.querySelector("time")).toHaveAttribute("datetime", FECHA_PREVIA);
    expect(dialogo).toHaveTextContent("Se registra en la bitácora con RN-03");
    expect(within(dialogo).getByRole("textbox", { name: "Tope nuevo" })).toHaveValue("");
    expect(within(dialogo).getByRole("textbox", { name: /^Motivo/ })).toHaveValue("");
    expect(within(dialogo).getByRole("button", { name: "Cancelar" })).toBeEnabled();
    expect(capturas).toHaveLength(0);

    await escribirEnRecaptura(usuario, dialogo, "50000.00", MOTIVO_RECAPTURA);
    await pulsarRecapturar(usuario, dialogo);

    await waitFor(() => expect(capturas).toHaveLength(1));
    expect(capturas[0]?.tipoPartidaId).toBe(ID_DE.MUROS);
    expect(capturas[0]?.cuerpo).toEqual({
      importe_tope: "50000.00",
      motivo: MOTIVO_RECAPTURA,
      confirmar_superior_a_venta: false,
    });
    expect(capturas[0]?.csrf).toBe(tokenCsrf().token);
    expect(veces(`PUT ${RUTA_CONTROL}/${ID_DE.MUROS}`)).toBe(1);

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    // El control se vuelve a pedir y la fila enseña el tope nuevo con el autor y la fecha de la recaptura.
    await waitFor(() => expect(pedidas.control).toBe(2));
    await waitFor(() => expect(filaDe("MUROS")).toHaveTextContent("$50,000.00"));
    expect(filaDe("MUROS")).not.toHaveTextContent("$45,000.00");
    expect(filaDe("MUROS")).toHaveTextContent("M. Torres");
    expect(filaDe("MUROS").querySelector("time")).toHaveAttribute("datetime", CAPTURADO_EN);
    expect(within(filaDe("MUROS")).getByRole("button", { name: BOTON_RECAPTURAR_MUROS })).toBeInTheDocument();
    expect(capturas).toHaveLength(1);
  });

  test("hdu001_esc22 · recaptura · TC-30 · «Cancelar» cierra el diálogo sin PUT, la fila no cambia y la siguiente apertura empieza vacía", async () => {
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], { filas: controlConMurosCapturado() });
    const dialogo = await abrirRecaptura(usuario);
    await escribirEnRecaptura(usuario, dialogo, "50000.00", MOTIVO_RECAPTURA);

    await usuario.click(within(dialogo).getByRole("button", { name: "Cancelar" }));

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(capturas).toHaveLength(0);
    expect(filaDe("MUROS")).toHaveTextContent("$45,000.00");
    expect(filaDe("MUROS")).not.toHaveTextContent("$50,000.00");

    const otraVez = await abrirRecaptura(usuario);
    expect(within(otraVez).getByRole("textbox", { name: "Tope nuevo" })).toHaveValue("");
    expect(within(otraVez).getByRole("textbox", { name: /^Motivo/ })).toHaveValue("");
    expect(capturas).toHaveLength(0);
  });
});

describe("TKT-018a · TC-31 · recaptura sin motivo (CA-9)", () => {
  test("hdu001_esc23 · recaptura sin motivo · TC-31 · «El motivo es obligatorio.» junto al campo, cero PUT y la fila sigue en «$45,000.00»", async () => {
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], { filas: controlConMurosCapturado() });
    const dialogo = await abrirRecaptura(usuario);
    await escribirEnRecaptura(usuario, dialogo, "50000.00");

    await pulsarRecapturar(usuario, dialogo);

    const campoMotivo = within(dialogo).getByRole("textbox", { name: /^Motivo/ });
    await waitFor(() => expect(campoMotivo).toHaveAccessibleDescription(TEXTO_MOTIVO_OBLIGATORIO));
    expect(campoMotivo).toHaveAttribute("aria-invalid", "true");
    // El tope bien formado no se marca y conserva lo escrito; el diálogo sigue abierto.
    expect(within(dialogo).getByRole("textbox", { name: "Tope nuevo" })).not.toHaveAttribute("aria-invalid", "true");
    expect(within(dialogo).getByRole("textbox", { name: "Tope nuevo" })).toHaveValue("50000.00");
    expect(screen.getByRole("dialog", { name: TITULO_RECAPTURA })).toBeInTheDocument();
    expect(capturas).toHaveLength(0);
    expect(veces(`PUT ${RUTA_CONTROL}/${ID_DE.MUROS}`)).toBe(0);
    expect(filaTrasElDialogo("MUROS")).toHaveTextContent("$45,000.00");
    expect(filaTrasElDialogo("MUROS")).not.toHaveTextContent("$50,000.00");
  });

  test("hdu001_esc23 · recaptura sin motivo · TC-31 · un motivo de solo espacios tampoco sale", async () => {
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], { filas: controlConMurosCapturado() });
    const dialogo = await abrirRecaptura(usuario);
    await escribirEnRecaptura(usuario, dialogo, "50000.00", "   ");

    await pulsarRecapturar(usuario, dialogo);

    await waitFor(() =>
      expect(within(dialogo).getByRole("textbox", { name: /^Motivo/ })).toHaveAccessibleDescription(TEXTO_MOTIVO_OBLIGATORIO),
    );
    expect(capturas).toHaveLength(0);
  });

  test("hdu001_esc23 · recaptura sin motivo · TC-31 · variante: el 422 del servidor en `motivo` se pinta junto al campo, el diálogo sigue abierto y la fila sigue en «$45,000.00»", async () => {
    const rechazo = errorValidacion([{ campo: "motivo", codigo: "FORMATO", mensaje: MENSAJE_422_MOTIVO }]);
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], {
      filas: controlConMurosCapturado(),
      rechazar: () => HttpResponse.json(rechazo, { status: 422 }),
    });
    const dialogo = await abrirRecaptura(usuario);
    await escribirEnRecaptura(usuario, dialogo, "50000.00", MOTIVO_RECAPTURA);

    await pulsarRecapturar(usuario, dialogo);

    const campoMotivo = within(dialogo).getByRole("textbox", { name: /^Motivo/ });
    await waitFor(() => expect(campoMotivo).toHaveAccessibleDescription(MENSAJE_422_MOTIVO));
    expect(campoMotivo).toHaveAttribute("aria-invalid", "true");
    expect(campoMotivo).toHaveValue(MOTIVO_RECAPTURA);
    expect(within(dialogo).getByRole("textbox", { name: "Tope nuevo" })).not.toHaveAttribute("aria-invalid", "true");
    expect(capturas).toHaveLength(1);
    expect(screen.getByRole("dialog", { name: TITULO_RECAPTURA })).toBeInTheDocument();
    expect(filaTrasElDialogo("MUROS")).toHaveTextContent("$45,000.00");
    expect(filaTrasElDialogo("MUROS")).not.toHaveTextContent("$50,000.00");
  });
});

describe("TKT-018a · TC-32 · 403 en la recaptura (CA-9)", () => {
  // Mutante M-10: la fábrica fija otro `mensaje` que el literal de `errorPermiso`.
  test("hdu001_esc23 · 403 en la recaptura · TC-32 · el mensaje del servidor con su referencia, dentro del diálogo; la fila no cambia y el cliente vuelve a pedir la sesión", async () => {
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], {
      filas: controlConMurosCapturado(),
      rechazar: () => rechazo403(),
    });
    const sesionesAntes = veces(`GET ${RUTA_SESION}`);
    const dialogo = await abrirRecaptura(usuario);
    await escribirEnRecaptura(usuario, dialogo, "50000.00", MOTIVO_RECAPTURA);

    await pulsarRecapturar(usuario, dialogo);

    const aviso = await within(dialogo).findByRole("alert");
    expect(aviso).toHaveTextContent(`${MENSAJE_403} Referencia: ${CORRELACION_FABRICA}`);
    expect(dialogo).not.toHaveTextContent("No tienes permiso para esta operación.");
    expect(capturas).toHaveLength(1);
    expect(screen.getByRole("dialog", { name: TITULO_RECAPTURA })).toBeInTheDocument();
    // Lo escrito se conserva y el tope vigente no cambia.
    expect(within(dialogo).getByRole("textbox", { name: "Tope nuevo" })).toHaveValue("50000.00");
    expect(within(dialogo).getByRole("textbox", { name: /^Motivo/ })).toHaveValue(MOTIVO_RECAPTURA);
    expect(filaTrasElDialogo("MUROS")).toHaveTextContent("$45,000.00");
    expect(filaTrasElDialogo("MUROS")).not.toHaveTextContent("$50,000.00");
    // Cada 403 invalida la sesión: el cliente la vuelve a pedir una vez.
    await waitFor(() => expect(veces(`GET ${RUTA_SESION}`)).toBe(sesionesAntes + 1));
  });
});

describe("TKT-018a · TC-33 · recaptura superior a la venta (CA-7, CA-8)", () => {
  /** El servidor rechaza el PUT sin confirmación con el 409 del tope superior y acepta el que la trae. */
  function exigirConfirmacionMuros() {
    return (captura: Captura) =>
      confirmaba(captura) ? null : HttpResponse.json(errorTopeSuperior("MUROS", "30000.0000", "50000.0000"), { status: 409 });
  }

  test("hdu001_esc17 · recaptura superior a la venta · TC-33 · el 409 se pinta en línea dentro del diálogo; «Confirmar el tope» reenvía con la confirmación y el mismo motivo", async () => {
    const rechazo = errorTopeSuperior("MUROS", "30000.0000", "50000.0000");
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], {
      filas: controlConMurosCapturado(),
      rechazar: exigirConfirmacionMuros(),
    });
    const dialogo = await abrirRecaptura(usuario);
    await escribirEnRecaptura(usuario, dialogo, "50000.00", MOTIVO_RECAPTURA);

    await pulsarRecapturar(usuario, dialogo);

    // El primer PUT salió sin confirmación; el rechazo es de negocio, no un error: va en línea, sin alerta roja.
    await waitFor(() => expect(dialogo.querySelector('[data-estado="bloqueado"]')).not.toBeNull());
    const enLinea = dialogo.querySelector<HTMLElement>('[data-estado="bloqueado"]');
    expect(enLinea).toHaveTextContent(rechazo.mensaje);
    expect(enLinea).toHaveTextContent("Venta $30,000.00");
    expect(enLinea).toHaveTextContent("Tope $50,000.00");
    expect(within(dialogo).queryByRole("alert")).not.toBeInTheDocument();
    expect(capturas).toHaveLength(1);
    expect(capturas[0]?.cuerpo).toEqual({
      importe_tope: "50000.00",
      motivo: MOTIVO_RECAPTURA,
      confirmar_superior_a_venta: false,
    });
    expect(filaTrasElDialogo("MUROS")).toHaveTextContent("$45,000.00");

    await usuario.click(within(dialogo).getByRole("button", { name: "Confirmar el tope" }));

    await waitFor(() => expect(capturas).toHaveLength(2));
    expect(capturas[1]?.tipoPartidaId).toBe(ID_DE.MUROS);
    expect(capturas[1]?.cuerpo).toEqual({
      importe_tope: "50000.00",
      motivo: MOTIVO_RECAPTURA,
      confirmar_superior_a_venta: true,
    });
    expect(capturas[1]?.csrf).toBe(tokenCsrf().token);

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => expect(filaDe("MUROS")).toHaveTextContent("$50,000.00"));
    expect(filaDe("MUROS").querySelector("time")).toHaveAttribute("datetime", CAPTURADO_EN);
    expect(capturas).toHaveLength(2);
  });
});

describe("TKT-018a · TC-34 · recaptura mal formada (CA-10)", () => {
  test.each([
    ["notación científica", "1e5"],
    ["importe negativo", "-1"],
  ])(
    "tkt018a_ca10 · recaptura mal formada · TC-34 · %s (%s): el mensaje junto a «Tope nuevo» con aria-invalid y cero PUT",
    async (_caso, entrada) => {
      const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], { filas: controlConMurosCapturado() });
      const dialogo = await abrirRecaptura(usuario);
      await escribirEnRecaptura(usuario, dialogo, entrada, MOTIVO_RECAPTURA);

      await pulsarRecapturar(usuario, dialogo);

      const campoTope = within(dialogo).getByRole("textbox", { name: "Tope nuevo" });
      await waitFor(() => expect(campoTope).toHaveAccessibleDescription(MENSAJE_IMPORTE_TOPE));
      expect(campoTope).toHaveAttribute("aria-invalid", "true");
      expect(campoTope).toHaveValue(entrada);
      // El motivo, bien escrito, no se marca; el diálogo sigue abierto y la fila no cambia.
      expect(within(dialogo).getByRole("textbox", { name: /^Motivo/ })).not.toHaveAttribute("aria-invalid", "true");
      expect(screen.getByRole("dialog", { name: TITULO_RECAPTURA })).toBeInTheDocument();
      expect(capturas).toHaveLength(0);
      expect(veces(`PUT ${RUTA_CONTROL}/${ID_DE.MUROS}`)).toBe(0);
      expect(filaTrasElDialogo("MUROS")).toHaveTextContent("$45,000.00");
    },
  );
});

// TKT-018a · entrega b · ciclo de corrección de la revisión (COD-1 a COD-5). Cada prueba nace del hallazgo que lleva en el nombre.
// Las respuestas se retienen con un doble de MSW cuya promesa controla la prueba: «en vuelo» se observa sin esperar por tiempo.

const TITULO_TOPE_MUROS = "Tope mayor que la venta · MUROS";
const TITULO_TOPE_GENERALES = "Tope mayor que la venta · GENERALES";
const MOTIVO_TOPE_MUROS = "Incluye andamiaje no presupuestado en muros";
const MOTIVO_TOPE_GENERALES = "Incluye la supervisión adicional que pidió el cliente";
const TITULO_RECAPTURA_ENCHAPES = "Recapturar tope · ENCHAPES";

function diferido<T>() {
  let resolver!: (valor: T) => void;
  const promesa = new Promise<T>((resolve) => {
    resolver = resolve;
  });
  return { promesa, resolver };
}

/** Dos 409 de tope superior en la misma captura: MUROS (venta 30,000, tope 35,000) y GENERALES (venta 7,400, tope 8,000). */
function exigirConfirmacionEnMurosYGenerales() {
  return (captura: Captura) => {
    if (confirmaba(captura)) return null;
    if (captura.tipoPartidaId === ID_DE.MUROS) {
      return HttpResponse.json(errorTopeSuperior("MUROS", "30000.0000", "35000.0000"), { status: 409 });
    }
    if (captura.tipoPartidaId === ID_DE.GENERALES) {
      return HttpResponse.json(errorTopeSuperior("GENERALES", "7400.0000", "8000.0000"), { status: 409 });
    }
    return null;
  };
}

/**
 * Retiene el `PUT` de `clave` hasta que la prueba lo suelte: `llego` se cumple cuando el servidor ya lo tiene en las manos (la
 * petición está en vuelo). Al soltarlo, lo atiende el doble de `abrirTabla`, que lo anota y lo guarda. Se registra después de
 * `abrirTabla`, así que manda sobre su manejador. `soloConfirmacion` retiene solo el que lleva `confirmar_superior_a_venta`.
 */
function retenerPut(clave: ClaveTipoPartida, soloConfirmacion: boolean) {
  const llegada = diferido<void>();
  const salida = diferido<void>();
  servidorPruebas.use(
    http.put(`${ORIGEN}/api/v1/lineas-base/:lineaBaseId/presupuesto-control/:tipoPartidaId`, async ({ request, params }) => {
      const cuerpo: unknown = await request.clone().json();
      if (params.tipoPartidaId !== ID_DE[clave] || !esCaptura(cuerpo)) return;
      if (soloConfirmacion && !cuerpo.confirmar_superior_a_venta) return;
      llegada.resolver();
      await salida.promesa;
    }),
  );
  return { llego: llegada.promesa, soltar: salida.resolver };
}

/** Escribe MUROS y GENERALES con tope mayor que su venta, guarda y devuelve el diálogo del primero de la cola (MUROS). */
async function abrirColaDeDos(usuario: Usuario): Promise<HTMLElement> {
  await escribirTope(usuario, "MUROS", "35000.00");
  await escribirTope(usuario, "GENERALES", "8000.00");
  await guardarTopes(usuario);
  return screen.findByRole("dialog", { name: TITULO_TOPE_MUROS });
}

async function confirmarConMotivo(usuario: Usuario, dialogo: HTMLElement, motivo: string) {
  await usuario.type(within(dialogo).getByRole("textbox", { name: "Motivo" }), motivo);
  await usuario.click(within(dialogo).getByRole("button", { name: "Confirmar con motivo" }));
}

/** El resumen leído del DOM sin filtrar por accesibilidad: con un diálogo abierto la tabla queda oculta a `getByRole`. */
function resumenTrasElDialogo(): HTMLElement {
  const resumen = document.querySelector<HTMLElement>('main [role="status"]');
  if (resumen === null) throw new Error("Falta el resumen del guardado.");
  return resumen;
}

function lineasDelResumen(resumen: HTMLElement): (string | null)[] {
  return [...resumen.querySelectorAll("p")].map((linea) => linea.textContent);
}

function clicEnElFondo(usuario: Usuario): Promise<void> {
  const fondo = document.querySelector<HTMLElement>('[data-slot="dialog-overlay"]');
  if (fondo === null) throw new Error("Falta el fondo del diálogo.");
  return usuario.click(fondo);
}

describe("TKT-018a · COD-2 · dos topes superiores a la venta en la cola de confirmación", () => {
  test("hdu001_esc17 · cola de dos 409 · COD-2 · confirmar el primero con motivo abre el segundo con su título y sus cifras; confirmar el segundo guarda ambos", async () => {
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], { rechazar: exigirConfirmacionEnMurosYGenerales() });

    const primero = await abrirColaDeDos(usuario);
    expect(primero).toHaveTextContent("Venta $30,000.00");
    expect(primero).toHaveTextContent("Tope $35,000.00");
    expect(capturas).toHaveLength(2);
    await confirmarConMotivo(usuario, primero, MOTIVO_TOPE_MUROS);

    const segundo = await screen.findByRole("dialog", { name: TITULO_TOPE_GENERALES });
    expect(screen.queryByRole("dialog", { name: TITULO_TOPE_MUROS })).not.toBeInTheDocument();
    expect(segundo).toHaveTextContent("Venta $7,400.00");
    expect(segundo).toHaveTextContent("Tope $8,000.00");
    // Cada confirmación empieza con el motivo vacío: el de MUROS no se hereda.
    expect(within(segundo).getByRole("textbox", { name: "Motivo" })).toHaveValue("");
    await confirmarConMotivo(usuario, segundo, MOTIVO_TOPE_GENERALES);

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await esperarResumen("Se guardaron: MUROS, GENERALES.");
    expect(within(principal()).getByRole("status")).not.toHaveTextContent("No se guardó");
    expect(capturas.map((captura) => captura.cuerpo)).toEqual([
      { importe_tope: "35000.00", confirmar_superior_a_venta: false },
      { importe_tope: "8000.00", confirmar_superior_a_venta: false },
      { importe_tope: "35000.00", motivo: MOTIVO_TOPE_MUROS, confirmar_superior_a_venta: true },
      { importe_tope: "8000.00", motivo: MOTIVO_TOPE_GENERALES, confirmar_superior_a_venta: true },
    ]);
    await waitFor(() => expect(filaDe("MUROS")).toHaveTextContent("$35,000.00"));
    await waitFor(() => expect(filaDe("GENERALES")).toHaveTextContent("$8,000.00"));
  });

  test("hdu001_esc17 · cola de dos 409 · COD-2 · «Corregir» el primero abre el segundo; el resumen dice «No se guardó: MUROS.» y lo guardado del segundo", async () => {
    const rechazoMuros = errorTopeSuperior("MUROS", "30000.0000", "35000.0000");
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], { rechazar: exigirConfirmacionEnMurosYGenerales() });

    const primero = await abrirColaDeDos(usuario);
    await usuario.click(within(primero).getByRole("button", { name: "Corregir" }));

    const segundo = await screen.findByRole("dialog", { name: TITULO_TOPE_GENERALES });
    expect(screen.queryByRole("dialog", { name: TITULO_TOPE_MUROS })).not.toBeInTheDocument();
    expect(segundo).toHaveTextContent("Venta $7,400.00");
    expect(segundo).toHaveTextContent("Tope $8,000.00");
    // Mientras se decide el segundo, ninguno de los dos está guardado.
    expect(lineasDelResumen(resumenTrasElDialogo())).toEqual(["No se guardó: MUROS, GENERALES."]);
    expect(capturas).toHaveLength(2);

    await confirmarConMotivo(usuario, segundo, MOTIVO_TOPE_GENERALES);

    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await esperarResumen("Se guardaron: GENERALES.");
    expect(lineasDelResumen(within(principal()).getByRole("status"))).toEqual(["Se guardaron: GENERALES.", "No se guardó: MUROS."]);
    expect(capturas).toHaveLength(3);
    expect(capturas[2]?.cuerpo).toEqual({ importe_tope: "8000.00", motivo: MOTIVO_TOPE_GENERALES, confirmar_superior_a_venta: true });
    // MUROS conserva lo escrito con el mensaje del servidor; GENERALES quedó guardado.
    expect(campoDe("MUROS")).toHaveValue("35000.00");
    expect(campoDe("MUROS")).toHaveAccessibleDescription(rechazoMuros.mensaje);
    expect(campoDe("MUROS")).toHaveAttribute("aria-invalid", "true");
    expect(within(filaDe("MUROS")).getByText("sin capturar")).toBeInTheDocument();
    await waitFor(() => expect(filaDe("GENERALES")).toHaveTextContent("$8,000.00"));
  });
});

describe("TKT-018a · COD-1 · la confirmación del tope superior con el PUT en vuelo", () => {
  test("hdu001_esc17 · PUT de confirmación en vuelo · COD-1 · «Corregir» y «Confirmar con motivo» quedan deshabilitados mientras la petición no responde", async () => {
    const { usuario } = await abrirTabla(["DIRECCION_GENERAL"], { rechazar: exigirConfirmacionEnMurosYGenerales() });
    const primero = await abrirColaDeDos(usuario);
    const retenido = retenerPut("MUROS", true);

    await confirmarConMotivo(usuario, primero, MOTIVO_TOPE_MUROS);
    await retenido.llego;

    expect(within(primero).getByRole("button", { name: "Corregir" })).toBeDisabled();
    expect(within(primero).getByRole("button", { name: "Confirmar con motivo" })).toBeDisabled();
    retenido.soltar();
    await screen.findByRole("dialog", { name: TITULO_TOPE_GENERALES });
  });

  // Con la salida abierta, el `alHecho` vivo de MUROS descartaba a ciegas lo siguiente de la cola (`slice(1)`): el segundo tope
  // nunca se preguntaba y el resumen lo daba por «No se guardó» sin que nadie lo hubiera decidido.
  test.each<[string, (usuario: Usuario, dialogo: HTMLElement) => Promise<void>]>([
    [
      "«Corregir»",
      async (usuario, dialogo) => {
        await usuario.click(within(dialogo).getByRole("button", { name: "Corregir" }));
      },
    ],
    [
      "Escape",
      async (usuario) => {
        await usuario.keyboard("{Escape}");
      },
    ],
    ["el clic fuera del diálogo", clicEnElFondo],
  ])(
    "hdu001_esc17 · PUT de confirmación en vuelo · COD-1 · intentar salir con %s no mueve la cola: al responder el PUT se pregunta el segundo tope y el resumen es coherente",
    async (_salida, intentarSalir) => {
      const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], { rechazar: exigirConfirmacionEnMurosYGenerales() });
      const primero = await abrirColaDeDos(usuario);
      const retenido = retenerPut("MUROS", true);
      await confirmarConMotivo(usuario, primero, MOTIVO_TOPE_MUROS);
      await retenido.llego;

      await intentarSalir(usuario, primero);

      // El diálogo de MUROS sigue ahí y el de GENERALES todavía no se ha pedido.
      expect(screen.getByRole("dialog", { name: TITULO_TOPE_MUROS })).toBeInTheDocument();
      expect(screen.queryByRole("dialog", { name: TITULO_TOPE_GENERALES })).not.toBeInTheDocument();
      expect(lineasDelResumen(resumenTrasElDialogo())).toEqual(["No se guardó: MUROS, GENERALES."]);

      retenido.soltar();

      const segundo = await screen.findByRole("dialog", { name: TITULO_TOPE_GENERALES });
      await waitFor(() =>
        expect(lineasDelResumen(resumenTrasElDialogo())).toEqual(["Se guardaron: MUROS.", "No se guardó: GENERALES."]),
      );
      // El segundo tope sigue en la cola: el `alHecho` de MUROS no lo descartó.
      expect(screen.getByRole("dialog", { name: TITULO_TOPE_GENERALES })).toBeInTheDocument();
      expect(screen.queryByRole("dialog", { name: TITULO_TOPE_MUROS })).not.toBeInTheDocument();
      expect(segundo).toHaveTextContent("Venta $7,400.00");
      expect(segundo).toHaveTextContent("Tope $8,000.00");

      await confirmarConMotivo(usuario, segundo, MOTIVO_TOPE_GENERALES);

      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
      await esperarResumen("Se guardaron: MUROS, GENERALES.");
      expect(within(principal()).getByRole("status")).not.toHaveTextContent("No se guardó");
      expect(capturas.map((captura) => captura.cuerpo)).toEqual([
        { importe_tope: "35000.00", confirmar_superior_a_venta: false },
        { importe_tope: "8000.00", confirmar_superior_a_venta: false },
        { importe_tope: "35000.00", motivo: MOTIVO_TOPE_MUROS, confirmar_superior_a_venta: true },
        { importe_tope: "8000.00", motivo: MOTIVO_TOPE_GENERALES, confirmar_superior_a_venta: true },
      ]);
    },
  );
});

function exigirConfirmacionMurosAlRecapturar() {
  return (captura: Captura) =>
    confirmaba(captura) ? null : HttpResponse.json(errorTopeSuperior("MUROS", "30000.0000", "50000.0000"), { status: 409 });
}

/** La recaptura de MUROS a «50000.00» con su motivo, ya rechazada con el 409 del tope superior. Lo usan COD-3 y F002. */
async function provocarElBloqueo() {
  const contexto = await abrirTabla(["DIRECCION_GENERAL"], {
    filas: controlConMurosCapturado(),
    rechazar: exigirConfirmacionMurosAlRecapturar(),
  });
  const dialogo = await abrirRecaptura(contexto.usuario);
  await escribirEnRecaptura(contexto.usuario, dialogo, "50000.00", MOTIVO_RECAPTURA);
  await pulsarRecapturar(contexto.usuario, dialogo);
  await waitFor(() => expect(dialogo.querySelector('[data-estado="bloqueado"]')).not.toBeNull());
  expect(contexto.capturas).toHaveLength(1);
  return { ...contexto, dialogo };
}

describe("TKT-018a · COD-3 · la confirmación del tope en la recaptura reenvía lo que provocó el 409", () => {
  /**
   * Lo que se confirma es lo que el servidor rechazó. Si tras editar el formulario el bloqueo desaparece, no hay confirmación
   * y nada con `confirmar_superior_a_venta: true` ha salido; si sigue, su botón reenvía el tope y el motivo del 409, no los actuales.
   */
  async function confirmarSiSigueElBloqueo(usuario: Usuario, dialogo: HTMLElement, capturas: Captura[]) {
    const confirmar = within(dialogo).queryByRole("button", { name: "Confirmar el tope" });
    if (confirmar !== null) {
      await usuario.click(confirmar);
      await waitFor(() => expect(capturas.filter(confirmaba)).toHaveLength(1));
    }
    expect(capturas.filter(confirmaba).map((captura) => captura.cuerpo)).toEqual(
      confirmar === null ? [] : [{ importe_tope: "50000.00", motivo: MOTIVO_RECAPTURA, confirmar_superior_a_venta: true }],
    );
  }

  test("hdu001_esc17 · recaptura superior a la venta · COD-3 · editar «Tope nuevo» tras el 409: la confirmación no lleva el importe nuevo, que el servidor no evaluó", async () => {
    const { usuario, capturas, dialogo } = await provocarElBloqueo();
    const campoTope = within(dialogo).getByRole("textbox", { name: "Tope nuevo" });

    await usuario.clear(campoTope);
    await usuario.type(campoTope, "60000.00");
    await confirmarSiSigueElBloqueo(usuario, dialogo, capturas);
  });

  test("hdu001_esc17 · recaptura superior a la venta · COD-3 · editar el motivo tras el 409: la confirmación no lleva el motivo nuevo, que no acompañó al 409", async () => {
    const { usuario, capturas, dialogo } = await provocarElBloqueo();
    const campoMotivo = within(dialogo).getByRole("textbox", { name: /^Motivo/ });

    await usuario.clear(campoMotivo);
    await usuario.type(campoMotivo, "Un motivo distinto del que provocó el bloqueo");
    await confirmarSiSigueElBloqueo(usuario, dialogo, capturas);
  });
});

describe("TKT-018a · COD-4 · la respuesta tardía de una recaptura cancelada", () => {
  test("hdu001_esc22 · cancelar con el PUT en vuelo · COD-4 · abrir «Recapturar» en otra fila y recibir entonces la respuesta no cierra el diálogo nuevo", async () => {
    const filas = [
      filaControl("MUROS", { importe_tope: "45000.0000", capturado_por: M_TORRES, capturado_en: FECHA_PREVIA }),
      filaControl("PLAFONES_Y_CAJILLOS"),
      filaControl("ENCHAPES", { importe_tope: "6000.0000", capturado_por: M_TORRES, capturado_en: FECHA_PREVIA }),
      filaControl("GENERALES"),
    ];
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], { filas });
    const retenido = retenerPut("MUROS", false);
    const dialogoMuros = await abrirRecaptura(usuario);
    await escribirEnRecaptura(usuario, dialogoMuros, "50000.00", MOTIVO_RECAPTURA);
    await pulsarRecapturar(usuario, dialogoMuros);
    await retenido.llego;

    await usuario.click(within(dialogoMuros).getByRole("button", { name: "Cancelar" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await usuario.click(within(filaDe("ENCHAPES")).getByRole("button", { name: "Recapturar ENCHAPES" }));
    const dialogoEnchapes = await screen.findByRole("dialog", { name: TITULO_RECAPTURA_ENCHAPES });
    await usuario.type(within(dialogoEnchapes).getByRole("textbox", { name: "Tope nuevo" }), "7000.00");

    retenido.soltar();

    // La recaptura de MUROS terminó y la tabla lo refleja; el diálogo de ENCHAPES, que es de otra fila, sigue como se dejó.
    await waitFor(() => expect(capturas).toHaveLength(1));
    await waitFor(() => expect(filaTrasElDialogo("MUROS")).toHaveTextContent("$50,000.00"));
    const vigente = screen.getByRole("dialog", { name: TITULO_RECAPTURA_ENCHAPES });
    expect(within(vigente).getByRole("textbox", { name: "Tope nuevo" })).toHaveValue("7000.00");
    expect(capturas[0]?.tipoPartidaId).toBe(ID_DE.MUROS);
  });
});

// TKT-018a · entrega b · ciclo 2 de corrección · F002 (auditor-codigo). Las acciones de `ConflictoEnLinea` («Confirmar el tope»,
// «Reintentar») llaman a `enviar()` sin pasar por `handleSubmit`, así que `isSubmitting` no se activa mientras su PUT está en
// vuelo: «Recapturar» sigue habilitado y un submit con otro tope lanza un segundo PUT concurrente (dos escrituras auditadas).
// Cada caso retiene el PUT de la acción con `retenerPut`; la ausencia del segundo PUT se comprueba al final, cuando el PUT
// retenido ya respondió: el intruso, de existir, salió justo después del submit y a esas alturas ya está contado.
interface CasoAccionEnVuelo {
  accion: string;
  etiqueta: string;
  /** El rechazo que deja la acción a la vista; el `intento` 1 es el PUT del botón «Recapturar». */
  rechazar: (captura: Captura, intento: number) => Response | null;
  /** Solo el PUT de la confirmación lleva `confirmar_superior_a_venta: true`; el reintento reenvía el mismo cuerpo. */
  soloConfirmacion: boolean;
  reenviado: Esquemas["CapturaPresupuestoControl"];
}

const CASOS_ACCION_EN_VUELO: CasoAccionEnVuelo[] = [
  {
    accion: "CONFIRMAR_TOPE_SUPERIOR",
    etiqueta: "Confirmar el tope",
    rechazar: (captura) =>
      confirmaba(captura) ? null : HttpResponse.json(errorTopeSuperior("MUROS", "30000.0000", "50000.0000"), { status: 409 }),
    soloConfirmacion: true,
    reenviado: { importe_tope: "50000.00", motivo: MOTIVO_RECAPTURA, confirmar_superior_a_venta: true },
  },
  {
    accion: "REINTENTAR",
    etiqueta: "Reintentar",
    rechazar: (_captura, intento) => (intento === 1 ? HttpResponse.json(errorConcurrencia(), { status: 409 }) : null),
    soloConfirmacion: false,
    reenviado: { importe_tope: "50000.00", motivo: MOTIVO_RECAPTURA, confirmar_superior_a_venta: false },
  },
];

describe("TKT-018a · F002 · la acción del bloqueo en línea con su PUT en vuelo", () => {
  /** La recaptura de MUROS a «50000.00» rechazada, la acción pulsada y su PUT ya en manos del servidor (retenido). */
  async function accionEnVuelo(caso: CasoAccionEnVuelo) {
    const contexto = await abrirTabla(["DIRECCION_GENERAL"], { filas: controlConMurosCapturado(), rechazar: caso.rechazar });
    const dialogo = await abrirRecaptura(contexto.usuario);
    await escribirEnRecaptura(contexto.usuario, dialogo, "50000.00", MOTIVO_RECAPTURA);
    await pulsarRecapturar(contexto.usuario, dialogo);
    await waitFor(() => expect(dialogo.querySelector('[data-estado="bloqueado"]')).not.toBeNull());
    expect(contexto.capturas).toHaveLength(1);

    const retenido = retenerPut("MUROS", caso.soloConfirmacion);
    await contexto.usuario.click(within(dialogo).getByRole("button", { name: caso.etiqueta }));
    await retenido.llego;
    return { ...contexto, dialogo, retenido };
  }

  test.each(CASOS_ACCION_EN_VUELO)(
    "hdu001_esc17 · acción en vuelo · F002 · con $accion en vuelo «Recapturar» queda deshabilitado hasta que responde la petición",
    async (caso) => {
      const { dialogo, retenido } = await accionEnVuelo(caso);
      try {
        expect(within(dialogo).getByRole("button", { name: "Recapturar" })).toBeDisabled();
      } finally {
        retenido.soltar();
      }
      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    },
  );

  test.each(CASOS_ACCION_EN_VUELO)(
    "hdu001_esc17 · acción en vuelo · F002 · con $accion en vuelo un submit forzado con otro tope no lanza un segundo PUT; al responder sale uno solo con el tope y el motivo del rechazo y el diálogo se cierra",
    async (caso) => {
      const { usuario, dialogo, capturas, retenido } = await accionEnVuelo(caso);
      const campoTope = within(dialogo).getByRole("textbox", { name: "Tope nuevo" });
      const formulario = dialogo.querySelector("form");
      if (formulario === null) throw new Error("Falta el formulario de la recaptura.");

      // Otro importe válido y un submit que el botón deshabilitado no deja pulsar: se fuerza sobre el formulario.
      await usuario.clear(campoTope);
      await usuario.type(campoTope, "60000.00");
      fireEvent.submit(formulario);

      retenido.soltar();

      await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
      await waitFor(() => expect(filaDe("MUROS")).toHaveTextContent("$50,000.00"));
      expect(veces(`PUT ${RUTA_CONTROL}/${ID_DE.MUROS}`)).toBe(2);
      expect(capturas).toHaveLength(2);
      expect(capturas[1]?.tipoPartidaId).toBe(ID_DE.MUROS);
      expect(capturas[1]?.cuerpo).toEqual(caso.reenviado);
      expect(capturas.filter((captura) => esCaptura(captura.cuerpo) && captura.cuerpo.importe_tope === "60000.00")).toEqual([]);
    },
  );

  // Cobertura que faltaba, no una regresión: el candado `enviando` se suelta en el `finally` de `enviar()`. Las pruebas de
  // arriba solo ven el candado cerrado y luego un diálogo que se cierra, así que ninguna notaba que no se abriera de nuevo
  // cuando el rechazo deja el diálogo abierto. Nace en verde porque el código ya lo hace bien; la prueba del mutante lo demuestra.
  test("hdu001_esc17 · recaptura superior a la venta · F002 · tras el 409 que deja el diálogo abierto, «Recapturar» vuelve a estar habilitado y un segundo envío sale como PUT", async () => {
    const { usuario, dialogo, capturas } = await provocarElBloqueo();

    expect(within(dialogo).getByRole("button", { name: "Recapturar" })).toBeEnabled();
    const campoTope = within(dialogo).getByRole("textbox", { name: "Tope nuevo" });
    await usuario.clear(campoTope);
    await usuario.type(campoTope, "60000.00");
    await pulsarRecapturar(usuario, dialogo);

    await waitFor(() => expect(veces(`PUT ${RUTA_CONTROL}/${ID_DE.MUROS}`)).toBe(2));
    expect(capturas).toHaveLength(2);
    expect(capturas[1]?.cuerpo).toEqual({ importe_tope: "60000.00", motivo: MOTIVO_RECAPTURA, confirmar_superior_a_venta: false });
    expect(screen.getByRole("dialog", { name: TITULO_RECAPTURA })).toBeInTheDocument();
  });

  // El servidor también puede responder VALIDACION en la recaptura (motivo con caracteres no válidos): el diálogo sigue abierto
  // por la misma razón y el candado debe soltarse igual.
  test("hdu001_esc23 · recaptura sin motivo · F002 · tras el 422 que deja el diálogo abierto, «Recapturar» vuelve a estar habilitado y un segundo envío sale como PUT", async () => {
    const rechazo = errorValidacion([{ campo: "motivo", codigo: "FORMATO", mensaje: MENSAJE_422_MOTIVO }]);
    const { usuario, capturas } = await abrirTabla(["DIRECCION_GENERAL"], {
      filas: controlConMurosCapturado(),
      rechazar: () => HttpResponse.json(rechazo, { status: 422 }),
    });
    const dialogo = await abrirRecaptura(usuario);
    await escribirEnRecaptura(usuario, dialogo, "50000.00", MOTIVO_RECAPTURA);
    await pulsarRecapturar(usuario, dialogo);
    const campoMotivo = within(dialogo).getByRole("textbox", { name: /^Motivo/ });
    await waitFor(() => expect(campoMotivo).toHaveAccessibleDescription(MENSAJE_422_MOTIVO));
    expect(capturas).toHaveLength(1);

    expect(within(dialogo).getByRole("button", { name: "Recapturar" })).toBeEnabled();
    const campoTope = within(dialogo).getByRole("textbox", { name: "Tope nuevo" });
    await usuario.clear(campoTope);
    await usuario.type(campoTope, "60000.00");
    await pulsarRecapturar(usuario, dialogo);

    await waitFor(() => expect(veces(`PUT ${RUTA_CONTROL}/${ID_DE.MUROS}`)).toBe(2));
    expect(capturas).toHaveLength(2);
    expect(capturas[1]?.cuerpo).toEqual({ importe_tope: "60000.00", motivo: MOTIVO_RECAPTURA, confirmar_superior_a_venta: false });
    expect(screen.getByRole("dialog", { name: TITULO_RECAPTURA })).toBeInTheDocument();
  });
});

describe("TKT-018a · COD-5 · un refetch fallido con datos ya cargados", () => {
  test("tkt018a_ca11 · refetch fallido · COD-5 · si recargar el control responde 500 tras guardar, la tabla y el resumen «Se guardaron» siguen a la vista", async () => {
    let caido = false;
    const { usuario, pedidas, queryClient } = await abrirTabla(["DIRECCION_GENERAL"], {
      responderControl: () =>
        caido
          ? HttpResponse.json({ mensaje: "Error interno del servidor.", correlacion_id: CORRELACION_500 }, { status: 500 })
          : HttpResponse.json(controlSinTopes()),
    });
    await escribirTope(usuario, "MUROS", "45000.00");
    caido = true;

    await guardarTopes(usuario);

    // Se espera por el estado de la consulta, no por un tiempo: el refetch ya falló y la pantalla ya pudo reaccionar.
    await waitFor(() => expect(queryClient.getQueryState(clavesLineaBase.control(ID_LINEA_BASE))?.status).toBe("error"));
    expect(pedidas.control).toBe(2);
    expect(within(principal()).getByRole("status")).toHaveTextContent("Se guardaron: MUROS.");
    expect(within(principal()).getByRole("heading", { level: 2, name: "Presupuesto de control" })).toBeInTheDocument();
    expect(filaDe("MUROS")).toBeInTheDocument();
    expect(campoDe("ENCHAPES")).toBeInTheDocument();
    expect(within(principal()).getByRole("button", { name: "Guardar topes" })).toBeInTheDocument();
  });
});
