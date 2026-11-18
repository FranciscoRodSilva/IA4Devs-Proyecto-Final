import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, test, vi } from "vitest";
import type { Accion } from "@/api/errores";
import { BotonesAcciones } from "./BotonesAcciones";
import { ETIQUETAS_ACCION } from "./etiquetas";

// TKT-012b · fila B4 · TC-77 y TC-78 (CA-16, HDU-001 esc. 20). Archivo nuevo: no altera ninguna aserción de
// `PantallaBloqueo.test.tsx`. El borrador OpenAPI (`eliminar_obra`) ofrece `SUSPENDER_OBRA` y `CERRAR_OBRA` en el 409
// `OBRA_CON_HISTORIAL`; sin rótulo, `BotonesAcciones` pinta la clave cruda.

const RUTA_OBRA = "/api/v1/obras/7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e";
const SUSPENDER_OBRA: Accion = { clave: "SUSPENDER_OBRA", metodo: "POST", ruta: `${RUTA_OBRA}/suspension` };
const CERRAR_OBRA: Accion = { clave: "CERRAR_OBRA", metodo: "POST", ruta: `${RUTA_OBRA}/cierre` };

describe("TKT-012b · TC-77 · los rótulos de las acciones de obra del contrato (CA-16)", () => {
  test.each([
    ["SUSPENDER_OBRA", "Suspender"],
    ["CERRAR_OBRA", "Cerrar"],
  ])("tkt012b_ca16 · TC-77 · ETIQUETAS_ACCION rotula %s como «%s»", (clave, rotulo) => {
    expect(ETIQUETAS_ACCION[clave]).toBe(rotulo);
  });

  test("tkt012b_ca16 · TC-77 · BotonesAcciones pinta «Suspender» y «Cerrar», en el orden del servidor, y no las claves crudas", () => {
    render(<BotonesAcciones acciones={[SUSPENDER_OBRA, CERRAR_OBRA]} alAccion={vi.fn()} />);

    expect(screen.getAllByRole("button").map((boton) => boton.textContent)).toEqual(["Suspender", "Cerrar"]);
    expect(screen.queryByText("SUSPENDER_OBRA")).not.toBeInTheDocument();
    expect(screen.queryByText("CERRAR_OBRA")).not.toBeInTheDocument();
  });

  test("tkt012b_ca16 · TC-77 · pulsar una acción entrega la acción tal como llegó, con su ruta", async () => {
    const alAccion = vi.fn<(accion: Accion) => void>();
    render(<BotonesAcciones acciones={[CERRAR_OBRA]} alAccion={alAccion} />);

    await userEvent.setup().click(screen.getByRole("button", { name: "Cerrar" }));

    expect(alAccion).toHaveBeenCalledExactlyOnceWith(CERRAR_OBRA);
  });

  test("tkt012b_ca16 · TC-78 · los rótulos existentes no cambian", () => {
    expect(ETIQUETAS_ACCION.VER_OBRA).toBe("Ver la obra");
    expect(ETIQUETAS_ACCION.CONGELAR_LINEA_BASE).toBe("Congelar la línea base");
    expect(ETIQUETAS_ACCION.REINTENTAR).toBe("Reintentar");
  });
});
