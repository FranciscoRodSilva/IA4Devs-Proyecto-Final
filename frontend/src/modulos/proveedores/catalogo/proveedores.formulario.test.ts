import { describe, expect, test } from "vitest";
import type { components } from "@/api/generado/servidor";
import {
  cambiosDe,
  DIAS,
  esquemaAlta,
  esquemaEdicion,
  VALORES_INICIALES_ALTA,
  valoresInicialesDe,
} from "./proveedores.formulario";

// TKT-032a · fila F4 · TC-F05, TC-F06 y TC-F08 (parte del formulario). Los esquemas validan el formulario, no espejan
// el modelo del servidor: los nombres de campo son los del API para que un 422 caiga en su campo, y todo lo que se
// rechaza aquí es cortesía (CA-4): el servidor manda. El tope de consignación es dinero: entra y sale como cadena
// y se compara con decimal.js, nunca como número (CA-R4).

type Esquemas = components["schemas"];
type Proveedor = Esquemas["Proveedor"];
type ValoresEdicion = Parameters<typeof cambiosDe>[1];

const NOMBRE_VALIDO = "CoPanel";
const RFC_VALIDO = "XAXX010101000";

/** El proveedor tal como lo devuelve el servidor, con el tope en la escala de su columna. */
function proveedor(cambios: Partial<Proveedor> = {}): Proveedor {
  return {
    id: "9c2e5a41-7b3d-4f68-a1c9-3d5e7f9b1a24",
    nombre: NOMBRE_VALIDO,
    rfc: RFC_VALIDO,
    tope_consignacion: "300000.0000",
    dia_corte: 4,
    dia_pago: 6,
    estado: "ACTIVO",
    creado_en: "2026-11-17T15:00:00Z",
    ...cambios,
  } satisfies Proveedor;
}

/** Lo que teclea la persona en el alta: todo texto. */
function escrito(cambios: Record<string, unknown> = {}): Record<string, unknown> {
  return { nombre: NOMBRE_VALIDO, rfc: RFC_VALIDO, tope_consignacion: "", dia_corte: "4", dia_pago: "6", ...cambios };
}

/** Lo que entrega el formulario de edición al guardar: ya validado, con los días como enteros. */
function valoresDe(base: Proveedor, cambios: Partial<ValoresEdicion> = {}): ValoresEdicion {
  return {
    nombre: base.nombre,
    tope_consignacion: base.tope_consignacion ?? null,
    dia_corte: base.dia_corte,
    dia_pago: base.dia_pago,
    ...cambios,
  };
}

function mensajesDe(entrada: Record<string, unknown>): Array<{ campo: string; mensaje: string }> {
  const resultado = esquemaAlta.safeParse(entrada);
  expect(resultado.success).toBe(false);
  return (resultado.error?.issues ?? []).map((asunto) => ({ campo: asunto.path.join("."), mensaje: asunto.message }));
}

/** Los campos distintos que el esquema señala: un campo con dos reglas rotas cuenta una vez. */
function camposRechazados(entrada: Record<string, unknown>): string[] {
  return [...new Set(mensajesDe(entrada).map((asunto) => asunto.campo))];
}

/** Lo mismo para el esquema de edición. */
function camposRechazadosEnEdicion(entrada: Record<string, unknown>): string[] {
  const resultado = esquemaEdicion.safeParse(entrada);
  expect(resultado.success).toBe(false);
  return [...new Set((resultado.error?.issues ?? []).map((asunto) => asunto.path.join(".")))];
}

