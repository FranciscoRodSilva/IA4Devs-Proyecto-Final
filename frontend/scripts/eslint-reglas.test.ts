import { fileURLToPath } from "node:url";
import { ESLint, type Linter } from "eslint";
import { describe, expect, test } from "vitest";

const RAIZ = fileURLToPath(new URL("..", import.meta.url));
const eslint = new ESLint({ cwd: RAIZ });

const REGLA_SINTAXIS = "no-restricted-syntax";
const REGLA_IMPORTACION = "no-restricted-imports";

// El mensaje de cada rechazo cita la regla que lo explica (regla 1, RNF-02 o CA-13).
const CITA_REGLA = /regla 1|RNF-02|CA-13/;

/** Mensajes de ESLint de `codigo` como si viviera en `ruta` (relativa a frontend/), solo de la regla pedida. */
async function mensajesDe(codigo: string, ruta: string, regla: string): Promise<Linter.LintMessage[]> {
  const [resultado] = await eslint.lintText(codigo, { filePath: `${RAIZ}${ruta}` });
  return (resultado?.messages ?? []).filter((mensaje) => mensaje.ruleId === regla);
}

/** Todo error (gravedad 2) de `codigo` en `ruta`, de cualquier regla. */
async function erroresDe(codigo: string, ruta: string): Promise<Linter.LintMessage[]> {
  const [resultado] = await eslint.lintText(codigo, { filePath: `${RAIZ}${ruta}` });
  return (resultado?.messages ?? []).filter((mensaje) => mensaje.severity === 2);
}

