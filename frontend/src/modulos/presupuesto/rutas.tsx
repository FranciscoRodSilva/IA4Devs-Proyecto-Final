import type { RouteObject } from "react-router";
import { GuardaSeccion } from "@/app/armazon/GuardaSeccion";
import { rutaMarcador } from "@/app/navegacion/ruta-marcador";
import { PantallaObras } from "@/modulos/presupuesto/obras/PantallaObras";

export const rutasPresupuesto: RouteObject[] = [
  rutaMarcador("LINEA_BASE"),
  rutaMarcador("PRESUPUESTO_CONTROL"),
  { path: "obras", element: <GuardaSeccion clave="OBRAS"><PantallaObras /></GuardaSeccion> },
];
