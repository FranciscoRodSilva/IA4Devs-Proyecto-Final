import { describe, expect, test } from "vitest";
import type { components } from "@/api/generado/servidor";
import { lineaBase } from "@/pruebas/cuerpos";
import { lineaBaseMostrada } from "./linea-base.consultas";

// TKT-018a · A1. Qué línea base enseña la pantalla cuando la obra tiene varias (D-2) y a quién se le oculta
// el borrador (D-1). Es presentación: el servidor devuelve la lista completa a los tres roles de lectura.

type LineaBase = components["schemas"]["LineaBase"];
type Estado = LineaBase["estado"];

/** Una versión de la línea base con identificador propio, para que cada caso distinga cuál se eligió. */
function version(numero: number, estado: Estado): LineaBase {
  const congelado =
    estado === "BORRADOR"
      ? {}
      : {
          congelada_en: "2026-10-13T18:30:00Z",
          congelada_por: { id: "0b6f1c3e-2d4a-4e5f-8a7b-9c0d1e2f3a4b", nombre: "J. Ramírez" },
          motivo: "Contrato firmado el 13-oct-2026",
        };
  return lineaBase({
    id: `e3b5c847-4a6f-4d9c-bf05-00000000000${String(numero)}`,
    version: numero,
    estado,
    ...congelado,
  });
}

describe("TKT-018a · lineaBaseMostrada", () => {
  const v1Congelada = version(1, "CONGELADA");
  const v2Borrador = version(2, "BORRADOR");
  const v3Borrador = version(3, "BORRADOR");
  const v2Supersedida = version(2, "SUPERSEDIDA");
  const v1Supersedida = version(1, "SUPERSEDIDA");
  const v1Borrador = version(1, "BORRADOR");

  // TC-01 · D-2 · CA-12. Con `verBorrador` (Director de Proyectos y Dirección General).
  test("tkt018a_d2 · qué línea base se muestra: con borrador v2 y congelada v1, la congelada", () => {
    expect(lineaBaseMostrada([v2Borrador, v1Congelada], true)).toEqual(v1Congelada);
  });

  test("tkt018a_d2 · qué línea base se muestra: la congelada también si la lista llega en orden inverso", () => {
    expect(lineaBaseMostrada([v1Congelada, v2Borrador], true)).toEqual(v1Congelada);
  });

  test("tkt018a_d2 · qué línea base se muestra: sin congelada, el borrador v3 y nunca una supersedida", () => {
    expect(lineaBaseMostrada([v3Borrador, v2Supersedida, v1Supersedida], true)).toEqual(v3Borrador);
  });

  // Orden ascendente a propósito: «tomar el primer borrador» devolvería la v2.
  test("tkt018a_d2 · qué línea base se muestra: entre dos borradores, el de mayor versión", () => {
    expect(lineaBaseMostrada([v2Borrador, v3Borrador], true)).toEqual(v3Borrador);
  });

  test("tkt018a_d2 · qué línea base se muestra: solo una supersedida, ninguna", () => {
    expect(lineaBaseMostrada([v1Supersedida], true)).toBeNull();
  });

  test("tkt018a_d2 · qué línea base se muestra: la obra sin líneas base, ninguna", () => {
    expect(lineaBaseMostrada([], true)).toBeNull();
  });

  // TC-02 · D-1 · CA-13 (rechazo). Sin `verBorrador` (COMPRAS).
  test("tkt018a_ca13 · sin ver borrador: con solo un borrador no se muestra ninguna", () => {
    expect(lineaBaseMostrada([v1Borrador], false)).toBeNull();
  });

  test("tkt018a_ca13 · sin ver borrador: con borrador v2 y congelada v1, la congelada", () => {
    expect(lineaBaseMostrada([v2Borrador, v1Congelada], false)).toEqual(v1Congelada);
  });
});
