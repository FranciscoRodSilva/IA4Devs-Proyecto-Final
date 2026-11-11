import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { type Accion, type ErrorApi, type ErrorBloqueo, type ErrorConcurrencia, type ErrorReglaNegocio } from "@/api/errores";
import { FalloApi } from "@/api/cliente";
import type { components } from "@/api/generado/servidor";
import { useApi } from "@/api/ProveedorApi";
import { type Rol, useSesion } from "@/api/sesion";
import { Button } from "@/components/ui/button";
import { ConflictoEnLinea } from "@/compartido/formularios/ConflictoEnLinea";
import { FormularioCatalogo } from "@/compartido/formularios/FormularioCatalogo";
import { CAMPOS_OBRA, esquemaObra, VALORES_INICIALES_OBRA } from "./obras.formulario";
import { claves, crearObra, obrasOptions } from "./obras.consultas";

type Esquemas = components["schemas"];

/** M5 · wireframe «Obras». Cortesía de navegación (PA-T8): el control real es el 403 del servidor. */
const ROLES_QUE_DAN_DE_ALTA: readonly Rol[] = ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL"];
const ETIQUETA_ALTA = "Dar de alta una obra";
const TITULO_FORMULARIO = "Alta de obra";
const ETIQUETA_ESTADO: Readonly<Record<Esquemas["EstadoObra"], string>> = {
  PLANEACION: "Planeación",
  ACTIVA: "Activa",
  SUSPENDIDA: "Suspendida",
  CERRADA: "Cerrada",
};

/** El error de la consulta, si es el de la capa de API. Cualquier otra cosa no tiene detalle que pintar. */
function errorDe(fallo: unknown): ErrorApi | null {
  return fallo instanceof FalloApi ? fallo.error : null;
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

function TablaObras({ obras, total }: { obras: Esquemas["Obra"][]; total: number }) {
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
          </tr>
        </thead>
        <tbody>
          {obras.map((obra) => (
            <tr key={obra.id} className="border-b">
              <td className="px-3 py-2">{obra.codigo}</td>
              <td className="px-3 py-2">{obra.nombre}</td>
              <td className="px-3 py-2">{ETIQUETA_ESTADO[obra.estado]}</td>
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
  const [bloqueo, setBloqueo] = useState<ErrorBloqueo | null>(null);
  const puedeDarDeAlta = sesion.data?.roles.some((rol) => ROLES_QUE_DAN_DE_ALTA.includes(rol)) ?? false;

  function abrirFormulario() {
    setBloqueo(null);
    setFormularioAbierto(true);
  }

  // D-7: «Ver la obra» cierra el formulario y deja la lista a la vista; la ficha queda para un ticket futuro.
  function alAccion(accion: Accion) {
    if (accion.clave === "VER_OBRA") setFormularioAbierto(false);
  }

  // El alta no declara 409 de regla ni de concurrencia. Si llegara uno, se pinta como bloqueo con sus datos, nunca como error.
  function alBloqueo(error: ErrorReglaNegocio | ErrorConcurrencia) {
    setBloqueo(error);
    setFormularioAbierto(false);
  }

  function contenidoLista() {
    if (lista.isPending) return <EsqueletoLista />;
    if (lista.isError) return <AvisoErrorLista error={lista.error} alReintentar={() => void lista.refetch()} />;
    const obras = lista.data.elementos;
    if (obras.length === 0) return <SinObras puedeDarDeAlta={puedeDarDeAlta} />;
    return <TablaObras obras={obras} total={lista.data.paginacion.total} />;
  }

  return (
    <section className="grid gap-4 p-6">
      <header className="flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold">Obras</h1>
        {puedeDarDeAlta ? (
          <Button type="button" size="icon" aria-label={ETIQUETA_ALTA} onClick={abrirFormulario}>
            <span aria-hidden="true">+</span>
          </Button>
        ) : null}
      </header>

      {bloqueo === null ? null : <ConflictoEnLinea error={bloqueo} alAccion={alAccion} />}

      {contenidoLista()}

      <FormularioCatalogo<typeof esquemaObra, Esquemas["Obra"]>
        abierto={formularioAbierto}
        titulo={TITULO_FORMULARIO}
        esquema={esquemaObra}
        campos={CAMPOS_OBRA}
        valoresIniciales={VALORES_INICIALES_OBRA}
        alGuardar={(valores) => crearObra(api, valores)}
        alGuardado={() => void queryClient.invalidateQueries({ queryKey: claves.obras })}
        alBloqueo={alBloqueo}
        alAccion={alAccion}
        alCerrar={() => setFormularioAbierto(false)}
      />
    </section>
  );
}
