import { describe, expect, test } from "vitest";
import { obra } from "@/pruebas/cuerpos";
import { CAMPOS_EDICION_OBRA, CAMPOS_OBRA, esquemaEdicionObra, valoresDeEdicion } from "./obras.formulario";

// TKT-012b · fila B2 · CA-15 · CA-2 · TC-68. El formulario de edición de una obra: solo lo editable. El código y el
// tipo de contrato no se cambian y el estado solo cambia con las transiciones (CA-2): el esquema no los declara, y lo
// que llegue con esos nombres no sale en lo que se envía. Los nombres de campo son los del API (`ObraCambios`) para
// que un 422 caiga en su campo.

const CAMPOS_EDITABLES = [
  "nombre",
  "domicilio",
  "retencion_destajo_pct",
  "fondo_garantia_pct",
  "umbral_alerta_pct",
  "iva_acreditable",
] as const;

const CAMPOS_FIJOS = ["codigo", "tipo_contrato", "estado"] as const;

const MENSAJE_PORCENTAJE = "Escribe un porcentaje, como 15";

/** Lo que teclea la persona: los porcentajes como «15», el umbral vacío si no hay. */
function escrito(cambios: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    nombre: "Union Square Fase 2",
    domicilio: "Av. Constituyentes 120, Querétaro",
    retencion_destajo_pct: "15",
    fondo_garantia_pct: "5",
    umbral_alerta_pct: "",
    iva_acreditable: true,
    ...cambios,
  };
}

function mensajesDe(entrada: Record<string, unknown>): Array<{ campo: string; mensaje: string }> {
  const resultado = esquemaEdicionObra.safeParse(entrada);
  expect(resultado.success).toBe(false);
  return (resultado.error?.issues ?? []).map((asunto) => ({ campo: asunto.path.join("."), mensaje: asunto.message }));
}

describe("TKT-012b · esquemaEdicionObra · lo que no se edita (CA-2, CA-15, TC-68, rechazo)", () => {
  test("tkt012b_ca15 · TC-68 · declara exactamente los seis campos editables", () => {
    expect(Object.keys(esquemaEdicionObra.shape).sort()).toEqual([...CAMPOS_EDITABLES].sort());
  });

  test.each(CAMPOS_FIJOS)("tkt012b_ca2 · TC-68 · el esquema no declara %s", (fijo) => {
    expect(Object.keys(esquemaEdicionObra.shape)).not.toContain(fijo);
  });

  test("tkt012b_ca2 · TC-68 · un valor con codigo, tipo_contrato y estado sale solo con los seis campos editables", () => {
    const resultado = esquemaEdicionObra.safeParse(
      escrito({ codigo: "OTRO-999", tipo_contrato: "PRECIO_ALZADO_MAXIMO_GARANTIZADO", estado: "CERRADA" }),
    );

    expect(resultado.success).toBe(true);
    // Lo que sale es lo que viaja al servidor: ni el código, ni el tipo, ni el estado.
    expect(resultado.data).toEqual({
      nombre: "Union Square Fase 2",
      domicilio: "Av. Constituyentes 120, Querétaro",
      retencion_destajo_pct: "0.150000",
      fondo_garantia_pct: "0.050000",
      umbral_alerta_pct: null,
      iva_acreditable: true,
    });
    for (const fijo of CAMPOS_FIJOS) expect(resultado.data).not.toHaveProperty(fijo);
  });
});