describe("TKT-032a · esquemaAlta · lo que se acepta (TC-F05, CA-2, CA-4)", () => {
  test("hdu004_esc02 · TC-F05 · nombre y RFC con los valores por omisión salen como el cuerpo del alta: jueves, sábado y sin tope", () => {
    const resultado = esquemaAlta.safeParse(escrito());

    expect(resultado.success).toBe(true);
    expect(resultado.data).toStrictEqual({
      nombre: NOMBRE_VALIDO,
      rfc: RFC_VALIDO,
      tope_consignacion: null,
      dia_corte: 4,
      dia_pago: 6,
    });
  });

  test("hdu004_esc02 · TC-F05 · el nombre y el RFC salen sin espacios en los extremos", () => {
    const resultado = esquemaAlta.safeParse(escrito({ nombre: "  CoPanel S.A.  ", rfc: "  XAXX010101000  " }));

    expect(resultado.data).toMatchObject({ nombre: "CoPanel S.A.", rfc: RFC_VALIDO });
  });

  test.each([
    ["13 posiciones, persona moral con cuatro letras", "XAXX010101000", "XAXX010101000"],
    ["12 posiciones, tres letras", "ABA040312KT7", "ABA040312KT7"],
    ["con Ñ", "ÑAB010101AB1", "ÑAB010101AB1"],
    ["con &", "&AB010101AB1", "&AB010101AB1"],
    ["en minúsculas", "xaxx010101000", "XAXX010101000"],
    ["con ñ minúscula", "ñab010101ab1", "ÑAB010101AB1"],
  ])("hdu004_esc02 · TC-F05 · el RFC %s sale en mayúsculas", (_descripcion, tecleado, enviado) => {
    const resultado = esquemaAlta.safeParse(escrito({ rfc: tecleado }));

    expect(resultado.success).toBe(true);
    expect(resultado.data).toMatchObject({ rfc: enviado });
  });

  test("hdu004_esc02 · TC-F05 · un nombre de exactamente 200 caracteres se acepta", () => {
    const resultado = esquemaAlta.safeParse(escrito({ nombre: "N".repeat(200) }));

    expect(resultado.success).toBe(true);
  });

  test.each([
    ["1", 1],
    ["2", 2],
    ["3", 3],
    ["4", 4],
    ["5", 5],
    ["6", 6],
    ["7", 7],
  ])("hdu004_esc02 · TC-F05 · el día «%s» del desplegable sale como el entero %i, en corte y en pago", (texto, entero) => {
    const resultado = esquemaAlta.safeParse(escrito({ dia_corte: texto, dia_pago: texto }));

    expect(resultado.success).toBe(true);
    expect(resultado.data?.dia_corte).toBe(entero);
    expect(resultado.data?.dia_pago).toBe(entero);
    // Un entero de verdad: el servidor rechaza «4» como texto.
    expect(typeof resultado.data?.dia_corte).toBe("number");
    expect(typeof resultado.data?.dia_pago).toBe("number");
  });

  test("hdu004_esc02 · TC-F05 · el tope vacío sale como null: sin tope", () => {
    const resultado = esquemaAlta.safeParse(escrito({ tope_consignacion: "" }));

    expect(resultado.success).toBe(true);
    // La clave existe y vale null: no «ausente», para que el cuerpo del alta diga que no hay tope.
    expect(resultado.data).toHaveProperty("tope_consignacion", null);
  });

  test.each(["0", "0.0001", "300000", "300000.00", "300000.0000", "12345678901234", "99999999999999.9999"])(
    "hdu004_esc02 · TC-F05 · CA-R4 · el tope «%s» sale tal cual, como cadena",
    (tope) => {
      const resultado = esquemaAlta.safeParse(escrito({ tope_consignacion: tope }));

      expect(resultado.success).toBe(true);
      expect(resultado.data?.tope_consignacion).toBe(tope);
      expect(typeof resultado.data?.tope_consignacion).toBe("string");
    },
  );

  test("hdu004_esc02 · TC-F05 · RN-17 · los valores iniciales del alta, con nombre y RFC, proponen jueves y sábado sin tope", () => {
    const resultado = esquemaAlta.safeParse({ ...VALORES_INICIALES_ALTA, nombre: NOMBRE_VALIDO, rfc: RFC_VALIDO });

    expect(resultado.success).toBe(true);
    expect(resultado.data).toStrictEqual({
      nombre: NOMBRE_VALIDO,
      rfc: RFC_VALIDO,
      tope_consignacion: null,
      dia_corte: 4,
      dia_pago: 6,
    });
  });
});

