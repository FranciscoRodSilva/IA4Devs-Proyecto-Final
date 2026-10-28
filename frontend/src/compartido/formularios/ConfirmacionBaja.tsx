import { useState } from "react";
import type { ResultadoApi } from "@/api/cliente";
import type { ErrorApi } from "@/api/errores";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export const ETIQUETA_CONFIRMAR_BAJA = "Confirmar baja";

export interface PropsConfirmacionBaja {
  abierta: boolean;
  /** La pregunta es el título del diálogo: un solo texto, y es el que nombra el diálogo. */
  pregunta: string;
  /** La pantalla envía; la confirmación no decide nada. */
  alConfirmar: () => Promise<ResultadoApi<unknown>>;
  alHecho: () => void;
  alRechazo: (error: ErrorApi) => void;
  alCancelar: () => void;
}

/** Baja sin motivo: una pregunta con dos salidas. Cancelar no envía nada (CA-11 esc. 6). */
export function ConfirmacionBaja({ abierta, pregunta, alConfirmar, alHecho, alRechazo, alCancelar }: PropsConfirmacionBaja) {
  const [enVuelo, setEnVuelo] = useState(false);

  async function confirmar() {
    setEnVuelo(true);
    let resultado: ResultadoApi<unknown>;
    try {
      resultado = await alConfirmar();
    } catch {
      // (asumido) PA-T16: si el envío lanza, se entrega un rechazo genérico en vez de relanzar y dejar el botón bloqueado.
      resultado = { ok: false, error: { tipo: "GENERICO", estado: 0, mensaje: null, correlacion_id: null } };
    } finally {
      setEnVuelo(false);
    }
    // Fuera del `try`: para que un fallo de la pantalla al procesar la baja no se disfrace de baja rechazada.
    if (resultado.ok) alHecho();
    else alRechazo(resultado.error);
  }

  return (
    <Dialog
      open={abierta}
      onOpenChange={(abriendo) => {
        if (!abriendo) alCancelar();
      }}
    >
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{pregunta}</DialogTitle>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="outline" onClick={alCancelar}>
            Cancelar
          </Button>
          <Button type="button" disabled={enVuelo} onClick={confirmar}>
            {ETIQUETA_CONFIRMAR_BAJA}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
