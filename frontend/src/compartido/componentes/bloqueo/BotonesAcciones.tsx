import type { Accion } from "@/api/errores";
import { Button } from "@/components/ui/button";
import { useCuentaAtras } from "@/compartido/tiempo/useCuentaAtras";
import { ETIQUETAS_ACCION } from "./etiquetas";

const CLAVE_REINTENTAR = "REINTENTAR";

export interface PropsBotonesAcciones {
  /** Las acciones del servidor, ya filtradas por rol; pueden venir ausentes. */
  acciones: readonly Accion[] | undefined;
  /** Entrega la acción tal como llegó, sin invocarla. */
  alAccion: (accion: Accion) => void;
  /** Si se omite, no se pinta «Cerrar» (lo usa `ConflictoEnLinea`). */
  alCerrar?: () => void;
  /** Si existe, «Reintentar» la llama en lugar de entregar la acción. */
  alReintentar?: () => void;
  /** Segundos de espera antes de poder reintentar (`Retry-After`). */
  esperaReintentoS?: number | null;
}

function etiquetaDe(clave: string): string {
  return Object.hasOwn(ETIQUETAS_ACCION, clave) ? (ETIQUETAS_ACCION[clave] ?? clave) : clave;
}

/** Un botón por acción del servidor, en su orden, y después «Cerrar». */
export function BotonesAcciones({ acciones, alAccion, alCerrar, alReintentar, esperaReintentoS = null }: PropsBotonesAcciones) {
  const restantes = useCuentaAtras(esperaReintentoS);

  function pulsar(accion: Accion) {
    if (accion.clave === CLAVE_REINTENTAR && alReintentar !== undefined) alReintentar();
    else alAccion(accion);
  }

  return (
    <div className="mt-4 flex flex-wrap items-center gap-2">
      {(acciones ?? []).map((accion, indice) => {
        const esperando = accion.clave === CLAVE_REINTENTAR && restantes > 0;
        return (
          <Button key={`${accion.clave}-${indice}`} type="button" disabled={esperando} onClick={() => pulsar(accion)}>
            {etiquetaDe(accion.clave)}
          </Button>
        );
      })}
      {alCerrar === undefined ? null : (
        <Button type="button" variant="outline" onClick={alCerrar}>
          Cerrar
        </Button>
      )}
    </div>
  );
}
