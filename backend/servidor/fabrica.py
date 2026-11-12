"""Fábrica de la aplicación FastAPI: raíz de composición (ADR-018, CA-12, CA-14).

Monta los enrutadores de `cimenta.<modulo>.api` y ningún módulo importa este paquete. Desde TKT-006
monta `cimenta.identidad.api.montaje`; desde TKT-017b también `cimenta.presupuesto.api.montaje`.
Desde TKT-015b también compone, por
`cimenta.presupuesto.interfaz` y `trabajos.barrido`, el barrido de las importaciones interrumpidas
y el ejecutor del análisis, en el `lifespan`: nada de `aplicacion/` ni de `infraestructura/` de
ningún módulo. Los manejadores de error se registran con `registrar_manejadores` (TKT-005, fila 6).
El motor del rol de aplicación es perezoso: construir la aplicación no exige variables de base ni
abre conexión. Sin variables de base el `lifespan` no barre ni crea el ejecutor (P16), de modo que
el servidor sigue arrancando sin base; con ellas, un barrido fallido impide arrancar (P11).

Desde TKT-059 fila 8 compone también el contexto de `cimenta.archivos.interfaz` en
`aplicacion.state.archivos`. El almacén de objetos es perezoso: construir la aplicación no crea el
cliente, y sin sus variables `almacen()` lanza `AlmacenNoConfigurado` (CA-2).
"""

import functools
import os
import sys
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import TextIO
from uuid import UUID

import structlog
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from pydantic import SecretStr
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

from cimenta.archivos.interfaz import (
    AlmacenNoConfigurado,
    AlmacenObjetos,
    ConfiguracionArchivos,
    LimitesArchivo,
    construir_contexto,
    crear_almacen_s3,
)
from cimenta.identidad.api.montaje import montar_identidad
from cimenta.presupuesto.api.montaje import montar_presupuesto
from cimenta.presupuesto.interfaz import (
    crear_ejecutor_analisis,
    definicion_barrido_importacion,
    leer_contenido_no_configurado,
)
from herramientas.conexion import crear_motor_aplicacion, variables_de_base_presentes
from servidor.ajustes import AjustesServidor, cargar_ajustes
from servidor.cabeceras import MiddlewareCabecerasSeguridad, cabeceras_de_seguridad
from servidor.correlacion import MiddlewareCorrelacion
from servidor.manejadores import registrar_manejadores
from servidor.registro import configurar_registro
from trabajos.barrido import barrer_todas


def _almacen_desde_ajustes(ajustes: AjustesServidor) -> AlmacenObjetos:
    """Crea el adaptador S3 con los ajustes (TKT-059, CA-2). Sin las cuatro obligatorias, no lo crea."""
    valores = ajustes.almacen_obligatorio()
    origen = valores["CIMENTA_ALMACEN_ORIGEN"]
    bucket = valores["CIMENTA_ALMACEN_BUCKET"]
    clave_acceso = valores["CIMENTA_ALMACEN_CLAVE_ACCESO"]
    clave_secreta = valores["CIMENTA_ALMACEN_CLAVE_SECRETA"]
    if not (
        isinstance(origen, str)
        and isinstance(bucket, str)
        and isinstance(clave_acceso, str)
        and isinstance(clave_secreta, SecretStr)
    ):
        raise AlmacenNoConfigurado("el almacén de objetos no está configurado")
    return crear_almacen_s3(
        endpoint=ajustes.almacen_endpoint,
        origen=origen,
        bucket=bucket,
        clave_acceso=clave_acceso,
        clave_secreta=clave_secreta.get_secret_value(),
    )


