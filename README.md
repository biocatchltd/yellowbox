# Yellowbox
![Test YellowBox](https://github.com/biocatchltd/yellowbox/workflows/Test%20YellowBox/badge.svg?branch=master)
[![Coverage](https://codecov.io/github/biocatchltd/yellowbox/coverage.svg?branch=master)](https://codecov.io/github/biocatchltd/yellowbox?branch=master)


Yellowbox makes it easy to run docker containers as part of black box tests.

**Documentation:** https://yellowbox.readthedocs.io/

---
## Examples
Say you want to run a blackbox test on a service that depends on a redis server.

```python
from yellowbox.clients import docker_client
from yellowbox.extras import RedisService


def test_black_box():
  with docker_client() as docker_client, RedisService.run(docker_client) as redis:
    redis_port = redis.client_port()  # this the host port the redis
    ...  # run your black box test here
  # yellowbox will automatically close the service when exiting the scope


def test_black_box_with_initial_data():
  # you can use the service's built-in utility functions to
  # easily interoperate the service
  with docker_client() as docker_client,
          RedisService.run(docker_client) as redis,
          redis.client() as client:
    client.set("foo", "bar")
  ...
```

## License
Yellowbox is registered under the MIT public license
