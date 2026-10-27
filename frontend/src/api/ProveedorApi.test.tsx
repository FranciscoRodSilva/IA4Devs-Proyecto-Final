import { render, renderHook, screen } from "@testing-library/react";
import { describe, expect, test, vi } from "vitest";
import { ProveedorApi, useApi } from "./ProveedorApi";
import { crearClienteApi } from "./cliente";

// F006 (deuda de TKT-008a): primera prueba del proveedor del cliente de API y de su hook.
function crearCliente() {
  return crearClienteApi({
    baseUrl: globalThis.location.origin,
    alTerminarSesion: vi.fn<() => void>(),
    alDenegarPermiso: vi.fn<() => void>(),
  });
}

describe("TKT-008 · ProveedorApi y useApi", () => {
  test("tkt008_f006 · useApi entrega el cliente que el proveedor recibió (TC-B2)", () => {
    const api = crearCliente();
    const otro = crearCliente();
    function Lector() {
      const recibido = useApi();
      return <p>{recibido === api ? "el mismo cliente" : recibido === otro ? "otro cliente" : "desconocido"}</p>;
    }

    render(
      <ProveedorApi api={api}>
        <Lector />
      </ProveedorApi>,
    );

    expect(screen.getByText("el mismo cliente")).toBeInTheDocument();
  });

  test("tkt008_f006 · useApi fuera de ProveedorApi lanza (TC-B3)", () => {
    // React escribe el error lanzado en la consola; la prueba lo espera y lo silencia.
    vi.spyOn(console, "error").mockImplementation(() => undefined);

    expect(() => renderHook(() => useApi())).toThrow("useApi fuera de ProveedorApi");
  });
});
