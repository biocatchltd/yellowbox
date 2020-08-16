from kafka import TopicPartition
from pytest import mark

from yellowbox import YellowNetwork
from yellowbox.extras.kafka import YellowKafka


@mark.parametrize('spinner', [True, False])
def test_make_kafka(docker_client, spinner):
    with YellowKafka.run(docker_client, spinner=spinner):
        pass


def test_kafka_works(docker_client):
    with YellowKafka.run(docker_client, spinner=False) as service:
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
    with YellowNetwork.create(docker_client) as network, \
            YellowKafka.run(docker_client, spinner=False) as service, \
            network.connect(service.broker) as alias:
        container = docker_client.containers.create("confluentinc/cp-kafkacat",
                                                    f"kafkacat -b {alias[0]}:9092 -L")
        with network.connect(container):
            container.start()
            return_status = container.wait()
            assert return_status["StatusCode"] == 0


def test_kafka_sibling(docker_client):
    with YellowKafka.run(docker_client, spinner=False):
        container = docker_client.containers.create("confluentinc/cp-kafkacat",
                                                    "kafkacat -b host.docker.internal:9092 -L")
        container.start()
        return_status = container.wait()
        assert return_status["StatusCode"] == 0
