"""Ajustes del servidor, leídos del entorno y validados antes de arrancar (TKT-057, fila 11; TKT-059, fila 8).

RNF-07: ningún secreto vive en el repositorio ni en un valor por omisión, así que la contraseña del
rol de aplicación no tiene omisión y su ausencia rechaza el arranque. CA-15 esc. 1 y 2: el servidor
solo recibe la contraseña de aplicación; las de migración y de lectura no tienen campo aquí. CA-14
y RNF-06: el origen del almacén se valida con el formato de un origen https sin ruta (http solo en
`localhost` y `127.0.0.1`, para MinIO local), para que la variable no pueda inyectar directivas en la
política de contenido ni abrirla a un origen sin cifrar.

TKT-059 (CA-2, CA-10): con base de datos, las cuatro variables obligatorias del almacén son
obligatorias también; el endpoint interno es opcional y admite un host no público (`http://minio:9000`).
Las vidas de las URL firmadas, el umbral de pendientes y los límites por categoría tienen omisión.

Un mapa explícito (`cargar_ajustes(mapa)`) no lee `os.environ`: así las pruebas no dependen del
entorno del proceso. `cargar_ajustes(None)` sí lee el entorno del proceso.
"""

import os
import re
from collections.abc import Iterable, Mapping
from typing import Any

from pydantic import SecretStr, ValidationError, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from herramientas.conexion import variables_de_base_presentes

PREFIJO_VARIABLES = "CIMENTA_"
PATRON_ORIGEN = (
    r"https://[A-Za-z0-9.-]+(:[0-9]{1,5})?|http://(localhost|127\.0\.0\.1)(:[0-9]{1,5})?"
)
PATRON_ENDPOINT = r"https?://[A-Za-z0-9.-]+(:[0-9]{1,5})?"
PATRON_BUCKET = r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]"


class ConfiguracionInvalida(RuntimeError):
    """El arranque se detiene: falta una variable obligatoria o una tiene un valor inválido.

    El mensaje nombra las variables afectadas y nunca sus valores (RNF-07).
    """


class AjustesServidor(BaseSettings):
    """Ajustes del proceso. Cada campo se lee de la variable `CIMENTA_` + su nombre en mayúsculas.

    RNF-07: `SecretStr` oculta la contraseña en `repr`, en `str` y en `model_dump_json`.
    """

    model_config = SettingsConfigDict(
        env_prefix=PREFIJO_VARIABLES,
        env_ignore_empty=True,
        extra="ignore",
        hide_input_in_errors=True,
    )

    db_contrasena_aplicacion: SecretStr
    almacen_origen: str | None = None
    trabajos_intervalo_latido: int = 5
    trabajos_umbral_vencimiento: int = 60
    almacen_endpoint: str | None = None
    almacen_bucket: str | None = None
    almacen_clave_acceso: str | None = None
    almacen_clave_secreta: SecretStr | None = None
    archivos_vida_url_subida: int = 900
    archivos_vida_url_lectura: int = 300
    archivos_umbral_pendiente: int = 86400
    archivos_limite_imagen_bytes: int = 15728640
    archivos_limite_video_bytes: int = 52428800
    archivos_limite_documento_bytes: int = 26214400

    @field_validator("trabajos_intervalo_latido")
    @classmethod
    def validar_intervalo_latido(cls, valor: int) -> int:
        """TKT-015b · PA-15.4 — el latido se emite cada 1 a 60 segundos."""
        if 1 <= valor <= 60:
            return valor
        raise ValueError("debe estar entre 1 y 60 segundos")

    @field_validator("trabajos_umbral_vencimiento")
    @classmethod
    def validar_umbral_vencimiento(cls, valor: int, info: ValidationInfo) -> int:
        """TKT-015b · PA-15.4 — el umbral es al menos tres intervalos de latido.

        Tolerante: si el intervalo ya falló, no está en `info.data` y no se compara, para que el
        error nombre solo la variable del intervalo.
        """
        intervalo = info.data.get("trabajos_intervalo_latido")
        if intervalo is None or valor >= 3 * intervalo:
            return valor
        raise ValueError("debe ser al menos tres veces el intervalo de latido")

    @field_validator("almacen_origen")
    @classmethod
    def validar_almacen_origen(cls, valor: str | None) -> str | None:
        """CA-14 · RNF-06 — solo un origen https sin ruta (http solo en localhost), para no inyectar la política."""
        if valor is None or re.fullmatch(PATRON_ORIGEN, valor):
            return valor
        raise ValueError("debe ser un origen https sin ruta (http solo en localhost)")

    @field_validator("almacen_endpoint")
    @classmethod
    def validar_almacen_endpoint(cls, valor: str | None) -> str | None:
        """TKT-059 · CA-10 — el endpoint interno admite http o https y un host no público, sin ruta."""
        if valor is None or re.fullmatch(PATRON_ENDPOINT, valor):
            return valor
        raise ValueError("debe ser una URL http o https sin ruta")

    @field_validator("almacen_bucket")
    @classmethod
    def validar_almacen_bucket(cls, valor: str | None) -> str | None:
        """TKT-059 · CA-2 — el nombre de bucket sigue la forma de S3 (minúsculas, dígitos, puntos y guiones)."""
        if valor is None or re.fullmatch(PATRON_BUCKET, valor):
            return valor
        raise ValueError("debe ser un nombre de bucket válido")

    @field_validator("archivos_vida_url_subida", "archivos_vida_url_lectura")
    @classmethod
    def validar_vida_url(cls, valor: int) -> int:
        """TKT-059 · CA-2 — una URL firmada vive de 1 a 60 minutos."""
        if 60 <= valor <= 3600:
            return valor
        raise ValueError("debe estar entre 60 y 3600 segundos")

    @field_validator("archivos_umbral_pendiente")
    @classmethod
    def validar_umbral_pendiente(cls, valor: int, info: ValidationInfo) -> int:
        """TKT-059 · CA-2 — el umbral supera la vida de la URL de subida (validador tolerante, como el de latido)."""
        vida = info.data.get("archivos_vida_url_subida")
        if vida is None or valor > vida:
            return valor
        raise ValueError("debe ser mayor que la vida de la URL de subida")

    @field_validator(
        "archivos_limite_imagen_bytes",
        "archivos_limite_video_bytes",
        "archivos_limite_documento_bytes",
    )
    @classmethod
    def validar_limite_bytes(cls, valor: int) -> int:
        """TKT-059 · CA-2 — un límite por categoría es de al menos un byte."""
        if valor >= 1:
            return valor
        raise ValueError("debe ser al menos 1")

    def almacen_obligatorio(self) -> dict[str, object | None]:
        """TKT-059 · CA-2 — las cuatro variables obligatorias del almacén, por su nombre de variable.

        Sin base no son obligatorias, pero el método devuelve igual sus valores: quien decide si se
        exigen es `_exigir_almacen_con_base`. Los valores pueden ser `None`; la clave secreta sigue
        siendo `SecretStr` (RNF-07).
        """
        return {
            "CIMENTA_ALMACEN_ORIGEN": self.almacen_origen,
            "CIMENTA_ALMACEN_BUCKET": self.almacen_bucket,
            "CIMENTA_ALMACEN_CLAVE_ACCESO": self.almacen_clave_acceso,
            "CIMENTA_ALMACEN_CLAVE_SECRETA": self.almacen_clave_secreta,
        }


