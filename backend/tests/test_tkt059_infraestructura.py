"""Almacén de objetos en local y en CI (TKT-059, fila 1a): TC-45a, con CA-R1 y CA-13.

Sin Docker: se leen `compose.yaml`, `compose.almacen.yaml`, `.env.example` y `.github/workflows/ci.yml`,
todos versionados en el repositorio. Ningún test lee `.env`, que contiene valores reales.

Decisiones que ajustan `sdd/tickets/tkt-059/design.md`, tomadas por la persona dueña del proyecto y vigentes
desde esta fila (prevalecen sobre el texto del diseño donde difieran):

- Imagen de MinIO: `pgsty/minio:RELEASE.2026-08-04T00-00-00Z@sha256:b6bfe7239bfc83fb90d31612d9704d86039dd714f7904b3f1ad68f211e602372`. El fork comunitario
  sustituye a `minio/minio`, que ya no se descarga. La etiqueta va fija (nunca `latest`) y la imagen se
  fija además por digest: una etiqueta se puede mover en el registro, un digest no (seguridad F002).
- `compose.yaml` conserva solo `db`. El servicio `minio` va en `compose.almacen.yaml`, en la raíz, y se carga
  con `-f compose.yaml -f compose.almacen.yaml` solo cuando hace falta. El servicio **no lleva perfil**: el
  fichero separado sustituye al perfil `almacen` (`P-14`) y al experimento `E-4`, porque `up -d db` no carga
  ese fichero y, por tanto, no interpola sus variables.
- Las dos credenciales de MinIO se leen con `${…:?…}`, sin variante `:-`.
- CORS (`E-5`, caso c2): `MINIO_API_CORS_ALLOW_ORIGIN: ${CIMENTA_SPA_ORIGEN:-http://localhost:5173}` en el
  entorno de `minio`. No hay `aplicar_cors` en `herramientas/`.
- La URL de subida firma `x-amz-checksum-sha256` (`E-1`). Esta fila no lo usa; se anota para la fila 5.

Estructura: cada comprobación es una función pura `problemas_de_*` que devuelve la lista de desvíos, vacía si el
criterio se cumple. Los tests sobre los archivos reales afirman que la lista está vacía. Los controles, sobre
texto sintético, demuestran que la misma función da por buena la forma correcta y señala cada desvío con su
problema; así un verde sobre el archivo real no es una vacuidad.
"""

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

RAIZ = Path(__file__).resolve().parents[2]
COMPOSE = RAIZ / "compose.yaml"
COMPOSE_ALMACEN = RAIZ / "compose.almacen.yaml"
ENV_EJEMPLO = RAIZ / ".env.example"
CI = RAIZ / ".github" / "workflows" / "ci.yml"

DIGEST_FIJADO = "sha256:b6bfe7239bfc83fb90d31612d9704d86039dd714f7904b3f1ad68f211e602372"
IMAGEN_FIJADA = "pgsty/minio:RELEASE.2026-08-04T00-00-00Z@" + DIGEST_FIJADO
PATRON_RELEASE = r"\S+:RELEASE\.\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z@sha256:[0-9a-f]{64}"
CORS_ESPERADO = "${CIMENTA_SPA_ORIGEN:-http://localhost:5173}"
COMANDO_ESPERADO = "server /data --console-address :9001"
PUERTOS_ESPERADOS = ["9000", "9001"]
CREDENCIALES_DE_MINIO = {
    "MINIO_ROOT_USER": "CIMENTA_ALMACEN_CLAVE_ACCESO",
    "MINIO_ROOT_PASSWORD": "CIMENTA_ALMACEN_CLAVE_SECRETA",
}
ORIGEN_ALMACEN_LOCAL = "http://localhost:9000"
ORIGEN_SPA_LOCAL = "http://localhost:5173"
OMISIONES_ARCHIVOS = {
    "CIMENTA_ARCHIVOS_VIDA_URL_SUBIDA": "900",
    "CIMENTA_ARCHIVOS_VIDA_URL_LECTURA": "300",
    "CIMENTA_ARCHIVOS_UMBRAL_PENDIENTE": "86400",
    "CIMENTA_ARCHIVOS_LIMITE_IMAGEN_BYTES": "15728640",
    "CIMENTA_ARCHIVOS_LIMITE_VIDEO_BYTES": "52428800",
    "CIMENTA_ARCHIVOS_LIMITE_DOCUMENTO_BYTES": "26214400",
}


