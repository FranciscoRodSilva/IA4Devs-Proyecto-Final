# Caddy 2.11.7 con proveedor DNS DuckDNS para ACME DNS-01 (TKT-070 · Alternativa A).
# Guía: docs/despliegue-prueba-vps.md

FROM caddy:2.11.7-builder AS builder

RUN xcaddy build \
	--with github.com/caddy-dns/duckdns@v0.4.0 \
	--output /usr/bin/caddy

FROM caddy:2.11.7

COPY --from=builder /usr/bin/caddy /usr/bin/caddy