describe("TKT-032a · esquemaAlta · lo que se rechaza, en su campo (TC-F05, CA-4, rechazo)", () => {
  test.each([
    ["vacío", ""],
    ["de solo espacios", "   "],
    ["de solo saltos de línea y tabuladores", "\n\t \n"],
  ])("tkt032a_alta · TC-F05 · rechazo: el nombre %s se señala en su campo con el texto del boceto", (_descripcion, nombre) => {
    expect(mensajesDe(escrito({ nombre }))).toEqual([{ campo: "nombre", mensaje: "Escribe el nombre del proveedor." }]);
  });

  test("tkt032a_alta · TC-F05 · rechazo: el nombre con el carácter NUL se señala en su campo", () => {
    expect(camposRechazados(escrito({ nombre: "Co\u0000Panel" }))).toEqual(["nombre"]);
  });

  test("tkt032a_alta · TC-F05 · rechazo: el nombre de 201 caracteres se señala en su campo", () => {
    expect(camposRechazados(escrito({ nombre: "N".repeat(201) }))).toEqual(["nombre"]);
  });

  test.each([
    ["vacío", ""],
    ["de solo espacios", "   "],
    ["con tres posiciones", "ABC"],
    ["de 11 posiciones", "ABC010101AB"],
    ["de 14 posiciones", "XAXX0101010000"],
    ["con dos letras al inicio", "AB010101ABC"],
    ["con cinco letras al inicio", "ABCDE010101AB"],
    ["con un guion", "XAXX010101-00"],
    ["con un espacio en medio", "XAXX010101 000"],
    ["con un salto de línea en medio", "XAXX010101\n000"],
    ["con dígitos que no son ASCII", "XAXX٠١٠١٠١000"],
    ["con letras donde van los seis dígitos", "XAXXAB0101000"],
  ])("tkt032a_alta · TC-F05 · rechazo: el RFC %s se señala en su campo", (_descripcion, rfc) => {
    expect(camposRechazados(escrito({ rfc }))).toEqual(["rfc"]);
  });

  test.each([
    ["con exponente", "1e3"],
    ["negativo", "-5"],
    ["con signo positivo", "+5"],
    ["con un dígito que no es ASCII", "٣"],
    ["con cinco decimales", "1.23456"],
    ["con quince enteros", "123456789012345"],
    ["con punto final y sin decimales", "1."],
    ["sin enteros", ".5"],
    ["con coma decimal", "1,5"],
    ["que no es un número", "abc"],
    ["infinito", "Infinity"],
    ["hexadecimal", "0x10"],
  ])("tkt032a_alta · TC-F05 · CA-R4 · rechazo: el tope %s se señala en su campo con mensaje", (_descripcion, tope) => {
    const asuntos = mensajesDe(escrito({ tope_consignacion: tope }));

    expect([...new Set(asuntos.map((asunto) => asunto.campo))]).toEqual(["tope_consignacion"]);
    expect(asuntos[0]?.mensaje).not.toBe("");
  });

  test.each([
    ["dia_corte", "0"],
    ["dia_corte", "8"],
    ["dia_corte", ""],
    ["dia_corte", "abc"],
    ["dia_corte", "1.5"],
    ["dia_corte", "-1"],
    ["dia_corte", "٣"],
    ["dia_pago", "0"],
    ["dia_pago", "8"],
    ["dia_pago", ""],
    ["dia_pago", "abc"],
    ["dia_pago", "1.5"],
    ["dia_pago", "-1"],
    ["dia_pago", "٣"],
  ])("tkt032a_alta · TC-F05 · rechazo: %s con «%s» no es un día de 1 a 7 y se señala en su campo", (campo, valor) => {
    expect(camposRechazados(escrito({ [campo]: valor }))).toEqual([campo]);
  });

  test("tkt032a_alta · TC-F05 · rechazo: con todo mal cada campo se señala en el suyo, con los nombres del API", () => {
    const campos = camposRechazados({
      nombre: "",
      rfc: "mal",
      tope_consignacion: "-5",
      dia_corte: "9",
      dia_pago: "0",
    });

    expect([...campos].sort()).toEqual(["dia_corte", "dia_pago", "nombre", "rfc", "tope_consignacion"]);
  });
});

