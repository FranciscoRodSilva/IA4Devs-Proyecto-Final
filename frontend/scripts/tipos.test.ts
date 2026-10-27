import { readFileSync } from "node:fs";
import { parse } from "yaml";
import { describe, expect, test, vi } from "vitest";
import {
  ARCHIVO_CONTRATO_ERROR,
  ARCHIVO_SERVIDOR,
  CABECERA_PROVISIONAL,
  CABECERA_SERVIDOR,
  RAICES_CONTRATO_ERROR,
  diferencias,
  exportarOpenapiPublicado,
  generarArchivos,
  principal,
  subconjuntoContratoError,
  type Documento,
  type Ejecutar,
} from "./tipos.ts";

// El borrador real, leído con `yaml`: el subconjunto se prueba contra el contrato verdadero, no contra uno inventado.
const borrador = parse(readFileSync(new URL("../../docs/api/openapi.yaml", import.meta.url), "utf8")) as Documento;

// Un OpenAPI publicado mínimo, con la ruta de sesión y un esquema propio del servidor.
const publicado: Documento = {
  openapi: "3.1.0",
  info: { title: "CIMENTA", version: "0.1.0" },
  paths: {
    "/api/v1/sesion": {
      post: {
        operationId: "iniciar_sesion",
        requestBody: {
          required: true,
          content: { "application/json": { schema: { $ref: "#/components/schemas/CredencialesPrueba" } } },
        },
        responses: { "204": { description: "Sesión iniciada" } },
      },
    },
  },
  components: {
    schemas: {
      CredencialesPrueba: {
        type: "object",
        required: ["correo", "contrasena"],
        properties: { correo: { type: "string" }, contrasena: { type: "string" } },
      },
    },
  },
};

// El subconjunto cerrado esperado, escrito a mano: las nueve raíces del contrato de error y todo lo que alcanzan por
// `$ref` en el borrador, en orden alfabético. Es el oráculo; no repite la lógica de recorrido de `tipos.ts`. Si el
// borrador cambia el contrato de error, esta lista cambia a propósito, en el mismo cambio y con revisión.
const ESQUEMAS_ESPERADOS = [
  "Accion", "Cantidad", "CantidadNoNegativa", "CodigoConflicto", "ConsumidoDesglose", "DetalleExcedeOrdenado",
  "DetalleExcedePresupuesto", "DetalleGenerico", "DetalleOrdenConSaldo", "ErrorConcurrencia", "ErrorConflicto",
  "ErrorConflictoEstado", "ErrorLimiteIntentos", "ErrorNoEncontrado", "ErrorPermiso", "ErrorReglaNegocio",
  "ErrorSesion", "ErrorValidacion", "EstadoOrdenCompra", "Fecha", "Importe", "ReglaId", "Rol", "Unidad", "Uuid",
];

/** Los esquemas de un documento, tal cual vienen: solo lectura de datos, sin recorrer referencias. */
const esquemasEn = (documento: Documento) => (documento["components"] as { schemas: Record<string, unknown> }).schemas;

