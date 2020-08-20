from contextlib import closing
from typing import ContextManager, cast, Union, Tuple

from docker import DockerClient
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

from yellowbox import connect
from yellowbox.containers import get_ports, create_and_pull
from yellowbox.networks import temp_network
from yellowbox.service import ContainerService
from yellowbox.utils import retry

KAFKA_DEFAULT_PORT = 9092


class KafkaService(ContainerService):
    @property
    def zookeeper(self):
        return self.containers[0]

    @property
    def broker(self):
        return self.containers[1]

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

    def start(self):
        super().start()
        with retry(self.consumer, (KafkaError, ConnectionError, ValueError), attempts=15):
            pass
        return self

    def stop(self, signal='SIGKILL'):
        # difference in default signal
        super().stop(signal)

    def _end_facing_containers(self):
        yield self.broker

    @classmethod
    def _make_containers(cls, docker_client: DockerClient, tag_or_images: Union[str, Tuple[str, str]] = 'latest'):
        if isinstance(tag_or_images, str):
            zookeeper_image = f"confluentinc/cp-zookeeper:{tag_or_images}"
            broker_image = f"confluentinc/cp-kafka:{tag_or_images}"
        else:
            zookeeper_image, broker_image = tag_or_images
            
        zk_container = create_and_pull(
            docker_client,
            zookeeper_image, detach=True,
            publish_all_ports=True,
            environment={
                'ZOOKEEPER_CLIENT_PORT': '2181',
                'ZOOKEEPER_TICK_TIME': '2000'
            })
        yield zk_container
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
        yield b_container

    @classmethod
    def from_docker(cls, docker_client: DockerClient, remove=True, **kwargs):
        self: KafkaService = super().from_docker(docker_client, remove, **kwargs)

        network = self.exit_stack.enter_context(temp_network(docker_client))
        self.exit_stack.enter_context(connect(network, self.zookeeper, aliases=["zk"]))
        self.exit_stack.enter_context(connect(network, self.broker))

        return self
