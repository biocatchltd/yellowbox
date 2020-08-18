from docker.models.networks import Network

from yellowbox import connect
from yellowbox.containers import get_ports, get_aliases, create_and_pull
from yellowbox.networks import temp_network

from typing import ContextManager, cast, Union, Tuple
from contextlib import contextmanager, closing

from docker import DockerClient
from docker.models.containers import Container
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

from yellowbox.utils import _get_spinner, retry
from yellowbox.service import YellowService

KAFKA_DEFAULT_PORT = 9092


class KafkaService(YellowService):
    def __init__(self, zk_container: Container, broker_container: Container,
                 *, _auto_remove: bool = False) -> None:
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
        self.broker.start()
        self.zookeeper.start()
        self.broker.reload()
        self.zookeeper.reload()
        with retry(self.consumer, (KafkaError, ConnectionError, ValueError),
                   attempts=15):
            pass
        return self

    def stop(self):
        if self.is_alive():
            self.zookeeper.kill("SIGKILL")
            self.broker.kill("SIGKILL")
            self._reload()
            if self._auto_remove:
                self.zookeeper.remove()
                self.broker.remove()

    def connect(self, network: Network):
        network.connect(self.broker)
        self.broker.reload()
        return get_aliases(self.broker, network)

    def disconnect(self, network: Network):
        network.disconnect(self.broker)
        self.broker.reload()

    @classmethod
    @contextmanager
    def run(cls, docker_client: DockerClient, image: Union[str, Tuple[str, str]] = 'latest',
            spinner=True, auto_remove=True) -> ContextManager['KafkaService']:
        if isinstance(image, str):
            zookeeper_image = f"confluentinc/cp-zookeeper:{image}"
            broker_image = f"confluentinc/cp-kafka:{image}"
        else:
            zookeeper_image, broker_image = image

        spinner = _get_spinner(spinner)
        with spinner("Fetching kafka..."):
            zk_container = create_and_pull(
                docker_client,
                zookeeper_image, detach=True,
                publish_all_ports=True,
                environment={
                    'ZOOKEEPER_CLIENT_PORT': '2181',
                    'ZOOKEEPER_TICK_TIME': '2000'
                })
            b_container = create_and_pull(
                docker_client,
                broker_image,
                ports={'9092': ('0.0.0.0', 9092)},
                publish_all_ports=True,
                detach=True,
                environment={
                    "KAFKA_ADVERTISED_HOST_NAME": "localhost",
                    'KAFKA_ADVERTISED_LISTENERS': 'PLAINTEXT://localhost:9092',
                    "KAFKA_ZOOKEEPER_CONNECT": "zk/2181",
                    "KAFKA_OPTS": "-Djava.net.preferIPv4Stack=True"
                })

        with temp_network(docker_client) as network, \
                connect(network, zk_container, aliases=["zk"]), \
                connect(network, b_container):
            with cls(zk_container, b_container, _auto_remove=auto_remove) as service:
                # Attempt pinging redis until it's up and running
                with spinner("Waiting for kafka to start..."):
                    service.start()
                yield service
