import { describe, expect, test } from "vitest";
import type { Rol } from "@/api/sesion";
import { primeraSeccion, seccionesDe, seccionPermitida } from "./secciones";

// Las secciones por rol son la tabla del wireframe §2 (unión de «Opera» y «Consulta»), en su orden.
// Es una cortesía de navegación (PA-T8): el control real es el 403 del servidor.

function titulosDe(roles: Rol[]): string[] {
  return seccionesDe(roles).map((s) => s.titulo);
}

// D-3 · fila B3 de TKT-012a: «Obras» se añade al final de la tabla del wireframe §2 (visible a los seis roles).
// Las listas de abajo ya la incluyen; el resto de cada lista es el de TKT-008, sin cambios.
const TITULOS_DE_LAS_DIEZ = [
  "Semáforo",
  "Línea base",
  "Presupuesto de control",
  "Requisiciones",
  "Órdenes de compra",
  "Proveedores",
  "Recepción · Pendientes de recibir",
  "Autorizaciones",
  "Bitácora de excepciones",
  "Obras",
];

describe("TKT-008 · secciones por rol", () => {
  test("tkt008_ca07_esc01 · ALMACEN", () => {
    // D-3 · fila B3 de TKT-012a: «Obras» al final de la lista de ALMACEN, en el orden de la tabla.
    expect(titulosDe(["ALMACEN"])).toEqual(["Órdenes de compra", "Proveedores", "Recepción · Pendientes de recibir", "Obras"]);
  });

  test("tkt008_ca07_esc02 · unión sin repetir", () => {
    // D-3 · fila B3 de TKT-012a: «Obras» al final de la unión, en el orden de la tabla.
    expect(titulosDe(["COMPRAS", "ALMACEN"])).toEqual([
      "Línea base",
      "Presupuesto de control",
      "Requisiciones",
      "Órdenes de compra",
      "Proveedores",
      "Recepción · Pendientes de recibir",
      "Obras",
    ]);
  });

  test("tkt008_ca07 · la tabla del wireframe", () => {
    // D-3 · fila B3 de TKT-012a: la tabla del wireframe §2 gana «Obras» al final, para los seis roles.
    const esperado: Record<Rol, string[]> = {
      DIRECCION_GENERAL: TITULOS_DE_LAS_DIEZ,
      DIRECTOR_PROYECTOS: [
        "Semáforo",
        "Línea base",
        "Presupuesto de control",
        "Requisiciones",
        "Órdenes de compra",
        "Proveedores",
        "Recepción · Pendientes de recibir",
        "Bitácora de excepciones",
        "Obras",
      ],
      RESIDENTE: ["Órdenes de compra", "Proveedores", "Recepción · Pendientes de recibir", "Obras"],
      COMPRAS: [
        "Línea base",
        "Presupuesto de control",
        "Requisiciones",
        "Órdenes de compra",
        "Proveedores",
        "Recepción · Pendientes de recibir",
        "Obras",
      ],
      ALMACEN: ["Órdenes de compra", "Proveedores", "Recepción · Pendientes de recibir", "Obras"],
      ADMINISTRACION: ["Proveedores", "Obras"],
    };

    for (const rol of Object.keys(esperado) as Rol[]) {
      expect(titulosDe([rol]), `secciones de ${rol}`).toEqual(esperado[rol]);
    }
  });

  test("tkt008_ca06_esc01 · primera sección", () => {
    expect(primeraSeccion(["ALMACEN"])?.ruta).toBe("/compras/ordenes-compra");
    expect(primeraSeccion(["COMPRAS"])?.ruta).toBe("/obra/linea-base");
    expect(primeraSeccion([])).toBeNull();
  });

  test("tkt008_ca07_esc05 · sección ajena", () => {
    expect(seccionPermitida("AUTORIZACIONES", ["ALMACEN"])).toBe(false);
    expect(seccionPermitida("AUTORIZACIONES", ["DIRECCION_GENERAL"])).toBe(true);
  });

  test("tkt008_ca07_esc06 · sin roles", () => {
    expect(seccionesDe([])).toEqual([]);
  });
});

// D-3 · fila B3 de TKT-012a. «Obras» va al final de SECCIONES para no mover la primera sección de nadie (PA-T2).
describe("TKT-012a · sección Obras · D-3", () => {
  const SEIS_ROLES: Rol[] = ["DIRECCION_GENERAL", "DIRECTOR_PROYECTOS", "RESIDENTE", "COMPRAS", "ALMACEN", "ADMINISTRACION"];

  test("TKT-012a · CA-9 · TC-F05 · «Obras» está para los seis roles, en el grupo Obra y con su ruta", () => {
    for (const rol of SEIS_ROLES) {
      const obras = seccionesDe([rol]).find((s) => s.titulo === "Obras");
      expect(obras, `«Obras» para ${rol}`).toBeDefined();
      expect(obras?.ruta, `ruta de «Obras» para ${rol}`).toBe("/obras");
      expect(obras?.grupo, `grupo de «Obras» para ${rol}`).toBe("Obra");
    }
  });

  // Guarda de no regresión: nace en verde a propósito. Solo se pone en rojo si «Obras» se mete antes de la primera sección de algún rol.
  test("TKT-012a · CA-9 · TC-F05 · primeraSeccion de cada rol no cambia", () => {
    const esperado: Record<Rol, string> = {
      DIRECCION_GENERAL: "/obra/semaforo",
      DIRECTOR_PROYECTOS: "/obra/semaforo",
      RESIDENTE: "/compras/ordenes-compra",
      COMPRAS: "/obra/linea-base",
      ALMACEN: "/compras/ordenes-compra",
      ADMINISTRACION: "/compras/proveedores",
    };
    for (const rol of SEIS_ROLES) {
      expect(primeraSeccion([rol])?.ruta, `primeraSeccion de ${rol}`).toBe(esperado[rol]);
    }
  });
});
