"""Verify actual Telegram signature checks and the explicit webapp owner boundary."""
import hashlib
import hmac
import importlib
import json
import time
import unittest
from urllib.parse import urlencode
from unittest.mock import patch

class OwnerIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.api=importlib.import_module('videl.__main__')
        cls.client=cls.api._flask.test_client()

    def send(self, body):
        with patch.object(self.api.config,'BOT_TOKEN','test-token'), patch.object(self.api.config,'WEBAPP_SECRET','test-secret'), patch.object(self.api.config,'OWNER_ID',999):
            return self.client.post('/internal/auth',json=body,headers={'X-Videl-Internal':'test-secret'})

    def mini_app(self, uid, age=0):
        fields={'auth_date':str(int(time.time())-age),'user':json.dumps({'id':uid,'first_name':'Test'})}
        secret=hmac.new(b'WebAppData',b'test-token','sha256').digest()
        fields['hash']=hmac.new(secret,'\n'.join(f'{k}={v}' for k,v in sorted(fields.items())).encode(),'sha256').hexdigest()
        return urlencode(fields)

    def test_only_explicit_owner_gets_access_even_if_config_differs(self):
        self.assertEqual(self.send({'init_data':self.mini_app(6265999542)}).status_code,200)
        self.assertEqual(self.send({'init_data':self.mini_app(999)}).status_code,403)

    def test_forged_expired_and_duplicate_data_fail(self):
        valid=self.mini_app(6265999542)
        self.assertEqual(self.send({'init_data':valid+'&auth_date=1'}).status_code,401)
        self.assertEqual(self.send({'init_data':self.mini_app(6265999542,86461)}).status_code,401)
        self.assertEqual(self.send({'init_data':valid.replace('Test','Forged')}).status_code,401)

    def test_login_widget_signature_and_owner_are_both_required(self):
        for uid,status in [(6265999542,200),(999,403)]:
            fields={'id':uid,'first_name':'Test','auth_date':int(time.time())}
            check='\n'.join(f'{k}={v}' for k,v in sorted(fields.items()))
            fields['hash']=hmac.new(hashlib.sha256(b'test-token').digest(),check.encode(),'sha256').hexdigest()
            self.assertEqual(self.send({'login_widget':fields}).status_code,status)
