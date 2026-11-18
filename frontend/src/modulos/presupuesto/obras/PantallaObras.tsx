import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { type Accion, type ErrorApi, type ErrorBloqueo, type ErrorConcurrencia, type ErrorConflictoEstado, type ErrorReglaNegocio } from "@/api/errores";
import { type ClienteApi, FalloApi, type ResultadoApi } from "@/api/cliente";
import type { components } from "@/api/generado/servidor";
import { useApi } from "@/api/ProveedorApi";
import { type Rol, useSesion } from "@/api/sesion";
import { seccionPermitida } from "@/app/navegacion/secciones";
import { Button } from "@/components/ui/button";
import { CapturaMotivo } from "@/compartido/formularios/CapturaMotivo";
import { ConfirmacionBaja } from "@/compartido/formularios/ConfirmacionBaja";
import { ConflictoEnLinea } from "@/compartido/formularios/ConflictoEnLinea";
import { FormularioCatalogo } from "@/compartido/formularios/FormularioCatalogo";
import { type AccionDeFila, accionesDeFila, accionesEjecutablesEnBaja, ROLES_QUE_OPERAN } from "./obras.acciones";
import {
  CAMPOS_OBRA,
  CAMPOS_VISTA_EDICION_OBRA,
  cambiosDeEdicion,
  esquemaObra,
  esquemaVistaEdicionObra,
  valoresDeVistaEdicion,
  VALORES_INICIALES_OBRA,
} from "./obras.formulario";
import {
  cerrarObra,
  claves,
  crearObra,
  editarObra,
  eliminarObra,
  obrasOptions,
  reactivarObra,
  suspenderObra,
} from "./obras.consultas";

type Esquemas = components["schemas"];
type Obra = Esquemas["Obra"];

/** M5 · wireframe «Obras». Cortesía de navegación (PA-T8): el control real es el 403 del servidor. */
const ETIQUETA_ALTA = "Dar de alta una obra";
const TITULO_FORMULARIO = "Alta de obra";
const TITULO_EDICION = "Editar obra";
const ETIQUETA_LINEA_BASE = "Línea base";
const ETIQUETA_ACCION: Readonly<Record<AccionDeFila, string>> = {
  EDITAR: "Editar",
  ELIMINAR: "Eliminar",
  SUSPENDER: "Suspender",
  REACTIVAR: "Reactivar",
  CERRAR: "Cerrar",
};
const ETIQUETA_ESTADO: Readonly<Record<Esquemas["EstadoObra"], string>> = {
  PLANEACION: "Planeación",
  ACTIVA: "Activa",
  SUSPENDIDA: "Suspendida",
  CERRADA: "Cerrada",
};

/** Las transiciones que piden motivo (CA-17). Cada una tiene su título, su confirmación y su función tipada. */
type VerboMotivo = "SUSPENDER" | "REACTIVAR" | "CERRAR";
const TITULO_MOTIVO: Readonly<Record<VerboMotivo, string>> = {
  SUSPENDER: "Suspender la obra",
  REACTIVAR: "Reactivar la obra",
  CERRAR: "Cerrar la obra",
};
const ETIQUETA_CONFIRMAR_MOTIVO: Readonly<Record<VerboMotivo, string>> = {
  SUSPENDER: "Suspender obra",
  REACTIVAR: "Reactivar obra",
  CERRAR: "Cerrar obra",
};
const OPERACION_DE_MOTIVO: Readonly<
  Record<VerboMotivo, (api: ClienteApi, obraId: string, motivo: string) => Promise<ResultadoApi<Obra>>>
> = {
  SUSPENDER: suspenderObra,
  REACTIVAR: reactivarObra,
  CERRAR: cerrarObra,
};

/** Una transición en curso: la obra de la fila o la del bloqueo, y el verbo. */
interface MotivoEnCurso {
  verbo: VerboMotivo;
  obra: Obra;
}

