from docker import DockerClient
from docker.models.containers import Container

from yellowbox.extras import RedisService
from yellowbox.extras.redis import REDIS_DEFAULT_PORT


def test_no_connect(docker_client: DockerClient):
    with RedisService.run(docker_client) as redis:
        command = f'nc -z localhost {redis.client_port()}'
        container: Container = docker_client.containers.create('bash:latest', command)
        container.start()
        return_status = container.wait()
        assert return_status["StatusCode"] != 0


def test_connect_parent(docker_client: DockerClient):
    with RedisService.run(docker_client) as redis:
        command = f'nc -z host.docker.internal {redis.client_port()}'
        container: Container = docker_client.containers.create('bash:latest', command)
        container.start()
        return_status = container.wait()
        assert return_status["StatusCode"] == 0
#
#
# def test_connect_shared_network(docker_client: DockerClient):
#     with YellowNetwork.create(docker_client) as network:
#         with YellowRedis.run(docker_client) as redis, \
#                 network.connect(redis) as aliases:
#             command = f'nc -z {aliases[0]} {REDIS_DEFAULT_PORT}'
#             container: Container = docker_client.containers.create('bash:latest', command)
#             with network.connect(container):
#                 container.start()
#                 return_status = container.wait()
#             assert return_status["StatusCode"] == 0
