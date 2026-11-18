import type { Accion } from "@/api/errores";
import type { components } from "@/api/generado/servidor";
import type { Rol } from "@/api/sesion";

/** Lo que una fila de «Obras» puede ofrecer (TKT-012b CA-14). */
export type AccionDeFila = "EDITAR" | "ELIMINAR" | "SUSPENDER" | "REACTIVAR" | "CERRAR";

/**
 * Quien opera las obras: el Director de Proyectos y la Dirección General (ROLES_ALTA de D-2 y de la alta, TKT-012a).
 * La alta y la columna «Acciones» de PantallaObras leen esta misma constante. `ROLES_QUE_VEN_BORRADOR` de la línea
 * base no se toca: su conjunto coincide hoy, pero es otra regla de lectura.
 */
export const ROLES_QUE_OPERAN: readonly Rol[] = ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL"];

/** CA-14. PLANEACION admite «Cerrar» (D-2: PLANEACION → CERRADA). La obra CERRADA no ofrece nada. */
const ACCIONES_POR_ESTADO: Readonly<Record<components["schemas"]["EstadoObra"], readonly AccionDeFila[]>> = {
  PLANEACION: ["EDITAR", "ELIMINAR", "CERRAR"],
  ACTIVA: ["EDITAR", "SUSPENDER", "CERRAR"],
  SUSPENDIDA: ["EDITAR", "REACTIVAR", "CERRAR"],
  CERRADA: [],
};

/**
 * Qué ofrece la fila según el estado y el rol. Es cortesía de navegación: el control real es el 403 y el 409 del
 * servidor. Devuelve una lista nueva en cada llamada, así que quien la modifica no altera la siguiente.
 */
export function accionesDeFila(estado: components["schemas"]["EstadoObra"], roles: readonly Rol[]): AccionDeFila[] {
  const opera = roles.some((rol) => ROLES_QUE_OPERAN.includes(rol));
  return opera ? [...ACCIONES_POR_ESTADO[estado]] : [];
}

/** Las claves de acción que esta pantalla sabe ejecutar desde el bloqueo de una baja (TKT-012b B4, CA-16). */
const CLAVES_EJECUTABLES_EN_BAJA: ReadonlySet<string> = new Set(["SUSPENDER_OBRA", "CERRAR_OBRA"]);

/**
 * De las acciones que trae el contrato, las que el cliente sabe ejecutar, en su orden. El contrato decide cuáles se
 * ofrecen; el cliente no pinta una clave que no sabe cumplir (TC-78). Devuelve una lista nueva.
 */
export function accionesEjecutablesEnBaja(acciones: readonly Accion[]): Accion[] {
  return acciones.filter((accion) => CLAVES_EJECUTABLES_EN_BAJA.has(accion.clave));
}
