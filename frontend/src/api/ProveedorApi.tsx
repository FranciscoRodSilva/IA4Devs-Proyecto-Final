import { createContext, type ReactNode, useContext } from "react";
import type { ClienteApi } from "@/api/cliente";

const ContextoApi = createContext<ClienteApi | null>(null);

export function ProveedorApi({ api, children }: { api: ClienteApi; children: ReactNode }) {
  return <ContextoApi.Provider value={api}>{children}</ContextoApi.Provider>;
}

export function useApi(): ClienteApi {
  const api = useContext(ContextoApi);
  if (api === null) throw new Error("useApi fuera de ProveedorApi");
  return api;
}
