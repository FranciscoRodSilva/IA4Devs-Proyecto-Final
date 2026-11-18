import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import type { ResultadoApi } from "@/api/cliente";
import type { ErrorConcurrencia, ErrorReglaNegocio } from "@/api/errores";
import type { components } from "@/api/generado/servidor";
import { useApi } from "@/api/ProveedorApi";
import { useSesion } from "@/api/sesion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { CapturaMotivo } from "@/compartido/formularios/CapturaMotivo";
import { PantallaBloqueo } from "@/compartido/componentes/bloqueo/PantallaBloqueo";
import { FormularioCatalogo } from "@/compartido/formularios/FormularioCatalogo";
import { type AccionDeFila, TablaProveedores } from "./TablaProveedores";
import { AvisoErrorLista, EsqueletoLista, SinProveedores } from "./estados-lista";
import {
  camposAlta,
  camposEdicion,
  cambiosDe,
  esquemaAlta,
  esquemaVistaEdicionProveedor,
  type SalidaEdicion,
  valoresInicialesDe,
  VALORES_INICIALES_ALTA,
} from "./proveedores.formulario";
import { actualizarProveedor, claves, crearProveedor, proveedoresOptions, totalDePaginas } from "./proveedores.consultas";
import {
  type AvisoCabecera,
  ETIQUETA_CONFIRMAR_MOTIVO,
  OPERACION_DE_ESTADO,
  TITULO_MOTIVO,
  useOperacionDeEstado,
} from "./useOperacionDeEstado";

type Esquemas = components["schemas"];
type Proveedor = Esquemas["Proveedor"];
type EstadoProveedor = Esquemas["EstadoProveedor"];

/** Cortesía de navegación: el control real es el 403 del servidor (D-2). */
const ETIQUETA_ALTA = "Dar de alta un proveedor";

type FiltroEstado = "ACTIVO" | "DESACTIVADO" | "BAJA" | "TODOS";
const OPCIONES_FILTRO: ReadonlyArray<{ valor: FiltroEstado; etiqueta: string }> = [
  { valor: "ACTIVO", etiqueta: "Activos" },
  { valor: "DESACTIVADO", etiqueta: "Desactivados" },
  { valor: "BAJA", etiqueta: "Dados de baja" },
  { valor: "TODOS", etiqueta: "Todos" },
];
const ESTADOS_DE_FILTRO: Readonly<Record<FiltroEstado, ReadonlyArray<EstadoProveedor>>> = {
  ACTIVO: ["ACTIVO"],
  DESACTIVADO: ["DESACTIVADO"],
  BAJA: ["BAJA"],
  TODOS: ["ACTIVO", "DESACTIVADO", "BAJA"],
};

const TITULO_ALTA = "Alta de proveedor";
const TITULO_EDICION = "Editar proveedor";

