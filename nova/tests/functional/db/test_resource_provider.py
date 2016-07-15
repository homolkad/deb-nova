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


from oslo_db import exception as db_exc

from nova import context
from nova import exception
from nova import objects
from nova.objects import fields
from nova import test
from nova.tests import fixtures
from nova.tests import uuidsentinel

RESOURCE_CLASS = fields.ResourceClass.DISK_GB
RESOURCE_CLASS_ID = fields.ResourceClass.index(
    fields.ResourceClass.DISK_GB)
DISK_INVENTORY = dict(
    total=200,
    reserved=10,
    min_unit=2,
    max_unit=5,
    step_size=1,
    allocation_ratio=1.0,
    resource_class=RESOURCE_CLASS
)

DISK_ALLOCATION = dict(
    consumer_id=uuidsentinel.disk_consumer,
    used=2,
    resource_class=RESOURCE_CLASS
)


class ResourceProviderBaseCase(test.NoDBTestCase):

    USES_DB_SELF = True

    def setUp(self):
        super(ResourceProviderBaseCase, self).setUp()
        self.useFixture(fixtures.Database())
        self.useFixture(fixtures.Database(database='api'))
        self.context = context.RequestContext('fake-user', 'fake-project')

    def _make_allocation(self, rp_uuid=None):
        rp_uuid = rp_uuid or uuidsentinel.allocation_resource_provider
        db_rp = objects.ResourceProvider(
            context=self.context,
            uuid=rp_uuid,
            name=rp_uuid)
        db_rp.create()
        updates = dict(DISK_ALLOCATION,
                       resource_class_id=RESOURCE_CLASS_ID,
                       resource_provider_id=db_rp.id)
        db_allocation = objects.Allocation._create_in_db(self.context,
                                                         updates)
        return db_rp, db_allocation


