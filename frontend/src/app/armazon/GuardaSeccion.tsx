import type { ReactNode } from "react";
import { AvisoSinPermiso } from "@/app/armazon/AvisoSinPermiso";
import { useSesion } from "@/api/sesion";
import { type ClaveSeccion, seccionPermitida } from "@/app/navegacion/secciones";

/** Cortesía de navegación (PA-T8): el control real es el 403 del servidor. Sin sesión cargada no decide nada. */
export function GuardaSeccion({ clave, children }: { clave: ClaveSeccion; children: ReactNode }) {
  const sesion = useSesion();
  if (sesion.data === undefined) return null;
  return seccionPermitida(clave, sesion.data.roles) ? children : <AvisoSinPermiso />;
}
