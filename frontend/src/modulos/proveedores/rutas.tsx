import type { RouteObject } from "react-router";
import { GuardaSeccion } from "@/app/armazon/GuardaSeccion";
import { seccion } from "@/app/navegacion/secciones";
import { PantallaProveedores } from "./catalogo/PantallaProveedores";

export const rutasProveedores: RouteObject[] = [
  {
    path: seccion("PROVEEDORES").ruta.slice(1),
    element: (
      <GuardaSeccion clave="PROVEEDORES">
        <PantallaProveedores />
      </GuardaSeccion>
    ),
  },
];
