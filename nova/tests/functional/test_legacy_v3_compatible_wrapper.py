# Copyright 2015 Intel Corporation.
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

from nova.api.openstack import wsgi
from nova.tests.functional import integrated_helpers
from nova.tests.functional.v3 import api_paste_fixture


class LegacyV2CompatibleTestBase(integrated_helpers._IntegratedTestBase):
    _api_version = 'v2'

    def setUp(self):
        self.useFixture(api_paste_fixture.ApiPasteV2CompatibleFixture())
        super(LegacyV2CompatibleTestBase, self).setUp()

    def test_request_with_microversion_headers(self):
        response = self.api.api_post('os-keypairs',
            {"keypair": {"name": "test"}},
            headers={wsgi.API_VERSION_REQUEST_HEADER: '2.100'})
        self.assertNotIn(wsgi.API_VERSION_REQUEST_HEADER, response.headers)
        self.assertNotIn('Vary', response.headers)
        self.assertNotIn('type', response.body["keypair"])
