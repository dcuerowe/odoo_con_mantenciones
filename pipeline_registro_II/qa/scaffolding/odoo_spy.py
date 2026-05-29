"""Doble de prueba (spy) de OdooClient.

Implementa la MISMA interfaz que `odoo_client.OdooClient` pero no abre ninguna
conexión: registra cada llamada en `self.calls` y devuelve respuestas programables.
Permite ejercitar `processor.process_entrys` afirmando sobre las llamadas XML-RPC
sin escribir en ningún Odoo (capa L2 de la estrategia de QA).

Uso típico:

    spy = OdooSpy()
    spy.queue("search_read", "maintenance.equipment", [{"id": 42, ...}])
    spy.queue("search", "maintenance.request", [])           # FIFO por (método, modelo)
    process_entrys(df, "KEY", resumen, exito, spy)
    assert spy.created("maintenance.request")                # algo se creó
    assert spy.calls_of("write", "maintenance.request")      # se actualizó algo
"""

import itertools
from dataclasses import dataclass, field


@dataclass
class Call:
    method: str
    model: str
    args: tuple = ()
    kwargs: dict = field(default_factory=dict)


class OdooSpy:
    def __init__(self):
        self.calls: list[Call] = []
        self._responses: dict[tuple[str, str], list] = {}
        self._defaults: dict[tuple[str, str], object] = {}
        self._ids = itertools.count(1000)
        self.uid = 1
        self.url = "spy://test"
        self.db = "spy"

    # ------------------------------------------------------------------ #
    # Programación de respuestas
    # ------------------------------------------------------------------ #
    def queue(self, method: str, model: str, response):
        """Encola una respuesta para la próxima llamada (método, modelo). FIFO."""
        self._responses.setdefault((method, model), []).append(response)

    def set_default(self, method: str, model: str, response):
        """Respuesta fija para (método, modelo) cuando la cola está vacía. Útil
        cuando un módulo consulta el mismo modelo varias veces (p.ej. R itera E+I)."""
        self._defaults[(method, model)] = response

    def _pop(self, method: str, model: str, default):
        q = self._responses.get((method, model))
        if q:
            return q.pop(0)
        return self._defaults.get((method, model), default)

    def _record(self, method, model, args=(), kwargs=None):
        self.calls.append(Call(method, model, tuple(args), dict(kwargs or {})))

    # ------------------------------------------------------------------ #
    # Interfaz OdooClient
    # ------------------------------------------------------------------ #
    def authenticate(self):
        self.uid = 1
        return self.uid

    def execute_kw(self, model, method, args, kwargs=None):
        self._record("execute_kw", model, (method, tuple(args)), kwargs)
        return self._pop("execute_kw", model, [])

    def search_read(self, model, domain, fields=None, limit=None):
        self._record("search_read", model, (domain,), {"fields": fields, "limit": limit})
        return self._pop("search_read", model, [])

    def search(self, model, domain, limit=None):
        self._record("search", model, (domain,), {"limit": limit})
        return self._pop("search", model, [])

    def read(self, model, ids, fields=None):
        self._record("read", model, (ids,), {"fields": fields})
        return self._pop("read", model, [])

    def create(self, model, values):
        self._record("create", model, (values,))
        r = self._pop("create", model, None)
        return r if r is not None else next(self._ids)

    def write(self, model, ids, values):
        self._record("write", model, (ids, values))
        return self._pop("write", model, True)

    def message_post(self, model, id, body, message_type="comment",
                     subtype_xmlid="mail.mt_note", partner_ids=None, attachment_ids=None):
        self._record("message_post", model, (id, body),
                     {"message_type": message_type, "partner_ids": partner_ids,
                      "attachment_ids": attachment_ids})
        return self._pop("message_post", model, True)

    def message_subscribe(self, model, ids, partner_ids):
        self._record("message_subscribe", model, (ids, partner_ids))
        return True

    def action_feedback(self, model, activity_ids, feedback):
        self._record("action_feedback", model, (activity_ids, feedback))
        return True

    # ------------------------------------------------------------------ #
    # Helpers de aserción
    # ------------------------------------------------------------------ #
    def calls_of(self, method, model=None):
        return [c for c in self.calls
                if c.method == method and (model is None or c.model == model)]

    def created(self, model):
        """Lista de dicts `values` de cada create sobre `model`."""
        return [c.args[0] for c in self.calls if c.method == "create" and c.model == model]

    def writes(self, model):
        """Lista de tuplas (ids, values) de cada write sobre `model`."""
        return [c.args for c in self.calls if c.method == "write" and c.model == model]

    def dump(self):
        """Texto legible de todas las llamadas — útil para calibrar asserts."""
        return "\n".join(
            f"{i:>2} {c.method:<16} {c.model:<26} args={c.args} kwargs={c.kwargs}"
            for i, c in enumerate(self.calls)
        )
