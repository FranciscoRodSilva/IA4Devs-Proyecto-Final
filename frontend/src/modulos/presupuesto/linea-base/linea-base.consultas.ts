import { queryOptions } from "@tanstack/react-query";
import { type ClienteApi, exigir, pedir, type ResultadoApi } from "@/api/cliente";
import type { components } from "@/api/generado/servidor";
import { claves } from "@/modulos/presupuesto/obras/obras.consultas";

type Esquemas = components["schemas"];
type LineaBase = Esquemas["LineaBase"];
type PresupuestoControl = Esquemas["PresupuestoControl"];
type CapturaPresupuestoControl = Esquemas["CapturaPresupuestoControl"];

/** Claves de caché de la línea base. Las líneas cuelgan de `claves.obras`: invalidar ese prefijo refresca
 *  a la vez la lista de obras, la obra y sus líneas base. */
export const clavesLineaBase = {
  lineas: (obraId: string) => [...claves.obras, obraId, "lineas-base"] as const,
  control: (lineaBaseId: string) => ["lineas-base", lineaBaseId, "presupuesto-control"] as const,
};

/** Las versiones de línea base de la obra. Sin regla propia: la congelación que las origina es RN-01. */
export const lineasBaseOptions = (api: ClienteApi, obraId: string) =>
  queryOptions({
    queryKey: clavesLineaBase.lineas(obraId),
    queryFn: async () =>
      exigir(await pedir(() => api.GET("/api/v1/obras/{obra_id}/lineas-base", { params: { path: { obra_id: obraId } } }))),
    staleTime: 30_000,
  });

/** RN-03. El presupuesto de control de la línea base: una fila por tipo de partida. */
export const controlOptions = (api: ClienteApi, lineaBaseId: string) =>
  queryOptions({
    queryKey: clavesLineaBase.control(lineaBaseId),
    queryFn: async () =>
      exigir(
        await pedir(() =>
          api.GET("/api/v1/lineas-base/{linea_base_id}/presupuesto-control", {
            params: { path: { linea_base_id: lineaBaseId } },
          }),
        ),
      ),
    staleTime: 30_000,
  });

/** RN-01. El congelado. Devuelve el resultado tal cual; la invalidación la hace quien la llama. */
export function congelarLineaBase(
  api: ClienteApi,
  lineaBaseId: string,
  motivo: string,
): Promise<ResultadoApi<LineaBase>> {
  return pedir(() =>
    api.POST("/api/v1/lineas-base/{linea_base_id}/congelacion", {
      params: { path: { linea_base_id: lineaBaseId } },
      body: { motivo },
    }),
  );
}

/** RN-03. Captura o recaptura del tope de un tipo de partida. La regla la evalúa el servidor; la confirmación del tope superior y la recaptura se registran con RN-04. */
export function capturarTope(
  api: ClienteApi,
  lineaBaseId: string,
  tipoPartidaId: string,
  cuerpo: CapturaPresupuestoControl,
): Promise<ResultadoApi<PresupuestoControl>> {
  return pedir(() =>
    api.PUT("/api/v1/lineas-base/{linea_base_id}/presupuesto-control/{tipo_partida_id}", {
      params: { path: { linea_base_id: lineaBaseId, tipo_partida_id: tipoPartidaId } },
      body: cuerpo,
    }),
  );
}

/** D-1, D-2. Qué línea base enseña la pantalla: la `CONGELADA` si hay; si no y `verBorrador`, el `BORRADOR`
 *  de mayor versión, sin depender del orden de la lista; una `SUPERSEDIDA`, nunca. Es presentación, no seguridad. */
export function lineaBaseMostrada(lineas: readonly LineaBase[], verBorrador: boolean): LineaBase | null {
  const congelada = lineas.find((linea) => linea.estado === "CONGELADA");
  if (congelada !== undefined) return congelada;
  if (!verBorrador) return null;
  return lineas
    .filter((linea) => linea.estado === "BORRADOR")
    .reduce<LineaBase | null>((mayor, linea) => (mayor === null || linea.version > mayor.version ? linea : mayor), null);
}
