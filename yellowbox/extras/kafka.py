from contextlib import closing
from typing import Any, ContextManager, cast
from uuid import uuid1
from warnings import warn

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

warn(
    "bitnami is gone! use `yellowbox-kraft` instead",
    DeprecationWarning,
    stacklevel=1,
)


class KafkaService(SingleEndpointService, RunMixin, AsyncRunMixin):
    def __init__(
        self,
        docker_client: DockerClient,
        tag_or_images: str | tuple[str, str] = "latest",
        inner_port=0,
        outer_port=0,
        bitnami_debug: bool = False,
        **kwargs,
    ):
        self.inner_port = inner_port or get_free_port()
        self.outer_port = outer_port or get_free_port()
        if isinstance(tag_or_images, str):
            zookeeper_image = f"bitnami/zookeeper:{tag_or_images}"
            broker_image = f"bitnami/kafka:{tag_or_images}"
        else:
            zookeeper_image, broker_image = tag_or_images

        # broker must have a known alias at creation time
        self.static_broker_alias = f"broker-{uuid1()}"

        creator = SafeContainerCreator(docker_client)

        extra_bitnami_env = {}
        if bitnami_debug:
            extra_bitnami_env["BITNAMI_DEBUG"] = "true"

        self.zookeeper = creator.create_and_pull(
            zookeeper_image,
            detach=True,
            publish_all_ports=True,
            environment={
                "ZOOKEEPER_CLIENT_PORT": "2181",
                "ZOOKEEPER_TICK_TIME": "2000",
                "ALLOW_ANONYMOUS_LOGIN": "yes",
                **extra_bitnami_env,
            },
        )

        self.broker = creator.create_and_pull(
            broker_image,
            ports={
                str(self.outer_port): ("0.0.0.0", self.outer_port),
                str(self.inner_port): ("0.0.0.0", self.inner_port),
            },
            publish_all_ports=True,
            detach=True,
            environment={
                "KAFKA_CFG_ADVERTISED_LISTENERS": f"INNER://{self.static_broker_alias}:{self.inner_port},"
                f"OUTER://localhost:{self.outer_port}",
                "KAFKA_CFG_ZOOKEEPER_CONNECT": "zk/2181",
                "ALLOW_PLAINTEXT_LISTENER": "yes",
                "KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP": "INNER:PLAINTEXT,OUTER:PLAINTEXT",
                "KAFKA_INTER_BROKER_LISTENER_NAME": "INNER",
                "KAFKA_CFG_LISTENERS": f"INNER://:{self.inner_port},OUTER://:{self.outer_port}",
                "KAFKA_ENABLE_KRAFT": "false",
                **extra_bitnami_env,
            },
        )

        self.network = anonymous_network(docker_client)
        self.network.connect(self.zookeeper, aliases=["zk"])
        self.network.connect(self.broker, aliases=[self.static_broker_alias])
        super().__init__((self.zookeeper, self.broker), **kwargs)

    def connection_port(self):
        self.broker.reload()
        ports = get_ports(self.broker)
        return ports[self.outer_port]

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

    def start(self, retry_spec: RetrySpec | None = None):
        super().start()
        retry_spec = retry_spec or RetrySpec(attempts=20)
        with retry_spec.retry(self._consumer, (KafkaError, ConnectionError, ValueError, TypeError)):
            pass
        return self

    async def astart(self, retry_spec: RetrySpec | None = None) -> None:
        super().start()
        retry_spec = retry_spec or RetrySpec(attempts=20)
        with await retry_spec.aretry(self._consumer, (KafkaError, ConnectionError, ValueError, TypeError)):
            pass

    def stop(self, signal="SIGKILL"):
        # difference in default signal
        self.network.disconnect(self.broker)
        self.network.disconnect(self.zookeeper)
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
