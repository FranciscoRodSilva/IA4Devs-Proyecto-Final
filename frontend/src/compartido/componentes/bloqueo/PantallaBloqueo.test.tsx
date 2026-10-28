import { act, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import type { Accion, ErrorBloqueo } from "@/api/errores";
import {
  errorConcurrencia,
  errorConflictoEstado,
  errorPermiso,
  errorRn03ExcedeImporte,
  errorRn03PorVolumen,
  errorRn07ExcedeOrdenado,
  errorValidacion,
} from "@/pruebas/cuerpos";
import { servidorPruebas } from "@/pruebas/servidor";
import { PantallaBloqueo, type PropsPantallaBloqueo } from "./PantallaBloqueo";

const CORRELACION_ID = "7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e";
const CIFRAS_EN_ORDEN = ["Presupuestado", "Consumido", "Disponible", "Solicitado", "Excedente"];

// Los tiempos se controlan con el reloj simulado que avanza solo: `usuario` de userEvent lo exige y ninguna prueba hace `sleep`.
beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
afterEach(() => {
  vi.useRealTimers();
  servidorPruebas.events.removeAllListeners();
});

/** Anota «MÉTODO /ruta» de cada petición que sale hacia el doble del servidor: la pantalla no debe lanzar ninguna. */
function registrarPeticiones(): string[] {
  const registro: string[] = [];
  servidorPruebas.events.on("request:start", ({ request }) => {
    registro.push(`${request.method} ${new URL(request.url).pathname}`);
  });
  return registro;
}

/** La pantalla de bloqueo con sus tres salidas espiadas. Todo es síncrono: el reloj simulado no se mueve entre el montaje y la prueba. */
function abrir(error: ErrorBloqueo, alReintentar?: PropsPantallaBloqueo["alReintentar"]) {
  const alAccion = vi.fn<(accion: Accion) => void>();
  const alCerrar = vi.fn<() => void>();
  render(<PantallaBloqueo error={error} alAccion={alAccion} alCerrar={alCerrar} alReintentar={alReintentar} />);
  const usuario = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  return { alAccion, alCerrar, usuario };
}

/** El `<dd>` que acompaña a un `<dt>` del detalle. */
function valorDe(termino: string): HTMLElement {
  const dt = screen.getByText(termino, { selector: "dt" });
  const dd = dt.nextElementSibling;
  if (!(dd instanceof HTMLElement) || dd.tagName !== "DD") throw new Error(`«${termino}» no va seguido de su <dd>`);
  return dd;
}

function nombresDeBotones(): Array<string | null> {
  return screen.getAllByRole("button").map((boton) => boton.textContent);
}

describe("TKT-008 · pantalla de bloqueo", () => {
  test("tkt008_ca08_esc01 · bloqueo por importe (TC-65)", () => {
    const error = errorRn03ExcedeImporte();

    abrir(error);

    const region = screen.getByRole("region");
    expect(region).toHaveAttribute("data-estado", "bloqueado");
    expect(screen.getByText(/Operación bloqueada/)).toBeInTheDocument();
    expect(screen.getByText(/Regla RN-03/)).toBeInTheDocument();
    expect(screen.getByText(error.mensaje)).toBeInTheDocument();

    const cifras = screen.getAllByRole("term").map((termino) => termino.textContent);
    expect(cifras.filter((termino) => termino !== null && CIFRAS_EN_ORDEN.includes(termino))).toEqual(CIFRAS_EN_ORDEN);
    expect(valorDe("Presupuestado")).toHaveTextContent("$45,000.00");
    expect(valorDe("Consumido")).toHaveTextContent("$33,000.00");
    expect(valorDe("Disponible")).toHaveTextContent("$12,000.00");
    expect(valorDe("Solicitado")).toHaveTextContent("$15,000.00");
    expect(valorDe("Excedente")).toHaveTextContent("$3,000.00");
    expect(
      screen.getByText("requisiciones vivas $6,000.00 · comprometido $9,000.00 · ejercido $18,000.00", { exact: false }),
    ).toBeInTheDocument();
    expect(valorDe("Excedente")).toHaveAttribute("data-resaltada", "true");
    expect(valorDe("Disponible")).not.toHaveAttribute("data-resaltada");
    expect(screen.getByText(/Referencia: /)).toHaveTextContent(`Referencia: ${CORRELACION_ID}`);
  });

  test("tkt008_ca08_esc01 · el excedente es el que llegó (TC-66)", () => {
    // Incoherente a propósito: 15,000 − 12,000 = 3,000. Un componente que resta mostraría $3,000.00.
    abrir(errorRn03ExcedeImporte({ detalle: { excedente: "2999.0000" } }));

    expect(valorDe("Excedente")).toHaveTextContent("$2,999.00");
    expect(valorDe("Excedente")).not.toHaveTextContent("$3,000.00");
    expect(screen.queryByText("$3,000.00")).not.toBeInTheDocument();
  });

  test("tkt008_ca08_esc02 · por volumen (TC-67)", () => {
    abrir(errorRn03PorVolumen());

    expect(screen.getAllByRole("columnheader").map((columna) => columna.textContent)).toEqual([
      "Insumo", "Presupuestado", "Consumido", "Disponible", "Solicitado", "Excedente",
    ]);
    const presupuestado = screen.getByRole("row", { name: /Placa de yeso de 12\.7 mm/ });
    expect(presupuestado).toHaveTextContent(/100\.00 PZA.*90\.00 PZA.*10\.00 PZA.*25\.00 PZA.*15\.00 PZA/);
    expect(presupuestado).not.toHaveTextContent("no presupuestado en esta partida");
    const sinPresupuestar = screen.getByRole("row", { name: /Perfil de acero galvanizado/ });
    expect(sinPresupuestar).toHaveTextContent(/0\.00 ML.*0\.00 ML.*0\.00 ML.*12\.00 ML.*12\.00 ML/);
    expect(sinPresupuestar).toHaveTextContent("no presupuestado en esta partida");
    expect(screen.getAllByText(/no presupuestado en esta partida/)).toHaveLength(1);
  });

  test("tkt008_ca08_esc03 · excedente de recepción (TC-68)", () => {
    const error = errorRn07ExcedeOrdenado();

    abrir(error);

    expect(screen.getByText(/Regla RN-07/)).toBeInTheDocument();
    expect(valorDe("Orden de compra")).toHaveTextContent("OC-2026-0118");
    expect(screen.getAllByRole("columnheader").map((columna) => columna.textContent)).toEqual([
      "Insumo", "Ordenado", "Recibido", "Saldo pendiente", "Entrante", "Excedente",
    ]);
    expect(screen.getByRole("row", { name: /Pasta para juntas/ })).toHaveTextContent(
      /40\.00.*30\.00.*10\.00.*15\.00.*5\.00/,
    );
    expect(screen.getByRole("row", { name: /Cinta de papel/ })).toHaveTextContent(
      /24\.00.*18\.00.*6\.00.*9\.00.*3\.00/,
    );
  });

  test("tkt008_ca08_esc04 · clave desconocida (TC-69)", () => {
    abrir(errorRn03ExcedeImporte({ detalle: { cifra_nueva: "12.0000", otra: { a: 1 } } }));

    expect(valorDe("cifra_nueva")).toHaveTextContent("12.0000");
    expect(valorDe("otra")).toHaveTextContent('{"a":1}');
    // Las referencias internas no se pintan (D-8): ni su nombre ni su valor.
    expect(screen.queryByText("requisicion_id")).not.toBeInTheDocument();
    expect(screen.queryByText("solicitud_autorizacion_id")).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("3d9a7c10-6b2e-4f41-8a95-0c7d2e5b9f13");
  });

  test("tkt008_ca08_esc05 · cifra no decimal (TC-70)", () => {
    expect(() => abrir(errorRn03ExcedeImporte({ detalle: { disponible: "abc" } }))).not.toThrow();

    expect(valorDe("Disponible")).toHaveTextContent("No disponible");
    expect(document.body).not.toHaveTextContent("NaN");
    // Las demás cifras no se contagian.
    expect(valorDe("Presupuestado")).toHaveTextContent("$45,000.00");
  });

  test("tkt008_ca09_esc01 · conflicto (TC-71)", () => {
    const error = errorConflictoEstado("ESTADO_NO_PERMITE_OPERACION");

    abrir(error);

    expect(screen.getByRole("region")).toHaveAttribute("data-estado", "bloqueado");
    expect(screen.getByText(/No se puede completar/)).toBeInTheDocument();
    expect(screen.getByText(/ESTADO_NO_PERMITE_OPERACION/)).toBeInTheDocument();
    expect(screen.getByText(error.mensaje)).toBeInTheDocument();
    // Un conflicto no viola ninguna regla RN: no hay «Regla» ni «Operación bloqueada».
    expect(screen.queryByText(/Regla/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Operación bloqueada/)).not.toBeInTheDocument();
  });

  test("tkt008_ca09_esc02 · reintentar con espera (TC-72)", async () => {
    const alReintentar = vi.fn<() => void>();
    const { alAccion, usuario } = abrir({ ...errorConcurrencia(), reintentar_tras_s: 2 }, alReintentar);

    expect(screen.getByText(/Inténtalo de nuevo/)).toBeInTheDocument();
    expect(screen.queryByText(/Regla/)).not.toBeInTheDocument();
    const reintentar = screen.getByRole("button", { name: "Reintentar" });
    expect(reintentar).toBeDisabled();

    // Síncrono hasta aquí: el reloj simulado solo avanza lo que la prueba le dice.
    act(() => {
      vi.advanceTimersByTime(1_999);
    });
    expect(reintentar).toBeDisabled();
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(reintentar).toBeEnabled();

    await usuario.click(reintentar);

    expect(alReintentar).toHaveBeenCalledTimes(1);
    expect(alAccion).not.toHaveBeenCalled();
  });

  test("tkt008_ca09_esc02 · una segunda concurrencia reinicia la espera (C1/A1)", () => {
    // Hallazgo C1/A1: la cuenta atrás tomaba los segundos solo al montar; un segundo 409 con otra espera
    // reutilizaba la primera (ya vencida) y «Reintentar» nacía habilitado.
    const primera: ErrorBloqueo = { ...errorConcurrencia(), reintentar_tras_s: 2 };
    const segunda: ErrorBloqueo = {
      ...errorConcurrencia({ correlacion_id: "0c9e5d3b-6e4a-4b9c-8d7f-2a3b4c5d6e7f" }),
      reintentar_tras_s: 3,
    };
    const props = { alAccion: vi.fn<(accion: Accion) => void>(), alCerrar: vi.fn<() => void>(), alReintentar: vi.fn<() => void>() };
    const { rerender } = render(<PantallaBloqueo error={primera} {...props} />);
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeDisabled();

    act(() => {
      vi.advanceTimersByTime(2_000);
    });
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeEnabled();

    rerender(<PantallaBloqueo error={segunda} {...props} />);

    // La espera nueva cuenta desde cero: el botón vuelve a quedar deshabilitado y se abre a los 3 s, no antes.
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeDisabled();
    act(() => {
      vi.advanceTimersByTime(2_999);
    });
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeDisabled();
    act(() => {
      vi.advanceTimersByTime(1);
    });
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeEnabled();
  });

  test("tkt008_ca08_esc03 · el identificador interno de la orden no se pinta (C7a, TC-68)", () => {
    const error = errorRn07ExcedeOrdenado();
    const detalle: Record<string, unknown> = error.detalle ?? {};
    const idOrden = detalle.orden_compra_id;
    // La prueba lee el valor de la fábrica: si no hubiera uno, la afirmación de abajo no demostraría nada.
    expect(typeof idOrden).toBe("string");

    abrir(error);

    // Las referencias internas no se pintan (D-8): ni su nombre ni su valor; el folio legible sí.
    expect(screen.queryByText("orden_compra_id")).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(String(idOrden));
    expect(valorDe("Orden de compra")).toHaveTextContent("OC-2026-0118");
  });

  test("tkt008_ca09_esc03 · sin función de reintento (TC-73)", async () => {
    const error: ErrorBloqueo = { ...errorConcurrencia(), reintentar_tras_s: null };
    const { alAccion, usuario } = abrir(error);

    await usuario.click(screen.getByRole("button", { name: "Reintentar" }));

    expect(alAccion).toHaveBeenCalledTimes(1);
    expect(alAccion).toHaveBeenCalledWith({
      clave: "REINTENTAR",
      metodo: "POST",
      ruta: "/api/v1/requisiciones/3d9a7c10-6b2e-4f41-8a95-0c7d2e5b9f13/envio",
    });
  });

  test("tkt008_ca09_esc04 · solo 409 (TC-74)", () => {
    // Lo comprueba `npm run typecheck`: si la entrada admitiera un 422 o un 403, el `@ts-expect-error` sobraría y fallaría.
    // @ts-expect-error CA-9 esc. 4: un ErrorValidacion (422) no es entrada de la pantalla de bloqueo.
    const desdeValidacion: PropsPantallaBloqueo["error"] = errorValidacion([]);
    // @ts-expect-error CA-9 esc. 4: un ErrorPermiso (403) no es entrada de la pantalla de bloqueo.
    const desdePermiso: PropsPantallaBloqueo["error"] = errorPermiso("ROL_INSUFICIENTE");

    expect(desdeValidacion).toBeDefined();
    expect(desdePermiso).toBeDefined();
  });

  test("tkt008_ca10_esc01 · un botón por acción (TC-75)", async () => {
    const registro = registrarPeticiones();
    const verSolicitud: Accion = {
      clave: "VER_SOLICITUD_AUTORIZACION",
      metodo: "GET",
      ruta: "/api/v1/solicitudes-autorizacion/5e2b8d41-7c3f-4a60-9b18-1d4e6f8a0c27",
    };
    const cancelar: Accion = {
      clave: "CANCELAR_REQUISICION",
      metodo: "POST",
      ruta: "/api/v1/requisiciones/3d9a7c10-6b2e-4f41-8a95-0c7d2e5b9f13/cancelacion",
    };
    const { alAccion, usuario } = abrir(errorRn03ExcedeImporte({ acciones: [verSolicitud, cancelar] }));

    expect(nombresDeBotones()).toEqual(["Ver solicitud de autorización", "Cancelar la requisición", "Cerrar"]);

    await usuario.click(screen.getByRole("button", { name: "Ver solicitud de autorización" }));

    expect(alAccion).toHaveBeenCalledTimes(1);
    expect(alAccion).toHaveBeenCalledWith(verSolicitud);
    // La pantalla entrega la acción, no la invoca: ninguna petición salió.
    expect(registro).toEqual([]);
  });

  test("tkt008_ca10_esc02 · solo Cerrar (TC-76)", async () => {
    const { alAccion, alCerrar, usuario } = abrir(errorRn03ExcedeImporte({ acciones: [] }));

    expect(nombresDeBotones()).toEqual(["Cerrar"]);

    await usuario.click(screen.getByRole("button", { name: "Cerrar" }));

    expect(alCerrar).toHaveBeenCalledTimes(1);
    expect(alAccion).not.toHaveBeenCalled();
  });

  test("tkt008_ca10_esc03 · clave desconocida (TC-77)", async () => {
    const desconocida: Accion = { clave: "HACER_ALGO", metodo: "POST", ruta: "/api/v1/algo" };
    const { alAccion, usuario } = abrir(errorRn03ExcedeImporte({ acciones: [desconocida] }));

    expect(nombresDeBotones()).toEqual(["HACER_ALGO", "Cerrar"]);

    await usuario.click(within(screen.getByRole("region")).getByRole("button", { name: "HACER_ALGO" }));

    expect(alAccion).toHaveBeenCalledTimes(1);
    expect(alAccion).toHaveBeenCalledWith(desconocida);
  });
});
