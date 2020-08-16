from docker.models.networks import Network

from yellowbox.containers import get_ports


@@ -0,0 +1,88 @@
from typing import ContextManager, cast
from contextlib import contextmanager, closing

from docker import DockerClient
from docker.models.containers import Container
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

from yellowbox.utils import _get_spinner, retry
from yellowbox.service import YellowService

KAFKA_DEFAULT_PORT = 9092


class YellowKafka(YellowService):
    def __init__(self, zk_container: Container, broker_container: Container,
                 network: Network ,*, _auto_remove: bool = False) -> None:
        super().__init__()
        self.zookeeper = zk_container
        self.broker = broker_container
        self._auto_remove = _auto_remove

    def connection_port(self):
        self.broker.reload()
        ports = get_ports(self.broker)
        return ports[KAFKA_DEFAULT_PORT]

    def consumer(self) -> ContextManager[KafkaConsumer]:
        port = self.connection_port()
        return cast(
            'ContextManager[KafkaConsumer]',
            closing(KafkaConsumer(bootstrap_servers=[f'localhost:{port}'], security_protocol="PLAINTEXT"))
        )

    def producer(self) -> ContextManager[KafkaProducer]:
        port = self.connection_port()
        return cast(
            'ContextManager[KafkaProducer]',
            closing(KafkaProducer(bootstrap_servers=[f'localhost:{port}'], security_protocol="PLAINTEXT"))
        )

    def _reload(self):
        self.zookeeper.reload()
        self.broker.reload()

    def is_alive(self):
        self._reload()
        return self.zookeeper.status.lower() not in ('exited', 'stopped') \
               and self.broker.status.lower() not in ('exited', 'stopped')

    def start(self):
        self.zookeeper.start()
        self.container.reload()
        return self

    def stop(self):
        self.zookeeper.kill("SIGKILL")
        self.broker.kill("SIGKILL")
        self._reload()
        if self._auto_remove:
            self.zookeeper.remove()
            self.broker.remove()

    def connect(self, network: Network):
        network.connect(self.broker)

    def disconnect(self, network: Network):
        network.disconnect(self.broker)

    @classmethod
    def from_docker(cls, docker_client: DockerClient, tag='latest'):
        zk_container = docker_client.containers.create(
            f"confluentinc/cp-zookeeper:{tag}", publish_all_ports=True, detach=True,                 environment={
                    'ZOOKEEPER_CLIENT_PORT': '2181',
                    'ZOOKEEPER_TICK_TIME': '2000'
                })

        b_container = docker_client.containers.create(
            f"confluentinc/cp-kafka:{tag}",
            ports={'9092': ('0.0.0.0', 9092)},
            publish_all_ports=True,
            detach=True,
            environment={
                "KAFKA_ADVERTISED_HOST_NAME": "localhost",
                'KAFKA_ADVERTISED_LISTENERS': 'PLAINTEXT://localhost:9092',
                "KAFKA_ZOOKEEPER_CONNECT": "zk/2181",
                "KAFKA_OPTS": "-Djava.net.preferIPv4Stack=True"
            })
        return cls(zk_container, b_container, _auto_remove=True)

    @classmethod
    @contextmanager
    def run(cls, docker_client: DockerClient, tag='latest', spinner=True) -> ContextManager['YellowKafka']:
        spinner = _get_spinner(spinner)
        with spinner("Fetching kafka..."):
            zk_container = docker_client.containers.run(
                f"confluentinc/cp-zookeeper:{tag}", detach=True,
                publish_all_ports=True,
                environment={
                    'ZOOKEEPER_CLIENT_PORT': '2181',
                    'ZOOKEEPER_TICK_TIME': '2000'
                })
            b_container = docker_client.containers.run(
                f"confluentinc/cp-kafka:{tag}",
                ports={'9092': ('0.0.0.0', 9092)},
                publish_all_ports=True,
                detach=True,
                environment={
                    "KAFKA_ADVERTISED_HOST_NAME": "localhost",
                    'KAFKA_ADVERTISED_LISTENERS': 'PLAINTEXT://localhost:9092',
                    "KAFKA_ZOOKEEPER_CONNECT": "zk/2181",
                    "KAFKA_OPTS": "-Djava.net.preferIPv4Stack=True"
                })
        with YellowNetwork.create(docker_client) as network, \
                network.connect(zk_container, aliases=["zk"]), network.connect(b_container), \
                killing(zk_container), killing(b_container):
            self = cls(zk_container, b_container, network)
            # Attempt pinging redis until it's up and running
            with spinner("Waiting for kafka to start..."):
                with retry(self.consumer, (KafkaError, ConnectionError, ValueError, KeyError), attempts=15):
                    pass

            yield self

