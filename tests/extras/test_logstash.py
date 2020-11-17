from yellowbox.extras.logstash import LogstashService

# rebuilding the logstash service is an ongoing ticket, for now we just want to make sure it runs alright

def test_make(docker_client):
    with LogstashService.run(docker_client):
        pass