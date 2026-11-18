import { FalloApi } from "@/api/cliente";
import type { ErrorApi } from "@/api/errores";
import { Button } from "@/components/ui/button";

/** El error de la consulta, si es el de la capa de API. Cualquier otra cosa no tiene detalle que pintar. */
function errorDe(fallo: unknown): ErrorApi | null {
  return fallo instanceof FalloApi ? fallo.error : null;
}

/** Cargando: un esqueleto con su etiqueta accesible, no un contenido vacío. */
export function EsqueletoLista() {
  return (
    <div role="status" aria-busy="true" aria-label="Cargando los proveedores" className="space-y-2">
      {[0, 1, 2].map((indice) => (
        <div key={indice} className="h-8 animate-pulse rounded bg-muted" />
      ))}
    </div>
  );
}

/** Error: el mensaje del servidor (o el genérico), la referencia si la trae y «Reintentar». */
export function AvisoErrorLista({ error, alReintentar }: { error: unknown; alReintentar: () => void }) {
  const detalle = errorDe(error);
  const mensaje = detalle !== null && "mensaje" in detalle ? detalle.mensaje : null;
  const referencia = detalle !== null && "correlacion_id" in detalle ? detalle.correlacion_id : null;
  return (
    <div role="alert" className="grid gap-2 rounded-md border border-destructive/40 p-4 text-sm">
      <p>{mensaje ?? "No se pudo cargar la lista de proveedores."}</p>
      {referencia === null ? null : <p>Referencia: {referencia}</p>}
      <div>
        <Button type="button" variant="outline" onClick={alReintentar}>
          Reintentar
        </Button>
      </div>
    </div>
  );
}

/** Vacío: la invitación al + solo se dice con el filtro por omisión y a quien puede dar de alta. */
export function SinProveedores({ invitarAlta }: { invitarAlta: boolean }) {
  return (
    <div className="grid gap-1 rounded-md border p-6 text-center">
      <p className="font-medium">No hay proveedores con este filtro</p>
      {invitarAlta ? <p className="text-sm text-muted-foreground">Da de alta el primer proveedor con el botón +.</p> : null}
    </div>
  );
}
