import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";
import { FalloApi } from "@/api/cliente";
import type { ErrorApi, ErrorConflictoEstado } from "@/api/errores";
import type { components } from "@/api/generado/servidor";
import { useApi } from "@/api/ProveedorApi";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { CapturaMotivo } from "@/compartido/formularios/CapturaMotivo";
import { DialogoRecaptura } from "./DialogoRecaptura";
import { capturarTope, clavesLineaBase, controlOptions } from "./linea-base.consultas";
import { autorYFecha, importe, mensajeDeFila, mensajeDeRechazo } from "./presentacion";
import { type EntradaTopes, resolverTopes } from "./tope.formulario";

type PresupuestoControl = components["schemas"]["PresupuestoControl"];

const CODIGO_TOPE_SUPERIOR = "TOPE_SUPERIOR_A_VENTA_SIN_CONFIRMAR";
const VALORES_VACIOS: EntradaTopes = { MUROS: "", PLAFONES_Y_CAJILLOS: "", ENCHAPES: "", GENERALES: "" };

/** Un tope que el servidor pidió confirmar: el mismo importe que se capturó, a la espera del motivo. */
interface PorConfirmar {
  fila: PresupuestoControl;
  importe: string;
  error: ErrorConflictoEstado;
}

interface Resumen {
  guardadas: string[];
  fallidas: string[];
}

function esTopeSuperior(error: ErrorApi): error is ErrorConflictoEstado {
  return error.tipo === "CONFLICTO" && error.codigo === CODIGO_TOPE_SUPERIOR;
}

function EsqueletoControl() {
  return (
    <div role="status" aria-busy="true" aria-label="Cargando el presupuesto de control" className="space-y-2">
      {[0, 1, 2, 3].map((indice) => (
        <div key={indice} className="h-8 animate-pulse rounded bg-muted" />
      ))}
    </div>
  );
}

function ErrorControl({ error, alReintentar }: { error: unknown; alReintentar: () => void }) {
  return (
    <div role="alert" className="grid gap-2 rounded-md border border-destructive/40 p-4 text-sm">
      <p className="font-medium">No se pudo cargar el presupuesto de control.</p>
      {error instanceof FalloApi ? <p>{mensajeDeRechazo(error.error)}</p> : null}
      <div>
        <Button type="button" variant="outline" onClick={alReintentar}>
          Reintentar
        </Button>
      </div>
    </div>
  );
}

function CeldaCapturado({ fila }: { fila: PresupuestoControl }) {
  const captura = autorYFecha(fila);
  if (captura === null) return <>sin capturar</>;
  return (
    <>
      {captura.nombre}
      {captura.fecha === null ? null : (
        <>
          {" · "}
          <time dateTime={captura.instante}>{captura.fecha}</time>
        </>
      )}
    </>
  );
}

function Resultado({ resumen }: { resumen: Resumen }) {
  return (
    <div role="status" className="grid gap-1 text-sm">
      {resumen.guardadas.length === 0 ? null : <p>{`Se guardaron: ${resumen.guardadas.join(", ")}.`}</p>}
      {resumen.fallidas.length === 0 ? null : <p>{`No se guardó: ${resumen.fallidas.join(", ")}.`}</p>}
    </div>
  );
}

/** Descripción del diálogo de confirmación: las dos cifras del `409`, y si faltan, las que ya se conocen. */
function descripcionTopeSuperior({ fila, importe: capturado, error }: PorConfirmar): string {
  const deDetalle = (valor: unknown, alternativa: string) => (typeof valor === "string" ? valor : alternativa);
  const venta = importe(deDetalle(error.detalle.importe_venta, fila.importe_venta));
  const tope = importe(deDetalle(error.detalle.importe_tope, capturado));
  return `Venta ${venta} · Tope ${tope}. ${error.mensaje}`;
}

/**
 * RN-03 · wireframe 4b. El presupuesto de control por tipo de partida de una línea base CONGELADA.
 * El cliente no evalúa nada: envía los topes y pinta lo que el servidor responde, incluida la confirmación
 * de un tope mayor que la venta.
 */
