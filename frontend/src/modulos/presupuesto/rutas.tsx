import type { RouteObject } from "react-router";
import { GuardaSeccion } from "@/app/armazon/GuardaSeccion";
import { type ClaveSeccion, seccion } from "@/app/navegacion/secciones";
import { ElegirObra } from "@/modulos/presupuesto/linea-base/ElegirObra";
import { PantallaLineaBase } from "@/modulos/presupuesto/linea-base/PantallaLineaBase";
import { PantallaObras } from "@/modulos/presupuesto/obras/PantallaObras";

/** D-7 · La sección conserva su ruta del menú y remite a «Obras» mientras no haya selector de obra. */
function rutaElegirObra(clave: ClaveSeccion): RouteObject {
  return {
    path: seccion(clave).ruta.slice(1),
    element: (
      <GuardaSeccion clave={clave}>
        <ElegirObra clave={clave} />
      </GuardaSeccion>
    ),
  };
}

export const rutasPresupuesto: RouteObject[] = [
  rutaElegirObra("LINEA_BASE"),
  rutaElegirObra("PRESUPUESTO_CONTROL"),
  { path: "obras", element: <GuardaSeccion clave="OBRAS"><PantallaObras /></GuardaSeccion> },
  { path: "obras/:obraId/linea-base", element: <GuardaSeccion clave="LINEA_BASE"><PantallaLineaBase /></GuardaSeccion> },
];
