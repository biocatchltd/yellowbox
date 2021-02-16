# Yellowbox Changelog
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
