import { describe, expect, test } from "vitest";
import type { Rol } from "@/api/sesion";
import { primeraSeccion, seccionesDe, seccionPermitida } from "./secciones";

// Las secciones por rol son la tabla del wireframe §2 (unión de «Opera» y «Consulta»), en su orden.
// Es una cortesía de navegación (PA-T8): el control real es el 403 del servidor.

function titulosDe(roles: Rol[]): string[] {
  return seccionesDe(roles).map((s) => s.titulo);
}

const TITULOS_DE_LAS_NUEVE = [
  "Semáforo",
  "Línea base",
  "Presupuesto de control",
  "Requisiciones",
  "Órdenes de compra",
  "Proveedores",
  "Recepción · Pendientes de recibir",
  "Autorizaciones",
  "Bitácora de excepciones",
];

describe("TKT-008 · secciones por rol", () => {
  test("tkt008_ca07_esc01 · ALMACEN", () => {
    expect(titulosDe(["ALMACEN"])).toEqual(["Órdenes de compra", "Proveedores", "Recepción · Pendientes de recibir"]);
  });

  test("tkt008_ca07_esc02 · unión sin repetir", () => {
    expect(titulosDe(["COMPRAS", "ALMACEN"])).toEqual([
      "Línea base",
      "Presupuesto de control",
      "Requisiciones",
      "Órdenes de compra",
      "Proveedores",
      "Recepción · Pendientes de recibir",
    ]);
  });

  test("tkt008_ca07 · la tabla del wireframe", () => {
    const esperado: Record<Rol, string[]> = {
      DIRECCION_GENERAL: TITULOS_DE_LAS_NUEVE,
      DIRECTOR_PROYECTOS: [
        "Semáforo",
        "Línea base",
        "Presupuesto de control",
        "Requisiciones",
        "Órdenes de compra",
        "Proveedores",
        "Recepción · Pendientes de recibir",
        "Bitácora de excepciones",
      ],
      RESIDENTE: ["Órdenes de compra", "Proveedores", "Recepción · Pendientes de recibir"],
      COMPRAS: [
        "Línea base",
        "Presupuesto de control",
        "Requisiciones",
        "Órdenes de compra",
        "Proveedores",
        "Recepción · Pendientes de recibir",
      ],
      ALMACEN: ["Órdenes de compra", "Proveedores", "Recepción · Pendientes de recibir"],
      ADMINISTRACION: ["Proveedores"],
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
