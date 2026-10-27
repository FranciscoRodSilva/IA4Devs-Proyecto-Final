import { spawnSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { delimiter } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Preparación global del humo de TKT-008 (CA-14). Siembra el único usuario de humo en la base local
 * con el script de `e2e/sembrar_usuario_humo.py`, que es idempotente: el correo es fijo y se reutiliza
 * (D-4), así que la contraseña cambia en cada corrida y ningún secreto vive en el repositorio.
 */

const CORREO_HUMO = "humo.compras@cimenta.test";

export default function preparacionGlobal(): void {
  const contrasena = randomBytes(24).toString("base64url");
  const backend = fileURLToPath(new URL("../../backend", import.meta.url));

  const resultado = spawnSync(
    "uv",
    ["run", "--locked", "--env-file", "../.env", "python", "../frontend/e2e/sembrar_usuario_humo.py"],
    {
      cwd: backend,
      encoding: "utf8",
      env: {
        ...process.env,
        PYTHONPATH: process.env.PYTHONPATH ? `.${delimiter}${process.env.PYTHONPATH}` : ".",
        CIMENTA_HUMO_CORREO: CORREO_HUMO,
        CIMENTA_HUMO_CONTRASENA: contrasena,
      },
    },
  );

  if (resultado.status !== 0) {
    const detalle = [resultado.stderr, resultado.error?.message].filter(Boolean).join("\n");
    throw new Error(
      `No se pudo sembrar el usuario de humo. ¿Corre \`docker compose up -d db\` y está migrada la base?\n${detalle}`,
    );
  }

  process.env.CIMENTA_HUMO_CORREO = CORREO_HUMO;
  process.env.CIMENTA_HUMO_CONTRASENA = contrasena;
}