class ResourceProviderTestCase(ResourceProviderBaseCase):
    """Test resource-provider objects' lifecycles."""

    def test_create_resource_provider_requires_uuid(self):
        resource_provider = objects.ResourceProvider(
            context = self.context)
        self.assertRaises(exception.ObjectActionError,
                          resource_provider.create)

    def test_create_resource_provider(self):
        created_resource_provider = objects.ResourceProvider(
            context=self.context,
            uuid=uuidsentinel.fake_resource_provider,
            name=uuidsentinel.fake_resource_name,
        )
        created_resource_provider.create()
        self.assertIsInstance(created_resource_provider.id, int)

        retrieved_resource_provider = objects.ResourceProvider.get_by_uuid(
            self.context,
            uuidsentinel.fake_resource_provider
        )
        self.assertEqual(retrieved_resource_provider.id,
                         created_resource_provider.id)
        self.assertEqual(retrieved_resource_provider.uuid,
                         created_resource_provider.uuid)
        self.assertEqual(retrieved_resource_provider.name,
                         created_resource_provider.name)
        self.assertEqual(0, created_resource_provider.generation)
        self.assertEqual(0, retrieved_resource_provider.generation)

    def test_save_resource_provider(self):
        created_resource_provider = objects.ResourceProvider(
            context=self.context,
            uuid=uuidsentinel.fake_resource_provider,
            name=uuidsentinel.fake_resource_name,
        )
        created_resource_provider.create()
        created_resource_provider.name = 'new-name'
        created_resource_provider.save()
        retrieved_resource_provider = objects.ResourceProvider.get_by_uuid(
            self.context,
            uuidsentinel.fake_resource_provider
        )
        self.assertEqual('new-name', retrieved_resource_provider.name)

    def test_destroy_resource_provider(self):
        created_resource_provider = objects.ResourceProvider(
            context=self.context,
            uuid=uuidsentinel.fake_resource_provider,
            name=uuidsentinel.fake_resource_name,
        )
        created_resource_provider.create()
        created_resource_provider.destroy()
        self.assertRaises(exception.NotFound,
                          objects.ResourceProvider.get_by_uuid,
                          self.context,
                          uuidsentinel.fake_resource_provider)
        self.assertRaises(exception.NotFound,
                          created_resource_provider.destroy)

    def test_destroy_allocated_resource_provider_fails(self):
        rp, allocation = self._make_allocation()
        self.assertRaises(exception.ResourceProviderInUse,
                          rp.destroy)

    def test_destroy_resource_provider_destroy_inventory(self):
        resource_provider = objects.ResourceProvider(
            context=self.context,
            uuid=uuidsentinel.fake_resource_provider,
            name=uuidsentinel.fake_resource_name,
        )
        resource_provider.create()
        disk_inventory = objects.Inventory(
            context=self.context,
            resource_provider=resource_provider,
            **DISK_INVENTORY
        )
        disk_inventory.create()
        inventories = objects.InventoryList.get_all_by_resource_provider_uuid(
            self.context, resource_provider.uuid)
        self.assertEqual(1, len(inventories))
        resource_provider.destroy()
        inventories = objects.InventoryList.get_all_by_resource_provider_uuid(
            self.context, resource_provider.uuid)
        self.assertEqual(0, len(inventories))

    def test_create_inventory_with_uncreated_provider(self):
        resource_provider = objects.ResourceProvider(
            context=self.context,
            uuid=uuidsentinel.inventory_resource_provider
        )
        disk_inventory = objects.Inventory(
            context=self.context,
            resource_provider=resource_provider,
            **DISK_INVENTORY
        )
        self.assertRaises(exception.ObjectActionError,
                          disk_inventory.create)

    def test_create_and_update_inventory(self):
        resource_provider = objects.ResourceProvider(
            context=self.context,
            uuid=uuidsentinel.inventory_resource_provider,
            name='foo',
        )
        resource_provider.create()
        resource_class = fields.ResourceClass.DISK_GB
        disk_inventory = objects.Inventory(
            context=self.context,
            resource_provider=resource_provider,
            **DISK_INVENTORY
        )
        disk_inventory.create()

        self.assertEqual(resource_class, disk_inventory.resource_class)
        self.assertEqual(resource_provider,
                         disk_inventory.resource_provider)
        self.assertEqual(DISK_INVENTORY['allocation_ratio'],
                         disk_inventory.allocation_ratio)
        self.assertEqual(DISK_INVENTORY['total'],
                         disk_inventory.total)

        disk_inventory.total = 32
        disk_inventory.save()

        inventories = objects.InventoryList.get_all_by_resource_provider_uuid(
            self.context, resource_provider.uuid)

        self.assertEqual(1, len(inventories))
        self.assertEqual(32, inventories[0].total)

        inventories[0].total = 33
        inventories[0].save()
        reloaded_inventories = (
            objects.InventoryList.get_all_by_resource_provider_uuid(
            self.context, resource_provider.uuid))
        self.assertEqual(33, reloaded_inventories[0].total)

    def test_provider_modify_inventory(self):
        rp = objects.ResourceProvider(context=self.context,
                                      uuid=uuidsentinel.rp_uuid,
                                      name=uuidsentinel.rp_name)
        rp.create()
        saved_generation = rp.generation

        disk_inv = objects.Inventory(
                resource_provider=rp,
                resource_class=fields.ResourceClass.DISK_GB,
                total=1024,
                reserved=15,
                min_unit=10,
                max_unit=100,
                step_size=10,
                allocation_ratio=1.0)

        vcpu_inv = objects.Inventory(
                resource_provider=rp,
                resource_class=fields.ResourceClass.VCPU,
                total=12,
                reserved=0,
                min_unit=1,
                max_unit=12,
                step_size=1,
                allocation_ratio=16.0)

        # set to new list
        inv_list = objects.InventoryList(objects=[disk_inv, vcpu_inv])
        rp.set_inventory(inv_list)

        # generation has bumped
        self.assertEqual(saved_generation + 1, rp.generation)
        saved_generation = rp.generation

        new_inv_list = objects.InventoryList.get_all_by_resource_provider_uuid(
                self.context, uuidsentinel.rp_uuid)
        self.assertEqual(2, len(new_inv_list))
        resource_classes = [inv.resource_class for inv in new_inv_list]
        self.assertIn(fields.ResourceClass.VCPU, resource_classes)
        self.assertIn(fields.ResourceClass.DISK_GB, resource_classes)

        # reset list to just disk_inv
        inv_list = objects.InventoryList(objects=[disk_inv])
        rp.set_inventory(inv_list)

        # generation has bumped
        self.assertEqual(saved_generation + 1, rp.generation)
        saved_generation = rp.generation

        new_inv_list = objects.InventoryList.get_all_by_resource_provider_uuid(
                self.context, uuidsentinel.rp_uuid)
        self.assertEqual(1, len(new_inv_list))
        resource_classes = [inv.resource_class for inv in new_inv_list]
        self.assertNotIn(fields.ResourceClass.VCPU, resource_classes)
        self.assertIn(fields.ResourceClass.DISK_GB, resource_classes)
        self.assertEqual(1024, new_inv_list[0].total)

        # update existing disk inv to new settings
        disk_inv = objects.Inventory(
                resource_provider=rp,
                resource_class=fields.ResourceClass.DISK_GB,
                total=2048,
                reserved=15,
                min_unit=10,
                max_unit=100,
                step_size=10,
                allocation_ratio=1.0)
        rp.update_inventory(disk_inv)

        # generation has bumped
        self.assertEqual(saved_generation + 1, rp.generation)
        saved_generation = rp.generation

        new_inv_list = objects.InventoryList.get_all_by_resource_provider_uuid(
                self.context, uuidsentinel.rp_uuid)
        self.assertEqual(1, len(new_inv_list))
        self.assertEqual(2048, new_inv_list[0].total)

        # fail when inventory bad
        disk_inv = objects.Inventory(
                resource_provider=rp,
                resource_class=fields.ResourceClass.DISK_GB,
                total=2048,
                reserved=2048)
        disk_inv.obj_set_defaults()
        self.assertRaises(exception.ObjectActionError,
                          rp.update_inventory, disk_inv)

        # generation has not bumped
        self.assertEqual(saved_generation, rp.generation)

        # delete inventory
        rp.delete_inventory(fields.ResourceClass.DISK_GB)

        # generation has bumped
        self.assertEqual(saved_generation + 1, rp.generation)
        saved_generation = rp.generation

        new_inv_list = objects.InventoryList.get_all_by_resource_provider_uuid(
                self.context, uuidsentinel.rp_uuid)
        result = new_inv_list.find(fields.ResourceClass.DISK_GB)
        self.assertIsNone(result)
        self.assertRaises(exception.NotFound, rp.delete_inventory,
                          fields.ResourceClass.DISK_GB)

        # check inventory list is empty
        inv_list = objects.InventoryList.get_all_by_resource_provider_uuid(
                self.context, uuidsentinel.rp_uuid)
        self.assertEqual(0, len(inv_list))

        # add some inventory
        rp.add_inventory(vcpu_inv)
        inv_list = objects.InventoryList.get_all_by_resource_provider_uuid(
                self.context, uuidsentinel.rp_uuid)
        self.assertEqual(1, len(inv_list))

        # generation has bumped
        self.assertEqual(saved_generation + 1, rp.generation)
        saved_generation = rp.generation

        # add same inventory again
        self.assertRaises(db_exc.DBDuplicateEntry,
                          rp.add_inventory, vcpu_inv)

        # generation has not bumped
        self.assertEqual(saved_generation, rp.generation)

        # fail when generation wrong
        rp.generation = rp.generation - 1
        self.assertRaises(exception.ConcurrentUpdateDetected,
                          rp.set_inventory, inv_list)

    def test_delete_inventory_not_found(self):
        rp = objects.ResourceProvider(context=self.context,
                                      uuid=uuidsentinel.rp_uuid,
                                      name=uuidsentinel.rp_name)
        rp.create()
        error = self.assertRaises(exception.NotFound, rp.delete_inventory,
                                  'DISK_GB')
        self.assertIn('No inventory of class DISK_GB found for delete',
                      str(error))

    def test_update_inventory_not_found(self):
        rp = objects.ResourceProvider(context=self.context,
                                      uuid=uuidsentinel.rp_uuid,
                                      name=uuidsentinel.rp_name)
        rp.create()
        disk_inv = objects.Inventory(resource_provider=rp,
                                     resource_class='DISK_GB',
                                     total=2048)
        disk_inv.obj_set_defaults()
        error = self.assertRaises(exception.NotFound, rp.update_inventory,
                                  disk_inv)
        self.assertIn('No inventory of class DISK_GB found for update',
                      str(error))