def _texto(ruta: Path) -> str:
    assert ruta.exists(), f"falta {ruta.relative_to(RAIZ).as_posix()}"
    return ruta.read_text(encoding="utf-8")


def _mutar(texto: str, antes: str, despues: str) -> str:
    assert antes in texto, f"la mutación no encuentra «{antes}» en el texto sintético"
    return texto.replace(antes, despues, 1)


def _entorno_de(bruto: Any) -> dict[str, str]:
    """`environment:` en forma de mapa o de lista `CLAVE=valor`, como texto."""
    if isinstance(bruto, dict):
        return {str(clave): "" if valor is None else str(valor) for clave, valor in bruto.items()}
    if isinstance(bruto, list):
        pares = [str(linea).split("=", 1) for linea in bruto]
        return {par[0]: par[1] if len(par) > 1 else "" for par in pares}
    return {}


# ---------------------------------------------------------------------------------------------
# compose.almacen.yaml · servicio minio
# ---------------------------------------------------------------------------------------------


def problemas_de_compose_almacen(texto: str) -> list[str]:
    """TC-45a · fila 1a: el servicio `minio` de compose.almacen.yaml, con la forma decidida."""
    datos = yaml.safe_load(texto)
    servicios = datos.get("services") if isinstance(datos, dict) else None
    minio = servicios.get("minio") if isinstance(servicios, dict) else None
    if not isinstance(minio, dict):
        return ["compose.almacen.yaml no define el servicio minio"]

    problemas: list[str] = []
    imagen = minio.get("image")
    if not (isinstance(imagen, str) and re.fullmatch(PATRON_RELEASE, imagen)):
        problemas.append(
            f"la imagen de minio no está fijada con una etiqueta RELEASE y un digest sha256: {imagen}"
        )
    elif imagen != IMAGEN_FIJADA:
        problemas.append(f"la imagen de minio debe ser {IMAGEN_FIJADA}; es {imagen}")
    if "profiles" in minio:
        problemas.append("minio tiene perfil (profiles); debe arrancar con el fichero, sin perfil")

    puertos = minio.get("ports") or []
    for puerto in puertos:
        if not (isinstance(puerto, str) and re.fullmatch(r"127\.0\.0\.1:\d+:\d+", puerto)):
            problemas.append(f"el puerto {puerto} no se publica solo en 127.0.0.1")
    publicados = sorted(str(puerto).split(":")[-1] for puerto in puertos)
    if publicados != PUERTOS_ESPERADOS:
        problemas.append(f"minio debe publicar 9000 y 9001; publica {publicados}")

    entorno = _entorno_de(minio.get("environment"))
    for clave, variable in CREDENCIALES_DE_MINIO.items():
        if not re.fullmatch(r"\$\{" + variable + r":\?[^}]+\}", entorno.get(clave, "")):
            problemas.append(f"{clave} debe leer su credencial con :? y sin valor por omisión")
    if entorno.get("MINIO_API_CORS_ALLOW_ORIGIN") != CORS_ESPERADO:
        problemas.append(f"MINIO_API_CORS_ALLOW_ORIGIN debe valer {CORS_ESPERADO}")

    comando = minio.get("command")
    texto_comando = " ".join(map(str, comando)) if isinstance(comando, list) else str(comando)
    if texto_comando != COMANDO_ESPERADO:
        problemas.append(f"minio arranca con «{texto_comando}»; debe ser «{COMANDO_ESPERADO}»")

    if "minio_datos:/data" not in (minio.get("volumes") or []):
        problemas.append("minio no monta minio_datos en /data")
    if "minio_datos" not in (datos.get("volumes") or {}):
        problemas.append("minio_datos no está declarado en volumes:")

    salud = minio.get("healthcheck")
    prueba = salud.get("test") if isinstance(salud, dict) else None
    if prueba not in (["CMD", "mc", "ready", "local"], ["CMD-SHELL", "mc ready local"]):
        problemas.append("el healthcheck no ejecuta mc ready local")
    return problemas


