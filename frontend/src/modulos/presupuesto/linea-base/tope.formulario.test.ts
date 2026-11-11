import { describe, expect, test } from "vitest";
import {
  esquemaRecaptura,
  esquemaTopes,
  MENSAJE_IMPORTE_TOPE,
  PATRON_IMPORTE_TOPE,
  resolverRecaptura,
  resolverTopes,
} from "./tope.formulario";

/** Las cuatro filas del control; `valor` va en MUROS y las demás quedan sin capturar. */
function topes(valor: string) {
  return { MUROS: valor, PLAFONES_Y_CAJILLOS: "", ENCHAPES: "", GENERALES: "" };
}

function recaptura(tope: string, motivo = "Ampliación de muros en nivel 9") {
  return { tope, motivo };
}

const ADMITIDAS: ReadonlyArray<readonly [descripcion: string, escrito: string, esperado: string]> = [
  ["importe con dos decimales", "45000.00", "45000.00"],
  ["cero", "0", "0"],
  ["14 enteros y 4 decimales", "12345678901234.1234", "12345678901234.1234"],
  ["con espacios alrededor, recortado", " 45000.00 ", "45000.00"],
];

const RECHAZADAS: ReadonlyArray<readonly [descripcion: string, escrito: string]> = [
  ["texto no numérico", "abc"],
  ["importe negativo", "-5"],
  ["más de cuatro decimales", "1.12345"],
  ["más de catorce enteros", "123456789012345"],
  ["notación exponencial", "1e5"],
  ["comas de millares", "45,000.00"],
  ["dígitos no ASCII", "٤٥"],
  ["salto de línea intermedio", "45000.00\n5"],
];

