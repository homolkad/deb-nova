# Copyright 2012 Nebula, Inc.
# Copyright 2013 IBM Corp.
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


import inspect
import os

from oslo_config import cfg
from oslo_log import log as logging
from oslo_serialization import jsonutils
from oslo_utils import importutils
import testtools

# Import extensions to pull in osapi_compute_extension CONF option used below.
from nova.console import manager as console_manager  # noqa - only for cfg
from nova.network.neutronv2 import api as neutron_api  # noqa - only for cfg
from nova import test
from nova.tests.functional import api_samples_test_base
from nova.tests.functional import integrated_helpers
from nova.tests.unit.api.openstack import fakes
from nova.tests.unit import fake_network
from nova.tests.unit import fake_utils
from nova.tests.unit.image import fake
from nova.volume import cinder

CONF = cfg.CONF
CONF.import_opt('allow_resize_to_same_host', 'nova.compute.api')
CONF.import_opt('shelved_offload_time', 'nova.compute.manager')
CONF.import_opt('enable_network_quota',
                'nova.api.openstack.compute.contrib.os_tenant_networks')
CONF.import_opt('osapi_compute_extension',
                'nova.api.openstack.compute.extensions')
CONF.import_opt('osapi_compute_link_prefix', 'nova.api.openstack.common')
CONF.import_opt('osapi_glance_link_prefix', 'nova.api.openstack.common')
CONF.import_opt('enable', 'nova.cells.opts', group='cells')
CONF.import_opt('cell_type', 'nova.cells.opts', group='cells')
CONF.import_opt('db_check_interval', 'nova.cells.state', group='cells')
LOG = logging.getLogger(__name__)


class ApiSampleTestBaseV2(api_samples_test_base.ApiSampleTestBase):
    _api_version = 'v2'

    def setUp(self):
        extends = []
        self.flags(use_ipv6=False,
                   osapi_compute_link_prefix=self._get_host(),
                   osapi_glance_link_prefix=self._get_glance_host())
        if not self.all_extensions:
            if hasattr(self, 'extends_name'):
                extends = [self.extends_name]
            ext = [self.extension_name] if self.extension_name else []
            self.flags(osapi_compute_extension=ext + extends)
        super(ApiSampleTestBaseV2, self).setUp()
        self.useFixture(test.SampleNetworks(host=self.network.host))
        fake_network.stub_compute_with_ips(self.stubs)
        fake_utils.stub_out_utils_spawn_n(self.stubs)
        self.generate_samples = os.getenv('GENERATE_SAMPLES') is not None


class ApiSamplesTrap(ApiSampleTestBaseV2):
    """Make sure extensions don't get added without tests."""

    all_extensions = True

    def _get_extensions_tested(self):
        tests = []
        for attr in globals().values():
            if not inspect.isclass(attr):
                continue  # Skip non-class objects
            if not issubclass(attr, integrated_helpers._IntegratedTestBase):
                continue  # Skip non-test classes
            if attr.extension_name is None:
                continue  # Skip base tests
            cls = importutils.import_class(attr.extension_name)
            tests.append(cls.alias)
        return tests

    def _get_extensions(self):
        extensions = []
        response = self._do_get('extensions')
        for extension in jsonutils.loads(response.content)['extensions']:
            extensions.append(str(extension['alias']))
        return extensions

    def test_all_extensions_have_samples(self):
        # NOTE(danms): This is a list of extensions which are currently
        # in the tree but that don't (yet) have tests. This list should
        # NOT be allowed to grow, and should shrink to zero (and be
        # removed) soon.

        # TODO(gmann): skip this tests as merging of sample tests for v2
        # and v2.1 are in progress. After merging all tests, this tests
        # need to implement in different way.
        raise testtools.TestCase.skipException('Merging of v2 and v2.1 '
                                               'sample tests is in progress. '
                                               'This test will be enabled '
                                               'after all tests gets merged.')
        do_not_approve_additions = []
        do_not_approve_additions.append('os-create-server-ext')
        do_not_approve_additions.append('os-baremetal-ext-status')

        tests = self._get_extensions_tested()
        extensions = self._get_extensions()
        missing_tests = []
        for extension in extensions:
            # NOTE(danms): if you add tests, remove it from the
            # exclusions list
            self.assertFalse(extension in do_not_approve_additions and
                             extension in tests)

            # NOTE(danms): if you add an extension, it must come with
            # api_samples tests!
            if (extension not in tests and
                    extension not in do_not_approve_additions):
                missing_tests.append(extension)

        if missing_tests:
            LOG.error("Extensions are missing tests: %s" % missing_tests)
        self.assertEqual(missing_tests, [])


