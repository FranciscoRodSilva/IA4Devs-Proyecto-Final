import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useId, useState } from "react";
import type { ErrorConcurrencia, ErrorReglaNegocio } from "@/api/errores";
import type { components } from "@/api/generado/servidor";
import { useApi } from "@/api/ProveedorApi";
import { useSesion } from "@/api/sesion";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FormularioCatalogo } from "@/compartido/formularios/FormularioCatalogo";
import { AvisoErrorLista, EsqueletoLista, SinProveedores } from "./estados-lista";
import { camposAlta, DIAS, esquemaAlta, VALORES_INICIALES_ALTA } from "./proveedores.formulario";
import { claves, crearProveedor, proveedoresOptions, totalDePaginas } from "./proveedores.consultas";

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

const ETIQUETA_ESTADO: Readonly<Record<EstadoProveedor, string>> = {
  ACTIVO: "Activo",
  DESACTIVADO: "Desactivado",
  BAJA: "Baja",
};

type AccionDeFila = "EDITAR" | "DESACTIVAR" | "DAR_DE_BAJA";
const ETIQUETA_ACCION: Readonly<Record<AccionDeFila, string>> = {
  EDITAR: "Editar",
  DESACTIVAR: "Desactivar",
  DAR_DE_BAJA: "Dar de baja",
};

/** D-7: lo que se ofrece sale del estado que devolvió el servidor; sobre una baja no se ofrece nada. */
function accionesDe(estado: EstadoProveedor): readonly AccionDeFila[] {
  switch (estado) {
    case "ACTIVO":
      return ["EDITAR", "DESACTIVAR", "DAR_DE_BAJA"];
    case "DESACTIVADO":
      return ["EDITAR", "DAR_DE_BAJA"];
    case "BAJA":
      return [];
  }
}

function nombreDeDia(dia: number): string {
  return DIAS.find((candidato) => candidato.valor === String(dia))?.etiqueta ?? String(dia);
}

interface PropsTabla {
  proveedores: Proveedor[];
  conAcciones: boolean;
}

function TablaProveedores({ proveedores, conAcciones }: PropsTabla) {
  const encabezados = ["Nombre", "RFC", "Estado", "Corte", "Pago", ...(conAcciones ? ["Acciones"] : [])];
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-left">
          {encabezados.map((encabezado) => (
            <th key={encabezado} scope="col" className="px-3 py-2 font-medium">
              {encabezado}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {proveedores.map((proveedor) => (
          <tr key={proveedor.id} className="border-b">
            <td className="px-3 py-2">{proveedor.nombre}</td>
            <td className="px-3 py-2">{proveedor.rfc}</td>
            <td className={proveedor.estado === "ACTIVO" ? "px-3 py-2" : "px-3 py-2 text-muted-foreground"}>
              {ETIQUETA_ESTADO[proveedor.estado]}
            </td>
            <td className="px-3 py-2">{nombreDeDia(proveedor.dia_corte)}</td>
            <td className="px-3 py-2">{nombreDeDia(proveedor.dia_pago)}</td>
            {conAcciones ? (
              <td className="px-3 py-2">
                <div className="flex flex-wrap gap-2">
                  {accionesDe(proveedor.estado).map((accion) => (
                    // F7 conecta «Editar» y F8 «Desactivar» y «Dar de baja»: hasta entonces los botones solo se pintan.
                    <Button
                      key={accion}
                      type="button"
                      size="sm"
                      variant="outline"
                      aria-label={`${ETIQUETA_ACCION[accion]} ${proveedor.nombre}`}
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
  );
}

const TITULO_ALTA = "Alta de proveedor";

/** Un rechazo del alta que no es de campo ni de RFC: se avisa en la cabecera, con su referencia si el servidor la trae. */
interface AvisoAlta {
  texto: string;
  referencia: string | null;
}

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
  const [avisoAlta, setAvisoAlta] = useState<AvisoAlta | null>(null);
  const lista = useQuery(proveedoresOptions(api, { estados: ESTADOS_DE_FILTRO[filtro], q, pagina }));
  const puedeOperar = (sesion.data?.roles ?? []).includes("COMPRAS");

  function abrirAlta() {
    setAvisoAlta(null);
    setAltaAbierta(true);
  }

  function refrescarProveedores() {
    void queryClient.invalidateQueries({ queryKey: claves.proveedores });
  }

  // El alta no debería recibir un bloqueo de regla ni de concurrencia: si llega, cierra el formulario y se avisa en la cabecera.
  function alBloqueoAlta(error: ErrorReglaNegocio | ErrorConcurrencia) {
    setAltaAbierta(false);
    setAvisoAlta({ texto: error.mensaje ?? "No se pudo dar de alta el proveedor.", referencia: error.correlacion_id });
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
        <TablaProveedores proveedores={elementos} conAcciones={puedeOperar} />
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

      {avisoAlta === null ? null : (
        <div role="alert" className="grid gap-1 rounded-md border border-destructive/40 p-4 text-sm">
          <p>{avisoAlta.texto}</p>
          {avisoAlta.referencia === null ? null : <p>Referencia: {avisoAlta.referencia}</p>}
        </div>
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
        alBloqueo={alBloqueoAlta}
        alAccion={() => undefined}
        alCerrar={() => setAltaAbierta(false)}
      />
    </section>
  );
}
