import { describe, expect, test } from "vitest";
import { fraccionAPorcentaje, porcentajeAFraccion } from "./dinero";

// TKT-012b · fila B1 · CA-15 · TC-63. La edición de una obra precarga «15» desde la fracción «0.150000» que envía el
// servidor. Las cifras entran como cadena y salen como cadena: ninguna prueba usa `Number`, que es justo lo que se vigila.

describe("TKT-012b · fraccionAPorcentaje", () => {
  const FRACCIONES = [
    { fraccion: "0.150000", porcentaje: "15" },
    { fraccion: "0.055000", porcentaje: "5.5" },
    { fraccion: "0", porcentaje: "0" },
    { fraccion: "1", porcentaje: "100" },
    { fraccion: "1.000000", porcentaje: "100" },
    { fraccion: "0.000000", porcentaje: "0" },
    { fraccion: "0.125000", porcentaje: "12.5" },
    // Cuatro decimales de porcentaje son seis de fracción: el máximo que admite `porcentajeAFraccion`.
    { fraccion: "0.123456", porcentaje: "12.3456" },
  ];

  test.each(FRACCIONES)("tkt012b_ca15 · TC-63 · $fraccion se muestra como $porcentaje", ({ fraccion, porcentaje }) => {
    expect(fraccionAPorcentaje(fraccion)).toBe(porcentaje);
  });

  // Con aritmética de punto flotante, 0.07 * 100 da 7.000000000000001 y 0.29 * 100 da 28.999999999999996.
  const CIFRAS_QUE_ROMPE_EL_FLOTANTE = [
    { fraccion: "0.070000", porcentaje: "7" },
    { fraccion: "0.290000", porcentaje: "29" },
    { fraccion: "0.570000", porcentaje: "57" },
    { fraccion: "0.001100", porcentaje: "0.11" },
  ];

  test.each(CIFRAS_QUE_ROMPE_EL_FLOTANTE)(
    "tkt012b_ca15 · TC-63 · sin pasar por number: $fraccion es exactamente $porcentaje",
    ({ fraccion, porcentaje }) => {
      expect(fraccionAPorcentaje(fraccion)).toBe(porcentaje);
    },
  );

  test("tkt012b_ca15 · TC-63 · el resultado no arrastra ceros de relleno ni signo de más", () => {
    const resultado = fraccionAPorcentaje("0.100000");
    expect(resultado).toBe("10");
    expect(resultado).not.toMatch(/\.0+$|^0\d|^\+/);
  });

  const PORCENTAJES_TECLEADOS = ["15", "5.5", "0", "100", "12.5", "12.3456", "7", "29", "0.0001"];

  test.each(PORCENTAJES_TECLEADOS)("tkt012b_ca15 · TC-63 · ida y vuelta: %s → fracción → porcentaje", (porcentaje) => {
    const fraccion = porcentajeAFraccion(porcentaje);
    expect(fraccion, `porcentajeAFraccion(${JSON.stringify(porcentaje)})`).not.toBeNull();
    if (fraccion === null) return;
    expect(fraccionAPorcentaje(fraccion)).toBe(porcentaje);
  });

  // La vuelta (fracción → porcentaje → fracción) devuelve la fracción a seis decimales, que es como la guarda el servidor.
  const VUELTA_E_IDA = [
    { fraccion: "0.150000", normalizada: "0.150000" },
    { fraccion: "0.055000", normalizada: "0.055000" },
    { fraccion: "0", normalizada: "0.000000" },
    { fraccion: "1", normalizada: "1.000000" },
    { fraccion: "0.123456", normalizada: "0.123456" },
  ];

  test.each(VUELTA_E_IDA)("tkt012b_ca15 · TC-63 · vuelta e ida: $fraccion → porcentaje → $normalizada", ({ fraccion, normalizada }) => {
    const porcentaje = fraccionAPorcentaje(fraccion);
    expect(porcentaje, `fraccionAPorcentaje(${JSON.stringify(fraccion)})`).not.toBeNull();
    if (porcentaje === null) return;
    expect(porcentajeAFraccion(porcentaje)).toBe(normalizada);
  });

  // Rechazo · lo que no es una fracción plana no se convierte: la edición no puede precargar basura en el campo.
  // (asumido) El retorno es `null`, como en `porcentajeAFraccion`; la spec no lo fija (ver las dudas del informe de la fila).
  const FRACCIONES_NO_VALIDAS = ["", "abc", "1e-1", "0.15.0", "-0.150000", "Infinity", "NaN"];

  test.each(FRACCIONES_NO_VALIDAS)("tkt012b_ca15 · TC-63 · rechazo: %j no es una fracción", (entrada) => {
    expect(fraccionAPorcentaje(entrada), `fraccionAPorcentaje(${JSON.stringify(entrada)})`).toBeNull();
  });
});
