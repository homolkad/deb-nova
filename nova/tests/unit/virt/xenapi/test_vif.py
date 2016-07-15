# Copyright 2013 OpenStack Foundation
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

import mock

from nova import exception
from nova.network import model
from nova import test
from nova.tests.unit.virt.xenapi import stubs
from nova.virt.xenapi import network_utils
from nova.virt.xenapi import vif


fake_vif = {
    'created_at': None,
    'updated_at': None,
    'deleted_at': None,
    'deleted': 0,
    'id': '123456789123',
    'address': '00:00:00:00:00:00',
    'network_id': 123,
    'instance_uuid': 'fake-uuid',
    'uuid': 'fake-uuid-2',
}


def fake_call_xenapi(method, *args):
    if method == "VM.get_VIFs":
        return ["fake_vif_ref", "fake_vif_ref_A2"]
    if method == "VIF.get_record":
        if args[0] == "fake_vif_ref":
            return {'uuid': fake_vif['uuid'],
                    'MAC': fake_vif['address'],
                    'network': 'fake_network',
                    'other_config': {'nicira-iface-id': fake_vif['id']}
                    }
        else:
            raise exception.Exception("Failed get vif record")
    if method == "VIF.unplug":
        return
    if method == "VIF.destroy":
        if args[0] == "fake_vif_ref":
            return
        else:
            raise exception.Exception("unplug vif failed")
    if method == "VIF.create":
        if args[0] == "fake_vif_rec":
            return "fake_vif_ref"
        else:
            raise exception.Exception("VIF existed")
    return "Unexpected call_xenapi: %s.%s" % (method, args)


class XenVIFDriverTestBase(stubs.XenAPITestBaseNoDB):
    def setUp(self):
        super(XenVIFDriverTestBase, self).setUp()
        self._session = mock.Mock()
        self._session.call_xenapi.side_effect = fake_call_xenapi

    def mock_patch_object(self, target, attribute, return_val=None,
                          side_effect=None):
        """Utilility function to mock object's attribute at runtime:
        Some methods are dynamic, so standard mocking does not work
        and we need to mock them at runtime.
        e.g. self._session.VIF.get_record which is dynamically
        created via the override function of __getattr__.
        """

        patcher = mock.patch.object(target, attribute,
                                    return_value=return_val,
                                    side_effect=side_effect)
        mock_one = patcher.start()
        self.addCleanup(patcher.stop)
        return mock_one


class XenVIFDriverTestCase(XenVIFDriverTestBase):
    def setUp(self):
        super(XenVIFDriverTestCase, self).setUp()
        self.base_driver = vif.XenVIFDriver(self._session)

    def test_get_vif_ref(self):
        vm_ref = "fake_vm_ref"
        vif_ref = 'fake_vif_ref'
        ret_vif_ref = self.base_driver._get_vif_ref(fake_vif, vm_ref)
        self.assertEqual(vif_ref, ret_vif_ref)

        expected = [mock.call('VM.get_VIFs', vm_ref),
                    mock.call('VIF.get_record', vif_ref)]
        self.assertEqual(expected, self._session.call_xenapi.call_args_list)

    def test_get_vif_ref_none_and_exception(self):
        vm_ref = "fake_vm_ref"
        vif = {'address': "no_match_vif_address"}
        ret_vif_ref = self.base_driver._get_vif_ref(vif, vm_ref)
        self.assertIsNone(ret_vif_ref)

        expected = [mock.call('VM.get_VIFs', vm_ref),
                    mock.call('VIF.get_record', 'fake_vif_ref'),
                    mock.call('VIF.get_record', 'fake_vif_ref_A2')]
        self.assertEqual(expected, self._session.call_xenapi.call_args_list)

    def test_create_vif(self):
        vif_rec = "fake_vif_rec"
        vm_ref = "fake_vm_ref"
        ret_vif_ref = self.base_driver._create_vif(fake_vif, vif_rec, vm_ref)
        self.assertEqual("fake_vif_ref", ret_vif_ref)

        expected = [mock.call('VIF.create', vif_rec)]
        self.assertEqual(expected, self._session.call_xenapi.call_args_list)

    def test_create_vif_exception(self):
        self.assertRaises(exception.NovaException,
                          self.base_driver._create_vif,
                          "fake_vif", "missing_vif_rec", "fake_vm_ref")

    @mock.patch.object(vif.XenVIFDriver, '_get_vif_ref',
                       return_value='fake_vif_ref')
    def test_unplug(self, mock_get_vif_ref):
        instance = {'name': "fake_instance"}
        vm_ref = "fake_vm_ref"
        self.base_driver.unplug(instance, fake_vif, vm_ref)
        expected = [mock.call('VIF.destroy', 'fake_vif_ref')]
        self.assertEqual(expected, self._session.call_xenapi.call_args_list)

    @mock.patch.object(vif.XenVIFDriver, '_get_vif_ref',
                       return_value='missing_vif_ref')
    def test_unplug_exception(self, mock_get_vif_ref):
        instance = "fake_instance"
        vm_ref = "fake_vm_ref"
        self.assertRaises(exception.NovaException,
                          self.base_driver.unplug,
                          instance, fake_vif, vm_ref)


