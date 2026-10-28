import type { ReactNode } from "react";
import { esObjeto } from "@/api/errores";
import { formatearCantidad, formatearImporte } from "@/compartido/dinero/dinero";
import {
  CLAVE_DESGLOSE,
  CLAVE_EXCEDENTE,
  CLAVES_DETALLE,
  CLAVES_OCULTAS,
  PARTES_CONSUMIDO,
  TABLAS_DETALLE,
  type ClaveDetalle,
  type ColumnaTabla,
  type TablaDetalle,
} from "./etiquetas";

const NO_DISPONIBLE = "No disponible";
const NO_PRESUPUESTADO = "no presupuestado en esta partida";

export interface PropsDetalleCifras {
  /** El `detalle` del rechazo tal como llegó; puede venir ausente. */
  detalle: Readonly<Record<string, unknown>> | undefined;
}

const CLAVES_CONOCIDAS: ReadonlySet<string> = new Set([
  ...CLAVES_DETALLE.map((c) => c.clave),
  ...TABLAS_DETALLE.map((t) => t.clave),
  CLAVE_DESGLOSE,
  ...CLAVES_OCULTAS,
]);

/** Cadena tal cual; cualquier otra cosa, su JSON. */
function comoTexto(valor: unknown): string {
  return typeof valor === "string" ? valor : (JSON.stringify(valor) ?? NO_DISPONIBLE);
}

/** Las cifras llegan como cadena y se muestran tal como llegaron: aquí no se resta ni se suma. */
function importe(valor: unknown): string {
  return typeof valor === "string" ? (formatearImporte(valor) ?? NO_DISPONIBLE) : NO_DISPONIBLE;
}

function cantidad(valor: unknown, unidad: unknown): string {
  if (typeof valor !== "string") return NO_DISPONIBLE;
  return formatearCantidad(valor, typeof unidad === "string" ? unidad : undefined) ?? NO_DISPONIBLE;
}

function desglose(valor: unknown): string | null {
  if (!esObjeto(valor)) return null;
  return PARTES_CONSUMIDO.map(({ clave, etiqueta }) => `${etiqueta} ${importe(valor[clave])}`).join(" · ");
}

function FilaCifra({ definicion, valor, detalle }: { definicion: ClaveDetalle; valor: unknown; detalle: Readonly<Record<string, unknown>> }) {
  const resaltada = definicion.clave === CLAVE_EXCEDENTE;
  const partes = definicion.clave === "consumido" ? desglose(detalle[CLAVE_DESGLOSE]) : null;
  return (
    <div className="flex flex-wrap gap-x-3 py-1">
      <dt className="min-w-40 text-amber-900/80">{definicion.etiqueta}</dt>
      <dd className={resaltada ? "font-semibold text-amber-950" : undefined} data-resaltada={resaltada ? "true" : undefined}>
        {definicion.formato === "importe" ? importe(valor) : comoTexto(valor)}
        {resaltada ? <span aria-hidden="true"> ◄</span> : null}
        {partes === null ? null : <span className="block text-sm text-amber-900/80">{partes}</span>}
      </dd>
    </div>
  );
}

function celda(columna: ColumnaTabla, fila: Readonly<Record<string, unknown>>): string {
  const valor = fila[columna.campo];
  if (columna.tipo === "cantidad") return cantidad(valor, fila.unidad);
  return valor === undefined ? "" : comoTexto(valor);
}

function Tabla({ tabla, filas }: { tabla: TablaDetalle; filas: ReadonlyArray<Readonly<Record<string, unknown>>> }) {
  return (
    <table className="mt-3 w-full text-left text-sm">
      <caption className="pb-1 text-left font-medium">{tabla.titulo}</caption>
      <thead>
        <tr>
          {tabla.columnas.map((columna) => (
            <th key={columna.campo} scope="col" className="pr-3 font-medium">
              {columna.encabezado}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {filas.map((fila, indice) => (
          <tr key={indice} className="border-t border-amber-200">
            {tabla.columnas.map((columna, posicion) => (
              <td key={columna.campo} className="py-1 pr-3">
                {celda(columna, fila)}
                {posicion === 0 && tabla.campoPresupuestado !== undefined && fila[tabla.campoPresupuestado] === false ? (
                  <span className="block text-xs text-amber-900/80">{NO_PRESUPUESTADO}</span>
                ) : null}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Pinta las cifras de un rechazo: las claves conocidas con su rótulo, las tablas y, al final, toda clave desconocida. */
export function DetalleCifras({ detalle }: PropsDetalleCifras): ReactNode {
  if (detalle === undefined || !esObjeto(detalle)) return null;

  const conocidas = CLAVES_DETALLE.filter((definicion) => detalle[definicion.clave] !== undefined);
  const tablas = TABLAS_DETALLE.flatMap((tabla) => {
    const valor = detalle[tabla.clave];
    const filas = Array.isArray(valor) ? valor.filter(esObjeto) : [];
    return filas.length > 0 ? [{ tabla, filas }] : [];
  });
  const desconocidas = Object.entries(detalle).filter(
    ([clave, valor]) => !CLAVES_CONOCIDAS.has(clave) && valor !== undefined,
  );

  return (
    <>
      {conocidas.length > 0 ? (
        <dl className="mt-3">
          {conocidas.map((definicion) => (
            <FilaCifra key={definicion.clave} definicion={definicion} valor={detalle[definicion.clave]} detalle={detalle} />
          ))}
        </dl>
      ) : null}
      {tablas.map(({ tabla, filas }) => (
        <Tabla key={tabla.clave} tabla={tabla} filas={filas} />
      ))}
      {desconocidas.length > 0 ? (
        <dl className="mt-3">
          {desconocidas.map(([clave, valor]) => (
            <div key={clave} className="flex flex-wrap gap-x-3 py-1">
              <dt className="min-w-40 text-amber-900/80">{clave}</dt>
              <dd>{comoTexto(valor)}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </>
  );
}
