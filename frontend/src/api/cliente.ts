import createClient, { type Middleware } from "openapi-fetch";
import type { paths } from "@/api/generado/servidor";
import { type ErrorApi, normalizarError } from "@/api/errores";

export const CABECERA_CSRF = "X-CSRF-Token";
const METODOS_QUE_MUTAN = new Set(["POST", "PUT", "PATCH", "DELETE"]);
const RUTA_INICIO = "/api/v1/sesion";
const RUTA_CIERRE = "/api/v1/sesion/cierre";

export type ResultadoApi<T> = { ok: true; datos: T } | { ok: false; error: ErrorApi };

/** Marca de que `fetch` mismo rechazó la promesa: la petición no llegó al servidor. */
class FalloDeFetch extends Error {
  readonly causa: unknown;
  constructor(causa: unknown) {
    super("fetch falló");
    this.causa = causa;
  }
}

export class FalloApi extends Error {
  readonly error: ErrorApi;
  constructor(error: ErrorApi) {
    super(error.tipo);
    this.error = error;
  }
}

/** RNF-05 · CA-3. Toda mutación lleva X-CSRF-Token; un GET, nunca. */
export async function aplicarCsrf(request: Request, obtenerToken: () => Promise<string>): Promise<Request> {
  if (!METODOS_QUE_MUTAN.has(request.method)) return request;
  request.headers.set(CABECERA_CSRF, await obtenerToken());
  return request;
}

export interface OpcionesCliente {
  baseUrl: string;
  /** Un 401 que no sea del propio inicio ni del cierre de sesión (CA-5 esc. 1 y 3). */
  alTerminarSesion: () => void;
  /** Cualquier 403: el armazón vuelve a preguntar quién es (CA-5 esc. 4, RNF-01). */
  alDenegarPermiso: () => void;
}

export function crearClienteApi(opciones: OpcionesCliente) {
  const cliente = createClient<paths>({
    baseUrl: opciones.baseUrl,
    credentials: "same-origin",
    // Se lee globalThis.fetch en cada llamada, no al crear el cliente: así lo intercepta MSW en pruebas.
    // Solo un rechazo de fetch se marca: un TypeError del propio código (p. ej. headers.set) no es una caída de red.
    fetch: async (request: Request) => {
      try {
        return await globalThis.fetch(request);
      } catch (causa: unknown) {
        throw new FalloDeFetch(causa);
      }
    },
  });
  let token: Promise<string> | null = null;
  async function pedirToken(): Promise<string> {
    const { data, error, response } = await cliente.GET("/api/v1/sesion/csrf");
    if (!response.ok) throw new FalloApi(normalizarError(response.status, error, response.headers));
    const valor: unknown = data?.token;
    if (typeof valor !== "string" || valor === "") {
      // 200 sin token utilizable: nunca se envía la cabecera con `undefined`.
      throw new FalloApi({ tipo: "GENERICO", estado: response.status, mensaje: null, correlacion_id: null });
    }
    return valor; // PA-T9: del cuerpo, nunca de la cookie
  }
  function obtenerToken(): Promise<string> {
    // Dos mutaciones simultáneas comparten una sola petición del token.
    token ??= pedirToken().catch((error: unknown) => {
      token = null;
      throw error;
    });
    return token;
  }
  const middleware: Middleware = {
    onRequest: ({ request }) => aplicarCsrf(request, obtenerToken),
    onResponse: ({ request, response }) => {
      const ruta = new URL(request.url).pathname;
      const esDeSesion = request.method === "POST" && (ruta === RUTA_INICIO || ruta === RUTA_CIERRE);
      if (esDeSesion) token = null; // PA-T9: se vuelve a pedir tras iniciar y tras cerrar
      if (response.status === 401 && !esDeSesion) opciones.alTerminarSesion();
      if (response.status === 403) {
        // Un 403 puede ser ORIGEN_NO_VERIFICADO (token viejo o ausente): se descarta el token sin leer
        // el cuerpo; en un ROL_INSUFICIENTE cuesta un GET de más en la siguiente mutación.
        token = null;
        opciones.alDenegarPermiso();
      }
      return undefined;
    },
  };
  cliente.use(middleware);
  return cliente;
}

export type ClienteApi = ReturnType<typeof crearClienteApi>;

/** M3. Nunca lanza: el error de red es RED; toda respuesta no 2xx se normaliza. */
export async function pedir<T>(
  llamada: () => Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<ResultadoApi<T>> {
  let resultado: { data?: T; error?: unknown; response: Response };
  try {
    resultado = await llamada();
  } catch (fallo: unknown) {
    if (fallo instanceof FalloApi) return { ok: false, error: fallo.error }; // el token CSRF no se obtuvo
    // RED solo cuando fetch mismo falla (sin conexión o abortada); cualquier otra excepción es GENERICO.
    if (fallo instanceof FalloDeFetch) return { ok: false, error: { tipo: "RED" } };
    return { ok: false, error: { tipo: "GENERICO", estado: 0, mensaje: null, correlacion_id: null } };
  }
  const { data, error, response } = resultado;
  if (!response.ok) return { ok: false, error: normalizarError(response.status, error, response.headers) };
  return { ok: true, datos: data as T }; // en un 204, T es el tipo vacío que declara openapi-fetch
}

/** Para queryFn: devuelve los datos o lanza FalloApi, que TanStack Query guarda como error de la consulta. */
export function exigir<T>(resultado: ResultadoApi<T>): T {
  if (!resultado.ok) throw new FalloApi(resultado.error);
  return resultado.datos;
}
