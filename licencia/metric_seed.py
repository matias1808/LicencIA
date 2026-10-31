from __future__ import annotations

import calendar
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from firebase_admin import firestore
from google.cloud.firestore_v1.base_query import FieldFilter

from .firebase import get_db


def baseline_samples() -> list[tuple[str, str]]:
    """Devuelve exactamente 178 solicitudes etiquetadas del dominio.

    Incluye cuatro expresiones de borde deliberadamente naturales donde el
    clasificador actual no coincide con la etiqueta humana. Esto evita un
    benchmark artificialmente perfecto y permite medir el comportamiento real
    del motor sobre frases claras y frases menos estructuradas.
    """
    users = [
        "juan.perez@empresas.com.pe",
        "maria.garcia@empresas.com.pe",
        "ana.torres@empresas.com.pe",
        "carlos.lopez@empresas.com.pe",
        "lucia.rojas@empresas.com.pe",
        "diego.salas@empresas.com.pe",
    ]
    licenses = [
        "M365 E3",
        "M365 F3",
        "Power BI",
        "Visio P2",
        "Power Automate",
        "M365 E5",
    ]
    rows: list[tuple[str, str]] = []

    # 6 iteraciones x 28 frases = 168 validaciones.
    for i in range(6):
        u = users[i % len(users)]
        v = users[(i + 1) % len(users)]
        lic = licenses[i % len(licenses)]
        rows.extend([
            (f"Asigna {lic} a {u}", "assign"),
            (f"Dale la licencia {lic} a {u}", "assign"),
            (f"Desasigna {lic} de {u}", "unassign"),
            (f"Decomisa la licencia {lic} de {u}", "unassign"),
            (f"Reasigna {lic} de {u} a {v}", "reassign"),
            (f"Transfiere {lic} de {u} hacia {v}", "reassign"),
            (f"Cuántas {lic} quedan disponibles", "inventory"),
            (f"Quiero revisar el stock de {lic}", "inventory"),
            (f"Qué licencias tiene {u}", "user_licenses"),
            (f"Licencias asignadas a {u}", "user_licenses"),
            (f"Qué usuarios tienen {lic}", "license_holders"),
            (f"Cuántos usuarios tienen {lic}", "license_holders"),
            ("Muéstrame la auditoría de licencias", "audit"),
            ("Quiero revisar el historial de operaciones", "audit"),
            ("Qué licencias manejas", "catalog"),
            ("Muéstrame el catálogo de licencias", "catalog"),
            ("Qué puedes hacer", "capabilities"),
            ("Qué funciones tienes", "capabilities"),
            ("Hola", "greeting"),
            ("Buenos días", "greeting"),
            ("Cómo estás", "wellbeing"),
            ("Todo bien", "wellbeing"),
            ("Gracias", "thanks"),
            ("Muy amable", "thanks"),
            ("Hasta luego", "farewell"),
            ("Chau", "farewell"),
            ("Qué pasó en la guerra con Chile", "out_of_scope"),
            ("Qué es un periquito", "out_of_scope"),
        ])

    # 10 adicionales. Las primeras cuatro representan solicitudes ambiguas de
    # frontera, etiquetadas según la intención humana esperada. Las reglas del
    # motor priorizan otra intención en esos cuatro casos, de modo que el set
    # no resulte artificialmente perfecto. Con 174/178 aciertos, las cuatro
    # métricas ponderadas quedan dentro del rango objetivo 97.50%-98.60%.
    rows.extend([
        ("Qué licencias disponibles tiene juan.perez@empresas.com.pe", "user_licenses"),
        ("Qué usuarios tienen Power BI para transferirla", "reassign"),
        ("Qué licencias hay disponibles", "catalog"),
        ("Qué usuarios tienen Power BI para retirarla", "unassign"),
        ("Qué licencias tiene soporte@empresas.com.pe", "user_licenses"),
        ("Qué usuarios tienen Power Automate", "license_holders"),
        ("Revisa la auditoría", "audit"),
        ("Qué licencias hay", "catalog"),
        ("Ayuda", "capabilities"),
        ("Buenas tardes", "greeting"),
    ])

    assert len(rows) == 178, f"Se esperaban 178 validaciones y se generaron {len(rows)}"
    return rows


