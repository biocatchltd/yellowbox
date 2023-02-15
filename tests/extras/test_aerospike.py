from pytest import fixture, mark

from yellowbox.extras.aerospike import AerospikeService


@mark.parametrize('spinner', [True, False])
def test_make_aerospike(docker_client, spinner):
    with AerospikeService.run(docker_client, spinner=spinner):
        pass


@mark.asyncio
async def test_make_aerospike_async(docker_client):
    async with AerospikeService.arun(docker_client):
        pass


@fixture(scope='module')
def aerospike_client(docker_client):
    with AerospikeService.run(docker_client) as service:
        yield service


@mark.asyncio
async def test_connection_works_async(aerospike_client):
    key = (aerospike_client.namespace, 'set1', 'record1')
    bins = {'a': '12'}
    with aerospike_client.client() as client:
        client.put(key, bins)
        (_, meta, resp) = client.select(key, ['a'])
    assert resp == bins
    assert meta['ttl']
    assert meta['gen']
