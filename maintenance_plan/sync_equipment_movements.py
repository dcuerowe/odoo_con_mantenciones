"""
Puente Connecteam → Odoo para movimientos de equipos.

Polea dos formularios de Connecteam ("Reemplazo en terreno" y
"Recepción de equipo calibrado") y dispara las Server Actions
SA-10 / SA-11 vía XML-RPC. Idempotente: la marca connecteam_entry:<id>
en notes evita reprocesos.

Uso:
    python sync_equipment_movements.py --once          # un tick y sale (cron)
    python sync_equipment_movements.py --since 24h     # procesa últimas 24h
    python sync_equipment_movements.py --dry-run       # no escribe en Odoo

Cron sugerido:
    */5 * * * * /opt/.venv/bin/python /opt/maintenance_plan/sync_equipment_movements.py --once

Requisitos en .env (raíz del workspace):
    URL_Odoo, DB_Odoo, USER_Odoo, ODOO_API_KEY
    CONNECTEAM_API_KEY
    CONNECTEAM_FORM_REPLACEMENT_ID
    CONNECTEAM_FORM_RETURN_ID
    SA10_XMLID    (default: __custom__.sa_10_register_replacement)
    SA11_XMLID    (default: __custom__.sa_11_receive_external_api)
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT / "pipeline_registro_II"))

from dotenv import load_dotenv

load_dotenv(dotenv_path="/home/dacmxo/Desktop/we/.env")

from odoo_client import OdooClient  # noqa: E402
# El módulo connecteam_api.py de pipeline_registro_II expone helpers de polling.
# Si la API ahí no calza exactamente, el wrapper de abajo lo deja explícito.
try:
    from connecteam_api import ConnecteamClient  # noqa: E402
except ImportError:
    ConnecteamClient = None  # fallback: usar requests directo (ver _fetch_entries_fallback)

LAST_RUN_FILE = HERE / "last_run.txt"
PENDING_REVIEW_FILE = HERE / "pending_review.json"
LOG_FILE = HERE / "sync_equipment_movements.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()],
)
log = logging.getLogger("sync_eq_movements")


# ── Helpers ─────────────────────────────────────────────────────────────────

def _read_last_run():
    if not LAST_RUN_FILE.exists():
        return datetime.now(timezone.utc) - timedelta(hours=24)
    try:
        return datetime.fromisoformat(LAST_RUN_FILE.read_text().strip())
    except Exception:
        return datetime.now(timezone.utc) - timedelta(hours=24)


def _write_last_run(ts):
    LAST_RUN_FILE.write_text(ts.isoformat())


def _append_pending(entry, error):
    pending = []
    if PENDING_REVIEW_FILE.exists():
        try:
            pending = json.loads(PENDING_REVIEW_FILE.read_text())
        except Exception:
            pending = []
    pending.append({
        "entry_id": entry.get("id"),
        "form_id": entry.get("form_id"),
        "error": str(error),
        "ts_failed": datetime.now(timezone.utc).isoformat(),
        "payload": entry,
    })
    PENDING_REVIEW_FILE.write_text(json.dumps(pending, indent=2))


# ── Conector Connecteam ─────────────────────────────────────────────────────

def _fetch_entries(form_id, since_dt):
    """Devuelve lista de dicts con al menos: id, submitted_at, fields."""
    if ConnecteamClient is None:
        return _fetch_entries_fallback(form_id, since_dt)
    api_key = os.getenv("CONNECTEAM_API_KEY")
    cc = ConnecteamClient(api_key)
    # Asume que el cliente expone list_form_entries(form_id, since). Ajustar si
    # la API real difiere.
    return cc.list_form_entries(form_id, since=since_dt.isoformat())


def _fetch_entries_fallback(form_id, since_dt):
    """Fallback con requests directo si ConnecteamClient no está disponible."""
    import requests
    api_key = os.getenv("CONNECTEAM_API_KEY")
    headers = {"X-API-KEY": api_key}
    url = f"https://api.connecteam.com/forms/v1/forms/{form_id}/entries"
    params = {"submittedAfter": since_dt.isoformat()}
    resp = requests.get(url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", {}).get("entries", [])


def _entry_field(entry, field_label):
    """Extrae un campo del entry por label. La estructura real de Connecteam
    varía; ajustar a la forma exacta que entrega tu API."""
    for f in entry.get("fields", []):
        if f.get("label", "").lower() == field_label.lower():
            return f.get("value")
    return None


# ── Payload builders por tipo de form ───────────────────────────────────────

def _build_kwargs_replacement(entry):
    return {
        "ctx_original_serial": _entry_field(entry, "original_serial"),
        "ctx_replacement_serial": _entry_field(entry, "replacement_serial"),
        "ctx_swap_date": _entry_field(entry, "swap_date"),
        "ctx_technician": _entry_field(entry, "technician_name"),
        "ctx_form_entry_id": str(entry["id"]),
        "ctx_notes": _entry_field(entry, "notes") or "",
    }


def _build_kwargs_return(entry):
    return {
        "ctx_returning_serial": _entry_field(entry, "returning_serial"),
        "ctx_destination_location_external_id": _entry_field(entry, "destination_point") or "stock",
        "ctx_replacement_policy": _entry_field(entry, "replacement_policy") or "return_to_stock",
        "ctx_replacement_new_location_external_id": _entry_field(entry, "replacement_new_point"),
        "ctx_calibration_cert_b64": _entry_field(entry, "calibration_cert"),
        "ctx_form_entry_id": str(entry["id"]),
        "ctx_notes": _entry_field(entry, "notes") or "",
    }


# ── Ejecución de SA en Odoo ────────────────────────────────────────────────

def _run_server_action(client, xmlid, kwargs, dry_run=False):
    """Ejecuta una ir.actions.server por XMLID pasando context."""
    if dry_run:
        log.info("[DRY-RUN] would call %s with %s", xmlid, kwargs)
        return
    # Resolver el ID del SA
    module, name = xmlid.split(".", 1)
    sa = client.execute_kw(
        "ir.model.data", "check_object_reference",
        [module, name], {}
    )
    # sa = ('ir.actions.server', <id>)
    sa_id = sa[1] if isinstance(sa, (list, tuple)) else sa
    # Disparar la acción con contexto
    client.execute_kw(
        "ir.actions.server", "with_context",
        [[sa_id]], {"context": kwargs}
    )
    # En Odoo 17 lo más limpio es:
    client.execute_kw(
        "ir.actions.server", "run",
        [[sa_id]], {"context": kwargs}
    )


# ── Loop principal ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="un tick y sale")
    parser.add_argument("--since", help="override de last_run, ej. '24h', '7d'")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.since:
        unit = args.since[-1]
        amount = int(args.since[:-1])
        delta = {"h": timedelta(hours=amount), "d": timedelta(days=amount)}.get(unit)
        if not delta:
            raise SystemExit("--since acepta sufijo h o d, ej. 24h o 7d")
        since_dt = datetime.now(timezone.utc) - delta
    else:
        since_dt = _read_last_run()

    log.info("Polling desde %s (dry_run=%s)", since_dt.isoformat(), args.dry_run)

    # Odoo
    url = os.getenv("URL_Odoo") or os.getenv("URL_TEST")
    db = os.getenv("DB_Odoo") or os.getenv("DB_TEST")
    user = os.getenv("USER_Odoo") or os.getenv("USER_TEST")
    pwd = os.getenv("ODOO_API_KEY") or os.getenv("ODOO_TEST_API_KEY")
    client = OdooClient(url, db, user, pwd)
    client.authenticate()

    # Mapping form_id → (builder, sa_xmlid)
    forms = {
        os.getenv("CONNECTEAM_FORM_REPLACEMENT_ID"): (
            _build_kwargs_replacement,
            os.getenv("SA10_XMLID", "__custom__.sa_10_register_replacement"),
        ),
        os.getenv("CONNECTEAM_FORM_RETURN_ID"): (
            _build_kwargs_return,
            os.getenv("SA11_XMLID", "__custom__.sa_11_receive_external_api"),
        ),
    }

    new_max_ts = since_dt
    processed = 0
    failed = 0

    for form_id, (builder, xmlid) in forms.items():
        if not form_id:
            log.warning("FORM_ID no configurado, salto.")
            continue
        try:
            entries = _fetch_entries(form_id, since_dt)
        except Exception as e:
            log.error("Fetch falló form %s: %s", form_id, e)
            continue

        log.info("Form %s: %d entries nuevos", form_id, len(entries))

        for entry in entries:
            entry["form_id"] = form_id
            try:
                kwargs = builder(entry)
                _run_server_action(client, xmlid, kwargs, dry_run=args.dry_run)
                processed += 1
                ts = entry.get("submitted_at")
                if ts:
                    try:
                        ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                        if ts_dt > new_max_ts:
                            new_max_ts = ts_dt
                    except Exception:
                        pass
            except Exception as e:
                log.exception("Entry %s falló: %s", entry.get("id"), e)
                _append_pending(entry, e)
                failed += 1

    if not args.dry_run and (processed or failed == 0):
        _write_last_run(new_max_ts)
    log.info("Tick OK. processed=%s failed=%s next_since=%s",
             processed, failed, new_max_ts.isoformat())


if __name__ == "__main__":
    main()