class VersionsSampleJsonTest(ApiSampleTestBaseV2):
    sample_dir = 'versions'

    def test_versions_get(self):
        response = self._do_get('', strip_version=True)
        subs = self._get_regexes()
        self._verify_response('versions-get-resp', subs, response, 200)


class ServersSampleBase(ApiSampleTestBaseV2):
    def _post_server(self, use_common_server_api_samples=True):
        # param use_common_server_api_samples: Boolean to set whether tests use
        # common sample files for server post request and response.
        # Default is True which means _get_sample_path method will fetch the
        # common server sample files.
        # Set False if tests need to use extension specific sample files
        subs = {
            'image_id': fake.get_valid_image_id(),
            'host': self._get_host(),
        }
        orig_value = self.__class__._use_common_server_api_samples
        try:
            self.__class__._use_common_server_api_samples = (
                                        use_common_server_api_samples)
            response = self._do_post('servers', 'server-post-req', subs)
            subs = self._get_regexes()
            status = self._verify_response('server-post-resp', subs,
                                           response, 202)
            return status
        finally:
            self.__class__._use_common_server_api_samples = orig_value


class ServersSampleMultiStatusJsonTest(ServersSampleBase):
    extension_name = '.'.join(('nova.api.openstack.compute.contrib',
                               'server_list_multi_status',
                               'Server_list_multi_status'))

    def test_servers_list(self):
        uuid = self._post_server()
        response = self._do_get('servers?status=active&status=error')
        subs = self._get_regexes()
        subs['id'] = uuid
        self._verify_response('servers-list-resp', subs, response, 200)


class FlavorsSampleJsonTest(ApiSampleTestBaseV2):
    sample_dir = 'flavors'

    def test_flavors_get(self):
        response = self._do_get('flavors/1')
        subs = self._get_regexes()
        self._verify_response('flavor-get-resp', subs, response, 200)

    def test_flavors_list(self):
        response = self._do_get('flavors')
        subs = self._get_regexes()
        self._verify_response('flavors-list-resp', subs, response, 200)


class FlavorsSampleAllExtensionJsonTest(FlavorsSampleJsonTest):
    all_extensions = True


class LimitsSampleJsonTest(ApiSampleTestBaseV2):
    sample_dir = 'limits'

    def test_limits_get(self):
        response = self._do_get('limits')
        subs = self._get_regexes()
        self._verify_response('limit-get-resp', subs, response, 200)


class VirtualInterfacesJsonTest(ServersSampleBase):
    extension_name = ("nova.api.openstack.compute.contrib"
                     ".virtual_interfaces.Virtual_interfaces")

    def test_vifs_list(self):
        uuid = self._post_server()

        response = self._do_get('servers/%s/os-virtual-interfaces' % uuid)

        subs = self._get_regexes()
        subs['mac_addr'] = '(?:[a-f0-9]{2}:){5}[a-f0-9]{2}'

        self._verify_response('vifs-list-resp', subs, response, 200)


class UsedLimitsSamplesJsonTest(ApiSampleTestBaseV2):
    extension_name = ("nova.api.openstack.compute.contrib.used_limits."
                      "Used_limits")

    def test_get_used_limits(self):
        # Get api sample to used limits.
        response = self._do_get('limits')
        subs = self._get_regexes()
        self._verify_response('usedlimits-get-resp', subs, response, 200)


class UsedLimitsForAdminSamplesJsonTest(ApiSampleTestBaseV2):
    ADMIN_API = True
    extends_name = ("nova.api.openstack.compute.contrib.used_limits."
                    "Used_limits")
    extension_name = (
        "nova.api.openstack.compute.contrib.used_limits_for_admin."
        "Used_limits_for_admin")

    def test_get_used_limits_for_admin(self):
        tenant_id = 'openstack'
        response = self._do_get('limits?tenant_id=%s' % tenant_id)
        subs = self._get_regexes()
        return self._verify_response('usedlimitsforadmin-get-resp', subs,
                                     response, 200)


