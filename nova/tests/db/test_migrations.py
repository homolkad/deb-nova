# Copyright 2010-2011 OpenStack Foundation
# Copyright 2012-2013 IBM Corp.
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

"""
Tests for database migrations.
There are "opportunistic" tests which allows testing against all 3 databases
(sqlite in memory, mysql, pg) in a properly configured unit test environment.

For the opportunistic testing you need to set up db's named 'openstack_citest'
with user 'openstack_citest' and password 'openstack_citest' on localhost. The
test will then use that db and u/p combo to run the tests.

For postgres on Ubuntu this can be done with the following commands::

| sudo -u postgres psql
| postgres=# create user openstack_citest with createdb login password
|       'openstack_citest';
| postgres=# create database openstack_citest with owner openstack_citest;

"""

import glob
import logging
import os

from migrate.versioning import repository
import mock
from oslo.config import cfg
from oslo.db.sqlalchemy import test_base
from oslo.db.sqlalchemy import test_migrations
from oslo.db.sqlalchemy import utils as oslodbutils
import sqlalchemy
import sqlalchemy.exc

from nova.db import migration
from nova.db.sqlalchemy import migrate_repo
from nova.db.sqlalchemy import migration as sa_migration
from nova.db.sqlalchemy import utils as db_utils
from nova.i18n import _
from nova import test
from nova.tests import conf_fixture
from nova.virt.baremetal.db import migration as bm_migration
from nova.virt.baremetal.db.sqlalchemy import migrate_repo as bm_migrate_repo
from nova.virt.baremetal.db.sqlalchemy import migration as bm_sa_migration

LOG = logging.getLogger(__name__)


class NovaMigrationsCheckersBase(test_migrations.WalkVersionsMixin):
    """Test sqlalchemy-migrate migrations."""

    @property
    def INIT_VERSION(self):
        return migration.db_initial_version()

    @property
    def REPOSITORY(self):
        return repository.Repository(
            os.path.abspath(os.path.dirname(migrate_repo.__file__)))

    @property
    def migration_api(self):
        return sa_migration.versioning_api

    @property
    def migrate_engine(self):
        return self.engine

    def setUp(self):
        super(NovaMigrationsCheckersBase, self).setUp()
        conf_fixture.ConfFixture(cfg.CONF)
        self.addCleanup(cfg.CONF.reset)
        # NOTE(viktors): We should reduce log output because it causes issues,
        #                when we run tests with testr
        migrate_log = logging.getLogger('migrate')
        old_level = migrate_log.level
        migrate_log.setLevel(logging.WARN)
        self.addCleanup(migrate_log.setLevel, old_level)

    def assertColumnExists(self, engine, table_name, column):
        self.assertTrue(oslodbutils.column_exists(engine, table_name, column))

    def assertColumnNotExists(self, engine, table_name, column):
        self.assertFalse(oslodbutils.column_exists(engine, table_name, column))

    def assertTableNotExists(self, engine, table):
        self.assertRaises(sqlalchemy.exc.NoSuchTableError,
                          oslodbutils.get_table, engine, table)

    def assertIndexExists(self, engine, table_name, index):
        self.assertTrue(oslodbutils.index_exists(engine, table_name, index))

    def assertIndexMembers(self, engine, table, index, members):
        self.assertIndexExists(engine, table, index)

        t = oslodbutils.get_table(engine, table)
        index_columns = None
        for idx in t.indexes:
            if idx.name == index:
                index_columns = idx.columns.keys()
                break

        self.assertEqual(sorted(members), sorted(index_columns))

    def migrate_up(self, version, with_data=False):
        if with_data:
            check = getattr(self, "_check_%03d" % version, None)
            if version not in self._skippable_migrations():
                self.assertIsNotNone(check,
                                     ('DB Migration %i does not have a '
                                      'test. Please add one!') % version)

        super(NovaMigrationsCheckersBase, self).migrate_up(version, with_data)

    def test_walk_versions(self):
        self.walk_versions(self.snake_walk, self.downgrade)