describe("TKT-032a · TC-F08 · el tope de consignación no pasa por number (CA-R4, rechazo)", () => {
  const TOPE_MAXIMO = "99999999999999.9999";

  test("tkt032a_tope · TC-F08 · el tope máximo de 14 enteros y 4 decimales sale idéntico y como cadena", () => {
    const resultado = esquemaAlta.safeParse(escrito({ tope_consignacion: TOPE_MAXIMO }));

    expect(resultado.success).toBe(true);
    // Si pasara por number valdría 100000000000000: la exactitud se perdería sin aviso.
    expect(resultado.data?.tope_consignacion).toBe(TOPE_MAXIMO);
    expect(typeof resultado.data?.tope_consignacion).toBe("string");
    expect(JSON.stringify(resultado.data)).toContain(`"tope_consignacion":"${TOPE_MAXIMO}"`);
  });

  test("tkt032a_tope · TC-F08 · el esquema de edición lo entrega igual: idéntico y como cadena", () => {
    const resultado = esquemaEdicion.safeParse(escrito({ tope_consignacion: TOPE_MAXIMO }));

    expect(resultado.success).toBe(true);
    expect(resultado.data?.tope_consignacion).toBe(TOPE_MAXIMO);
    expect(typeof resultado.data?.tope_consignacion).toBe("string");
  });
});

describe("TKT-032a · esquemaEdicion · el mismo formulario con el RFC de solo lectura (CA-5, TC-F05)", () => {
  test("tkt032a_edicion · TC-F05 · los valores iniciales de un proveedor pasan el esquema y salen con los días como enteros", () => {
    const resultado = esquemaEdicion.safeParse(valoresInicialesDe(proveedor()));

    expect(resultado.success).toBe(true);
    expect(resultado.data).toMatchObject({
      nombre: NOMBRE_VALIDO,
      tope_consignacion: "300000.0000",
      dia_corte: 4,
      dia_pago: 6,
    });
  });

  test("tkt032a_edicion · TC-F05 · el tope vaciado sale como null: así se borra el tope", () => {
    const resultado = esquemaEdicion.safeParse(escrito({ tope_consignacion: "" }));

    expect(resultado.success).toBe(true);
    expect(resultado.data).toHaveProperty("tope_consignacion", null);
  });

  test("tkt032a_edicion · TC-F05 · rechazo: un nombre vacío se señala en su campo", () => {
    expect(camposRechazadosEnEdicion(escrito({ nombre: "  " }))).toEqual(["nombre"]);
  });

  test.each(["1e3", "-5", "٣", "1.23456", "123456789012345"])(
    "tkt032a_edicion · TC-F05 · CA-R4 · rechazo: el tope «%s» se señala en su campo",
    (tope) => {
      expect(camposRechazadosEnEdicion(escrito({ tope_consignacion: tope }))).toEqual(["tope_consignacion"]);
    },
  );

  test.each(["0", "8", "abc"])("tkt032a_edicion · TC-F05 · rechazo: el día de pago «%s» se señala en su campo", (dia) => {
    expect(camposRechazadosEnEdicion(escrito({ dia_pago: dia }))).toEqual(["dia_pago"]);
  });
});

describe("TKT-032a · DIAS y VALORES_INICIALES_ALTA (TC-F05, RN-17)", () => {
  test("hdu004_esc02 · TC-F05 · los siete días van de lunes a domingo, en minúsculas, con el valor que viaja como texto", () => {
    expect(DIAS).toEqual([
      { valor: "1", etiqueta: "lunes" },
      { valor: "2", etiqueta: "martes" },
      { valor: "3", etiqueta: "miércoles" },
      { valor: "4", etiqueta: "jueves" },
      { valor: "5", etiqueta: "viernes" },
      { valor: "6", etiqueta: "sábado" },
      { valor: "7", etiqueta: "domingo" },
    ]);
  });

  test("hdu004_esc02 · TC-F05 · RN-17 · el alta propone jueves («4») para el corte, sábado («6») para el pago y el tope vacío", () => {
    expect(VALORES_INICIALES_ALTA).toEqual({
      nombre: "",
      rfc: "",
      tope_consignacion: "",
      dia_corte: "4",
      dia_pago: "6",
    });
  });
});

