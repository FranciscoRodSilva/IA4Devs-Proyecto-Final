/** Rótulos de la pantalla de bloqueo. El servidor manda claves; el cliente solo les pone texto (D-7, D-8). */

export type FormatoCifra = "texto" | "importe";

export interface ClaveDetalle {
  clave: string;
  etiqueta: string;
  formato: FormatoCifra;
}

/** Claves conocidas del `detalle`, en el orden en que se pintan. */
export const CLAVES_DETALLE: readonly ClaveDetalle[] = [
  { clave: "obra", etiqueta: "Obra", formato: "texto" },
  { clave: "tipo_partida", etiqueta: "Tipo de partida", formato: "texto" },
  { clave: "folio", etiqueta: "Folio", formato: "texto" },
  { clave: "folio_orden", etiqueta: "Orden de compra", formato: "texto" },
  { clave: "estado", etiqueta: "Estado", formato: "texto" },
  { clave: "causa", etiqueta: "Causa", formato: "texto" },
  { clave: "presupuestado", etiqueta: "Presupuestado", formato: "importe" },
  { clave: "consumido", etiqueta: "Consumido", formato: "importe" },
  { clave: "disponible", etiqueta: "Disponible", formato: "importe" },
  { clave: "solicitado", etiqueta: "Solicitado", formato: "importe" },
  { clave: "excedente", etiqueta: "Excedente", formato: "importe" },
];

/** La clave del `detalle` que lleva el marcador de excedente. */
export const CLAVE_EXCEDENTE = "excedente";

/** Las partes del consumido, en orden, con su rótulo en el desglose. */
export const PARTES_CONSUMIDO: ReadonlyArray<{ clave: string; etiqueta: string }> = [
  { clave: "requisiciones_vivas", etiqueta: "requisiciones vivas" },
  { clave: "comprometido", etiqueta: "comprometido" },
  { clave: "ejercido", etiqueta: "ejercido" },
];

export const CLAVE_DESGLOSE = "consumido_desglose";

/** Referencias internas: nunca se pintan (D-8). */
export const CLAVES_OCULTAS: readonly string[] = [
  "requisicion_id",
  "solicitud_autorizacion_id",
  "orden_compra_id",
  "insumo_id",
  "orden_compra_renglon_id",
];

export type TipoColumna = "texto" | "cantidad" | "fecha";

export interface ColumnaTabla {
  encabezado: string;
  campo: string;
  tipo: TipoColumna;
}

export interface TablaDetalle {
  clave: string;
  titulo: string;
  columnas: readonly ColumnaTabla[];
  /** Campo booleano que, en `false`, marca la fila como no presupuestada en la partida. */
  campoPresupuestado?: string;
}

const INSUMO: ColumnaTabla = { encabezado: "Insumo", campo: "insumo", tipo: "texto" };

/** Tablas conocidas del `detalle`, en el orden en que se pintan. */
export const TABLAS_DETALLE: readonly TablaDetalle[] = [
  {
    clave: "insumos",
    titulo: "Insumos",
    campoPresupuestado: "presupuestado_en_partida",
    columnas: [
      INSUMO,
      { encabezado: "Presupuestado", campo: "cantidad_presupuestada", tipo: "cantidad" },
      { encabezado: "Consumido", campo: "cantidad_consumida", tipo: "cantidad" },
      { encabezado: "Disponible", campo: "cantidad_disponible", tipo: "cantidad" },
      { encabezado: "Solicitado", campo: "cantidad_solicitada", tipo: "cantidad" },
      { encabezado: "Excedente", campo: "excedente", tipo: "cantidad" },
    ],
  },
  {
    clave: "renglones",
    titulo: "Renglones",
    columnas: [
      INSUMO,
      { encabezado: "Ordenado", campo: "cantidad_ordenada", tipo: "cantidad" },
      { encabezado: "Recibido", campo: "cantidad_recibida", tipo: "cantidad" },
      { encabezado: "Saldo pendiente", campo: "saldo_pendiente", tipo: "cantidad" },
      { encabezado: "Entrante", campo: "cantidad_entrante", tipo: "cantidad" },
      { encabezado: "Excedente", campo: "excedente", tipo: "cantidad" },
    ],
  },
  {
    clave: "renglones_con_saldo",
    titulo: "Renglones con saldo",
    columnas: [
      INSUMO,
      { encabezado: "Saldo pendiente", campo: "saldo_pendiente", tipo: "cantidad" },
      { encabezado: "Fecha compromiso", campo: "fecha_compromiso", tipo: "fecha" },
    ],
  },
];

/** Rótulo de cada acción que el servidor puede ofrecer. Una clave que no está aquí se rotula con ella misma (D-7). */
export const ETIQUETAS_ACCION: Readonly<Partial<Record<string, string>>> = {
  VER_SOLICITUD_AUTORIZACION: "Ver solicitud de autorización",
  SOLICITAR_AUTORIZACION: "Solicitar autorización",
  CANCELAR_REQUISICION: "Cancelar la requisición",
  REPROGRAMAR: "Reprogramar",
  CONGELAR_LINEA_BASE: "Congelar la línea base",
  CAPTURAR_PRESUPUESTO_CONTROL: "Capturar el presupuesto de control",
  CONFIRMAR_REEMPLAZO: "Confirmar el reemplazo",
  CONFIRMAR_TOPE_SUPERIOR: "Confirmar el tope",
  VER_ENTRADA: "Ver la entrada",
  REINTENTAR: "Reintentar",
};
