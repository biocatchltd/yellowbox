from pytest import fail, fixture, mark

from yellowbox.extras.kafka import KafkaService
from yellowbox.networks import connect, temp_network
from yellowbox.utils import docker_host_name

KAFKA_IMAGE_TAG = "latest"


@mark.parametrize("bitnami_debug", [True, False])
def test_make_kafka(docker_client, bitnami_debug):
    with KafkaService.run(docker_client, spinner=False, tag_or_images=KAFKA_IMAGE_TAG, bitnami_debug=bitnami_debug):
        pass


def test_kafka_works(docker_client):
    with KafkaService.run(
        docker_client, spinner=False, tag_or_images=KAFKA_IMAGE_TAG
    ) as service, service.consumer() as consumer, service.producer() as producer:
        producer.send("test", b"hello world")

        consumer.subscribe("test")
        consumer.topics()
        consumer.seek_to_beginning()

        for msg in consumer:
            assert msg.value == b"hello world"
            break
        else:
            fail("No message received")


@mark.asyncio
async def test_kafka_works_async(docker_client):
    async with KafkaService.arun(docker_client, tag_or_images=KAFKA_IMAGE_TAG) as service:
        with service.consumer() as consumer, service.producer() as producer:
            producer.send("test", b"hello world")

            consumer.subscribe("test")
            consumer.topics()
            consumer.seek_to_beginning()

            for msg in consumer:
                assert msg.value == b"hello world"
                break
            else:
                fail("No message received")


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
