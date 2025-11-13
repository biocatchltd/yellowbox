import warnings
from contextlib import closing
from typing import Any, ContextManager, Optional, Tuple, Union, cast
from uuid import uuid1

from docker import DockerClient

try:
    from kafka import KafkaConsumer, KafkaProducer
    from kafka.errors import KafkaError
except ImportError:
    KafkaConsumer = KafkaProducer = None
    # python3.12 uses confluent_kafka
    from confluent_kafka import Consumer as ConfluentConsumer
    from confluent_kafka.error import KafkaError

from yellowbox.containers import SafeContainerCreator, get_ports
from yellowbox.networks import anonymous_network
from yellowbox.retry import RetrySpec
from yellowbox.subclasses import AsyncRunMixin, RunMixin, SingleEndpointService
from yellowbox.utils import DOCKER_EXPOSE_HOST, get_free_port

__all__ = ["KafkaService"]


class KafkaService(SingleEndpointService, RunMixin, AsyncRunMixin):
    def __init__(
        self,
        docker_client: DockerClient,
        tag_or_images: Union[str, Tuple[str, str]] = "latest",
        inner_port: Optional[int] = None,
        outer_port: int = 0,
        bitnami_debug: Optional[bool] = None,
        debug: bool = False,
        **kwargs,
    ):
        if inner_port is not None:
            warnings.warn(
                "`inner_port` is deprecated and ignored. "
                "Apache Kafka uses fixed internal port 9092."
                "To remove this warning, remove `inner_port` from your call.",
                DeprecationWarning,
                stacklevel=2,
            )
        if bitnami_debug is not None:
            warnings.warn(
                "`bitnami_debug` is deprecated. To remove this warning, use `debug` parameter instead.",
                DeprecationWarning,
                stacklevel=2,
            )
            debug = bitnami_debug
        if not isinstance(tag_or_images, str):
            tag_or_images = tag_or_images[1]
            warnings.warn(
                f"Zookeeper is no longer supported. Using {tag_or_images} as Kafka broker image. "
                f"To remove this warning, pass a single broker image string instead of a tuple.",
                DeprecationWarning,
                stacklevel=2,
            )

        self.inner_port = 9092  # Standard Kafka internal port for broker communication (same as for KRaft)
        self.outer_port = outer_port or get_free_port()  # External port for host connection

        broker_image = tag_or_images if ":" in tag_or_images else f"apache/kafka:{tag_or_images}"

        # broker must have a known alias at creation time
        self.static_broker_alias = f"broker-{uuid1()}"

        creator = SafeContainerCreator(docker_client)

        # Base KRaft mode configuration
        environment = {
            "KAFKA_NODE_ID": "1",
            "KAFKA_PROCESS_ROLES": "broker,controller",
            "KAFKA_LISTENERS": "PLAINTEXT://0.0.0.0:9092,CONTROLLER://0.0.0.0:9093",
            "KAFKA_ADVERTISED_LISTENERS": f"PLAINTEXT://localhost:{self.outer_port}",
            "KAFKA_CONTROLLER_LISTENER_NAMES": "CONTROLLER",
            "KAFKA_LISTENER_SECURITY_PROTOCOL_MAP": "CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT",
            "KAFKA_CONTROLLER_QUORUM_VOTERS": "1@localhost:9093",
            "KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR": "1",
            "KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR": "1",
            "KAFKA_TRANSACTION_STATE_LOG_MIN_ISR": "1",
            "KAFKA_INTER_BROKER_LISTENER_NAME": "PLAINTEXT",
            "KAFKA_LOG_DIRS": "/tmp/kraft-combined-logs",
        }

        # Enable debug logging if requested
        if debug:
            environment["KAFKA_LOG4J_ROOT_LOGLEVEL"] = "DEBUG"
            environment["KAFKA_TOOLS_LOG4J_LOGLEVEL"] = "DEBUG"

        self.broker = creator.create_and_pull(
            broker_image,
            ports={
                "9092/tcp": ("0.0.0.0", self.outer_port),
            },
            publish_all_ports=True,
            detach=True,
            environment=environment,
        )

        self.network = anonymous_network(docker_client)
        self.network.connect(self.broker, aliases=[self.static_broker_alias])
        super().__init__((self.broker,), **kwargs)

    def connection_port(self):
        self.broker.reload()
        # After connecting to custom network, port mappings may not appear in NetworkSettings.Ports
        # but they're still there in the HostConfig
        hostconfig_ports = self.broker.attrs.get("HostConfig", {}).get("PortBindings", {}) or {}

        # Try HostConfig first, then NetworkSettings
        port_key = f"{self.inner_port}/tcp"
        if hostconfig_ports.get(port_key):
            return int(hostconfig_ports[port_key][0]["HostPort"])

        # Fallback to NetworkSettings
        ports = get_ports(self.broker)
        if self.inner_port in ports:
            return ports[self.inner_port]

        # If still not found, just return outer_port as it should match
        return self.outer_port

    def _consumer(self, **kwargs) -> ContextManager[Any]:
        port = self.connection_port()
        if KafkaConsumer is not None:
            return closing(
                KafkaConsumer(
                    bootstrap_servers=[f"{DOCKER_EXPOSE_HOST}:{port}"], security_protocol="PLAINTEXT", **kwargs
                )
            )
        else:
            return closing(
                ConfluentConsumer(
                    {
                        "bootstrap.servers": f"{DOCKER_EXPOSE_HOST}:{port}",
                        "security.protocol": "PLAINTEXT",
                        "group.id": "yb-0",
                        **kwargs,
                    }
                )
            )

    def consumer(self, **kwargs) -> ContextManager[KafkaConsumer]:
        if KafkaConsumer is None:
            raise ImportError("kafka-python is not installed")
        return self._consumer(**kwargs)

    def producer(self, **kwargs) -> ContextManager[KafkaProducer]:
        if KafkaProducer is None:
            raise ImportError("kafka-python is not installed")
        port = self.connection_port()
        return cast(
            "ContextManager[KafkaProducer]",
            closing(
                KafkaProducer(
                    bootstrap_servers=[f"{DOCKER_EXPOSE_HOST}:{port}"], security_protocol="PLAINTEXT", **kwargs
                )
            ),
        )

    def start(self, retry_spec: Optional[RetrySpec] = None):
        super().start()
        retry_spec = retry_spec or RetrySpec(attempts=20)
        with retry_spec.retry(self._consumer, (KafkaError, ConnectionError, ValueError, TypeError)):
            pass
        return self

    async def astart(self, retry_spec: Optional[RetrySpec] = None) -> None:
        super().start()
        retry_spec = retry_spec or RetrySpec(attempts=20)
        with await retry_spec.aretry(self._consumer, (KafkaError, ConnectionError, ValueError, TypeError)):
            pass

    def stop(self, signal="SIGKILL"):
        # difference in default signal
        self.network.disconnect(self.broker)
        self.network.remove()
        super().stop(signal)

    def connect(self, network, *, aliases=(), **kwargs):
        if not isinstance(aliases, list):
            aliases = list(aliases)
        aliases.append(self.static_broker_alias)
        kwargs["aliases"] = aliases
        return super().connect(network, **kwargs)

    @property
    def _single_endpoint(self):
        return self.broker