class XenAPIBridgeDriverTestCase(XenVIFDriverTestBase, object):
    def setUp(self):
        super(XenAPIBridgeDriverTestCase, self).setUp()
        self.bridge_driver = vif.XenAPIBridgeDriver(self._session)

    @mock.patch.object(vif.XenAPIBridgeDriver, '_ensure_vlan_bridge',
                       return_value='fake_network_ref')
    @mock.patch.object(vif.XenVIFDriver, '_create_vif',
                       return_value='fake_vif_ref')
    def test_plug_create_vlan(self, mock_create_vif, mock_ensure_vlan_bridge):
        instance = {'name': "fake_instance_name"}
        network = model.Network()
        network._set_meta({'should_create_vlan': True})
        vif = model.VIF()
        vif._set_meta({'rxtx_cap': 1})
        vif['network'] = network
        vif['address'] = "fake_address"
        vm_ref = "fake_vm_ref"
        device = 1
        ret_vif_ref = self.bridge_driver.plug(instance, vif, vm_ref, device)
        self.assertEqual('fake_vif_ref', ret_vif_ref)


class XenAPIOpenVswitchDriverTestCase(XenVIFDriverTestBase):
    def setUp(self):
        super(XenAPIOpenVswitchDriverTestCase, self).setUp()
        self.ovs_driver = vif.XenAPIOpenVswitchDriver(self._session)

    @mock.patch.object(vif.XenVIFDriver, '_create_vif',
                       return_value='fake_vif_ref')
    @mock.patch.object(vif.XenAPIOpenVswitchDriver,
                       'create_vif_interim_network')
    @mock.patch.object(vif.XenVIFDriver, '_get_vif_ref', return_value=None)
    @mock.patch.object(vif.vm_utils, 'lookup', return_value='fake_vm_ref')
    def test_plug(self, mock_lookup, mock_get_vif_ref,
                  mock_create_vif_interim_network,
                  mock_create_vif):
        instance = {'name': "fake_instance_name"}
        ret_vif_ref = self.ovs_driver.plug(
            instance, fake_vif, vm_ref=None, device=1)
        self.assertTrue(mock_lookup.called)
        self.assertTrue(mock_get_vif_ref.called)
        self.assertTrue(mock_create_vif_interim_network.called)
        self.assertTrue(mock_create_vif.called)
        self.assertEqual('fake_vif_ref', ret_vif_ref)

    @mock.patch.object(vif.XenAPIOpenVswitchDriver, '_delete_linux_bridge')
    @mock.patch.object(vif.XenAPIOpenVswitchDriver, '_delete_linux_port')
    @mock.patch.object(vif.XenAPIOpenVswitchDriver, '_device_exists',
                       return_value=True)
    @mock.patch.object(vif.XenAPIOpenVswitchDriver, '_ovs_del_br')
    @mock.patch.object(vif.XenAPIOpenVswitchDriver, '_ovs_del_port')
    @mock.patch.object(network_utils, 'find_network_with_name_label',
                       return_value='fake_network')
    @mock.patch.object(vif.XenVIFDriver, 'unplug')
    def test_unplug(self, mock_super_unplug,
                    mock_find_network_with_name_label,
                    mock_ovs_del_port,
                    mock_ovs_del_br,
                    mock_device_exists,
                    mock_delete_linux_port,
                    mock_delete_linux_bridge):
        instance = {'name': "fake_instance"}
        vm_ref = "fake_vm_ref"

        mock_network_get_VIFs = self.mock_patch_object(
            self._session.network, 'get_VIFs', return_val=None)
        mock_network_get_bridge = self.mock_patch_object(
            self._session.network, 'get_bridge', return_val='fake_bridge')
        mock_network_destroy = self.mock_patch_object(
            self._session.network, 'destroy')
        self.ovs_driver.unplug(instance, fake_vif, vm_ref)

        self.assertTrue(mock_super_unplug.called)
        self.assertTrue(mock_find_network_with_name_label.called)
        self.assertTrue(mock_network_get_VIFs.called)
        self.assertTrue(mock_network_get_bridge.called)
        self.assertEqual(mock_ovs_del_port.call_count, 2)
        self.assertTrue(mock_network_destroy.called)

    @mock.patch.object(vif.XenAPIOpenVswitchDriver, '_ovs_del_br')
    @mock.patch.object(vif.XenAPIOpenVswitchDriver, '_ovs_del_port')
    @mock.patch.object(network_utils, 'find_network_with_name_label',
                       return_value='fake_network')
    @mock.patch.object(vif.XenVIFDriver, 'unplug')
    def test_unplug_exception(self, mock_super_unplug,
                    mock_find_network_with_name_label,
                    mock_ovs_del_port,
                    mock_ovs_del_br):
        instance = {'name': "fake_instance"}
        vm_ref = "fake_vm_ref"

        self.mock_patch_object(
            self._session.network, 'get_VIFs', return_val=None)
        self.mock_patch_object(
            self._session.network, 'get_bridge', return_val='fake_bridge')
        self.mock_patch_object(
            self._session.network, 'destroy',
            side_effect=test.TestingException)

        self.assertRaises(exception.VirtualInterfaceUnplugException,
                          self.ovs_driver.unplug, instance, fake_vif,
                          vm_ref)

    @mock.patch.object(vif.XenAPIOpenVswitchDriver, '_brctl_add_if')
    @mock.patch.object(vif.XenAPIOpenVswitchDriver, '_create_linux_bridge')
    @mock.patch.object(vif.XenAPIOpenVswitchDriver, '_ovs_add_port')
    def test_post_start_actions(self, mock_ovs_add_port,
                                mock_create_linux_bridge,
                                mock_brctl_add_if):
        vif_ref = "fake_vif_ref"
        instance = {'name': 'fake_instance_name'}
        fake_vif_rec = {'uuid': fake_vif['uuid'],
                        'MAC': fake_vif['address'],
                        'network': 'fake_network',
                        'other_config': {
                            'nicira-iface-id': 'fake-nicira-iface-id'}
                       }
        mock_VIF_get_record = self.mock_patch_object(
            self._session.VIF, 'get_record', return_val=fake_vif_rec)
        mock_network_get_bridge = self.mock_patch_object(
            self._session.network, 'get_bridge',
            return_val='fake_bridge_name')
        mock_network_get_uuid = self.mock_patch_object(
            self._session.network, 'get_uuid',
            return_val='fake_network_uuid')

        self.ovs_driver.post_start_actions(instance, vif_ref)

        self.assertTrue(mock_VIF_get_record.called)
        self.assertTrue(mock_network_get_bridge.called)
        self.assertTrue(mock_network_get_uuid.called)
        self.assertEqual(mock_ovs_add_port.call_count, 1)
        self.assertTrue(mock_brctl_add_if.called)

    @mock.patch.object(network_utils, 'find_network_with_name_label',
                       return_value="exist_network_ref")
    def test_create_vif_interim_network_exist(self,
                  mock_find_network_with_name_label):
        mock_network_create = self.mock_patch_object(
            self._session.network, 'create', return_val='new_network_ref')
        network_ref = self.ovs_driver.create_vif_interim_network(fake_vif)
        self.assertFalse(mock_network_create.called)
        self.assertEqual(network_ref, 'exist_network_ref')

    @mock.patch.object(network_utils, 'find_network_with_name_label',
                       return_value=None)
    def test_create_vif_interim_network_new(self,
                  mock_find_network_with_name_label):
        mock_network_create = self.mock_patch_object(
            self._session.network, 'create', return_val='new_network_ref')
        network_ref = self.ovs_driver.create_vif_interim_network(fake_vif)
        self.assertTrue(mock_network_create.called)
        self.assertEqual(network_ref, 'new_network_ref')
