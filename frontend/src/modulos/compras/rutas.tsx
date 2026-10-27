import type { RouteObject } from "react-router";
import { rutaMarcador } from "@/app/navegacion/ruta-marcador";

export const rutasCompras: RouteObject[] = [
  rutaMarcador("REQUISICIONES"),
  rutaMarcador("ORDENES_COMPRA"),
  rutaMarcador("AUTORIZACIONES"),
];
