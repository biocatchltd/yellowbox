try:
    from yellowbox.extras.redis import RedisService
except ImportError:
    pass

# try:
#     from yellowbox.extras.logstash import YellowLogstash
# except ImportError:
#     pass

try:
    from yellowbox.extras.rabbit_mq import RabbitMQService
except ImportError:
    pass