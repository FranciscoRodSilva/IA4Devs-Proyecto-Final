import { Navigate } from "react-router";
import { useSesion } from "@/api/sesion";
import { primeraSeccion } from "@/app/navegacion/secciones";

/** CA-6 esc. 1 · la raíz del armazón lleva a la primera sección que el rol permite. Sin roles, lo dice (PA-T3). */
export function InicioArmazon() {
  const sesion = useSesion();
  if (sesion.data === undefined) return null;
  const primera = primeraSeccion(sesion.data.roles);
  if (primera === null) {
    return <p className="p-6">No tienes secciones asignadas. Pide a un administrador que te asigne un rol.</p>;
  }
  return <Navigate to={primera.ruta} replace />;
}
