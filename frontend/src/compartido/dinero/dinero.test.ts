import { describe, expect, test } from "vitest";
import { Decimal, aDecimal, enteroNoNegativo, formatearCantidad, formatearImporte } from "./dinero";

// El módulo de dinero es el único que puede construir un Decimal. Estas pruebas lo importan de aquí y nunca
// de `decimal.js` (la regla de ESLint lo prohíbe fuera de `src/compartido/dinero`, también en las pruebas
// de otras carpetas). Las cifras entran siempre como cadena, como las envía el servidor.

/** Una cifra de prueba que se sabe válida: si no lo es, el fallo es de la prueba y no del módulo. */
function decimalDe(valor: string): Decimal {
  const decimal = aDecimal(valor);
  if (decimal === null) throw new Error(`Cifra de prueba inválida: ${valor}`);
  return decimal;
}

const CIFRAS_INVALIDAS = ["abc", "1e3", "Infinity", "NaN", "0x10", ""];

describe("TKT-008 · dinero del cliente", () => {
  test("tkt008_ca13_esc01 · suma exacta", () => {
    const suma = decimalDe("0.1000").plus(decimalDe("0.2000"));

    expect(suma).toBeInstanceOf(Decimal);
    expect(formatearImporte(suma)).toBe("$0.30");
  });

  test("tkt008_ca13_esc02 · redondeo al presentar", () => {
    expect(formatearImporte("1234.5650")).toBe("$1,234.57");
    // El redondeo ocurre solo al presentar: el valor conserva sus cuatro decimales.
    expect(decimalDe("1234.5650").toFixed(4)).toBe("1234.5650");
  });

  test("tkt008_ca13_esc02 · sin pasar por number", () => {
    // Pasado por `Number`, este importe sale «$12,345,678,901,234.56»: ya perdió exactitud antes de formatear.
    expect(formatearImporte("12345678901234.5650")).toBe("$12,345,678,901,234.57");
  });

  test("tkt008_ca08_esc05 · cifra inválida", () => {
    for (const cifra of CIFRAS_INVALIDAS) {
      expect(aDecimal(cifra), `aDecimal(${JSON.stringify(cifra)})`).toBeNull();
      expect(formatearImporte(cifra), `formatearImporte(${JSON.stringify(cifra)})`).toBeNull();
      expect(formatearCantidad(cifra), `formatearCantidad(${JSON.stringify(cifra)})`).toBeNull();
    }
  });

  test("tkt008_ca13_esc02 · negativo", () => {
    expect(formatearImporte("-3000.0000")).toBe("-$3,000.00");
  });

  test("tkt008_ca13_esc02 · TC-F4 · un negativo que redondea a cero no lleva signo", () => {
    // Ciclo de corrección 1 · F004. `toFixed(2)` de "-0.0040" da "-0.00" y Intl conserva el signo.
    expect(formatearImporte("-0.0040")).toBe("$0.00");
    expect(formatearCantidad("-0.0010")).toBe("0.00");
  });

  // Revisión · C003. `new Decimal(1).div(0)` es Infinity: el módulo no puede dibujar «∞» ni «NaN» como si fueran un importe.
  const noFinitos = [
    { nombre: "Infinity", valor: new Decimal(1).div(0) },
    { nombre: "NaN", valor: new Decimal(0).div(0) },
    { nombre: "-Infinity", valor: new Decimal(-1).div(0) },
  ];

  test.each(noFinitos)("tkt008_ca08_esc05 · TC-R1f · un importe $nombre no se presenta", ({ valor }) => {
    expect(formatearImporte(valor)).toBeNull();
  });

  test.each(noFinitos)("tkt008_ca08_esc05 · TC-R1g · una cantidad $nombre no se presenta", ({ valor }) => {
    expect(formatearCantidad(valor)).toBeNull();
    expect(formatearCantidad(valor, "PZA")).toBeNull();
  });

  test("tkt008_ca08_esc02 · cantidades", () => {
    expect(formatearCantidad("100.0000", "PZA")).toBe("100.00 PZA");
    expect(formatearCantidad("1234.5")).toBe("1,234.50");
  });

  test("tkt008_ca09_esc02 · Retry-After", () => {
    expect(enteroNoNegativo("2")).toBe(2);
    for (const texto of ["-1", "2.5", "abc", "", null]) {
      expect(enteroNoNegativo(texto), `enteroNoNegativo(${JSON.stringify(texto)})`).toBeNull();
    }
  });
});
