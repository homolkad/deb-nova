..
      Copyright 2009-2015 OpenStack Foundation

      Licensed under the Apache License, Version 2.0 (the "License"); you may
      not use this file except in compliance with the License. You may obtain
      a copy of the License at

          http://www.apache.org/licenses/LICENSE-2.0

      Unless required by applicable law or agreed to in writing, software
      distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
      WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
      License for the specific language governing permissions and limitations
      under the License.

===========
Compute API
===========

The nova project has a ReSTful HTTP service called the OpenStack Compute API.
Through this API, the service provides massively scalable, on demand,
self-service access to compute resources. Depending on the deployment those
compute resources might be Virtual Machines, Physical Machines or Containers.

We welcome feedback, comments, and bug reports at
`bugs.launchpad.net/nova <http://bugs.launchpad.net/nova>`__.


Intended audience
=================

This guide assists software developers who want to develop applications
using the OpenStack Compute API. To use this information, you should
have access to an account from an OpenStack Compute provider, or have
access to your own deployment, and you should also be familiar with the
following concepts:

*  OpenStack Compute service
*  ReSTful web services
*  HTTP/1.1
*  JSON data serialization formats


Versions and Extensions
=======================

Following the Liberty release, every Nova deployment should have
the following endpoints:

* / - list of available versions
* /v2.0 - the first version of the Compute API, uses extensions
* /v1.1 - an alias for v2.0 for backwards compatibility
* /v2.1 - same API, except uses microversions

For more information on how to make use the API, how to get the endpoint
from the keystone service catalog and pick what version of the API to use,
please read:

.. toctree::
    :maxdepth: 1

    versions
    extensions
    microversions


Key API concepts
================

The following documents go into more details about the key concepts of the
OpenStack Compute API:

.. toctree::
    :maxdepth: 2

    general_info
    server_concepts
    authentication
    faults
    limits
    links_and_references
    paginated_collections
    polling_changes-since_parameter
    request_and_response_formats


Full reference
==============

For a full reference listing for the OpenStack Compute API, please see:

* `*Compute API reference (CURRENT)* <http://developer.openstack.org/api-ref-compute-v2.1.html>`__.
