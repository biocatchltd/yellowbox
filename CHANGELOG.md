# Yellowbox Changelog
## 0.8.7
### Deprecated
* this will be the last release to support python 3.7
### Added
* recorded WS and HTTP messages now also include the time they were received
### Fixed
* webservers will now wait a maximum of 5 seconds for the service thread to shut down.
### Changed
* before they are used, local images are now checked against remote repositories to see if they are up to date.
* in python 3.12, confluent-kafka is used instead of kafka-python
* the type hint for `astart` has been changed to `object` to indicate that the response is not used.
### Internal
* changed documentation theme to furo
* upgraded minimum frozenlist and aiohttp dependencies for python 3.12
* changed internal formatter to ruff
* fixed some tye hints that had implicit `Optional` types
* added `overload` annotation for `containers.upload_file`
* added 3.12 to unittests
* using 'Trust server certificate' option in sqlcmd (for testing)
## 0.8.6
### Deprecated
* the `file` parameter of build_image
### Added
* added `container_create_kwargs` to all `SingleContainerService` extras.
* build_image_async for asynchronous image building
* `RecordedHTTPRequest.text` to get the request body as text
* `RecordedHTTPRequest.json` to get the request body as json
* `ExpectedHTTPRequest.json_submap` to expect a submap of the request body as json
### Fixed
* fixed import of exceptions in aerospike that would cause an error with newer clients
* fixed `forbid_implicit_head_verb` being incorrectly named in the `class_http_endpoint` overload.
### Documentation
* fixed documentation of MockWSEndpoint.side_effect
## 0.8.5
### Fixed
* `RunMixin` and `AsyncRunMixin` no longer subclass `ContainerService`
## 0.8.4
### Deprecated
* `DockerfileParseException` should be renamed to `DockerfileParseError`
### Changed
* `DockerfileParseException` has been renamed to `DockerfileParseError` (legacy alias preserved)
* `RunMixin` and `AsyncRunMixin` are now subclasses of `ContainerService`
* vault: default tag changed to hashicorp/vault:latest
### Fixed
* fixed issue where latest bitnami kafka would not start
### Added
* extras/kafka: added `bitnami_debug` parameter to enable bitnami debug.
* the "pending_exception" method and "raise_from_pending" method of webservice are now public, but 
undocumented. Their API is likely to change.
* `AsyncRunMixin` noe exit asynchronously
## 0.8.3
### Changed
* docker_expose_host is no longer inferred for WSL2
## 0.8.2
### Fixed
* support for gcloud-aio-storage 8.0.0
* support for sqlalchemy2
## 0.8.1
### Added
* documentation to the aerospike service
### Changed
* revamped aerospike service
## 0.8.0
### Added
* added the `Aerospike` extra, to set up an aerospike enterprise container.
### Fixed
* Fixed issue in webserver where if a client connection would disconnect abrubtly, the entire 
  server would stop working. This is probably not the expected behaviour of the mocked service so it
  has been changed to ignore these events. 
### Added
* `AzuriteService` added `host_connection_string` and `host_endpoint_url` properties
* `allow_abrubt_disconnect` for websocket webserver endpoints.
## 0.7.8
### Added
* image names in docker-build can now be manually tagged
### Fixed
* the default fake-gcs-server has been locked to 1.42, since the altest has a bug.
## 0.7.7
### Fixed
* all connections to localhost are now patched appropriately for WSL2 (experimental)
### Internal
* simplified the azure-storage dependency
## 0.7.6
### Changed
* `None` is no longer an acceptable port for webserver
* Changed webserver's default port from `None` to `0`.
### Fixed
* fixed issue when starting up webserver with the uvicorn debugger enabled
## 0.7.5
### Added
* support for python 3.11
* added the `fake_gcs` extra, to set up a fake google cloud storage container.
### Internal
* removed deprecated function from hvac tests
## 0.7.4
### Fixed
* all dependencies have been unlocked for major changes (`^X` => `>=X`)
## 0.7.3
### Fixed
* the type hints for `class_http_endpoint` and `class_ws_endpoint` have been changed to allow any side effect 
(including methods).
### Changed
* When an `MockHTTPEndpoint`/`MockWSEndpoint` raises an exception, the traceback is printed.
## 0.7.2
### Added
* `removing` context wrapper, that ensures containers will be removed after exiting.
* `MSSQLService`, a new service that can be used to create a new MSSQL database.
* `database` mixing method, use to create and manage database within an sql service. In use both in `MSSQLService` and
  `PostgreSQLService`.
