# Yellowbox
![Test YellowBox](https://github.com/biocatchltd/yellowbox/workflows/Test%20YellowBox/badge.svg?branch=master)
[![Coverage](https://codecov.io/github/biocatchltd/yellowbox/coverage.svg?branch=master)](https://codecov.io/github/biocatchltd/yellowbox?branch=master)


Yellowbox makes it easy to run docker containers as part of black box tests.
## Examples
Say you want to run a blackbox test on a service that depends on a redis server.
```python
from docker import DockerClient
from yellowbox.extras import RedisService

def test_black_box():
    docker_client = DockerClient.from_env()
    with RedisService.run(docker_client) as redis:
        redis_port = redis.client_port()  # this the host port the redis
        ...  # run your black box test here
    # yellowbox will automatically close the service when exiting the scope

def test_black_box_with_initial_data():
    # you can use the service's built-in utility functions to
    # easily interoperate the service
    docker_client = DockerClient.from_env()
    with RedisService.run(docker_client) as redis:
        with redis.client() as client:
            client.set("foo","bar")
        ...
```
## Supported Extras
The currently supported built-in services are:
* Kafka: `from yellowbox.extras import KafkaService`
    * currently, the kafka service supports only plaintext protocol, and always binds to the host port 9092
* Logstash: `from yellowbox.extras import LogstashService`
* RabbitMQ: `from yellowbox.extras import RabbitMQService`
* Redis: `from yellowbox.extras import RedisService`

Note: all these extras require additional dependencies as specified in the project's `extras`.
## Networks
Yellowbox also makes it easy to set up temporary docker networks, so that different containers and services can
communicate directly.
```python
from docker import DockerClient
from yellowbox import temp_network, connect
from yellowbox.extras import RabbitMQService

def test_network():
    docker_client = DockerClient.from_env()
    with RabbitMQService.run(docker_client) as rabbit, \
        temp_network(docker_client) as network, \
        connect(network, rabbit) as alias:
        # yellow's "connect" function connects between a network and a
        # Container/YellowService, retrieves the container's alias(es) on 
        # the network, and disconnects the two when done
        another_container = docker_client.containers.create("my-image", 
            environment={"RABBITMQ_HOSTNAME": alias[0]}
        )
        with connect(network, another_container):
            another_container.start()
            another_container.wait()
```
## As Pytest Fixtures
Both yellow services and networks can be used fluently with `pytest` fixures
```python
from docker import DockerClient
from pytest import fixture

from yellowbox.extras import RedisService

@fixture
def docker_client():
    docker_client = DockerClient.from_env()
    yield docker_client
    docker_client.close()

@fixture
def redis_service(docker_client):
    with RedisService.run(docker_client) as service:
        yield service

def black_box(redis_service):
    # run your test with the redis service provided
    ...
```
since docker container may take some time to set up, it's advisable to set their scope to at least `"module"`
## Extending Yellow
Users can create their own Yellow Service classes by implementing the `YellowService` abstract class.
If the service encapsulates only a single container, the `SingleContainerService` class already implements
the necessary methods.

## License
Yellowbox is registered under the MIT public license
