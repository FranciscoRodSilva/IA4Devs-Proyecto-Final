import { http, HttpResponse } from "msw";
import type { Client } from "openapi-fetch";
import { describe, expect, test, vi } from "vitest";
import { servidorPruebas } from "@/pruebas/servidor";
import { FalloApi, type ResultadoApi, aplicarCsrf, crearClienteApi, exigir, pedir } from "./cliente";
import type { components as Provisional } from "./generado/contrato-error.provisional.ts";
import type { components as Servidor, paths } from "./generado/servidor.ts";

// Los cuerpos cumplen los esquemas generados por compilación (`satisfies`): si el contrato cambia, `npm run typecheck`
// lo dice. El servidor se sustituye con MSW, que intercepta la petición real con sus cabeceras (D-2).
type Errores = Provisional["schemas"];
type Esquemas = Servidor["schemas"];

const ORIGEN = globalThis.location.origin;
const RUTA_CSRF = "/api/v1/sesion/csrf";
const RUTA_SESION = "/api/v1/sesion";
const RUTA_CIERRE = "/api/v1/sesion/cierre";
// Una mutación que no es de sesión: el borrador de TKT-008 solo publica rutas de sesión, así que el test declara su ruta.
const RUTA_MUTACION = "/api/v1/requisiciones";

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
type ClienteDePrueba = Client<paths & { [RUTA_MUTACION]: RutaDePrueba }>;

const correlacion_id = "7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e";

const usuarioActual = {
  id: "0b6f1c3e-2d4a-4e5f-8a7b-9c0d1e2f3a4b",
  nombre: "Rosa Villanueva",
  email: "ana@cimenta.test",
  roles: ["COMPRAS"],
  sesion: { expira_en: "2026-10-27T02:00:00Z", expira_por_inactividad_en: "2026-10-26T22:00:00Z" },
} satisfies Esquemas["UsuarioActual"];

const credenciales = { email: "ana@cimenta.test", contrasena: "contrasena-de-prueba" } satisfies Esquemas["CredencialesInicio"];

const origenNoVerificado = {
  tipo: "PERMISO",
  motivo: "ORIGEN_NO_VERIFICADO",
  mensaje: "No se pudo verificar el origen de la petición. Recarga la página.",
  roles_requeridos: [],
  correlacion_id,
} satisfies Errores["ErrorPermiso"];

const rolInsuficiente = {
  tipo: "PERMISO",
  motivo: "ROL_INSUFICIENTE",
  mensaje: "Tu rol no permite esta operación.",
  roles_requeridos: ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL"],
  correlacion_id,
} satisfies Errores["ErrorPermiso"];

const sesionCaducada = {
  tipo: "SESION",
  motivo: "SESION_CADUCADA",
  mensaje: "La sesión caducó.",
  correlacion_id,
} satisfies Errores["ErrorSesion"];

const credencialesInvalidas = {
  tipo: "SESION",
  motivo: "CREDENCIALES_INVALIDAS",
  mensaje: "Correo o contraseña incorrectos.",
  correlacion_id,
} satisfies Errores["ErrorSesion"];

interface Peticion {
  metodo: string;
  ruta: string;
  csrf: string | null;
}

function anotar(registro: Peticion[], request: Request): void {
  registro.push({ metodo: request.method, ruta: new URL(request.url).pathname, csrf: request.headers.get("X-CSRF-Token") });
}

const resumen = (registro: Peticion[]) => registro.map(({ metodo, ruta }) => `${metodo} ${ruta}`);

/** `GET /sesion/csrf` emite un token nuevo en cada petición (M1): `token-1`, `token-2`… */
function dobleCsrf(registro: Peticion[]) {
  let emitidos = 0;
  return http.get(`${ORIGEN}${RUTA_CSRF}`, ({ request }) => {
    anotar(registro, request);
    emitidos += 1;
    return HttpResponse.json({ token: `token-${emitidos}` } satisfies Esquemas["TokenCsrf"]);
  });
}

function responde(registro: Peticion[], metodo: "get" | "post", ruta: string, respuesta: () => Response) {
  return http[metodo](`${ORIGEN}${ruta}`, ({ request }) => {
    anotar(registro, request);
    return respuesta();
  });
}

const sinContenido = () => new HttpResponse(null, { status: 204 });
const mutacionAceptada = () => HttpResponse.json({ id: "9c8b7a6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d" });

