import { spawnSync } from "node:child_process";
import { delimiter } from "node:path";
import { fileURLToPath } from "node:url";

/**
 * Ayuda de siembra de TKT-032a (F10): crea en la base local una orden de compra `PARCIAL` contra un
 * proveedor que el spec acaba de dar de alta, con `herramientas.semilla_orden_proveedor_local`. Así la baja
 * con órdenes pendientes (CA-8) se prueba de punta a punta con el `409` real del servidor, sin esperar a que
 * exista el flujo de órdenes de TKT-030.
 *
 * El sembrador lee tres variables de entorno que esta ayuda fija, sin valor por omisión:
 *
 * - `CIMENTA_SEMILLA_OC_RFC`: el RFC del proveedor (el sembrador resuelve su identificador por RFC).
 * - `CIMENTA_SEMILLA_OC_OBRA_ID`: la obra de humo (`CIMENTA_HUMO_LB_OBRA_ID`).
 * - `CIMENTA_SEMILLA_OC_CORREO`: el correo del solicitante (el usuario de Compras de humo).
 *
 * Deja como última línea de la salida `ORDEN_ID=<uuid>`. El folio es `OC-E2E-<8 hex>` y lo escoge el
 * sembrador e imprime también una línea `FOLIO=<folio>`: esta ayuda exige que exista y que empiece por `OC-`.
 * Sin identificador, sin línea de folio o con un folio que no empieza por `OC-`, la ayuda lanza con un mensaje
 * que dice qué faltó y qué imprimió el sembrador: nunca devuelve el identificador de una orden que no se sembró.
 */

const BACKEND = fileURLToPath(new URL("../../backend", import.meta.url));

const PREFIJO_ORDEN_ID = "ORDEN_ID=";
const PREFIJO_FOLIO = "FOLIO=";
const PREFIJO_DE_FOLIO = "OC-";
const FORMA_DE_UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export interface EntradaOrdenParcial {
  /** RFC del proveedor ya dado de alta, tal como lo normaliza el servidor (mayúsculas). */
  rfc: string;
  /** Identificador de la obra de humo. */
  obraId: string;
  /** Correo del usuario que figura como solicitante. */
  correo: string;
}

export interface OrdenSembrada {
  ordenId: string;
  /** El folio que imprimió el sembrador; siempre empieza por `OC-`. */
  folio: string;
}

function exigirTexto(nombre: string, valor: string): string {
  if (valor.trim() === "") {
    throw new Error(`sembrarOrdenParcial: falta ${nombre}.`);
  }
  return valor;
}

function lineasNoVacias(salida: string | null | undefined): string[] {
  return (salida ?? "")
    .split(/\r?\n/)
    .map((linea) => linea.trim())
    .filter((linea) => linea !== "");
}

/**
 * Siembra una orden `PARCIAL` contra el proveedor de `rfc` y devuelve su identificador. Corre en `backend/`
 * con el mismo `uv run --locked --env-file ../.env python …` que usa `preparacion-global.ts`.
 */
export function sembrarOrdenParcial({ rfc, obraId, correo }: EntradaOrdenParcial): OrdenSembrada {
  const resultado = spawnSync(
    "uv",
    ["run", "--locked", "--env-file", "../.env", "python", "-m", "herramientas.semilla_orden_proveedor_local"],
    {
      cwd: BACKEND,
      encoding: "utf8",
      timeout: 120_000,
      env: {
        ...process.env,
        PYTHONPATH: process.env.PYTHONPATH ? `.${delimiter}${process.env.PYTHONPATH}` : ".",
        CIMENTA_SEMILLA_OC_RFC: exigirTexto("el RFC del proveedor", rfc),
        CIMENTA_SEMILLA_OC_OBRA_ID: exigirTexto("el identificador de la obra", obraId),
        CIMENTA_SEMILLA_OC_CORREO: exigirTexto("el correo del solicitante", correo),
      },
    },
  );

  const detalleDelFallo = [resultado.stderr, resultado.error?.message].filter(Boolean).join("\n");
  const fallo = (motivo: string): Error =>
    new Error(
      `No se pudo sembrar la orden PARCIAL del proveedor ${rfc}: ${motivo}. ¿Corre \`docker compose up -d db\`, está migrada la base y existe el sembrador \`herramientas.semilla_orden_proveedor_local\`?\n${detalleDelFallo}`,
    );

  if (resultado.error !== undefined || resultado.status !== 0) {
    throw fallo(`el sembrador salió con estado ${String(resultado.status)}`);
  }

  const lineas = lineasNoVacias(resultado.stdout);
  const ultima = lineas[lineas.length - 1] ?? "";
  if (!ultima.startsWith(PREFIJO_ORDEN_ID)) {
    throw fallo(`la última línea de la salida no es ${PREFIJO_ORDEN_ID}<uuid> (fue «${ultima}»)`);
  }
  const ordenId = ultima.slice(PREFIJO_ORDEN_ID.length);
  if (!FORMA_DE_UUID.test(ordenId)) {
    throw fallo(`ORDEN_ID no tiene forma de uuid (fue «${ordenId}»)`);
  }

  const lineaDeFolio = lineas.find((linea) => linea.startsWith(PREFIJO_FOLIO));
  if (lineaDeFolio === undefined) {
    throw fallo(`no hay línea ${PREFIJO_FOLIO}`);
  }
  const folio = lineaDeFolio.slice(PREFIJO_FOLIO.length);
  if (!folio.startsWith(PREFIJO_DE_FOLIO)) {
    throw fallo(`el folio no empieza por ${PREFIJO_DE_FOLIO} (fue «${folio}»)`);
  }

  return { ordenId, folio };
}
