import { useState } from "react";
import type { ClienteApi, ResultadoApi } from "@/api/cliente";
import type { Accion, ErrorApi, ErrorBloqueo } from "@/api/errores";
import type { components } from "@/api/generado/servidor";
import { darDeBajaProveedor, desactivarProveedor } from "./proveedores.consultas";

type Proveedor = components["schemas"]["Proveedor"];

/** Las dos operaciones de estado que piden motivo: cada una con su título, su confirmación y su función tipada. */
export type VerboEstado = "DESACTIVAR" | "DAR_DE_BAJA";
export const TITULO_MOTIVO: Readonly<Record<VerboEstado, (nombre: string) => string>> = {
  DESACTIVAR: (nombre) => `Desactivar a ${nombre}`,
  DAR_DE_BAJA: (nombre) => `Dar de baja a ${nombre}`,
};
export const ETIQUETA_CONFIRMAR_MOTIVO: Readonly<Record<VerboEstado, string>> = {
  DESACTIVAR: "Confirmar desactivación",
  DAR_DE_BAJA: "Confirmar baja",
};
export const OPERACION_DE_ESTADO: Readonly<
  Record<VerboEstado, (api: ClienteApi, proveedorId: string, motivo: string) => Promise<ResultadoApi<Proveedor>>>
> = {
  DESACTIVAR: desactivarProveedor,
  DAR_DE_BAJA: darDeBajaProveedor,
};

/** Una operación de estado en curso: siempre con el proveedor de la fila (o del bloqueo) sobre el que se pidió. */
export interface OperacionEnCurso {
  verbo: VerboEstado;
  proveedor: Proveedor;
}

/** Un 409 con la operación y el proveedor que lo provocaron: sus acciones y su reintento operan sobre ese proveedor. */
export interface BloqueoEstado extends OperacionEnCurso {
  error: ErrorBloqueo;
}

/** Un rechazo que se avisa en la cabecera, con su referencia si el servidor la trae. */
export interface AvisoCabecera {
  texto: string;
  referencia: string | null;
}

const CLAVE_DESACTIVAR_PROVEEDOR = "DESACTIVAR_PROVEEDOR";

function esBloqueo(error: ErrorApi): error is ErrorBloqueo {
  return error.tipo === "REGLA_NEGOCIO" || error.tipo === "CONFLICTO" || error.tipo === "CONCURRENCIA";
}

/**
 * Las operaciones de estado del catálogo (desactivar y dar de baja): la operación con el diálogo de motivo abierto y el
 * 409 que dejó, con su proveedor. El aviso de cabecera es de la pantalla: aquí solo se fija o se limpia.
 */
export function useOperacionDeEstado(refrescar: () => void, fijarAviso: (aviso: AvisoCabecera | null) => void) {
  // La operación de estado con el diálogo de motivo abierto, y el 409 que dejó (con su proveedor), si lo hubo.
  const [operacion, setOperacion] = useState<OperacionEnCurso | null>(null);
  const [bloqueo, setBloqueo] = useState<BloqueoEstado | null>(null);

  function abrirMotivo(verbo: VerboEstado, proveedor: Proveedor) {
    fijarAviso(null);
    setBloqueo(null);
    setOperacion({ verbo, proveedor });
  }

  // Un 409 es un bloqueo con su dato; lo demás, un aviso con el mensaje del servidor. Un estado ya cambiado o un
  // proveedor desaparecido dejan la lista desactualizada: se vuelve a pedir.
  function rechazar(error: ErrorApi, actual: OperacionEnCurso) {
    setOperacion(null);
    if (esBloqueo(error)) {
      setBloqueo({ ...actual, error });
      if (error.tipo === "CONFLICTO" && error.codigo === "ESTADO_NO_PERMITE_OPERACION") refrescar();
      return;
    }
    if (error.tipo === "NO_ENCONTRADO") refrescar();
    fijarAviso(
      error.tipo === "RED"
        ? { texto: "No se pudo completar la operación.", referencia: null }
        : { texto: error.mensaje ?? "No se pudo completar la operación.", referencia: error.correlacion_id },
    );
  }

  // Las acciones del bloqueo son las que mandó el servidor y operan sobre el proveedor que se intentó operar.
  function alAccionBloqueo(accion: Accion, actual: BloqueoEstado) {
    if (accion.clave === CLAVE_DESACTIVAR_PROVEEDOR) abrirMotivo("DESACTIVAR", actual.proveedor);
  }

  /** Cierra el diálogo de motivo (al cancelar o al terminar); el bloqueo ya se limpió al abrirlo. */
  function cerrar() {
    setOperacion(null);
  }

  function cerrarBloqueo() {
    setBloqueo(null);
  }

  return { operacion, bloqueo, abrirMotivo, rechazar, alAccionBloqueo, cerrar, cerrarBloqueo };
}