function crearCliente() {
  const alTerminarSesion = vi.fn<() => void>();
  const alDenegarPermiso = vi.fn<() => void>();
  const api = crearClienteApi({ baseUrl: ORIGEN, alTerminarSesion, alDenegarPermiso });
  // Misma instancia, vista con la ruta de mutación que declara este archivo.
  return { api, apiConMutacion: api as unknown as ClienteDePrueba, alTerminarSesion, alDenegarPermiso };
}

function iniciarSesion(api: ReturnType<typeof crearCliente>["api"]) {
  return pedir(() => api.POST(RUTA_SESION, { body: credenciales }));
}

describe("TKT-008 · cliente de API", () => {
  test("tkt008_ca03_esc01 · token antes de iniciar", async () => {
    const registro: Peticion[] = [];
    servidorPruebas.use(dobleCsrf(registro), responde(registro, "post", RUTA_SESION, () => HttpResponse.json(usuarioActual)));
    const { api } = crearCliente();

    const resultado = await iniciarSesion(api);

    expect(resultado).toEqual({ ok: true, datos: usuarioActual });
    expect(resumen(registro)).toEqual([`GET ${RUTA_CSRF}`, `POST ${RUTA_SESION}`]);
    expect(registro[1]?.csrf).toBe("token-1");
    // La petición que pide el token no lleva la cabecera: un GET nunca la lleva.
    expect(registro[0]?.csrf).toBeNull();
  });

  test("tkt008_ca03_esc02 · mutaciones sí, GET no", async () => {
    for (const metodo of ["POST", "PUT", "PATCH", "DELETE"]) {
      const obtenerToken = vi.fn(() => Promise.resolve("token-de-prueba"));
      const solicitud = new Request(`${ORIGEN}${RUTA_MUTACION}`, { method: metodo });

      const resultado = await aplicarCsrf(solicitud, obtenerToken);

      expect(resultado.headers.get("X-CSRF-Token"), metodo).toBe("token-de-prueba");
      expect(obtenerToken, metodo).toHaveBeenCalledTimes(1);
    }

    for (const metodo of ["GET", "HEAD"]) {
      const obtenerToken = vi.fn(() => Promise.resolve("token-de-prueba"));
      const solicitud = new Request(`${ORIGEN}${RUTA_MUTACION}`, { method: metodo });

      const resultado = await aplicarCsrf(solicitud, obtenerToken);

      expect(resultado.headers.get("X-CSRF-Token"), metodo).toBeNull();
      expect(obtenerToken, metodo).not.toHaveBeenCalled();
    }
  });

  test("tkt008_ca03_esc01 · PA-T9 · tras iniciar sesión la siguiente mutación vuelve a pedir el token", async () => {
    const trasInicio: Peticion[] = [];
    servidorPruebas.use(
      dobleCsrf(trasInicio),
      responde(trasInicio, "post", RUTA_SESION, () => HttpResponse.json(usuarioActual)),
      responde(trasInicio, "post", RUTA_MUTACION, mutacionAceptada),
    );
    const primero = crearCliente();
    await iniciarSesion(primero.api);
    await pedir(() => primero.apiConMutacion.POST(RUTA_MUTACION));

    expect(resumen(trasInicio)).toEqual([`GET ${RUTA_CSRF}`, `POST ${RUTA_SESION}`, `GET ${RUTA_CSRF}`, `POST ${RUTA_MUTACION}`]);
    expect(trasInicio.filter(({ ruta }) => ruta === RUTA_CSRF)).toHaveLength(2);
    expect(trasInicio[1]?.csrf).toBe("token-1");
    expect(trasInicio[3]?.csrf).toBe("token-2");
  });

  test("tkt008_ca03_esc01 · PA-T9 · tras cerrar sesión la siguiente mutación vuelve a pedir el token", async () => {
    const trasCierre: Peticion[] = [];
    servidorPruebas.use(
      dobleCsrf(trasCierre),
      responde(trasCierre, "post", RUTA_CIERRE, sinContenido),
      responde(trasCierre, "post", RUTA_MUTACION, mutacionAceptada),
    );
    const segundo = crearCliente();
    await pedir(() => segundo.api.POST(RUTA_CIERRE));
    await pedir(() => segundo.apiConMutacion.POST(RUTA_MUTACION));

    expect(resumen(trasCierre)).toEqual([`GET ${RUTA_CSRF}`, `POST ${RUTA_CIERRE}`, `GET ${RUTA_CSRF}`, `POST ${RUTA_MUTACION}`]);
    expect(trasCierre[1]?.csrf).toBe("token-1");
    expect(trasCierre[3]?.csrf).toBe("token-2");
  });

  test("tkt008_ca03_esc01 · PA-T9 · dos mutaciones simultáneas sin token comparten una sola petición del token", async () => {
    const simultaneas: Peticion[] = [];
    servidorPruebas.use(dobleCsrf(simultaneas), responde(simultaneas, "post", RUTA_MUTACION, mutacionAceptada));
    const tercero = crearCliente();
    const resultados = await Promise.all([
      pedir(() => tercero.apiConMutacion.POST(RUTA_MUTACION)),
      pedir(() => tercero.apiConMutacion.POST(RUTA_MUTACION)),
    ]);

    expect(resultados.map(({ ok }) => ok)).toEqual([true, true]);
    expect(simultaneas.filter(({ ruta }) => ruta === RUTA_CSRF)).toHaveLength(1);
    expect(simultaneas.filter(({ metodo }) => metodo === "POST").map(({ csrf }) => csrf)).toEqual(["token-1", "token-1"]);
  });

  test("tkt008_ca03_esc03 · origen no verificado", async () => {
    const registro: Peticion[] = [];
    servidorPruebas.use(
      dobleCsrf(registro),
      responde(registro, "post", RUTA_MUTACION, () => HttpResponse.json(origenNoVerificado, { status: 403 })),
    );
    const { apiConMutacion, alDenegarPermiso, alTerminarSesion } = crearCliente();

    const rechazada = await pedir(() => apiConMutacion.POST(RUTA_MUTACION));

    // Entrega el error completo con su motivo y no reintenta en silencio: un solo POST.
    expect(rechazada).toEqual({ ok: false, error: origenNoVerificado });
    expect(resumen(registro)).toEqual([`GET ${RUTA_CSRF}`, `POST ${RUTA_MUTACION}`]);
    expect(registro[1]?.csrf).toBe("token-1");
    expect(alDenegarPermiso).toHaveBeenCalledTimes(1);
    expect(alTerminarSesion).not.toHaveBeenCalled();

    // El token rechazado no se reutiliza (hallazgo m-4): la siguiente mutación pide otro y lleva el nuevo.
    servidorPruebas.use(responde(registro, "post", RUTA_MUTACION, mutacionAceptada));
    const siguiente = await pedir(() => apiConMutacion.POST(RUTA_MUTACION));

    expect(siguiente.ok).toBe(true);
    expect(registro.filter(({ ruta }) => ruta === RUTA_CSRF)).toHaveLength(2);
    expect(resumen(registro)).toEqual([`GET ${RUTA_CSRF}`, `POST ${RUTA_MUTACION}`, `GET ${RUTA_CSRF}`, `POST ${RUTA_MUTACION}`]);
    expect(registro[3]?.csrf).toBe("token-2");
  });

  test("tkt008_ca04_esc03 · sin red", async () => {
    servidorPruebas.use(http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.error()));
    const { api, alTerminarSesion, alDenegarPermiso } = crearCliente();

    const resultado = await pedir(() => api.GET(RUTA_SESION));

    // Distinto de cualquier tipo del contrato y de un 401: la sesión no termina.
    expect(resultado).toEqual({ ok: false, error: { tipo: "RED" } });
    expect(alTerminarSesion).not.toHaveBeenCalled();
    expect(alDenegarPermiso).not.toHaveBeenCalled();
  });

  // Un 401 termina la sesión solo si no es de la propia sesión (CA-5 esc. 1 y 3). El cierre de sesión no tiene escenario
  // propio en la spec; se trata como el inicio, y por eso lleva `esc03`.
  const casos401: {
    titulo: string;
    doble: (registro: Peticion[]) => ReturnType<typeof http.get>[];
    llamar: (api: ReturnType<typeof crearCliente>["api"]) => Promise<ResultadoApi<unknown>>;
    cuerpo: Errores["ErrorSesion"];
    terminanLaSesion: number;
  }[] = [
    {
      titulo: `tkt008_ca05_esc01 · GET ${RUTA_SESION} con 401 termina la sesión`,
      doble: (registro) => [responde(registro, "get", RUTA_SESION, () => HttpResponse.json(sesionCaducada, { status: 401 }))],
      llamar: (api) => pedir(() => api.GET(RUTA_SESION)),
      cuerpo: sesionCaducada,
      terminanLaSesion: 1,
    },
    {
      titulo: `tkt008_ca05_esc03 · POST ${RUTA_SESION} con 401 no termina la sesión`,
      doble: (registro) => [
        dobleCsrf(registro),
        responde(registro, "post", RUTA_SESION, () => HttpResponse.json(credencialesInvalidas, { status: 401 })),
      ],
      llamar: (api) => iniciarSesion(api),
      cuerpo: credencialesInvalidas,
      terminanLaSesion: 0,
    },
    {
      titulo: `tkt008_ca05_esc03 · POST ${RUTA_CIERRE} con 401 no termina la sesión`,
      doble: (registro) => [
        dobleCsrf(registro),
        responde(registro, "post", RUTA_CIERRE, () => HttpResponse.json(sesionCaducada, { status: 401 })),
      ],
      llamar: (api) => pedir(() => api.POST(RUTA_CIERRE)),
      cuerpo: sesionCaducada,
      terminanLaSesion: 0,
    },
  ];

  // `%s` y no `$titulo`: Vitest recorta a 40 caracteres lo que interpola con `$`, y el nombre lleva el escenario completo.
  test.each(casos401.map((caso) => [caso.titulo, caso] as const))("%s", async (titulo, { doble, llamar, cuerpo, terminanLaSesion }) => {
    servidorPruebas.use(...doble([]));
    const { api, alTerminarSesion, alDenegarPermiso } = crearCliente();

    const resultado = await llamar(api);

    // El error normalizado llega completo en los tres casos; lo que cambia es si la aplicación termina la sesión.
    expect(resultado, titulo).toEqual({ ok: false, error: cuerpo });
    expect(alTerminarSesion, titulo).toHaveBeenCalledTimes(terminanLaSesion);
    expect(alDenegarPermiso, titulo).not.toHaveBeenCalled();
  });

  test("tkt008_ca05_esc04 · 403 pregunta de nuevo", async () => {
    const registro: Peticion[] = [];
    servidorPruebas.use(
      dobleCsrf(registro),
      responde(registro, "get", RUTA_SESION, () => HttpResponse.json(rolInsuficiente, { status: 403 })),
      responde(registro, "post", RUTA_MUTACION, () => HttpResponse.json(rolInsuficiente, { status: 403 })),
    );

    const lectura = crearCliente();
    const alLeer = await pedir(() => lectura.api.GET(RUTA_SESION));

    expect(alLeer).toEqual({ ok: false, error: rolInsuficiente });
    expect(lectura.alDenegarPermiso).toHaveBeenCalledTimes(1);
    expect(lectura.alTerminarSesion).not.toHaveBeenCalled();

    const mutacion = crearCliente();
    const alMutar = await pedir(() => mutacion.apiConMutacion.POST(RUTA_MUTACION));

    expect(alMutar).toEqual({ ok: false, error: rolInsuficiente });
    expect(mutacion.alDenegarPermiso).toHaveBeenCalledTimes(1);
    expect(mutacion.alTerminarSesion).not.toHaveBeenCalled();
  });

  test("tkt008_car3 · nadie lee la cookie", async () => {
    // MSW lee `document.cookie` por su cuenta al emparejar cada petición en jsdom; ese lector no es el cliente.
    // Se anota quién lee: el primer marco de la pila que no es el espía, jsdom ni una llamada anónima.
    const lectores: string[] = [];
    const quienLee = (pila: string): string =>
      pila
        .split("\n")
        .slice(1)
        .filter((marco) => !marco.includes("Proxy.get") && !marco.includes("jsdom") && !marco.includes("<anonymous>"))[0] ?? "";

    const registro: Peticion[] = [];
    servidorPruebas.use(
      dobleCsrf(registro),
      responde(registro, "post", RUTA_SESION, () => HttpResponse.json(usuarioActual)),
      responde(registro, "post", RUTA_CIERRE, sinContenido),
    );
    Object.defineProperty(document, "cookie", {
      configurable: true,
      get() {
        lectores.push(quienLee(new Error().stack ?? ""));
        return "";
      },
      set() {
        // Escribir la cookie tampoco es cosa del cliente, pero este test solo vigila las lecturas.
      },
    });
    try {
      const { api } = crearCliente();
      const inicio = await iniciarSesion(api);
      const cierre = await pedir(() => api.POST(RUTA_CIERRE));

      expect(inicio.ok).toBe(true);
      expect(cierre.ok).toBe(true);
    } finally {
      Reflect.deleteProperty(document, "cookie");
    }

    // Un inicio y un cierre completos, y ninguna lectura salió del código de la aplicación (solo de node_modules).
    expect(resumen(registro)).toEqual([`GET ${RUTA_CSRF}`, `POST ${RUTA_SESION}`, `GET ${RUTA_CSRF}`, `POST ${RUTA_CIERRE}`]);
    expect(lectores.filter((lector) => !lector.includes("node_modules"))).toEqual([]);
  });

  test("tkt008_ca07_esc07 · 204", async () => {
    const registro: Peticion[] = [];
    servidorPruebas.use(dobleCsrf(registro), responde(registro, "post", RUTA_CIERRE, sinContenido));
    const { api, alTerminarSesion } = crearCliente();

    const resultado = await pedir(() => api.POST(RUTA_CIERRE));

    expect(resultado.ok).toBe(true);
    expect(resultado).toEqual({ ok: true });
    expect(resumen(registro)).toEqual([`GET ${RUTA_CSRF}`, `POST ${RUTA_CIERRE}`]);
    expect(alTerminarSesion).not.toHaveBeenCalled();
  });

  test("tkt008_ca03_esc01 · el token fallido no se cachea", async () => {
    // TC-H1 · MT-A1. Si `GET /sesion/csrf` falla, esa promesa rechazada no se queda en caché: la siguiente mutación vuelve a pedirlo.
    const registro: Peticion[] = [];
    let respuestas = 0;
    servidorPruebas.use(
      http.get(`${ORIGEN}${RUTA_CSRF}`, ({ request }) => {
        anotar(registro, request);
        respuestas += 1;
        return respuestas === 1
          ? new HttpResponse(null, { status: 500 })
          : HttpResponse.json({ token: "token-tras-el-fallo" } satisfies Esquemas["TokenCsrf"]);
      }),
      responde(registro, "post", RUTA_MUTACION, mutacionAceptada),
    );
    const { apiConMutacion } = crearCliente();

    const fallida = await pedir(() => apiConMutacion.POST(RUTA_MUTACION));

    // Sin token no se envía la mutación: solo se intentó pedirlo. El servidor respondió, así que no es RED (F005).
    expect(fallida).toEqual({ ok: false, error: { tipo: "GENERICO", estado: 500, mensaje: null, correlacion_id: null } });
    expect(resumen(registro)).toEqual([`GET ${RUTA_CSRF}`]);

    const siguiente = await pedir(() => apiConMutacion.POST(RUTA_MUTACION));

    expect(siguiente.ok).toBe(true);
    expect(resumen(registro)).toEqual([`GET ${RUTA_CSRF}`, `GET ${RUTA_CSRF}`, `POST ${RUTA_MUTACION}`]);
    expect(registro[2]?.csrf).toBe("token-tras-el-fallo");
  });

  test("tkt008_ca04_esc02 · TC-F5a · el token con 500 es GENERICO con su correlación", async () => {
    // Ciclo de corrección 1 · F005. RED es solo «la petición no llegó al servidor»: aquí el servidor respondió 500.
    const registro: Peticion[] = [];
    servidorPruebas.use(
      http.get(`${ORIGEN}${RUTA_CSRF}`, ({ request }) => {
        anotar(registro, request);
        return HttpResponse.json({ mensaje: "Error interno.", correlacion_id }, { status: 500 });
      }),
      responde(registro, "post", RUTA_MUTACION, mutacionAceptada),
    );
    const { apiConMutacion, alTerminarSesion, alDenegarPermiso } = crearCliente();

    const resultado = await pedir(() => apiConMutacion.POST(RUTA_MUTACION));

    expect(resultado).toEqual({
      ok: false,
      error: { tipo: "GENERICO", estado: 500, mensaje: "Error interno.", correlacion_id },
    });
    expect(resumen(registro)).toEqual([`GET ${RUTA_CSRF}`]);
    expect(alTerminarSesion).not.toHaveBeenCalled();
    expect(alDenegarPermiso).not.toHaveBeenCalled();
  });

  test("tkt008_ca04_esc02 · TC-F5b · el token con 200 y sin campo token es GENERICO", async () => {
    const registro: Peticion[] = [];
    servidorPruebas.use(
      http.get(`${ORIGEN}${RUTA_CSRF}`, ({ request }) => {
        anotar(registro, request);
        return HttpResponse.json({});
      }),
      responde(registro, "post", RUTA_MUTACION, mutacionAceptada),
    );
    const { apiConMutacion } = crearCliente();

    const resultado = await pedir(() => apiConMutacion.POST(RUTA_MUTACION));

    expect(resultado.ok).toBe(false);
    expect(!resultado.ok ? resultado.error.tipo : null).toBe("GENERICO");
    expect(!resultado.ok && resultado.error.tipo === "GENERICO" ? resultado.error.estado : null).toBe(200);
    expect(resumen(registro)).toEqual([`GET ${RUTA_CSRF}`]);
  });

  test("tkt008_ca04_esc03 · TC-F5c · un fallo de red al pedir el token sigue siendo RED", async () => {
    // El caso real de RED: la petición del token no llega al servidor (HttpResponse.error() de MSW).
    const registro: Peticion[] = [];
    servidorPruebas.use(
      http.get(`${ORIGEN}${RUTA_CSRF}`, ({ request }) => {
        anotar(registro, request);
        return HttpResponse.error();
      }),
      responde(registro, "post", RUTA_MUTACION, mutacionAceptada),
    );
    const { apiConMutacion } = crearCliente();

    const resultado = await pedir(() => apiConMutacion.POST(RUTA_MUTACION));

    expect(resultado).toEqual({ ok: false, error: { tipo: "RED" } });
    expect(resumen(registro)).toEqual([`GET ${RUTA_CSRF}`]);
  });

  test("tkt008_ca04_esc02 · TC-R1d · un Error que no es de red es GENERICO con estado 0", async () => {
    // Revisión · C002. RED es solo «la petición no llegó al servidor» (TypeError de fetch o AbortError): cualquier otro
    // Error que escape de la llamada no es una caída de red.
    const resultado = await pedir(() => Promise.reject(new Error("fallo inesperado")));

    expect(resultado).toEqual({ ok: false, error: { tipo: "GENERICO", estado: 0, mensaje: null, correlacion_id: null } });
  });

  test("tkt008_ca04_esc02 · TC-R1e · un TypeError de código propio, no de fetch, no es RED", async () => {
    // Revisión · C002. El servidor responde y entrega un token que no es un valor de cabecera válido: `headers.set` lanza
    // `TypeError` dentro del cliente, y eso no es un fallo de red.
    const registro: Peticion[] = [];
    servidorPruebas.use(
      http.get(`${ORIGEN}${RUTA_CSRF}`, ({ request }) => {
        anotar(registro, request);
        return HttpResponse.json({ token: "token\ninválido" });
      }),
      responde(registro, "post", RUTA_MUTACION, mutacionAceptada),
    );
    const { apiConMutacion, alTerminarSesion, alDenegarPermiso } = crearCliente();

    const resultado = await pedir(() => apiConMutacion.POST(RUTA_MUTACION));

    expect(resultado).toEqual({ ok: false, error: { tipo: "GENERICO", estado: 0, mensaje: null, correlacion_id: null } });
    expect(resumen(registro)).toEqual([`GET ${RUTA_CSRF}`]);
    expect(alTerminarSesion).not.toHaveBeenCalled();
    expect(alDenegarPermiso).not.toHaveBeenCalled();
  });

  test("tkt008_ca04_esc01 · exigir lanza FalloApi con el error normalizado", async () => {
    // TC-H2 · MT-A2. `exigir` devuelve los datos si la respuesta fue buena y, si no, lanza `FalloApi` con el error íntegro.
    servidorPruebas.use(http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(usuarioActual)));
    const { api } = crearCliente();

    const buena = await pedir(() => api.GET(RUTA_SESION));

    expect(exigir(buena)).toEqual(usuarioActual);

    servidorPruebas.use(http.get(`${ORIGEN}${RUTA_SESION}`, () => HttpResponse.json(rolInsuficiente, { status: 403 })));
    const rechazada = await pedir(() => api.GET(RUTA_SESION));
    let capturado: unknown;
    try {
      exigir(rechazada);
    } catch (error) {
      capturado = error;
    }

    expect(capturado).toBeInstanceOf(FalloApi);
    expect(capturado instanceof FalloApi ? capturado.error : null).toEqual(rolInsuficiente);
    expect(capturado instanceof FalloApi ? capturado.message : null).toBe("PERMISO");
  });
});
