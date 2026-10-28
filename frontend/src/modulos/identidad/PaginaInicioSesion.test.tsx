import { act, screen, waitFor, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { Client } from "openapi-fetch";
import { afterEach, beforeEach, describe, expect, it, test, vi } from "vitest";
import { pedir } from "@/api/cliente";
import type { paths } from "@/api/generado/servidor";
import { claves, type Rol } from "@/api/sesion";
import { errorLimiteIntentos, errorPermiso, errorSesion, errorValidacion, tokenCsrf, usuarioActual } from "@/pruebas/cuerpos";
import { renderizarAplicacion } from "@/pruebas/render";
import { servidorPruebas } from "@/pruebas/servidor";

const ORIGEN = globalThis.location.origin;
const RUTA_SESION = "/api/v1/sesion";
const RUTA_CSRF = "/api/v1/sesion/csrf";
const INICIO_SESION = "/inicio-sesion";
const AVISO_TERMINADA = "Tu sesión terminó. Vuelve a iniciarla.";
const SIN_CONEXION = "Sin conexión. Para iniciar sesión hace falta conexión con el servidor.";
const ORIGEN_NO_VERIFICADO = "No se pudo verificar el origen de la petición. Recarga la página para continuar.";
const CORREO = "rosa@cimenta.test";
const CONTRASENA = "una-contrasena-larga";

// Los tiempos se controlan con el reloj simulado que avanza solo: `usuario` de userEvent lo exige y ninguna prueba hace `sleep`.
beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
});
afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  servidorPruebas.events.removeAllListeners();
});

/** Anota «MÉTODO /ruta» de cada petición que sale hacia el doble del servidor, en el orden en que salen. */
function registrarPeticiones(): string[] {
  const registro: string[] = [];
  servidorPruebas.events.on("request:start", ({ request }) => {
    registro.push(`${request.method} ${new URL(request.url).pathname}`);
  });
  return registro;
}

function dobleSesion(roles: Rol[]) {
  return http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(usuarioActual(roles)));
}

function dobleCsrf() {
  return http.get(`${ORIGEN}${RUTA_CSRF}`, () => HttpResponse.json(tokenCsrf()));
}

function dobleInicio(respuesta: () => Response | Promise<Response>) {
  return http.post(`${ORIGEN}${RUTA_SESION}`, respuesta);
}

type Usuario = ReturnType<typeof renderizarAplicacion>["usuario"];

async function escribirCredenciales(usuario: Usuario, correo = CORREO, contrasena = CONTRASENA) {
  const campoCorreo = await screen.findByLabelText("Correo");
  const campoContrasena = screen.getByLabelText("Contraseña");
  if (correo !== "") await usuario.type(campoCorreo, correo);
  if (contrasena !== "") await usuario.type(campoContrasena, contrasena);
}

function botonIniciar() {
  return screen.getByRole("button", { name: /^Iniciar sesión/ });
}

/** El texto de los elementos que el campo señala con `aria-errormessage` o `aria-describedby`: el mensaje «junto al campo». */
function mensajeDelCampo(campo: HTMLElement): string {
  const ids = [campo.getAttribute("aria-errormessage"), campo.getAttribute("aria-describedby")]
    .filter((valor): valor is string => valor !== null)
    .flatMap((valor) => valor.split(/\s+/));
  return ids.map((id) => document.getElementById(id)?.textContent ?? "").join(" ");
}

