from collections.abc import Iterable
from contextlib import contextmanager
from os import environ, getenv
from typing import Any
from warnings import warn

import requests
from docker import DockerClient

from yellowbox.containers import create_and_pull_with_defaults, get_ports
from yellowbox.retry import RetrySpec
from yellowbox.subclasses import AsyncRunMixin, RunMixin, SingleContainerService
from yellowbox.utils import DOCKER_EXPOSE_HOST, docker_host_name

FAKE_GCS_DEFAULT_PORT = 4443


class FakeGoogleCloudStorage(SingleContainerService, RunMixin, AsyncRunMixin):
    def __init__(
        self,
        docker_client: DockerClient,
        image: str = "fsouza/fake-gcs-server:1.42",
        scheme: str = "https",
        command: str = "",
        *,
        container_create_kwargs: dict[str, Any] | None = None,
        **kwargs,
    ):
        # note that fake-gcs-server 1.43.0 has a bug https://github.com/fsouza/fake-gcs-server/issues/1034
        command = f"-scheme {scheme} {command}"
        self.scheme = scheme
        container = create_and_pull_with_defaults(
            docker_client, image, command, _kwargs=container_create_kwargs, publish_all_ports=True
        )
        super().__init__(container, **kwargs)

    def client_port(self):
        return get_ports(self.container)[FAKE_GCS_DEFAULT_PORT]

    def local_url(self, scheme: str | None = ...):  # type: ignore[assignment]
        ret = f"{DOCKER_EXPOSE_HOST}:{self.client_port()}"
        if scheme is ...:
            scheme = self.scheme
        if scheme:
            ret = f"{self.scheme}://{ret}"
        return ret

    def container_url(self, hostname: str, scheme: str | None = ...):  # type: ignore[assignment]
        ret = f"{hostname}:{FAKE_GCS_DEFAULT_PORT}"
        if scheme is ...:
            scheme = self.scheme
        if scheme:
            ret = f"{self.scheme}://{ret}"
        return ret

    def host_url(self, scheme: str | None = ...):  # type: ignore[assignment]
        ret = f"{docker_host_name}:{self.client_port()}"
        if scheme is ...:
            scheme = self.scheme
        if scheme:
            ret = f"{self.scheme}://{ret}"
        return ret

    def start(self, retry_spec: RetrySpec | None = None):
        super().start()
        url = self.local_url() + "/storage/v1/b"
        retry_spec = retry_spec or RetrySpec(attempts=15)
        retry_spec.retry(
            lambda: requests.get(url, verify=False).raise_for_status(), requests.exceptions.RequestException
        )
        return self

    async def astart(self, retry_spec: RetrySpec | None = None):
        super().start()
        url = self.local_url() + "/storage/v1/b"
        retry_spec = retry_spec or RetrySpec(attempts=15)
        await retry_spec.aretry(
            lambda: requests.get(url, verify=False).raise_for_status(), requests.exceptions.RequestException
        )

    @contextmanager
    def patch_gcloud_aio(self):
        from gcloud.aio.storage import __version__ as gcloud_aio_version  # noqa: PLC0415

        if not gcloud_aio_version.startswith("7."):
            # for newer gcloud_aio, we can just adjust the environment
            warn(
                "newer gcloud versions should be patched directly by setting the environment variable "
                "STORAGE_EMULATOR_HOST to service.local_url()",
                stacklevel=1,
            )
            prev_env = getenv("STORAGE_EMULATOR_HOST")
            environ["STORAGE_EMULATOR_HOST"] = self.local_url(None)
            yield
            if prev_env is None:
                del environ["STORAGE_EMULATOR_HOST"]
            else:
                environ["STORAGE_EMULATOR_HOST"] = prev_env
            return
        import gcloud.aio.storage.storage as gcloud_module  # noqa: PLC0415

        previous_state = (
            gcloud_module.API_ROOT,
            gcloud_module.API_ROOT_UPLOAD,
            gcloud_module.VERIFY_SSL,
            gcloud_module.STORAGE_EMULATOR_HOST,
        )
        (
            gcloud_module.API_ROOT,
            gcloud_module.API_ROOT_UPLOAD,
            gcloud_module.VERIFY_SSL,
            gcloud_module.STORAGE_EMULATOR_HOST,
        ) = (
            self.local_url() + "/storage/v1/b",
            self.local_url() + "/upload/storage/v1/b",
            False,
            self.local_url(scheme=""),
        )
        yield
        (
            gcloud_module.API_ROOT,
            gcloud_module.API_ROOT_UPLOAD,
            gcloud_module.VERIFY_SSL,
            gcloud_module.STORAGE_EMULATOR_HOST,
        ) = previous_state

    def create_bucket(self, bucket_name: str) -> dict[str, Any]:
        url = self.local_url()

        resp = requests.post(url + "/storage/v1/b", json={"name": bucket_name}, verify=False)
        resp.raise_for_status()

        return resp.json()

    def clear_bucket(self, bucket_name: str, prefix: str | None = None) -> Iterable[str]:
        url = self.local_url()
        params = {}
        if prefix:
            params["prefix"] = prefix
        page_token = None
        ret = []
        while True:
            if page_token:
                params["pageToken"] = page_token
            resp = requests.get(url + f"/storage/v1/b/{bucket_name}/o", params=params, verify=False)
            resp.raise_for_status()
            data = resp.json()
            for item in data["items"]:
                ret.append(item["name"])
                requests.delete(url + f"/storage/v1/b/{bucket_name}/o/{item['name']}", verify=False).raise_for_status()
            if "nextPageToken" in data:
                page_token = data["next_page_token"]
            else:
                break
        return ret

    def delete_bucket(self, bucket_name: str, force: bool = False, missing_ok: bool = False):
        url = self.local_url()

        try:
            if force:
                # we need to delete all the objects in the bucket
                self.clear_bucket(bucket_name)

            resp = requests.delete(url + f"/storage/v1/b/{bucket_name}", verify=False)
            resp.raise_for_status()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code != 404 or not missing_ok:
                raise
