import { type RefObject, useId, useRef, useState } from "react";
import { type UseFormRegister, useForm } from "react-hook-form";
import type { z } from "zod";
import type { ResultadoApi } from "@/api/cliente";
import { type Accion, type ErrorApi, type ErrorBloqueo, type ErrorConcurrencia, type ErrorReglaNegocio, esObjeto } from "@/api/errores";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CapturaMotivo } from "@/compartido/formularios/CapturaMotivo";
import { ConfirmacionBaja, ETIQUETA_CONFIRMAR_BAJA } from "@/compartido/formularios/ConfirmacionBaja";
import { ConflictoEnLinea } from "@/compartido/formularios/ConflictoEnLinea";
import { resolverCatalogo, rutaDeCampo, valoresDeFormulario } from "@/compartido/formularios/catalogo.formulario";

export interface CampoCatalogo<N extends string> {
  nombre: N;
  etiqueta: string;
  tipo?: "text" | "email" | "date";          // "text" por omisión; los importes son texto
}

export interface BajaCatalogo {
  etiqueta: string;                          // p. ej. «Dar de baja»
  pregunta: string;                          // texto de la confirmación
  exigeMotivo: boolean;                      // PA-T12
  alConfirmar: (motivo: string | null) => Promise<ResultadoApi<unknown>>;
  alHecha: () => void;
}

export interface PropsFormularioCatalogo<E extends z.ZodObject, R> {
  abierto: boolean;
  titulo: string;
  esquema: E;
  campos: ReadonlyArray<CampoCatalogo<keyof z.input<E> & string>>;
  valoresIniciales: z.input<E>;
  etiquetaGuardar?: string;                  // «Guardar» por omisión
  alGuardar: (valores: z.output<E>) => Promise<ResultadoApi<R>>;
  alGuardado: (respuesta: R) => void;
  alBloqueo: (error: ErrorReglaNegocio | ErrorConcurrencia) => void;
  alAccion: (accion: Accion) => void;
  alCerrar: () => void;
  baja?: BajaCatalogo;
}

type Nombre<E extends z.ZodObject> = keyof z.input<E> & string;

/** Lo que la pantalla muestra tras una operación fallida: un bloqueo en línea o avisos de la cabecera. */
type Rechazo = { vista: "conflicto"; error: ErrorBloqueo } | { vista: "aviso"; textos: readonly string[]; referencia: string | null };

function esNombreDeCampo<E extends z.ZodObject>(nombre: string, campos: ReadonlyArray<CampoCatalogo<Nombre<E>>>): nombre is Nombre<E> {
  return campos.some((campo) => campo.nombre === nombre);
}

function esBloqueo(error: ErrorApi): error is ErrorBloqueo {
  return error.tipo === "REGLA_NEGOCIO" || error.tipo === "CONFLICTO" || error.tipo === "CONCURRENCIA";
}

/** El mensaje de error de un campo de React Hook Form, si lo tiene. */
function mensajeDeError(error: unknown): string | undefined {
  return esObjeto(error) && typeof error.message === "string" ? error.message : undefined;
}

/** El mensaje del servidor, o el genérico de la operación; la referencia solo si el servidor la trae. */
function avisoDe(error: ErrorApi, textoPorOmision: string): Extract<Rechazo, { vista: "aviso" }> {
  if (error.tipo === "RED") return { vista: "aviso", textos: [textoPorOmision], referencia: null };
  return { vista: "aviso", textos: [error.mensaje ?? textoPorOmision], referencia: error.correlacion_id };
}

interface PropsCampoTexto<E extends z.ZodObject> {
  campo: CampoCatalogo<Nombre<E>>;
  registrar: UseFormRegister<z.input<E>>;
  error: string | undefined;
  /** Solo el primer campo: el diálogo le da el foco al abrir (CA-11 esc. 1). */
  campoRef?: RefObject<HTMLInputElement | null>;
}

