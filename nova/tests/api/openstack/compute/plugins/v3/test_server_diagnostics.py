# Copyright 2011 Eldar Nugaev
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from lxml import etree

from nova.api.openstack import compute
from nova.api.openstack.compute.plugins.v3 import server_diagnostics
from nova.api.openstack import wsgi
from nova.compute import api as compute_api
from nova import exception
from nova.openstack.common import jsonutils
from nova import test
from nova.tests.api.openstack import fakes


UUID = 'abc'


def fake_get_diagnostics(self, _context, instance_uuid):
    return {'data': 'Some diagnostic info'}


def fake_instance_get(self, _context, instance_uuid):
    if instance_uuid != UUID:
        raise Exception("Invalid UUID")
    return {'uuid': instance_uuid}


def fake_instance_get_instance_not_found(self, _context, instance_uuid):
    raise exception.InstanceNotFound(instance_id=instance_uuid)


class ServerDiagnosticsTest(test.TestCase):

    def setUp(self):
        super(ServerDiagnosticsTest, self).setUp()
        self.stubs.Set(compute_api.API, 'get_diagnostics',
                       fake_get_diagnostics)
        self.stubs.Set(compute_api.API, 'get', fake_instance_get)

        self.router = compute.APIRouterV3(init_only=('servers',
                                                     'os-server-diagnostics'))

    def test_get_diagnostics(self):
        req = fakes.HTTPRequestV3.blank(
            '/servers/%s/os-server-diagnostics' % UUID)
        res = req.get_response(self.router)
        output = jsonutils.loads(res.body)
        self.assertEqual(output, {'data': 'Some diagnostic info'})

    def test_get_diagnostics_with_non_existed_instance(self):
        req = fakes.HTTPRequestV3.blank(
            '/servers/%s/os-server-diagnostics' % UUID)
        self.stubs.Set(compute_api.API, 'get',
                       fake_instance_get_instance_not_found)
        res = req.get_response(self.router)
        self.assertEqual(res.status_int, 404)


class TestServerDiagnosticsXMLSerializer(test.TestCase):
    namespace = wsgi.XMLNS_V11

    def _tag(self, elem):
        tagname = elem.tag
        self.assertEqual(tagname[0], '{')
        tmp = tagname.partition('}')
        namespace = tmp[0][1:]
        self.assertEqual(namespace, self.namespace)
        return tmp[2]

    def test_index_serializer(self):
        serializer = server_diagnostics.ServerDiagnosticsTemplate()
        exemplar = dict(diag1='foo', diag2='bar')
        text = serializer.serialize(exemplar)

        tree = etree.fromstring(text)

        self.assertEqual('diagnostics', self._tag(tree))
        self.assertEqual(len(tree), len(exemplar))
        for child in tree:
            tag = self._tag(child)
            self.assertTrue(tag in exemplar)
            self.assertEqual(child.text, exemplar[tag])
