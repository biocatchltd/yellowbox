from pytest import fixture, mark

from yellowbox.extras.kafka import KafkaService
from yellowbox.networks import connect, temp_network
from yellowbox.utils import docker_host_name

# this is a patch for a known issue where latest kafka won't start, actual fix OTW
KAFKA_IMAGE_TAG = ("bitnami/zookeeper:3.8.0", "bitnami/kafka:3.2.0")


@mark.parametrize('spinner', [True, False])
def test_make_kafka(docker_client, spinner):
    with KafkaService.run(docker_client, spinner=spinner, tag_or_images=KAFKA_IMAGE_TAG):
        pass


def test_kafka_works(docker_client):
    with KafkaService.run(docker_client, spinner=False, tag_or_images=KAFKA_IMAGE_TAG) as service:
        with service.consumer() as consumer, \
                service.producer() as producer:

            producer.send('test', b'hello world')

            consumer.subscribe('test')
            consumer.topics()
            consumer.seek_to_beginning()

            for msg in consumer:
                assert msg.value == b'hello world'
                break
            else:
                assert False


@mark.asyncio
async def test_kafka_works_async(docker_client):
    async with KafkaService.arun(docker_client, tag_or_images=KAFKA_IMAGE_TAG) as service:
        with service.consumer() as consumer, service.producer() as producer:

            producer.send('test', b'hello world')

            consumer.subscribe('test')
            consumer.topics()
            consumer.seek_to_beginning()

            for msg in consumer:
                assert msg.value == b'hello world'
                break
            else:
                assert False


@fixture(scope='module')
def kafka_service(docker_client):
    with KafkaService.run(docker_client, spinner=False, tag_or_images=KAFKA_IMAGE_TAG) as service:
        yield service


def test_kafka_sibling_network(docker_client, create_and_pull, kafka_service):
    with temp_network(docker_client) as network, \
            connect(network, kafka_service) as alias:
        container = create_and_pull(docker_client,
                                    "confluentinc/cp-kafkacat:latest",
                                    f"kafkacat -b {alias[0]}:{kafka_service.inner_port} -L")
        with connect(network, container):
            container.start()
            return_status = container.wait()
            assert return_status["StatusCode"] == 0


def test_kafka_sibling(docker_client, create_and_pull, kafka_service):
    container = create_and_pull(docker_client,
                                "confluentinc/cp-kafkacat:latest",
                                f"kafkacat -b {docker_host_name}:{kafka_service.outer_port} -L")
    container.start()
    return_status = container.wait()
    assert return_status["StatusCode"] == 0