describe("TKT-008 · inicio de sesión", () => {
  it("tkt008c_marca · el inicio de sesión muestra el logo de AP Buildings", async () => {
    renderizarAplicacion(INICIO_SESION);

    expect(await screen.findByRole("img", { name: "AP Buildings" })).toBeInTheDocument();
  });

  test("tkt008_ca06_esc01 · iniciar sesión · el botón se deshabilita en vuelo y luego entra a la primera sección (TC-57)", async () => {
    const registro = registrarPeticiones();
    let liberar: () => void = () => undefined;
    const respuestaDelServidor = new Promise<void>((resolver) => {
      liberar = resolver;
    });
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(async () => {
        await respuestaDelServidor;
        return HttpResponse.json(usuarioActual(["COMPRAS"]));
      }),
      dobleSesion(["COMPRAS"]),
    );
    const { router, usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);
    const boton = botonIniciar();
    expect(boton).toBeEnabled();

    await usuario.click(boton);

    await waitFor(() => expect(boton).toBeDisabled());
    expect(router.state.location.pathname).toBe(INICIO_SESION);

    liberar();

    expect(await screen.findByRole("heading", { level: 1, name: "Línea base" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/obra/linea-base");
    expect(registro).toEqual([`GET ${RUTA_CSRF}`, `POST ${RUTA_SESION}`, `GET ${RUTA_SESION}`]);
  });

  test("tkt008_ca06_esc01 · iniciar sesión · la primera sección sale de los roles de la sesión recibida (TC-57)", async () => {
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() => HttpResponse.json(usuarioActual(["ALMACEN"]))),
      dobleSesion(["ALMACEN"]),
    );
    const { router, usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    expect(await screen.findByRole("heading", { level: 1, name: "Órdenes de compra" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/compras/ordenes-compra");
  });

  test("tkt008_ca06_esc03 · credenciales incorrectas · mensaje único, contraseña vacía y correo conservado (TC-58)", async () => {
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() => HttpResponse.json(errorSesion("CREDENCIALES_INVALIDAS"), { status: 401 })),
    );
    const { router, usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toBe("Correo o contraseña incorrectos.");
    expect(screen.getAllByRole("alert")).toHaveLength(1);
    expect(screen.getByLabelText("Contraseña")).toHaveValue("");
    expect(screen.getByLabelText("Correo")).toHaveValue(CORREO);
    expect(router.state.location.pathname).toBe(INICIO_SESION);
    expect(screen.queryByText(AVISO_TERMINADA)).not.toBeInTheDocument();
    expect(botonIniciar()).toBeEnabled();
  });

  test("tkt008_ca06_esc04 · forma inválida · un correo sin dominio se marca junto al campo y no se envía nada (TC-59)", async () => {
    const registro = registrarPeticiones();
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario, "x@", CONTRASENA);

    await usuario.click(botonIniciar());

    expect(await screen.findByText("Escribe un correo válido.")).toBeInTheDocument();
    const campo = screen.getByLabelText("Correo");
    expect(campo).toHaveAttribute("aria-invalid", "true");
    expect(mensajeDelCampo(campo)).toContain("Escribe un correo válido.");
    expect(screen.queryByText("Escribe tu contraseña.")).not.toBeInTheDocument();
    expect(registro).toEqual([]);
  });

  test("tkt008_ca06_esc04 · forma inválida · una contraseña vacía se marca junto al campo y no se envía nada (TC-59)", async () => {
    const registro = registrarPeticiones();
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario, CORREO, "");

    await usuario.click(botonIniciar());

    expect(await screen.findByText("Escribe tu contraseña.")).toBeInTheDocument();
    const campo = screen.getByLabelText("Contraseña");
    expect(campo).toHaveAttribute("aria-invalid", "true");
    expect(mensajeDelCampo(campo)).toContain("Escribe tu contraseña.");
    expect(screen.queryByText("Escribe un correo válido.")).not.toBeInTheDocument();
    expect(registro).toEqual([]);
  });

  test("tkt008_ca06_esc04 · forma inválida · el 422 del servidor se pinta junto al campo que nombra (TC-59)", async () => {
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() =>
        HttpResponse.json(
          errorValidacion([
            { campo: "email", codigo: "FORMATO", mensaje: "El servidor no acepta este correo." },
            { campo: "contrasena", codigo: "DEMASIADO_LARGO", mensaje: "El servidor no acepta una contraseña tan larga." },
          ]),
          { status: 422 },
        ),
      ),
    );
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    expect(await screen.findByText("El servidor no acepta este correo.")).toBeInTheDocument();
    const campoCorreo = screen.getByLabelText("Correo");
    const campoContrasena = screen.getByLabelText("Contraseña");
    expect(mensajeDelCampo(campoCorreo)).toContain("El servidor no acepta este correo.");
    expect(mensajeDelCampo(campoCorreo)).not.toContain("contraseña tan larga");
    expect(mensajeDelCampo(campoContrasena)).toContain("El servidor no acepta una contraseña tan larga.");
    expect(mensajeDelCampo(campoContrasena)).not.toContain("este correo");
  });

  test("tkt008_ca06_esc04 · forma inválida · el error del 422 que no nombra un campo del formulario va al mensaje general (TC-59)", async () => {
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() =>
        HttpResponse.json(
          errorValidacion([{ campo: "cabecera.origen", codigo: "OBLIGATORIO", mensaje: "Falta el origen." }]),
          { status: 422 },
        ),
      ),
    );
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    const alerta = await screen.findByRole("alert");
    expect(within(alerta).getByText(/Falta el origen\./)).toBeInTheDocument();
    expect(mensajeDelCampo(screen.getByLabelText("Correo"))).not.toContain("Falta el origen.");
    expect(mensajeDelCampo(screen.getByLabelText("Contraseña"))).not.toContain("Falta el origen.");
  });

  test("tkt008_ca06_esc05 · demasiados intentos · el mensaje dice cuánto falta y la cuenta atrás rehabilita el botón (TC-60)", async () => {
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() => HttpResponse.json(errorLimiteIntentos(900), { status: 429 })),
    );
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    expect(await screen.findByText("Demasiados intentos fallidos. Vuelve a intentarlo en 15 minutos.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Iniciar sesión (15:00)" })).toBeDisabled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(899_000);
    });
    expect(screen.getByRole("button", { name: "Iniciar sesión (00:01)" })).toBeDisabled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });
    expect(screen.getByRole("button", { name: "Iniciar sesión" })).toBeEnabled();
  });

  test("tkt008_ca06_esc05 · demasiados intentos · al llegar la cuenta atrás a cero el botón se rehabilita y el mensaje de espera desaparece (TC-F207)", async () => {
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() => HttpResponse.json(errorLimiteIntentos(60), { status: 429 })),
    );
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    expect(await screen.findByText(/Vuelve a intentarlo en/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Iniciar sesión (01:00)" })).toBeDisabled();

    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });

    expect(screen.getByRole("button", { name: "Iniciar sesión" })).toBeEnabled();
    expect(screen.queryByText(/Vuelve a intentarlo en/)).not.toBeInTheDocument();
  });

  test.each([
    [1, "1 segundo"],
    [45, "45 segundos"],
    [60, "1 minuto"],
    [61, "2 minutos"],
  ])(
    "tkt008_ca06_esc05 · demasiados intentos · la espera de %i s se dice como «%s» (TC-60)",
    async (segundos, espera) => {
      servidorPruebas.use(
        dobleCsrf(),
        dobleInicio(() => HttpResponse.json(errorLimiteIntentos(segundos), { status: 429 })),
      );
      const { usuario } = renderizarAplicacion(INICIO_SESION);
      await escribirCredenciales(usuario);

      await usuario.click(botonIniciar());

      expect(await screen.findByText(`Demasiados intentos fallidos. Vuelve a intentarlo en ${espera}.`)).toBeInTheDocument();
    },
  );

  test("tkt008_ca06_esc06 · sin conexión · el botón se deshabilita con su explicación y no se envía nada (TC-61)", async () => {
    const registro = registrarPeticiones();
    const enLinea = vi.spyOn(globalThis.navigator, "onLine", "get").mockReturnValue(false);
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);

    expect(screen.getByText(SIN_CONEXION)).toBeInTheDocument();
    const boton = botonIniciar();
    expect(boton).toBeDisabled();
    await usuario.click(boton);
    expect(registro).toEqual([]);

    await act(async () => {
      enLinea.mockReturnValue(true);
      globalThis.dispatchEvent(new Event("online"));
    });

    expect(botonIniciar()).toBeEnabled();
    expect(screen.queryByText(SIN_CONEXION)).not.toBeInTheDocument();
  });

  test("tkt008_ca06_esc07 · origen no verificado · pide recargar y no reintenta (TC-62)", async () => {
    const registro = registrarPeticiones();
    const recargar = vi.fn();
    // `location.reload` no se puede espiar en jsdom (propiedad no redefinible): se sustituye `location` entera.
    vi.stubGlobal("location", { ...globalThis.location, origin: ORIGEN, reload: recargar });
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() => HttpResponse.json(errorPermiso("ORIGEN_NO_VERIFICADO"), { status: 403 })),
    );
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    expect(await screen.findByText(ORIGEN_NO_VERIFICADO)).toBeInTheDocument();
    // Un reintento saldría en cuanto se pinta el mensaje: se vacían las promesas pendientes con el reloj simulado, no con una espera real.
    await act(async () => {
      await vi.advanceTimersByTimeAsync(100);
    });
    expect(registro.filter((peticion) => peticion === `POST ${RUTA_SESION}`)).toHaveLength(1);
    expect(recargar).not.toHaveBeenCalled();

    await usuario.click(screen.getByRole("button", { name: "Recargar" }));

    expect(recargar).toHaveBeenCalledTimes(1);
    expect(registro.filter((peticion) => peticion === `POST ${RUTA_SESION}`)).toHaveLength(1);
  });
});

