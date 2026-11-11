import { queryOptions } from "@tanstack/react-query";
import { type ClienteApi, exigir, pedir } from "@/api/cliente";
import type { components } from "@/api/generado/servidor";

type Esquemas = components["schemas"];
type ObraNueva = Esquemas["ObraNueva"];

/** Claves de caché de las obras. El alta invalida el prefijo `obras` entero, así que la lista se vuelve a pedir. */
export const claves = { obras: ["obras"] as const };

/** D-4: una sola página de hasta 200 obras, ordenadas por código en el servidor. */
const PAGINA_UNICA = { pagina: 1, tamano_pagina: 200 } as const;

/** La lista de obras. La clave lleva la página porque la función de consulta depende de ella. */
export const obrasOptions = (api: ClienteApi) =>
  queryOptions({
    queryKey: [...claves.obras, "lista", PAGINA_UNICA] as const,
    queryFn: async () => exigir(await pedir(() => api.GET("/api/v1/obras", { params: { query: PAGINA_UNICA } }))),
    staleTime: 30_000,
  });

/** El alta. Devuelve el resultado tal cual; la invalidación la hace quien la llama tras confirmar. */
export function crearObra(api: ClienteApi, cuerpo: ObraNueva) {
  return pedir(() => api.POST("/api/v1/obras", { body: cuerpo }));
}
