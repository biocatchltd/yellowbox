from kafka import TopicPartition
from pytest import mark

from yellowbox.containers import get_aliases, create_and_pull
from yellowbox.extras.kafka import KafkaService
from yellowbox.networks import temp_network, connect


@mark.parametrize('spinner', [True, False])
def test_make_kafka(docker_client, spinner):
    with KafkaService.run(docker_client, spinner=spinner):
        pass


def test_kafka_works(docker_client):
    with KafkaService.run(docker_client, spinner=False) as service:
        with service.consumer() as consumer, \
                service.producer() as producer:

            producer.send('test', b'hello world')

            partition = TopicPartition('test', 0)
            consumer.assign([partition])
            consumer.seek_to_beginning()

            for msg in consumer:
                assert msg.value == b'hello world'
                break
            else:
                assert False


def test_kafka_sibling_network(docker_client):
    with temp_network(docker_client) as network, \
            KafkaService.run(docker_client, spinner=False) as service, \
            connect(network, service) as alias:
        container = create_and_pull(docker_client,
                                    "confluentinc/cp-kafkacat:latest",
                                    f"kafkacat -b {alias[0]}:9092 -L")
        with connect(network, container):
            container.start()
            return_status = container.wait()
            assert return_status["StatusCode"] == 0


def test_kafka_sibling(docker_client, host_ip):
    with KafkaService.run(docker_client, spinner=False):
        container = create_and_pull(docker_client,
                                    "confluentinc/cp-kafkacat",
                                    f"kafkacat -b {host_ip}:9092 -L")
        container.start()
        return_status = container.wait()
        assert return_status["StatusCode"] == 0
