import type { Rol } from "@/api/sesion";

export type ClaveSeccion =
  | "SEMAFORO"
  | "LINEA_BASE"
  | "PRESUPUESTO_CONTROL"
  | "REQUISICIONES"
  | "ORDENES_COMPRA"
  | "PROVEEDORES"
  | "RECEPCION"
  | "AUTORIZACIONES"
  | "BITACORA";

export interface Seccion {
  clave: ClaveSeccion;
  grupo: "Obra" | "Compras" | "Almacén" | "Dirección";
  titulo: string;
  ruta: string;
  roles: readonly Rol[];
}

const TODOS: readonly Rol[] = [
  "DIRECCION_GENERAL",
  "DIRECTOR_PROYECTOS",
  "RESIDENTE",
  "COMPRAS",
  "ALMACEN",
  "ADMINISTRACION",
];

/** M5 · wireframe §2. Cortesía de navegación (PA-T8): el control real es el 403 del servidor. */
export const SECCIONES: readonly Seccion[] = [
  { clave: "SEMAFORO", grupo: "Obra", titulo: "Semáforo", ruta: "/obra/semaforo", roles: ["DIRECCION_GENERAL", "DIRECTOR_PROYECTOS"] },
  { clave: "LINEA_BASE", grupo: "Obra", titulo: "Línea base", ruta: "/obra/linea-base", roles: ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL", "COMPRAS"] },
  { clave: "PRESUPUESTO_CONTROL", grupo: "Obra", titulo: "Presupuesto de control", ruta: "/obra/presupuesto-control", roles: ["DIRECCION_GENERAL", "DIRECTOR_PROYECTOS", "COMPRAS"] },
  { clave: "REQUISICIONES", grupo: "Compras", titulo: "Requisiciones", ruta: "/compras/requisiciones", roles: ["COMPRAS", "DIRECCION_GENERAL", "DIRECTOR_PROYECTOS"] },
  { clave: "ORDENES_COMPRA", grupo: "Compras", titulo: "Órdenes de compra", ruta: "/compras/ordenes-compra", roles: ["COMPRAS", "ALMACEN", "RESIDENTE", "DIRECCION_GENERAL", "DIRECTOR_PROYECTOS"] },
  { clave: "PROVEEDORES", grupo: "Compras", titulo: "Proveedores", ruta: "/compras/proveedores", roles: TODOS },
  { clave: "RECEPCION", grupo: "Almacén", titulo: "Recepción · Pendientes de recibir", ruta: "/almacen/recepcion", roles: ["ALMACEN", "RESIDENTE", "COMPRAS", "DIRECCION_GENERAL", "DIRECTOR_PROYECTOS"] },
  { clave: "AUTORIZACIONES", grupo: "Dirección", titulo: "Autorizaciones", ruta: "/direccion/autorizaciones", roles: ["DIRECCION_GENERAL"] },
  { clave: "BITACORA", grupo: "Dirección", titulo: "Bitácora de excepciones", ruta: "/direccion/bitacora", roles: ["DIRECCION_GENERAL", "DIRECTOR_PROYECTOS"] },
];

export const NOMBRE_ROL: Readonly<Record<Rol, string>> = {
  DIRECCION_GENERAL: "Dirección General",
  DIRECTOR_PROYECTOS: "Director de Proyectos",
  RESIDENTE: "Residente de obra",
  COMPRAS: "Compras",
  ALMACEN: "Almacén",
  ADMINISTRACION: "Administración",
};

/** La unión de los roles, en el orden de la tabla y sin repetir (CA-7 esc. 2). */
export function seccionesDe(roles: readonly Rol[]): Seccion[] {
  return SECCIONES.filter((s) => s.roles.some((r) => roles.includes(r)));
}

/** PA-T2: la primera de la tabla que permite alguno de los roles; null sin roles. */
export function primeraSeccion(roles: readonly Rol[]): Seccion | null {
  return seccionesDe(roles)[0] ?? null;
}

export function seccionPermitida(clave: ClaveSeccion, roles: readonly Rol[]): boolean {
  return seccionesDe(roles).some((s) => s.clave === clave);
}

/** La entrada de SECCIONES con esa clave. Lanza si no existe: una clave ajena al catálogo es un error de programación. */
export function seccion(clave: ClaveSeccion): Seccion {
  const encontrada = SECCIONES.find((s) => s.clave === clave);
  if (encontrada === undefined) throw new Error(`Sección desconocida: ${clave}`);
  return encontrada;
}