class _AjustesDesdeMapa(AjustesServidor):
    """Ajustes construidos desde un mapa explícito: solo cuentan los argumentos, nunca `os.environ`."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings,)


def cargar_ajustes(entorno: Mapping[str, str] | None) -> AjustesServidor:
    """Carga los ajustes o detiene el arranque con `ConfiguracionInvalida` (CA-15, CA-16, CA-14, CA-2).

    Con `None` lee el entorno del proceso. Con un mapa, usa solo sus claves; una variable vacía
    cuenta como ausente (CA-16).
    """
    if entorno is None:
        try:
            # mypy exige el campo obligatorio en __init__; pydantic-settings lo toma del entorno.
            ajustes = AjustesServidor()  # type: ignore[call-arg]
        except ValidationError as error:
            raise ConfiguracionInvalida(_mensaje(error)) from None
        return _exigir_almacen_con_base(ajustes, os.environ)

    valores: dict[str, Any] = {}
    for campo in AjustesServidor.model_fields:
        valor = entorno.get(PREFIJO_VARIABLES + campo.upper())
        if valor:
            valores[campo] = valor
    try:
        ajustes = _AjustesDesdeMapa(**valores)
    except ValidationError as error:
        raise ConfiguracionInvalida(_mensaje(error)) from None
    return _exigir_almacen_con_base(ajustes, entorno)


def _exigir_almacen_con_base(
    ajustes: AjustesServidor, entorno_efectivo: Mapping[str, str]
) -> AjustesServidor:
    """TKT-059 · CA-2 — con las tres variables de base, las cuatro del almacén son obligatorias.

    Sin base no se exige nada (CA-R1): el arranque no toca el almacén. El error nombra las que faltan,
    ordenadas, y nunca sus valores.
    """
    if not variables_de_base_presentes(entorno_efectivo):
        return ajustes
    faltan = [nombre for nombre, valor in ajustes.almacen_obligatorio().items() if valor is None]
    if faltan:
        raise ConfiguracionInvalida(_mensaje_de_variables(faltan))
    return ajustes


def _mensaje_de_variables(variables: Iterable[str]) -> str:
    """Nombra las variables afectadas, ordenadas y sin repetir; nunca sus valores (RNF-07)."""
    return (
        f"Configuración incompleta o inválida: {', '.join(sorted(set(variables)))}. "
        "Defínelas en el entorno; las claves están en .env.example."
    )


def _mensaje(error: ValidationError) -> str:
    """Nombra las variables afectadas, ordenadas, y nunca sus valores.

    `error.errors()` conserva el valor de entrada (`input`): aquí solo se lee `loc`.
    """
    return _mensaje_de_variables(
        PREFIJO_VARIABLES + str(e["loc"][0]).upper() for e in error.errors()
    )