def problemas_de_compose_base(texto: str) -> list[str]:
    """TC-45a · fila 1a: compose.yaml sigue sin minio y con una sola imagen de PostgreSQL."""
    datos = yaml.safe_load(texto)
    if not isinstance(datos, dict):
        return ["compose.yaml no es un mapa YAML"]

    problemas: list[str] = []
    for nombre, servicio in (datos.get("services") or {}).items():
        imagen = servicio.get("image", "") if isinstance(servicio, dict) else ""
        if "minio" in str(nombre).lower() or "minio" in str(imagen).lower():
            problemas.append(f"compose.yaml define minio ({nombre}); va en compose.almacen.yaml")
    if "minio_datos" in (datos.get("volumes") or {}):
        problemas.append("compose.yaml declara el volumen minio_datos; va en compose.almacen.yaml")

    imagenes = re.findall(r"^\s*image:\s*(postgres:\S+)\s*$", texto, flags=re.MULTILINE)
    if len(imagenes) != 1:
        problemas.append(
            "compose.yaml debe declarar exactamente una imagen postgres:<etiqueta>, "
            f"y declara {len(imagenes)}"
        )
    return problemas


# ---------------------------------------------------------------------------------------------
# .env.example · sección del almacén
# ---------------------------------------------------------------------------------------------


def _claves_activas(texto: str) -> dict[str, str]:
    """`CLAVE=valor` de las líneas no comentadas, sin el comentario al final de línea."""
    pares: dict[str, str] = {}
    for linea in texto.splitlines():
        contenido = linea.strip()
        if not contenido or contenido.startswith("#") or "=" not in contenido:
            continue
        clave, valor = contenido.split("=", 1)
        pares[clave.strip()] = re.split(r"\s+#", valor, maxsplit=1)[0].strip()
    return pares


def problemas_de_env_example_almacen(texto: str) -> list[str]:
    """TC-45a · fila 1a: las claves del almacén activas, la secreta vacía, el endpoint y los límites comentados."""
    problemas: list[str] = []
    activas = _claves_activas(texto)

    for clave in ("CIMENTA_ALMACEN_BUCKET", "CIMENTA_ALMACEN_CLAVE_ACCESO"):
        if not activas.get(clave):
            problemas.append(f"falta {clave} activa con valor")
    origen = activas.get("CIMENTA_ALMACEN_ORIGEN")
    if not origen:
        problemas.append("falta CIMENTA_ALMACEN_ORIGEN activa con valor")
    elif origen != ORIGEN_ALMACEN_LOCAL:
        problemas.append(
            f"CIMENTA_ALMACEN_ORIGEN debe ser {ORIGEN_ALMACEN_LOCAL}, el puerto que publica minio"
        )

    if "CIMENTA_ALMACEN_CLAVE_SECRETA" not in activas:
        problemas.append("falta CIMENTA_ALMACEN_CLAVE_SECRETA activa y vacía")
    elif activas["CIMENTA_ALMACEN_CLAVE_SECRETA"] != "":
        problemas.append("CIMENTA_ALMACEN_CLAVE_SECRETA lleva valor")

    if activas.get("CIMENTA_SPA_ORIGEN") != ORIGEN_SPA_LOCAL:
        problemas.append(f"falta CIMENTA_SPA_ORIGEN activa con {ORIGEN_SPA_LOCAL}")

    if "CIMENTA_ALMACEN_ENDPOINT" in activas:
        problemas.append("CIMENTA_ALMACEN_ENDPOINT está activa; debe ir comentada")
    elif not re.search(r"^\s*#\s*CIMENTA_ALMACEN_ENDPOINT=", texto, flags=re.MULTILINE):
        problemas.append("no documenta CIMENTA_ALMACEN_ENDPOINT (comentada)")

    for clave, omision in OMISIONES_ARCHIVOS.items():
        if clave in activas:
            problemas.append(f"{clave} está activa; debe ir comentada")
        elif not re.search(rf"^\s*#\s*{clave}={omision}(?!\d)", texto, flags=re.MULTILINE):
            problemas.append(f"no documenta {clave} comentada con su omisión {omision}")
    return problemas


