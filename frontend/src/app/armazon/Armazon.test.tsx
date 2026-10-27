import { act, screen, waitFor, within } from "@testing-library/react";
import { delay, http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { claves, type Rol, type UsuarioActual } from "@/api/sesion";
import { errorPermiso, errorSesion, tokenCsrf, usuarioActual } from "@/pruebas/cuerpos";
import { renderizarAplicacion } from "@/pruebas/render";
import { servidorPruebas } from "@/pruebas/servidor";

const ORIGEN = globalThis.location.origin;
const RUTA_SESION = "/api/v1/sesion";
const RUTA_CSRF = "/api/v1/sesion/csrf";
const RUTA_CIERRE = "/api/v1/sesion/cierre";
const INICIO_SESION = "/inicio-sesion";
const AVISO_SIN_SECCIONES = "No tienes secciones asignadas. Pide a un administrador que te asigne un rol.";
const AVISO_TERMINADA = "Tu sesión terminó. Vuelve a iniciarla.";

// Los tiempos se controlan con el reloj simulado que avanza solo: `usuario` de userEvent lo exige y ninguna prueba hace `sleep`.
beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
afterEach(() => {
  vi.useRealTimers();
});

function dobleSesion(roles: Rol[], cambios?: Partial<UsuarioActual>) {
  return http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(usuarioActual(roles, cambios)));
}

function dobleCsrf() {
  return http.get(`${ORIGEN}${RUTA_CSRF}`, () => HttpResponse.json(tokenCsrf()));
}

function menu() {
  return screen.getByRole("navigation", { name: "Secciones" });
}

