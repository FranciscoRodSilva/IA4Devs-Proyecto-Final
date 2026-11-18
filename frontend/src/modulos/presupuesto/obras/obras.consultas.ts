import { queryOptions } from "@tanstack/react-query";
import { type ClienteApi, exigir, pedir, type ResultadoApi } from "@/api/cliente";
import type { ErrorApi } from "@/api/errores";
import type { components } from "@/api/generado/servidor";
import { esquemaMotivo } from "@/compartido/formularios/motivo.formulario";

type Esquemas = components["schemas"];
type ObraNueva = Esquemas["ObraNueva"];
type Obra = Esquemas["Obra"];
type ObraCambios = Esquemas["ObraCambios"];

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

/** Una obra por su identificador (`GET /api/v1/obras/{obra_id}`); trae `linea_base_vigente_id`. Cuelga de `claves.obras`: el mismo prefijo la invalida. */
export const obraOptions = (api: ClienteApi, obraId: string) =>
  queryOptions({
    queryKey: [...claves.obras, obraId] as const,
    queryFn: async () =>
      exigir(await pedir(() => api.GET("/api/v1/obras/{obra_id}", { params: { path: { obra_id: obraId } } }))),
    staleTime: 30_000,
  });

/** El alta. Devuelve el resultado tal cual; la invalidación la hace quien la llama tras confirmar. */
export function crearObra(api: ClienteApi, cuerpo: ObraNueva) {
  return pedir(() => api.POST("/api/v1/obras", { body: cuerpo }));
}

// Como `crearObra`, devuelven el resultado tal cual; la invalidación de `claves.obras` la hace quien las llama.

/** `PATCH /obras/{obra_id}`: solo viajan los campos de `cambios`; `umbral_alerta_pct: null` borra el umbral. */
export function editarObra(api: ClienteApi, obraId: string, cambios: ObraCambios): Promise<ResultadoApi<Obra>> {
  return pedir(() => api.PATCH("/api/v1/obras/{obra_id}", { params: { path: { obra_id: obraId } }, body: cambios }));
}

/** `DELETE /obras/{obra_id}`: responde 204 sin cuerpo. */
export function eliminarObra(api: ClienteApi, obraId: string): Promise<ResultadoApi<unknown>> {
  return pedir(() => api.DELETE("/api/v1/obras/{obra_id}", { params: { path: { obra_id: obraId } } }));
}

/**
 * El motivo de una transición (CA-17): obligatorio, sin espacios en los extremos. Si falta, el rechazo es local y
 * ninguna petición sale. Lleva estado 0 porque nunca llegó al servidor, igual que los rechazos previos a la red.
 */
function validarMotivo(motivo: string): ResultadoApi<string> {
  const validado = esquemaMotivo.safeParse({ motivo });
  if (validado.success) return { ok: true, datos: validado.data.motivo };
  const error: ErrorApi = {
    tipo: "GENERICO",
    estado: 0,
    mensaje: validado.error.issues[0]?.message ?? "El motivo es obligatorio.",
    correlacion_id: null,
  };
  return { ok: false, error };
}

/**
 * Una transición con motivo: valida el motivo (CA-17) y, si es válido, llama a la operación con el motivo ya limpio.
 * Si el motivo falta, el rechazo es local y `llamar` no se ejecuta: ninguna petición sale.
 */
async function transicionar(
  api: ClienteApi,
  obraId: string,
  motivo: string,
  llamar: (cliente: ClienteApi, id: string, motivoLimpio: string) => Promise<ResultadoApi<Obra>>,
): Promise<ResultadoApi<Obra>> {
  const validado = validarMotivo(motivo);
  if (!validado.ok) return validado;
  return llamar(api, obraId, validado.datos);
}

/** `POST /obras/{obra_id}/suspension`: el motivo es obligatorio; sin él no sale ninguna petición. */
export function suspenderObra(api: ClienteApi, obraId: string, motivo: string): Promise<ResultadoApi<Obra>> {
  return transicionar(api, obraId, motivo, (cliente, id, motivoLimpio) =>
    pedir(() => cliente.POST("/api/v1/obras/{obra_id}/suspension", { params: { path: { obra_id: id } }, body: { motivo: motivoLimpio } })),
  );
}

/** `POST /obras/{obra_id}/reactivacion`: el motivo es obligatorio; sin él no sale ninguna petición. */
export function reactivarObra(api: ClienteApi, obraId: string, motivo: string): Promise<ResultadoApi<Obra>> {
  return transicionar(api, obraId, motivo, (cliente, id, motivoLimpio) =>
    pedir(() => cliente.POST("/api/v1/obras/{obra_id}/reactivacion", { params: { path: { obra_id: id } }, body: { motivo: motivoLimpio } })),
  );
}

/** `POST /obras/{obra_id}/cierre`: el motivo es obligatorio; sin él no sale ninguna petición. */
export function cerrarObra(api: ClienteApi, obraId: string, motivo: string): Promise<ResultadoApi<Obra>> {
  return transicionar(api, obraId, motivo, (cliente, id, motivoLimpio) =>
    pedir(() => cliente.POST("/api/v1/obras/{obra_id}/cierre", { params: { path: { obra_id: id } }, body: { motivo: motivoLimpio } })),
  );
}