# ---------------------------------------------------------------------------------------------
# ci.yml · trabajo humo, paso «Preparar el entorno…»
# ---------------------------------------------------------------------------------------------


def _run(paso: dict[str, Any]) -> str:
    return str(paso.get("run", ""))


def problemas_de_humo_almacen(texto: str) -> list[str]:
    """TC-45a · fila 1a: el paso «Preparar el entorno…» de humo excluye la clave del almacén y la genera antes de levantar la base."""
    flujo = yaml.safe_load(texto)
    try:
        pasos = list(flujo["jobs"]["humo"]["steps"])
    except (KeyError, TypeError):
        return ["falta el trabajo humo con sus pasos"]

    indice = next(
        (
            i
            for i, paso in enumerate(pasos)
            if str(paso.get("name", "")).startswith("Preparar el entorno")
        ),
        None,
    )
    if indice is None:
        return ["falta el paso «Preparar el entorno…» en humo"]
    run = _run(pasos[indice])

    problemas: list[str] = []
    if not re.search(
        r"grep\s+-v\b[^\n]*['\"]?\^CIMENTA_ALMACEN_CLAVE_SECRETA=['\"]?[^\n]*\.env\.example\s*>\s*\.env",
        run,
    ):
        problemas.append("la copia de .env.example no excluye CIMENTA_ALMACEN_CLAVE_SECRETA")

    if not re.search(
        r"CIMENTA_ALMACEN_CLAVE_SECRETA=\$\(openssl rand -hex \d+\)[^\n]*>>\s*\.env\b", run
    ):
        problemas.append(
            "ningún paso genera CIMENTA_ALMACEN_CLAVE_SECRETA con openssl rand -hex y la escribe en .env"
        )
    else:
        levantar = next(
            (i for i, paso in enumerate(pasos) if "docker compose up" in _run(paso)), None
        )
        if levantar is None:
            problemas.append("ningún paso levanta la base con docker compose up")
        elif indice >= levantar:
            problemas.append("la clave del almacén se genera después de docker compose up")

    for asignacion in re.finditer(r"CIMENTA_ALMACEN_CLAVE_SECRETA=([^\s'\"$][^\s'\"]*)", run):
        problemas.append(f"valor literal para CIMENTA_ALMACEN_CLAVE_SECRETA: {asignacion.group(0)}")

    ambitos = [flujo["jobs"]["humo"], *pasos]
    for ambito in ambitos:
        entorno = ambito.get("env") or {}
        if "CIMENTA_ALMACEN_CLAVE_SECRETA" in entorno:
            problemas.append("CIMENTA_ALMACEN_CLAVE_SECRETA fijada en env con un valor literal")
    return problemas


# ---------------------------------------------------------------------------------------------
# Textos sintéticos de control: la forma correcta de cada archivo
# ---------------------------------------------------------------------------------------------

