import type { components } from "@/api/generado/servidor";
import { Button } from "@/components/ui/button";
import { DIAS } from "./proveedores.formulario";

type Esquemas = components["schemas"];
type Proveedor = Esquemas["Proveedor"];
type EstadoProveedor = Esquemas["EstadoProveedor"];

const ETIQUETA_ESTADO: Readonly<Record<EstadoProveedor, string>> = {
  ACTIVO: "Activo",
  DESACTIVADO: "Desactivado",
  BAJA: "Baja",
};

export type AccionDeFila = "EDITAR" | "DESACTIVAR" | "DAR_DE_BAJA";
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
  alAccionFila: (accion: AccionDeFila, proveedor: Proveedor) => void;
}

export function TablaProveedores({ proveedores, conAcciones, alAccionFila }: PropsTabla) {
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
                    <Button
                      key={accion}
                      type="button"
                      size="sm"
                      variant="outline"
                      aria-label={`${ETIQUETA_ACCION[accion]} ${proveedor.nombre}`}
                      onClick={() => alAccionFila(accion, proveedor)}
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