describe("TKT-008 · aplicación y armazón", () => {
  test("tkt008_ca06_esc02 · ya hay sesión", async () => {
    servidorPruebas.use(dobleSesion(["COMPRAS"]));

    const { router } = renderizarAplicacion("/");

    expect(await screen.findByRole("heading", { level: 1, name: "Línea base" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/obra/linea-base");
    expect(screen.queryByLabelText("Contraseña")).not.toBeInTheDocument();
  });

  test("tkt008_ca07_esc01 · cabecera y menú", async () => {
    servidorPruebas.use(dobleSesion(["ALMACEN"]));

    renderizarAplicacion("/");

    expect(await screen.findByText(/Rosa Villanueva/)).toBeInTheDocument();
    // El rol aparece en la cabecera y, aparte, como encabezado del grupo «Almacén» del menú: aquí solo cuenta el primero.
    const rolesEnCabecera = screen.getAllByText(/Almacén/).filter((elemento) => elemento.closest("nav") === null);
    expect(rolesEnCabecera).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Salir" })).toBeInTheDocument();

    const enlaces = within(menu()).getAllByRole("link");
    expect(enlaces.map((enlace) => enlace.textContent)).toEqual([
      "Órdenes de compra",
      "Proveedores",
      "Recepción · Pendientes de recibir",
    ]);
  });

  test("tkt008_ca07_esc03 · ruta marcador", async () => {
    servidorPruebas.use(dobleSesion(["DIRECCION_GENERAL"]));
    const { router, usuario } = renderizarAplicacion("/");
    await screen.findByRole("heading", { level: 1, name: "Semáforo" });

    await usuario.click(within(menu()).getByRole("link", { name: "Bitácora de excepciones" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Bitácora de excepciones" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/direccion/bitacora");
    expect(screen.getByText("Esta sección aún no está disponible.")).toBeInTheDocument();
  });

  test("tkt008_ca07_esc04 · el menor vencimiento · gana la inactividad", async () => {
    servidorPruebas.use(
      dobleSesion(["COMPRAS"], {
        sesion: { expira_en: "2026-10-26T20:00:00-06:00", expira_por_inactividad_en: "2026-10-26T10:30:00-06:00" },
      }),
    );

    renderizarAplicacion("/");

    await screen.findByRole("button", { name: "Salir" });
    expect(screen.getByText(/Sesión vigente hasta/)).toBeInTheDocument();
    expect(document.querySelector("time")).toHaveAttribute("datetime", "2026-10-26T10:30:00-06:00");
  });

  test("tkt008_ca07_esc04 · el menor vencimiento · gana el absoluto", async () => {
    servidorPruebas.use(
      dobleSesion(["COMPRAS"], {
        sesion: { expira_en: "2026-10-26T10:30:00-06:00", expira_por_inactividad_en: "2026-10-26T20:00:00-06:00" },
      }),
    );

    renderizarAplicacion("/");

    await screen.findByRole("button", { name: "Salir" });
    expect(document.querySelector("time")).toHaveAttribute("datetime", "2026-10-26T10:30:00-06:00");
  });

  test("tkt008_ca07_esc05 · sección ajena por URL", async () => {
    servidorPruebas.use(dobleSesion(["ALMACEN"]));

    renderizarAplicacion("/direccion/autorizaciones");

    expect(await screen.findByRole("heading", { level: 1, name: "No tienes permiso para esta sección" })).toBeInTheDocument();
    expect(screen.queryByText("Esta sección aún no está disponible.")).not.toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("$");
    expect(within(menu()).queryByRole("link", { name: "Autorizaciones" })).not.toBeInTheDocument();
  });

  test("tkt008_ca07_esc06 · sin roles", async () => {
    servidorPruebas.use(dobleSesion([]));

    renderizarAplicacion("/");

    expect(await screen.findByText(AVISO_SIN_SECCIONES)).toBeInTheDocument();
    expect(screen.queryAllByRole("link")).toEqual([]);
    expect(screen.getByRole("button", { name: "Salir" })).toBeInTheDocument();
  });

  test("tkt008_ca07_esc07 · salir · cierre aceptado", async () => {
    const csrfRecibido: Array<string | null> = [];
    servidorPruebas.use(
      dobleSesion(["COMPRAS"]),
      dobleCsrf(),
      http.post(`${ORIGEN}${RUTA_CIERRE}`, ({ request }) => {
        csrfRecibido.push(request.headers.get("X-CSRF-Token"));
        return new HttpResponse(null, { status: 204 });
      }),
    );
    const { router, queryClient, usuario } = renderizarAplicacion("/");
    await screen.findByRole("heading", { level: 1, name: "Línea base" });

    await usuario.click(screen.getByRole("button", { name: "Salir" }));

    await waitFor(() => expect(router.state.location.pathname).toBe(INICIO_SESION));
    await waitFor(() => expect(queryClient.getQueryData(claves.sesion)).toBeUndefined());
    expect(csrfRecibido).toEqual([tokenCsrf().token]);
    expect(screen.queryByText(AVISO_TERMINADA)).not.toBeInTheDocument();
  });

  test("tkt008_ca07_esc07 · salir · el cierre responde 401 porque la sesión ya había terminado", async () => {
    servidorPruebas.use(
      dobleSesion(["COMPRAS"]),
      dobleCsrf(),
      http.post(`${ORIGEN}${RUTA_CIERRE}`, () => HttpResponse.json(errorSesion("SESION_CADUCADA"), { status: 401 })),
    );
    const { router, queryClient, usuario } = renderizarAplicacion("/");
    await screen.findByRole("heading", { level: 1, name: "Línea base" });

    await usuario.click(screen.getByRole("button", { name: "Salir" }));

    await waitFor(() => expect(router.state.location.pathname).toBe(INICIO_SESION));
    await waitFor(() => expect(queryClient.getQueryData(claves.sesion)).toBeUndefined());
    expect(screen.queryByText(AVISO_TERMINADA)).not.toBeInTheDocument();
  });

  test.each<[string, () => Response]>([
    ["TC-F201a · el cierre no llega al servidor (RED)", () => HttpResponse.error()],
    [
      "TC-F201b · el cierre responde 500",
      () => HttpResponse.json({ mensaje: "Error interno.", correlacion_id: "7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e" }, { status: 500 }),
    ],
  ])(
    "tkt008_ca07_esc07 · salir · %s · avisa, se queda en el armazón y conserva la sesión",
    async (_nombre, respuestaDelCierre) => {
      servidorPruebas.use(dobleSesion(["COMPRAS"]), dobleCsrf(), http.post(`${ORIGEN}${RUTA_CIERRE}`, respuestaDelCierre));
      const { router, queryClient, usuario } = renderizarAplicacion("/");
      await screen.findByRole("heading", { level: 1, name: "Línea base" });
      const rutaAntes = router.state.location.pathname;

      await usuario.click(screen.getByRole("button", { name: "Salir" }));

      const alerta = await screen.findByRole("alert");
      expect(alerta.textContent).toBe("No se pudo cerrar la sesión. Inténtalo de nuevo.");
      expect(router.state.location.pathname).toBe(rutaAntes);
      expect(router.state.location.pathname).not.toBe(INICIO_SESION);
      expect(queryClient.getQueryData(claves.sesion)).toBeDefined();
      expect(menu()).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Salir" })).toBeInTheDocument();
      expect(screen.queryByLabelText("Contraseña")).not.toBeInTheDocument();
    },
  );

  test("tkt008_ca07_esc08 · menú plegable", async () => {
    servidorPruebas.use(dobleSesion(["COMPRAS"]));
    const { usuario } = renderizarAplicacion("/");
    const boton = await screen.findByRole("button", { name: "Menú" });
    expect(boton).toHaveAttribute("aria-expanded", "false");
    expect(menu()).toHaveAttribute("data-abierto", "false");

    await usuario.click(boton);

    expect(boton).toHaveAttribute("aria-expanded", "true");
    expect(menu()).toHaveAttribute("data-abierto", "true");

    await usuario.click(within(menu()).getByRole("link", { name: "Requisiciones" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Requisiciones" })).toBeInTheDocument();
    expect(boton).toHaveAttribute("aria-expanded", "false");
    expect(menu()).toHaveAttribute("data-abierto", "false");
  });

  test("tkt008_ca01_esc03 · ruta que no existe", async () => {
    servidorPruebas.use(dobleSesion(["COMPRAS"]));

    renderizarAplicacion("/no-existe");

    expect(await screen.findByRole("heading", { level: 1, name: "Página no encontrada" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Salir" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir al inicio" })).toHaveAttribute("href", "/");
  });

  test("tkt008_ca05_esc04 · rol retirado", async () => {
    servidorPruebas.use(dobleSesion(["COMPRAS", "ALMACEN"]));
    const { api } = renderizarAplicacion("/");
    await screen.findByRole("link", { name: "Requisiciones" });

    servidorPruebas.use(
      dobleSesion(["ALMACEN"]),
      dobleCsrf(),
      http.post(`${ORIGEN}${RUTA_CIERRE}`, () => HttpResponse.json(errorPermiso("ROL_INSUFICIENTE"), { status: 403 })),
    );
    await act(async () => {
      await api.POST("/api/v1/sesion/cierre");
    });

    await waitFor(() => expect(screen.queryByRole("link", { name: "Requisiciones" })).not.toBeInTheDocument());
    expect(within(menu()).getByRole("link", { name: "Órdenes de compra" })).toBeInTheDocument();
  });

  test("tkt008_m10 · estados del armazón · cargando", async () => {
    servidorPruebas.use(http.get(`${ORIGEN}${RUTA_SESION}`, () => delay("infinite")));

    renderizarAplicacion("/");

    expect(screen.getByLabelText("Cargando la sesión")).toHaveAttribute("aria-busy", "true");
    expect(screen.queryByRole("button", { name: "Salir" })).not.toBeInTheDocument();
  });

  test("tkt008_m10 · estados del armazón · sin conexión y reintentar", async () => {
    servidorPruebas.use(http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.error()));
    const { usuario } = renderizarAplicacion("/");

    expect(await screen.findByText("No se pudo cargar la sesión.")).toBeInTheDocument();
    expect(screen.getByText("Sin conexión con el servidor.")).toBeInTheDocument();
    const reintentar = screen.getByRole("button", { name: "Reintentar" });

    servidorPruebas.use(dobleSesion(["COMPRAS"]));
    await usuario.click(reintentar);

    expect(await screen.findByRole("navigation", { name: "Secciones" })).toBeInTheDocument();
    expect(screen.queryByText("No se pudo cargar la sesión.")).not.toBeInTheDocument();
  });
});

// Casos que el plan no numera y que la fila 9 hereda o necesita (TC-B1 a TC-B5 viven en src/api y scripts).
describe("TKT-008 · armazón · errores que no son de red", () => {
  test("tkt008_m10 · error del servidor · reintentar sin decir «sin conexión» (TC-B6)", async () => {
    servidorPruebas.use(
      http.get(`${ORIGEN}${RUTA_SESION}`, () =>
        HttpResponse.json({ mensaje: "Error interno.", correlacion_id: "7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e" }, { status: 500 }),
      ),
    );

    renderizarAplicacion("/");

    expect(await screen.findByText("No se pudo cargar la sesión.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
    expect(screen.queryByText("Sin conexión con el servidor.")).not.toBeInTheDocument();
  });

  test("tkt008_m10 · error de sesión · el middleware lleva al inicio y no queda un error pintado (TC-B7)", async () => {
    servidorPruebas.use(
      http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(errorSesion("SIN_SESION"), { status: 401 })),
    );

    const { router } = renderizarAplicacion("/");

    await waitFor(() => expect(router.state.location.pathname).toBe(INICIO_SESION));
    expect(screen.queryByText("No se pudo cargar la sesión.")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reintentar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Salir" })).not.toBeInTheDocument();
  });
});

// Ciclo de corrección 1 de /sdd-revisar · TC-R302 (C102) y TC-R308, TC-R309 y TC-R311 (C106).
describe("TKT-008 · armazón · ciclo de corrección 1", () => {
  const formatoHora = new Intl.DateTimeFormat("es-MX", { hour: "2-digit", minute: "2-digit" });
  const horaVisible = (instante: string) => formatoHora.format(new Date(instante));

  // El instante que vence primero se decide por `Date.parse`, no por el orden de las cadenas: con desfases distintos
  // («Z» frente a «-06:00») el orden alfabético y el orden en el tiempo no coinciden.
  test.each<[string, { expira_en: string; expira_por_inactividad_en: string }, string]>([
    [
      "gana la inactividad",
      { expira_en: "2026-10-26T20:00:00-06:00", expira_por_inactividad_en: "2026-10-26T10:30:00-06:00" },
      "2026-10-26T10:30:00-06:00",
    ],
    [
      "gana el absoluto",
      { expira_en: "2026-10-26T10:30:00-06:00", expira_por_inactividad_en: "2026-10-26T20:00:00-06:00" },
      "2026-10-26T10:30:00-06:00",
    ],
    [
      "desfases mixtos · gana el absoluto (12:00Z antes que 16:00Z) aunque su cadena sea mayor",
      { expira_en: "2026-10-26T12:00:00Z", expira_por_inactividad_en: "2026-10-26T10:00:00-06:00" },
      "2026-10-26T12:00:00Z",
    ],
    [
      "desfases mixtos · gana la inactividad (12:00Z antes que 16:00Z) aunque su cadena sea mayor",
      { expira_en: "2026-10-26T10:00:00-06:00", expira_por_inactividad_en: "2026-10-26T12:00:00Z" },
      "2026-10-26T12:00:00Z",
    ],
  ])("tkt008_ca07_esc04 · el menor vencimiento · %s · el texto visible y `dateTime` son el mismo instante (TC-R302)", async (_nombre, sesion, vence) => {
    servidorPruebas.use(dobleSesion(["COMPRAS"], { sesion }));

    renderizarAplicacion("/");

    await screen.findByRole("button", { name: "Salir" });
    const hora = screen.getByText(/Sesión vigente hasta/).querySelector("time");
    expect(hora).not.toBeNull();
    expect(hora).toHaveAttribute("datetime", vence);
    expect(hora?.textContent).toBe(horaVisible(vence));
  });

  test("tkt008_m10 · estados del armazón · cargando es un estado anunciado (TC-R308)", () => {
    servidorPruebas.use(http.get(`${ORIGEN}${RUTA_SESION}`, () => delay("infinite")));

    renderizarAplicacion("/");

    const estado = screen.getByRole("status", { name: "Cargando la sesión" });
    expect(estado).toHaveAttribute("aria-busy", "true");
  });

  test.each<[string, () => Response, string[]]>([
    [
      "el servidor responde 500",
      () => HttpResponse.json({ mensaje: "Error interno.", correlacion_id: "7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e" }, { status: 500 }),
      ["No se pudo cargar la sesión."],
    ],
    ["no hay conexión", () => HttpResponse.error(), ["No se pudo cargar la sesión.", "Sin conexión con el servidor."]],
  ])("tkt008_m10 · estados del armazón · error · %s · se anuncia como alerta (TC-R309)", async (_nombre, respuesta, textos) => {
    servidorPruebas.use(http.get(`${ORIGEN}${RUTA_SESION}`, respuesta));

    renderizarAplicacion("/");

    const alerta = await screen.findByRole("alert");
    for (const texto of textos) expect(within(alerta).getByText(texto)).toBeInTheDocument();
  });

  // El foco puede estar en el botón «Menú» (lo acaba de pulsar) o dentro del menú abierto: Escape cierra en los dos casos.
  test.each<[string, (menuAbierto: HTMLElement) => void]>([
    ["con el foco en el botón «Menú»", () => undefined],
    [
      "con el foco en un enlace del menú",
      (menuAbierto) => {
        within(menuAbierto).getAllByRole("link")[0]?.focus();
      },
    ],
  ])("tkt008_ca07_esc08 · menú plegable · Escape lo cierra %s (TC-R311)", async (_nombre, colocarFoco) => {
    servidorPruebas.use(dobleSesion(["COMPRAS"]));
    const { usuario } = renderizarAplicacion("/");
    const boton = await screen.findByRole("button", { name: "Menú" });
    await usuario.click(boton);
    expect(boton).toHaveAttribute("aria-expanded", "true");
    act(() => colocarFoco(menu()));

    await usuario.keyboard("{Escape}");

    expect(boton).toHaveAttribute("aria-expanded", "false");
    expect(menu()).toHaveAttribute("data-abierto", "false");
    expect(boton).toHaveFocus();
  });
});