describe("TKT-012b · esquemaEdicionObra · lo que sí se edita (CA-15, TC-68)", () => {
  test("tkt012b_ca15 · TC-68 · los porcentajes tecleados salen como fracción exacta de seis decimales", () => {
    const resultado = esquemaEdicionObra.safeParse(escrito({ retencion_destajo_pct: "12.5", fondo_garantia_pct: "7" }));

    expect(resultado.data).toMatchObject({ retencion_destajo_pct: "0.125000", fondo_garantia_pct: "0.070000" });
  });

  test("tkt012b_ca15 · TC-68 · el umbral tecleado sale como fracción", () => {
    const resultado = esquemaEdicionObra.safeParse(escrito({ umbral_alerta_pct: "5.5" }));

    expect(resultado.data).toMatchObject({ umbral_alerta_pct: "0.055000" });
  });

  test.each([
    ["vacío", ""],
    ["de solo espacios", "   "],
  ])("tkt012b_ca15 · TC-68 · el umbral %s sale como null: así se borra el umbral", (_descripcion, umbral) => {
    const resultado = esquemaEdicionObra.safeParse(escrito({ umbral_alerta_pct: umbral }));

    expect(resultado.success).toBe(true);
    // La clave existe y vale null: ausente significaría «no tocarlo».
    expect(resultado.data).toHaveProperty("umbral_alerta_pct", null);
  });

  test("tkt012b_ca15 · TC-68 · (asumido) sin la clave del umbral, la salida no la lleva: ausente es no tocarlo", () => {
    const sinUmbral = escrito();
    delete sinUmbral.umbral_alerta_pct;

    const resultado = esquemaEdicionObra.safeParse(sinUmbral);

    expect(resultado.success).toBe(true);
    expect(resultado.data).not.toHaveProperty("umbral_alerta_pct");
    expect(resultado.data).toMatchObject({ nombre: "Union Square Fase 2", retencion_destajo_pct: "0.150000" });
  });

  test("tkt012b_ca15 · TC-68 · el nombre y el domicilio salen sin espacios en los extremos", () => {
    const resultado = esquemaEdicionObra.safeParse(escrito({ nombre: "  Union Square F2  ", domicilio: "  Av. Constituyentes 120  " }));

    expect(resultado.data).toMatchObject({ nombre: "Union Square F2", domicilio: "Av. Constituyentes 120" });
  });

  test("tkt012b_ca15 · TC-68 · la casilla del IVA sale como booleano, marcada o no", () => {
    expect(esquemaEdicionObra.safeParse(escrito({ iva_acreditable: false })).data).toMatchObject({ iva_acreditable: false });
    expect(esquemaEdicionObra.safeParse(escrito({ iva_acreditable: true })).data).toMatchObject({ iva_acreditable: true });
  });

  test("tkt012b_ca15 · TC-68 · rechazo: el nombre vacío o de solo espacios se señala en su campo", () => {
    expect(mensajesDe(escrito({ nombre: "   " }))).toEqual([{ campo: "nombre", mensaje: "Escribe el nombre de la obra." }]);
  });

  test("tkt012b_ca15 · TC-68 · rechazo: el domicilio vacío se señala en su campo", () => {
    expect(mensajesDe(escrito({ domicilio: "" }))).toEqual([{ campo: "domicilio", mensaje: "Escribe el domicilio de la obra." }]);
  });

  test.each(["retencion_destajo_pct", "fondo_garantia_pct", "umbral_alerta_pct"])(
    "tkt012b_ca15 · TC-68 · rechazo: %s con texto que no es un porcentaje se señala en su campo",
    (campo) => {
      expect(mensajesDe(escrito({ [campo]: "abc" }))).toEqual([{ campo, mensaje: MENSAJE_PORCENTAJE }]);
    },
  );

  test.each(["retencion_destajo_pct", "fondo_garantia_pct"])(
    "tkt012b_ca15 · TC-68 · rechazo: %s vacío se señala en su campo: los dos porcentajes no se pueden borrar",
    (campo) => {
      expect(mensajesDe(escrito({ [campo]: "" }))).toEqual([{ campo, mensaje: MENSAJE_PORCENTAJE }]);
    },
  );
});