/** Un 409 `OBRA_CON_HISTORIAL` con la obra que se intentó eliminar: sus acciones operan sobre ella (CA-16). */
interface BloqueoBaja {
  error: ErrorConflictoEstado;
  obra: Obra;
}

/** Un rechazo que no es de negocio ni de estado: se avisa en la cabecera, con su referencia si el servidor la trae. */
interface Aviso {
  texto: string;
  referencia: string | null;
}

/** El error de la consulta, si es el de la capa de API. Cualquier otra cosa no tiene detalle que pintar. */
function errorDe(fallo: unknown): ErrorApi | null {
  return fallo instanceof FalloApi ? fallo.error : null;
}

/** El mensaje del servidor, o el genérico de la operación; la referencia solo si el servidor la trae. */
function avisoDe(error: ErrorApi, textoPorOmision: string): Aviso {
  if (error.tipo === "RED") return { texto: textoPorOmision, referencia: null };
  return { texto: error.mensaje ?? textoPorOmision, referencia: error.correlacion_id };
}

function EsqueletoLista() {
  return (
    <div role="status" aria-busy="true" aria-label="Cargando las obras" className="space-y-2">
      {[0, 1, 2].map((indice) => (
        <div key={indice} className="h-8 animate-pulse rounded bg-muted" />
      ))}
    </div>
  );
}

function AvisoErrorLista({ error, alReintentar }: { error: unknown; alReintentar: () => void }) {
  const detalle = errorDe(error);
  const mensaje = detalle !== null && "mensaje" in detalle ? detalle.mensaje : null;
  const referencia = detalle !== null && "correlacion_id" in detalle ? detalle.correlacion_id : null;
  return (
    <div role="alert" className="grid gap-2 rounded-md border border-destructive/40 p-4 text-sm">
      <p>{mensaje ?? "No se pudo cargar la lista de obras."}</p>
      {referencia === null ? null : <p>Referencia: {referencia}</p>}
      <div>
        <Button type="button" variant="outline" onClick={alReintentar}>
          Reintentar
        </Button>
      </div>
    </div>
  );
}

function AvisoAccion({ aviso }: { aviso: Aviso }) {
  return (
    <div role="alert" className="grid gap-1 rounded-md border border-destructive/40 p-4 text-sm">
      <p>{aviso.texto}</p>
      {aviso.referencia === null ? null : <p>Referencia: {aviso.referencia}</p>}
    </div>
  );
}

function SinObras({ puedeDarDeAlta }: { puedeDarDeAlta: boolean }) {
  return (
    <div className="grid gap-1 rounded-md border p-6 text-center">
      <p className="font-medium">No hay obras</p>
      <p className="text-sm text-muted-foreground">
        {puedeDarDeAlta
          ? "Da de alta la primera obra con el botón +."
          : "Las obras las da de alta el Director de Proyectos o la Dirección General."}
      </p>
    </div>
  );
}

interface PropsTablaObras {
  obras: Obra[];
  total: number;
  conLineaBase: boolean;
  /** La columna «Acciones» (encabezado y celdas) existe solo si el rol puede operar: lo decide el rol, no las filas. */
  conAcciones: boolean;
  roles: readonly Rol[];
  alAccionFila: (accion: AccionDeFila, obra: Obra) => void;
}