function CampoTexto<E extends z.ZodObject>({ campo, registrar, error, campoRef }: PropsCampoTexto<E>) {
  const idCampo = useId();
  const idError = useId();
  const { ref: registrarCampo, ...registro } = registrar(rutaDeCampo<E>(campo.nombre));
  return (
    <div className="grid gap-2">
      <Label htmlFor={idCampo}>{campo.etiqueta}</Label>
      <Input
        id={idCampo}
        type={campo.tipo ?? "text"}
        aria-invalid={error !== undefined}
        aria-describedby={error !== undefined ? idError : undefined}
        {...registro}
        ref={(elemento) => {
          registrarCampo(elemento);
          if (campoRef !== undefined) campoRef.current = elemento;
        }}
      />
      {error !== undefined && (
        <p id={idError} className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}

interface PropsContenidoFormulario<E extends z.ZodObject, R> extends Omit<PropsFormularioCatalogo<E, R>, "abierto" | "titulo"> {
  campoRef: RefObject<HTMLInputElement | null>;
}

/** Vive dentro del diálogo: al cerrarse se desmonta, así que cada apertura empieza con los valores iniciales. */
function ContenidoFormulario<E extends z.ZodObject, R>({
  esquema,
  campos,
  valoresIniciales,
  etiquetaGuardar = "Guardar",
  alGuardar,
  alGuardado,
  alBloqueo,
  alAccion,
  alCerrar,
  baja,
  campoRef,
}: PropsContenidoFormulario<E, R>) {
  const [rechazo, setRechazo] = useState<Rechazo | null>(null);
  const [motivoAbierto, setMotivoAbierto] = useState(false);
  const [confirmacionAbierta, setConfirmacionAbierta] = useState(false);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<z.input<E>, unknown, z.output<E>>({
    resolver: resolverCatalogo(esquema),
    defaultValues: valoresDeFormulario<E>(valoresIniciales),
    shouldFocusError: true,
  });

  async function enviar(valores: z.output<E>) {
    setRechazo(null);
    const resultado = await alGuardar(valores);
    if (resultado.ok) {
      alGuardado(resultado.datos);
      alCerrar();
      return;
    }
    rechazarGuardado(resultado.error);
  }

  function rechazarGuardado(error: ErrorApi) {
    switch (error.tipo) {
      case "VALIDACION": {
        // Cada mensaje junto a su campo; lo que no es de ningún campo, a la cabecera. Lo escrito se conserva.
        // El foco va solo al primer campo mapeado: con `shouldFocus` en todos, el último se lo queda.
        const restantes: string[] = [];
        let primero = true;
        for (const detalle of error.errores) {
          const nombre = detalle.campo;
          if (esNombreDeCampo<E>(nombre, campos)) {
            setError(rutaDeCampo<E>(nombre), { type: "servidor", message: detalle.mensaje }, { shouldFocus: primero });
            primero = false;
          } else restantes.push(detalle.mensaje);
        }
        if (restantes.length > 0) setRechazo({ vista: "aviso", textos: restantes, referencia: null });
        // (asumido) PA-T13: un 422 sin entradas no tiene campo al que apuntar; se pinta en la cabecera.
        else if (error.errores.length === 0) setRechazo(avisoDe(error, "No se pudo guardar."));
        return;
      }
      case "CONFLICTO":
        setRechazo({ vista: "conflicto", error });
        return;
      case "REGLA_NEGOCIO":
      case "CONCURRENCIA":
        alBloqueo(error);
        return;
      default:
        setRechazo(avisoDe(error, "No se pudo guardar."));
        return;
    }
  }

  function rechazarBaja(error: ErrorApi) {
    if (esBloqueo(error)) setRechazo({ vista: "conflicto", error });
    else setRechazo(avisoDe(error, "No se pudo dar de baja."));
  }

  return (
    <>
      {rechazo?.vista === "aviso" && (
        <div role="alert" className="grid gap-1 text-sm text-destructive">
          {rechazo.textos.map((texto, indice) => (
            <p key={indice}>{texto}</p>
          ))}
          {rechazo.referencia === null ? null : <p>Referencia: {rechazo.referencia}</p>}
        </div>
      )}

      <form noValidate onSubmit={handleSubmit(enviar)} className="grid gap-4">
        {campos.map((campo, indice) => (
          <CampoTexto<E>
            key={campo.nombre}
            campo={campo}
            registrar={register}
            error={mensajeDeError(errors[rutaDeCampo<E>(campo.nombre)])}
            campoRef={indice === 0 ? campoRef : undefined}
          />
        ))}

        <div aria-live="polite">
          {rechazo?.vista === "conflicto" && <ConflictoEnLinea error={rechazo.error} alAccion={alAccion} regionViva={false} />}
        </div>

        <DialogFooter>
          {baja === undefined ? null : (
            <Button
              type="button"
              variant="outline"
              className="sm:mr-auto"
              onClick={() => {
                if (baja.exigeMotivo) setMotivoAbierto(true);
                else setConfirmacionAbierta(true);
              }}
            >
              {baja.etiqueta}
            </Button>
          )}
          <Button type="submit" disabled={isSubmitting}>
            {etiquetaGuardar}
          </Button>
        </DialogFooter>
      </form>

      {baja === undefined ? null : (
        <>
          <ConfirmacionBaja
            abierta={confirmacionAbierta}
            pregunta={baja.pregunta}
            alConfirmar={() => {
              setRechazo(null);
              return baja.alConfirmar(null);
            }}
            alHecho={() => {
              setConfirmacionAbierta(false);
              baja.alHecha();
            }}
            alRechazo={(error) => {
              setConfirmacionAbierta(false);
              rechazarBaja(error);
            }}
            alCancelar={() => setConfirmacionAbierta(false)}
          />
          <CapturaMotivo
            abierta={motivoAbierto}
            titulo={baja.etiqueta}
            descripcion={baja.pregunta}
            etiquetaConfirmar={ETIQUETA_CONFIRMAR_BAJA}
            alConfirmar={(motivo) => {
              setRechazo(null);
              return baja.alConfirmar(motivo);
            }}
            alHecho={() => {
              setMotivoAbierto(false);
              baja.alHecha();
            }}
            alRechazo={(error) => {
              setMotivoAbierto(false);
              rechazarBaja(error);
            }}
            alCancelar={() => setMotivoAbierto(false)}
          />
        </>
      )}
    </>
  );
}

/** Diálogo de alta o edición de un catálogo (TKT-008 · CA-11). Muestra el bloqueo, no lo decide. */
export function FormularioCatalogo<E extends z.ZodObject, R>({ abierto, titulo, ...resto }: PropsFormularioCatalogo<E, R>) {
  const campoRef = useRef<HTMLInputElement>(null);

  return (
    <Dialog
      open={abierto}
      onOpenChange={(abriendo) => {
        if (!abriendo) resto.alCerrar();
      }}
    >
      <DialogContent initialFocus={campoRef}>
        <DialogHeader>
          <DialogTitle>{titulo}</DialogTitle>
        </DialogHeader>
        <ContenidoFormulario<E, R> {...resto} campoRef={campoRef} />
      </DialogContent>
    </Dialog>
  );
}