COMPOSE_ALMACEN_VALIDO = """\
services:
  minio:
    image: pgsty/minio:RELEASE.2026-08-04T00-00-00Z@sha256:b6bfe7239bfc83fb90d31612d9704d86039dd714f7904b3f1ad68f211e602372
    command: ["server", "/data", "--console-address", ":9001"]
    environment:
      MINIO_ROOT_USER: ${CIMENTA_ALMACEN_CLAVE_ACCESO:?define CIMENTA_ALMACEN_CLAVE_ACCESO en .env}
      MINIO_ROOT_PASSWORD: ${CIMENTA_ALMACEN_CLAVE_SECRETA:?define CIMENTA_ALMACEN_CLAVE_SECRETA en .env}
      MINIO_API_CORS_ALLOW_ORIGIN: ${CIMENTA_SPA_ORIGEN:-http://localhost:5173}
    ports:
      - "127.0.0.1:9000:9000"
      - "127.0.0.1:9001:9001"
    volumes:
      - minio_datos:/data
    healthcheck:
      test: ["CMD", "mc", "ready", "local"]
      interval: 5s
      timeout: 3s
      retries: 12

volumes:
  minio_datos:
"""

COMPOSE_BASE_VALIDO = """\
name: cimenta

services:
  db:
    image: postgres:18.6
    ports:
      - "127.0.0.1:${CIMENTA_DB_PUERTO:-5432}:5432"

volumes:
  pg_datos:
"""

ENV_ALMACEN_VALIDO = """\
CIMENTA_ALMACEN_ORIGEN=http://localhost:9000
CIMENTA_ALMACEN_BUCKET=cimenta
CIMENTA_ALMACEN_CLAVE_ACCESO=cimenta-local
CIMENTA_ALMACEN_CLAVE_SECRETA=
CIMENTA_SPA_ORIGEN=http://localhost:5173
# CIMENTA_ALMACEN_ENDPOINT=   # sin valor: vale CIMENTA_ALMACEN_ORIGEN
# CIMENTA_ARCHIVOS_VIDA_URL_SUBIDA=900
# CIMENTA_ARCHIVOS_VIDA_URL_LECTURA=300
# CIMENTA_ARCHIVOS_UMBRAL_PENDIENTE=86400
# CIMENTA_ARCHIVOS_LIMITE_IMAGEN_BYTES=15728640
# CIMENTA_ARCHIVOS_LIMITE_VIDEO_BYTES=52428800
# CIMENTA_ARCHIVOS_LIMITE_DOCUMENTO_BYTES=26214400
"""

CABECERA_HUMO = """\
jobs:
  humo:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@abc
"""

PASO_PREPARAR = """\
      - name: Preparar el entorno con contraseñas de prueba generadas
        run: |
          grep -v -e '^CIMENTA_DB_CONTRASENA_' -e '^CIMENTA_ALMACEN_CLAVE_SECRETA=' .env.example > .env
          for rol in MIGRACION APLICACION LECTURA; do
            echo "CIMENTA_DB_CONTRASENA_${rol}=$(openssl rand -hex 24)" >> .env
          done
          echo "CIMENTA_ALMACEN_CLAVE_SECRETA=$(openssl rand -hex 24)" >> .env
"""

PASO_LEVANTAR = """\
      - name: Levantar PostgreSQL
        run: docker compose up -d --wait db
"""

HUMO_VALIDO = CABECERA_HUMO + PASO_PREPARAR + PASO_LEVANTAR


# ---------------------------------------------------------------------------------------------
# Casos reales: los archivos del repositorio
# ---------------------------------------------------------------------------------------------


def test_tkt059_car1_compose_con_minio() -> None:
    """TC-45a · CA-13 · fila 1a — compose.almacen.yaml define minio con la imagen fijada, sin perfil, puertos solo en 127.0.0.1, volumen declarado, credenciales con :?, CORS y healthcheck."""
    texto = _texto(COMPOSE_ALMACEN)

    assert problemas_de_compose_almacen(texto) == []
    assert yaml.safe_load(texto)["services"]["minio"]["image"] == IMAGEN_FIJADA


def test_tkt059_car1_compose_base_sin_minio() -> None:
    """TC-45a · CA-R1 · fila 1a — compose.yaml sigue solo con db y con una sola imagen de PostgreSQL. Guarda de un estado que ya se cumple: su verde es esperado."""
    assert problemas_de_compose_base(_texto(COMPOSE)) == []


