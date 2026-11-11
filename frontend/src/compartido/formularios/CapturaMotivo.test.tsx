import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import type { ResultadoApi } from "@/api/cliente";
import type { ErrorApi } from "@/api/errores";
import { errorRn03ExcedeImporte, errorValidacion } from "@/pruebas/cuerpos";
import { CapturaMotivo, type PropsCapturaMotivo } from "./CapturaMotivo";

const MENSAJE_OBLIGATORIO = "El motivo es obligatorio.";
const MENSAJE_DEL_SERVIDOR = "El motivo no puede repetir el anterior.";
const CONFIRMAR = "Confirmar baja";

/** Una promesa cuyo desenlace decide la prueba: así «en vuelo» se observa sin esperar por tiempo. */
function diferido<T>() {
  let resolver!: (valor: T) => void;
  const promesa = new Promise<T>((resolve) => {
    resolver = resolve;
  });
  return { promesa, resolver };
}

/** La captura abierta, con sus cuatro salidas espiadas. `alConfirmar` lo pone cada prueba: es lo que simula al servidor. */
function abrir(alConfirmar: PropsCapturaMotivo["alConfirmar"]) {
  const alHecho = vi.fn<PropsCapturaMotivo["alHecho"]>();
  const alRechazo = vi.fn<(error: ErrorApi) => void>();
  const alCancelar = vi.fn<PropsCapturaMotivo["alCancelar"]>();
  render(
    <CapturaMotivo
      abierta
      titulo="Dar de baja al proveedor"
      etiquetaConfirmar={CONFIRMAR}
      alConfirmar={alConfirmar}
      alHecho={alHecho}
      alRechazo={alRechazo}
      alCancelar={alCancelar}
    />,
  );
  const usuario = userEvent.setup();
  return { alHecho, alRechazo, alCancelar, usuario };
}

function campoMotivo(): HTMLElement {
  return screen.getByRole("textbox", { name: "Motivo" });
}

const rechazo = (error: ErrorApi): ResultadoApi<unknown> => ({ ok: false, error });

