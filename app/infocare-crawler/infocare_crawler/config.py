"""
config
======

"""
import tanker.config
import typing
from tanker.config import fields

SCHEMA = {
    #: Running environment
    "ENVIRONMENT": fields.OneOfField(
        {"local", "test", "development", "production", }, default="local",
    ),
    #: Login id
    "LOGIN_ID": fields.StringField(optional=False),
    #: Login pw
    "LOGIN_PW": fields.StringField(optional=False),
    #: Si, Do
    "SIDO": fields.StringField(optional=True, default="서울"),
    #: Si, Gun, Gu
    "SIGUNGU": fields.StringField(optional=True, default="강남구"),
    #: Eup, Myeon, Dong
    "DONGLI": fields.StringField(optional=True, default="개포동"),
    #: Building type
    "MAIN_USING_TYPE": fields.StringField(optional=True, default="집합건물"),
    #: Building desc
    "SUB_USING_TYPE": fields.StringField(optional=True, default="아파트"),
    #: Client Delay
    "CLIENT_DELAY": fields.StringField(optional=True),
    #: Debug
    "DEBUG": fields.BooleanField(optional=True),
    #: Running environment
    "PROXY_HOST": fields.StringField(optional=True),
    #: AWS sepecific access key id value
    "AWS_ACCESS_KEY_ID": fields.StringField(optional=True),
    #: AWS sepecific secret access key value
    "AWS_SECRET_ACCESS_KEY": fields.StringField(optional=True),
    #: AWS sepecific region name value
    "AWS_REGION_NAME": fields.StringField(optional=True),
    #: AWS sepecific endpoint url value
    "AWS_ENDPOINT_URL": fields.StringField(optional=True),
    #: AWS sepecific endpoint url value
    "AWS_S3_BUCKET_NAME": fields.StringField(optional=True),
    #: Slack Info
    "SLACK_API_TOKEN": fields.StringField(optional=True),
    "SLACK_CHANNEL": fields.StringField(optional=True),
    #: Sentry DSN
    'SENTRY_DSN': fields.StringField(optional=True),
}


def load() -> typing.Dict[str, typing.Union[object, str]]:
    config = tanker.config.load_from_env(prefix="CRAWLER_", schema=SCHEMA)
    config.setdefault("DEBUG", config["ENVIRONMENT"] in {"local", "test"})
    return config
