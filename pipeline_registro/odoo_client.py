import xmlrpc.client

class OdooClient:
    def __init__(self, url, db, username, password):
        self.url = url
        self.db = db
        self.username = username
        self.password = password
        self.uid = None
        self.common = None
        self.models = None

    def authenticate(self):
        try:
            self.common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(self.url))
            self.uid = self.common.authenticate(self.db, self.username, self.password, {})
            self.models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(self.url))
            return self.uid
        except Exception as e:
            print(f"Error en el inicio de sesión desde la API Odoo: {e}")
            raise

    def execute_kw(self, model, method, args, kwargs=None):
        if kwargs is None:
            kwargs = {}
        return self.models.execute_kw(self.db, self.uid, self.password, model, method, args, kwargs)

    def search_read(self, model, domain, fields=None, limit=None):
        kwargs = {}
        if fields:
            kwargs['fields'] = fields
        if limit:
            kwargs['limit'] = limit
        return self.execute_kw(model, 'search_read', [domain], kwargs)

    def search(self, model, domain, limit=None):
        kwargs = {}
        if limit:
            kwargs['limit'] = limit
        return self.execute_kw(model, 'search', [domain], kwargs)

    def read(self, model, ids, fields=None):
        kwargs = {}
        if fields:
            kwargs['fields'] = fields
        return self.execute_kw(model, 'read', [ids], kwargs)

    def create(self, model, values):
        return self.execute_kw(model, 'create', [values])

    def write(self, model, ids, values):
        return self.execute_kw(model, 'write', [ids, values])

    def message_post(self, model, id, body, message_type='comment', subtype_xmlid='mail.mt_note', attachment_ids=None):
        kwargs = {
            'body': body,
            'message_type': message_type,
            'subtype_xmlid': subtype_xmlid
        }
        if attachment_ids:
            kwargs['attachment_ids'] = attachment_ids
        return self.execute_kw(model, 'message_post', [id], kwargs)

    def action_feedback(self, model, activity_ids, feedback):
        return self.execute_kw(model, 'action_feedback', [activity_ids], {'feedback': feedback})
