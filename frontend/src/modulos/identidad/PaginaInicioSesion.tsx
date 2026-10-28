import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState, useId } from "react";
import { useForm } from "react-hook-form";
import { useLocation, useNavigate } from "react-router";
import { FalloApi, pedir } from "@/api/cliente";
import { type ErrorApi, esObjeto } from "@/api/errores";
import { useApi } from "@/api/ProveedorApi";
import { sesionOptions } from "@/api/sesion";
import { AVISO_SESION_TERMINADA } from "@/app/navegacion/ruta-inicio-sesion";
import { primeraSeccion } from "@/app/navegacion/secciones";
import logo from "@/assets/ap-logo.jpeg";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useEnLinea } from "@/compartido/red/useEnLinea";
import { formatearCuentaAtras, useCuentaAtras } from "@/compartido/tiempo/useCuentaAtras";
import {
  type EntradaInicioSesion,
  resolverInicioSesion,
} from "@/modulos/identidad/inicio-sesion.formulario";

const SIN_CONEXION = "Sin conexión. Para iniciar sesión hace falta conexión con el servidor.";
const ERROR_DESCONOCIDO: ErrorApi = { tipo: "GENERICO", estado: 0, mensaje: null, correlacion_id: null };

interface MensajeGeneral {
  texto: string;
  /** El origen no verificado se resuelve recargando la página, no reintentando (CA-6 esc. 7). */
  recargar: boolean;
}

interface Espera {
  /** Cambia con cada bloqueo nuevo: es la `key` del botón, y así una espera igual a la anterior también cuenta. */
  id: number;
  segundos: number;
}

/** Redacción de la espera (wireframe §1): minutos desde 60 s, redondeados hacia arriba. */
function describirEspera(segundos: number): string {
  if (segundos >= 60) {
    const minutos = Math.ceil(segundos / 60);
    return `${minutos} ${minutos === 1 ? "minuto" : "minutos"}`;
  }
  return `${segundos} ${segundos === 1 ? "segundo" : "segundos"}`;
}

interface PropsBotonIniciar {
  espera: number | null;
  deshabilitado: boolean;
  /** Se llama una vez, al llegar la cuenta atrás a cero (CA-6 esc. 5). Debe ser estable entre renderizados. */
  alVencer: () => void;
}

/** Botón con la cuenta atrás del bloqueo por intentos (CA-6 esc. 5). Se rehabilita en cero. */
function BotonIniciar({ espera, deshabilitado, alVencer }: PropsBotonIniciar) {
  const restantes = useCuentaAtras(espera);
  const bloqueado = restantes > 0;
  useEffect(() => {
    if (espera !== null && espera > 0 && restantes === 0) alVencer();
  }, [espera, restantes, alVencer]);
  return (
    <Button type="submit" className="w-full" disabled={deshabilitado || bloqueado}>
      {bloqueado ? `Iniciar sesión (${formatearCuentaAtras(restantes)})` : "Iniciar sesión"}
    </Button>
  );
}