class NovaMigrationsCheckers(NovaMigrationsCheckersBase):
    """Test sqlalchemy-migrate migrations."""

    TIMEOUT_SCALING_FACTOR = 2

    snake_walk = True
    downgrade = True

    def _skippable_migrations(self):
        special = [
            216,  # Havana
        ]

        havana_placeholders = range(217, 227)
        icehouse_placeholders = range(235, 244)
        juno_placeholders = range(255, 265)

        return (special +
                havana_placeholders +
                icehouse_placeholders +
                juno_placeholders)

    def _check_227(self, engine, data):
        table = oslodbutils.get_table(engine, 'project_user_quotas')

        # Insert fake_quotas with the longest resource name.
        fake_quotas = {'id': 5,
                       'project_id': 'fake_project',
                       'user_id': 'fake_user',
                       'resource': 'injected_file_content_bytes',
                       'hard_limit': 10}
        table.insert().execute(fake_quotas)

        # Check we can get the longest resource name.
        quota = table.select(table.c.id == 5).execute().first()
        self.assertEqual(quota['resource'], 'injected_file_content_bytes')

    def _check_228(self, engine, data):
        self.assertColumnExists(engine, 'compute_nodes', 'metrics')

        compute_nodes = oslodbutils.get_table(engine, 'compute_nodes')
        self.assertIsInstance(compute_nodes.c.metrics.type,
                              sqlalchemy.types.Text)

    def _post_downgrade_228(self, engine):
        self.assertColumnNotExists(engine, 'compute_nodes', 'metrics')

    def _check_229(self, engine, data):
        self.assertColumnExists(engine, 'compute_nodes', 'extra_resources')

        compute_nodes = oslodbutils.get_table(engine, 'compute_nodes')
        self.assertIsInstance(compute_nodes.c.extra_resources.type,
                              sqlalchemy.types.Text)

    def _post_downgrade_229(self, engine):
        self.assertColumnNotExists(engine, 'compute_nodes', 'extra_resources')

    def _check_230(self, engine, data):
        for table_name in ['instance_actions_events',
                           'shadow_instance_actions_events']:
            self.assertColumnExists(engine, table_name, 'host')
            self.assertColumnExists(engine, table_name, 'details')

        action_events = oslodbutils.get_table(engine,
                                              'instance_actions_events')
        self.assertIsInstance(action_events.c.host.type,
                              sqlalchemy.types.String)
        self.assertIsInstance(action_events.c.details.type,
                              sqlalchemy.types.Text)

    def _post_downgrade_230(self, engine):
        for table_name in ['instance_actions_events',
                           'shadow_instance_actions_events']:
            self.assertColumnNotExists(engine, table_name, 'host')
            self.assertColumnNotExists(engine, table_name, 'details')

    def _check_231(self, engine, data):
        self.assertColumnExists(engine, 'instances', 'ephemeral_key_uuid')

        instances = oslodbutils.get_table(engine, 'instances')
        self.assertIsInstance(instances.c.ephemeral_key_uuid.type,
                              sqlalchemy.types.String)
        self.assertTrue(db_utils.check_shadow_table(engine, 'instances'))

    def _post_downgrade_231(self, engine):
        self.assertColumnNotExists(engine, 'instances', 'ephemeral_key_uuid')
        self.assertTrue(db_utils.check_shadow_table(engine, 'instances'))

    def _check_232(self, engine, data):
        table_names = ['compute_node_stats', 'compute_nodes',
                       'instance_actions', 'instance_actions_events',
                       'instance_faults', 'migrations']
        for table_name in table_names:
            self.assertTableNotExists(engine, 'dump_' + table_name)

    def _check_233(self, engine, data):
        self.assertColumnExists(engine, 'compute_nodes', 'stats')

        compute_nodes = oslodbutils.get_table(engine, 'compute_nodes')
        self.assertIsInstance(compute_nodes.c.stats.type,
                              sqlalchemy.types.Text)

        self.assertRaises(sqlalchemy.exc.NoSuchTableError,
                          oslodbutils.get_table, engine, 'compute_node_stats')

    def _post_downgrade_233(self, engine):
        self.assertColumnNotExists(engine, 'compute_nodes', 'stats')

        # confirm compute_node_stats exists
        oslodbutils.get_table(engine, 'compute_node_stats')

    def _check_234(self, engine, data):
        self.assertIndexMembers(engine, 'reservations',
                                'reservations_deleted_expire_idx',
                                ['deleted', 'expire'])

    def _check_244(self, engine, data):
        volume_usage_cache = oslodbutils.get_table(
            engine, 'volume_usage_cache')
        self.assertEqual(64, volume_usage_cache.c.user_id.type.length)

    def _post_downgrade_244(self, engine):
        volume_usage_cache = oslodbutils.get_table(
            engine, 'volume_usage_cache')
        self.assertEqual(36, volume_usage_cache.c.user_id.type.length)

    def _pre_upgrade_245(self, engine):
        # create a fake network
        networks = oslodbutils.get_table(engine, 'networks')
        fake_network = {'id': 1}
        networks.insert().execute(fake_network)

    def _check_245(self, engine, data):
        networks = oslodbutils.get_table(engine, 'networks')
        network = networks.select(networks.c.id == 1).execute().first()
        # mtu should default to None
        self.assertIsNone(network.mtu)
        # dhcp_server should default to None
        self.assertIsNone(network.dhcp_server)
        # enable dhcp should default to true
        self.assertTrue(network.enable_dhcp)
        # share address should default to false
        self.assertFalse(network.share_address)

    def _post_downgrade_245(self, engine):
        self.assertColumnNotExists(engine, 'networks', 'mtu')
        self.assertColumnNotExists(engine, 'networks', 'dhcp_server')
        self.assertColumnNotExists(engine, 'networks', 'enable_dhcp')
        self.assertColumnNotExists(engine, 'networks', 'share_address')

    def _check_246(self, engine, data):
        pci_devices = oslodbutils.get_table(engine, 'pci_devices')
        self.assertEqual(1, len([fk for fk in pci_devices.foreign_keys
                                 if fk.parent.name == 'compute_node_id']))

    def _post_downgrade_246(self, engine):
        pci_devices = oslodbutils.get_table(engine, 'pci_devices')
        self.assertEqual(0, len([fk for fk in pci_devices.foreign_keys
                                 if fk.parent.name == 'compute_node_id']))

    def _check_247(self, engine, data):
        quota_usages = oslodbutils.get_table(engine, 'quota_usages')
        self.assertFalse(quota_usages.c.resource.nullable)

        pci_devices = oslodbutils.get_table(engine, 'pci_devices')
        self.assertTrue(pci_devices.c.deleted.nullable)
        self.assertFalse(pci_devices.c.product_id.nullable)
        self.assertFalse(pci_devices.c.vendor_id.nullable)
        self.assertFalse(pci_devices.c.dev_type.nullable)

    def _post_downgrade_247(self, engine):
        quota_usages = oslodbutils.get_table(engine, 'quota_usages')
        self.assertTrue(quota_usages.c.resource.nullable)

        pci_devices = oslodbutils.get_table(engine, 'pci_devices')
        self.assertFalse(pci_devices.c.deleted.nullable)
        self.assertTrue(pci_devices.c.product_id.nullable)
        self.assertTrue(pci_devices.c.vendor_id.nullable)
        self.assertTrue(pci_devices.c.dev_type.nullable)

    def _check_248(self, engine, data):
        self.assertIndexMembers(engine, 'reservations',
                                'reservations_deleted_expire_idx',
                                ['deleted', 'expire'])

    def _post_downgrade_248(self, engine):
        reservations = oslodbutils.get_table(engine, 'reservations')
        index_names = [idx.name for idx in reservations.indexes]
        self.assertNotIn('reservations_deleted_expire_idx', index_names)

    def _check_249(self, engine, data):
        # Assert that only one index exists that covers columns
        # instance_uuid and device_name
        bdm = oslodbutils.get_table(engine, 'block_device_mapping')
        self.assertEqual(1, len([i for i in bdm.indexes
                                 if [c.name for c in i.columns] ==
                                    ['instance_uuid', 'device_name']]))

    def _post_downgrade_249(self, engine):
        # The duplicate index is not created on downgrade, so this
        # asserts that only one index exists that covers columns
        # instance_uuid and device_name
        bdm = oslodbutils.get_table(engine, 'block_device_mapping')
        self.assertEqual(1, len([i for i in bdm.indexes
                                 if [c.name for c in i.columns] ==
                                    ['instance_uuid', 'device_name']]))

    def _check_250(self, engine, data):
        self.assertTableNotExists(engine, 'instance_group_metadata')
        self.assertTableNotExists(engine, 'shadow_instance_group_metadata')

    def _post_downgrade_250(self, engine):
        oslodbutils.get_table(engine, 'instance_group_metadata')
        oslodbutils.get_table(engine, 'shadow_instance_group_metadata')

    def _check_251(self, engine, data):
        self.assertColumnExists(engine, 'compute_nodes', 'numa_topology')
        self.assertColumnExists(engine, 'shadow_compute_nodes',
                                'numa_topology')

        compute_nodes = oslodbutils.get_table(engine, 'compute_nodes')
        shadow_compute_nodes = oslodbutils.get_table(engine,
                                                     'shadow_compute_nodes')
        self.assertIsInstance(compute_nodes.c.numa_topology.type,
                              sqlalchemy.types.Text)
        self.assertIsInstance(shadow_compute_nodes.c.numa_topology.type,
                              sqlalchemy.types.Text)

    def _post_downgrade_251(self, engine):
        self.assertColumnNotExists(engine, 'compute_nodes', 'numa_topology')
        self.assertColumnNotExists(engine, 'shadow_compute_nodes',
                                   'numa_topology')

    def _check_252(self, engine, data):
        oslodbutils.get_table(engine, 'instance_extra')
        oslodbutils.get_table(engine, 'shadow_instance_extra')
        self.assertIndexMembers(engine, 'instance_extra',
                                'instance_extra_idx',
                                ['instance_uuid'])

    def _post_downgrade_252(self, engine):
        self.assertTableNotExists(engine, 'instance_extra')
        self.assertTableNotExists(engine, 'shadow_instance_extra')

    def _check_253(self, engine, data):
        self.assertColumnExists(engine, 'instance_extra', 'pci_requests')
        self.assertColumnExists(
            engine, 'shadow_instance_extra', 'pci_requests')
        instance_extra = oslodbutils.get_table(engine, 'instance_extra')
        shadow_instance_extra = oslodbutils.get_table(engine,
                                                      'shadow_instance_extra')
        self.assertIsInstance(instance_extra.c.pci_requests.type,
                              sqlalchemy.types.Text)
        self.assertIsInstance(shadow_instance_extra.c.pci_requests.type,
                              sqlalchemy.types.Text)

    def _post_downgrade_253(self, engine):
        self.assertColumnNotExists(engine, 'instance_extra', 'pci_requests')
        self.assertColumnNotExists(engine, 'shadow_instance_extra',
                                   'pci_requests')

    def _check_254(self, engine, data):
        self.assertColumnExists(engine, 'pci_devices', 'request_id')
        self.assertColumnExists(
            engine, 'shadow_pci_devices', 'request_id')

        pci_devices = oslodbutils.get_table(engine, 'pci_devices')
        shadow_pci_devices = oslodbutils.get_table(
            engine, 'shadow_pci_devices')
        self.assertIsInstance(pci_devices.c.request_id.type,
                              sqlalchemy.types.String)
        self.assertIsInstance(shadow_pci_devices.c.request_id.type,
                              sqlalchemy.types.String)

    def _post_downgrade_254(self, engine):
        self.assertColumnNotExists(engine, 'pci_devices', 'request_id')
        self.assertColumnNotExists(
            engine, 'shadow_pci_devices', 'request_id')

    def _check_265(self, engine, data):
        # Assert that only one index exists that covers columns
        # host and deleted
        instances = oslodbutils.get_table(engine, 'instances')
        self.assertEqual(1, len([i for i in instances.indexes
                                 if [c.name for c in i.columns][:2] ==
                                    ['host', 'deleted']]))
        # and only one index covers host column
        iscsi_targets = oslodbutils.get_table(engine, 'iscsi_targets')
        self.assertEqual(1, len([i for i in iscsi_targets.indexes
                                 if [c.name for c in i.columns][:1] ==
                                    ['host']]))

    def _post_downgrade_265(self, engine):
        # The duplicated index is not created on downgrade, so this
        # asserts that only one index exists that covers columns
        # host and deleted
        instances = oslodbutils.get_table(engine, 'instances')
        self.assertEqual(1, len([i for i in instances.indexes
                                 if [c.name for c in i.columns][:2] ==
                                    ['host', 'deleted']]))
        # and only one index covers host column
        iscsi_targets = oslodbutils.get_table(engine, 'iscsi_targets')
        self.assertEqual(1, len([i for i in iscsi_targets.indexes
                                 if [c.name for c in i.columns][:1] ==
                                    ['host']]))