describe("TKT-008 · generación de tipos del cliente", () => {
  test("tkt008_ca02_esc01 · subconjunto cerrado", () => {
    const subconjunto = subconjuntoContratoError(borrador);
    const esquemas = esquemasEn(subconjunto);

    // Las nueve raíces están.
    for (const raiz of RAICES_CONTRATO_ERROR) expect(esquemas).toHaveProperty(raiz);
    // Es un subconjunto, no el borrador entero: exactamente la lista literal esperada.
    expect(Object.keys(esquemas)).toEqual(ESQUEMAS_ESPERADOS);
    expect(esquemas).not.toHaveProperty("UsuarioActual");
    expect(esquemas).not.toHaveProperty("Insumo");
    expect(subconjunto["paths"]).toEqual({});
    // Cerrado: todo `$ref` del texto del resultado resuelve dentro del propio resultado.
    const referencias = JSON.stringify(subconjunto).matchAll(/#\/components\/schemas\/([A-Za-z0-9_]+)/g);
    for (const [referencia, nombre] of referencias) {
      expect(esquemas, `el $ref ${referencia} no resuelve dentro del subconjunto`).toHaveProperty(nombre ?? "");
    }

    // Rechazo: un borrador al que le falta un esquema alcanzable lanza nombrándolo.
    const roto = structuredClone(borrador);
    delete esquemasEn(roto)["Accion"];

    expect(() => subconjuntoContratoError(roto)).toThrow(/Accion/);
  });

  test("tkt008_ca02_esc04 · TC-R1c · O4 · las claves del subconjunto salen en orden alfabético", () => {
    // El recorrido encuentra los esquemas por las raíces, no por orden alfabético; solo `.sort()` los ordena.
    // Se invierte el orden de los esquemas del borrador para que tampoco dependa de cómo vengan escritos.
    const invertido = structuredClone(borrador);
    const esquemas = esquemasEn(invertido);
    const alReves = Object.entries(esquemas).reverse();
    for (const nombre of Object.keys(esquemas)) delete esquemas[nombre];
    for (const [nombre, esquema] of alReves) esquemas[nombre] = esquema;

    const claves = Object.keys(esquemasEn(subconjuntoContratoError(invertido)));

    expect(claves).toEqual(ESQUEMAS_ESPERADOS);
  });

  test("tkt008_ca02_esc01 · cabecera provisional", async () => {
    const archivos = await generarArchivos({ publicado, borrador });

    const contratoError = archivos.get(ARCHIVO_CONTRATO_ERROR);
    const servidor = archivos.get(ARCHIVO_SERVIDOR);
    expect(contratoError?.startsWith(CABECERA_PROVISIONAL)).toBe(true);
    expect(contratoError).toContain("Se retira");
    expect(servidor?.startsWith(CABECERA_SERVIDOR)).toBe(true);
  });

  test("tkt008_ca02_esc04 · determinista", async () => {
    const primera = await generarArchivos({ publicado, borrador });
    const segunda = await generarArchivos({ publicado, borrador });

    expect([...segunda.keys()]).toEqual([...primera.keys()]);
    expect(segunda.size).toBe(2);
    for (const [ruta, contenido] of primera) {
      expect(segunda.get(ruta)).toBe(contenido);
      expect(contenido).not.toContain("\r");
      expect(contenido.endsWith("\n")).toBe(true);
      expect(contenido.endsWith("\n\n")).toBe(false);
    }
  });

  test("tkt008_ca02_esc03 · desfase", async () => {
    const generados = await generarArchivos({ publicado, borrador });

    const otroServidor = diferencias(generados, (ruta) =>
      ruta === ARCHIVO_SERVIDOR ? "// otro contenido\n" : (generados.get(ruta) ?? null),
    );
    const sinProvisional = diferencias(generados, (ruta) =>
      ruta === ARCHIVO_CONTRATO_ERROR ? null : (generados.get(ruta) ?? null),
    );

    expect(otroServidor).toEqual([ARCHIVO_SERVIDOR]);
    expect(sinProvisional).toEqual([ARCHIVO_CONTRATO_ERROR]);
  });

  test("tkt008_ca02_esc05 · edición a mano", async () => {
    const generados = await generarArchivos({ publicado, borrador });

    const conLineaAMano = diferencias(generados, (ruta) =>
      ruta === ARCHIVO_CONTRATO_ERROR ? `${generados.get(ruta)}// a mano\n` : (generados.get(ruta) ?? null),
    );
    const exacto = diferencias(generados, (ruta) => generados.get(ruta) ?? null);

    expect(conLineaAMano).toEqual([ARCHIVO_CONTRATO_ERROR]);
    expect(exacto).toEqual([]);
  });

  test("tkt008_ca02_esc05 · edición de igual longitud", async () => {
    // TC-M6 · MT-6. Una edición a mano que no cambia el número de caracteres (una letra por otra) también difiere.
    const generados = await generarArchivos({ publicado, borrador });
    const original = generados.get(ARCHIVO_SERVIDOR) ?? "";
    const editado = original.replace("export", "exprot");

    expect(editado).not.toBe(original);
    expect(editado).toHaveLength(original.length);
    const difieren = diferencias(generados, (ruta) =>
      ruta === ARCHIVO_SERVIDOR ? editado : (generados.get(ruta) ?? null),
    );

    expect(difieren).toEqual([ARCHIVO_SERVIDOR]);
  });

  test("tkt008_ca02_esc01 · exportación fallida lanza con la pista de uv, PA-T10 y el stderr", () => {
    // exportarOpenapiPublicado: estado distinto de 0 lanza con la pista de uv, PA-T10 y el stderr de Python.
    const fallida: Ejecutar = () => ({ status: 1, stdout: "", stderr: "Falta la variable X" });
    expect(() => exportarOpenapiPublicado(fallida)).toThrow(/uv/);
    expect(() => exportarOpenapiPublicado(fallida)).toThrow(/PA-T10/);
    expect(() => exportarOpenapiPublicado(fallida)).toThrow(/Falta la variable X/);
  });

  test("tkt008_ca02_esc01 · exportación correcta devuelve el JSON que imprimió Python", () => {
    // Con estado 0 devuelve el JSON que imprimió Python.
    const correcta: Ejecutar = () => ({ status: 0, stdout: JSON.stringify(publicado), stderr: "" });
    expect(exportarOpenapiPublicado(correcta)).toEqual(publicado);
  });

  test("tkt008_ca02_esc01 · salida 2 · no se pudo generar, nunca se confunde con un desfase", async () => {
    // principal: los códigos de salida de la tabla del diseño.
    const generados = await generarArchivos({ publicado, borrador });
    const leerBorrador = () => borrador;

    const salidaDeError: string[] = [];
    const sinExportar = await principal(["verificar"], {
      exportar: () => {
        throw new Error("Falta uv");
      },
      leerBorrador,
      leer: (ruta) => generados.get(ruta) ?? null,
      escribir: () => {},
      escribirError: (linea) => salidaDeError.push(linea),
    });
    expect(sinExportar).toBe(2);
    expect(salidaDeError.join("\n")).toContain("No se pudieron generar los tipos");
  });

  test("tkt008_ca02_esc03 · salida 1 · archivos que difieren", async () => {
    const salidaDesfase: string[] = [];
    const desfasado = await principal(["verificar"], {
      exportar: () => publicado,
      leerBorrador: () => borrador,
      leer: () => "// desfasado\n",
      escribir: (linea) => salidaDesfase.push(linea),
      escribirError: (linea) => salidaDesfase.push(linea),
    });
    expect(desfasado).toBe(1);
    expect(salidaDesfase.join("\n")).toContain(`Difiere: ${ARCHIVO_SERVIDOR}`);
  });

  test("tkt008_ca02_esc04 · salida 0 · archivos iguales", async () => {
    const generados = await generarArchivos({ publicado, borrador });

    const salidaAlDia: string[] = [];
    const alDia = await principal(["verificar"], {
      exportar: () => publicado,
      leerBorrador: () => borrador,
      leer: (ruta) => generados.get(ruta) ?? null,
      escribir: (linea) => salidaAlDia.push(linea),
      escribirError: () => {},
    });
    expect(alDia).toBe(0);
    expect(salidaAlDia.join("\n")).toContain("Tipos al día.");
  });

  test("tkt008_ca02 · salida 3 · argumento desconocido muestra el uso y no exporta nada", async () => {
    const exportar = vi.fn(() => publicado);
    const desconocido = await principal(["otro"], { exportar, escribir: () => {}, escribirError: () => {} });
    expect(desconocido).toBe(3);
    expect(exportar).not.toHaveBeenCalled();
  });

  test("tkt008_ca02_esc01 · TC-R1a · generar escribe los dos archivos con su contenido generado", async () => {
    // Revisión · C001. El modo `generar` llama a `escribirArchivo` con cada ruta y su contenido, y lo dice.
    const generados = await generarArchivos({ publicado, borrador });
    const escritos = new Map<string, string>();
    const salida: string[] = [];

    const codigo = await principal(["generar"], {
      exportar: () => publicado,
      leerBorrador: () => borrador,
      escribirArchivo: (ruta, contenido) => {
        escritos.set(ruta, contenido);
      },
      escribir: (linea) => salida.push(linea),
      escribirError: (linea) => salida.push(linea),
    });

    expect(codigo).toBe(0);
    expect([...escritos.keys()]).toEqual([ARCHIVO_SERVIDOR, ARCHIVO_CONTRATO_ERROR]);
    expect(escritos.get(ARCHIVO_SERVIDOR)).toBe(generados.get(ARCHIVO_SERVIDOR));
    expect(escritos.get(ARCHIVO_CONTRATO_ERROR)).toBe(generados.get(ARCHIVO_CONTRATO_ERROR));
    expect(salida).toEqual([`Tipos generados: ${ARCHIVO_SERVIDOR}, ${ARCHIVO_CONTRATO_ERROR}`]);
  });

  test("tkt008_ca02_esc01 · TC-R1b · si escribir un archivo falla, sale con 2 y lo dice", async () => {
    // Revisión · C001. Un fallo de disco es «no se pudo generar» (2), no un desfase (1) ni un éxito.
    const salida: string[] = [];

    const codigo = await principal(["generar"], {
      exportar: () => publicado,
      leerBorrador: () => borrador,
      escribirArchivo: () => {
        throw new Error("Disco lleno");
      },
      escribir: (linea) => salida.push(`ok: ${linea}`),
      escribirError: (linea) => salida.push(`error: ${linea}`),
    });

    expect(codigo).toBe(2);
    expect(salida).toEqual(["error: No se pudieron generar los tipos: Disco lleno"]);
  });

  // TC-R2a · N-1 de la revisión de código de 008a · `verificar` solo lee: nunca escribe un archivo, ni al día ni desfasado.
  test.each([
    ["con los archivos al día", 0],
    ["con los archivos desfasados", 1],
  ] as const)("tkt008_ca02_esc03 · TC-R2a · verificar no escribe ningún archivo %s", async (_caso, esperado) => {
    const generados = await generarArchivos({ publicado, borrador });
    const escribirArchivo = vi.fn();

    const codigo = await principal(["verificar"], {
      exportar: () => publicado,
      leerBorrador: () => borrador,
      leer: (ruta) => (esperado === 0 ? (generados.get(ruta) ?? null) : "// desfasado\n"),
      escribirArchivo,
      escribir: () => {},
      escribirError: () => {},
    });

    expect(codigo).toBe(esperado);
    expect(escribirArchivo).not.toHaveBeenCalled();
  });
});
