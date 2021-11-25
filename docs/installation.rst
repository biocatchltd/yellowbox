.. _installation:

Installation
------------

Yellowbox is available on PyPI:

.. code-block:: console

    $ pip install yellowbox

In order to run specific extras (like redis, or webserver), you will also need to install the package's relevant extra.
Current extras are:

    * :mod:`azure (for running an Azurite container) <extras.azure_storage>`
    * :mod:`kafka (for running a Kafka message broker) <extras.kafka>`
    * :mod:`postgresql (for running a postgreSQL) <extras.postgresql>`
    * :mod:`rabbit (for running a RabbitMQ message queue) <extras.rabbit_mq>`
    * :mod:`redis (for running a Redis database) <extras.redis>`
    * :mod:`vault (for running a Vault secret storage) <extras.vault>`
    * :mod:`webserver (for running an http/websocket server) <extras.webserver>`
    * :mod:`websocket (for running a websocket server, deprecated) <extras.websocket>`

For development purposes, you can also install the ``dev`` extra, which will install all of the above extras.