describe("TKT-008 · captura de motivo", () => {
  test("tkt008_ca12_esc01 · confirmar con motivo (TC-78)", async () => {
    const respuesta = diferido<ResultadoApi<unknown>>();
    const alConfirmar = vi.fn<PropsCapturaMotivo["alConfirmar"]>(() => respuesta.promesa);
    const { alHecho, alRechazo, usuario } = abrir(alConfirmar);

    // El foco abre en el campo: quien captura puede escribir sin tocar el ratón.
    await waitFor(() => expect(campoMotivo()).toHaveFocus());

    await usuario.type(campoMotivo(), "  Material dañado  ");
    await usuario.click(screen.getByRole("button", { name: CONFIRMAR }));

    // El texto llega recortado, una sola vez, y el botón no admite un segundo envío mientras la petición está en vuelo.
    await waitFor(() => expect(alConfirmar).toHaveBeenCalledTimes(1));
    expect(alConfirmar).toHaveBeenCalledWith("Material dañado");
    expect(screen.getByRole("button", { name: CONFIRMAR })).toBeDisabled();
    expect(alHecho).not.toHaveBeenCalled();

    respuesta.resolver({ ok: true, datos: null });

    await waitFor(() => expect(alHecho).toHaveBeenCalledTimes(1));
    expect(alRechazo).not.toHaveBeenCalled();
  });

  test.each([
    ["vacío", ""],
    ["solo espacios", "   "],
  ])("tkt008_ca12_esc02 · sin motivo, %s (TC-79)", async (_descripcion, escrito) => {
    const alConfirmar = vi.fn<PropsCapturaMotivo["alConfirmar"]>();
    const { alHecho, alRechazo, usuario } = abrir(alConfirmar);

    if (escrito !== "") await usuario.type(campoMotivo(), escrito);
    await usuario.click(screen.getByRole("button", { name: CONFIRMAR }));

    expect(await screen.findByText(MENSAJE_OBLIGATORIO)).toBeInTheDocument();
    expect(campoMotivo()).toHaveAttribute("aria-invalid", "true");
    // Nada sale: la pantalla no recibe un motivo que no existe.
    expect(alConfirmar).not.toHaveBeenCalled();
    expect(alHecho).not.toHaveBeenCalled();
    expect(alRechazo).not.toHaveBeenCalled();
  });

  test("tkt008_ca12_esc03 · el servidor rechaza el motivo (TC-80)", async () => {
    const alConfirmar = vi.fn<PropsCapturaMotivo["alConfirmar"]>(async () =>
      rechazo(errorValidacion([{ campo: "motivo", codigo: "VALOR_NO_PERMITIDO", mensaje: MENSAJE_DEL_SERVIDOR }])),
    );
    const { alHecho, alRechazo, usuario } = abrir(alConfirmar);

    await usuario.type(campoMotivo(), "Material dañado");
    await usuario.click(screen.getByRole("button", { name: CONFIRMAR }));

    // El mensaje es el del servidor, no uno propio, y queda junto al campo marcado como inválido.
    expect(await screen.findByText(MENSAJE_DEL_SERVIDOR)).toBeInTheDocument();
    expect(screen.queryByText(MENSAJE_OBLIGATORIO)).not.toBeInTheDocument();
    expect(campoMotivo()).toHaveAttribute("aria-invalid", "true");
    // Lo escrito se conserva para corregirlo, no para volver a teclearlo.
    expect(campoMotivo()).toHaveValue("Material dañado");
    expect(alRechazo).not.toHaveBeenCalled();
    expect(alHecho).not.toHaveBeenCalled();
  });

  test("tkt008_ca12_esc04 · el servidor rechaza la operación (TC-81)", async () => {
    const error = errorRn03ExcedeImporte();
    const alConfirmar = vi.fn<PropsCapturaMotivo["alConfirmar"]>(async () => rechazo(error));
    const { alHecho, alRechazo, usuario } = abrir(alConfirmar);

    await usuario.type(campoMotivo(), "Material dañado");
    await usuario.click(screen.getByRole("button", { name: CONFIRMAR }));

    // El error llega tal cual: es la pantalla quien lo pinta con la de bloqueo.
    await waitFor(() => expect(alRechazo).toHaveBeenCalledTimes(1));
    expect(alRechazo).toHaveBeenCalledWith(error);
    expect(alRechazo.mock.calls[0]?.[0]).toBe(error);
    // La captura no añade mensaje propio: ni alerta, ni el texto del servidor, ni el de obligatorio.
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.queryByText(error.mensaje)).not.toBeInTheDocument();
    expect(screen.queryByText(MENSAJE_OBLIGATORIO)).not.toBeInTheDocument();
    expect(alHecho).not.toHaveBeenCalled();
  });

  test("tkt008_ca12 · cancelar no envía nada", async () => {
    const alConfirmar = vi.fn<PropsCapturaMotivo["alConfirmar"]>();
    const { alCancelar, alHecho, alRechazo, usuario } = abrir(alConfirmar);

    await usuario.type(campoMotivo(), "Material dañado");
    await usuario.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(alCancelar).toHaveBeenCalledTimes(1);
    expect(alConfirmar).not.toHaveBeenCalled();
    expect(alHecho).not.toHaveBeenCalled();
    expect(alRechazo).not.toHaveBeenCalled();
  });

  test("tkt008_ca12 · Escape cierra como cancelar", async () => {
    const alConfirmar = vi.fn<PropsCapturaMotivo["alConfirmar"]>();
    const { alCancelar, usuario } = abrir(alConfirmar);

    await usuario.keyboard("{Escape}");

    expect(alCancelar).toHaveBeenCalledTimes(1);
    expect(alConfirmar).not.toHaveBeenCalled();
  });

  test("tkt008_ca12_esc02 · el aviso de motivo obligatorio es la descripción del campo (C7b, TC-79)", async () => {
    const alConfirmar = vi.fn<PropsCapturaMotivo["alConfirmar"]>();
    const { usuario } = abrir(alConfirmar);

    await usuario.click(screen.getByRole("button", { name: CONFIRMAR }));

    await screen.findByText(MENSAJE_OBLIGATORIO);
    expect(campoMotivo()).toHaveAccessibleDescription(MENSAJE_OBLIGATORIO);
  });

  test("tkt008_ca12_esc03 · el mensaje del servidor es la descripción del campo (C7b, TC-80)", async () => {
    const alConfirmar = vi.fn<PropsCapturaMotivo["alConfirmar"]>(async () =>
      rechazo(errorValidacion([{ campo: "motivo", codigo: "VALOR_NO_PERMITIDO", mensaje: MENSAJE_DEL_SERVIDOR }])),
    );
    const { usuario } = abrir(alConfirmar);

    await usuario.type(campoMotivo(), "Material dañado");
    await usuario.click(screen.getByRole("button", { name: CONFIRMAR }));

    await screen.findByText(MENSAJE_DEL_SERVIDOR);
    expect(campoMotivo()).toHaveAccessibleDescription(MENSAJE_DEL_SERVIDOR);
  });

  test("tkt008_ca12_esc03 · tras el rechazo del servidor el foco va al campo del motivo (C5)", async () => {
    // Hallazgo C5: el error del servidor marcaba el campo pero el foco se quedaba en el botón de confirmar.
    const alConfirmar = vi.fn<PropsCapturaMotivo["alConfirmar"]>(async () =>
      rechazo(errorValidacion([{ campo: "motivo", codigo: "VALOR_NO_PERMITIDO", mensaje: MENSAJE_DEL_SERVIDOR }])),
    );
    const { usuario } = abrir(alConfirmar);

    await usuario.type(campoMotivo(), "Material dañado");
    await usuario.click(screen.getByRole("button", { name: CONFIRMAR }));

    await screen.findByText(MENSAJE_DEL_SERVIDOR);
    await waitFor(() => expect(campoMotivo()).toHaveFocus());
  });

  test("tkt008_ca12_esc02 · un motivo de 2,001 caracteres no se envía (C7c)", async () => {
    const alConfirmar = vi.fn<PropsCapturaMotivo["alConfirmar"]>();
    const { alHecho, usuario } = abrir(alConfirmar);

    await usuario.click(campoMotivo());
    await usuario.paste("a".repeat(2001));
    await usuario.click(screen.getByRole("button", { name: CONFIRMAR }));

    expect(await screen.findByText("El motivo admite hasta 2,000 caracteres.")).toBeInTheDocument();
    expect(campoMotivo()).toHaveAttribute("aria-invalid", "true");
    expect(alConfirmar).not.toHaveBeenCalled();
    expect(alHecho).not.toHaveBeenCalled();
  });

  test("tkt008_ca12_esc01 · un motivo de 2,000 caracteres sí se envía (C7c)", async () => {
    const alConfirmar = vi.fn<PropsCapturaMotivo["alConfirmar"]>(async () => ({ ok: true, datos: null }));
    const { alHecho, usuario } = abrir(alConfirmar);

    await usuario.click(campoMotivo());
    await usuario.paste("a".repeat(2000));
    await usuario.click(screen.getByRole("button", { name: CONFIRMAR }));

    await waitFor(() => expect(alConfirmar).toHaveBeenCalledTimes(1));
    expect(alConfirmar).toHaveBeenCalledWith("a".repeat(2000));
    await waitFor(() => expect(alHecho).toHaveBeenCalledTimes(1));
    expect(screen.queryByText("El motivo admite hasta 2,000 caracteres.")).not.toBeInTheDocument();
  });

  test("tkt008_ca12 · cerrar y reabrir deja el campo vacío (C7d)", async () => {
    const props: PropsCapturaMotivo = {
      abierta: true,
      titulo: "Dar de baja al proveedor",
      etiquetaConfirmar: CONFIRMAR,
      alConfirmar: vi.fn<PropsCapturaMotivo["alConfirmar"]>(),
      alHecho: vi.fn<PropsCapturaMotivo["alHecho"]>(),
      alRechazo: vi.fn<(error: ErrorApi) => void>(),
      alCancelar: vi.fn<PropsCapturaMotivo["alCancelar"]>(),
    };
    const usuario = userEvent.setup();
    const { rerender } = render(<CapturaMotivo {...props} />);
    await usuario.type(campoMotivo(), "Material dañado");
    expect(campoMotivo()).toHaveValue("Material dañado");

    rerender(<CapturaMotivo {...props} abierta={false} />);
    await waitFor(() => expect(screen.queryByRole("textbox", { name: "Motivo" })).not.toBeInTheDocument());
    rerender(<CapturaMotivo {...props} abierta />);

    expect(await screen.findByRole("textbox", { name: "Motivo" })).toHaveValue("");
  });

  test("tkt008_ca12_esc04 · una validación sin errores se delega a la pantalla (C7e)", async () => {
    // `errores: []` no señala ningún campo: no hay a quién marcar, así que el rechazo lo pinta la pantalla.
    const error = errorValidacion([]);
    const alConfirmar = vi.fn<PropsCapturaMotivo["alConfirmar"]>(async () => rechazo(error));
    const { alHecho, alRechazo, usuario } = abrir(alConfirmar);

    await usuario.type(campoMotivo(), "Material dañado");
    await usuario.click(screen.getByRole("button", { name: CONFIRMAR }));

    await waitFor(() => expect(alRechazo).toHaveBeenCalledTimes(1));
    expect(alRechazo.mock.calls[0]?.[0]).toBe(error);
    expect(campoMotivo()).not.toHaveAttribute("aria-invalid", "true");
    expect(alHecho).not.toHaveBeenCalled();
  });

  test("tkt008_ca12 · el error de otro campo va a la alerta del diálogo", async () => {
    const alConfirmar = vi.fn<PropsCapturaMotivo["alConfirmar"]>(async () =>
      rechazo(errorValidacion([{ campo: "proveedor_id", codigo: "VALOR_NO_PERMITIDO", mensaje: "El proveedor ya no existe." }])),
    );
    const { alHecho, alRechazo, usuario } = abrir(alConfirmar);

    await usuario.type(campoMotivo(), "Material dañado");
    await usuario.click(screen.getByRole("button", { name: CONFIRMAR }));

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("El proveedor ya no existe.");
    // El campo de motivo no es el culpable: no se marca ni se le adjudica el mensaje.
    expect(campoMotivo()).not.toHaveAttribute("aria-invalid", "true");
    expect(campoMotivo()).toHaveValue("Material dañado");
    expect(alRechazo).not.toHaveBeenCalled();
    expect(alHecho).not.toHaveBeenCalled();
  });
});

