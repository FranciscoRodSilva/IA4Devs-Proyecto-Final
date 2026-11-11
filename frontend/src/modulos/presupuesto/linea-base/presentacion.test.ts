import { describe, expect, test } from "vitest";
import type { ErrorGenerico, ErrorPermiso, ErrorRed } from "@/api/errores";
import { errorNoEncontrado, errorPermiso } from "@/pruebas/cuerpos";
import { formatearFecha, mensajeDeRechazo } from "./presentacion";

// TKT-018a · A1 · TC-03 (CA-4, CA-9; D-8). El texto que la pantalla enseña ante un rechazo que no es un 409.
// El `mensaje` del 403 de estas pruebas es distinto, a propósito, del literal de `errorPermiso`
// («No tienes permiso para esta operación.»): con el mismo texto, una implementación que devolviera
// una frase fija en vez del mensaje del servidor pasaría la prueba (mutante M-10).

const MENSAJE_403 = "Tu rol no permite esta operación.";
const MENSAJE_403_CSRF = "No se pudo verificar el origen de la petición. Recarga la página e inténtalo de nuevo.";

function permiso(motivo: ErrorPermiso["motivo"], mensaje: string): ErrorPermiso {
  return { ...errorPermiso(motivo), mensaje };
}

describe("TKT-018a · mensajeDeRechazo", () => {
  test("tkt018a_ca04 · mensajeDeRechazo: el 403 muestra el mensaje del servidor con su referencia", () => {
    const error = permiso("ROL_INSUFICIENTE", MENSAJE_403);

    expect(mensajeDeRechazo(error)).toBe(`${MENSAJE_403} Referencia: ${error.correlacion_id}`);
  });

  test("tkt018a_ca04 · mensajeDeRechazo: el 403 de origen no verificado conserva la pista de recargar", () => {
    const error = permiso("ORIGEN_NO_VERIFICADO", MENSAJE_403_CSRF);

    expect(mensajeDeRechazo(error)).toBe(`${MENSAJE_403_CSRF} Referencia: ${error.correlacion_id}`);
    expect(mensajeDeRechazo(error)).toContain("Recarga la página");
  });

  test("tkt018a_ca04 · mensajeDeRechazo: el 404 muestra el mensaje del servidor tal cual", () => {
    const error = errorNoEncontrado("linea_base", "La línea base no existe.");

    expect(mensajeDeRechazo(error)).toBe("La línea base no existe.");
  });

  test("tkt018a_ca04 · mensajeDeRechazo: sin red dice que no hay conexión con el servidor", () => {
    const error: ErrorRed = { tipo: "RED" };

    expect(mensajeDeRechazo(error)).toBe("Sin conexión con el servidor.");
  });

  test("tkt018a_ca04 · mensajeDeRechazo: el error genérico con identificador muestra la referencia", () => {
    const error: ErrorGenerico = {
      tipo: "GENERICO",
      estado: 500,
      mensaje: "Traceback (most recent call last)",
      correlacion_id: "9c4e7a15-2b6d-4f83-a1c9-5d8e0f3b6a72",
    };

    expect(mensajeDeRechazo(error)).toBe(
      "No se pudo completar la operación. Referencia: 9c4e7a15-2b6d-4f83-a1c9-5d8e0f3b6a72",
    );
  });

  test("tkt018a_ca04 · mensajeDeRechazo: el error genérico sin identificador no inventa referencia", () => {
    const error: ErrorGenerico = { tipo: "GENERICO", estado: 502, mensaje: null, correlacion_id: null };

    expect(mensajeDeRechazo(error)).toBe("No se pudo completar la operación.");
  });
});

describe("TKT-018a · formatearFecha", () => {
  test("tkt018a_ca02 · formatearFecha: un instante ISO se pinta en formato medio de es-MX", () => {
    expect(formatearFecha("2026-10-15T12:00:00Z")).toBe("15 oct 2026");
  });

  test("tkt018a_ca02 · formatearFecha: una cadena que no es fecha devuelve null en vez de lanzar", () => {
    expect(formatearFecha("no-es-fecha")).toBeNull();
  });
});
