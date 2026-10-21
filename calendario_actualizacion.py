
"""Calendario de actualización mensual y reintentos."""

import calendar
import datetime as dt


def mes_despues(fecha):
    anio = fecha.year + (fecha.month == 12)
    mes = fecha.month % 12 + 1
    dia = min(fecha.day, calendar.monthrange(anio, mes)[1])
    return dt.date(anio, mes, dia)


def inicial():
    return {
        "version": 1,
        "ultima_actualizacion_datos": "2026-10-09",
        "origen_fecha": "carga inicial",
        "tareas": {},
    }


def agregar(estado, tipo, fecha, parametro=None):
    referencia = parametro or (
        str(fecha.year)
        if tipo == "renuncias"
        else fecha.isoformat()
    )

    if tipo == "mensual":
        periodo = (
            dt.date.fromisoformat(referencia).replace(day=1)
            - dt.timedelta(days=1)
        ).strftime("%Y-%m")
    elif tipo == "renuncias":
        periodo = referencia
    else:
        periodo = fecha.strftime("%Y-%m")

    clave = tipo + ":" + periodo

    if clave not in estado["tareas"]:
        estado["tareas"][clave] = {
            "tipo": tipo,
            "periodo": periodo,
            "referencia": referencia,
            "inicio": fecha.isoformat(),
            "limite": mes_despues(fecha).isoformat(),
            "estado": "pendiente",
            "intentos": 0,
        }

    return estado["tareas"][clave]


def planificar(estado, hoy, modo="programado", parametro=None):
    if modo == "programado":
        if hoy.day >= 15:
            anterior = (
                hoy.replace(day=1) - dt.timedelta(days=1)
            ).strftime("%Y-%m")

            tarea = estado["tareas"].get("mensual:" + anterior)

            if tarea is None:
                agregar(estado, "mensual", hoy)
            elif tarea["estado"] == "agotado":
                tarea.update(
                    estado="pendiente",
                    limite=mes_despues(hoy).isoformat(),
                )

        if hoy.day == calendar.monthrange(
            hoy.year, hoy.month
        )[1]:
            agregar(estado, "recaudacion", hoy)

        if hoy.month == 7 and hoy.day == 1:
            agregar(estado, "renuncias", hoy)

    elif modo != "publicar":
        tarea = agregar(estado, modo, hoy, parametro)

        if tarea["estado"] != "pendiente":
            tarea.update(
                estado="pendiente",
                inicio=hoy.isoformat(),
                limite=mes_despues(hoy).isoformat(),
            )
            tarea.pop("ultimo_intento", None)

    pendientes = []

    for tarea in estado["tareas"].values():
        if tarea["estado"] != "pendiente":
            continue

        if hoy >= dt.date.fromisoformat(tarea["limite"]):
            tarea["estado"] = "agotado"
            continue

        if tarea.get("ultimo_intento", "")[:10] != hoy.isoformat():
            pendientes.append(tarea)

    return pendientes if modo != "publicar" else []


def registrar(estado, tarea, ahora, error=None):
    tarea["intentos"] += 1
    tarea["ultimo_intento"] = ahora.isoformat()

    if error:
        tarea["error"] = str(error)[:1500]
        tarea["estado"] = "pendiente"
    else:
        tarea["estado"] = "completado"
        tarea["ultimo_exito"] = ahora.isoformat()
        tarea.pop("error", None)

        estado["ultima_actualizacion_datos"] = ahora.isoformat()
        estado["origen_fecha"] = (
            "consulta automática validada"
        )
