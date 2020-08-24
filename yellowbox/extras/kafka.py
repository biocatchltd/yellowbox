from contextlib import closing
from typing import ContextManager, cast, Union, Tuple

from docker import DockerClient
from kafka import KafkaConsumer, KafkaProducer
from kafka.errors import KafkaError

from yellowbox.containers import get_ports, SafeContainerCreator
from yellowbox.networks import anonymous_network
from yellowbox.subclasses import SingleEndpointService, RunnableWithContext
from yellowbox.utils import retry

KAFKA_DEFAULT_PORT = 9092


class KafkaService(SingleEndpointService, RunnableWithContext):
    def __init__(self, docker_client: DockerClient, tag_or_images: Union[str, Tuple[str, str]] = 'latest', **kwargs):
        if isinstance(tag_or_images, str):
            zookeeper_image = f"confluentinc/cp-zookeeper:{tag_or_images}"
            broker_image = f"confluentinc/cp-kafka:{tag_or_images}"
        else:
            zookeeper_image, broker_image = tag_or_images

        creator = SafeContainerCreator(docker_client)

        self.zookeeper = creator.create_and_pull(
            zookeeper_image, detach=True,
            publish_all_ports=True,
            environment={
                'ZOOKEEPER_CLIENT_PORT': '2181',
                'ZOOKEEPER_TICK_TIME': '2000'
            })

        self.broker = creator.create_and_pull(
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

        self.network = anonymous_network(docker_client)
        self.network.connect(self.zookeeper, aliases=["zk"])
        self.network.connect(self.broker)
        super().__init__((self.zookeeper, self.broker), **kwargs)

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

    def start(self):
        super().start()
        with retry(self.consumer, (KafkaError, ConnectionError, ValueError), attempts=15):
            pass
        return self

    def stop(self, signal='SIGKILL'):
        # difference in default signal
        self.network.disconnect(self.broker)
        self.network.disconnect(self.zookeeper)
        self.network.remove()
        super().stop(signal)

    @property
    def _single_endpoint(self):
        return self.broker