export function TablaPresupuestoControl({
  lineaBaseId,
  puedeCapturar,
}: {
  lineaBaseId: string;
  puedeCapturar: boolean;
}) {
  const api = useApi();
  const queryClient = useQueryClient();
  const idBase = useId();
  const control = useQuery(controlOptions(api, lineaBaseId));
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [cola, setCola] = useState<PorConfirmar[]>([]);
  const [recapturando, setRecapturando] = useState<PresupuestoControl | null>(null);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<EntradaTopes>({ resolver: resolverTopes, defaultValues: VALORES_VACIOS });

  if (control.data === undefined && control.isError) return <ErrorControl error={control.error} alReintentar={() => void control.refetch()} />;
  if (control.isPending) return <EsqueletoControl />;

  const filas = control.data;
  const hayPendientes = filas.some((fila) => fila.importe_tope === null);

  function invalidarControl() {
    return queryClient.invalidateQueries({ queryKey: clavesLineaBase.control(lineaBaseId) });
  }

  async function enviarTopes(valores: EntradaTopes) {
    setResumen(null);
    setCola([]);
    const guardadas: string[] = [];
    const fallidas: string[] = [];
    const porConfirmar: PorConfirmar[] = [];
    const pendientes = filas.filter((fila) => fila.importe_tope === null && valores[fila.tipo_partida.clave] !== "");
    for (const fila of pendientes) {
      const clave = fila.tipo_partida.clave;
      const resultado = await capturarTope(api, lineaBaseId, fila.tipo_partida.id, {
        importe_tope: valores[clave],
        confirmar_superior_a_venta: false,
      });
      if (resultado.ok) {
        guardadas.push(fila.tipo_partida.nombre);
        continue;
      }
      fallidas.push(fila.tipo_partida.nombre);
      if (esTopeSuperior(resultado.error)) {
        porConfirmar.push({ fila, importe: valores[clave], error: resultado.error });
      } else {
        setError(clave, { type: "servidor", message: mensajeDeFila(resultado.error) });
      }
    }
    setResumen({ guardadas, fallidas });
    setCola(porConfirmar);
    if (guardadas.length > 0) await invalidarControl();
  }

  const enCurso = cola[0];

  function sacarDeLaCola(id: string) {
    setCola((actual) => actual.filter((pendiente) => pendiente.fila.tipo_partida.id !== id));
  }

  return (
    <div className="grid gap-4">
      <h2 className="text-lg font-semibold">Presupuesto de control</h2>
      <form noValidate onSubmit={handleSubmit(enviarTopes)} className="grid gap-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b text-left">
              <th scope="col" className="px-3 py-2 font-medium">
                Tipo de partida
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Venta
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Sugerido
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Tope de control
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Capturado
              </th>
            </tr>
          </thead>
          <tbody>
            {filas.map((fila) => {
              const clave = fila.tipo_partida.clave;
              const mensaje = errors[clave]?.message;
              const idMensaje = `${idBase}-${clave}`;
              return (
                <tr key={fila.tipo_partida.id} className="border-b">
                  <th scope="row" className="px-3 py-2 text-left font-normal">
                    {fila.tipo_partida.nombre}
                  </th>
                  <td className="px-3 py-2 text-right tabular-nums">{importe(fila.importe_venta)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{importe(fila.importe_sugerido)}</td>
                  <td className="px-3 py-2 tabular-nums">
                    {fila.importe_tope !== null ? (
                      <div className="flex items-center gap-2">
                        <span>{importe(fila.importe_tope)}</span>
                        {puedeCapturar ? (
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            aria-label={`Recapturar ${fila.tipo_partida.nombre}`}
                            onClick={() => setRecapturando(fila)}
                          >
                            Recapturar
                          </Button>
                        ) : null}
                      </div>
                    ) : puedeCapturar ? (
                      <div className="grid gap-1">
                        <Input
                          inputMode="decimal"
                          aria-label={`Tope de ${fila.tipo_partida.nombre}`}
                          aria-invalid={mensaje !== undefined}
                          aria-describedby={mensaje !== undefined ? idMensaje : undefined}
                          {...register(clave)}
                        />
                        {mensaje !== undefined && (
                          <p id={idMensaje} className="text-sm text-destructive">
                            {mensaje}
                          </p>
                        )}
                      </div>
                    ) : (
                      "sin capturar"
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <CeldaCapturado fila={fila} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>

        <p className="text-sm text-muted-foreground">
          El sugerido resta utilidad e indirectos al precio de venta. Es una referencia: manda el tope capturado, y es
          contra ese contra el que se evalúan las requisiciones (RN-03).
        </p>

        {resumen === null ? null : <Resultado resumen={resumen} />}

        {puedeCapturar && hayPendientes ? (
          <div>
            <Button type="submit" disabled={isSubmitting}>
              Guardar topes
            </Button>
          </div>
        ) : null}
      </form>

      <DialogoRecaptura
        fila={recapturando}
        lineaBaseId={lineaBaseId}
        alCerrar={() => setRecapturando(null)}
        alHecho={(id) => {
          setRecapturando((actual) => (actual?.tipo_partida.id === id ? null : actual));
          void invalidarControl();
        }}
      />

      {enCurso === undefined ? null : (
        <CapturaMotivo
          key={enCurso.fila.tipo_partida.id}
          abierta
          titulo={`Tope mayor que la venta · ${enCurso.fila.tipo_partida.nombre}`}
          descripcion={descripcionTopeSuperior(enCurso)}
          etiquetaConfirmar="Confirmar con motivo"
          etiquetaCancelar="Corregir"
          alConfirmar={(motivo) =>
            capturarTope(api, lineaBaseId, enCurso.fila.tipo_partida.id, {
              importe_tope: enCurso.importe,
              motivo,
              confirmar_superior_a_venta: true,
            })
          }
          alHecho={() => {
            const nombre = enCurso.fila.tipo_partida.nombre;
            sacarDeLaCola(enCurso.fila.tipo_partida.id);
            setResumen((actual) =>
              actual === null
                ? actual
                : {
                    guardadas: [...actual.guardadas, nombre],
                    fallidas: actual.fallidas.filter((candidata) => candidata !== nombre),
                  },
            );
            void invalidarControl();
          }}
          alRechazo={(error) => {
            sacarDeLaCola(enCurso.fila.tipo_partida.id);
            setError(enCurso.fila.tipo_partida.clave, { type: "servidor", message: mensajeDeFila(error) });
          }}
          alCancelar={() => {
            sacarDeLaCola(enCurso.fila.tipo_partida.id);
            setError(enCurso.fila.tipo_partida.clave, { type: "servidor", message: enCurso.error.mensaje });
          }}
        />
      )}
    </div>
  );
}
