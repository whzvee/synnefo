Upgrade to Synnefo v0.17
^^^^^^^^^^^^^^^^^^^^^^^^

Upgrade Steps
=============

The upgrade to v0.17 consists of the following steps:

0. Install the latest Synnefo, Archipelago and Ganeti packages. For the
   following steps, the Cyclades API must be down.

1. Run the migrations for the Cyclades DB:

   .. code-block:: console

     cyclades.host$ snf-manage migrate db

2. Update the names of Archipelago volumes:

   .. code-block:: console

     cyclades.host$ /usr/lib/synnefo/tools/rename_unique_name_of_disks \
                      --parallel


   The ``--parallel`` switch is optional, but it will greatly improve the
   script's running time.

3. Create helper VMs in all Ganeti clusters.

   Helper VMs are required for the deletion of detachable volumes. These helper
   VMs must be attributed to a user, and thus an admin account must be created.
   The account can be the same as the one used for the upload of the images.

   Before creating the helper VMs, you need to bring the Cyclades API back up,
   but firewall it from the outside world.

   In order to facilitate the creation of helper VMs, we have created an
   snf-manage command for this purpose:

   .. code-block:: console

     cyclades.host$ snf-manage helper-servers-sync --flavor <flavor_id> \
                      --image <image_id> --user <admin_user_id> \
                      --password *****


   The above script will create a helper server in all online Ganeti clusters
   and will immediately shut it down so that it reserves no resources.

   .. note::

     You must choose a flavor which has an Archipelago disk template.

4. Once the syncing of the helper servers has finished, you can remove the
   firewall from the Cyclades API.

5. On the node where pithos UI (`snf-pithos-webclient`) package is installed, 
   remove existing pithos UI package and install the `snf-ui-app` package. 
   The `snf-pithos-webclient` package is deprecated and should no longer be 
   installed in any of your service nodes.
   
   .. code-block:: console
   
     (pithos-ui-node)$ apt-get remove snf-pithos-webclient --purge
     (pithos-ui-node)$ apt-get install snf-ui-app

  Edit `/etc/synnefo/20-snf-ui-cloudbar.conf` and
  `/etc/synnefo/20-snf-ui-settings.conf` to match your deployment
  configuration.

  Notice that the new UI application no longer redirects service root paths 
  to the pithos UI endpoint. If you want to preserve this behaviour consider 
  adding a rewrite rule such as the following in your apache vhost 
  configuration.
  
  .. code-block:: console
    
    RewriteRule ^/$ /ui [R=302]
   