from contextlib import closing
from time import sleep

from confluent_kafka import Consumer as ConfluentConsumer, Producer as ConfluentProducer
from pytest import fixture, mark

from yellowbox.extras.kafka import KafkaService
from yellowbox.networks import connect, temp_network
from yellowbox.utils import DOCKER_EXPOSE_HOST, docker_host_name

KAFKA_IMAGE_TAG = "latest"


@mark.parametrize("bitnami_debug", [True, False])
def test_make_kafka(docker_client, bitnami_debug):
    with KafkaService.run(docker_client, spinner=False, tag_or_images=KAFKA_IMAGE_TAG, bitnami_debug=bitnami_debug):
        pass


def get_consumer(kafka_service: KafkaService):
    return closing(
        ConfluentConsumer(
            {
                "bootstrap.servers": f"{DOCKER_EXPOSE_HOST}:{kafka_service.connection_port()}",
                "security.protocol": "PLAINTEXT",
                "group.id": "yb-0",
            }
        )
    )


def get_producer(kafka_service: KafkaService):
    return ConfluentProducer(
        {
            "bootstrap.servers": f"{DOCKER_EXPOSE_HOST}:{kafka_service.connection_port()}",
            "security.protocol": "PLAINTEXT",
        }
    )


def test_kafka_works(docker_client):
    with KafkaService.run(docker_client, spinner=False, tag_or_images=KAFKA_IMAGE_TAG) as service, get_consumer(
        service
    ) as consumer:
        producer = get_producer(service)
        producer.produce("test", b"hello world")
        producer.flush()

        sleep(1)

        def on_assign(consumer, partitions):
            for p in partitions:
                p.offset = -2
            consumer.assign(partitions)

        consumer.subscribe(["test"], on_assign=on_assign)
        msg = consumer.poll(10)
        assert msg is not None
        assert not msg.error()
        assert msg.value() == b"hello world"


@mark.asyncio
async def test_kafka_works_async(docker_client):
    async with KafkaService.arun(docker_client, tag_or_images=KAFKA_IMAGE_TAG) as service:
        with get_consumer(service) as consumer:
            producer = get_producer(service)
            producer.produce("test", b"hello world async")
            producer.flush()

            sleep(1)

            def on_assign(consumer, partitions):
                for p in partitions:
                    p.offset = -2
                consumer.assign(partitions)

            consumer.subscribe(["test"], on_assign=on_assign)
            msg = consumer.poll(10)
            assert msg is not None
            assert not msg.error()
            assert msg.value() == b"hello world async"


@fixture(scope="module")
def kafka_service(docker_client):
    with KafkaService.run(docker_client, spinner=False, tag_or_images=KAFKA_IMAGE_TAG) as service:
        yield service


def test_kafka_sibling_network(docker_client, create_and_pull, kafka_service):
    with temp_network(docker_client) as network, connect(network, kafka_service) as alias:
        container = create_and_pull(
            docker_client, "confluentinc/cp-kafkacat:latest", f"kafkacat -b {alias[0]}:{kafka_service.inner_port} -L"
        )
        with connect(network, container):
            container.start()
            return_status = container.wait()
            assert return_status["StatusCode"] == 0


def test_kafka_sibling(docker_client, create_and_pull, kafka_service):
    container = create_and_pull(
        docker_client,
        "confluentinc/cp-kafkacat:latest",
        f"kafkacat -b {docker_host_name}:{kafka_service.outer_port} -L",
    )
    container.start()
    return_status = container.wait()
    assert return_status["StatusCode"] == 0