def test_tkt059_car1_env_example_seccion_del_almacen() -> None:
    """TC-45a · CA-R1 · fila 1a — .env.example trae activas las claves del almacén, la secreta vacía, la SPA y los límites comentados."""
    assert problemas_de_env_example_almacen(_texto(ENV_EJEMPLO)) == []


def test_tkt059_car1_humo_genera_la_clave_del_almacen() -> None:
    """TC-45a · CA-13 · fila 1a — humo excluye CIMENTA_ALMACEN_CLAVE_SECRETA de la copia y la genera con openssl rand antes de docker compose up."""
    assert problemas_de_humo_almacen(_texto(CI)) == []


# ---------------------------------------------------------------------------------------------
# Controles: cada desvío se señala con su problema, y la forma correcta pasa
# ---------------------------------------------------------------------------------------------

CASOS_COMPOSE = [
    pytest.param(
        lambda t: _mutar(t, IMAGEN_FIJADA, "pgsty/minio:latest"),
        [
            "la imagen de minio no está fijada con una etiqueta RELEASE y un digest sha256: "
            "pgsty/minio:latest"
        ],
        id="imagen_latest",
    ),
    pytest.param(
        lambda t: _mutar(t, "@" + DIGEST_FIJADO, ""),
        [
            "la imagen de minio no está fijada con una etiqueta RELEASE y un digest sha256: "
            "pgsty/minio:RELEASE.2026-08-04T00-00-00Z"
        ],
        id="imagen_sin_digest",
    ),
    pytest.param(
        lambda t: _mutar(t, DIGEST_FIJADO, "sha256:" + "0" * 64),
        [
            f"la imagen de minio debe ser {IMAGEN_FIJADA}; "
            "es pgsty/minio:RELEASE.2026-08-04T00-00-00Z@sha256:" + "0" * 64
        ],
        id="imagen_con_digest_distinto",
    ),
    pytest.param(
        lambda t: _mutar(
            t,
            "    command:",
            '    profiles: ["almacen"]\n    command:',
        ),
        ["minio tiene perfil (profiles); debe arrancar con el fichero, sin perfil"],
        id="con_perfil",
    ),
    pytest.param(
        lambda t: _mutar(
            t,
            "MINIO_ROOT_PASSWORD: ${CIMENTA_ALMACEN_CLAVE_SECRETA:?",
            "MINIO_ROOT_PASSWORD: ${CIMENTA_ALMACEN_CLAVE_SECRETA:-",
        ),
        ["MINIO_ROOT_PASSWORD debe leer su credencial con :? y sin valor por omisión"],
        id="credencial_con_dos_puntos_menos",
    ),
    pytest.param(
        lambda t: _mutar(
            t,
            "MINIO_ROOT_USER: ${CIMENTA_ALMACEN_CLAVE_ACCESO:?define CIMENTA_ALMACEN_CLAVE_ACCESO en .env}",
            "MINIO_ROOT_USER: cimenta-local",
        ),
        ["MINIO_ROOT_USER debe leer su credencial con :? y sin valor por omisión"],
        id="usuario_literal",
    ),
    pytest.param(
        lambda t: _mutar(t, '"127.0.0.1:9000:9000"', '"9000:9000"'),
        ["el puerto 9000:9000 no se publica solo en 127.0.0.1"],
        id="puerto_sin_127_0_0_1",
    ),
    pytest.param(
        lambda t: _mutar(
            t,
            "      MINIO_API_CORS_ALLOW_ORIGIN: ${CIMENTA_SPA_ORIGEN:-http://localhost:5173}\n",
            "",
        ),
        ["MINIO_API_CORS_ALLOW_ORIGIN debe valer ${CIMENTA_SPA_ORIGEN:-http://localhost:5173}"],
        id="cors_ausente",
    ),
    pytest.param(
        lambda t: _mutar(t, "\nvolumes:\n  minio_datos:\n", "\n"),
        ["minio_datos no está declarado en volumes:"],
        id="volumen_sin_declarar",
    ),
    pytest.param(
        lambda t: _mutar(t, ':9001"]', ':9002"]'),
        [
            "minio arranca con «server /data --console-address :9002»; "
            "debe ser «server /data --console-address :9001»"
        ],
        id="comando_distinto",
    ),
    pytest.param(
        lambda t: _mutar(
            t,
            'test: ["CMD", "mc", "ready", "local"]',
            'test: ["CMD", "curl", "-f", "http://localhost:9000/minio/health/live"]',
        ),
        ["el healthcheck no ejecuta mc ready local"],
        id="healthcheck_distinto",
    ),
]

