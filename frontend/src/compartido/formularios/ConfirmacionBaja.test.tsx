import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, test, vi } from "vitest";
import type { ResultadoApi } from "@/api/cliente";
import type { ErrorApi } from "@/api/errores";
import { type PropsConfirmacionBaja, ConfirmacionBaja, ETIQUETA_CONFIRMAR_BAJA } from "./ConfirmacionBaja";

const PREGUNTA = "¿Dar de baja este proveedor?";

/** Una promesa cuyo desenlace decide la prueba: así «en vuelo» se observa sin esperar por tiempo. */
function diferido<T>() {
  let resolver!: (valor: T) => void;
  let rechazar!: (motivo: unknown) => void;
  const promesa = new Promise<T>((resolve, reject) => {
    resolver = resolve;
    rechazar = reject;
  });
  return { promesa, resolver, rechazar };
}

/** El arnés: «+» abre la confirmación; cancelar o un rechazo ordenado la cierran, como hace el formulario que la contiene. */
function abrir(
  alConfirmar: PropsConfirmacionBaja["alConfirmar"],
  { alHecho = vi.fn<PropsConfirmacionBaja["alHecho"]>(), alRechazo = vi.fn<PropsConfirmacionBaja["alRechazo"]>() } = {},
) {

  function Arnes() {
    const [abierta, setAbierta] = useState(false);
    return (
      <>
        <button type="button" onClick={() => setAbierta(true)}>
          +
        </button>
        <ConfirmacionBaja
          abierta={abierta}
          pregunta={PREGUNTA}
          alConfirmar={alConfirmar}
          alHecho={() => {
            setAbierta(false);
            alHecho();
          }}
          alRechazo={(error) => {
            setAbierta(false);
            alRechazo(error);
          }}
          alCancelar={() => setAbierta(false)}
        />
      </>
    );
  }

  render(<Arnes />);
  return { alHecho, alRechazo, usuario: userEvent.setup() };
}

type Usuario = ReturnType<typeof userEvent.setup>;

async function abrirConfirmacion(usuario: Usuario) {
  await usuario.click(screen.getByRole("button", { name: "+" }));
  await screen.findByText(PREGUNTA);
}

/**
 * Un error que se escapa de un manejador de clic async llega como `unhandledRejection`, y Vitest lo reporta como
 * «Unhandled Error» y da la suite por fallida. Aquí se captura de forma controlada: se retiran los oyentes de Vitest
 * mientras dura la prueba, se anota lo que llega y se restauran al terminar. Un turno de macrotarea basta para que
 * Node entregue el rechazo pendiente; no es una espera por tiempo.
 */
async function capturandoRechazosSinManejar(prueba: () => Promise<void>): Promise<unknown[]> {
  const capturados: unknown[] = [];
  const previos = process.listeners("unhandledRejection");
  process.removeAllListeners("unhandledRejection");
  const capturar = (motivo: unknown) => {
    capturados.push(motivo);
  };
  process.on("unhandledRejection", capturar);
  try {
    await prueba();
    await new Promise((resolve) => setTimeout(resolve, 0));
  } finally {
    process.off("unhandledRejection", capturar);
    for (const oyente of previos) process.on("unhandledRejection", oyente);
  }
  return capturados;
}

const botonConfirmar = () => screen.getByRole("button", { name: ETIQUETA_CONFIRMAR_BAJA });