class ExtendedIpsSampleJsonTests(ServersSampleBase):
    extension_name = ("nova.api.openstack.compute.contrib"
                      ".extended_ips.Extended_ips")

    def test_show(self):
        uuid = self._post_server()
        response = self._do_get('servers/%s' % uuid)
        subs = self._get_regexes()
        subs['hostid'] = '[a-f0-9]+'
        subs['id'] = uuid
        subs['hypervisor_hostname'] = r'[\w\.\-]+'
        self._verify_response('server-get-resp', subs, response, 200)

    def test_detail(self):
        uuid = self._post_server()
        response = self._do_get('servers/detail')
        subs = self._get_regexes()
        subs['id'] = uuid
        subs['hostid'] = '[a-f0-9]+'
        self._verify_response('servers-detail-resp', subs, response, 200)


class ExtendedIpsMacSampleJsonTests(ServersSampleBase):
    extension_name = ("nova.api.openstack.compute.contrib"
                      ".extended_ips_mac.Extended_ips_mac")

    def test_show(self):
        uuid = self._post_server()
        response = self._do_get('servers/%s' % uuid)
        self.assertEqual(response.status_code, 200)
        subs = self._get_regexes()
        subs['hostid'] = '[a-f0-9]+'
        subs['id'] = uuid
        subs['hypervisor_hostname'] = r'[\w\.\-]+'
        subs['mac_addr'] = '(?:[a-f0-9]{2}:){5}[a-f0-9]{2}'
        self._verify_response('server-get-resp', subs, response, 200)

    def test_detail(self):
        uuid = self._post_server()
        response = self._do_get('servers/detail')
        self.assertEqual(response.status_code, 200)
        subs = self._get_regexes()
        subs['id'] = uuid
        subs['hostid'] = '[a-f0-9]+'
        subs['mac_addr'] = '(?:[a-f0-9]{2}:){5}[a-f0-9]{2}'
        self._verify_response('servers-detail-resp', subs, response, 200)


class ExtendedVIFNetSampleJsonTests(ServersSampleBase):
    extension_name = ("nova.api.openstack.compute.contrib"
          ".extended_virtual_interfaces_net.Extended_virtual_interfaces_net")

    def _get_flags(self):
        f = super(ExtendedVIFNetSampleJsonTests, self)._get_flags()
        f['osapi_compute_extension'] = CONF.osapi_compute_extension[:]
        # extended_virtual_interfaces_net_update also
        # needs virtual_interfaces to be loaded
        f['osapi_compute_extension'].append(
            ('nova.api.openstack.compute.contrib'
             '.virtual_interfaces.Virtual_interfaces'))
        return f

    def test_vifs_list(self):
        uuid = self._post_server()

        response = self._do_get('servers/%s/os-virtual-interfaces' % uuid)
        self.assertEqual(response.status_code, 200)

        subs = self._get_regexes()
        subs['mac_addr'] = '(?:[a-f0-9]{2}:){5}[a-f0-9]{2}'

        self._verify_response('vifs-list-resp', subs, response, 200)


class BlockDeviceMappingV2BootJsonTest(ServersSampleBase):
    extension_name = ('nova.api.openstack.compute.contrib.'
                      'block_device_mapping_v2_boot.'
                      'Block_device_mapping_v2_boot')

    def _get_flags(self):
        f = super(BlockDeviceMappingV2BootJsonTest, self)._get_flags()
        f['osapi_compute_extension'] = CONF.osapi_compute_extension[:]
        # We need the volumes extension as well
        f['osapi_compute_extension'].append(
            'nova.api.openstack.compute.contrib.volumes.Volumes')
        return f

    def test_servers_post_with_bdm_v2(self):
        self.stubs.Set(cinder.API, 'get', fakes.stub_volume_get)
        self.stubs.Set(cinder.API, 'check_attach',
                       fakes.stub_volume_check_attach)
        return self._post_server()


class ServerGroupQuotas_LimitsSampleJsonTest(LimitsSampleJsonTest):
    sample_dir = None
    extension_name = ("nova.api.openstack.compute.contrib."
                      "server_group_quotas.Server_group_quotas")


class ServerGroupQuotas_UsedLimitsSamplesJsonTest(UsedLimitsSamplesJsonTest):
    extension_name = ("nova.api.openstack.compute.contrib."
               "server_group_quotas.Server_group_quotas")
    extends_name = ("nova.api.openstack.compute.contrib.used_limits."
                    "Used_limits")