/** Catálogo de proveedores (M-wireframe 2c): lista con filtro, búsqueda y paginación; solo COMPRAS ve las acciones. */
export function PantallaProveedores() {
  const api = useApi();
  const queryClient = useQueryClient();
  const sesion = useSesion();
  const idEstado = useId();
  const [filtro, setFiltro] = useState<FiltroEstado>("ACTIVO");
  const [texto, setTexto] = useState("");
  const [q, setQ] = useState("");
  const [pagina, setPagina] = useState(1);
  const [altaAbierta, setAltaAbierta] = useState(false);
  // El proveedor que se edita; el diálogo se monta solo mientras hay uno, así que cada apertura parte de sus valores.
  const [edicion, setEdicion] = useState<Proveedor | null>(null);
  const [aviso, setAviso] = useState<AvisoCabecera | null>(null);
  const { operacion, bloqueo, abrirMotivo, rechazar, alAccionBloqueo, cerrar, cerrarBloqueo } = useOperacionDeEstado(
    refrescarProveedores,
    setAviso,
  );
  const lista = useQuery(proveedoresOptions(api, { estados: ESTADOS_DE_FILTRO[filtro], q, pagina }));
  const puedeOperar = (sesion.data?.roles ?? []).includes("COMPRAS");

  function abrirAlta() {
    setAviso(null);
    setAltaAbierta(true);
  }

  function abrirEdicion(proveedor: Proveedor) {
    setAviso(null);
    setEdicion(proveedor);
  }

  // Cada fila entrega su acción con el proveedor de esa fila: nunca con el primero de la lista.
  function alAccionFila(accion: AccionDeFila, proveedor: Proveedor) {
    switch (accion) {
      case "EDITAR":
        abrirEdicion(proveedor);
        return;
      case "DESACTIVAR":
        abrirMotivo("DESACTIVAR", proveedor);
        return;
      case "DAR_DE_BAJA":
        abrirMotivo("DAR_DE_BAJA", proveedor);
        return;
    }
  }

  function refrescarProveedores() {
    void queryClient.invalidateQueries({ queryKey: claves.proveedores });
  }

  // Un bloqueo de concurrencia (`BLOQUEO_VENCIDO`) cierra la edición y se avisa en la cabecera; el alta también puede
  // recibir `CONCURRENCIA` y se trata igual. Un 404 no llega aquí (es un error del formulario).
  function avisarYCerrar(cerrarFormulario: () => void, textoPorOmision: string) {
    return (error: ErrorReglaNegocio | ErrorConcurrencia) => {
      cerrarFormulario();
      setAviso({ texto: error.mensaje ?? textoPorOmision, referencia: error.correlacion_id });
    };
  }
  // Sin cambios no hay petición: el resultado vacío cierra el diálogo sin pedir la lista otra vez (datos: null).
  // Un 404 deja al proveedor sin existir en el servidor: se devuelve el error al formulario y se recarga la lista.
  async function guardarEdicion(proveedor: Proveedor, valores: SalidaEdicion): Promise<ResultadoApi<Proveedor | null>> {
    const cambios = cambiosDe(proveedor, valores);
    if (cambios === null) return { ok: true, datos: null };
    const resultado = await actualizarProveedor(api, proveedor.id, cambios);
    if (!resultado.ok && resultado.error.tipo === "NO_ENCONTRADO") refrescarProveedores();
    return resultado;
  }

  // La página pedida salió vacía pero el filtro tiene datos: se pide la última con datos (ajuste durante el render).
  if (lista.data !== undefined && lista.data.elementos.length === 0 && lista.data.paginacion.total > 0) {
    const ultima = totalDePaginas(lista.data.paginacion.total);
    if (ultima !== pagina) setPagina(ultima);
  }

  function buscar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setQ(texto.trim());
    setPagina(1);
  }

  function contenidoLista() {
    if (lista.isPending) return <EsqueletoLista />;
    if (lista.isError) return <AvisoErrorLista error={lista.error} alReintentar={() => void lista.refetch()} />;
    const { elementos, paginacion } = lista.data;
    if (elementos.length === 0) {
      // Solo se espera (esqueleto) cuando ya se pidió otra página; si la última es la actual, no hay nada que esperar.
      if (paginacion.total > 0 && totalDePaginas(paginacion.total) !== pagina) return <EsqueletoLista />;
      return <SinProveedores invitarAlta={puedeOperar && filtro === "ACTIVO" && q === "" && paginacion.total === 0} />;
    }
    const totalPaginas = totalDePaginas(paginacion.total);
    return (
      <div className="grid gap-2">
        <TablaProveedores proveedores={elementos} conAcciones={puedeOperar} alAccionFila={alAccionFila} />
        <div className="flex items-center justify-between gap-2">
          <Button type="button" variant="outline" disabled={pagina <= 1} onClick={() => setPagina(pagina - 1)}>
            Anterior
          </Button>
          <span className="text-sm">{`Página ${pagina} de ${totalPaginas}`}</span>
          <Button type="button" variant="outline" disabled={pagina >= totalPaginas} onClick={() => setPagina(pagina + 1)}>
            Siguiente
          </Button>
        </div>
      </div>
    );
  }

  return (
    <section className="grid gap-4 p-6">
      <header className="flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold">Proveedores</h1>
        {puedeOperar ? (
          <Button type="button" size="icon" aria-label={ETIQUETA_ALTA} onClick={abrirAlta}>
            <span aria-hidden="true">+</span>
          </Button>
        ) : null}
      </header>

      <div className="flex flex-wrap items-end gap-4">
        <div className="grid gap-1">
          <Label htmlFor={idEstado}>Estado</Label>
          <select
            id={idEstado}
            value={filtro}
            onChange={(evento) => {
              const elegido = OPCIONES_FILTRO.find((opcion) => opcion.valor === evento.target.value);
              if (elegido === undefined) return;
              setFiltro(elegido.valor);
              setPagina(1);
            }}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {OPCIONES_FILTRO.map((opcion) => (
              <option key={opcion.valor} value={opcion.valor}>
                {opcion.etiqueta}
              </option>
            ))}
          </select>
        </div>
        <form role="search" onSubmit={buscar} className="flex items-end gap-2">
          <Input
            type="search"
            aria-label="Buscar por nombre o RFC"
            placeholder="Buscar por nombre o RFC"
            value={texto}
            onChange={(evento) => setTexto(evento.target.value)}
          />
          <Button type="submit" variant="outline">
            Buscar
          </Button>
        </form>
      </div>

      {aviso === null ? null : (
        <div role="alert" className="grid gap-1 rounded-md border border-destructive/40 p-4 text-sm">
          <p>{aviso.texto}</p>
          {aviso.referencia === null ? null : <p>Referencia: {aviso.referencia}</p>}
        </div>
      )}

      {bloqueo === null ? null : (
        <PantallaBloqueo
          error={bloqueo.error}
          alAccion={(accion) => alAccionBloqueo(accion, bloqueo)}
          alCerrar={cerrarBloqueo}
          alReintentar={() => abrirMotivo(bloqueo.verbo, bloqueo.proveedor)}
        />
      )}

      {contenidoLista()}

      <FormularioCatalogo<typeof esquemaAlta, Proveedor>
        abierto={altaAbierta}
        titulo={TITULO_ALTA}
        esquema={esquemaAlta}
        campos={camposAlta}
        valoresIniciales={VALORES_INICIALES_ALTA}
        alGuardar={(valores) => crearProveedor(api, valores)}
        alGuardado={refrescarProveedores}
        alBloqueo={avisarYCerrar(() => setAltaAbierta(false), "No se pudo dar de alta el proveedor.")}
        alAccion={() => undefined}
        alCerrar={() => setAltaAbierta(false)}
      />

      {edicion === null ? null : (
        <FormularioCatalogo<typeof esquemaVistaEdicionProveedor, Proveedor | null>
          abierto
          titulo={TITULO_EDICION}
          esquema={esquemaVistaEdicionProveedor}
          campos={camposEdicion}
          valoresIniciales={valoresInicialesDe(edicion)}
          alGuardar={(valores) => guardarEdicion(edicion, valores)}
          alGuardado={(respuesta) => {
            if (respuesta !== null) refrescarProveedores();
          }}
          alBloqueo={avisarYCerrar(() => setEdicion(null), "No se pudo editar el proveedor.")}
          alAccion={() => undefined}
          alCerrar={() => setEdicion(null)}
        />
      )}

      {/* Se monta solo mientras hay una operación de estado: el motivo vacío no envía y el id es el de la fila pulsada. */}
      {operacion === null ? null : (
        <CapturaMotivo
          abierta
          titulo={TITULO_MOTIVO[operacion.verbo](operacion.proveedor.nombre)}
          etiquetaConfirmar={ETIQUETA_CONFIRMAR_MOTIVO[operacion.verbo]}
          alConfirmar={(motivo) => OPERACION_DE_ESTADO[operacion.verbo](api, operacion.proveedor.id, motivo)}
          alHecho={() => {
            cerrar();
            refrescarProveedores();
          }}
          alRechazo={(error) => rechazar(error, operacion)}
          alCancelar={cerrar}
        />
      )}
    </section>
  );
}