describe("TKT-008 · confirmación de baja", () => {
  test("tkt008_ca11_esc06 · mientras la baja está en vuelo no admite otra confirmación", async () => {
    const respuesta = diferido<ResultadoApi<unknown>>();
    const alConfirmar = vi.fn<PropsConfirmacionBaja["alConfirmar"]>(() => respuesta.promesa);
    const { alHecho, usuario } = abrir(alConfirmar);
    await abrirConfirmacion(usuario);

    await usuario.click(botonConfirmar());

    // En vuelo: una sola petición y el botón deshabilitado; un segundo clic no envía nada.
    await waitFor(() => expect(alConfirmar).toHaveBeenCalledTimes(1));
    expect(botonConfirmar()).toBeDisabled();
    await usuario.click(botonConfirmar());
    expect(alConfirmar).toHaveBeenCalledTimes(1);
    expect(alHecho).not.toHaveBeenCalled();

    respuesta.resolver({ ok: true, datos: null });

    await waitFor(() => expect(alHecho).toHaveBeenCalledTimes(1));
  });

  test("tkt008_ca11_esc06 · si la baja lanza, entrega un rechazo genérico y al reabrir el botón vuelve a estar habilitado", async () => {
    // `enVuelo` no puede quedar en `true` si `alConfirmar` rechaza: la confirmación (siempre montada)
    // conserva el estado, y al reabrirla, «Confirmar baja» seguía deshabilitado y no había forma de reintentar.
    // Decisión (asumido, PA-T16): el componente absorbe el fallo, no lo relanza y lo entrega como rechazo genérico.
    // Una promesa rechazada sin manejar tumba la suite de Vitest, así que la ausencia de relanzado se verifica sola.
    const respuesta = diferido<ResultadoApi<unknown>>();
    const alConfirmar = vi.fn<PropsConfirmacionBaja["alConfirmar"]>(() => respuesta.promesa);
    const { alHecho, alRechazo, usuario } = abrir(alConfirmar);
    await abrirConfirmacion(usuario);

    await usuario.click(botonConfirmar());
    await waitFor(() => expect(alConfirmar).toHaveBeenCalledTimes(1));
    expect(botonConfirmar()).toBeDisabled();

    await act(async () => {
      respuesta.rechazar(new Error("fallo inesperado"));
    });

    // Una sola vez y con el objeto exacto; no es un éxito.
    await waitFor(() => expect(alRechazo).toHaveBeenCalledTimes(1));
    expect(alRechazo).toHaveBeenCalledWith({ tipo: "GENERICO", estado: 0, mensaje: null, correlacion_id: null });
    expect(alHecho).not.toHaveBeenCalled();

    // El arnés cerró la confirmación al recibir el rechazo; la persona la vuelve a abrir y debe poder reenviar.
    await waitFor(() => expect(screen.queryByText(PREGUNTA)).not.toBeInTheDocument());
    await abrirConfirmacion(usuario);

    expect(botonConfirmar()).toBeEnabled();
  });

  test("tkt008_ca11_esc06 · si alHecho lanza tras una baja exitosa, no se entrega un rechazo", async () => {
    // `alHecho()` va fuera del `try`: un fallo de la pantalla no se disfraza de baja rechazada.
    // El error de `alHecho` no es de la baja: puede propagarse (aquí se captura como rechazo sin manejar) pero no llega a `alRechazo`.
    const fallo = new Error("fallo de la pantalla al cerrar");
    const alHecho = vi.fn<PropsConfirmacionBaja["alHecho"]>(() => {
      throw fallo;
    });
    const alRechazo = vi.fn<PropsConfirmacionBaja["alRechazo"]>();
    const alConfirmar = vi.fn<PropsConfirmacionBaja["alConfirmar"]>(async () => ({ ok: true, datos: null }));
    const { usuario } = abrir(alConfirmar, { alHecho, alRechazo });
    await abrirConfirmacion(usuario);

    const capturados = await capturandoRechazosSinManejar(async () => {
      await usuario.click(botonConfirmar());
      await waitFor(() => expect(alHecho).toHaveBeenCalledTimes(1));
      expect(alRechazo).not.toHaveBeenCalled();
    });

    // El fallo de la pantalla se propaga (no se traga) y es exactamente el que lanzó `alHecho`.
    expect(capturados).toHaveLength(1);
    expect(capturados[0]).toBe(fallo);
    expect(alConfirmar).toHaveBeenCalledTimes(1);
    expect(alRechazo).not.toHaveBeenCalled();
  });

  test("tkt008_ca11_esc07 · si alRechazo lanza tras un rechazo del servidor, se llama una sola vez", async () => {
    // Si `alRechazo` lanza, el `catch` no puede volver a llamarlo con un rechazo genérico.
    const rechazoDelServidor: ErrorApi = { tipo: "GENERICO", estado: 500, mensaje: "Fallo interno al dar de baja.", correlacion_id: null };
    const fallo = new Error("fallo de la pantalla al mostrar el rechazo");
    const alHecho = vi.fn<PropsConfirmacionBaja["alHecho"]>();
    const alRechazo = vi.fn<PropsConfirmacionBaja["alRechazo"]>(() => {
      throw fallo;
    });
    const alConfirmar = vi.fn<PropsConfirmacionBaja["alConfirmar"]>(async () => ({ ok: false, error: rechazoDelServidor }));
    const { usuario } = abrir(alConfirmar, { alHecho, alRechazo });
    await abrirConfirmacion(usuario);

    const capturados = await capturandoRechazosSinManejar(async () => {
      await usuario.click(botonConfirmar());
      await waitFor(() => expect(alRechazo).toHaveBeenCalled());
    });

    // El fallo de la pantalla se propaga (no se traga) y es exactamente el que lanzó `alRechazo`.
    expect(capturados).toHaveLength(1);
    expect(capturados[0]).toBe(fallo);
    expect(alRechazo).toHaveBeenCalledTimes(1);
    expect(alRechazo).toHaveBeenCalledWith(rechazoDelServidor);
    expect(alHecho).not.toHaveBeenCalled();
  });
});
