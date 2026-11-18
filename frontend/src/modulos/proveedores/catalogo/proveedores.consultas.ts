import { queryOptions } from "@tanstack/react-query";
import { type ClienteApi, exigir, pedir, type ResultadoApi } from "@/api/cliente";
import type { components } from "@/api/generado/servidor";

type Esquemas = components["schemas"];
type Proveedor = Esquemas["Proveedor"];
type ProveedorNuevo = Esquemas["ProveedorNuevo"];
type ProveedorCambios = Esquemas["ProveedorCambios"];
type EstadoProveedor = Esquemas["EstadoProveedor"];
type ListaProveedores = Esquemas["ListaProveedores"];

/** Claves de caché de los proveedores. Las mutaciones invalidan el prefijo `proveedores` entero. */
export const claves = { proveedores: ["proveedores"] as const };

/** Lo que cambia la consulta de la lista; todo lo omitido toma su valor por omisión (`ACTIVO`, sin búsqueda, página 1). */
export interface ParametrosLista {
  estados?: ReadonlyArray<EstadoProveedor>;
  q?: string;
  pagina?: number;
}

/** Igual que el servidor: sin filtro, la lista trae solo los activos (D-5). */
const ESTADOS_POR_OMISION: ReadonlyArray<EstadoProveedor> = ["ACTIVO"];
/** Tamaño de página que pide la lista; la pantalla lo importa para contar las páginas. */
export const TAMANO_PAGINA = 50;

/** Cuántas páginas hay para `total` filas: al menos una, aunque no haya ninguna. */
export function totalDePaginas(total: number): number {
  return Math.max(1, Math.ceil(total / TAMANO_PAGINA));
}

/**
 * La lista de proveedores. Toda dependencia de la consulta va en la clave: estados, búsqueda, página y tamaño. El
 * estado se envía siempre; la búsqueda solo si no está vacía (D-5).
 */
export function proveedoresOptions(api: ClienteApi, parametros: ParametrosLista = {}) {
  const estados = [...(parametros.estados ?? ESTADOS_POR_OMISION)];
  const q = (parametros.q ?? "").trim();
  const pagina = parametros.pagina ?? 1;
  return queryOptions({
    queryKey: [...claves.proveedores, "lista", { estados, q, pagina, tamano_pagina: TAMANO_PAGINA }] as const,
    queryFn: async (): Promise<ListaProveedores> =>
      exigir(
        await pedir(() =>
          api.GET("/api/v1/proveedores", {
            params: {
              query: {
                estado: estados,
                pagina,
                tamano_pagina: TAMANO_PAGINA,
                ...(q === "" ? {} : { q }),
              },
            },
          }),
        ),
      ),
    staleTime: 30_000,
  });
}

// Las mutaciones devuelven el resultado tal cual; la invalidación de `claves.proveedores` la hace quien las llama.

export function crearProveedor(api: ClienteApi, cuerpo: ProveedorNuevo): Promise<ResultadoApi<Proveedor>> {
  return pedir(() => api.POST("/api/v1/proveedores", { body: cuerpo }));
}

/** `PATCH /proveedores/{proveedor_id}`: solo viajan los campos de `cambios`; `tope_consignacion: null` borra el tope. */
export function actualizarProveedor(
  api: ClienteApi,
  proveedorId: string,
  cambios: ProveedorCambios,
): Promise<ResultadoApi<Proveedor>> {
  return pedir(() =>
    api.PATCH("/api/v1/proveedores/{proveedor_id}", { params: { path: { proveedor_id: proveedorId } }, body: cambios }),
  );
}

/** `POST /proveedores/{proveedor_id}/desactivacion`: la baja lógica. El motivo lo valida el formulario que lo pide. */
export function desactivarProveedor(api: ClienteApi, proveedorId: string, motivo: string): Promise<ResultadoApi<Proveedor>> {
  return pedir(() =>
    api.POST("/api/v1/proveedores/{proveedor_id}/desactivacion", {
      params: { path: { proveedor_id: proveedorId } },
      body: { motivo },
    }),
  );
}

/** `POST /proveedores/{proveedor_id}/baja`: definitiva; el servidor la rechaza con órdenes ABIERTA o PARCIAL. */
export function darDeBajaProveedor(api: ClienteApi, proveedorId: string, motivo: string): Promise<ResultadoApi<Proveedor>> {
  return pedir(() =>
    api.POST("/api/v1/proveedores/{proveedor_id}/baja", {
      params: { path: { proveedor_id: proveedorId } },
      body: { motivo },
    }),
  );
}
