import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import type { Accion, ErrorBloqueo } from "@/api/errores";
import { errorConcurrencia, errorConflictoEstado } from "@/pruebas/cuerpos";
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
