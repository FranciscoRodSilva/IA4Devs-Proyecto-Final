import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { delimiter } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Preparación global del humo. Siembra en la base local, con el script de `e2e/sembrar_usuario_humo.py`,
 * dos usuarios de humo:
 *
 * - COMPRAS (TKT-008): `humo.compras@cimenta.test`, el que usa `humo.spec.ts`.
 * - DIRECTOR_PROYECTOS (TKT-012a B5): `humo.director@cimenta.test`, el que da de alta obras en `obras.spec.ts`.
 *
 * El script es idempotente: los correos son fijos y se reutilizan (D-4), así que la contraseña cambia en
 * cada corrida y ningún secreto vive en el repositorio. Las contraseñas se dejan en el entorno del proceso
 * de pruebas, nunca en un archivo.
 */

const CORREO_HUMO_COMPRAS = "humo.compras@cimenta.test";
const CORREO_HUMO_DIRECTOR = "humo.director@cimenta.test";

const BACKEND = fileURLToPath(new URL("../../backend", import.meta.url));

interface UsuarioDeHumo {
  correo: string;
  contrasena: string;
}

function sembrarUsuarioDeHumo(correo: string, rol: string, nombre: string): UsuarioDeHumo {
  const contrasena = randomBytes(24).toString("base64url");

  const resultado = spawnSync(
    "uv",
    ["run", "--locked", "--env-file", "../.env", "python", "../frontend/e2e/sembrar_usuario_humo.py"],
    {
      cwd: BACKEND,
      encoding: "utf8",
      env: {
        ...process.env,
        PYTHONPATH: process.env.PYTHONPATH ? `.${delimiter}${process.env.PYTHONPATH}` : ".",
        CIMENTA_HUMO_CORREO: correo,
        CIMENTA_HUMO_CONTRASENA: contrasena,
        CIMENTA_HUMO_ROL: rol,
        CIMENTA_HUMO_NOMBRE: nombre,
      },
    },
  );

  if (resultado.status !== 0) {
    const detalle = [resultado.stderr, resultado.error?.message].filter(Boolean).join("\n");
    throw new Error(
      `No se pudo sembrar el usuario de humo ${rol}. ¿Corre \`docker compose up -d db\` y está migrada la base?\n${detalle}`,
    );
  }

  return { correo, contrasena };
}

export default function preparacionGlobal(): void {
  const compras = sembrarUsuarioDeHumo(CORREO_HUMO_COMPRAS, "COMPRAS", "Humo Compras");
  process.env.CIMENTA_HUMO_CORREO = compras.correo;
  process.env.CIMENTA_HUMO_CONTRASENA = compras.contrasena;

  const director = sembrarUsuarioDeHumo(CORREO_HUMO_DIRECTOR, "DIRECTOR_PROYECTOS", "Humo Director de Proyectos");
  process.env.CIMENTA_HUMO_DP_CORREO = director.correo;
  process.env.CIMENTA_HUMO_DP_CONTRASENA = director.contrasena;
}