describe("TKT-032a · valoresInicialesDe (TC-F23, CA-5)", () => {
  test("tkt032a_edicion · el proveedor de la lista se precarga con el RFC, el tope sin cambiar de forma y los días como texto", () => {
    expect(valoresInicialesDe(proveedor())).toEqual({
      nombre: NOMBRE_VALIDO,
      rfc: RFC_VALIDO,
      tope_consignacion: "300000.0000",
      dia_corte: "4",
      dia_pago: "6",
    });
  });

  test.each([
    ["null", null],
    ["ausente", undefined],
  ])("tkt032a_edicion · un proveedor sin tope (%s) se precarga con el tope vacío, no con «null» ni «undefined»", (_descripcion, tope) => {
    const base = proveedor();
    const sinTope: Proveedor = { ...base, tope_consignacion: tope };

    expect(valoresInicialesDe(sinTope)).toHaveProperty("tope_consignacion", "");
  });

  test.each([
    [1, 7, "1", "7"],
    [7, 1, "7", "1"],
  ])("tkt032a_edicion · corte %i y pago %i se precargan como «%s» y «%s»", (corte, pago, textoCorte, textoPago) => {
    expect(valoresInicialesDe(proveedor({ dia_corte: corte, dia_pago: pago }))).toMatchObject({
      dia_corte: textoCorte,
      dia_pago: textoPago,
    });
  });

  test.each([
    ["con cuatro decimales", "300000.0000"],
    ["sin decimales", "300000"],
    ["con el máximo", "99999999999999.9999"],
    ["sin tope", null],
  ])("tkt032a_edicion · TC-F25 · ida y vuelta: guardar sin tocar nada un proveedor %s no genera cambios", (_descripcion, tope) => {
    const base = proveedor({ tope_consignacion: tope });

    const resultado = esquemaEdicion.safeParse(valoresInicialesDe(base));

    if (!resultado.success) throw new Error("los valores precargados deben pasar el esquema de edición");
    expect(cambiosDe(base, resultado.data)).toBeNull();
  });
});

