import type { RouteObject } from "react-router";
import { rutaMarcador } from "@/app/navegacion/ruta-marcador";

export const rutasPresupuesto: RouteObject[] = [rutaMarcador("LINEA_BASE"), rutaMarcador("PRESUPUESTO_CONTROL")];
