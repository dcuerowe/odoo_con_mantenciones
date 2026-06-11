"""
Introspecta los modelos maintenance.equipment, maintenance.request y
x_studio_location en la instancia Odoo configurada en .env, y vuelca:
  - fields_get() de cada modelo (filtrado a metadatos relevantes para ER)
  - registros de ir.model.fields para los mismos modelos (para ttype y relation)
en un JSON consumible por el generador del .drawio.
"""

import json
import os
import sys
from pathlib import Path

# Estamos en ../maintenance_plan/; OdooClient vive en ../pipeline_registro_II/
HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT / "pipeline_registro_II"))

from dotenv import load_dotenv

# Carga .env desde la raíz del workspace (donde el usuario lo tiene)
load_dotenv(dotenv_path="/home/dacmxo/Desktop/we/.env")

from odoo_client import OdooClient  # noqa: E402

MODELS = [
    "maintenance.equipment",
    "maintenance.request",
    # El usuario pidió "x_studio_location", que en realidad es el campo
    # many2one x_studio_location en maintenance.equipment cuya relation es
    # el modelo Studio x_maintenance_location.
    "x_maintenance_location",
]

FIELD_ATTRS = [
    "name", "string", "type", "required", "readonly", "store",
    "relation", "relation_field", "relation_table",
    "column1", "column2", "selection", "help",
]


def main():
    # Soporta tanto el bloque de producción como el de TEST que aparece en .env
    url = os.getenv("URL_Odoo") or os.getenv("URL_TEST")
    db = os.getenv("DB_Odoo") or os.getenv("DB_TEST")
    user = os.getenv("USER_Odoo") or os.getenv("USER_TEST")
    pwd = os.getenv("ODOO_API_KEY") or os.getenv("ODOO_TEST_API_KEY")

    missing = [name for name, v in (
        ("URL", url), ("DB", db), ("USER", user), ("API_KEY", pwd)
    ) if not v]
    if missing:
        raise SystemExit(
            "Faltan variables en .env: " + ", ".join(missing) +
            " (acepta sufijo _Odoo o _TEST)"
        )

    client = OdooClient(url, db, user, pwd)
    uid = client.authenticate()
    if not uid:
        raise SystemExit("Autenticación fallida: revisa credenciales en .env")

    out = {"server": url, "db": db, "models": {}}

    for model in MODELS:
        info = {"exists": True, "fields": {}, "ir_model_fields": []}
        try:
            fields = client.execute_kw(model, "fields_get", [], {"attributes": FIELD_ATTRS})
        except Exception as e:
            info["exists"] = False
            info["error"] = str(e)
            out["models"][model] = info
            continue

        # Conserva solo claves útiles para ER
        cleaned = {}
        for fname, meta in fields.items():
            cleaned[fname] = {k: meta.get(k) for k in FIELD_ATTRS if k in meta}
        info["fields"] = cleaned

        # ir.model.fields da relation_table/column1/column2 confiables para many2many
        try:
            irfields = client.search_read(
                "ir.model.fields",
                [["model", "=", model]],
                fields=[
                    "name", "field_description", "ttype",
                    "relation", "relation_field",
                    "relation_table", "column1", "column2",
                    "required", "store", "compute",
                ],
            )
        except Exception as e:
            irfields = [{"error": str(e)}]
        info["ir_model_fields"] = irfields

        out["models"][model] = info

    out_path = HERE / "er_introspection.json"
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    print(f"OK -> {out_path}")
    for m in MODELS:
        present = out["models"][m].get("exists", False)
        nfields = len(out["models"][m].get("fields", {}))
        print(f"  {m}: exists={present} fields={nfields}")


if __name__ == "__main__":
    main()
