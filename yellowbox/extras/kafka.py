from typing import ContextManager, cast
from contextlib import contextmanager, closing

from docker import DockerClient
from docker.models.containers import Container
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

from yellowbox import YellowNetwork
from yellowbox.context_managers import get_spinner, killing
from yellowbox.utils import retry, get_container_ports
from yellowbox.service import YellowService

KAFKA_DEFAULT_PORT = 9092


class YellowKafka(YellowService):
    def __init__(self, zk_container: Container, broker_container: Container, network: YellowNetwork):
        super().__init__()
        self.zookeeper = zk_container
        self.broker = broker_container
        self.network = network

    def connection_port(self):
        self.broker.reload()
        ports = get_container_ports(self.broker)
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

    def reload(self):
        self.zookeeper.reload()
        self.broker.reload()

    def is_alive(self):
        self.reload()
        return self.zookeeper.status.lower() not in ('exited', 'stopped') \
               and self.broker.status.lower() not in ('exited', 'stopped')

    def kill(self, signal='SIGKILL'):
        self.zookeeper.kill(signal)
        self.broker.kill(signal)

    @classmethod
    @contextmanager
    def run(cls, docker_client: DockerClient, tag='latest', spinner=True) -> ContextManager['YellowKafka']:
        spinner = get_spinner(spinner)
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