/** M10 · CA-6 · inicio de sesión. Los rechazos se distinguen por `tipo` y `motivo`, nunca por el texto. */
export function PaginaInicioSesion() {
  const api = useApi();
  const queryClient = useQueryClient();
  const navegar = useNavigate();
  const estadoRuta: unknown = useLocation().state;
  const aviso = esObjeto(estadoRuta) && estadoRuta.aviso === AVISO_SESION_TERMINADA;
  const enLinea = useEnLinea();

  const idTitulo = useId();
  const idCorreo = useId();
  const idErrorCorreo = useId();
  const idContrasena = useId();
  const idErrorContrasena = useId();

  const [mensajeGeneral, setMensajeGeneral] = useState<MensajeGeneral | null>(null);
  const [espera, setEspera] = useState<Espera | null>(null);
  // Mientras dura la espera el botón está deshabilitado, así que el único mensaje posible es el del bloqueo.
  const alVencerEspera = useCallback(() => setMensajeGeneral(null), []);

  const {
    register,
    handleSubmit,
    setError,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm<EntradaInicioSesion>({
    resolver: resolverInicioSesion,
    defaultValues: { email: "", contrasena: "" },
  });

  function mostrar(texto: string, recargar = false) {
    setMensajeGeneral({ texto, recargar });
  }

  function rechazar(error: ErrorApi) {
    switch (error.tipo) {
      case "VALIDACION": {
        const generales: string[] = [];
        for (const detalle of error.errores) {
          if (detalle.campo === "email" || detalle.campo === "contrasena") {
            setError(detalle.campo, { type: "servidor", message: detalle.mensaje }, { shouldFocus: true });
          } else {
            generales.push(detalle.mensaje);
          }
        }
        if (generales.length > 0) mostrar(generales.join(" "));
        return;
      }
      case "SESION":
        if (error.motivo === "CREDENCIALES_INVALIDAS") {
          // Un único mensaje para correo y contraseña incorrectos: no revela qué cuentas existen (CA-6 esc. 3).
          setValue("contrasena", "");
          mostrar("Correo o contraseña incorrectos.");
          return;
        }
        break;
      case "LIMITE_INTENTOS":
        setEspera((anterior) => ({ id: (anterior?.id ?? 0) + 1, segundos: error.reintentar_en_s }));
        // C104: con 0 no hay espera que contar; el contrato lo permite (`minimum: 0`).
        mostrar(
          error.reintentar_en_s === 0
            ? "Demasiados intentos fallidos. Vuelve a intentarlo."
            : `Demasiados intentos fallidos. Vuelve a intentarlo en ${describirEspera(error.reintentar_en_s)}.`,
        );
        return;
      case "PERMISO":
        if (error.motivo === "ORIGEN_NO_VERIFICADO") {
          mostrar("No se pudo verificar el origen de la petición. Recarga la página para continuar.", true);
          return;
        }
        break;
      case "RED":
        mostrar("No se pudo conectar con el servidor. Inténtalo de nuevo.");
        return;
      default:
        break;
    }
    // Cualquier otro: sin el mensaje ni el código del servidor; la referencia solo si la trae (CA-4).
    // Tras el switch, RED ya está descartado por su `return`: todo lo que queda trae correlacion_id.
    const referencia = error.correlacion_id;
    mostrar(referencia === null ? "No se pudo iniciar sesión." : `No se pudo iniciar sesión. Referencia: ${referencia}`);
  }

  async function enviar(valores: EntradaInicioSesion) {
    setMensajeGeneral(null);
    const resultado = await pedir(() => api.POST("/api/v1/sesion", { body: valores }));
    if (!resultado.ok) {
      rechazar(resultado.error);
      return;
    }
    // S102: nada de la persona anterior sobrevive en la caché al iniciar sesión.
    queryClient.clear();
    try {
      // La sesión se vuelve a leer del servidor: los roles que mandan la primera sección son los de GET /sesion.
      const sesion = await queryClient.fetchQuery({ ...sesionOptions(api), staleTime: 0 });
      void navegar(primeraSeccion(sesion.roles)?.ruta ?? "/", { replace: true });
    } catch (fallo: unknown) {
      rechazar(fallo instanceof FalloApi ? fallo.error : ERROR_DESCONOCIDO);
    }
  }

  const errorCorreo = errors.email?.message;
  const errorContrasena = errors.contrasena?.message;

  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <section aria-labelledby={idTitulo} className="w-full max-w-sm space-y-6 rounded-xl border bg-card p-6 shadow-sm">
        <header className="space-y-1 text-center">
          <img src={logo} alt="AP Buildings" className="mx-auto h-24 w-auto" />
          <h1 id={idTitulo} className="text-2xl font-semibold">
            CIMENTA
          </h1>
          <p className="text-sm text-muted-foreground">Control de costos de obra</p>
        </header>

        {aviso && <p role="status" className="rounded-lg border p-3 text-sm">Tu sesión terminó. Vuelve a iniciarla.</p>}

        <form noValidate onSubmit={handleSubmit(enviar)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor={idCorreo}>Correo</Label>
            <Input
              id={idCorreo}
              type="email"
              autoComplete="username"
              aria-invalid={errorCorreo !== undefined}
              aria-describedby={errorCorreo !== undefined ? idErrorCorreo : undefined}
              {...register("email")}
            />
            {errorCorreo !== undefined && (
              <p id={idErrorCorreo} className="text-sm text-destructive">
                {errorCorreo}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor={idContrasena}>Contraseña</Label>
            <Input
              id={idContrasena}
              type="password"
              autoComplete="current-password"
              aria-invalid={errorContrasena !== undefined}
              aria-describedby={errorContrasena !== undefined ? idErrorContrasena : undefined}
              {...register("contrasena")}
            />
            {errorContrasena !== undefined && (
              <p id={idErrorContrasena} className="text-sm text-destructive">
                {errorContrasena}
              </p>
            )}
          </div>

          {mensajeGeneral !== null && (
            <div role="alert" className="space-y-2 rounded-lg border border-destructive/40 p-3 text-sm text-destructive">
              <p>{mensajeGeneral.texto}</p>
              {mensajeGeneral.recargar && (
                <Button type="button" variant="outline" onClick={() => globalThis.location.reload()}>
                  Recargar
                </Button>
              )}
            </div>
          )}

          <BotonIniciar
            key={espera?.id ?? 0}
            espera={espera?.segundos ?? null}
            deshabilitado={isSubmitting || !enLinea}
            alVencer={alVencerEspera}
          />

          {!enLinea && <p className="text-sm text-muted-foreground">{SIN_CONEXION}</p>}
        </form>
      </section>
    </main>
  );
}