describe("TKT-012b · valoresDeEdicion (CA-15, TC-68)", () => {
  test("tkt012b_ca15 · TC-68 · la obra de la lista se precarga con los porcentajes como se teclean", () => {
    expect(valoresDeEdicion(obra())).toEqual({
      nombre: "Union Square F2",
      domicilio: "Av. Constituyentes 120, Querétaro",
      retencion_destajo_pct: "15",
      fondo_garantia_pct: "5",
      umbral_alerta_pct: "",
      iva_acreditable: true,
    });
  });

  test.each([
    ["0.150000", "15"],
    ["0.055000", "5.5"],
    ["0.000000", "0"],
  ])("tkt012b_ca15 · TC-68 · el umbral %s se precarga como %s", (umbral, tecleado) => {
    expect(valoresDeEdicion(obra({ umbral_alerta_pct: umbral }))).toHaveProperty("umbral_alerta_pct", tecleado);
  });

  test("tkt012b_ca15 · TC-68 · una obra sin umbral se precarga con el umbral vacío, no con null ni «null»", () => {
    expect(valoresDeEdicion(obra({ umbral_alerta_pct: null }))).toHaveProperty("umbral_alerta_pct", "");
  });

  test("tkt012b_ca15 · TC-68 · el IVA no acreditable se precarga sin marcar", () => {
    expect(valoresDeEdicion(obra({ iva_acreditable: false }))).toHaveProperty("iva_acreditable", false);
  });

  test.each(CAMPOS_FIJOS)("tkt012b_ca2 · TC-68 · rechazo: la precarga no trae %s", (fijo) => {
    expect(valoresDeEdicion(obra({ estado: "ACTIVA" }))).not.toHaveProperty(fijo);
  });

  test.each([
    ["0.150000", "0.150000"],
    ["0.055000", "0.055000"],
    [null, null],
  ])("tkt012b_ca15 · TC-68 · ida y vuelta: guardar sin cambios envía el mismo umbral (%s)", (umbral, enviado) => {
    const precargado = valoresDeEdicion(obra({ umbral_alerta_pct: umbral }));

    const resultado = esquemaEdicionObra.safeParse(precargado);

    expect(resultado.success).toBe(true);
    expect(resultado.data).toMatchObject({
      retencion_destajo_pct: "0.150000",
      fondo_garantia_pct: "0.050000",
      umbral_alerta_pct: enviado,
    });
  });
});

describe("TKT-012b · CAMPOS_EDICION_OBRA (CA-15, TC-68)", () => {
  const editables = () => CAMPOS_EDICION_OBRA.filter((campo) => campo.soloLectura !== true);

  test("tkt012b_ca15 · TC-68 · los campos editables son los seis, en el orden del formulario de alta", () => {
    expect(editables().map((campo) => campo.nombre)).toEqual([...CAMPOS_EDITABLES]);
  });

  test("tkt012b_ca15 · TC-68 · las etiquetas son las del alta", () => {
    const etiquetasDelAlta = new Map(CAMPOS_OBRA.map((campo) => [campo.nombre as string, campo.etiqueta]));

    expect(editables()).toHaveLength(CAMPOS_EDITABLES.length);
    for (const campo of editables()) {
      expect(campo.etiqueta).toBe(etiquetasDelAlta.get(campo.nombre));
    }
  });

  test("tkt012b_ca15 · TC-68 · el IVA es una casilla y el resto, campos de texto", () => {
    const tipos = Object.fromEntries(editables().map((campo) => [campo.nombre, campo.tipo ?? "text"]));

    expect(tipos).toEqual({
      nombre: "text",
      domicilio: "text",
      retencion_destajo_pct: "text",
      fondo_garantia_pct: "text",
      umbral_alerta_pct: "text",
      iva_acreditable: "casilla",
    });
  });

  test("tkt012b_ca2 · TC-68 · rechazo: el código y el tipo de contrato, si se muestran, son de solo lectura; el estado no se muestra", () => {
    for (const campo of CAMPOS_EDICION_OBRA) {
      if (campo.nombre === "codigo" || campo.nombre === "tipo_contrato") expect(campo.soloLectura).toBe(true);
      expect(campo.nombre).not.toBe("estado");
    }
  });

  test("tkt012b_ca15 · TC-68 · cada campo de la lista es un campo del esquema: un 422 cae en su campo", () => {
    const nombresDelEsquema = Object.keys(esquemaEdicionObra.shape);

    expect(CAMPOS_EDICION_OBRA.length).toBeGreaterThan(0);
    for (const campo of CAMPOS_EDICION_OBRA) expect(nombresDelEsquema).toContain(campo.nombre);
  });
});
