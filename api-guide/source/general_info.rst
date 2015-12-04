=========================
Key Compute API Concepts
=========================

The OpenStack Compute API is defined as a ReSTful HTTP service. The API
takes advantage of all aspects of the HTTP protocol (methods, URIs,
media types, response codes, etc.) and providers are free to use
existing features of the protocol such as caching, persistent
connections, and content compression among others.

Providers can return information identifying requests in HTTP response
headers, for example, to facilitate communication between the provider
and client users.

OpenStack Compute is a compute service that provides server capacity in
the cloud. Compute Servers come in different flavors of memory, cores,
disk space, and CPU, and can be provisioned in minutes. Interactions
with Compute Servers can happen programmatically with the OpenStack
Compute API.

User Concepts
==============

To use the OpenStack Compute API effectively, you should understand
several key concepts:

-  **Server**

   A virtual machine (VM) instance in the compute system. Flavor and
   image are requisite elements when creating a server. A name for the server
   is also required.

   For more details, such as server actions and server metadata,
   please see: :doc:`server_concepts`

-  **Flavor**

   An available hardware configuration for a server. Each flavor has a
   unique combination of disk space, memory capacity and priority for
   CPU time.

-  **Image**

   A collection of files used to create or rebuild a server. Operators
   provide a number of pre-built OS images by default. You may also
   create custom images from cloud servers you have launched. These
   custom images are useful for backup purposes or for producing “gold”
   server images if you plan to deploy a particular server configuration
   frequently.

-  **Key Pair**

   An ssh or x509 keypair that can be injected into a server. This allows you
   to connect to your server once it has been created without having to use a
   password. If you don't specify a key pair, Nova will create a root password
   for you, and return it in plain text in the server create response.

-  **Volume**

   A block storage device that Nova can use as permanent storage. When a server
   is created it has some disk storage available, but that is considered
   ephemeral, as it is destroyed when the server is destroyed. A volume can be
   attached to a server, then later detached and used by another server.
   Volumes are created and managed by the Cinder service, though the Nova API
   can proxy some of these calls.

-  **Quotas**

   An upper bound on the amount of resources any individual tenant may consume.
   Quotas can be used to limit the number of servers a tenant creates, or the
   amount of disk space consumed, so that no one tenant can overwhelm the
   system and prevent normal operation for others. Changing quotas is an
   admin-level action.

-  **Rate Limiting**

   Please see :doc:`limits`

-  **Availability zone**

   A grouping of host machines that can be used to control where a new server
   is created. There is some confusion about this, as the name "availability
   zone" is used in other clouds, such as Amazon Web Services, to denote a
   physical separation of server locations that can be used to distribute cloud
   resources for fault tolerance in case one zone is unavailable for any
   reason. Such a separation is possible in Nova if an admin carefully sets up
   availability zones for that, but it is not the default.

Networking Concepts
-------------------

In this section we focus on this related to networking.

-  **Port**

   TODO

-  **Floating IPs, Pools and DNS**

   TODO

-  **Security Groups**

   TODO

-  **Cloudpipe**

   TODO

-  **Extended Networks**

   TODO


Administrator Concepts
=======================

Come APIs are largely focused on administration of Nova, and generally focus
on compute hosts rather than servers.

-  **Hosts**

   TODO

-  **Host Actions**

   TODO

-  **Hypervisors**

   TODO

-  **Aggregates**

   TODO

-  **Migrations**

   TODO

-  **Certificates**

   TODO

Error Handling
==============

The Compute API follows the standard HTTP error code conventions.

TODO - add details including: request id, migrations and instance actions.

Relationship with Volume API
=============================

Here we discuss about Cinder's API and how Nova users volume uuids.

TODO - add more details.

Relationship with Image API
=============================

Here we discuss about Glance's API and how Nova users image uuids.
We also discuss how Nova proxies setting image metadata.

TODO - add more details.

Interactions with Neutron and Nova-Network
==========================================

We talk about how networking can be provided be either by Nova or Neutron.

Here we discuss about Neutron's API an how Nova users port uuids.
We also discuss Nova automatically creating ports, proxying security groups,
and proxying floating IPs. Also talk about the APIs we do not proxy.

TODO - add more details.