describe("TKT-008 · inicio de sesión · sesión terminada", () => {
  test.each<[string, "SESION_CADUCADA" | "SESION_REVOCADA"]>([
    ["caducada", "SESION_CADUCADA"],
    ["revocada", "SESION_REVOCADA"],
  ])("tkt008_ca05_esc01 · sesión terminada · %s dentro del armazón lleva al inicio con el aviso y la caché vacía (TC-63)", async (_nombre, motivo) => {
    servidorPruebas.use(dobleSesion(["COMPRAS"]));
    const { router, queryClient } = renderizarAplicacion("/");
    await screen.findByRole("heading", { level: 1, name: "Línea base" });

    servidorPruebas.use(http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(errorSesion(motivo), { status: 401 })));
    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: claves.sesion });
    });

    await waitFor(() => expect(router.state.location.pathname).toBe(INICIO_SESION));
    expect(await screen.findByText(AVISO_TERMINADA)).toBeInTheDocument();
    expect(await screen.findByLabelText("Correo")).toBeInTheDocument();
    expect(queryClient.getQueryData(claves.sesion)).toBeUndefined();
  });

  test("tkt008_ca05_esc02 · primera visita sin aviso · el 401 sin usuario previo muestra el inicio sin «Tu sesión terminó» (TC-64)", async () => {
    servidorPruebas.use(
      http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(errorSesion("SIN_SESION"), { status: 401 })),
    );

    const { router } = renderizarAplicacion("/");

    await waitFor(() => expect(router.state.location.pathname).toBe(INICIO_SESION));
    expect(await screen.findByLabelText("Correo")).toBeInTheDocument();
    expect(screen.getByLabelText("Contraseña")).toBeInTheDocument();
    expect(screen.queryByText(AVISO_TERMINADA)).not.toBeInTheDocument();
  });
});

