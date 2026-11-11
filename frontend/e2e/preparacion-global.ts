import { spawnSync, type SpawnSyncReturns } from "node:child_process";
import { randomBytes } from "node:crypto";
import { delimiter } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Preparación global del humo. Siembra en la base local tres usuarios de humo, con el script de
 * `e2e/sembrar_usuario_humo.py`:
 *
 * - COMPRAS (TKT-008): `humo.compras@cimenta.test`, el que usa `humo.spec.ts`.
 * - DIRECTOR_PROYECTOS (TKT-012a B5): `humo.director@cimenta.test`, el que da de alta obras en `obras.spec.ts`
 *   y congela la línea base en `linea-base.spec.ts`.
 * - DIRECCION_GENERAL (TKT-018a D-9): `humo.direccion@cimenta.test`, la que captura el tope en `linea-base.spec.ts`.
 *
 * Después siembra, con `herramientas.semilla_linea_base_local`, una obra nueva `E2E-LB-<8 hex>` con línea base
 * BORRADOR, y deja su identificador en `CIMENTA_HUMO_LB_OBRA_ID`.
 *
 * El script es idempotente: los correos son fijos y se reutilizan (D-4), así que la contraseña cambia en
 * cada corrida y ningún secreto vive en el repositorio. Las contraseñas se dejan en el entorno del proceso
 * de pruebas, nunca en un archivo.
 */

const CORREO_HUMO_COMPRAS = "humo.compras@cimenta.test";
const CORREO_HUMO_DIRECTOR = "humo.director@cimenta.test";
const CORREO_HUMO_DIRECCION = "humo.direccion@cimenta.test";

const BACKEND = fileURLToPath(new URL("../../backend", import.meta.url));

interface UsuarioDeHumo {
  correo: string;
  contrasena: string;
}

/** Ejecuta `uv run --locked --env-file ../.env python …` en `backend/` y devuelve el resultado sin lanzar. */
function ejecutarEnBackend(
  argumentosPython: string[],
  entorno: Record<string, string>,
): SpawnSyncReturns<string> {
  return spawnSync("uv", ["run", "--locked", "--env-file", "../.env", "python", ...argumentosPython], {
    cwd: BACKEND,
    encoding: "utf8",
    env: {
      ...process.env,
      PYTHONPATH: process.env.PYTHONPATH ? `.${delimiter}${process.env.PYTHONPATH}` : ".",
      ...entorno,
    },
  });
}

/** Lo que el proceso escribió por error y, si no llegó a arrancar, el motivo (p. ej. `uv` fuera del PATH). */
function detalleDelFallo(resultado: SpawnSyncReturns<string>): string {
  return [resultado.stderr, resultado.error?.message].filter(Boolean).join("\n");
}

function sembrarUsuarioDeHumo(correo: string, rol: string, nombre: string): UsuarioDeHumo {
  const contrasena = randomBytes(24).toString("base64url");

  const resultado = ejecutarEnBackend(["../frontend/e2e/sembrar_usuario_humo.py"], {
    CIMENTA_HUMO_CORREO: correo,
    CIMENTA_HUMO_CONTRASENA: contrasena,
    CIMENTA_HUMO_ROL: rol,
    CIMENTA_HUMO_NOMBRE: nombre,
  });

  if (resultado.status !== 0) {
    throw new Error(
      `No se pudo sembrar el usuario de humo ${rol}. ¿Corre \`docker compose up -d db\` y está migrada la base?\n${detalleDelFallo(resultado)}`,
    );
  }

  return { correo, contrasena };
}

/**
 * Crea la obra `E2E-LB-<8 hex>` con su línea base BORRADOR y devuelve su identificador, que el script deja
 * como última línea de salida (`OBRA_ID=<uuid>`). Un código nuevo en cada corrida evita chocar con la obra
 * de la corrida anterior.
 */
function sembrarLineaBaseDeHumo(correoDirector: string): string {
  const codigo = `E2E-LB-${randomBytes(4).toString("hex").toUpperCase()}`;

  const resultado = ejecutarEnBackend(["-m", "herramientas.semilla_linea_base_local"], {
    CIMENTA_SEMILLA_LB_CODIGO: codigo,
    CIMENTA_SEMILLA_LB_CORREO: correoDirector,
  });

  const errorDeSiembra = (): Error =>
    new Error(
      `No se pudo sembrar la línea base de humo (${codigo}). ¿Corre \`docker compose up -d db\` y está migrada la base?\n${detalleDelFallo(resultado)}`,
    );

  if (resultado.error !== undefined || resultado.status !== 0) {
    throw errorDeSiembra();
  }

  const lineas = (resultado.stdout ?? "")
    .split(/\r?\n/)
    .map((linea) => linea.trim())
    .filter((linea) => linea !== "");
  const ultima = lineas[lineas.length - 1] ?? "";
  const obraId = ultima.startsWith("OBRA_ID=") ? ultima.slice("OBRA_ID=".length) : "";

  if (obraId === "") {
    throw errorDeSiembra();
  }

  return obraId;
}

export default function preparacionGlobal(): void {
  const compras = sembrarUsuarioDeHumo(CORREO_HUMO_COMPRAS, "COMPRAS", "Humo Compras");
  process.env.CIMENTA_HUMO_CORREO = compras.correo;
  process.env.CIMENTA_HUMO_CONTRASENA = compras.contrasena;

  const director = sembrarUsuarioDeHumo(CORREO_HUMO_DIRECTOR, "DIRECTOR_PROYECTOS", "Humo Director de Proyectos");
  process.env.CIMENTA_HUMO_DP_CORREO = director.correo;
  process.env.CIMENTA_HUMO_DP_CONTRASENA = director.contrasena;

  const direccion = sembrarUsuarioDeHumo(CORREO_HUMO_DIRECCION, "DIRECCION_GENERAL", "Humo Direccion General");
  process.env.CIMENTA_HUMO_DG_CORREO = direccion.correo;
  process.env.CIMENTA_HUMO_DG_CONTRASENA = direccion.contrasena;

  process.env.CIMENTA_HUMO_LB_OBRA_ID = sembrarLineaBaseDeHumo(director.correo);
}
