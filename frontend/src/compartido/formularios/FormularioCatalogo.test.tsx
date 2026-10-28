import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, test, vi } from "vitest";
import { z } from "zod";
import type { ResultadoApi } from "@/api/cliente";
import type { Accion, ErrorApi, ErrorBloqueo, ErrorConcurrencia, ErrorGenerico } from "@/api/errores";
import {
  errorConcurrencia,
  errorConflictoEstado,
  errorRn03ExcedeImporte,
  errorValidacion,
} from "@/pruebas/cuerpos";
import {
  type BajaCatalogo,
  type CampoCatalogo,
  FormularioCatalogo,
  type PropsFormularioCatalogo,
} from "./FormularioCatalogo";

// El arnés del plan (TC-82 a TC-89): un botón «+» abre el formulario con dos campos y este esquema.
const esquema = z.object({
  codigo: z.string().min(1, "El código es obligatorio."),
  nombre: z.string().min(1, "El nombre es obligatorio."),
});

const CAMPOS: ReadonlyArray<CampoCatalogo<"codigo" | "nombre">> = [
  { nombre: "codigo", etiqueta: "Código" },
  { nombre: "nombre", etiqueta: "Nombre" },
];

/** La respuesta del alta: el componente es genérico en `R`, así que la prueba fija la suya. */
interface RespuestaAlta {
  id: string;
  codigo: string;
  nombre: string;
}

type Props = PropsFormularioCatalogo<typeof esquema, RespuestaAlta>;

const CODIGO = "AP-058-25";
const NOMBRE = "Union Square F2";
const CORRELACION_ID = "7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e";
const PREGUNTA = "¿Dar de baja este proveedor?";
const ETIQUETA_BAJA = "Dar de baja";
const CONFIRMAR_BAJA = "Confirmar baja";

/** Una promesa cuyo desenlace decide la prueba: así «en vuelo» se observa sin esperar por tiempo. */
function diferido<T>() {
  let resolver!: (valor: T) => void;
  const promesa = new Promise<T>((resolve) => {
    resolver = resolve;
  });
  return { promesa, resolver };
}

const ok = <T,>(datos: T): ResultadoApi<T> => ({ ok: true, datos });
const rechazo = (error: ErrorApi): ResultadoApi<never> => ({ ok: false, error });

function errorGenerico(mensaje: string | null): ErrorGenerico {
  return { tipo: "GENERICO", estado: 500, mensaje, correlacion_id: CORRELACION_ID };
}

interface OpcionesArnes {
  alGuardar?: Props["alGuardar"];
  baja?: BajaCatalogo;
  valoresIniciales?: Props["valoresIniciales"];
}

/** El arnés: «+» abre el formulario; `alCerrar` de la pantalla lo cierra. Las salidas son espías. */
function abrir({ alGuardar = vi.fn<Props["alGuardar"]>(), baja, valoresIniciales = { codigo: "", nombre: "" } }: OpcionesArnes = {}) {
  const alGuardado = vi.fn<Props["alGuardado"]>();
  const alBloqueo = vi.fn<(error: ErrorBloqueo) => void>();
  const alAccion = vi.fn<Props["alAccion"]>();
  const alCerrar = vi.fn<Props["alCerrar"]>();

  function Arnes() {
    const [abierto, setAbierto] = useState(false);
    return (
      <>
        <button type="button" onClick={() => setAbierto(true)}>
          +
        </button>
        <FormularioCatalogo<typeof esquema, RespuestaAlta>
          abierto={abierto}
          titulo="Nueva obra"
          esquema={esquema}
          campos={CAMPOS}
          valoresIniciales={valoresIniciales}
          alGuardar={alGuardar}
          alGuardado={alGuardado}
          alBloqueo={alBloqueo}
          alAccion={alAccion}
          alCerrar={() => {
            alCerrar();
            setAbierto(false);
          }}
          baja={baja}
        />
      </>
    );
  }

  render(<Arnes />);
  const usuario = userEvent.setup();
  return { alGuardar, alGuardado, alBloqueo, alAccion, alCerrar, usuario };
}

