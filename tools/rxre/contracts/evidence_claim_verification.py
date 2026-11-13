#!/usr/bin/env python3
"""RXRE-220 — Verificación de propiedad concreta de artefacto observado.

Clase acotada: propiedad técnica de un artefacto identificado por hash sha256,
verificable mediante evidencia existente en DB operativa y archivo real.

No modifica DB ni crea nuevos datos operativos; solo lee.
No es una generalización universal de verificación semántica.
"""
import hashlib, sqlite3, os
from typing import Dict, Any, Optional, List

DB_OP = "/home/lucas/Escritorio/rxre/.rxre/storage/rxre.sqlite3"


def _coincide_hash(registrado: str, real: str) -> bool:
    """Comparar hash registrado con archivo observado; tolera truncamiento."""
    if not registrado or not real:
        return False
    r = registrado.replace("sha256:", "").replace("...", "").strip()
    if len(r) == 64:
        return r == real
    return len(r) >= 8 and real.startswith(r)


def calcular_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(65536)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def resolver_evidence_ref(ref_id: str) -> bool:
    """Resolver un result_id existente en DB_OP (solo lectura)."""
    try:
        c = sqlite3.connect(DB_OP)
        row = c.execute("SELECT 1 FROM results WHERE result_id = ?", (ref_id,)).fetchone()
        c.close()
        return row is not None
    except Exception:
        return False


