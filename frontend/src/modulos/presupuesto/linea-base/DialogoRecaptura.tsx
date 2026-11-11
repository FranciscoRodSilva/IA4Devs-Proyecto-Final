import { useId, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import type { Accion, ErrorApi, ErrorBloqueo } from "@/api/errores";
import type { components } from "@/api/generado/servidor";
import { useApi } from "@/api/ProveedorApi";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ConflictoEnLinea } from "@/compartido/formularios/ConflictoEnLinea";
import { capturarTope } from "./linea-base.consultas";
import { autorYFecha, importe, mensajeDeFila } from "./presentacion";
import { type EntradaRecaptura, resolverRecaptura } from "./tope.formulario";

type PresupuestoControl = components["schemas"]["PresupuestoControl"];

interface PropsDialogoRecaptura {
  /** La fila cuyo tope se recaptura; `null` mantiene el diálogo cerrado. */
  fila: PresupuestoControl | null;
  lineaBaseId: string;
  alCerrar: () => void;
  alHecho: (id: string) => void;
}

function Vigente({ fila }: { fila: PresupuestoControl }) {
  const captura = autorYFecha(fila);
  const tope = fila.importe_tope === null ? "No disponible" : importe(fila.importe_tope);
  return (
    <>
      {`Tope vigente ${tope}`}
      {captura === null ? null : (
        <>
          {` (${captura.nombre}`}
          {captura.fecha === null ? null : (
            <>
              {" · "}
              <time dateTime={captura.instante}>{captura.fecha}</time>
            </>
          )}
          {")"}
        </>
      )}
    </>
  );
}

/**
 * RN-03 · RN-04 · wireframe 4b. La recaptura de un tope ya capturado: tope nuevo y motivo. El cliente no evalúa
 * nada: envía y pinta lo que el servidor responde, incluida la confirmación de un tope mayor que la venta.
 */
function FormularioRecaptura({
  fila,
  lineaBaseId,
  alCerrar,
  alHecho,
}: Omit<PropsDialogoRecaptura, "fila"> & { fila: PresupuestoControl }) {
  const api = useApi();
  const idTope = useId();
  const idErrorTope = useId();
  const idMotivo = useId();
  const idErrorMotivo = useId();
  const [bloqueo, setBloqueo] = useState<ErrorBloqueo | null>(null);
  const [alerta, setAlerta] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);
  const enCurso = useRef(false);
  const ultimoEnvio = useRef<{ tope: string; motivo: string; confirmar: boolean } | null>(null);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<EntradaRecaptura>({ resolver: resolverRecaptura, defaultValues: { tope: "", motivo: "" } });
  const errorTope = errors.tope?.message;
  const errorMotivo = errors.motivo?.message;

  /** Cada rechazo se distingue por `tipo`, nunca por el texto del mensaje. */
  function rechazar(error: ErrorApi) {
    switch (error.tipo) {
      case "VALIDACION": {
        const deTope = error.errores.find((detalle) => detalle.campo === "importe_tope");
        const deMotivo = error.errores.find((detalle) => detalle.campo === "motivo");
        if (deTope !== undefined) setError("tope", { type: "servidor", message: deTope.mensaje });
        if (deMotivo !== undefined) setError("motivo", { type: "servidor", message: deMotivo.mensaje });
        const otros = error.errores
          .filter((detalle) => detalle.campo !== "importe_tope" && detalle.campo !== "motivo")
          .map((detalle) => detalle.mensaje);
        if (otros.length > 0) setAlerta(otros.join(" "));
        else if (deTope === undefined && deMotivo === undefined) setAlerta(error.mensaje);
        return;
      }
      case "REGLA_NEGOCIO":
      case "CONFLICTO":
      case "CONCURRENCIA":
        setBloqueo(error);
        return;
      default:
        setAlerta(mensajeDeFila(error));
    }
  }

  async function enviar({ tope, motivo }: EntradaRecaptura, confirmar: boolean) {
    // El ref cubre la ventana entre dos llamadas del mismo render, en que el estado aún no se ha repintado.
    if (enCurso.current) return;
    enCurso.current = true;
    setEnviando(true);
    try {
      setBloqueo(null);
      setAlerta(null);
      ultimoEnvio.current = { tope, motivo, confirmar };
      const resultado = await capturarTope(api, lineaBaseId, fila.tipo_partida.id, {
        importe_tope: tope,
        motivo,
        confirmar_superior_a_venta: confirmar,
      });
      if (resultado.ok) {
        alHecho(fila.tipo_partida.id);
        return;
      }
      rechazar(resultado.error);
    } finally {
      enCurso.current = false;
      setEnviando(false);
    }
  }

  function alAccion(accion: Accion) {
    const previo = ultimoEnvio.current;
    if (previo === null) return;
    if (accion.clave === "CONFIRMAR_TOPE_SUPERIOR") void enviar(previo, true);
    else if (accion.clave === "REINTENTAR") void enviar(previo, previo.confirmar);
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>{`Recapturar tope · ${fila.tipo_partida.nombre}`}</DialogTitle>
        <DialogDescription>
          <Vigente fila={fila} />
        </DialogDescription>
      </DialogHeader>
      <form noValidate onSubmit={handleSubmit((valores) => enviar(valores, false))} className="grid gap-4">
        <div className="grid gap-2">
          <Label htmlFor={idTope}>Tope nuevo</Label>
          <Input
            id={idTope}
            inputMode="decimal"
            aria-invalid={errorTope !== undefined}
            aria-describedby={errorTope !== undefined ? idErrorTope : undefined}
            {...register("tope")}
          />
          {errorTope !== undefined && (
            <p id={idErrorTope} className="text-sm text-destructive">
              {errorTope}
            </p>
          )}
        </div>

        <div className="grid gap-2">
          <Label htmlFor={idMotivo}>Motivo (obligatorio)</Label>
          <Textarea
            id={idMotivo}
            aria-invalid={errorMotivo !== undefined}
            aria-describedby={errorMotivo !== undefined ? idErrorMotivo : undefined}
            {...register("motivo")}
          />
          {errorMotivo !== undefined && (
            <p id={idErrorMotivo} className="text-sm text-destructive">
              {errorMotivo}
            </p>
          )}
        </div>

        <p className="text-sm text-muted-foreground">
          Se registra en la bitácora con RN-03 y aparece en la bitácora de excepciones junto a las autorizaciones.
        </p>

        {bloqueo === null ? null : <ConflictoEnLinea error={bloqueo} alAccion={alAccion} />}

        {alerta !== null && (
          <div role="alert" className="text-sm text-destructive">
            <p>{alerta}</p>
          </div>
        )}

        <DialogFooter>
          <Button type="button" variant="outline" onClick={alCerrar}>
            Cancelar
          </Button>
          <Button type="submit" disabled={isSubmitting || enviando}>
            Recapturar
          </Button>
        </DialogFooter>
      </form>
    </>
  );
}

export function DialogoRecaptura({ fila, lineaBaseId, alCerrar, alHecho }: PropsDialogoRecaptura) {
  return (
    <Dialog
      open={fila !== null}
      onOpenChange={(abriendo) => {
        if (!abriendo) alCerrar();
      }}
    >
      <DialogContent showCloseButton={false}>
        {fila === null ? null : (
          <FormularioRecaptura
            key={fila.tipo_partida.id}
            fila={fila}
            lineaBaseId={lineaBaseId}
            alCerrar={alCerrar}
            alHecho={alHecho}
          />
        )}
      </DialogContent>
    </Dialog>
  );
}