type Usuario = ReturnType<typeof userEvent.setup>;

async function abrirFormulario(usuario: Usuario) {
  await usuario.click(screen.getByRole("button", { name: "+" }));
  await screen.findByRole("textbox", { name: "Código" });
}

const campoCodigo = () => screen.getByRole("textbox", { name: "Código" });
const campoNombre = () => screen.getByRole("textbox", { name: "Nombre" });
const botonGuardar = () => screen.getByRole("button", { name: "Guardar" });

async function escribirYGuardar(usuario: Usuario, codigo = CODIGO, nombre = NOMBRE) {
  await usuario.type(campoCodigo(), codigo);
  await usuario.type(campoNombre(), nombre);
  await usuario.click(botonGuardar());
}

/** El diálogo (el más interior) que contiene el texto: acota las consultas sin atarlas a la estructura. */
function dialogoCon(texto: string | RegExp): HTMLElement {
  const encontrados = screen
    .getAllByRole("dialog")
    .filter((dialogo) => within(dialogo).queryByText(texto) !== null);
  const dialogo = encontrados.at(-1);
  if (dialogo === undefined) throw new Error(`Ningún diálogo contiene ${String(texto)}`);
  return dialogo;
}

const accionVerObra = {
  clave: "VER_OBRA",
  metodo: "GET",
  ruta: "/api/v1/obras/7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e",
} satisfies Accion;

const accionDesactivar = {
  clave: "DESACTIVAR_PROVEEDOR",
  metodo: "POST",
  ruta: "/api/v1/proveedores/2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e/desactivacion",
} satisfies Accion;

const accionVerOrdenes = {
  clave: "VER_ORDENES_ABIERTAS",
  metodo: "GET",
  ruta: "/api/v1/ordenes-compra?proveedor_id=2b3c4d5e-6f7a-4b8c-9d0e-1f2a3b4c5d6e",
} satisfies Accion;

function bajaDe(alConfirmar: BajaCatalogo["alConfirmar"], exigeMotivo = false): BajaCatalogo & { alHecha: ReturnType<typeof vi.fn<BajaCatalogo["alHecha"]>> } {
  return {
    etiqueta: ETIQUETA_BAJA,
    pregunta: PREGUNTA,
    exigeMotivo,
    alConfirmar,
    alHecha: vi.fn<BajaCatalogo["alHecha"]>(),
  };
}