def verificar_propiedad_artefacto(
    artifact_path: str,
    claim_propiedad: Dict[str, Any],
    evidencia_refs: Optional[List[str]] = None,
    resolver_refs: Optional[callable] = None,
) -> Dict[str, Any]:
    """Verifica una propiedad técnica de un artefacto observado.

    claim_propiedad debe incluir al menos:
      - tipo: tipo de verificación (ej. "linea_contiene")
      - parametro: dict con datos específicos (ej. {"linea": 396, "texto_esperado": "..."})
    evidencia_refs: referencias a registros `results` que respaldan la observación.
    resolver_refs: callable(str)->bool; por defecto `resolver_evidence_ref`.

    Devuelve un dict con:
      - resultado: SUPPORTED / REFUTED / INSUFFICIENT / ERROR
      - integridad_evidencia: detalles del hash/procedencia del archivo
      - contenido_verificado: detalles del contenido comparado
      - procedencia: referencias operativas verificadas
      - motivo: explicación determinista
    """
    resolver = resolver_refs or resolver_evidence_ref
    refs = evidencia_refs or []

    # --- Verificación de referencias (procedencia operativa) ---
    refs_verificadas = []
    refs_faltantes = []
    for ref in refs:
        if resolver(ref):
            refs_verificadas.append(ref)
        else:
            refs_faltantes.append(ref)

    # Una referencia declarada pero no resoluble NO es evidencia: sin
    # procedencia verificable no se puede acreditar nada.
    if refs_faltantes:
        return {
            "resultado": "INSUFFICIENT",
            "motivo": "referencias de evidencia no resolubles: %s; sin procedencia verificable no se evalúa la propiedad" % refs_faltantes,
            "integridad_evidencia": {"archivo_existe": False, "archivo_lectura": False,
                                     "hash_sha256": None, "hash_coincide": False,
                                     "archivo_path": artifact_path,
                                     "procedencia": refs_verificadas},
            "contenido_verificado": {},
            "procedencia": refs_verificadas,
            "referencias_faltantes": refs_faltantes,
            "limitaciones": ["referencias de evidencia no verificables"],
        }

    # --- Verificación del archivo de artefacto ---
    integridad = {"archivo_existe": False, "archivo_lectura": False,
                  "hash_sha256": None, "hash_coincide": False,
                  "archivo_path": artifact_path, "procedencia": refs_verificadas}
    if not os.path.exists(artifact_path):
        return {
            "resultado": "INSUFFICIENT",
            "motivo": "archivo de evidencia no existe: %s; no se puede verificar propiedad sin evidencia observable" % artifact_path,
            "integridad_evidencia": integridad,
            "contenido_verificado": {},
            "procedencia": refs_verificadas,
            "referencias_faltantes": refs_faltantes,
            "limitaciones": ["evidencia observacional no disponible; referencia operativa ausente"],
        }

    integridad["archivo_existe"] = True
    integridad["archivo_lectura"] = os.access(artifact_path, os.R_OK)
    integridad["hash_sha256"] = calcular_sha256(artifact_path)
    # Buscar hash registrado en DB_OP para verificar coincidencia con evidencia operativa
    hash_registrado = None
    refs_con_hash = refs if refs else []
    for ref in refs_con_hash:
        c = sqlite3.connect(DB_OP)
        row = c.execute("SELECT raw_json FROM results WHERE result_id = ?", (ref,)).fetchone()
        c.close()
        if row and row[0]:
            import json
            try:
                meta = json.loads(row[0])
                hash_registrado = meta.get("hash", meta.get("artefacto_hash_sha256"))
                if hash_registrado:
                    break
            except Exception:
                pass
    integridad["hash_registrado_operativo"] = hash_registrado
    integridad["hash_coincide"] = _coincide_hash(hash_registrado, integridad["hash_sha256"])
    # Si la evidencia operativa registra un hash que no coincide con el
    # archivo real, la referencia operativa NO respalda este archivo
    # concreto (la evidencia podría ser de otro archivo o alterada).
    if hash_registrado is not None and not integridad["hash_coincide"]:
        return {
            "resultado": "INSUFFICIENT",
            "motivo": "hash registrado operativamente (%s...) no coincide con archivo observado (%s...); evidencia operativa no respalda este artefacto" % (str(hash_registrado)[:16], integridad["hash_sha256"][:16]),
            "integridad_evidencia": integridad,
            "contenido_verificado": {},
            "procedencia": refs_verificadas,
            "referencias_faltantes": refs_faltantes,
            "limitaciones": ["desajuste de integridad: archivo observado no coincide con registro operativo"],
        }

    # --- Verificación de la propiedad del contenido ---
    tipo = claim_propiedad.get("tipo")
    contenido = {"tipo_verificacion": tipo, "archivo_path": artifact_path,
                 "parametro": claim_propiedad.get("parametro", {}),
                 "resultado": None}

    if tipo in ("linea_contiene", "linea_igual"):
        linea_esp = claim_propiedad.get("parametro", {}).get("linea")
        texto_esp = claim_propiedad.get("parametro", {}).get("texto_esperado")
        if linea_esp is None or texto_esp is None:
            return {
                "resultado": "INSUFFICIENT",
                "motivo": "propiedad '%s' requiere linea y texto_esperado en parametro" % tipo,
                "integridad_evidencia": integridad,
                "contenido_verificado": contenido,
                "procedencia": refs_verificadas,
                "referencias_faltantes": refs_faltantes,
                "limitaciones": ["parametros incompletos para verificacion de contenido"],
            }
        try:
            with open(artifact_path, encoding="utf-8", errors="replace") as f:
                lineas = f.read().splitlines()
            contenido["lineas_totales"] = len(lineas)
            contenido["linea_esperada"] = linea_esp
            contenido["linea_encontrada"] = linea_esp if linea_esp <= len(lineas) else None
            if linea_esp > len(lineas):
                contenido["resultado"] = "INSUFFICIENT"
                contenido["motivo"] = "linea %d excede total de lineas (%d)" % (linea_esp, len(lineas))
            else:
                texto_real = lineas[linea_esp - 1]
                contenido["texto_real"] = texto_real
                contenido["texto_esperado"] = texto_esp
                if tipo == "linea_igual":
                    coincide = texto_real == texto_esp
                    semantica = "igualdad exacta de linea"
                else:
                    coincide = texto_esp in texto_real
                    semantica = "contenido de subcadena dentro de la linea"
                contenido["semantica"] = semantica
                contenido["texto_coincide"] = coincide
                if coincide:
                    contenido["resultado"] = "SUPPORTED"
                    contenido["motivo"] = "propiedad verificada por observacion directa (%s) en linea %d" % (semantica, linea_esp)
                else:
                    contenido["resultado"] = "REFUTED"
                    contenido["motivo"] = "propiedad refutada: linea %d presente pero no satisface la relacion (%s); evidencia observacional no respalda la afirmacion" % (linea_esp, semantica)
        except Exception as exc:
            contenido["resultado"] = "INSUFFICIENT"
            contenido["motivo"] = "error al leer archivo: %s" % str(exc)
    elif tipo == "archivo_contiene_texto":
        texto_esp = claim_propiedad.get("parametro", {}).get("texto_esperado")
        if texto_esp is None or not isinstance(texto_esp, str) or texto_esp == "":
            return {
                "resultado": "INSUFFICIENT",
                "motivo": "propiedad '%s' requiere texto_esperado (cadena no vacia) en parametro" % tipo,
                "integridad_evidencia": integridad,
                "contenido_verificado": contenido,
                "procedencia": refs_verificadas,
                "referencias_faltantes": refs_faltantes,
                "limitaciones": ["parametros incompletos para verificacion de contenido"],
            }
        try:
            with open(artifact_path, encoding="utf-8", errors="replace") as f:
                texto_total = f.read()
            contenido["texto_esperado"] = texto_esp
            contenido["texto_coincide"] = texto_esp in texto_total
            contenido["longitud_archivo"] = len(texto_total)
            contenido["semantica"] = "subcadena dentro del archivo completo"
            if contenido["texto_coincide"]:
                contenido["resultado"] = "SUPPORTED"
                contenido["motivo"] = "propiedad verificada: texto '%s...' encontrado en archivo (len=%d)" % (texto_esp[:24], contenido["longitud_archivo"])
            else:
                contenido["resultado"] = "REFUTED"
                contenido["motivo"] = "propiedad refutada: texto '%s...' no presente en archivo (len=%d)" % (texto_esp[:24], contenido["longitud_archivo"])
        except Exception as exc:
            contenido["resultado"] = "INSUFFICIENT"
            contenido["motivo"] = "error al leer archivo: %s" % str(exc)
    else:
        # Tipo de verificacion no reconocido para esta clase acotada.
        contenido["resultado"] = "INSUFFICIENT"
        contenido["motivo"] = "tipo de verificacion '%s' no implementado en clase acotada; requiere extension de contrato" % tipo

    # --- Resultado final ---
    resultado = contenido.get("resultado") or "INSUFFICIENT"
    return {
        "resultado": resultado,
        "motivo": contenido.get("motivo", ""),
        "integridad_evidencia": integridad,
        "contenido_verificado": contenido,
        "procedencia": refs_verificadas,
        "referencias_faltantes": refs_faltantes,
        "limitaciones": ["clase acotada: solo verificacion de propiedad tecnica de artefacto por contenido/identidad; no generaliza a afirmaciones semanticas universales"],
    }
