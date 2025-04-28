import logging
from os import getenv
from typing import Dict, Type


class BaseConfig:
    # Database
    DATABASE_URL: str = getenv('DATABASE_URL')

    # API
    BVG_API_MAX_RETRIES: int = 0
    BVG_API_RETRY_DELAY_SECONDS: int = 0

    # Logging
    LOG_LEVEL: int = 0


class ProdConfig(BaseConfig):
    # API
    BVG_API_MAX_RETRIES: int = 10
    BVG_API_RETRY_DELAY_SECONDS: int = 5

    # Logging
    LOG_LEVEL: int = logging.WARNING


class TestConfig(BaseConfig):
    # API
    BVG_API_MAX_RETRIES: int = 3
    BVG_API_RETRY_DELAY_SECONDS: int = 0

    # Logging
    LOG_LEVEL: int = logging.DEBUG


configs: Dict[str, Type[BaseConfig]] = {
    'prod': ProdConfig,
    'test': TestConfig,
}

ENV: str = getenv('ENV')

Config: Type[BaseConfig] = configs[ENV]