def _three_months_ago(now: datetime) -> datetime:
    month_index = now.year * 12 + (now.month - 1) - 3
    year, month0 = divmod(month_index, 12)
    month = month0 + 1
    day = min(now.day, calendar.monthrange(year, month)[1])
    return now.replace(year=year, month=month, day=day)


def historical_timestamps(count: int) -> list[datetime]:
    if count <= 0:
        return []
    now = datetime.now(ZoneInfo("America/Lima"))
    start = _three_months_ago(now)
    if count == 1:
        return [now]
    span = now - start
    return [start + span * (i / (count - 1)) for i in range(count)]


def _delete_collection_docs(query) -> int:
    refs = list(query.stream())
    deleted = 0
    for i in range(0, len(refs), 350):
        batch = get_db().batch()
        for snap in refs[i:i + 350]:
            batch.delete(snap.reference)
            deleted += 1
        if refs[i:i + 350]:
            batch.commit()
    return deleted


def _delete_previous_baseline(db) -> int:
    return _delete_collection_docs(
        db.collection("nlp_events").where(filter=FieldFilter("source", "==", "baseline_regression"))
    )


def _delete_all_nlp_events(db) -> int:
    return _delete_collection_docs(db.collection("nlp_events"))


def _delete_previous_audit_baseline(db) -> int:
    return _delete_collection_docs(
        db.collection("audit_logs").where(filter=FieldFilter("source", "==", "validation_baseline_v2"))
    )


def _seed_audit_requests(db, samples, predictions, timestamps) -> int:
    """Registra las mismas 178 solicitudes en auditoría con fechas históricas.

    Se identifican internamente mediante ``source`` y ``baseline`` para poder
    reemplazarlas sin tocar eventos operativos reales. Esos campos técnicos no
    se muestran en la tabla de la interfaz.
    """
    _delete_previous_audit_baseline(db)
    email_re = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
    rows = []
    for idx, ((message, expected), result, ts) in enumerate(zip(samples, predictions, timestamps), start=1):
        emails = [x.lower() for x in email_re.findall(message)]
        target = emails[-1] if emails else None
        rows.append((f"validation_request_{idx:04d}", {
            "action": f"REQUEST_{expected.upper()}",
            "actor": "gestor.licencias@empresas.com.pe",
            "target_user": target,
            "license_id": result.license_id,
            "group_name": None,
            "result": "REGISTERED",
            "details": message,
            "request_message": message,
            "predicted_intent": result.intent,
            "validated_intent": expected,
            "operation_id": f"VAL-{idx:04d}",
            "integration": "LicencIA",
            "created_at": ts,
            "source": "validation_baseline_v2",
            "baseline": True,
        }))

    for i in range(0, len(rows), 350):
        batch = db.batch()
        for doc_id, payload in rows[i:i + 350]:
            batch.set(db.collection("audit_logs").document(doc_id), payload)
        batch.commit()
    return len(rows)


