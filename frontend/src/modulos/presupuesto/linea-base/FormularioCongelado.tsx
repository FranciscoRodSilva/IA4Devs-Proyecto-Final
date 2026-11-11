import { useQueryClient } from "@tanstack/react-query";
import { useId, useState } from "react";
import { useForm } from "react-hook-form";
import type { Accion, ErrorApi, ErrorBloqueo } from "@/api/errores";
import { useApi } from "@/api/ProveedorApi";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { PantallaBloqueo } from "@/compartido/componentes/bloqueo/PantallaBloqueo";
import { ConflictoEnLinea } from "@/compartido/formularios/ConflictoEnLinea";
import { type EntradaMotivo, resolverMotivo } from "@/compartido/formularios/motivo.formulario";
import { claves } from "@/modulos/presupuesto/obras/obras.consultas";
import { congelarLineaBase } from "./linea-base.consultas";
import { mensajeDeRechazo } from "./presentacion";

/**
 * RN-01 · wireframe 4a. El Director de Proyectos congela la línea base con su motivo.
 * El cliente no evalúa nada: envía y pinta lo que el servidor responde. Ningún rechazo invalida consultas,
 * así que la línea base sigue en `BORRADOR` en pantalla hasta que el servidor la congela.
 */
export function FormularioCongelado({ lineaBaseId }: { lineaBaseId: string }) {
  const api = useApi();
  const queryClient = useQueryClient();
  const idCampo = useId();
  const idError = useId();
  const [bloqueo, setBloqueo] = useState<ErrorBloqueo | null>(null);
  const [alerta, setAlerta] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<EntradaMotivo>({
    resolver: resolverMotivo,
    defaultValues: { motivo: "" },
  });
  const errorMotivo = errors.motivo?.message;

  function limpiar() {
    setBloqueo(null);
    setAlerta(null);
  }

  /** Cada rechazo se distingue por `tipo`, nunca por el texto del mensaje. */
  function rechazar(error: ErrorApi) {
    switch (error.tipo) {
      case "VALIDACION": {
        // El texto del servidor se conserva tal cual; el campo queda marcado y lo escrito no se pierde.
        const deMotivo = error.errores.find((detalle) => detalle.campo === "motivo");
        if (deMotivo !== undefined) {
          setError("motivo", { type: "servidor", message: deMotivo.mensaje }, { shouldFocus: true });
        }
        const otros = error.errores.filter((detalle) => detalle.campo !== "motivo").map((detalle) => detalle.mensaje);
        if (otros.length > 0) setAlerta(otros.join(" "));
        if (deMotivo === undefined && otros.length === 0) setAlerta(error.mensaje);
        return;
      }
      case "REGLA_NEGOCIO":
      case "CONFLICTO":
      case "CONCURRENCIA":
        setBloqueo(error);
        return;
      default:
        setAlerta(mensajeDeRechazo(error));
    }
  }

  async function enviar({ motivo }: EntradaMotivo) {
    limpiar();
    const resultado = await congelarLineaBase(api, lineaBaseId, motivo);
    if (resultado.ok) {
      // Por prefijo: la lista de obras, la obra y sus líneas base se vuelven a pedir.
      await queryClient.invalidateQueries({ queryKey: claves.obras });
      return;
    }
    rechazar(resultado.error);
  }

  // El congelado solo ofrece reintentar, que reenvía el mismo motivo; cualquier otra clave no hace nada.
  function alAccion(accion: Accion) {
    if (accion.clave === "REINTENTAR") void handleSubmit(enviar)();
  }

  return (
    <form noValidate onSubmit={handleSubmit(enviar)} className="grid gap-4 rounded-md border p-4">
      <p className="text-sm text-muted-foreground">
        Al congelar, los conceptos y la explosión por tipo de partida se copian y ya no se pueden modificar. La obra
        pasa a ACTIVA.
      </p>

      <div className="grid gap-2">
        <Label htmlFor={idCampo}>Motivo (obligatorio)</Label>
        <Textarea
          id={idCampo}
          aria-invalid={errorMotivo !== undefined}
          aria-describedby={errorMotivo !== undefined ? idError : undefined}
          {...register("motivo")}
        />
        {errorMotivo !== undefined && (
          <p id={idError} className="text-sm text-destructive">
            {errorMotivo}
          </p>
        )}
      </div>

      {bloqueo === null ? null : bloqueo.tipo === "REGLA_NEGOCIO" ? (
        <PantallaBloqueo error={bloqueo} alCerrar={limpiar} alAccion={limpiar} />
      ) : (
        <ConflictoEnLinea error={bloqueo} alAccion={alAccion} />
      )}

      {alerta !== null && (
        <div role="alert" className="text-sm text-destructive">
          <p>{alerta}</p>
        </div>
      )}

      <div>
        <Button type="submit" disabled={isSubmitting}>
          Congelar línea base
        </Button>
      </div>
    </form>
  );
}