* `PostgreSQLService`'s `*_connection_string` methods now also accept an `options` argument.
* `PostgreSQLService`'s constructor now accept the `local_driver` and `local_options` arguments. 
### Deprecated
* `PostgreSQLService`'s `engine` and `connection` methods are now deprecated, create an sqlalchemy engine and
 connection manually instead.
### Fixed
* rabbitmq service startup can now handle `AMQPConnectorException`.
* `azure-blob-storage` of versions `12.11.0` and up can now be installed.
* header type hinting for expected webservice requests
* headers in recorded webservice requests are now always lowercase
### Changed
* redis' default retry attempts changed from 10 to 15.
### Internal
* tests have been streamlined to be faster and more stable
* If a helper container fails during tests, it will not be removed
## 0.7.1
### Added
* pytest integration, with the `docker_client` fixture
* `AsyncRunMixin` class, to allow starting up services asynchronously
  * Note: Currently, only waiting for services to start is asynchronous.
* `webserver.verbose_http_side_effect` to print all http traffic through an endpoint.
* Webserver: all endpoint factory functions now also accept a `name` parameter, to manually set the name of an endpoint.
* `RetrySpec.aretry` to retry a function but to wait asynchronously between attempts. 
### Changed
* `docker_client` function renamed to `open_docker_client` (legacy alias kept for backwards compatibility)
* `extras.BlobStorageService` renamed to `extras.AzuriteService` (legacy alias kept for backwards compatibility)
* Webserver no longer uses uvicorn's logging. This can be reverted by manually setting the `log_config` in `WebServer`'s constructor.
  To note endpoint access, use `webserver.verbose_http_side_effect`.
### Deprecated
* `yellowbox.docker_client` should be replaced with `yellowbox.open_docker_client` 
* `yellowbox.extras.BlobStorageService` should be replaced with `yellowbox.extras.AzuriteService`
## 0.7.0
### Removed
* the method ``RecordedHTTPRequests.has_requests_any_order`` has been removed.
### Fixed
* webserver: fixed websocket endpoint not working for starlette 0.18
### Changed
* igraph is no longer a requirement for webserver
## 0.6.9
### Changed
* the "_all" extra has been renamed to "dev"
* Added minimum versions for uvicorn and starlette
### Fixed
* webserver: forbid_head_verb fixed to forbid_implicit_head_verb in the type annotation.
### Internal
* fixed the dependency for igraph
## 0.6.8
### Fixed
* Fixed issue where webserver would refuse connections from containers on some platforms
* Webserver logs now show the client address
## 0.6.7
### Added
* MockHttpEndpoint and MockWSEndpoint added to webserver package
* Webserver: `class_http_endpoint` and `class_ws_endpoint`, WebServer subclasses automatically add all
class_*_endpoints to their instances when started
* Webserver: `iter_side_effects` to create a side effect that delegates to other per request.
### Changed
* Webserver: `PORT_ACCESS_MAX_RETRIES` renamed to `_PORT_ACCESS_MAX_RETRIES`
### Fixed
* removed the flask dependency
## 0.6.6
### Deprecated
* `HttpService` is now deprecated in favor of `WebService`
* `WebsocketService` is now deprecated in favor of `WebService`
### Added
* `WebService`, a new service to mock http and websocket server
* PostgreSQLService: added method host_connection_string to connect to the database from another container.
* Added tests for python 3.10
* `extras.vault.VaultService`, A new service for Hashicorp Vault.
### Fixed
* `websocket-client` has been downgraded to a dev dependency
## 0.6.5
### Added
* build_image ContextManager, to create an image from dockerfile
* docker_client can be imported directly from yellowbox package
## 0.6.4
### Fixed
* Changed rabbitmq configuration to use config files instead of env vars. Allowing usage of rabbitmq 3.9.0 and upwards.
## 0.6.3
### Fixed
* A bug in newer docker desktop versions that prevented RabbitMQ from starting up. Fixed.
* improved WSL detection to detect WSL2 releases
### Changed
* Cached engine was deleted for postgresql engine
* the "all" extra was renamed to "_all" to discourage non-development usages
### Internal
* Changed linters to mypy and isort
## 0.6.1
### Added
* HttpServer: the request handler can now be returned by callbacks to handle the request manually
## 0.6.0
### Added
* Option in RunMixin.run to accept network parameter
* Utility function to access docker client from WSL (docker_client in yellowbox.docker_utils)
### Fixed
* docker_host_name was broken within WSL
* Services can now be disconnected after they are stopped
## 0.5.1
### Added
* New WebSocketService to emulate Websocket servers.
## 0.5.0
### Added
* HttpServer: added `path_params` method to parse path parameters of a request.
### Fixed
* `TypeError` when accessing body of a request without a body. (now `handler.body()` of a request returns `None`)
* Excluded usage of any azure-storage-blob version above 12.7.0 as a tempfix.
### Internal
* changed `local_url` to use 127.0.0.1, to earn a speedup in some cases.
## 0.4.1
### Fixed
* Excluded usage of a broken version of azure-storage-blob package: 12.7.0
## 0.4.0
### Removed
* `clean_slate` methods are now gone, replaced with `reset_state`.
### Changed
* now retry is only a a parameter for select services, including all container services.
### Added
* New PostgreSQL service.
* `clear_state` to reset the data on select services.
## 0.3.2
### Added
* new properties in `BlobStorageService`: `endpoint_url`, `container_endpoint_url`, `account_credentials`.
### Fixed
* `RabbitMQService` suppress `ConnectionError`s on startup retries.
## 0.3.1
### Fixed
* `LogstashService` correctly reconstructs fragmented data.
## 0.3.0
### Changed
* Revamped LogstashService. It now fakes the Logstash json_lines protocol.
### Removed
* YellowService no longer has `connect` & `disconnect`. They are now delegated to `ContainerService`.
## 0.2.1
### Fixed
* logstash is now fixed
* all `retry_specs` parameters have been replaced with `retry_spec`
## 0.2.0
### Added
* all extra-containers with retrying startup mechanisms now support retry
 arguments in run