describe("TKT-018a · forma del tope (CA-10, TC-20)", () => {
  test("tkt018a_ca10 · el patrón del tope usa [0-9] anclado, sin dígitos no ASCII", () => {
    expect(PATRON_IMPORTE_TOPE.test("45000.00")).toBe(true);
    expect(PATRON_IMPORTE_TOPE.test("1.12345")).toBe(false);
    expect(PATRON_IMPORTE_TOPE.test("٤٥")).toBe(false);
    expect(PATRON_IMPORTE_TOPE.test("45000.00\n5")).toBe(false);
  });

  test("tkt018a_ca10 · el mensaje del tope dice cómo escribirlo", () => {
    expect(MENSAJE_IMPORTE_TOPE).toBe(
      "Escribe un importe sin signo ni comas, con hasta 14 enteros y 4 decimales, como 45000.00.",
    );
  });

  describe("esquemaTopes", () => {
    test.each(ADMITIDAS)("tkt018a_ca10 · admite %s", (_descripcion, escrito, esperado) => {
      const resultado = esquemaTopes.safeParse(topes(escrito));

      expect(resultado.success).toBe(true);
      // El valor sale recortado y como cadena: el importe nunca pasa por un número.
      expect(resultado.data?.MUROS).toBe(esperado);
    });

    test.each(RECHAZADAS)("tkt018a_ca10 · rechaza %s con el mensaje del tope", (_descripcion, escrito) => {
      const resultado = esquemaTopes.safeParse(topes(escrito));

      expect(resultado.success).toBe(false);
      const mensajes = resultado.error?.issues.map((asunto) => ({ campo: asunto.path.join("."), mensaje: asunto.message }));
      expect(mensajes).toEqual([{ campo: "MUROS", mensaje: MENSAJE_IMPORTE_TOPE }]);
    });

    test("tkt018a_ca10 · la fila sin capturar (cadena vacía) es válida", () => {
      const resultado = esquemaTopes.safeParse(topes(""));

      expect(resultado.success).toBe(true);
      expect(resultado.data).toEqual(topes(""));
    });

    test("tkt018a_ca10 · una fila de solo espacios queda vacía y es válida", () => {
      const resultado = esquemaTopes.safeParse(topes("   "));

      expect(resultado.success).toBe(true);
      expect(resultado.data?.MUROS).toBe("");
    });

    test("tkt018a_ca10 · el error se marca en la fila que lo tiene, no en las demás", () => {
      const resultado = esquemaTopes.safeParse({
        MUROS: "45000.00",
        PLAFONES_Y_CAJILLOS: "1.12345",
        ENCHAPES: "",
        GENERALES: "-5",
      });

      expect(resultado.success).toBe(false);
      const campos = resultado.error?.issues.map((asunto) => asunto.path.join("."));
      expect(campos).toEqual(["PLAFONES_Y_CAJILLOS", "GENERALES"]);
    });

    test("tkt018a_ca10 · el resolutor devuelve el valor recortado cuando todo es válido", async () => {
      const resultado = await resolverTopes(topes(" 45000.00 "), undefined, {
        fields: {},
        shouldUseNativeValidation: false,
      });

      expect(resultado.errors).toEqual({});
      expect(resultado.values.MUROS).toBe("45000.00");
    });

    test("tkt018a_ca10 · el resolutor marca la fila inválida con el mensaje del tope", async () => {
      const resultado = await resolverTopes(topes("1.12345"), undefined, {
        fields: {},
        shouldUseNativeValidation: false,
      });

      expect(resultado.values).toEqual({});
      expect(resultado.errors.MUROS?.message).toBe(MENSAJE_IMPORTE_TOPE);
    });
  });

  describe("esquemaRecaptura", () => {
    test.each(ADMITIDAS)("tkt018a_ca10 · admite %s", (_descripcion, escrito, esperado) => {
      const resultado = esquemaRecaptura.safeParse(recaptura(escrito));

      expect(resultado.success).toBe(true);
      expect(resultado.data?.tope).toBe(esperado);
    });

    test.each(RECHAZADAS)("tkt018a_ca10 · rechaza %s con el mensaje del tope", (_descripcion, escrito) => {
      const resultado = esquemaRecaptura.safeParse(recaptura(escrito));

      expect(resultado.success).toBe(false);
      const mensajes = resultado.error?.issues.map((asunto) => ({ campo: asunto.path.join("."), mensaje: asunto.message }));
      expect(mensajes).toEqual([{ campo: "tope", mensaje: MENSAJE_IMPORTE_TOPE }]);
    });

    test("tkt018a_ca10 · la cadena vacía no es válida: la recaptura exige el tope", () => {
      const resultado = esquemaRecaptura.safeParse(recaptura(""));

      expect(resultado.success).toBe(false);
      const primero = resultado.error?.issues[0];
      expect(primero?.path).toEqual(["tope"]);
      expect(primero?.message).toBe("El tope es obligatorio.");
    });

    test("tkt018a_ca10 · el tope de solo espacios tampoco es válido", () => {
      const resultado = esquemaRecaptura.safeParse(recaptura("   "));

      expect(resultado.success).toBe(false);
      expect(resultado.error?.issues[0]?.path).toEqual(["tope"]);
    });

    test.each([
      ["vacío", "", "El motivo es obligatorio."],
      ["solo espacios", "   ", "El motivo es obligatorio."],
      ["de 2,001 caracteres", "a".repeat(2001), "El motivo admite hasta 2,000 caracteres."],
    ])("tkt018a_ca10 · el motivo %s usa las reglas de esquemaMotivo", (_descripcion, motivo, mensaje) => {
      const resultado = esquemaRecaptura.safeParse(recaptura("50000.00", motivo));

      expect(resultado.success).toBe(false);
      const mensajes = resultado.error?.issues.map((asunto) => ({ campo: asunto.path.join("."), mensaje: asunto.message }));
      expect(mensajes).toEqual([{ campo: "motivo", mensaje }]);
    });

    test("tkt018a_ca10 · el motivo de 2,000 caracteres y el tope válido pasan, con el motivo recortado", () => {
      const resultado = esquemaRecaptura.safeParse(recaptura("50000.00", `  ${"a".repeat(2000)}  `));

      expect(resultado.success).toBe(true);
      expect(resultado.data).toEqual({ tope: "50000.00", motivo: "a".repeat(2000) });
    });

    test("tkt018a_ca10 · el resolutor marca el tope y el motivo inválidos a la vez", async () => {
      const resultado = await resolverRecaptura(recaptura("abc", "   "), undefined, {
        fields: {},
        shouldUseNativeValidation: false,
      });

      expect(resultado.values).toEqual({});
      expect(resultado.errors.tope?.message).toBe(MENSAJE_IMPORTE_TOPE);
      expect(resultado.errors.motivo?.message).toBe("El motivo es obligatorio.");
    });
  });
});