class TestNovaMigrationsSQLite(NovaMigrationsCheckers,
                               test_base.DbTestCase):
    pass


class TestNovaMigrationsMySQL(NovaMigrationsCheckers,
                              test_base.MySQLOpportunisticTestCase):
    def test_innodb_tables(self):
        with mock.patch.object(sa_migration, 'get_engine',
                               return_value=self.migrate_engine):
            sa_migration.db_sync()

        total = self.migrate_engine.execute(
            "SELECT count(*) "
            "FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA = '%(database)s'" %
            {'database': self.migrate_engine.url.database})
        self.assertTrue(total.scalar() > 0, "No tables found. Wrong schema?")

        noninnodb = self.migrate_engine.execute(
            "SELECT count(*) "
            "FROM information_schema.TABLES "
            "WHERE TABLE_SCHEMA='%(database)s' "
            "AND ENGINE != 'InnoDB' "
            "AND TABLE_NAME != 'migrate_version'" %
            {'database': self.migrate_engine.url.database})
        count = noninnodb.scalar()
        self.assertEqual(count, 0, "%d non InnoDB tables created" % count)


class TestNovaMigrationsPostgreSQL(NovaMigrationsCheckers,
                                   test_base.PostgreSQLOpportunisticTestCase):
    pass


class BaremetalMigrationsCheckers(NovaMigrationsCheckersBase):
    """Test sqlalchemy-migrate migrations."""
    TIMEOUT_SCALING_FACTOR = 2

    snake_walk = True
    downgrade = True

    @property
    def INIT_VERSION(self):
        return bm_migration.db_initial_version()

    @property
    def REPOSITORY(self):
        return repository.Repository(
            os.path.abspath(os.path.dirname(bm_migrate_repo.__file__)))

    @property
    def migration_api(self):
        return bm_sa_migration.versioning_api

    @property
    def migrate_engine(self):
        return self.engine

    def _skippable_migrations(self):
        # NOTE(danms): This is deprecated code, soon to be removed, so don't
        # obsess about tests here.
        return range(1, 100)

    def _pre_upgrade_002(self, engine):
        data = [{'id': 1, 'key': 'fake-key', 'image_path': '/dev/null',
                 'pxe_config_path': '/dev/null/', 'root_mb': 0, 'swap_mb': 0}]
        table = oslodbutils.get_table(engine, 'bm_deployments')
        engine.execute(table.insert(), data)
        return data

    def _check_002(self, engine, data):
        self.assertRaises(sqlalchemy.exc.NoSuchTableError,
                          oslodbutils.get_table, engine, 'bm_deployments')

    def _post_downgrade_004(self, engine):
        bm_nodes = oslodbutils.get_table(engine, 'bm_nodes')
        self.assertNotIn(u'instance_name', [c.name for c in bm_nodes.columns])

    def _check_005(self, engine, data):
        bm_nodes = oslodbutils.get_table(engine, 'bm_nodes')
        columns = [c.name for c in bm_nodes.columns]
        self.assertNotIn(u'prov_vlan_id', columns)
        self.assertNotIn(u'registration_status', columns)

    def _pre_upgrade_006(self, engine):
        nodes = oslodbutils.get_table(engine, 'bm_nodes')
        ifs = oslodbutils.get_table(engine, 'bm_interfaces')
        # node 1 has two different addresses in bm_nodes and bm_interfaces
        engine.execute(nodes.insert(),
                       [{'id': 1,
                         'prov_mac_address': 'aa:aa:aa:aa:aa:aa'}])
        engine.execute(ifs.insert(),
                       [{'id': 101,
                         'bm_node_id': 1,
                         'address': 'bb:bb:bb:bb:bb:bb'}])
        # node 2 has one same address both in bm_nodes and bm_interfaces
        engine.execute(nodes.insert(),
                       [{'id': 2,
                         'prov_mac_address': 'cc:cc:cc:cc:cc:cc'}])
        engine.execute(ifs.insert(),
                       [{'id': 201,
                         'bm_node_id': 2,
                         'address': 'cc:cc:cc:cc:cc:cc'}])

    def _check_006(self, engine, data):
        ifs = oslodbutils.get_table(engine, 'bm_interfaces')
        rows = ifs.select().\
                    where(ifs.c.bm_node_id == 1).\
                    execute().\
                    fetchall()
        self.assertEqual(len(rows), 2)
        rows = ifs.select().\
                    where(ifs.c.bm_node_id == 2).\
                    execute().\
                    fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['address'], 'cc:cc:cc:cc:cc:cc')

    def _post_downgrade_006(self, engine):
        ifs = oslodbutils.get_table(engine, 'bm_interfaces')
        rows = ifs.select().where(ifs.c.bm_node_id == 1).execute().fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['address'], 'bb:bb:bb:bb:bb:bb')

        rows = ifs.select().where(ifs.c.bm_node_id == 2).execute().fetchall()
        self.assertEqual(len(rows), 0)

    def _check_007(self, engine, data):
        bm_nodes = oslodbutils.get_table(engine, 'bm_nodes')
        columns = [c.name for c in bm_nodes.columns]
        self.assertNotIn(u'prov_mac_address', columns)

    def _check_008(self, engine, data):
        self.assertRaises(sqlalchemy.exc.NoSuchTableError,
                          oslodbutils.get_table, engine, 'bm_pxe_ips')

    def _post_downgrade_008(self, engine):
        oslodbutils.get_table(engine, 'bm_pxe_ips')

    def _pre_upgrade_010(self, engine):
        bm_nodes = oslodbutils.get_table(engine, 'bm_nodes')
        data = [{'id': 10, 'prov_mac_address': 'cc:cc:cc:cc:cc:cc'}]
        engine.execute(bm_nodes.insert(), data)

        return data

    def _check_010(self, engine, data):
        bm_nodes = oslodbutils.get_table(engine, 'bm_nodes')
        self.assertIn('preserve_ephemeral', bm_nodes.columns)

        default = engine.execute(
            sqlalchemy.select([bm_nodes.c.preserve_ephemeral])
                      .where(bm_nodes.c.id == data[0]['id'])
        ).scalar()
        self.assertEqual(default, False)

        bm_nodes.delete().where(bm_nodes.c.id == data[0]['id']).execute()

    def _post_downgrade_010(self, engine):
        bm_nodes = oslodbutils.get_table(engine, 'bm_nodes')
        self.assertNotIn('preserve_ephemeral', bm_nodes.columns)