* a new extra: HTTPService, to easily create and mock http services
### Fixed
* redis's minimum version was changed to 3.3.0
### Changed
* create_and_pull will throw an error if no tag is specified
## 0.1.1
### Removed
* Since logstash has no "latest" image tag, the default image name has been removed.
### Changed
* Project now uses poetry instead of setup.py
* `YellowKafka` has been renamed to `KafkaService`
* `YellowLogstash` has been renamed to `LogstashService`
* extra dependencies are now starred to increase compatibility.
* Major overhaul to class hierarchy. All "extras" services can now only be initialized using docker client.
* `KafkaService` Now accepts teo ports to bind to, one for external communication via docker host, and another for internal communication via networks.
### Added
* Short examples in the readme
* This changelog
* automatic testing in github repository
* the default package can now be used to import some common names.
* `KafkaService` can now accept the names of the zookeeper and broker images
* `connect` now accepts keyword arguments, forwarded to the inner connect call.
* `RabbitMQService` tests now include vhost cases.
* Utility functions `download_file` and `upload_file`
* `RabbitMQService` now has multiple management-related methods (useful for debugging)
* `BlobStorageService`: a new extra service that holds azurite blob storage.
* The `clean_slate` context for `RedisService` and `RabbitService` that ensures the service is in an empty state before and after the context.
* `RedisService`'s new `set_state` method to easily set the state of the internal redis DB.
* automatic linting on every PR
* all extra client methods also accept `**kwargs` forwarded to client constructor
* `BlobStorageService.connection_string` for obtaining the connection string to the container's blob storage.
* `BlobStorageService.container_connection_string` for obtaining the connection string to be used inside a docker network.
* `containers.short_id(container)` retrieves the short id of a container.
### Fixed
* Bug where tests failed on linux because linux doesn't have `host.docker.internal`. Linux now uses IP `172.17.0.1` to target host.
* Bug where services would fail if trying to run a non-pulled image.
* Issue where the rabbit service test was not tries on the main tag.
* restored some network tests
* Bug in `connect` where networks would try to disconnect containers that have since been removed.
* Bug in `KafkaService` where the service would try to kill if the containers even if they are no longer running.
* Bug in `KafkaService` where the network would not disconnect from the server after.
* Bug in `RabbitMQService` where the container would no kill cleanly
* When removing a container, the volumes are now removed as well.
## 0.0.1
initial release