describe("TKT-008 · formulario de catálogo", () => {
  test("tkt008_ca11_esc01 · foco en el primer campo (TC-82)", async () => {
    const { usuario } = abrir();

    await abrirFormulario(usuario);

    // Quien abre el formulario escribe sin tocar el ratón.
    await waitFor(() => expect(campoCodigo()).toHaveFocus());
    expect(campoNombre()).not.toHaveFocus();
  });

  test("tkt008_ca11_esc02 · guardar (TC-83)", async () => {
    const respuesta = diferido<ResultadoApi<RespuestaAlta>>();
    const alGuardar = vi.fn<Props["alGuardar"]>(() => respuesta.promesa);
    const { alGuardado, alBloqueo, alCerrar, usuario } = abrir({ alGuardar });
    await abrirFormulario(usuario);

    await escribirYGuardar(usuario);

    // Una sola petición, con lo escrito, y el botón no admite un segundo envío mientras está en vuelo.
    await waitFor(() => expect(alGuardar).toHaveBeenCalledTimes(1));
    expect(alGuardar).toHaveBeenCalledWith({ codigo: CODIGO, nombre: NOMBRE });
    expect(botonGuardar()).toBeDisabled();
    expect(alGuardado).not.toHaveBeenCalled();
    expect(alCerrar).not.toHaveBeenCalled();

    const creada: RespuestaAlta = { id: "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d", codigo: CODIGO, nombre: NOMBRE };
    respuesta.resolver(ok(creada));

    await waitFor(() => expect(alGuardado).toHaveBeenCalledTimes(1));
    expect(alGuardado).toHaveBeenCalledWith(creada);
    expect(alCerrar).toHaveBeenCalledTimes(1);
    expect(alBloqueo).not.toHaveBeenCalled();
  });

  test("tkt008_ca11_esc03 · forma inválida (TC-84)", async () => {
    const { alGuardar, alGuardado, alCerrar, usuario } = abrir();
    await abrirFormulario(usuario);

    await usuario.type(campoCodigo(), CODIGO);
    await usuario.click(botonGuardar());

    // Zod lo marca junto al campo, el foco va al campo con error y no sale ninguna petición.
    expect(await screen.findByText("El nombre es obligatorio.")).toBeInTheDocument();
    expect(campoNombre()).toHaveAttribute("aria-invalid", "true");
    expect(campoNombre()).toHaveAccessibleDescription("El nombre es obligatorio.");
    await waitFor(() => expect(campoNombre()).toHaveFocus());
    expect(campoCodigo()).not.toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByText("El código es obligatorio.")).not.toBeInTheDocument();
    expect(campoCodigo()).toHaveValue(CODIGO);
    expect(alGuardar).not.toHaveBeenCalled();
    expect(alGuardado).not.toHaveBeenCalled();
    expect(alCerrar).not.toHaveBeenCalled();
  });

  test("tkt008_ca11_esc04 · el servidor responde 422 (TC-85)", async () => {
    const mensajeCodigo = "El código ya tiene un formato distinto.";
    const mensajeNombre = "El nombre excede la longitud permitida.";
    const mensajeRfc = "El RFC no es válido.";
    const alGuardar = vi.fn<Props["alGuardar"]>(async () =>
      rechazo(
        errorValidacion([
          { campo: "codigo", codigo: "VALOR_NO_PERMITIDO", mensaje: mensajeCodigo },
          { campo: "nombre", codigo: "VALOR_NO_PERMITIDO", mensaje: mensajeNombre },
          { campo: "rfc", codigo: "VALOR_NO_PERMITIDO", mensaje: mensajeRfc },
        ]),
      ),
    );
    const { alGuardado, alBloqueo, alCerrar, usuario } = abrir({ alGuardar });
    await abrirFormulario(usuario);

    await escribirYGuardar(usuario);

    // Cada mensaje del servidor, tal cual, junto a su campo.
    expect(await screen.findByText(mensajeCodigo)).toBeInTheDocument();
    expect(campoCodigo()).toHaveAttribute("aria-invalid", "true");
    expect(campoCodigo()).toHaveAccessibleDescription(mensajeCodigo);
    expect(campoNombre()).toHaveAttribute("aria-invalid", "true");
    expect(campoNombre()).toHaveAccessibleDescription(mensajeNombre);
    // El campo que el formulario no tiene va a la cabecera, y solo él.
    const alerta = screen.getByRole("alert");
    expect(alerta).toHaveTextContent(mensajeRfc);
    expect(alerta).not.toHaveTextContent(mensajeCodigo);
    expect(alerta).not.toHaveTextContent(mensajeNombre);
    // Lo escrito se conserva y nada se entrega ni se delega.
    expect(campoCodigo()).toHaveValue(CODIGO);
    expect(campoNombre()).toHaveValue(NOMBRE);
    expect(alGuardado).not.toHaveBeenCalled();
    expect(alBloqueo).not.toHaveBeenCalled();
    expect(alCerrar).not.toHaveBeenCalled();
  });

  test("tkt008_ca11_esc05 · duplicado en línea (TC-86)", async () => {
    const duplicado = errorConflictoEstado("CODIGO_OBRA_DUPLICADO", {
      mensaje: `Ya existe una obra con el código ${CODIGO}.`,
      detalle: { codigo: CODIGO, nombre: NOMBRE },
      acciones: [accionVerObra],
    });
    const alGuardar = vi.fn<Props["alGuardar"]>(async () => rechazo(duplicado));
    const { alGuardado, alBloqueo, alAccion, alCerrar, usuario } = abrir({ alGuardar });
    await abrirFormulario(usuario);

    await escribirYGuardar(usuario);

    // El conflicto se pinta en línea con su cabecera, su mensaje y el registro existente.
    expect(await screen.findByText("No se puede completar")).toBeInTheDocument();
    expect(screen.getByText("CODIGO_OBRA_DUPLICADO")).toBeInTheDocument();
    expect(screen.getByText(duplicado.mensaje)).toBeInTheDocument();
    expect(screen.getByText(CODIGO)).toBeInTheDocument();
    expect(screen.getByText(NOMBRE)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "VER_OBRA" })).toBeInTheDocument();
    // No es un error de forma ni se delega a la pantalla de bloqueo.
    expect(alBloqueo).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(alGuardado).not.toHaveBeenCalled();
    expect(alCerrar).not.toHaveBeenCalled();
    // Los datos capturados se conservan.
    expect(campoCodigo()).toHaveValue(CODIGO);
    expect(campoNombre()).toHaveValue(NOMBRE);

    // La acción se entrega tal como llegó, sin invocarla.
    await usuario.click(screen.getByRole("button", { name: "VER_OBRA" }));
    expect(alAccion).toHaveBeenCalledTimes(1);
    expect(alAccion).toHaveBeenCalledWith(accionVerObra);
  });

  test("tkt008_ca11 · una regla de negocio al guardar se delega a la pantalla (TC-87)", async () => {
    const error = errorRn03ExcedeImporte();
    const alGuardar = vi.fn<Props["alGuardar"]>(async () => rechazo(error));
    const { alGuardado, alBloqueo, alAccion, alCerrar, usuario } = abrir({ alGuardar });
    await abrirFormulario(usuario);

    await escribirYGuardar(usuario);

    // El error llega tal cual: es la pantalla quien lo pinta con la de bloqueo.
    await waitFor(() => expect(alBloqueo).toHaveBeenCalledTimes(1));
    expect(alBloqueo.mock.calls[0]?.[0]).toBe(error);
    // El formulario no añade mensaje propio ni conflicto en línea, y no se cierra ni entrega nada.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(error.mensaje)).not.toBeInTheDocument();
    expect(screen.queryByText("No se puede completar")).not.toBeInTheDocument();
    expect(alAccion).not.toHaveBeenCalled();
    expect(alGuardado).not.toHaveBeenCalled();
    expect(alCerrar).not.toHaveBeenCalled();
  });

  test("tkt008_ca11 · una concurrencia al guardar se delega a la pantalla (TC-87)", async () => {
    const error: ErrorConcurrencia = { ...errorConcurrencia(), reintentar_tras_s: 2 };
    const alGuardar = vi.fn<Props["alGuardar"]>(async () => rechazo(error));
    const { alGuardado, alBloqueo, alCerrar, usuario } = abrir({ alGuardar });
    await abrirFormulario(usuario);

    await escribirYGuardar(usuario);

    await waitFor(() => expect(alBloqueo).toHaveBeenCalledTimes(1));
    expect(alBloqueo.mock.calls[0]?.[0]).toBe(error);
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(error.mensaje)).not.toBeInTheDocument();
    expect(alGuardado).not.toHaveBeenCalled();
    expect(alCerrar).not.toHaveBeenCalled();
  });

  test.each([
    ["sin mensaje del servidor", null, "No se pudo guardar."],
    ["con mensaje del servidor", "Fallo interno al guardar la obra.", "Fallo interno al guardar la obra."],
  ])("tkt008_ca11 · cualquier otro error al guardar va a la cabecera, %s", async (_descripcion, mensaje, esperado) => {
    const alGuardar = vi.fn<Props["alGuardar"]>(async () => rechazo(errorGenerico(mensaje)));
    const { alGuardado, alBloqueo, alAccion, alCerrar, usuario } = abrir({ alGuardar });
    await abrirFormulario(usuario);

    await escribirYGuardar(usuario);

    // Qué falló y cómo citarlo: el mensaje (o el genérico) y la referencia, en la cabecera del formulario.
    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent(esperado);
    expect(alerta).toHaveTextContent(CORRELACION_ID);
    // Ningún campo se marca, no se delega, y lo escrito se conserva para reintentar.
    expect(campoCodigo()).not.toHaveAttribute("aria-invalid", "true");
    expect(campoNombre()).not.toHaveAttribute("aria-invalid", "true");
    expect(campoCodigo()).toHaveValue(CODIGO);
    expect(campoNombre()).toHaveValue(NOMBRE);
    expect(alBloqueo).not.toHaveBeenCalled();
    expect(alAccion).not.toHaveBeenCalled();
    expect(alGuardado).not.toHaveBeenCalled();
    expect(alCerrar).not.toHaveBeenCalled();
  });

  test("tkt008_ca11_esc06 · la baja pide confirmación y cancelar no envía nada (TC-88)", async () => {
    const alConfirmar = vi.fn<BajaCatalogo["alConfirmar"]>(async () => ok(null));
    const baja = bajaDe(alConfirmar);
    const { usuario } = abrir({ baja });
    await abrirFormulario(usuario);

    await usuario.click(screen.getByRole("button", { name: ETIQUETA_BAJA }));

    // La pregunta aparece antes de enviar nada, con sus dos únicas salidas.
    expect(await screen.findByText(PREGUNTA)).toBeInTheDocument();
    const pregunta = dialogoCon(PREGUNTA);
    expect(within(pregunta).getByRole("button", { name: "Cancelar" })).toBeInTheDocument();
    expect(within(pregunta).getByRole("button", { name: CONFIRMAR_BAJA })).toBeInTheDocument();
    expect(alConfirmar).not.toHaveBeenCalled();

    await usuario.click(within(pregunta).getByRole("button", { name: "Cancelar" }));

    await waitFor(() => expect(screen.queryByText(PREGUNTA)).not.toBeInTheDocument());
    expect(alConfirmar).not.toHaveBeenCalled();
    expect(baja.alHecha).not.toHaveBeenCalled();
  });

  test("tkt008_ca11_esc06 · confirmar la baja sin motivo envía null (TC-88)", async () => {
    const alConfirmar = vi.fn<BajaCatalogo["alConfirmar"]>(async () => ok(null));
    const baja = bajaDe(alConfirmar);
    const { usuario } = abrir({ baja });
    await abrirFormulario(usuario);

    await usuario.click(screen.getByRole("button", { name: ETIQUETA_BAJA }));
    await screen.findByText(PREGUNTA);
    await usuario.click(within(dialogoCon(PREGUNTA)).getByRole("button", { name: CONFIRMAR_BAJA }));

    await waitFor(() => expect(alConfirmar).toHaveBeenCalledTimes(1));
    expect(alConfirmar).toHaveBeenCalledWith(null);
    await waitFor(() => expect(baja.alHecha).toHaveBeenCalledTimes(1));
  });

  test("tkt008_ca11_esc06 · con exigeMotivo la baja abre el motivo y no envía nada (TC-88, PA-T12)", async () => {
    const alConfirmar = vi.fn<BajaCatalogo["alConfirmar"]>(async () => ok(null));
    const baja = bajaDe(alConfirmar, true);
    const { usuario } = abrir({ baja });
    await abrirFormulario(usuario);

    await usuario.click(screen.getByRole("button", { name: ETIQUETA_BAJA }));

    // Se abre la captura de motivo, no la pregunta simple; y todavía no salió nada.
    const campoMotivo = await screen.findByRole("textbox", { name: "Motivo" });
    expect(campoMotivo).toBeInTheDocument();
    expect(alConfirmar).not.toHaveBeenCalled();
    expect(baja.alHecha).not.toHaveBeenCalled();

    // Cancelar el motivo tampoco envía.
    const dialogoMotivo = screen
      .getAllByRole("dialog")
      .filter((dialogo) => within(dialogo).queryByRole("textbox", { name: "Motivo" }) !== null)
      .at(-1);
    expect(dialogoMotivo).toBeDefined();
    if (dialogoMotivo === undefined) return;
    await usuario.click(within(dialogoMotivo).getByRole("button", { name: "Cancelar" }));
    expect(alConfirmar).not.toHaveBeenCalled();
    expect(baja.alHecha).not.toHaveBeenCalled();
  });

  test("tkt008_ca11_esc07 · la baja la rechaza el servidor (TC-89)", async () => {
    const mensaje = "CoPanel tiene 2 órdenes pendientes de recibir; se puede desactivar para órdenes nuevas.";
    const rechazoBaja = errorConflictoEstado("PROVEEDOR_CON_ORDENES_ABIERTAS", {
      mensaje,
      detalle: { ordenes: [{ id: "5c4b3a29-1807-4f6e-9d5c-4b3a29180716", folio: "OC-AP05825-0017", estado: "PARCIAL" }] },
      acciones: [accionDesactivar, accionVerOrdenes],
    });
    const alConfirmar = vi.fn<BajaCatalogo["alConfirmar"]>(async () => rechazo(rechazoBaja));
    const baja = bajaDe(alConfirmar);
    const { alBloqueo, alAccion, alCerrar, usuario } = abrir({ baja });
    await abrirFormulario(usuario);

    await usuario.click(screen.getByRole("button", { name: ETIQUETA_BAJA }));
    await screen.findByText(PREGUNTA);
    await usuario.click(within(dialogoCon(PREGUNTA)).getByRole("button", { name: CONFIRMAR_BAJA }));

    // El rechazo se pinta en línea, con su código, su mensaje y el registro que lo causa.
    expect(await screen.findByText(mensaje)).toBeInTheDocument();
    expect(screen.getByText("No se puede completar")).toBeInTheDocument();
    expect(screen.getByText("PROVEEDOR_CON_ORDENES_ABIERTAS")).toBeInTheDocument();
    expect(screen.getByText(/OC-AP05825-0017/)).toBeInTheDocument();

    // Exactamente las dos acciones del servidor, contiguas y en su orden; ningún «Cerrar» las acompaña.
    // La X de cierre del diálogo (`data-slot="dialog-close"`, nombre «Cerrar») no es una acción del conflicto: se excluye.
    const nombres = within(dialogoCon(mensaje))
      .getAllByRole("button")
      .filter((boton) => boton.dataset.slot !== "dialog-close")
      .map((boton) => boton.textContent?.trim() ?? "");
    const primera = nombres.indexOf("DESACTIVAR_PROVEEDOR");
    expect(primera).toBeGreaterThanOrEqual(0);
    expect(nombres.slice(primera, primera + 2)).toEqual(["DESACTIVAR_PROVEEDOR", "VER_ORDENES_ABIERTAS"]);
    expect(nombres).not.toContain("Cerrar");
    expect(nombres.filter((nombre) => nombre === "DESACTIVAR_PROVEEDOR" || nombre === "VER_ORDENES_ABIERTAS")).toHaveLength(2);

    // El formulario no decide por su cuenta: no da la baja por hecha, no delega ni se cierra.
    expect(baja.alHecha).not.toHaveBeenCalled();
    expect(alBloqueo).not.toHaveBeenCalled();
    expect(alCerrar).not.toHaveBeenCalled();
    expect(alAccion).not.toHaveBeenCalled();

    // Elegir una alternativa la entrega tal como llegó.
    await usuario.click(screen.getByRole("button", { name: "DESACTIVAR_PROVEEDOR" }));
    expect(alAccion).toHaveBeenCalledTimes(1);
    expect(alAccion).toHaveBeenCalledWith(accionDesactivar);
  });

  test("tkt008_ca11_esc07 · cualquier otro error de la baja va a la cabecera (TC-89)", async () => {
    const mensaje = "Fallo interno al dar de baja.";
    const alConfirmar = vi.fn<BajaCatalogo["alConfirmar"]>(async () => rechazo(errorGenerico(mensaje)));
    const baja = bajaDe(alConfirmar);
    const { alBloqueo, alAccion, usuario } = abrir({ baja });
    await abrirFormulario(usuario);

    await usuario.click(screen.getByRole("button", { name: ETIQUETA_BAJA }));
    await screen.findByText(PREGUNTA);
    await usuario.click(within(dialogoCon(PREGUNTA)).getByRole("button", { name: CONFIRMAR_BAJA }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent(mensaje);
    expect(alerta).toHaveTextContent(CORRELACION_ID);
    expect(screen.queryByText("No se puede completar")).not.toBeInTheDocument();
    expect(baja.alHecha).not.toHaveBeenCalled();
    expect(alBloqueo).not.toHaveBeenCalled();
    expect(alAccion).not.toHaveBeenCalled();
  });

  test("tkt008_ca11_esc04 · una validación del servidor sin errores muestra un aviso en la cabecera", async () => {
    // Con `errores: []` no hay campo que marcar ni texto restante, y el guardado no puede fallar en silencio.
    const alGuardar = vi.fn<Props["alGuardar"]>(async () => rechazo(errorValidacion([])));
    const { alGuardado, alBloqueo, alCerrar, usuario } = abrir({ alGuardar });
    await abrirFormulario(usuario);

    await escribirYGuardar(usuario);

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent(/La petición no es válida\.|No se pudo guardar\./);
    // Ningún campo se marca, y lo escrito se conserva para reintentar.
    expect(campoCodigo()).not.toHaveAttribute("aria-invalid", "true");
    expect(campoNombre()).not.toHaveAttribute("aria-invalid", "true");
    expect(campoCodigo()).toHaveValue(CODIGO);
    expect(campoNombre()).toHaveValue(NOMBRE);
    expect(alGuardado).not.toHaveBeenCalled();
    expect(alBloqueo).not.toHaveBeenCalled();
    expect(alCerrar).not.toHaveBeenCalled();
  });

  test("tkt008_ca11_esc04 · tras el 422 del servidor el foco va al campo señalado", async () => {
    // El error del servidor marca el campo y el foco no se queda en «Guardar».
    const mensajeNombre = "El nombre excede la longitud permitida.";
    const alGuardar = vi.fn<Props["alGuardar"]>(async () =>
      rechazo(errorValidacion([{ campo: "nombre", codigo: "VALOR_NO_PERMITIDO", mensaje: mensajeNombre }])),
    );
    const { usuario } = abrir({ alGuardar });
    await abrirFormulario(usuario);

    await escribirYGuardar(usuario);

    await screen.findByText(mensajeNombre);
    await waitFor(() => expect(campoNombre()).toHaveFocus());
  });

  test("tkt008_ca11_esc04 · con varios errores del servidor el foco va al primer campo señalado", async () => {
    // Enfocar cada campo dentro del bucle dejaría el foco en el último; debe quedar en el primero.
    const mensajeCodigo = "El código ya tiene un formato distinto.";
    const mensajeNombre = "El nombre excede la longitud permitida.";
    const alGuardar = vi.fn<Props["alGuardar"]>(async () =>
      rechazo(
        errorValidacion([
          { campo: "codigo", codigo: "VALOR_NO_PERMITIDO", mensaje: mensajeCodigo },
          { campo: "nombre", codigo: "VALOR_NO_PERMITIDO", mensaje: mensajeNombre },
        ]),
      ),
    );
    const { usuario } = abrir({ alGuardar });
    await abrirFormulario(usuario);

    await escribirYGuardar(usuario);

    // Los dos campos quedan marcados con su mensaje, y el foco va al primero, no al último.
    await screen.findByText(mensajeCodigo);
    expect(await screen.findByText(mensajeNombre)).toBeInTheDocument();
    await waitFor(() => expect(campoCodigo()).toHaveFocus());
    expect(campoNombre()).not.toHaveFocus();
  });

  test("tkt008_ca11_esc05 · el conflicto en línea se anuncia en una región viva que ya existía", async () => {
    // Un lector de pantalla solo anuncia lo que aparece dentro de una región viva ya presente al guardar.
    const duplicado = errorConflictoEstado("CODIGO_OBRA_DUPLICADO", { mensaje: `Ya existe una obra con el código ${CODIGO}.` });
    const alGuardar = vi.fn<Props["alGuardar"]>(async () => rechazo(duplicado));
    const { usuario } = abrir({ alGuardar });
    await abrirFormulario(usuario);
    const regionesAntes = screen.getByRole("dialog").querySelectorAll('[aria-live="polite"]');
    expect(regionesAntes.length).toBeGreaterThan(0);

    await escribirYGuardar(usuario);

    const conflicto = await screen.findByRole("region");
    expect(conflicto).toHaveTextContent("No se puede completar");
    const region = conflicto.closest('[aria-live="polite"]');
    expect(region).not.toBeNull();
    expect(region).toBeInTheDocument();
    expect(Array.from(regionesAntes)).toContain(region);
  });

  test("tkt008_ca11 · la X de cierre se llama «Cerrar», no «Close»", async () => {
    const { usuario } = abrir();
    await abrirFormulario(usuario);

    const cerrar = screen.getByRole("button", { name: "Cerrar" });

    expect(cerrar).toHaveAttribute("data-slot", "dialog-close");
    expect(screen.queryByRole("button", { name: "Close" })).not.toBeInTheDocument();
  });

  test("tkt008_ca11 · reabrir el formulario muestra los valores iniciales, no lo editado", async () => {
    const { usuario } = abrir({ valoresIniciales: { codigo: "AP-001-26", nombre: "Obra original" } });
    await abrirFormulario(usuario);
    await usuario.clear(campoNombre());
    await usuario.type(campoNombre(), "Obra editada");
    expect(campoNombre()).toHaveValue("Obra editada");

    await usuario.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("textbox", { name: "Código" })).not.toBeInTheDocument());
    await abrirFormulario(usuario);

    expect(campoCodigo()).toHaveValue("AP-001-26");
    expect(campoNombre()).toHaveValue("Obra original");
  });

  test("tkt008_ca11_esc06 · Escape en la confirmación anidada no cierra el formulario padre", async () => {
    const alConfirmar = vi.fn<BajaCatalogo["alConfirmar"]>(async () => ok(null));
    const { alCerrar, usuario } = abrir({ baja: bajaDe(alConfirmar) });
    await abrirFormulario(usuario);
    await usuario.type(campoCodigo(), CODIGO);
    await usuario.click(screen.getByRole("button", { name: ETIQUETA_BAJA }));
    await screen.findByText(PREGUNTA);

    await usuario.keyboard("{Escape}");

    await waitFor(() => expect(screen.queryByText(PREGUNTA)).not.toBeInTheDocument());
    // Solo se cerró la pregunta: el formulario sigue abierto con lo escrito, y la baja no se envió.
    expect(campoCodigo()).toHaveValue(CODIGO);
    expect(alCerrar).not.toHaveBeenCalled();
    expect(alConfirmar).not.toHaveBeenCalled();
  });
});
