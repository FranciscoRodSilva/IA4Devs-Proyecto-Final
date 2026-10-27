import { spawnSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";
import { parse } from "yaml";

// Rutas fijas: el script vive en frontend/scripts/, y el borrador y el backend están en la raíz del repositorio.
const FRONTEND = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const BACKEND = resolve(FRONTEND, "..", "backend");
const BORRADOR = resolve(FRONTEND, "..", "docs", "api", "openapi.yaml");

export const ARCHIVO_SERVIDOR = "src/api/generado/servidor.ts";
export const ARCHIVO_CONTRATO_ERROR = "src/api/generado/contrato-error.provisional.ts";
export const RAICES_CONTRATO_ERROR = [
  "ErrorConflicto", "ErrorReglaNegocio", "ErrorConflictoEstado", "ErrorConcurrencia", "ErrorValidacion",
  "ErrorPermiso", "ErrorSesion", "ErrorLimiteIntentos", "ErrorNoEncontrado",
] as const;

export const CABECERA_SERVIDOR = [
  "// Generado por `npm run tipos:generar` del OpenAPI que publica FastAPI",
  "// (servidor.fabrica.crear_aplicacion, sin servidor en marcha). No se edita a mano:",
  "// `npm run tipos:verificar` falla si este archivo difiere de lo que se generaría.",
  "", "",
].join("\n");
export const CABECERA_PROVISIONAL = [
  "// PROVISIONAL (TKT-008, PA-T1). Tipos del contrato de error generados del borrador",
  "// docs/api/openapi.yaml, porque el OpenAPI que publica FastAPI todavía no declara los",
  "// esquemas de error. Se retira cuando el servidor los publique con responses= en cada",
  "// ruta (ticket futuro, antes de TKT-061). Generado por `npm run tipos:generar`.",
  "// No se edita a mano: `npm run tipos:verificar` lo detecta.",
  "", "",
].join("\n");

const CODIGO_EXPORTACION = [
  "import json, sys",
  "from servidor.fabrica import crear_aplicacion",
  "esquema = crear_aplicacion(destino_registro=sys.stderr, entorno={}).openapi()",
  "sys.stdout.write(json.dumps(esquema, ensure_ascii=True))",
].join("\n");

const PREFIJO_ESQUEMA = "#/components/schemas/";
const TAMANO_MAXIMO_SALIDA = 64 * 1024 * 1024;
const USO = "Uso: node scripts/tipos.ts <generar|verificar>";

export type Documento = Record<string, unknown>;
export type Ejecutar = (comando: string, argumentos: string[], cwd: string) =>
  { status: number | null; stdout: string; stderr: string };

type Dependencias = {
  exportar?: () => Documento;
  leerBorrador?: () => Documento;
  leer?: (ruta: string) => string | null;
  escribirArchivo?: (ruta: string, contenido: string) => void;
  escribir?: (linea: string) => void;
  escribirError?: (linea: string) => void;
};

function esDocumento(valor: unknown): valor is Documento {
  return typeof valor === "object" && valor !== null && !Array.isArray(valor);
}

function mensajeDe(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function esNoExiste(error: unknown): boolean {
  return error instanceof Error && "code" in error && error.code === "ENOENT";
}

function esquemasDe(documento: Documento): Documento {
  const componentes = documento["components"];
  const esquemas = esDocumento(componentes) ? componentes["schemas"] : undefined;
  if (!esDocumento(esquemas)) throw new Error("El documento no tiene components.schemas.");
  return esquemas;
}

/** Todo `$ref` de `#/components/schemas/X` que aparece en cualquier profundidad de `nodo`. */
function referenciasDe(nodo: unknown, acumulado: string[] = []): string[] {
  if (Array.isArray(nodo)) {
    for (const elemento of nodo) referenciasDe(elemento, acumulado);
  } else if (esDocumento(nodo)) {
    for (const [clave, valor] of Object.entries(nodo)) {
      if (clave === "$ref" && typeof valor === "string") acumulado.push(valor);
      else referenciasDe(valor, acumulado);
    }
  }
  return acumulado;
}

/** Recoge `nombre` y todo lo que alcanza. Un esquema ausente en el borrador lanza nombrándolo. */
function recoger(nombre: string, esquemas: Documento, incluidos: Map<string, unknown>): void {
  if (incluidos.has(nombre)) return;
  if (!Object.hasOwn(esquemas, nombre)) {
    throw new Error(`El borrador no define el esquema ${nombre}, que el contrato de error alcanza.`);
  }
  const esquema = esquemas[nombre];
  incluidos.set(nombre, esquema);
  for (const referencia of referenciasDe(esquema)) {
    if (!referencia.startsWith(PREFIJO_ESQUEMA)) {
      throw new Error(`El borrador referencia ${referencia}, fuera de components.schemas.`);
    }
    recoger(referencia.slice(PREFIJO_ESQUEMA.length), esquemas, incluidos);
  }
}

const EJECUTAR_UV: Ejecutar = (comando, argumentos, cwd) => {
  const resultado = spawnSync(comando, argumentos, {
    cwd,
    encoding: "utf8",
    shell: false,
    maxBuffer: TAMANO_MAXIMO_SALIDA,
  });
  if (resultado.error) return { status: null, stdout: "", stderr: resultado.error.message };
  return { status: resultado.status, stdout: resultado.stdout, stderr: resultado.stderr };
};

/** M2 · PA-T10. Ejecuta `uv run --locked python -c CODIGO_EXPORTACION` con cwd = backend/ y devuelve el
 *  JSON. Estado distinto de 0: lanza Error con «No se pudo exportar el OpenAPI publicado: hace falta uv y
 *  `uv sync --locked` en backend/ (PA-T10).» seguido del stderr. ensure_ascii evita la página de códigos
 *  de la consola de Windows. Por omisión `ejecutar` es spawnSync con encoding utf8, shell false y
 *  maxBuffer de 64 MiB. */
export function exportarOpenapiPublicado(ejecutar: Ejecutar = EJECUTAR_UV): Documento {
  const resultado = ejecutar("uv", ["run", "--locked", "python", "-c", CODIGO_EXPORTACION], BACKEND);
  if (resultado.status !== 0) {
    throw new Error(
      "No se pudo exportar el OpenAPI publicado: hace falta uv y `uv sync --locked` en backend/ (PA-T10).\n" +
        resultado.stderr,
    );
  }
  const valor: unknown = JSON.parse(resultado.stdout);
  if (!esDocumento(valor)) throw new Error("La exportación del OpenAPI publicado no es un objeto JSON.");
  return valor;
}

/** Copia profunda: todo objeto con `const` y sin `enum` gana `enum: [const]`. Un `const` cuyo valor es un
 *  esquema (una propiedad que se llama `const`) no se convierte. */
export function constComoEnum(nodo: unknown): unknown {
  if (Array.isArray(nodo)) return nodo.map((elemento) => constComoEnum(elemento));
  if (!esDocumento(nodo)) return nodo;
  const copia: Documento = {};
  for (const [clave, valor] of Object.entries(nodo)) copia[clave] = constComoEnum(valor);
  if ("const" in copia && !("enum" in copia) && !esDocumento(copia["const"])) {
    copia["enum"] = [copia["const"]];
  }
  return copia;
}

/** Documento OpenAPI con `openapi` e `info.version` del borrador, `info.title` = «CIMENTA · contrato de
 *  error (provisional)», `paths: {}` y en `components.schemas` las RAICES y todo lo que alcanzan por
 *  `$ref: '#/components/schemas/X'`, recorrido a cualquier profundidad, con las claves en orden
 *  alfabético. Un $ref que no existe en el borrador lanza Error nombrándolo. */
export function subconjuntoContratoError(borrador: Documento): Documento {
  const esquemas = esquemasDe(borrador);
  const incluidos = new Map<string, unknown>();
  for (const raiz of RAICES_CONTRATO_ERROR) recoger(raiz, esquemas, incluidos);

  const seleccionados = Object.fromEntries(
    [...incluidos.keys()].sort().map((nombre) => [nombre, incluidos.get(nombre)]),
  );
  const info = borrador["info"];
  return {
    openapi: borrador["openapi"],
    info: {
      title: "CIMENTA · contrato de error (provisional)",
      version: esDocumento(info) ? info["version"] : undefined,
    },
    paths: {},
    components: { schemas: seleccionados },
  };
}

async function aTipos(documento: Documento): Promise<string> {
  // `constComoEnum` devuelve `unknown` y `openapiTS` espera su tipo de documento OpenAPI, que no se puede
  // estrechar sin duplicar su esquema: el aserto es el único punto donde se cruza esa frontera.
  const ast = await openapiTS(constComoEnum(documento) as Parameters<typeof openapiTS>[0]);
  return astToString(ast);
}

/** Un solo final de línea LF: convierte CRLF y deja exactamente un `\n` al final. */
function normalizar(texto: string): string {
  return `${texto.replace(/\r\n/g, "\n").replace(/\n+$/, "")}\n`;
}

/** Devuelve las dos rutas con su contenido: cabecera + astToString(await openapiTS(constComoEnum(doc))),
 *  con \r\n → \n y exactamente un \n final. */
export async function generarArchivos(entradas: { publicado: Documento; borrador: Documento }):
  Promise<Map<string, string>> {
  const servidor = await aTipos(entradas.publicado);
  const contratoError = await aTipos(subconjuntoContratoError(entradas.borrador));
  return new Map([
    [ARCHIVO_SERVIDOR, normalizar(CABECERA_SERVIDOR + servidor)],
    [ARCHIVO_CONTRATO_ERROR, normalizar(CABECERA_PROVISIONAL + contratoError)],
  ]);
}

/** Rutas cuyo contenido en disco (leer devuelve null si no existe) difiere del generado, en el orden de
 *  ARCHIVO_SERVIDOR, ARCHIVO_CONTRATO_ERROR. */
export function diferencias(generados: Map<string, string>, leer: (ruta: string) => string | null): string[] {
  return [ARCHIVO_SERVIDOR, ARCHIVO_CONTRATO_ERROR].filter(
    (ruta) => leer(ruta) !== (generados.get(ruta) ?? null),
  );
}

function leerBorradorDisco(): Documento {
  const valor: unknown = parse(readFileSync(BORRADOR, "utf8"));
  if (!esDocumento(valor)) throw new Error(`${BORRADOR} no es un documento OpenAPI.`);
  return valor;
}

function leerDisco(ruta: string): string | null {
  try {
    return readFileSync(resolve(FRONTEND, ruta), "utf8");
  } catch (error) {
    if (esNoExiste(error)) return null;
    throw error;
  }
}

function escribirDisco(ruta: string, contenido: string): void {
  const absoluta = resolve(FRONTEND, ruta);
  mkdirSync(dirname(absoluta), { recursive: true });
  writeFileSync(absoluta, contenido, "utf8");
}

/** El modo `generar` o `verificar` completo, con sus dependencias inyectables; devuelve el código de
 *  salida de la tabla de abajo y escribe sus mensajes con `escribir` y `escribirError`. Por omisión
 *  exporta con uv, lee el borrador del disco y lee y escribe los archivos reales. El bloque principal
 *  solo hace `process.exitCode = await principal(process.argv.slice(2))`. */
export async function principal(
  argumentos: string[],
  dependencias: Dependencias = {},
): Promise<number> {
  const {
    exportar = () => exportarOpenapiPublicado(),
    leerBorrador = leerBorradorDisco,
    leer = leerDisco,
    escribirArchivo = escribirDisco,
    escribir = (linea: string) => console.log(linea),
    escribirError = (linea: string) => console.error(linea),
  } = dependencias;

  const modo = argumentos[0];
  if (argumentos.length !== 1 || (modo !== "generar" && modo !== "verificar")) {
    escribirError(USO);
    return 3;
  }

  let generados: Map<string, string>;
  try {
    generados = await generarArchivos({ publicado: exportar(), borrador: leerBorrador() });
    if (modo === "generar") {
      for (const [ruta, contenido] of generados) escribirArchivo(ruta, contenido);
    }
  } catch (error) {
    escribirError(`No se pudieron generar los tipos: ${mensajeDe(error)}`);
    return 2;
  }

  if (modo === "generar") {
    escribir(`Tipos generados: ${[...generados.keys()].join(", ")}`);
    return 0;
  }

  const difieren = diferencias(generados, leer);
  if (difieren.length === 0) {
    escribir("Tipos al día.");
    return 0;
  }
  for (const ruta of difieren) escribirError(`Difiere: ${ruta}`);
  escribirError("Ejecuta npm run tipos:generar y versiona el resultado.");
  return 1;
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  process.exitCode = await principal(process.argv.slice(2));
}
