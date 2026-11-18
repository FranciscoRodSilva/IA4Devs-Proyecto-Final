import { describe, expect, test } from "vitest";
import type { components } from "@/api/generado/servidor";
import type { Rol } from "@/api/sesion";
import { type AccionDeFila, accionesDeFila } from "./obras.acciones";

// TKT-012b · fila B2 · CA-14 · TC-65 y TC-66. Qué ofrece la fila de «Obras» según el estado de la obra y el rol.
// Es cortesía de navegación: el control real es el 403 y el 409 del servidor. Solo el Director de Proyectos y la
// Dirección General operan (ROLES_ALTA); el orden de la lista es el de la spec y el de la pantalla.

type Estado = components["schemas"]["EstadoObra"];

const ROLES_QUE_OPERAN: readonly Rol[] = ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL"];
const ROLES_DE_CONSULTA: readonly Rol[] = ["COMPRAS", "ALMACEN", "RESIDENTE", "ADMINISTRACION"];
const ESTADOS: readonly Estado[] = ["PLANEACION", "ACTIVA", "SUSPENDIDA", "CERRADA"];

// CA-14 con la corrección D-DIS-1: PLANEACION también ofrece «Cerrar» (D-2 admite PLANEACION → CERRADA).
const OFRECE: ReadonlyArray<readonly [Estado, readonly AccionDeFila[]]> = [
  ["PLANEACION", ["EDITAR", "ELIMINAR", "CERRAR"]],
  ["ACTIVA", ["EDITAR", "SUSPENDER", "CERRAR"]],
  ["SUSPENDIDA", ["EDITAR", "REACTIVAR", "CERRAR"]],
  ["CERRADA", []],
];

const PRODUCTO_ROLES_Y_ESTADOS = ROLES_QUE_OPERAN.flatMap((rol) => OFRECE.map(([estado, acciones]) => [rol, estado, acciones] as const));
const PRODUCTO_CONSULTA_Y_ESTADOS = ROLES_DE_CONSULTA.flatMap((rol) => ESTADOS.map((estado) => [rol, estado] as const));

describe("TKT-012b · accionesDeFila · quien opera (CA-14, TC-65)", () => {
  test.each(PRODUCTO_ROLES_Y_ESTADOS)(
    "tkt012b_ca14 · TC-65 · %s con la obra en %s ofrece la lista de CA-14",
    (rol, estado, esperadas) => {
      expect(accionesDeFila(estado, [rol])).toEqual(esperadas);
    },
  );

  test("tkt012b_ca14 · TC-65 · D-DIS-1: la obra en PLANEACION ofrece «Cerrar» además de Editar y Eliminar", () => {
    expect(accionesDeFila("PLANEACION", ["DIRECTOR_PROYECTOS"])).toContain("CERRAR");
  });

  test("tkt012b_ca14 · TC-65 · «Eliminar» solo se ofrece en PLANEACION (CA-18: dos obras)", () => {
    const estadosConEliminar = ESTADOS.filter((estado) => accionesDeFila(estado, ["DIRECTOR_PROYECTOS"]).includes("ELIMINAR"));

    expect(estadosConEliminar).toEqual(["PLANEACION"]);
  });

  test("tkt012b_ca14 · TC-65 · la obra CERRADA no ofrece ninguna transición ni edición", () => {
    expect(accionesDeFila("CERRADA", ["DIRECTOR_PROYECTOS"])).toEqual([]);
    expect(accionesDeFila("CERRADA", ["DIRECCION_GENERAL"])).toEqual([]);
  });

  test("tkt012b_ca14 · TC-65 · una persona con varios roles opera si alguno de ellos opera", () => {
    expect(accionesDeFila("ACTIVA", ["COMPRAS", "DIRECTOR_PROYECTOS"])).toEqual(["EDITAR", "SUSPENDER", "CERRAR"]);
  });

  test("tkt012b_ca14 · TC-65 · la lista que devuelve es nueva en cada llamada: quien la cambia no altera la siguiente", () => {
    const primera = accionesDeFila("ACTIVA", ["DIRECTOR_PROYECTOS"]);
    primera.push("ELIMINAR");

    expect(accionesDeFila("ACTIVA", ["DIRECTOR_PROYECTOS"])).toEqual(["EDITAR", "SUSPENDER", "CERRAR"]);
  });
});

describe("TKT-012b · accionesDeFila · quien solo consulta (CA-14, TC-66, rechazo)", () => {
  test.each(PRODUCTO_CONSULTA_Y_ESTADOS)(
    "tkt012b_ca14 · TC-66 · %s con la obra en %s no ofrece ninguna acción",
    (rol, estado) => {
      expect(accionesDeFila(estado, [rol])).toEqual([]);
    },
  );

  test("tkt012b_ca14 · TC-66 · varios roles de consulta juntos tampoco operan", () => {
    for (const estado of ESTADOS) {
      expect(accionesDeFila(estado, ROLES_DE_CONSULTA)).toEqual([]);
    }
  });

  test("tkt012b_ca14 · TC-66 · sin roles (sesión sin cargar) la fila no ofrece nada", () => {
    for (const estado of ESTADOS) {
      expect(accionesDeFila(estado, [])).toEqual([]);
    }
  });
});