def crear_aplicacion(
    *,
    destino_registro: TextIO | None = None,
    motor: Engine | None = None,
    reloj: Callable[[], datetime] | None = None,
    entorno: Mapping[str, str] | None = None,
    leer_contenido_archivo: Callable[[UUID], bytes] | None = None,
    almacen: AlmacenObjetos | None = None,
) -> FastAPI:
    """CA-14: depuración desactivada, para que un error nunca devuelva una traza al cliente.

    CA-15 · RNF-07: los ajustes van primero. Sin la contraseña de aplicación no se configura el
    registro ni se construye ningún motor: la excepción `ConfiguracionInvalida` sale antes.

    TKT-015b: `leer_contenido_archivo` es el origen de los bytes de un archivo; sin él, el
    ejecutor usa `leer_contenido_no_configurado` hasta que TKT-059 conecte el almacén.

    TKT-059 fila 8: `almacen` inyecta el almacén (pruebas); sin él, el adaptador S3 se crea con los
    ajustes en la primera llamada, y solo si están sus cuatro variables.
    """
    ajustes = cargar_ajustes(entorno)
    entorno_efectivo = os.environ if entorno is None else entorno
    leer_contenido = (
        leer_contenido_archivo
        if leer_contenido_archivo is not None
        else leer_contenido_no_configurado
    )
    proveedor_motor: Callable[[], Engine] = (
        (lambda: motor)
        if motor is not None
        else functools.cache(
            functools.partial(
                crear_motor_aplicacion, ajustes.db_contrasena_aplicacion.get_secret_value()
            )
        )
    )
    proveedor_almacen: Callable[[], AlmacenObjetos] = (
        (lambda: almacen)
        if almacen is not None
        else functools.cache(functools.partial(_almacen_desde_ajustes, ajustes))
    )
    configuracion_archivos = ConfiguracionArchivos(
        vida_url_subida=timedelta(seconds=ajustes.archivos_vida_url_subida),
        vida_url_lectura=timedelta(seconds=ajustes.archivos_vida_url_lectura),
        umbral_pendiente=timedelta(seconds=ajustes.archivos_umbral_pendiente),
        limites=LimitesArchivo(
            imagen_bytes=ajustes.archivos_limite_imagen_bytes,
            video_bytes=ajustes.archivos_limite_video_bytes,
            documento_bytes=ajustes.archivos_limite_documento_bytes,
        ),
    )

    @asynccontextmanager
    async def _ciclo_de_vida(aplicacion: FastAPI) -> AsyncIterator[None]:
        """P13 · P16: única corrutina del backend; todo lo bloqueante va al grupo de hilos."""
        if motor is None and not variables_de_base_presentes(entorno_efectivo):
            structlog.get_logger("cimenta.servidor").warning(
                "trabajos_omitidos", motivo="sin variables de base"
            )
            aplicacion.state.ejecutor_analisis = None
            yield
            return

        fabrica_sesiones = sessionmaker(bind=proveedor_motor(), expire_on_commit=False)
        cuentas = await run_in_threadpool(
            barrer_todas,
            fabrica_sesiones,
            [
                definicion_barrido_importacion(
                    timedelta(seconds=ajustes.trabajos_umbral_vencimiento)
                )
            ],
        )
        structlog.get_logger("cimenta.servidor").info("barrido", cuentas=cuentas)
        ejecutor = crear_ejecutor_analisis(
            fabrica_sesiones,
            leer_contenido,
            timedelta(seconds=ajustes.trabajos_intervalo_latido),
        )
        aplicacion.state.ejecutor_analisis = ejecutor
        try:
            yield
        finally:
            await run_in_threadpool(ejecutor.cerrar)

    configurar_registro(destino_registro if destino_registro is not None else sys.stdout)
    aplicacion = FastAPI(title="CIMENTA", version="0.1.0", debug=False, lifespan=_ciclo_de_vida)
    registrar_manejadores(aplicacion)
    # RNF-05 · RNF-06: el último `add_middleware` es el más externo. Cabeceras se registra antes,
    # así que la correlación queda por fuera de ella.
    cabeceras = cabeceras_de_seguridad(ajustes.almacen_origen)
    aplicacion.state.cabeceras_seguridad = cabeceras
    aplicacion.add_middleware(MiddlewareCabecerasSeguridad, cabeceras=cabeceras)
    aplicacion.add_middleware(MiddlewareCorrelacion)
    montar_identidad(
        aplicacion,
        proveedor_motor=proveedor_motor,
        reloj=reloj,
        entorno=entorno_efectivo,
    )
    aplicacion.state.archivos = construir_contexto(
        proveedor_motor=proveedor_motor,
        proveedor_almacen=proveedor_almacen,
        configuracion=configuracion_archivos,
        reloj=reloj,
    )
    montar_presupuesto(aplicacion, proveedor_motor=proveedor_motor, reloj=reloj)
    return aplicacion