class TestBaremetalMigrationsSQLite(BaremetalMigrationsCheckers,
                               test_base.DbTestCase):
    pass


class TestBaremetalMigrationsMySQL(BaremetalMigrationsCheckers,
                                   test_base.MySQLOpportunisticTestCase):
    pass


class TestBaremetalMigrationsPostgreSQL(
        NovaMigrationsCheckers,
        test_base.PostgreSQLOpportunisticTestCase):
    pass


class ProjectTestCase(test.NoDBTestCase):

    def test_all_migrations_have_downgrade(self):
        topdir = os.path.normpath(os.path.dirname(__file__) + '/../../../')
        py_globs = [os.path.join(topdir, "nova", "db", "sqlalchemy",
                                 "migrate_repo", "versions", "*.py"),
                    os.path.join(topdir, "nova", "virt", "baremetal", "db",
                                 "sqlalchemy", "migrate_repo", "versions",
                                 "*.py")]
        migrate_files = []
        for g in py_globs:
            migrate_files += list(glob.iglob(g))

        missing_downgrade = []
        for path in migrate_files:
            has_upgrade = False
            has_downgrade = False
            with open(path, "r") as f:
                for line in f:
                    if 'def upgrade(' in line:
                        has_upgrade = True
                    if 'def downgrade(' in line:
                        has_downgrade = True

                if has_upgrade and not has_downgrade:
                    fname = os.path.basename(path)
                    missing_downgrade.append(fname)

        helpful_msg = (_("The following migrations are missing a downgrade:"
                         "\n\t%s") % '\n\t'.join(sorted(missing_downgrade)))
        self.assertFalse(missing_downgrade, helpful_msg)
