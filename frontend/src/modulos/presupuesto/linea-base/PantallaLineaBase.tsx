import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router";
import { FalloApi } from "@/api/cliente";
import type { ErrorApi } from "@/api/errores";
import type { components } from "@/api/generado/servidor";
import { useApi } from "@/api/ProveedorApi";
import { type Rol, useSesion } from "@/api/sesion";
import { AvisoSinPermiso } from "@/app/armazon/AvisoSinPermiso";
import { NoEncontrado } from "@/app/armazon/NoEncontrado";
import { Button } from "@/components/ui/button";
import { obraOptions } from "@/modulos/presupuesto/obras/obras.consultas";
import { FormularioCongelado } from "./FormularioCongelado";
import { lineaBaseMostrada, lineasBaseOptions } from "./linea-base.consultas";
import { formatearFecha, importe, mensajeDeRechazo } from "./presentacion";
import { TablaPresupuestoControl } from "./TablaPresupuestoControl";

type Esquemas = components["schemas"];
type Obra = Esquemas["Obra"];
type LineaBase = Esquemas["LineaBase"];

/** D-1 · cortesía de presentación, no seguridad: COMPRAS no ve el borrador aunque el servidor se lo devuelva. */
const ROLES_QUE_VEN_BORRADOR: readonly Rol[] = ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL"];

/** El error de la consulta, si es el de la capa de API. Cualquier otra cosa no tiene detalle que pintar. */
function errorDe(fallo: unknown): ErrorApi | null {
  return fallo instanceof FalloApi ? fallo.error : null;
}

function EsqueletoLineaBase() {
  return (
    <div role="status" aria-busy="true" aria-label="Cargando la línea base" className="space-y-2 p-6">
      {[0, 1, 2].map((indice) => (
        <div key={indice} className="h-8 animate-pulse rounded bg-muted" />
      ))}
    </div>
  );
}

function ObraInexistente() {
  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold">La obra no existe</h1>
    </div>
  );
}

function AvisoError({ error, alReintentar }: { error: ErrorApi | null; alReintentar: () => void }) {
  return (
    <div className="p-6">
      <div role="alert" className="grid gap-2 rounded-md border border-destructive/40 p-4 text-sm">
        <p className="font-medium">No se pudo cargar la línea base.</p>
        {error === null ? null : <p>{mensajeDeRechazo(error)}</p>}
        <div>
          <Button type="button" variant="outline" onClick={alReintentar}>
            Reintentar
          </Button>
        </div>
      </div>
    </div>
  );
}

function SinLineaBase() {
  return (
    <div className="grid gap-1 rounded-md border p-6 text-center">
      <p className="font-medium">Esta obra todavía no tiene línea base.</p>
      <p className="text-sm text-muted-foreground">
        La importación del presupuesto llegará en una próxima entrega (TKT-018b).
      </p>
    </div>
  );
}

function Dato({ rotulo, valor }: { rotulo: string; valor: string }) {
  return (
    <div>
      <dt className="text-muted-foreground">{rotulo}</dt>
      <dd className="font-medium">{valor}</dd>
    </div>
  );
}

function DatosLineaBase({ obra, linea }: { obra: Obra; linea: LineaBase }) {
  return (
    <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
      <Dato rotulo="Estado" valor={linea.estado} />
      <Dato rotulo="Versión" valor={String(linea.version)} />
      <Dato rotulo="Estado de la obra" valor={obra.estado} />
      <Dato rotulo="Importe de venta" valor={importe(linea.importe_venta)} />
    </dl>
  );
}