class ResourceProviderListTestCase(test.NoDBTestCase):

    USES_DB_SELF = True

    def setUp(self):
        super(ResourceProviderListTestCase, self).setUp()
        self.useFixture(fixtures.Database())
        self.useFixture(fixtures.Database(database='api'))
        self.context = context.RequestContext('fake-user', 'fake-project')

    def test_get_all_by_filters(self):
        for rp_i in ['1', '2']:
            uuid = getattr(uuidsentinel, 'rp_uuid_' + rp_i)
            name = 'rp_name_' + rp_i
            rp = objects.ResourceProvider(self.context, name=name, uuid=uuid)
            rp.create()

        resource_providers = objects.ResourceProviderList.get_all_by_filters(
            self.context)
        self.assertEqual(2, len(resource_providers))
        resource_providers = objects.ResourceProviderList.get_all_by_filters(
            self.context, filters={'name': 'rp_name_1'})
        self.assertEqual(1, len(resource_providers))
        resource_providers = objects.ResourceProviderList.get_all_by_filters(
            self.context, filters={'can_host': 1})
        self.assertEqual(0, len(resource_providers))


class TestAllocation(ResourceProviderBaseCase):

    def test_create_list_and_delete_allocation(self):
        resource_provider = objects.ResourceProvider(
            context=self.context,
            uuid=uuidsentinel.allocation_resource_provider,
            name=uuidsentinel.allocation_resource_name
        )
        resource_provider.create()
        resource_class = fields.ResourceClass.DISK_GB
        disk_allocation = objects.Allocation(
            context=self.context,
            resource_provider=resource_provider,
            **DISK_ALLOCATION
        )
        disk_allocation.create()

        self.assertEqual(resource_class, disk_allocation.resource_class)
        self.assertEqual(resource_provider,
                         disk_allocation.resource_provider)
        self.assertEqual(DISK_ALLOCATION['used'],
                         disk_allocation.used)
        self.assertEqual(DISK_ALLOCATION['consumer_id'],
                         disk_allocation.consumer_id)
        self.assertIsInstance(disk_allocation.id, int)

        allocations = objects.AllocationList.get_all_by_resource_provider_uuid(
            self.context, resource_provider.uuid)

        self.assertEqual(1, len(allocations))

        self.assertEqual(DISK_ALLOCATION['used'],
                        allocations[0].used)

        allocations[0].destroy()

        allocations = objects.AllocationList.get_all_by_resource_provider_uuid(
            self.context, resource_provider.uuid)

        self.assertEqual(0, len(allocations))

    def test_destroy(self):
        rp, allocation = self._make_allocation()
        allocations = objects.AllocationList.get_all_by_resource_provider_uuid(
            self.context, rp.uuid)
        self.assertEqual(1, len(allocations))
        objects.Allocation._destroy(self.context, allocation.id)
        allocations = objects.AllocationList.get_all_by_resource_provider_uuid(
            self.context, rp.uuid)
        self.assertEqual(0, len(allocations))
        self.assertRaises(exception.NotFound, objects.Allocation._destroy,
                          self.context, allocation.id)

    def test_get_allocations_from_db(self):
        rp, allocation = self._make_allocation()
        allocations = objects.AllocationList._get_allocations_from_db(
            self.context, rp.uuid)
        self.assertEqual(1, len(allocations))
        self.assertEqual(rp.id, allocations[0].resource_provider_id)
        self.assertEqual(allocation.resource_provider_id,
                         allocations[0].resource_provider_id)

        allocations = objects.AllocationList._get_allocations_from_db(
            self.context, uuidsentinel.bad_rp_uuid)
        self.assertEqual(0, len(allocations))

    def test_get_all_by_resource_provider(self):
        rp, allocation = self._make_allocation()
        allocations = objects.AllocationList.get_all_by_resource_provider_uuid(
            self.context, rp.uuid)
        self.assertEqual(1, len(allocations))
        self.assertEqual(rp.id, allocations[0].resource_provider.id)
        self.assertEqual(allocation.resource_provider_id,
                         allocations[0].resource_provider.id)

    def test_get_all_multiple_providers(self):
        # This confirms that the join with resource provider is
        # behaving.
        rp1, allocation1 = self._make_allocation(uuidsentinel.rp1)
        rp2, allocation2 = self._make_allocation(uuidsentinel.rp2)
        allocations = objects.AllocationList.get_all_by_resource_provider_uuid(
            self.context, rp1.uuid)
        self.assertEqual(1, len(allocations))
        self.assertEqual(rp1.id, allocations[0].resource_provider.id)
        self.assertEqual(allocation1.resource_provider_id,
                         allocations[0].resource_provider.id)

        # add more allocations for the first resource provider
        # of the same class
        updates = dict(consumer_id=uuidsentinel.consumer1,
                       resource_class_id=RESOURCE_CLASS_ID,
                       resource_provider_id=rp1.id,
                       used=2)
        objects.Allocation._create_in_db(self.context, updates)
        allocations = objects.AllocationList.get_all_by_resource_provider_uuid(
            self.context, rp1.uuid)
        self.assertEqual(2, len(allocations))

        # add more allocations for the first resource provider
        # of a different class
        updates = dict(consumer_id=uuidsentinel.consumer1,
                       resource_class_id=fields.ResourceClass.index(
                           fields.ResourceClass.IPV4_ADDRESS),
                       resource_provider_id=rp1.id,
                       used=4)
        objects.Allocation._create_in_db(self.context, updates)
        allocations = objects.AllocationList.get_all_by_resource_provider_uuid(
            self.context, rp1.uuid)
        self.assertEqual(3, len(allocations))
        self.assertEqual(rp1.uuid, allocations[0].resource_provider.uuid)

        allocations = objects.AllocationList.get_all_by_resource_provider_uuid(
            self.context, rp2.uuid)
        self.assertEqual(1, len(allocations))
        self.assertEqual(rp2.uuid, allocations[0].resource_provider.uuid)
        self.assertIn(RESOURCE_CLASS,
                      [allocation.resource_class
                       for allocation in allocations])
        self.assertNotIn(fields.ResourceClass.IPV4_ADDRESS,
                      [allocation.resource_class
                       for allocation in allocations])
