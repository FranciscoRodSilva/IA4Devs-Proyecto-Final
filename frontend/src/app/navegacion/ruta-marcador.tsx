import type { RouteObject } from "react-router";
import { GuardaSeccion } from "@/app/armazon/GuardaSeccion";
import { SeccionMarcador } from "@/app/armazon/SeccionMarcador";
import { type ClaveSeccion, seccion } from "@/app/navegacion/secciones";

/** Ruta hija de la sección, relativa al armazón («/»): sin la barra inicial de su ruta. */
export function rutaMarcador(clave: ClaveSeccion): RouteObject {
  return {
    path: seccion(clave).ruta.slice(1),
    element: (
      <GuardaSeccion clave={clave}>
        <SeccionMarcador clave={clave} />
      </GuardaSeccion>
    ),
  };
}