CASOS_ENV = [
    pytest.param(
        lambda t: _mutar(
            t, "CIMENTA_ALMACEN_CLAVE_SECRETA=\n", "CIMENTA_ALMACEN_CLAVE_SECRETA=abcdef\n"
        ),
        ["CIMENTA_ALMACEN_CLAVE_SECRETA lleva valor"],
        id="secreta_con_valor",
    ),
    pytest.param(
        lambda t: _mutar(
            t,
            "# CIMENTA_ALMACEN_ENDPOINT=   # sin valor: vale CIMENTA_ALMACEN_ORIGEN",
            "CIMENTA_ALMACEN_ENDPOINT=http://minio:9000",
        ),
        ["CIMENTA_ALMACEN_ENDPOINT está activa; debe ir comentada"],
        id="endpoint_activo",
    ),
    pytest.param(
        lambda t: _mutar(
            t,
            "# CIMENTA_ARCHIVOS_LIMITE_VIDEO_BYTES=52428800",
            "CIMENTA_ARCHIVOS_LIMITE_VIDEO_BYTES=52428800",
        ),
        ["CIMENTA_ARCHIVOS_LIMITE_VIDEO_BYTES está activa; debe ir comentada"],
        id="limite_archivos_activo",
    ),
    pytest.param(
        lambda t: _mutar(
            t,
            "CIMENTA_SPA_ORIGEN=http://localhost:5173",
            "# CIMENTA_SPA_ORIGEN=http://localhost:5173",
        ),
        ["falta CIMENTA_SPA_ORIGEN activa con http://localhost:5173"],
        id="spa_comentada",
    ),
    pytest.param(
        lambda t: _mutar(
            t,
            "CIMENTA_ALMACEN_ORIGEN=http://localhost:9000",
            "CIMENTA_ALMACEN_ORIGEN=http://localhost:9100",
        ),
        ["CIMENTA_ALMACEN_ORIGEN debe ser http://localhost:9000, el puerto que publica minio"],
        id="origen_en_otro_puerto",
    ),
    pytest.param(
        lambda t: _mutar(t, "CIMENTA_ALMACEN_BUCKET=cimenta", "CIMENTA_ALMACEN_BUCKET="),
        ["falta CIMENTA_ALMACEN_BUCKET activa con valor"],
        id="bucket_vacio",
    ),
]

CASOS_HUMO = [
    pytest.param(
        lambda t: _mutar(t, " -e '^CIMENTA_ALMACEN_CLAVE_SECRETA='", ""),
        ["la copia de .env.example no excluye CIMENTA_ALMACEN_CLAVE_SECRETA"],
        id="copia_sin_exclusion",
    ),
    pytest.param(
        lambda t: _mutar(
            t,
            '          echo "CIMENTA_ALMACEN_CLAVE_SECRETA=$(openssl rand -hex 24)" >> .env\n',
            "",
        ),
        [
            "ningún paso genera CIMENTA_ALMACEN_CLAVE_SECRETA con openssl rand -hex y la escribe en .env"
        ],
        id="ci_sin_generar",
    ),
    pytest.param(
        lambda t: _mutar(
            t,
            'CIMENTA_ALMACEN_CLAVE_SECRETA=$(openssl rand -hex 24)"',
            'CIMENTA_ALMACEN_CLAVE_SECRETA=hunter2"',
        ),
        [
            "ningún paso genera CIMENTA_ALMACEN_CLAVE_SECRETA con openssl rand -hex y la escribe en .env",
            "valor literal para CIMENTA_ALMACEN_CLAVE_SECRETA: CIMENTA_ALMACEN_CLAVE_SECRETA=hunter2",
        ],
        id="secreta_literal",
    ),
    pytest.param(
        lambda t: _mutar(
            t,
            "    runs-on: ubuntu-24.04\n",
            "    runs-on: ubuntu-24.04\n    env:\n      CIMENTA_ALMACEN_CLAVE_SECRETA: abc\n",
        ),
        ["CIMENTA_ALMACEN_CLAVE_SECRETA fijada en env con un valor literal"],
        id="secreta_en_env_del_trabajo",
    ),
]