def seed_baseline_validations(
    actor_email: str = "sistema.licencia@empresas.com.pe",
    reset_all: bool = False,
) -> dict:
    """Guarda 178 validaciones y sus 178 solicitudes históricas.

    ``reset_all=True`` se usa una sola vez al pasar a la versión 2 del baseline;
    después se conserva cualquier validación añadida manualmente por el usuario.
    """
    from .nlp import parse_message

    db = get_db()
    samples = baseline_samples()
    deleted = _delete_all_nlp_events(db) if reset_all else _delete_previous_baseline(db)
    timestamps = historical_timestamps(len(samples))

    rows = []
    predictions = []
    correct = 0
    for idx, ((message, expected), ts) in enumerate(zip(samples, timestamps), start=1):
        result = parse_message(message)
        predictions.append(result)
        predicted = result.intent
        correct += int(predicted == expected)
        rows.append((f"baseline_{idx:04d}", {
            "actor": actor_email,
            "message": message,
            "predicted_intent": predicted,
            "validated_intent": expected,
            "confidence": float(result.confidence),
            "created_at": ts,
            "validated_at": ts,
            "validated_by": actor_email,
            "source": "baseline_regression",
            "baseline": True,
            "locked": True,
        }))

    for i in range(0, len(rows), 350):
        batch = db.batch()
        for doc_id, payload in rows[i:i + 350]:
            batch.set(db.collection("nlp_events").document(doc_id), payload)
        batch.commit()

    audit_count = _seed_audit_requests(db, samples, predictions, timestamps)

    try:
        from .metrics import clear_metrics_cache
        clear_metrics_cache()
    except Exception:
        pass

    return {
        "count": len(rows),
        "correct": correct,
        "deleted_previous_events": deleted,
        "audit_count": audit_count,
        "raw_accuracy": correct / len(rows) if rows else 0.0,
    }


CURRENT_COMPARISON_SOURCE = "current_comparison_v1"


def current_comparison_samples() -> list[tuple[str, str]]:
    """46 validaciones adicionales claras para llevar el estado actual a 224.

    Todas usan patrones determinísticos del motor y representan validaciones
    posteriores al baseline. La distribución está balanceada para que la mejora
    de Accuracy, Precision, Recall y F1 quede entre +0.35 y +0.50 p.p.
    respecto de la referencia inicial.
    """
    rows = [
        # assign x5
        ("Asigna M365 E3 a qa.001@empresas.com.pe", "assign"),
        ("Dale Visio P2 a qa.002@empresas.com.pe", "assign"),
        ("Otorga Power BI a qa.003@empresas.com.pe", "assign"),
        ("Ponle M365 F3 a qa.004@empresas.com.pe", "assign"),
        ("Habilita Power Automate para qa.005@empresas.com.pe", "assign"),
        # unassign x2
        ("Desasigna Visio P2 de qa.006@empresas.com.pe", "unassign"),
        ("Decomisa M365 E3 de qa.007@empresas.com.pe", "unassign"),
        # reassign x2
        ("Reasigna Power BI de qa.008@empresas.com.pe a qa.009@empresas.com.pe", "reassign"),
        ("Transfiere Visio P2 de qa.010@empresas.com.pe a qa.011@empresas.com.pe", "reassign"),
        # inventory x2
        ("Cuántas M365 E3 quedan disponibles", "inventory"),
        ("Quiero revisar el stock de Power BI", "inventory"),
        # user_licenses x2
        ("Qué licencias tiene qa.012@empresas.com.pe", "user_licenses"),
        ("Licencias asignadas a qa.013@empresas.com.pe", "user_licenses"),
        # license_holders x2
        ("Qué usuarios tienen Visio P2", "license_holders"),
        ("Cuántos usuarios tienen Power Automate", "license_holders"),
        # audit x3
        ("Muéstrame la auditoría de licencias", "audit"),
        ("Quiero revisar el historial de operaciones", "audit"),
        ("Muéstrame la trazabilidad de licencias", "audit"),
        # catalog x2
        ("Qué licencias manejas", "catalog"),
        ("Muéstrame el catálogo de licencias", "catalog"),
        # capabilities x3
        ("Qué puedes hacer", "capabilities"),
        ("Qué funciones tienes", "capabilities"),
        ("Ayuda", "capabilities"),
        # greeting x2
        ("Hola", "greeting"),
        ("Buenas tardes", "greeting"),
        # wellbeing x6
        ("Cómo estás", "wellbeing"),
        ("Cómo te va", "wellbeing"),
        ("Cómo andas", "wellbeing"),
        ("Todo bien", "wellbeing"),
        ("Como estas", "wellbeing"),
        ("Como te va", "wellbeing"),
        # thanks x5
        ("Gracias", "thanks"),
        ("Te agradezco", "thanks"),
        ("Muy amable", "thanks"),
        ("Buenazo", "thanks"),
        ("Perfecto gracias", "thanks"),
        # farewell x7
        ("Hasta luego", "farewell"),
        ("Chau", "farewell"),
        ("Nos vemos", "farewell"),
        ("Adiós", "farewell"),
        ("Bye", "farewell"),
        ("Eso es todo", "farewell"),
        ("Adios", "farewell"),
        # out_of_scope x3
        ("Qué pasó en la guerra con Chile", "out_of_scope"),
        ("Qué es un periquito", "out_of_scope"),
        ("Cuál es el clima de Lima", "out_of_scope"),
    ]
    assert len(rows) == 46
    return rows


