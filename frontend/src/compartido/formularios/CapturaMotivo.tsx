import { type RefObject, useId, useRef, useState } from "react";
import { useForm } from "react-hook-form";
import type { ResultadoApi } from "@/api/cliente";
import type { ErrorApi } from "@/api/errores";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { type EntradaMotivo, resolverMotivo } from "@/compartido/formularios/motivo.formulario";

export interface PropsCapturaMotivo {
  abierta: boolean;
  titulo: string;
  descripcion?: string;
  etiquetaConfirmar: string;
  alConfirmar: (motivo: string) => Promise<ResultadoApi<unknown>>;   // la pantalla envía; RN-04
  alHecho: () => void;
  alRechazo: (error: ErrorApi) => void;                               // 409 y demás: los pinta la pantalla
  alCancelar: () => void;
}

type PropsFormularioMotivo = Pick<
  PropsCapturaMotivo,
  "etiquetaConfirmar" | "alConfirmar" | "alHecho" | "alRechazo" | "alCancelar"
> & {
  campoRef: RefObject<HTMLTextAreaElement | null>;
};

/**
 * Formulario del motivo. Vive dentro del diálogo: al cerrarse se desmonta y cada apertura empieza vacía.
 * Implementa CA-12 (esc. 1 a 4) y el cierre por cancelar.
 */
function FormularioMotivo({
  campoRef,
  etiquetaConfirmar,
  alConfirmar,
  alHecho,
  alRechazo,
  alCancelar,
}: PropsFormularioMotivo) {
  const idCampo = useId();
  const idError = useId();
  const [alertaGeneral, setAlertaGeneral] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<EntradaMotivo>({
    resolver: resolverMotivo,
    defaultValues: { motivo: "" },
  });

  const { ref: registrarCampo, ...campoMotivo } = register("motivo");
  const errorMotivo = errors.motivo?.message;

  function rechazar(error: ErrorApi) {
    if (error.tipo !== "VALIDACION" || error.errores.length === 0) {
      alRechazo(error);
      return;
    }
    // El texto del servidor se conserva tal cual; el campo queda marcado y lo escrito no se pierde.
    const deMotivo = error.errores.find((detalle) => detalle.campo === "motivo");
    if (deMotivo !== undefined) setError("motivo", { type: "servidor", message: deMotivo.mensaje }, { shouldFocus: true });
    const otros = error.errores.filter((detalle) => detalle.campo !== "motivo").map((detalle) => detalle.mensaje);
    if (otros.length > 0) setAlertaGeneral(otros.join(" "));
  }

  async function enviar({ motivo }: EntradaMotivo) {
    setAlertaGeneral(null);
    const resultado = await alConfirmar(motivo);
    if (resultado.ok) {
      alHecho();
      return;
    }
    rechazar(resultado.error);
  }

  return (
    <form noValidate onSubmit={handleSubmit(enviar)} className="grid gap-4">
      <div className="grid gap-2">
        <Label htmlFor={idCampo}>Motivo</Label>
        <Textarea
          id={idCampo}
          aria-invalid={errorMotivo !== undefined}
          aria-describedby={errorMotivo !== undefined ? idError : undefined}
          {...campoMotivo}
          ref={(elemento) => {
            registrarCampo(elemento);
            campoRef.current = elemento;
          }}
        />
        {errorMotivo !== undefined && (
          <p id={idError} className="text-sm text-destructive">
            {errorMotivo}
          </p>
        )}
      </div>

      {alertaGeneral !== null && (
        <div role="alert" className="text-sm text-destructive">
          <p>{alertaGeneral}</p>
        </div>
      )}

      <DialogFooter>
        <Button type="button" variant="outline" onClick={alCancelar}>
          Cancelar
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {etiquetaConfirmar}
        </Button>
      </DialogFooter>
    </form>
  );
}

/** TKT-008 · CA-12. Captura el motivo antes de una operación; la pantalla envía y pinta los rechazos. */
export function CapturaMotivo({
  abierta,
  titulo,
  descripcion,
  etiquetaConfirmar,
  alConfirmar,
  alHecho,
  alRechazo,
  alCancelar,
}: PropsCapturaMotivo) {
  const campoRef = useRef<HTMLTextAreaElement>(null);

  return (
    <Dialog
      open={abierta}
      onOpenChange={(abriendo) => {
        if (!abriendo) alCancelar();
      }}
    >
      <DialogContent showCloseButton={false} initialFocus={campoRef}>
        <DialogHeader>
          <DialogTitle>{titulo}</DialogTitle>
          {descripcion !== undefined && <DialogDescription>{descripcion}</DialogDescription>}
        </DialogHeader>
        <FormularioMotivo
          campoRef={campoRef}
          etiquetaConfirmar={etiquetaConfirmar}
          alConfirmar={alConfirmar}
          alHecho={alHecho}
          alRechazo={alRechazo}
          alCancelar={alCancelar}
        />
      </DialogContent>
    </Dialog>
  );
}