// Casos que el plan no numera: la condición O-6 heredada de TKT-008a y las dos filas «RED» y «Cualquier otro» de la tabla de comportamiento.
describe("TKT-008 · inicio de sesión · fallos fuera del contrato", () => {
  test("tkt008_ca04 · un fallo genérico con estado 0 no se pinta como código HTTP (TC-B8)", async () => {
    // Un 200 con cuerpo que no es JSON hace que openapi-fetch lance al leerlo: `pedir` lo entrega como GENERICO con `estado: 0`.
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(
        () => new HttpResponse("<html>no es JSON</html>", { status: 200, headers: { "Content-Type": "application/json" } }),
      ),
    );
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toBe("No se pudo iniciar sesión.");
    expect(document.body.textContent).not.toMatch(/Error\s*0/i);
    expect(document.body.textContent).not.toMatch(/\b0\b/);
  });

  test("tkt008_ca04 · un fallo genérico con correlación la muestra como referencia (TC-B9)", async () => {
    const correlacion = "9c1d2e3f-4a5b-4c6d-8e7f-0a1b2c3d4e5f";
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() => HttpResponse.json({ mensaje: "Error interno.", correlacion_id: correlacion }, { status: 500 })),
    );
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toBe(`No se pudo iniciar sesión. Referencia: ${correlacion}`);
    expect(alerta.textContent).not.toMatch(/500/);
  });

  test("tkt008_ca04 · sin red se dice que no se pudo conectar y se puede volver a intentar (TC-B10)", async () => {
    servidorPruebas.use(dobleCsrf(), dobleInicio(() => HttpResponse.error()));
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toBe("No se pudo conectar con el servidor. Inténtalo de nuevo.");
    expect(botonIniciar()).toBeEnabled();
    expect(screen.getByLabelText("Correo")).toHaveValue(CORREO);
  });
});

