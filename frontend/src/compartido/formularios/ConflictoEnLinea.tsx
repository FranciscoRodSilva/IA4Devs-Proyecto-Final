import { useId } from "react";
import type { Accion, ErrorBloqueo } from "@/api/errores";
import { BotonesAcciones } from "@/compartido/componentes/bloqueo/BotonesAcciones";
import { CabeceraBloqueo } from "@/compartido/componentes/bloqueo/CabeceraBloqueo";
import { DetalleCifras } from "@/compartido/componentes/bloqueo/DetalleCifras";

export interface PropsConflictoEnLinea {
  /** Un 409 de cualquier tipo: el rechazo se pinta junto al formulario, no en una pantalla aparte. */
  error: ErrorBloqueo;
  /** Entrega la acción tal como llegó, sin invocarla. */
  alAccion: (accion: Accion) => void;
  /** Región viva propia. El formulario aporta una persistente y pasa `false` para no anunciar el conflicto dos veces. */
  regionViva?: boolean;
}

/** El estado bloqueado dentro del formulario: su cabecera en tamaño de línea, el registro que lo causa y sus acciones, sin «Cerrar». */
export function ConflictoEnLinea({ error, alAccion, regionViva = true }: PropsConflictoEnLinea) {
  const idTitulo = useId();
  return (
    <section
      aria-labelledby={idTitulo}
      data-estado="bloqueado"
      aria-live={regionViva ? "polite" : undefined}
      className="rounded-md border border-amber-300 bg-amber-50 p-3 text-sm text-amber-950"
    >
      <CabeceraBloqueo error={error} id={idTitulo} tamano="linea" />
      <p className="mt-1">{error.mensaje}</p>
      <DetalleCifras detalle={error.detalle} />
      <BotonesAcciones
        key={error.correlacion_id}
        acciones={error.acciones}
        alAccion={alAccion}
        esperaReintentoS={error.tipo === "CONCURRENCIA" ? error.reintentar_tras_s : null}
      />
    </section>
  );
}