function TablaObras({ obras, total, conLineaBase, conAcciones, roles, alAccionFila }: PropsTablaObras) {
  return (
    <div className="grid gap-2">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b text-left">
            <th scope="col" className="px-3 py-2 font-medium">
              Código
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Nombre
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Estado
            </th>
            {conLineaBase ? (
              <th scope="col" className="px-3 py-2 font-medium">
                {ETIQUETA_LINEA_BASE}
              </th>
            ) : null}
            {conAcciones ? (
              <th scope="col" className="px-3 py-2 font-medium">
                Acciones
              </th>
            ) : null}
          </tr>
        </thead>
        <tbody>
          {obras.map((obra) => (
            <tr key={obra.id} className="border-b">
              <td className="px-3 py-2">{obra.codigo}</td>
              <td className="px-3 py-2">{obra.nombre}</td>
              <td className="px-3 py-2">{ETIQUETA_ESTADO[obra.estado]}</td>
              {conLineaBase ? (
                <td className="px-3 py-2">
                  <Link to={`/obras/${obra.id}/linea-base`} aria-label={`${ETIQUETA_LINEA_BASE} de ${obra.codigo}`} className="underline">
                    {ETIQUETA_LINEA_BASE}
                  </Link>
                </td>
              ) : null}
              {conAcciones ? (
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-2">
                    {accionesDeFila(obra.estado, roles).map((accion) => (
                      <Button
                        key={accion}
                        type="button"
                        size="sm"
                        variant="outline"
                        aria-label={`${ETIQUETA_ACCION[accion]} ${obra.codigo}`}
                        onClick={() => alAccionFila(accion, obra)}
                      >
                        {ETIQUETA_ACCION[accion]}
                      </Button>
                    ))}
                  </div>
                </td>
              ) : null}
            </tr>
          ))}
        </tbody>
      </table>
      {total > obras.length ? <p className="text-sm text-muted-foreground">{`Mostrando ${obras.length} de ${total} obras`}</p> : null}
    </div>
  );
}