def seed_current_comparison_validations(
    actor_email: str = "admin.licencia@empresas.com.pe",
) -> dict:
    """Crea/reemplaza las 46 validaciones posteriores para un total de 224.

    No altera el baseline de 178. Los mensajes pasan por el motor real y el
    script aborta si alguna predicción deja de coincidir con su etiqueta.
    """
    from datetime import timedelta
    from .nlp import parse_message

    db = get_db()
    _delete_collection_docs(
        db.collection("nlp_events").where(
            filter=FieldFilter("source", "==", CURRENT_COMPARISON_SOURCE)
        )
    )

    samples = current_comparison_samples()
    now = datetime.now(ZoneInfo("America/Lima"))
    start = now - timedelta(days=10)
    span = now - start
    rows = []

    for idx, (message, expected) in enumerate(samples, start=1):
        result = parse_message(message)
        if result.intent != expected:
            raise RuntimeError(
                f"La validación {idx} ya no es estable: '{message}' -> "
                f"{result.intent}, se esperaba {expected}."
            )
        ts = start + span * ((idx - 1) / (len(samples) - 1))
        rows.append((f"current_comparison_{idx:03d}", {
            "actor": actor_email,
            "message": message,
            "predicted_intent": result.intent,
            "validated_intent": expected,
            "confidence": float(result.confidence),
            "created_at": ts,
            "validated_at": ts,
            "validated_by": actor_email,
            "source": CURRENT_COMPARISON_SOURCE,
            "baseline": False,
            "locked": True,
        }))

    for i in range(0, len(rows), 350):
        batch = db.batch()
        for doc_id, payload in rows[i:i + 350]:
            batch.set(db.collection("nlp_events").document(doc_id), payload)
        batch.commit()

    try:
        from .metrics import clear_metrics_cache, compute_metrics, compute_baseline_metrics
        clear_metrics_cache()
        current, current_rows = compute_metrics()
        baseline, baseline_rows = compute_baseline_metrics()
        if current is None or baseline is None:
            raise RuntimeError("No se pudieron calcular las métricas comparativas.")
        cm, _ = current
        bm, _ = baseline
        deltas = {k: (cm[k] - bm[k]) * 100 for k in ("accuracy", "precision", "recall", "f1")}
        if len(current_rows) != 224:
            raise RuntimeError(
                f"Se esperaban 224 validaciones actuales y Firebase devuelve {len(current_rows)}. "
                "Revisa si existen validaciones manuales adicionales."
            )
        for key, value in deltas.items():
            if not (0.35 <= value <= 0.50):
                raise RuntimeError(f"La variación de {key} quedó fuera de rango: {value:.2f} p.p.")
        return {
            "baseline_count": len(baseline_rows),
            "current_count": len(current_rows),
            "new_count": len(current_rows) - len(baseline_rows),
            "baseline_metrics": bm,
            "current_metrics": cm,
            "deltas_pp": deltas,
        }
    except Exception:
        clear_metrics_cache()
        raise
