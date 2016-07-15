# needs:fix_opt_description
# needs:check_deprecation_status
# needs:check_opt_group_and_type
# needs:fix_opt_description_indentation
# needs:fix_opt_registration_consistency


# Copyright 2016 OpenStack Foundation
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

import copy

from keystoneauth1 import loading as ks_loading
from oslo_config import cfg

NEUTRON_GROUP = 'neutron'

neutron_group = cfg.OptGroup(NEUTRON_GROUP, title='Neutron Options')
neutron_options = None

neutron_opts = [
    cfg.StrOpt(
        'url',
        default='http://127.0.0.1:9696',
        help="""
This option specifies the URL for connecting to Neutron.

Possible values:

  * The default is 'http://127.0.0.1:9696' however any valid URL that
    points to the Neutron API service is appropriate here. This typically
    matches the URL returned for the 'network' service type from the
    Keystone service catalog.

Related options:

  * None
"""),
    cfg.StrOpt(
        'region_name',
        default='RegionOne',
        help="""
Region name for connecting to Neutron in admin context.

This option is used in multi-region setups. If there are two Neutron
servers running in two regions in two different machines, then two
services need to be created in Keystone with two different regions and
associate corresponding endpoints to those services. When requests are made
to Keystone, the Keystone service uses the region_name to determine the
region the request is coming from.

Possible values:

  * Any string representing a region name.

Related options:

  * None
"""),
    cfg.StrOpt(
        'ovs_bridge',
         default='br-int',
         help="""
Specifies the name of an integration bridge interface used by OpenvSwitch.
This option is used only if Neutron does not specify the OVS bridge name.

Possible values:

  * Any string representing OVS bridge name.
  * default value is 'br-int'

Related options:

  * None
"""),
    cfg.IntOpt(
        'extension_sync_interval',
         default=600,
         help="""
Number of seconds to wait before querying Neutron for extensions.
After this number of seconds the next time Nova needs to create a resource in
Neutron it will requery Neutron for the extensions that it has loaded.

Possible values:

  * Any positive Integer value
  * default value is 600

Related options:

  * None
"""),
]

metadata_proxy_opts = [
    cfg.BoolOpt(
        "service_metadata_proxy",
        default=False,
        help="""
When set to True, this option indicates that Neutron will be used to proxy
metadata requests and resolve instance ids. Otherwise, the instance ID must be
passed to the metadata request in the 'X-Instance-ID' header.

Possible values:

    True, False (default)

* Services which consume this:

    ``nova-api``

* Related options:

    metadata_proxy_shared_secret
"""),
     cfg.StrOpt(
        "metadata_proxy_shared_secret",
        default="",
        secret=True,
        help="""
This option holds the shared secret string used to validate proxy requests to
Neutron metadata requests. In order to be used, the
'X-Metadata-Provider-Signature' header must be supplied in the request.

Possible values:

    Any string

* Services which consume this:

    ``nova-api``

* Related options:

    service_metadata_proxy
"""),
]

ALL_OPTS = (neutron_opts + metadata_proxy_opts)

deprecations = {'cafile': [cfg.DeprecatedOpt('ca_certificates_file',
                                             group=NEUTRON_GROUP)],
                'insecure': [cfg.DeprecatedOpt('api_insecure',
                                               group=NEUTRON_GROUP)],
                'timeout': [cfg.DeprecatedOpt('url_timeout',
                                              group=NEUTRON_GROUP)]}


def _gen_opts_from_plugins():
    opts = copy.deepcopy(neutron_options)
    opts.insert(0, ks_loading.get_auth_common_conf_options()[0])
    # NOTE(dims): There are a lot of auth plugins, we just generate
    # the config options for a few common ones
    plugins = ['password', 'v2password', 'v3password']
    for name in plugins:
        plugin = ks_loading.get_plugin_loader(name)
        for plugin_option in ks_loading.get_auth_plugin_conf_options(plugin):
            for option in opts:
                if option.name == plugin_option.name:
                    break
            else:
                opts.append(plugin_option)
    opts.sort(key=lambda x: x.name)
    return opts


def register_opts(conf):
    global neutron_options
    conf.register_group(neutron_group)
    conf.register_opts(ALL_OPTS, group=neutron_group)
    neutron_options = ks_loading.register_session_conf_options(
        conf, NEUTRON_GROUP, deprecated_opts=deprecations)
    ks_loading.register_auth_conf_options(conf, NEUTRON_GROUP)


def list_opts():
    return {
        neutron_group: ALL_OPTS + _gen_opts_from_plugins()
    }
