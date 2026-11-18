import { screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import type { components as Servidor } from "@/api/generado/servidor";
import type { Rol } from "@/api/sesion";
import { errorSesion, tokenCsrf, usuarioActual } from "@/pruebas/cuerpos";
import { renderizarAplicacion } from "@/pruebas/render";
import { servidorPruebas } from "@/pruebas/servidor";

// TKT-032a · fila F5 · TC-F17 (CA-R1, CA-9) · REGRESIÓN. `/compras/proveedores` conserva la guarda de sección, la entrada de
// menú «Proveedores» y su título de TKT-008b al cambiar el marcador por la pantalla del catálogo.
// Estas pruebas NACEN EN VERDE a propósito: el marcador de hoy ya cumple lo que aquí se fija, y la fila no puede romperlo.
// No son un rojo falso: protegen lo que ya funciona. Lo que la pantalla añade lo prueban las de `PantallaProveedores.test.tsx`.

type Esquemas = Servidor["schemas"];

const ORIGEN = globalThis.location.origin;
const RUTA_SESION = "/api/v1/sesion";
const RUTA_CSRF = "/api/v1/sesion/csrf";
const RUTA_LISTA = "/api/v1/proveedores";
const RUTA_OBRAS = "/api/v1/obras";
const RUTA_PANTALLA = "/compras/proveedores";
const INICIO_SESION = "/inicio-sesion";

const TODOS_LOS_ROLES: Rol[] = ["DIRECCION_GENERAL", "DIRECTOR_PROYECTOS", "RESIDENTE", "COMPRAS", "ALMACEN", "ADMINISTRACION"];

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
afterEach(() => {
  vi.useRealTimers();
});

function dobleSesion(roles: Rol[]) {
  return http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(usuarioActual(roles)));
}

function dobleCsrf() {
  return http.get(`${ORIGEN}${RUTA_CSRF}`, () => HttpResponse.json(tokenCsrf()));
}

/** GET /proveedores sin ningún proveedor; anota cada petición para comprobar que la guarda no deja llegar a la pantalla. */
function dobleListaVacia() {
  const pedidas: URL[] = [];
  const handler = http.get(`${ORIGEN}${RUTA_LISTA}`, ({ request }) => {
    pedidas.push(new URL(request.url));
    return HttpResponse.json({
      elementos: [],
      paginacion: { pagina: 1, tamano_pagina: 50, total: 0 },
    } satisfies Esquemas["ListaProveedores"]);
  });
  return { handler, pedidas };
}

function dobleObrasVacias() {
  return http.get(`${ORIGEN}${RUTA_OBRAS}`, () =>
    HttpResponse.json({
      elementos: [],
      paginacion: { pagina: 1, tamano_pagina: 200, total: 0 },
    } satisfies Esquemas["ListaObras"]),
  );
}

function menu() {
  return screen.getByRole("navigation", { name: "Secciones" });
}

describe("TKT-032a · TC-F17 · la ruta de proveedores conserva su guarda, su menú y su título (CA-R1)", () => {
  test("tkt032a_car1 · TC-F17 · una sesión sin la sección ve «No tienes permiso para esta sección», sin la pantalla y sin pedir la lista", async () => {
    // El catálogo de secciones da «Proveedores» a los seis roles: solo una sesión sin ningún rol queda fuera de ella.
    const lista = dobleListaVacia();
    servidorPruebas.use(dobleSesion([]), dobleCsrf(), lista.handler);

    renderizarAplicacion(RUTA_PANTALLA);

    expect(await screen.findByRole("heading", { level: 1, name: "No tienes permiso para esta sección" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1, name: "Proveedores" })).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Dar de alta un proveedor" })).not.toBeInTheDocument();
    expect(within(menu()).queryByRole("link", { name: "Proveedores" })).not.toBeInTheDocument();
    // La guarda impide que la pantalla se monte: nadie le pidió la lista al servidor.
    expect(lista.pedidas).toHaveLength(0);
  });

  test.each(TODOS_LOS_ROLES)("tkt032a_car1 · TC-F17 · %s tiene la entrada «Proveedores» en el grupo «Compras» del menú y su título es «Proveedores»", async (rol) => {
    servidorPruebas.use(dobleSesion([rol]), dobleCsrf(), dobleListaVacia().handler);

    renderizarAplicacion(RUTA_PANTALLA);

    expect(await screen.findByRole("heading", { level: 1, name: "Proveedores" })).toBeInTheDocument();
    const entrada = within(menu()).getByRole("link", { name: "Proveedores" });
    expect(entrada).toHaveAttribute("href", RUTA_PANTALLA);
    expect(entrada).toHaveAttribute("aria-current", "page");
    expect(within(menu()).getByRole("heading", { level: 2, name: "Compras" })).toBeInTheDocument();
  });

  test("tkt032a_car1 · TC-F17 · la entrada «Proveedores» del menú lleva a la ruta y a su título desde otra sección", async () => {
    servidorPruebas.use(dobleSesion(["ALMACEN"]), dobleCsrf(), dobleObrasVacias(), dobleListaVacia().handler);
    const { router, usuario } = renderizarAplicacion("/obras");
    await screen.findByRole("heading", { level: 1, name: "Obras" });

    await usuario.click(within(menu()).getByRole("link", { name: "Proveedores" }));

    await waitFor(() => expect(router.state.location.pathname).toBe(RUTA_PANTALLA));
    expect(await screen.findByRole("heading", { level: 1, name: "Proveedores" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 1, name: "Obras" })).not.toBeInTheDocument();
  });

  test("tkt032a_car1 · TC-F17 · sin sesión la ruta redirige al inicio de sesión, sin pantalla y sin pedir la lista", async () => {
    const lista = dobleListaVacia();
    servidorPruebas.use(
      http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(errorSesion("SIN_SESION"), { status: 401 })),
      lista.handler,
    );

    const { router } = renderizarAplicacion(RUTA_PANTALLA);

    await waitFor(() => expect(router.state.location.pathname).toBe(INICIO_SESION));
    expect(screen.queryByRole("heading", { level: 1, name: "Proveedores" })).not.toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(lista.pedidas).toHaveLength(0);
  });
});