/** Lista de obras con sus cuatro estados (CA-12). El estado bloqueado no aplica a la lista: el del alta vive en el formulario. */
export function PantallaObras() {
  const api = useApi();
  const queryClient = useQueryClient();
  const sesion = useSesion();
  const lista = useQuery(obrasOptions(api));
  const [formularioAbierto, setFormularioAbierto] = useState(false);
  // La obra cuyo formulario de edición está abierto; null cuando no hay ninguno (CA-15).
  const [obraEditada, setObraEditada] = useState<Obra | null>(null);
  const [bloqueo, setBloqueo] = useState<ErrorBloqueo | null>(null);
  // La obra cuya baja se confirma; null cuando no hay confirmación abierta (CA-5).
  const [obraAEliminar, setObraAEliminar] = useState<Obra | null>(null);
  const [bloqueoBaja, setBloqueoBaja] = useState<BloqueoBaja | null>(null);
  // La transición con motivo abierta, y el 409 de estado que el servidor devolvió dentro de ella (CA-17).
  const [motivo, setMotivo] = useState<MotivoEnCurso | null>(null);
  const [conflictoMotivo, setConflictoMotivo] = useState<ErrorConflictoEstado | null>(null);
  const [aviso, setAviso] = useState<Aviso | null>(null);
  const roles = sesion.data?.roles ?? [];
  // Cortesía de navegación (PA-T8): el control real es el 403 del servidor. Lo decide el rol, nunca el estado de las filas.
  const puedeOperar = roles.some((rol) => ROLES_QUE_OPERAN.includes(rol));
  // Cortesía de navegación: el control real es la guarda de la sección y el 403 del servidor.
  const veLineaBase = seccionPermitida("LINEA_BASE", roles);

  function limpiarRechazos() {
    setBloqueo(null);
    setBloqueoBaja(null);
    setAviso(null);
  }

  // Reparto común de un rechazo: el de negocio o de concurrencia es un bloqueo con sus datos; el resto, un aviso.
  function pintarRechazo(error: ErrorApi, textoPorOmision: string) {
    limpiarRechazos();
    if (error.tipo === "REGLA_NEGOCIO" || error.tipo === "CONCURRENCIA") setBloqueo(error);
    else setAviso(avisoDe(error, textoPorOmision));
  }

  function abrirFormulario() {
    limpiarRechazos();
    setFormularioAbierto(true);
  }

  function abrirEdicion(obra: Obra) {
    limpiarRechazos();
    setObraEditada(obra);
  }

  function cerrarFormularios() {
    setFormularioAbierto(false);
    setObraEditada(null);
  }

  function refrescarObras() {
    void queryClient.invalidateQueries({ queryKey: claves.obras });
  }

  function abrirMotivo(verbo: VerboMotivo, obra: Obra) {
    setAviso(null);
    setConflictoMotivo(null);
    setMotivo({ verbo, obra });
  }

  // Cerrar el motivo. La lista se vuelve a pedir solo si el servidor respondió: cancelar sin enviar no consulta nada.
  function cerrarMotivo(refrescar: boolean) {
    setMotivo(null);
    setConflictoMotivo(null);
    if (refrescar) refrescarObras();
  }

  // D-7: «Ver la obra» cierra el formulario y deja la lista a la vista; la ficha queda para un ticket futuro.
  function alAccion(accion: Accion) {
    if (accion.clave === "VER_OBRA") cerrarFormularios();
  }

  // Un 409 de regla o de concurrencia cierra el formulario abierto y se pinta como bloqueo con sus datos, nunca como error.
  function alBloqueo(error: ErrorReglaNegocio | ErrorConcurrencia) {
    // Solo llegan los dos tipos de bloqueo: el texto de aviso no llega a pintarse.
    pintarRechazo(error, "No se pudo completar la operación.");
    cerrarFormularios();
  }

  // Cada fila entrega su acción con la obra de esa fila: nunca con la primera de la lista.
  function alAccionFila(accion: AccionDeFila, obra: Obra) {
    limpiarRechazos();
    switch (accion) {
      case "EDITAR":
        abrirEdicion(obra);
        return;
      case "ELIMINAR":
        setObraAEliminar(obra);
        return;
      case "SUSPENDER":
        abrirMotivo("SUSPENDER", obra);
        return;
      case "REACTIVAR":
        abrirMotivo("REACTIVAR", obra);
        return;
      case "CERRAR":
        abrirMotivo("CERRAR", obra);
        return;
    }
  }

  // El 409 de la baja: `OBRA_CON_HISTORIAL` es un bloqueo de la página; cualquier otro rechazo se avisa.
  function rechazarBaja(error: ErrorApi, obra: Obra) {
    setObraAEliminar(null);
    if (error.tipo === "CONFLICTO" && error.codigo === "OBRA_CON_HISTORIAL") {
      limpiarRechazos();
      setBloqueoBaja({ error, obra });
      return;
    }
    pintarRechazo(error, "No se pudo eliminar la obra.");
  }

  // El 409 de estado se queda dentro del diálogo, con el motivo tecleado. Lo demás cierra el diálogo y se pinta en la página.
  function rechazarMotivo(error: ErrorApi) {
    if (error.tipo === "CONFLICTO") {
      setConflictoMotivo(error);
      return;
    }
    cerrarMotivo(true);
    pintarRechazo(error, "No se pudo completar la operación.");
  }

  // Las acciones del bloqueo de baja operan sobre la obra que se intentó eliminar, no sobre la primera fila.
  function alAccionBloqueoBaja(accion: Accion, obra: Obra) {
    if (accion.clave === "SUSPENDER_OBRA") abrirMotivo("SUSPENDER", obra);
    else if (accion.clave === "CERRAR_OBRA") abrirMotivo("CERRAR", obra);
  }

  function contenidoLista() {
    if (lista.isPending) return <EsqueletoLista />;
    if (lista.isError) return <AvisoErrorLista error={lista.error} alReintentar={() => void lista.refetch()} />;
    const obras = lista.data.elementos;
    if (obras.length === 0) return <SinObras puedeDarDeAlta={puedeOperar} />;
    return (
      <TablaObras
        obras={obras}
        total={lista.data.paginacion.total}
        conLineaBase={veLineaBase}
        conAcciones={puedeOperar}
        roles={roles}
        alAccionFila={alAccionFila}
      />
    );
  }

  return (
    <section className="grid gap-4 p-6">
      <header className="flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold">Obras</h1>
        {puedeOperar ? (
          <Button type="button" size="icon" aria-label={ETIQUETA_ALTA} onClick={abrirFormulario}>
            <span aria-hidden="true">+</span>
          </Button>
        ) : null}
      </header>

      {bloqueo === null ? null : <ConflictoEnLinea error={bloqueo} alAccion={alAccion} />}

      {bloqueoBaja === null ? null : (
        <ConflictoEnLinea
          error={{ ...bloqueoBaja.error, acciones: accionesEjecutablesEnBaja(bloqueoBaja.error.acciones) }}
          alAccion={(accion) => alAccionBloqueoBaja(accion, bloqueoBaja.obra)}
        />
      )}

      {aviso === null ? null : <AvisoAccion aviso={aviso} />}

      {contenidoLista()}

      <FormularioCatalogo<typeof esquemaObra, Obra>
        abierto={formularioAbierto}
        titulo={TITULO_FORMULARIO}
        esquema={esquemaObra}
        campos={CAMPOS_OBRA}
        valoresIniciales={VALORES_INICIALES_OBRA}
        alGuardar={(valores) => crearObra(api, valores)}
        alGuardado={refrescarObras}
        alBloqueo={alBloqueo}
        alAccion={alAccion}
        alCerrar={cerrarFormularios}
      />

      {/* Se monta solo mientras hay una obra en edición: cada apertura arranca con los valores de esa obra. */}
      {obraEditada === null ? null : (
        <FormularioCatalogo<typeof esquemaVistaEdicionObra, Obra>
          abierto
          titulo={TITULO_EDICION}
          esquema={esquemaVistaEdicionObra}
          campos={CAMPOS_VISTA_EDICION_OBRA}
          valoresIniciales={valoresDeVistaEdicion(obraEditada)}
          alGuardar={(valores) => editarObra(api, obraEditada.id, cambiosDeEdicion(valores))}
          alGuardado={refrescarObras}
          alBloqueo={alBloqueo}
          alAccion={alAccion}
          alCerrar={cerrarFormularios}
        />
      )}

      {/* Se monta solo mientras hay una eliminación por confirmar: la pregunta nombra la obra de esa fila (CA-5). */}
      {obraAEliminar === null ? null : (
        <ConfirmacionBaja
          abierta
          pregunta={`¿Eliminar la obra ${obraAEliminar.codigo}?`}
          alConfirmar={() => eliminarObra(api, obraAEliminar.id)}
          alHecho={() => {
            setObraAEliminar(null);
            limpiarRechazos();
            refrescarObras();
          }}
          alRechazo={(error) => rechazarBaja(error, obraAEliminar)}
          alCancelar={() => setObraAEliminar(null)}
        />
      )}

      {/* Se monta solo mientras hay una transición con motivo: el motivo vacío no envía (CA-17). */}
      {motivo === null ? null : (
        <CapturaMotivo
          abierta
          titulo={TITULO_MOTIVO[motivo.verbo]}
          descripcion={`Obra ${motivo.obra.codigo}`}
          etiquetaConfirmar={ETIQUETA_CONFIRMAR_MOTIVO[motivo.verbo]}
          alConfirmar={(texto) => {
            setConflictoMotivo(null);
            return OPERACION_DE_MOTIVO[motivo.verbo](api, motivo.obra.id, texto);
          }}
          alHecho={() => {
            setBloqueoBaja(null);
            cerrarMotivo(true);
          }}
          alRechazo={rechazarMotivo}
          alCancelar={() => cerrarMotivo(conflictoMotivo !== null)}
          avisoEnLinea={
            conflictoMotivo === null ? undefined : (
              <ConflictoEnLinea error={{ ...conflictoMotivo, acciones: [] }} alAccion={() => undefined} regionViva={false} />
            )
          }
        />
      )}
    </section>
  );
}