describe("TKT-018a · CapturaMotivo con etiqueta de cancelar propia (CA-7, TC-21)", () => {
  /** La misma captura que `abrir`, pero con las props que la prueba añade. */
  function abrirCon(extra: { etiquetaCancelar?: string }) {
    const alConfirmar = vi.fn<PropsCapturaMotivo["alConfirmar"]>();
    const alHecho = vi.fn<PropsCapturaMotivo["alHecho"]>();
    const alRechazo = vi.fn<(error: ErrorApi) => void>();
    const alCancelar = vi.fn<PropsCapturaMotivo["alCancelar"]>();
    render(
      <CapturaMotivo
        abierta
        titulo="Tope mayor que la venta · GENERALES"
        etiquetaConfirmar="Confirmar con motivo"
        alConfirmar={alConfirmar}
        alHecho={alHecho}
        alRechazo={alRechazo}
        alCancelar={alCancelar}
        {...extra}
      />,
    );
    return { alConfirmar, alHecho, alRechazo, alCancelar, usuario: userEvent.setup() };
  }

  test("tkt018a_ca07 · con etiquetaCancelar «Corregir» el botón se llama así y cancela sin enviar", async () => {
    const { alConfirmar, alHecho, alRechazo, alCancelar, usuario } = abrirCon({ etiquetaCancelar: "Corregir" });

    // El botón de salida lleva la etiqueta pedida y ya no se llama «Cancelar».
    expect(screen.getByRole("button", { name: "Corregir" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancelar" })).not.toBeInTheDocument();

    await usuario.type(campoMotivo(), "Ampliación autorizada");
    await usuario.click(screen.getByRole("button", { name: "Corregir" }));

    expect(alCancelar).toHaveBeenCalledTimes(1);
    expect(alConfirmar).not.toHaveBeenCalled();
    expect(alHecho).not.toHaveBeenCalled();
    expect(alRechazo).not.toHaveBeenCalled();
  });

  test("tkt018a_ca07 · sin etiquetaCancelar el botón sigue llamándose «Cancelar» (CA-R1)", () => {
    abrirCon({});

    expect(screen.getByRole("button", { name: "Cancelar" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Corregir" })).not.toBeInTheDocument();
  });
});

// TKT-018a · entrega b · ciclo de corrección · COD-1. Con el envío en vuelo, la captura no admite salir: «Cancelar»/«Corregir»
// queda deshabilitado y Escape o el clic fuera se ignoran. Cerrarla entonces desmonta el formulario con su petición viva y
// el `alHecho` que llega después actúa sobre una pantalla que ya pasó a otra cosa.
describe("TKT-018a · CapturaMotivo con el envío en vuelo (COD-1)", () => {
  /** Una captura cuyo `alConfirmar` queda pendiente hasta que la prueba lo resuelva; el motivo ya está escrito y enviado. */
  async function enviarYDejarEnVuelo(etiquetaCancelar?: string) {
    const respuesta = diferido<ResultadoApi<unknown>>();
    const alConfirmar = vi.fn<PropsCapturaMotivo["alConfirmar"]>(() => respuesta.promesa);
    const alHecho = vi.fn<PropsCapturaMotivo["alHecho"]>();
    const alRechazo = vi.fn<(error: ErrorApi) => void>();
    const alCancelar = vi.fn<PropsCapturaMotivo["alCancelar"]>();
    render(
      <CapturaMotivo
        abierta
        titulo="Tope mayor que la venta · MUROS"
        etiquetaConfirmar="Confirmar con motivo"
        etiquetaCancelar={etiquetaCancelar}
        alConfirmar={alConfirmar}
        alHecho={alHecho}
        alRechazo={alRechazo}
        alCancelar={alCancelar}
      />,
    );
    const usuario = userEvent.setup();
    await usuario.type(campoMotivo(), "Incluye andamiaje no presupuestado");
    await usuario.click(screen.getByRole("button", { name: "Confirmar con motivo" }));
    await waitFor(() => expect(alConfirmar).toHaveBeenCalledTimes(1));
    return { respuesta, alHecho, alRechazo, alCancelar, usuario };
  }

  test.each([
    ["por omisión «Cancelar»", undefined, "Cancelar"],
    ["con etiqueta propia «Corregir»", "Corregir", "Corregir"],
  ])(
    "tkt018a_ca07 · envío en vuelo · COD-1 · %s: el botón de salida queda deshabilitado, su clic no cancela y al responder llega alHecho una sola vez",
    async (_caso, etiquetaCancelar, etiqueta) => {
      const { respuesta, alHecho, alCancelar, usuario } = await enviarYDejarEnVuelo(etiquetaCancelar);

      expect(screen.getByRole("button", { name: etiqueta })).toBeDisabled();
      await usuario.click(screen.getByRole("button", { name: etiqueta }));
      expect(alCancelar).not.toHaveBeenCalled();
      expect(screen.getByRole("dialog", { name: "Tope mayor que la venta · MUROS" })).toBeInTheDocument();

      respuesta.resolver({ ok: true, datos: null });

      await waitFor(() => expect(alHecho).toHaveBeenCalledTimes(1));
      expect(alCancelar).not.toHaveBeenCalled();
    },
  );

  test("tkt018a_ca07 · envío en vuelo · COD-1 · Escape se ignora: no llama a alCancelar y el diálogo sigue abierto", async () => {
    const { respuesta, alHecho, alCancelar, usuario } = await enviarYDejarEnVuelo();

    await usuario.keyboard("{Escape}");

    expect(alCancelar).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "Tope mayor que la venta · MUROS" })).toBeInTheDocument();

    respuesta.resolver({ ok: true, datos: null });
    await waitFor(() => expect(alHecho).toHaveBeenCalledTimes(1));
    expect(alCancelar).not.toHaveBeenCalled();
  });

  test("tkt018a_ca07 · envío en vuelo · COD-1 · el clic fuera del diálogo se ignora: no llama a alCancelar", async () => {
    const { respuesta, alHecho, alCancelar, usuario } = await enviarYDejarEnVuelo();
    const fondo = document.querySelector<HTMLElement>('[data-slot="dialog-overlay"]');
    if (fondo === null) throw new Error("Falta el fondo del diálogo.");

    await usuario.click(fondo);

    expect(alCancelar).not.toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "Tope mayor que la venta · MUROS" })).toBeInTheDocument();

    respuesta.resolver({ ok: true, datos: null });
    await waitFor(() => expect(alHecho).toHaveBeenCalledTimes(1));
    expect(alCancelar).not.toHaveBeenCalled();
  });

  // Frena el mutante que deja la salida deshabilitada para siempre: un rechazo del servidor la devuelve a la persona.
  test("tkt018a_ca07 · envío en vuelo · COD-1 · tras el rechazo del servidor la salida vuelve a estar disponible: «Corregir» y Escape cancelan", async () => {
    const { respuesta, alRechazo, alCancelar, usuario } = await enviarYDejarEnVuelo("Corregir");
    expect(screen.getByRole("button", { name: "Corregir" })).toBeDisabled();

    respuesta.resolver(rechazo(errorRn03ExcedeImporte()));

    await waitFor(() => expect(alRechazo).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getByRole("button", { name: "Corregir" })).toBeEnabled());
    await usuario.click(screen.getByRole("button", { name: "Corregir" }));
    expect(alCancelar).toHaveBeenCalledTimes(1);
    await usuario.keyboard("{Escape}");
    expect(alCancelar).toHaveBeenCalledTimes(2);
  });
});