describe("TKT-008 · reglas de ESLint del cliente", () => {
  test("tkt008_ca13_esc03 · Number en src", async () => {
    const mensajes = await mensajesDe('export const a = Number("1");', "src/modulos/compras/x.ts", REGLA_SINTAXIS);

    expect(mensajes).toHaveLength(1);
    expect(mensajes[0]?.line).toBe(1);
    expect(mensajes[0]?.severity).toBe(2);
    expect(mensajes[0]?.message).toMatch(CITA_REGLA);
  });

  test("tkt008_ca13_esc03 · las demás conversiones", async () => {
    const codigo = [
      "parseFloat(texto);",
      "parseInt(texto);",
      "Number.parseFloat(texto);",
      "Number.parseInt(texto);",
      "new Number(1);",
      "+texto;",
    ].join("\n");

    const mensajes = await mensajesDe(codigo, "src/modulos/compras/x.ts", REGLA_SINTAXIS);

    expect(mensajes.map((mensaje) => mensaje.line)).toEqual([1, 2, 3, 4, 5, 6]);
    for (const mensaje of mensajes) {
      expect(mensaje.severity).toBe(2);
      expect(mensaje.message).toMatch(CITA_REGLA);
    }
  });

  test("tkt008_ca13_esc03 · el módulo de dinero está exento", async () => {
    const codigo = 'export const a = Number("1");';

    // Control: el mismo código fuera del módulo de dinero se rechaza; sin él, la exención no demostraría nada.
    const fuera = await mensajesDe(codigo, "src/modulos/compras/x.ts", REGLA_SINTAXIS);
    expect(fuera).toHaveLength(1);

    const dentro = await erroresDe(codigo, "src/compartido/dinero/x.ts");
    expect(dentro).toEqual([]);
  });

  test("tkt008_car3 · document.cookie", async () => {
    const codigo = "export const c = document.cookie;";

    for (const ruta of ["src/app/x.ts", "src/compartido/dinero/x.ts"]) {
      const mensajes = await mensajesDe(codigo, ruta, REGLA_SINTAXIS);

      expect(mensajes, ruta).toHaveLength(1);
      expect(mensajes[0]?.line, ruta).toBe(1);
      expect(mensajes[0]?.severity, ruta).toBe(2);
      expect(mensajes[0]?.message, ruta).toMatch(/RNF-02/);
    }
  });

  // Ciclo de corrección 1 · F001. Las guardas de arriba se esquivan con otra forma de escribir lo mismo.
  // Cada caso se prueba en `src/modulos/x.ts` (la regla general) y, el de la cookie, también en el módulo de dinero.

  test("tkt008_car3 · TC-F1a · document[\"cookie\"]", async () => {
    for (const ruta of ["src/modulos/x.ts", "src/compartido/dinero/x.ts"]) {
      const mensajes = await mensajesDe('export const c = document["cookie"];', ruta, REGLA_SINTAXIS);

      expect(mensajes, ruta).toHaveLength(1);
      expect(mensajes[0]?.line, ruta).toBe(1);
      expect(mensajes[0]?.severity, ruta).toBe(2);
      expect(mensajes[0]?.message, ruta).toMatch(/RNF-02/);
    }
  });

  test("tkt008_car3 · TC-F1b · window.document.cookie", async () => {
    for (const ruta of ["src/modulos/x.ts", "src/compartido/dinero/x.ts"]) {
      const mensajes = await mensajesDe("export const c = window.document.cookie;", ruta, REGLA_SINTAXIS);

      expect(mensajes, ruta).toHaveLength(1);
      expect(mensajes[0]?.line, ruta).toBe(1);
      expect(mensajes[0]?.severity, ruta).toBe(2);
      expect(mensajes[0]?.message, ruta).toMatch(/RNF-02/);
    }
  });

  test("tkt008_car3 · TC-F1c · const { cookie } = document", async () => {
    for (const ruta of ["src/modulos/x.ts", "src/compartido/dinero/x.ts"]) {
      const mensajes = await mensajesDe("export const { cookie } = document;", ruta, REGLA_SINTAXIS);

      expect(mensajes, ruta).toHaveLength(1);
      expect(mensajes[0]?.line, ruta).toBe(1);
      expect(mensajes[0]?.severity, ruta).toBe(2);
      expect(mensajes[0]?.message, ruta).toMatch(/RNF-02/);
    }
  });

  test("tkt008_ca13_esc03 · TC-F1d · globalThis.Number y window.Number", async () => {
    const codigo = ['export const a = globalThis.Number("1");', 'export const b = window.Number("1");'].join("\n");

    const mensajes = await mensajesDe(codigo, "src/modulos/x.ts", REGLA_SINTAXIS);

    expect(mensajes.map((mensaje) => mensaje.line)).toEqual([1, 2]);
    for (const mensaje of mensajes) {
      expect(mensaje.severity).toBe(2);
      expect(mensaje.message).toMatch(CITA_REGLA);
    }
    // El módulo de dinero sigue exento.
    expect(await erroresDe(codigo, "src/compartido/dinero/x.ts")).toEqual([]);
  });

  test("tkt008_ca13_esc03 · TC-F1e · import() dinámico de decimal.js", async () => {
    const codigo = 'export const cargar = () => import("decimal.js");';

    // Da igual qué regla lo rechace; lo que importa es que algo lo rechace con el motivo, en la línea y como error.
    const rechazos = (await erroresDe(codigo, "src/modulos/x.ts")).filter(
      (mensaje) => mensaje.ruleId === REGLA_IMPORTACION || mensaje.ruleId === REGLA_SINTAXIS,
    );

    expect(rechazos).toHaveLength(1);
    expect(rechazos[0]?.line).toBe(1);
    expect(rechazos[0]?.severity).toBe(2);
    expect(rechazos[0]?.message).toMatch(/decimal\.js/);
    // El módulo de dinero puede importarlo.
    expect(await erroresDe(codigo, "src/compartido/dinero/x.ts")).toEqual([]);
  });

  test("tkt008_car3 · TC-F1f · control: document.title no se rechaza", async () => {
    // Sin este control, una regla que prohibiera `document` entero pasaría las pruebas de arriba.
    for (const ruta of ["src/modulos/x.ts", "src/compartido/dinero/x.ts"]) {
      expect(await erroresDe("export const t = document.title;", ruta), ruta).toEqual([]);
    }
  });

  test("tkt008_ca13_esc04 · Zod solo en formularios", async () => {
    const codigo = 'import { z } from "zod";\nexport const esquema = z.string();';

    const rechazado = await mensajesDe(codigo, "src/modulos/compras/x.ts", REGLA_IMPORTACION);
    expect(rechazado).toHaveLength(1);
    expect(rechazado[0]?.line).toBe(1);
    expect(rechazado[0]?.severity).toBe(2);
    expect(rechazado[0]?.message).toMatch(/CA-13/);

    for (const ruta of ["src/modulos/identidad/inicio-sesion.formulario.ts", "src/compartido/formularios/X.tsx"]) {
      expect(await erroresDe(codigo, ruta), ruta).toEqual([]);
    }
  });

  test("tkt008_ca13_esc03 · decimal.js solo en su módulo", async () => {
    const codigo = 'import Decimal from "decimal.js";\nexport const cero = new Decimal("0");';

    const rechazado = await mensajesDe(codigo, "src/api/x.ts", REGLA_IMPORTACION);
    expect(rechazado).toHaveLength(1);
    expect(rechazado[0]?.line).toBe(1);
    expect(rechazado[0]?.severity).toBe(2);
    expect(rechazado[0]?.message).toMatch(/decimal\.js/);

    expect(await erroresDe(codigo, "src/compartido/dinero/x.ts")).toEqual([]);
  });

  test("tkt008_car1 · TSX", async () => {
    const mensajes = await mensajesDe(
      'export const A = () => <p>{Number("1")}</p>;',
      "src/app/A.tsx",
      REGLA_SINTAXIS,
    );

    expect(mensajes).toHaveLength(1);
    expect(mensajes[0]?.line).toBe(1);
    expect(mensajes[0]?.severity).toBe(2);
    expect(mensajes[0]?.message).toMatch(CITA_REGLA);
  });
});
