import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactElement } from "react";
import { createBrowserRouter, createMemoryRouter, RouterProvider } from "react-router";
import { type ClienteApi, crearClienteApi } from "@/api/cliente";
import { ProveedorApi } from "@/api/ProveedorApi";
import { claves } from "@/api/sesion";
import { AVISO_SESION_TERMINADA, RUTA_INICIO_SESION } from "@/app/navegacion/ruta-inicio-sesion";
import { rutas } from "@/app/rutas";

export type Router = ReturnType<typeof createBrowserRouter>;

/** Raíz de composición (fila 9). Crea una sola vez el QueryClient, el cliente de API y el enrutador. */
export function crearAplicacion(opciones: { rutaInicial?: string } = {}): {
  elemento: ReactElement;
  router: Router;
  queryClient: QueryClient;
  api: ClienteApi;
} {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });

  // Un 401 de una petición que no es el propio inicio ni cierre: la sesión terminó (CA-5 esc. 1).
  // El aviso sale si y solo si había un usuario cargado (D-6): se decide antes de vaciar la caché.
  function terminarSesion() {
    const habia = queryClient.getQueryData(claves.sesion) !== undefined;
    if (router.state.location.pathname !== RUTA_INICIO_SESION) {
      void router.navigate(RUTA_INICIO_SESION, {
        replace: true,
        state: habia ? { aviso: AVISO_SESION_TERMINADA } : null,
      });
    }
    queryClient.clear();
    // S101: el token CSRF era de la sesión que terminó; el siguiente inicio de sesión pide uno nuevo.
    api.reiniciarToken();
  }

  const api = crearClienteApi({
    baseUrl: globalThis.location.origin,
    alTerminarSesion: terminarSesion,
    alDenegarPermiso: () => void queryClient.invalidateQueries({ queryKey: claves.sesion }),
  });

  const router: Router =
    opciones.rutaInicial === undefined
      ? createBrowserRouter(rutas)
      : createMemoryRouter(rutas, { initialEntries: [opciones.rutaInicial] });

  const elemento = (
    <ProveedorApi api={api}>
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ProveedorApi>
  );

  return { elemento, router, queryClient, api };
}