@pytest.mark.parametrize(("mutar", "esperado"), CASOS_COMPOSE)
def test_tkt059_car1_control_compose_detecta_el_desvio(
    mutar: Callable[[str], str], esperado: list[str]
) -> None:
    """TC-45a · control · CA-13 — la forma correcta de compose.almacen.yaml pasa; cada desvío se señala con su problema."""
    assert problemas_de_compose_almacen(COMPOSE_ALMACEN_VALIDO) == []
    assert problemas_de_compose_almacen(mutar(COMPOSE_ALMACEN_VALIDO)) == esperado


def test_tkt059_car1_control_compose_base_detecta_minio_y_dos_imagenes_postgres() -> None:
    """TC-45a · control · CA-R1 — compose.yaml con minio, o con dos imágenes de PostgreSQL, se señala."""
    assert problemas_de_compose_base(COMPOSE_BASE_VALIDO) == []

    con_minio = _mutar(
        COMPOSE_BASE_VALIDO,
        "\nvolumes:\n",
        "\n  minio:\n    image: pgsty/minio:RELEASE.2026-08-04T00-00-00Z\n\nvolumes:\n",
    )
    assert problemas_de_compose_base(con_minio) == [
        "compose.yaml define minio (minio); va en compose.almacen.yaml"
    ]

    con_dos_postgres = _mutar(
        COMPOSE_BASE_VALIDO,
        "\nvolumes:\n",
        "\n  copia:\n    image: postgres:17\n\nvolumes:\n",
    )
    assert problemas_de_compose_base(con_dos_postgres) == [
        "compose.yaml debe declarar exactamente una imagen postgres:<etiqueta>, y declara 2"
    ]


@pytest.mark.parametrize(("mutar", "esperado"), CASOS_ENV)
def test_tkt059_car1_control_env_example_detecta_el_desvio(
    mutar: Callable[[str], str], esperado: list[str]
) -> None:
    """TC-45a · control · CA-R1 — la sección correcta de .env.example pasa; cada desvío se señala con su problema."""
    assert problemas_de_env_example_almacen(ENV_ALMACEN_VALIDO) == []
    assert problemas_de_env_example_almacen(mutar(ENV_ALMACEN_VALIDO)) == esperado


@pytest.mark.parametrize(("mutar", "esperado"), CASOS_HUMO)
def test_tkt059_car1_control_humo_detecta_el_desvio(
    mutar: Callable[[str], str], esperado: list[str]
) -> None:
    """TC-45a · control · CA-13 — el paso correcto de humo pasa; cada desvío se señala con su problema."""
    assert problemas_de_humo_almacen(HUMO_VALIDO) == []
    assert problemas_de_humo_almacen(mutar(HUMO_VALIDO)) == esperado


def test_tkt059_car1_control_humo_detecta_la_generacion_despues_de_levantar() -> None:
    """TC-45a · control · CA-13 — generar la clave después de docker compose up se señala."""
    despues = CABECERA_HUMO + PASO_LEVANTAR + PASO_PREPARAR
    assert problemas_de_humo_almacen(despues) == [
        "la clave del almacén se genera después de docker compose up"
    ]
