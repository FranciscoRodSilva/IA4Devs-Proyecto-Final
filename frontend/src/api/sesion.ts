import { queryOptions, useQuery } from "@tanstack/react-query";
import { type ClienteApi, exigir, pedir } from "@/api/cliente";
import type { components } from "@/api/generado/servidor";
import { useApi } from "@/api/ProveedorApi";

export const claves = { sesion: ["sesion"] as const };

export type UsuarioActual = components["schemas"]["UsuarioActual"];
export type Rol = UsuarioActual["roles"][number];

/** La sesión de la persona (C107): una sola definición de la consulta para el armazón, la guarda y el inicio. */
export function useSesion() {
  return useQuery(sesionOptions(useApi()));
}

/** Excepción declarada a conv-frontend-react §4: la instancia `api` es el transporte, no selecciona
 *  ningún registro, y nace junto al QueryClient; por eso no entra en la clave (no es serializable). */
export const sesionOptions = (api: ClienteApi) =>
  queryOptions({
    queryKey: claves.sesion,
    queryFn: async () => exigir(await pedir(() => api.GET("/api/v1/sesion"))),
    staleTime: 30_000,
  });
