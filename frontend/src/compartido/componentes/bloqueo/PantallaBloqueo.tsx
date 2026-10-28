import type { Accion, ErrorBloqueo } from "@/api/errores";
import { BotonesAcciones } from "./BotonesAcciones";
import { CabeceraBloqueo } from "./CabeceraBloqueo";
import { DetalleCifras } from "./DetalleCifras";

export interface PropsPantallaBloqueo {
  /** Solo los 409: un 422 o un 403 no compilan (CA-9 esc. 4). */
  error: ErrorBloqueo;
  /** Entrega la acción tal como llegó, sin invocarla. */
  alAccion: (accion: Accion) => void;
  alCerrar: () => void;
  /** La pantalla que la abrió repite su petición original. */
  alReintentar?: () => void;
}

/** El estado bloqueado: un rechazo de negocio con su dato y sus salidas. No es un error (RN-03, RN-07). */
export function PantallaBloqueo({ error, alAccion, alCerrar, alReintentar }: PropsPantallaBloqueo) {
  return (
    <section
      aria-labelledby="titulo-bloqueo"
      data-estado="bloqueado"
      className="rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-950"
    >
      <CabeceraBloqueo error={error} id="titulo-bloqueo" tamano="bloque" />
      <p className="mt-2">{error.mensaje}</p>
      <DetalleCifras detalle={error.detalle} />
      <BotonesAcciones
        key={error.correlacion_id}
        acciones={error.acciones}
        alAccion={alAccion}
        alCerrar={alCerrar}
        alReintentar={alReintentar}
        esperaReintentoS={error.tipo === "CONCURRENCIA" ? error.reintentar_tras_s : null}
      />
      <p className="mt-4 text-xs text-amber-900/80">Referencia: {error.correlacion_id}</p>
    </section>
  );
}
