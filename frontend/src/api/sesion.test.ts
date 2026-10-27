import { QueryClient } from "@tanstack/react-query";
import { http, HttpResponse } from "msw";
import { describe, expect, test, vi } from "vitest";
import { errorSesion, usuarioActual } from "@/pruebas/cuerpos";
import { servidorPruebas } from "@/pruebas/servidor";
import { FalloApi, crearClienteApi } from "./cliente";
import { claves, sesionOptions } from "./sesion";

const ORIGEN = globalThis.location.origin;
const RUTA_SESION = `${ORIGEN}/api/v1/sesion`;

// F006 (deuda de TKT-008a): primera prueba de `sesionOptions`, que hasta ahora solo ejercitaban las pantallas.
function crearCliente() {
  return crearClienteApi({ baseUrl: ORIGEN, alTerminarSesion: vi.fn<() => void>(), alDenegarPermiso: vi.fn<() => void>() });
}

async function fallo(promesa: Promise<unknown>): Promise<unknown> {
  return promesa.then(
    () => null,
    (error: unknown) => error,
  );
}

describe("TKT-008 · sesionOptions", () => {
  test("tkt008_f006 · una respuesta 200 entrega al usuario y lo guarda bajo claves.sesion (TC-B1)", async () => {
    servidorPruebas.use(http.get(RUTA_SESION, () => HttpResponse.json(usuarioActual(["COMPRAS"]))));
    const queryClient = new QueryClient();

    const usuario = await queryClient.fetchQuery(sesionOptions(crearCliente()));

    expect(usuario).toEqual(usuarioActual(["COMPRAS"]));
    expect(queryClient.getQueryData(claves.sesion)).toEqual(usuarioActual(["COMPRAS"]));
  });

  test("tkt008_f006 · un error del servidor se convierte en FalloApi con su error (TC-B1)", async () => {
    servidorPruebas.use(http.get(RUTA_SESION, () => HttpResponse.json(errorSesion("SESION_CADUCADA"), { status: 401 })));

    const resultado = await fallo(new QueryClient().fetchQuery(sesionOptions(crearCliente())));

    expect(resultado).toBeInstanceOf(FalloApi);
    expect(resultado).toMatchObject({ error: { tipo: "SESION", motivo: "SESION_CADUCADA" } });
  });

  test("tkt008_f006 · un fallo de red se convierte en FalloApi de tipo RED (TC-B1)", async () => {
    servidorPruebas.use(http.get(RUTA_SESION, () => HttpResponse.error()));

    const resultado = await fallo(new QueryClient().fetchQuery(sesionOptions(crearCliente())));

    expect(resultado).toBeInstanceOf(FalloApi);
    expect(resultado).toMatchObject({ error: { tipo: "RED" } });
  });
});