// Ciclo de corrección 1 de /sdd-revisar. Los TC-R301 a TC-R304 y TC-R313 a TC-R315 nacen en verde y los mata un mutante (impl.md);
// TC-R305, TC-R306, TC-R307, TC-R310 y TC-R312 nacen en rojo porque la corrección cambia el código.
const RUTA_MUTACION = "/api/v1/requisiciones";
const CORRELACION_500 = "9c1d2e3f-4a5b-4c6d-8e7f-0a1b2c3d4e5f";

// Una mutación que no es de sesión: el borrador de TKT-008 solo publica rutas de sesión, así que la prueba declara la suya.
interface RutaDePrueba {
  parameters: { query?: never; header?: never; path?: never; cookie?: never };
  get?: never;
  put?: never;
  delete?: never;
  options?: never;
  head?: never;
  patch?: never;
  trace?: never;
  post: {
    parameters: { query?: never; header?: never; path?: never; cookie?: never };
    requestBody?: never;
    responses: { 200: { headers: Record<string, unknown>; content: { "application/json": { id: string } } } };
  };
}
type ClienteConMutacion = Client<paths & { [RUTA_MUTACION]: RutaDePrueba }>;

describe("TKT-008 · inicio de sesión · ciclo de corrección 1", () => {
  test("tkt008_ca06_esc05 · dos bloqueos seguidos de igual duración · la segunda cuenta atrás vuelve a empezar (TC-R301)", async () => {
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() => HttpResponse.json(errorLimiteIntentos(60), { status: 429 })),
    );
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);
    await usuario.click(botonIniciar());
    expect(await screen.findByRole("button", { name: "Iniciar sesión (01:00)" })).toBeDisabled();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(60_000);
    });
    expect(botonIniciar()).toBeEnabled();
    expect(botonIniciar()).toHaveAccessibleName("Iniciar sesión");

    await usuario.click(botonIniciar());

    expect(await screen.findByRole("button", { name: "Iniciar sesión (01:00)" })).toBeDisabled();
  });

  test("tkt008_ca06_esc01 · la lectura posterior de la sesión falla · mensaje genérico con su referencia y se sigue en el inicio (TC-R303)", async () => {
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() => HttpResponse.json(usuarioActual(["COMPRAS"]))),
      http.get(`${ORIGEN}${RUTA_SESION}`, () =>
        HttpResponse.json({ mensaje: "Error interno.", correlacion_id: CORRELACION_500 }, { status: 500 }),
      ),
    );
    const { router, usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toBe(`No se pudo iniciar sesión. Referencia: ${CORRELACION_500}`);
    expect(router.state.location.pathname).toBe(INICIO_SESION);
    expect(botonIniciar()).toBeEnabled();
    expect(screen.getByLabelText("Correo")).toHaveValue(CORREO);
  });

  test("tkt008_ca06_esc01 · iniciar sesión · la entrada del inicio de sesión se reemplaza y no se apila (TC-R304)", async () => {
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() => HttpResponse.json(usuarioActual(["COMPRAS"]))),
      dobleSesion(["COMPRAS"]),
    );
    const { router, usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    expect(await screen.findByRole("heading", { level: 1, name: "Línea base" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/obra/linea-base");
    expect(router.state.historyAction).toBe("REPLACE");
  });

  test("tkt008_ca06_esc01 · iniciar sesión · con otra persona en la caché, entra a la primera sección de la nueva y no queda nada de la anterior (TC-R305)", async () => {
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() => HttpResponse.json(usuarioActual(["COMPRAS"]))),
      dobleSesion(["COMPRAS"]),
    );
    const { router, queryClient, usuario } = renderizarAplicacion(INICIO_SESION);
    // La persona anterior dejó su sesión y un dato de su trabajo en la caché de esta pestaña.
    queryClient.setQueryData(claves.sesion, usuarioActual(["ALMACEN"]));
    queryClient.setQueryData(["obra", "obra-anterior", "semaforo"], { dato: "de la persona anterior" });
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    expect(await screen.findByRole("heading", { level: 1, name: "Línea base" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/obra/linea-base");
    expect(queryClient.getQueryData(claves.sesion)).toMatchObject({ roles: ["COMPRAS"] });
    expect(queryClient.getQueryData(["obra", "obra-anterior", "semaforo"])).toBeUndefined();
    expect(queryClient.getQueryCache().getAll().map((consulta) => consulta.queryKey)).toEqual([claves.sesion]);
  });

  test("tkt008_ca06_esc05 · reintentar_en_s en cero · no hay espera: sin «0 segundos», sin cuenta atrás y con el botón habilitado (TC-R306)", async () => {
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() => HttpResponse.json(errorLimiteIntentos(0), { status: 429 })),
    );
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toMatch(/Demasiados intentos/);
    expect(alerta.textContent).not.toMatch(/\b0\b|segundo/);
    expect(document.body.textContent).not.toMatch(/\d\d:\d\d/);
    expect(botonIniciar()).toBeEnabled();
    expect(botonIniciar()).toHaveAccessibleName("Iniciar sesión");
  });

  // `vi.setSystemTime` mueve `Date.now()` sin disparar ningún temporizador: es lo que ve una pestaña dormida
  // (los intervalos se retrasan, el reloj no). Después, un solo tick de un segundo. Una cuenta que resta de uno en uno dice 00:59;
  // una que compara con el reloj dice que ya venció. La corrección debe leer `Date.now()`: el reloj de `performance` no se mueve con `setSystemTime`.
  test("tkt008_ca06_esc05 · la cuenta atrás sigue al reloj y no al número de ticks (TC-R307)", async () => {
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() => HttpResponse.json(errorLimiteIntentos(60), { status: 429 })),
    );
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);
    await usuario.click(botonIniciar());
    expect(await screen.findByRole("button", { name: "Iniciar sesión (01:00)" })).toBeDisabled();

    await act(async () => {
      vi.setSystemTime(Date.now() + 60_000);
      await vi.advanceTimersByTimeAsync(1_000);
    });

    expect(botonIniciar()).toBeEnabled();
    expect(botonIniciar()).toHaveAccessibleName("Iniciar sesión");
  });

  test.each<[string, string, string]>([
    ["el correo", "email", "Correo"],
    ["la contraseña", "contrasena", "Contraseña"],
  ])("tkt008_ca06_esc04 · forma inválida · el 422 que nombra %s pone el foco en ese campo (TC-R310)", async (_nombre, campo, etiqueta) => {
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() =>
        HttpResponse.json(errorValidacion([{ campo, codigo: "FORMATO", mensaje: "El servidor no acepta este valor." }]), { status: 422 }),
      ),
    );
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    expect(await screen.findByText("El servidor no acepta este valor.")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByLabelText(etiqueta)).toHaveFocus());
  });

  // S101 · un 401 de una petición que no es de sesión termina la sesión; el token CSRF de esa sesión no sirve a la siguiente.
  test("tkt008_ca05_esc01 · sesión terminada · el siguiente inicio de sesión pide un token CSRF nuevo (TC-R312)", async () => {
    let emitidos = 0;
    const tokensEnviados: Array<string | null> = [];
    servidorPruebas.use(
      dobleSesion(["COMPRAS"]),
      http.get(`${ORIGEN}${RUTA_CSRF}`, () => {
        emitidos += 1;
        return HttpResponse.json(tokenCsrf(`token-${emitidos}`));
      }),
      http.post(`${ORIGEN}${RUTA_MUTACION}`, () => HttpResponse.json({ id: "x" })),
      http.post(`${ORIGEN}${RUTA_SESION}`, ({ request }) => {
        tokensEnviados.push(request.headers.get("X-CSRF-Token"));
        return HttpResponse.json(errorSesion("CREDENCIALES_INVALIDAS"), { status: 401 });
      }),
    );
    const { router, queryClient, api, usuario } = renderizarAplicacion("/");
    await screen.findByRole("heading", { level: 1, name: "Línea base" });
    // Una mutación cualquiera deja el token de la sesión viva en el cliente (GET csrf número 1).
    const mutacion = await pedir(() => (api as unknown as ClienteConMutacion).POST(RUTA_MUTACION));
    expect(mutacion.ok).toBe(true);
    expect(emitidos).toBe(1);

    servidorPruebas.use(http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(errorSesion("SESION_CADUCADA"), { status: 401 })));
    await act(async () => {
      await queryClient.invalidateQueries({ queryKey: claves.sesion });
    });
    await waitFor(() => expect(router.state.location.pathname).toBe(INICIO_SESION));
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    expect((await screen.findByRole("alert")).textContent).toBe("Correo o contraseña incorrectos.");
    expect(emitidos).toBe(2);
    expect(tokensEnviados).toEqual(["token-2"]);
  });

  test("tkt008_ca06_esc03 · credenciales incorrectas · al reenviar, el mensaje anterior desaparece mientras la petición está en vuelo (TC-R313)", async () => {
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() => HttpResponse.json(errorSesion("CREDENCIALES_INVALIDAS"), { status: 401 })),
    );
    const { router, usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);
    await usuario.click(botonIniciar());
    expect((await screen.findByRole("alert")).textContent).toBe("Correo o contraseña incorrectos.");

    let liberar: () => void = () => undefined;
    const respuestaDelServidor = new Promise<void>((resolver) => {
      liberar = resolver;
    });
    servidorPruebas.use(
      dobleInicio(async () => {
        await respuestaDelServidor;
        return HttpResponse.json(usuarioActual(["COMPRAS"]));
      }),
      dobleSesion(["COMPRAS"]),
    );
    await usuario.type(screen.getByLabelText("Contraseña"), CONTRASENA);

    await usuario.click(botonIniciar());

    await waitFor(() => expect(botonIniciar()).toBeDisabled());
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(router.state.location.pathname).toBe(INICIO_SESION);

    liberar();

    expect(await screen.findByRole("heading", { level: 1, name: "Línea base" })).toBeInTheDocument();
  });

  test("tkt008_ca06_esc06 · sin conexión · si el navegador pasa de en línea a sin conexión, el botón se deshabilita y aparece el aviso (TC-R314)", async () => {
    const registro = registrarPeticiones();
    const enLinea = vi.spyOn(globalThis.navigator, "onLine", "get").mockReturnValue(true);
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);
    expect(botonIniciar()).toBeEnabled();
    expect(screen.queryByText(SIN_CONEXION)).not.toBeInTheDocument();

    await act(async () => {
      enLinea.mockReturnValue(false);
      globalThis.dispatchEvent(new Event("offline"));
    });

    expect(botonIniciar()).toBeDisabled();
    expect(screen.getByText(SIN_CONEXION)).toBeInTheDocument();
    await usuario.click(botonIniciar());
    expect(registro).toEqual([]);
  });

  test("tkt008_ca04 · un 403 que no es de origen no verificado · mensaje genérico con su referencia y sin «Recargar» (TC-R315)", async () => {
    servidorPruebas.use(
      dobleCsrf(),
      dobleInicio(() => HttpResponse.json(errorPermiso("ROL_INSUFICIENTE"), { status: 403 })),
    );
    const { usuario } = renderizarAplicacion(INICIO_SESION);
    await escribirCredenciales(usuario);

    await usuario.click(botonIniciar());

    const alerta = await screen.findByRole("alert");
    expect(alerta.textContent).toBe("No se pudo iniciar sesión. Referencia: 7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e");
    expect(screen.queryByText(ORIGEN_NO_VERIFICADO)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Recargar" })).not.toBeInTheDocument();
  });
});
