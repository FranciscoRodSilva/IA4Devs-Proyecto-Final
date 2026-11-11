import { act, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { type Accion, type ErrorBloqueo, esObjeto } from "@/api/errores";
import {
  errorConcurrencia,
  errorConflictoEstado,
  errorExplosionNoCalculable,
  errorTopeSuperior,
} from "@/pruebas/cuerpos";
import { ConflictoEnLinea } from "./ConflictoEnLinea";

// Los tiempos se controlan con el reloj simulado; ninguna prueba hace `sleep`.
beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
afterEach(() => {
  vi.useRealTimers();
});

describe("TKT-008 · conflicto en línea", () => {
  test("tkt008_ca11_esc05 · una segunda concurrencia reinicia la espera (C1/A1)", () => {
    // Hallazgo C1/A1: la cuenta atrás tomaba los segundos solo al montar; el segundo 409 reutilizaba la primera espera.
    const alAccion = vi.fn<(accion: Accion) => void>();
    const primera: ErrorBloqueo = { ...errorConcurrencia(), reintentar_tras_s: 2 };
    const segunda: ErrorBloqueo = {
      ...errorConcurrencia({ correlacion_id: "0c9e5d3b-6e4a-4b9c-8d7f-2a3b4c5d6e7f" }),
      reintentar_tras_s: 3,
    };
    const { rerender } = render(<ConflictoEnLinea error={primera} alAccion={alAccion} />);
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeDisabled();

    act(() => {
      vi.advanceTimersByTime(2_000);
    });
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeEnabled();

    rerender(<ConflictoEnLinea error={segunda} alAccion={alAccion} />);

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

  test("tkt008_ca11_esc05 · el conflicto se anuncia en una región viva (C4)", () => {
    // Hallazgo C4: el conflicto aparece tras guardar; sin región viva, un lector de pantalla no lo anuncia.
    render(<ConflictoEnLinea error={errorConflictoEstado("CODIGO_OBRA_DUPLICADO")} alAccion={vi.fn()} />);

    const conflicto = screen.getByRole("region");
    expect(conflicto.closest('[aria-live="polite"]')).not.toBeNull();
  });

  test("hdu001_esc03 · TC-F02 · el código duplicado muestra la obra existente con «Ver la obra» y sin su UUID", () => {
    // CA-11 esc. 1. La persona necesita el código y el nombre del registro que ya existe, no su identificador interno.
    const idExistente = "9a1f2b3c-4d5e-4f60-8a71-b2c3d4e5f607";
    const error = errorConflictoEstado("CODIGO_OBRA_DUPLICADO", {
      mensaje: "Ya existe una obra con el código AP-058-25.",
      detalle: { obra_existente_id: idExistente, obra_existente: "AP-058-25 · Union Square F2" },
      acciones: [{ clave: "VER_OBRA", metodo: "GET", ruta: `/api/v1/obras/${idExistente}` }],
    });

    render(<ConflictoEnLinea error={error} alAccion={vi.fn()} />);

    expect(screen.getByText("Obra existente", { selector: "dt" })).toBeInTheDocument();
    expect(screen.getByText("AP-058-25 · Union Square F2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ver la obra" })).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(idExistente);
    expect(screen.queryByText("obra_existente_id")).not.toBeInTheDocument();
  });
});

describe("TKT-018a · rechazos de la línea base en línea (TC-04)", () => {
  /** El `<dd>` que acompaña a un `<dt>` del detalle. */
  function valorDe(termino: string): HTMLElement {
    const dt = screen.getByText(termino, { selector: "dt" });
    const dd = dt.nextElementSibling;
    if (!(dd instanceof HTMLElement) || dd.tagName !== "DD") throw new Error(`«${termino}» no va seguido de su <dd>`);
    return dd;
  }

  test("tkt018a_ca04 · la explosión no calculable muestra la tabla «Causas» con concepto, causa e insumo", () => {
    // CA-4: `ESTADO_NO_PERMITE_OPERACION` con las causas de `detalle_de_causas`. Sin tabla, llegarían como JSON crudo.
    const error = errorExplosionNoCalculable();

    render(<ConflictoEnLinea error={error} alAccion={vi.fn()} />);

    expect(screen.getByRole("region")).toHaveAttribute("data-estado", "bloqueado");
    expect(screen.getByText(error.mensaje)).toBeInTheDocument();
    const tabla = screen.getByRole("table", { name: "Causas" });
    expect(within(tabla).getAllByRole("columnheader").map((columna) => columna.textContent)).toEqual([
      "Concepto", "Causa", "Insumo",
    ]);
    // El encabezado más una fila por causa, en el orden en que llegaron.
    const filas = within(tabla).getAllByRole("row");
    expect(filas).toHaveLength(3);
    const [, primera] = filas;
    if (primera === undefined) throw new Error("Falta la fila de la primera causa");
    expect(within(primera).getAllByRole("cell").map((celda) => celda.textContent)).toEqual([
      "620040-A", "INSUMO_SIN_COSTO", "TAB-0127",
    ]);
    expect(filas[2]).toHaveTextContent("SUGERIDO_NEGATIVO");
    // Las causas no se pintan además como clave cruda con su JSON.
    expect(screen.queryByText("causas")).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("clave_insumo");
  });

  test("tkt018a_ca04 · las causas no pintan ningún identificador interno", () => {
    // D-8: ni el de la línea base ni el del tipo de partida de una causa; tampoco sus claves.
    const error = errorExplosionNoCalculable();
    const idLineaBase = error.detalle.linea_base_id;
    const causas: unknown = error.detalle.causas;
    const idsTipoPartida = (Array.isArray(causas) ? causas : [])
      .map((causa: unknown) => (esObjeto(causa) ? causa.tipo_partida_id : null))
      .filter((id): id is string => typeof id === "string");
    // La prueba lee los valores de la fábrica: sin identificadores, las afirmaciones de abajo no demostrarían nada.
    expect(typeof idLineaBase).toBe("string");
    expect(idsTipoPartida).toHaveLength(1);

    render(<ConflictoEnLinea error={error} alAccion={vi.fn()} />);

    expect(screen.queryByText("linea_base_id")).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent(String(idLineaBase));
    expect(document.body).not.toHaveTextContent("tipo_partida_id");
    const [idTipoPartida] = idsTipoPartida;
    expect(idTipoPartida).toBeDefined();
    expect(document.body).not.toHaveTextContent(String(idTipoPartida));
  });

  test("tkt018a_ca04 · una causa sin concepto ni insumo deja la celda vacía y no pinta «null»", () => {
    // El sugerido negativo es una causa por tipo de partida: el servidor manda `concepto` y `clave_insumo` en `null`.
    render(<ConflictoEnLinea error={errorExplosionNoCalculable()} alAccion={vi.fn()} />);

    const tabla = screen.getByRole("table", { name: "Causas" });
    const fila = within(tabla).getByRole("row", { name: /SUGERIDO_NEGATIVO/ });
    expect(within(fila).getAllByRole("cell").map((celda) => celda.textContent)).toEqual(["", "SUGERIDO_NEGATIVO", ""]);
    expect(tabla).not.toHaveTextContent("null");
  });

  test("tkt018a_ca04 · la obra fuera de planeación muestra «Estado de la obra» con su valor", () => {
    // CA-4: el congelado sobre una obra que no está en PLANEACION. El `detalle` es el de `_conflicto_obra` del backend.
    const error = errorConflictoEstado("ESTADO_NO_PERMITE_OPERACION", {
      mensaje: "La obra AP-058-25 está en SUSPENDIDA y no admite esta operación.",
      detalle: { obra: "AP-058-25 · Union Square F2", estado_obra: "SUSPENDIDA" },
    });

    render(<ConflictoEnLinea error={error} alAccion={vi.fn()} />);

    expect(screen.getByText(error.mensaje)).toBeInTheDocument();
    expect(valorDe("Obra")).toHaveTextContent("AP-058-25 · Union Square F2");
    expect(valorDe("Estado de la obra")).toHaveTextContent(/^SUSPENDIDA$/);
    expect(screen.queryByText("estado_obra")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  test("hdu001_esc17 · el tope mayor que la venta muestra «Venta» y «Tope» con las cifras del servidor", () => {
    // CA-7 · RN-03, RN-04. Las dos cifras llegan como cadena con escala 4 y se muestran sin pérdida ni resta.
    const error = errorTopeSuperior("GENERALES", "7400.0000", "8000.0000");

    render(<ConflictoEnLinea error={error} alAccion={vi.fn()} />);

    expect(screen.getByText(/TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR/)).toBeInTheDocument();
    expect(screen.getByText(error.mensaje)).toBeInTheDocument();
    expect(valorDe("Venta")).toHaveTextContent("$7,400.00");
    expect(valorDe("Tope")).toHaveTextContent("$8,000.00");
    expect(valorDe("Tipo de partida")).toHaveTextContent("GENERALES");
    // Ninguna clave cruda del detalle a la vista, y solo la acción que mandó el servidor.
    expect(screen.queryByText("importe_venta")).not.toBeInTheDocument();
    expect(screen.queryByText("importe_tope")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button").map((boton) => boton.textContent)).toEqual(["Confirmar el tope"]);
  });
});