describe("TKT-032a · cambiosDe · el cuerpo del PATCH solo lleva lo que cambió (TC-F06, CA-5)", () => {
  test("tkt032a_edicion · TC-F06 · sin ningún cambio devuelve null: no hay petición que enviar", () => {
    const base = proveedor();

    expect(cambiosDe(base, valoresDe(base))).toBeNull();
  });

  test("tkt032a_edicion · TC-F06 · solo el nombre", () => {
    const base = proveedor();

    expect(cambiosDe(base, valoresDe(base, { nombre: "CoPanel S.A. de C.V." }))).toStrictEqual({
      nombre: "CoPanel S.A. de C.V.",
    });
  });

  test("tkt032a_edicion · TC-F06 · solo el día de pago", () => {
    const base = proveedor();

    expect(cambiosDe(base, valoresDe(base, { dia_pago: 5 }))).toStrictEqual({ dia_pago: 5 });
  });

  test("tkt032a_edicion · TC-F06 · solo el día de corte", () => {
    const base = proveedor();

    expect(cambiosDe(base, valoresDe(base, { dia_corte: 2 }))).toStrictEqual({ dia_corte: 2 });
  });

  test("tkt032a_edicion · TC-F06 · solo el tope, que viaja como cadena", () => {
    const base = proveedor();

    const cambios = cambiosDe(base, valoresDe(base, { tope_consignacion: "350000.50" }));

    expect(cambios).toStrictEqual({ tope_consignacion: "350000.50" });
    expect(typeof cambios?.tope_consignacion).toBe("string");
  });

  test("tkt032a_edicion · TC-F06 · el tope vaciado envía null: así se borra, y no se confunde con «sin cambio»", () => {
    const base = proveedor();

    expect(cambiosDe(base, valoresDe(base, { tope_consignacion: null }))).toStrictEqual({ tope_consignacion: null });
  });

  test.each([
    ["null", null],
    ["ausente", undefined],
  ])("tkt032a_edicion · TC-F06 · un proveedor sin tope (%s) al que se le deja el tope vacío no cambia", (_descripcion, tope) => {
    const base: Proveedor = { ...proveedor(), tope_consignacion: tope };

    expect(cambiosDe(base, valoresDe(base, { tope_consignacion: null }))).toBeNull();
  });

  test("tkt032a_edicion · TC-F06 · un proveedor sin tope al que se le captura uno lo envía", () => {
    const base = proveedor({ tope_consignacion: null });

    expect(cambiosDe(base, valoresDe(base, { tope_consignacion: "1000" }))).toStrictEqual({ tope_consignacion: "1000" });
  });

  test("tkt032a_edicion · TC-F06 · varios cambios a la vez viajan juntos y nada más", () => {
    const base = proveedor();

    const cambios = cambiosDe(
      base,
      valoresDe(base, { nombre: "CoPanel Norte", dia_pago: 5, tope_consignacion: "400000" }),
    );

    expect(cambios).toStrictEqual({ nombre: "CoPanel Norte", dia_pago: 5, tope_consignacion: "400000" });
  });

  test.each([
    ["300000.0000", "300000"],
    ["300000.0000", "300000.00"],
    ["300000", "300000.0000"],
    ["0.0000", "0"],
    ["1000.5000", "1000.5"],
  ])(
    "tkt032a_edicion · TC-F06 · CA-R4 · el tope «%s» contra «%s» es el mismo número y no cuenta como cambio (Decimal.eq)",
    (guardado, capturado) => {
      const base = proveedor({ tope_consignacion: guardado });

      expect(cambiosDe(base, valoresDe(base, { tope_consignacion: capturado }))).toBeNull();
    },
  );

  test.each([
    ["300000.0000", "300000.0001"],
    ["300000.0000", "299999.9999"],
    ["0.0000", "0.0001"],
  ])("tkt032a_edicion · TC-F06 · rechazo: el tope «%s» contra «%s» sí es un cambio, aunque sea de la última cifra", (guardado, capturado) => {
    const base = proveedor({ tope_consignacion: guardado });

    expect(cambiosDe(base, valoresDe(base, { tope_consignacion: capturado }))).toStrictEqual({ tope_consignacion: capturado });
  });

  test("tkt032a_edicion · TC-F06 · CA-R4 · un cambio en la última cifra del tope máximo se detecta: no se compara como number", () => {
    // Como number, 99999999999999.9999 y 99999999999999.9998 son el mismo valor.
    const base = proveedor({ tope_consignacion: "99999999999999.9999" });

    expect(cambiosDe(base, valoresDe(base, { tope_consignacion: "99999999999999.9998" }))).toStrictEqual({
      tope_consignacion: "99999999999999.9998",
    });
  });

  test("tkt032a_edicion · TC-F06 · tope 0 y sin tope son cosas distintas: pasar de null a «0» es un cambio, y de «0.0000» a vacío también", () => {
    const sinTope = proveedor({ tope_consignacion: null });
    const enCero = proveedor({ tope_consignacion: "0.0000" });

    expect(cambiosDe(sinTope, valoresDe(sinTope, { tope_consignacion: "0" }))).toStrictEqual({ tope_consignacion: "0" });
    expect(cambiosDe(enCero, valoresDe(enCero, { tope_consignacion: null }))).toStrictEqual({ tope_consignacion: null });
  });

  test("tkt032a_edicion · TC-F06 · CA-5 · el RFC nunca viaja: ni cambiado ni sin cambiar", () => {
    const base = proveedor();

    expect(cambiosDe(base, { ...valoresDe(base), rfc: "OTRO010101000" })).toBeNull();
    expect(cambiosDe(base, { ...valoresDe(base, { nombre: "CoPanel Norte" }), rfc: "OTRO010101000" })).toStrictEqual({
      nombre: "CoPanel Norte",
    });
  });
});
