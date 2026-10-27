import type { RouteObject } from "react-router";
import { Armazon } from "@/app/armazon/Armazon";
import { InicioArmazon } from "@/app/armazon/InicioArmazon";
import { NoEncontrado } from "@/app/armazon/NoEncontrado";
import { RUTA_INICIO_SESION } from "@/app/navegacion/ruta-inicio-sesion";
import { PaginaInicioSesion } from "@/modulos/identidad/PaginaInicioSesion";
import { rutasAnalitica } from "@/modulos/analitica/rutas";
import { rutasAlmacen } from "@/modulos/almacen/rutas";
import { rutasAuditoria } from "@/modulos/auditoria/rutas";
import { rutasCompras } from "@/modulos/compras/rutas";
import { rutasPresupuesto } from "@/modulos/presupuesto/rutas";
import { rutasProveedores } from "@/modulos/proveedores/rutas";

export const rutas: RouteObject[] = [
  { path: RUTA_INICIO_SESION, Component: PaginaInicioSesion },
  {
    path: "/",
    Component: Armazon,
    children: [
      { index: true, Component: InicioArmazon },
      ...rutasAnalitica,
      ...rutasPresupuesto,
      ...rutasCompras,
      ...rutasProveedores,
      ...rutasAlmacen,
      ...rutasAuditoria,
      { path: "*", Component: NoEncontrado },
    ],
  },
];