function Desglose({ linea }: { linea: LineaBase }) {
  return (
    <table className="w-full text-sm">
      <caption className="pb-2 text-left font-medium">Desglose por tipo de partida</caption>
      <thead>
        <tr className="border-b text-left">
          <th scope="col" className="px-3 py-2 font-medium">
            Tipo de partida
          </th>
          <th scope="col" className="px-3 py-2 text-right font-medium">
            Venta
          </th>
        </tr>
      </thead>
      <tbody>
        {linea.por_tipo_partida.map((fila) => (
          <tr key={fila.tipo_partida.id} className="border-b">
            <th scope="row" className="px-3 py-2 text-left font-normal">
              {fila.tipo_partida.nombre}
            </th>
            <td className="px-3 py-2 text-right tabular-nums">{importe(fila.importe_venta)}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Solo lectura de una línea base CONGELADA: quién congeló, cuándo y por qué (RN-01). Ningún control. */
function DatosCongelado({ linea }: { linea: LineaBase }) {
  // El contrato declara los tres campos opcionales y anulables: ninguno se da por presente.
  const congeladaEn = linea.congelada_en ?? null;
  const fecha = congeladaEn === null ? null : formatearFecha(congeladaEn);
  const autor = linea.congelada_por?.nombre ?? null;
  const motivo = linea.motivo ?? null;
  return (
    <div className="grid gap-1 text-sm">
      <p>
        Congelada
        {congeladaEn === null || fecha === null ? null : (
          <>
            {" el "}
            <time dateTime={congeladaEn}>{fecha}</time>
          </>
        )}
        {autor === null ? null : ` por ${autor}`}
      </p>
      {motivo === null ? null : <p>{`Motivo: ${motivo}`}</p>}
    </div>
  );
}

function VistaLineaBase({ obraId }: { obraId: string }) {
  const api = useApi();
  const sesion = useSesion();
  const obra = useQuery(obraOptions(api, obraId));
  const lineas = useQuery(lineasBaseOptions(api, obraId));
  const verBorrador = sesion.data?.roles.some((rol) => ROLES_QUE_VEN_BORRADOR.includes(rol)) ?? false;
  const puedeCongelar = sesion.data?.roles.includes("DIRECTOR_PROYECTOS") ?? false;
  const puedeCapturar = sesion.data?.roles.includes("DIRECCION_GENERAL") ?? false;

  // Los rechazos se distinguen por `tipo`, y basta con que falle una de las dos consultas.
  const errores = [obra, lineas].filter((consulta) => consulta.isError).map((consulta) => errorDe(consulta.error));
  const tipos = errores.map((error) => error?.tipo);
  if (tipos.includes("NO_ENCONTRADO") || tipos.includes("VALIDACION")) return <ObraInexistente />;
  if (tipos.includes("PERMISO")) return <AvisoSinPermiso />;
  if (obra.isError || lineas.isError) {
    function reintentar() {
      void obra.refetch();
      void lineas.refetch();
    }
    return <AvisoError error={errores[0] ?? null} alReintentar={reintentar} />;
  }
  if (obra.isPending || lineas.isPending) return <EsqueletoLineaBase />;

  const linea = lineaBaseMostrada(lineas.data, verBorrador);
  return (
    <section className="grid gap-4 p-6">
      <h1 className="text-xl font-semibold">{`Línea base · ${obra.data.codigo} · ${obra.data.nombre}`}</h1>
      {linea === null ? (
        <SinLineaBase />
      ) : (
        <>
          <DatosLineaBase obra={obra.data} linea={linea} />
          <Desglose linea={linea} />
          {linea.estado === "CONGELADA" ? (
            <>
              <DatosCongelado linea={linea} />
              <TablaPresupuestoControl lineaBaseId={linea.id} puedeCapturar={puedeCapturar} />
            </>
          ) : (
            <>
              {puedeCongelar ? <FormularioCongelado lineaBaseId={linea.id} /> : null}
              <p className="text-sm text-muted-foreground">
                Congela primero la línea base para capturar el presupuesto de control.
              </p>
            </>
          )}
        </>
      )}
    </section>
  );
}

/** M4a · wireframe «Línea base». La obra entra por la ruta `/obras/:obraId/linea-base`. */
export function PantallaLineaBase() {
  const { obraId } = useParams();
  if (obraId === undefined) return <NoEncontrado />;
  return <VistaLineaBase obraId={obraId} />;
}
