import asyncio
import json
import subprocess
import time
from contextlib import asynccontextmanager
from unittest import TestCase
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
import redis
from freezegun import freeze_time
from pytest_redis import factories

from core.config import RedisSettings
from core.database.redis import redis_connection_manager
from core.database.redis.connection import RedisConnectionManager
from infrastructure.schemas import ABCSchema
from services.cache.manager import RedisCacheManager, redis_cache_manager
from services.loggs import logger


class TestModel(ABCSchema):
    name: str
    value: int


TestModel.__test__ = False


@pytest.fixture
def redis_mock():
    return MagicMock


class TestRedisCacheManager:

    @pytest.fixture
    def redis_mock(self):
        redis = AsyncMock()
        return redis

    @pytest.fixture
    def cache_manager(self, redis_mock):
        return RedisCacheManager(redis_mock)

    def test_create_cache_prefix_pattern(self, cache_manager):
        result = cache_manager._create_cache_prefix_pattern("test")
        assert result == ":test://"

    def test_create_user_pattern(self, cache_manager):
        result = cache_manager._create_user_pattern(123)
        assert result == "user:123:"

    def test_generate_handler_key_basic(self, cache_manager):
        result = cache_manager._generate_handler_key("api", "test_func", None, None)
        assert result == ":api://test_func:"

    def test_generate_handler_key_with_user(self, cache_manager):
        result = cache_manager._generate_handler_key("api", "test_func", None, 123)
        assert result == ":api://test_func:user:123:"

    def test_generate_handler_key_with_additional(self, cache_manager):
        result = cache_manager._generate_handler_key(
            "api", "test_func", "additional", None
        )
        assert result == ":api://test_func:additional"

    def test_generate_handler_key_complete(self, cache_manager):
        result = cache_manager._generate_handler_key(
            "api", "test_func", "additional", 123
        )
        assert result == ":api://test_func:user:123:additional"

    @pytest.mark.asyncio
    async def test_get_cache_success(self, cache_manager, redis_mock):
        test_data = {"name": "test", "value": 42}
        redis_mock.get.return_value = json.dumps(test_data)

        result = await cache_manager.get_cache("test_key")

        redis_mock.get.assert_called_once_with("test_key")
        assert result == test_data

    @pytest.mark.asyncio
    async def test_get_cache_empty(self, cache_manager, redis_mock):
        redis_mock.get.return_value = None

        result = await cache_manager.get_cache("test_key")

        redis_mock.get.assert_called_once_with("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_cache_exception(self, cache_manager, redis_mock):
        redis_mock.get.side_effect = Exception("Redis error")

        result = await cache_manager.get_cache("test_key")

        redis_mock.get.assert_called_once_with("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_cache_success(self, cache_manager, redis_mock):
        test_model = TestModel(name="test", value=42)
        expected_json = test_model.model_dump_json()

        await cache_manager.set_cache("test_key", test_model, 60)

        redis_mock.set.assert_called_once_with("test_key", expected_json, 60)

    @pytest.mark.asyncio
    async def test_get_cache_empty(self, cache_manager, redis_mock):
        redis_mock.get.return_value = None

        result = await cache_manager.get_cache("test_key")

        redis_mock.get.assert_called_once_with("test_key")
        assert result is None

    @pytest.mark.asyncio
    async def test_invalidate_all(self, cache_manager, redis_mock):
        await cache_manager.invalidate_all()
        redis_mock.flushdb.assert_called_once()

    @pytest.mark.asyncio
    async def test_invalidate_by_prefix_with_keys(self, cache_manager, redis_mock):
        test_keys = [b"key1", b"key2"]
        redis_mock.keys.return_value = test_keys

        await cache_manager.invalidate_by_prefix("api")

        redis_mock.keys.assert_called_once_with("*:api://*")
        redis_mock.delete.assert_called_once_with(*test_keys)


async def func_for_cache_test(name: str, value: int):
    model = TestModel(
        name=name,
        value=value,
    )
    return model


@asynccontextmanager
async def cache_manager():
    redis_settings = RedisSettings(HOST="localhost")
    connection_manager = RedisConnectionManager(redis_settings)
    pool = await connection_manager.get_redis_connection_pool(db=15)
    manager = RedisCacheManager(pool)

    yield manager
    await pool.flushdb()
    await pool.aclose()


@pytest.mark.asyncio
async def test_set_cache():
    async with cache_manager() as manager:
        test_key = "test_key"
        test_model = TestModel(
            name="Test Name",
            value=5,
        )
        await manager.set_cache(test_key, test_model, 60)
        cached_value = await manager.get_cache(test_key)
        assert cached_value == test_model.model_dump()


@pytest.mark.asyncio
async def test_empty_key():
    async with cache_manager() as manager:
        test_key = "test_key"
        test_model = TestModel(
            name="Test Name",
            value=5,
        )
        empty_key = "empty_key"
        await manager.set_cache(test_key, test_model, 60)
        cached_value = await manager.get_cache(empty_key)
        assert cached_value is None


@pytest.mark.asyncio
async def test_ttl():
    async with cache_manager() as manager:
        test_key = "test_key"
        test_model = TestModel(
            name="Test Name",
            value=5,
        )

        current_ttl = 60
        await manager.set_cache(test_key, test_model, current_ttl)
        ttl = await manager.redis.ttl(test_key)
        assert current_ttl == ttl


@pytest.mark.asyncio
async def test_ttl_eternal():
    async with cache_manager() as manager:
        test_key = "test_key"
        test_model = TestModel(
            name="Test Name",
            value=5,
        )

        current_ttl = None
        await manager.set_cache(test_key, test_model, current_ttl)
        ttl = await manager.redis.ttl(test_key)
        assert ttl == -1


@pytest.mark.asyncio
async def test_func_handle_cache():
    test_data = [
        ("TestName1", 10, "test_prefix_1", None, None, None),
        ("TestName1", 10, "test_prefix_1", None, None, 20),
        ("TestName1", 10, "test_prefix_1", None, None, 60),
        ("TestName1", 10, "test_prefix_1", None, 123, None),
        ("TestName1", 10, "test_prefix_1", None, 123, 20),
        ("TestName1", 10, "test_prefix_1", None, 123, 60),
        ("TestName1", 10, "test_prefix_1", None, "user_id_str", None),
        ("TestName1", 10, "test_prefix_1", None, "user_id_str", 20),
        ("TestName1", 10, "test_prefix_1", None, "user_id_str", 60),
        ("TestName1", 10, "test_prefix_1", "add_key_1", None, None),
        ("TestName1", 10, "test_prefix_1", "add_key_1", None, 20),
        ("TestName1", 10, "test_prefix_1", "add_key_1", None, 60),
        ("TestName1", 10, "test_prefix_1", "add_key_1", 123, None),
        ("TestName1", 10, "test_prefix_1", "add_key_1", 123, 20),
        ("TestName1", 10, "test_prefix_1", "add_key_1", 123, 60),
        ("TestName1", 10, "test_prefix_1", "add_key_1", "user_id_str", None),
        ("TestName1", 10, "test_prefix_1", "add_key_1", "user_id_str", 20),
        ("TestName1", 10, "test_prefix_1", "add_key_1", "user_id_str", 60),
        ("TestName1", 10, "test_prefix_1", "add_key_2", None, None),
        ("TestName1", 10, "test_prefix_1", "add_key_2", None, 20),
        ("TestName1", 10, "test_prefix_1", "add_key_2", None, 60),
        ("TestName1", 10, "test_prefix_1", "add_key_2", 123, None),
        ("TestName1", 10, "test_prefix_1", "add_key_2", 123, 20),
        ("TestName1", 10, "test_prefix_1", "add_key_2", 123, 60),
        ("TestName1", 10, "test_prefix_1", "add_key_2", "user_id_str", None),
        ("TestName1", 10, "test_prefix_1", "add_key_2", "user_id_str", 20),
        ("TestName1", 10, "test_prefix_1", "add_key_2", "user_id_str", 60),
        ("TestName1", 10, "test_prefix_2", None, None, None),
        ("TestName1", 10, "test_prefix_2", None, None, 20),
        ("TestName1", 10, "test_prefix_2", None, None, 60),
        ("TestName1", 10, "test_prefix_2", None, 123, None),
        ("TestName1", 10, "test_prefix_2", None, 123, 20),
        ("TestName1", 10, "test_prefix_2", None, 123, 60),
        ("TestName1", 10, "test_prefix_2", None, "user_id_str", None),
        ("TestName1", 10, "test_prefix_2", None, "user_id_str", 20),
        ("TestName1", 10, "test_prefix_2", None, "user_id_str", 60),
        ("TestName1", 10, "test_prefix_2", "add_key_1", None, None),
        ("TestName1", 10, "test_prefix_2", "add_key_1", None, 20),
        ("TestName1", 10, "test_prefix_2", "add_key_1", None, 60),
        ("TestName1", 10, "test_prefix_2", "add_key_1", 123, None),
        ("TestName1", 10, "test_prefix_2", "add_key_1", 123, 20),
        ("TestName1", 10, "test_prefix_2", "add_key_1", 123, 60),
        ("TestName1", 10, "test_prefix_2", "add_key_1", "user_id_str", None),
        ("TestName1", 10, "test_prefix_2", "add_key_1", "user_id_str", 20),
        ("TestName1", 10, "test_prefix_2", "add_key_1", "user_id_str", 60),
        ("TestName1", 10, "test_prefix_2", "add_key_2", None, None),
        ("TestName1", 10, "test_prefix_2", "add_key_2", None, 20),
        ("TestName1", 10, "test_prefix_2", "add_key_2", None, 60),
        ("TestName1", 10, "test_prefix_2", "add_key_2", 123, None),
        ("TestName1", 10, "test_prefix_2", "add_key_2", 123, 20),
        ("TestName1", 10, "test_prefix_2", "add_key_2", 123, 60),
        ("TestName1", 10, "test_prefix_2", "add_key_2", "user_id_str", None),
        ("TestName1", 10, "test_prefix_2", "add_key_2", "user_id_str", 20),
        ("TestName1", 10, "test_prefix_2", "add_key_2", "user_id_str", 60),
        ("TestName1", 10, "test_prefix_3", None, None, None),
        ("TestName1", 10, "test_prefix_3", None, None, 20),
        ("TestName1", 10, "test_prefix_3", None, None, 60),
        ("TestName1", 10, "test_prefix_3", None, 123, None),
        ("TestName1", 10, "test_prefix_3", None, 123, 20),
        ("TestName1", 10, "test_prefix_3", None, 123, 60),
        ("TestName1", 10, "test_prefix_3", None, "user_id_str", None),
        ("TestName1", 10, "test_prefix_3", None, "user_id_str", 20),
        ("TestName1", 10, "test_prefix_3", None, "user_id_str", 60),
        ("TestName1", 10, "test_prefix_3", "add_key_1", None, None),
        ("TestName1", 10, "test_prefix_3", "add_key_1", None, 20),
        ("TestName1", 10, "test_prefix_3", "add_key_1", None, 60),
        ("TestName1", 10, "test_prefix_3", "add_key_1", 123, None),
        ("TestName1", 10, "test_prefix_3", "add_key_1", 123, 20),
        ("TestName1", 10, "test_prefix_3", "add_key_1", 123, 60),
        ("TestName1", 10, "test_prefix_3", "add_key_1", "user_id_str", None),
        ("TestName1", 10, "test_prefix_3", "add_key_1", "user_id_str", 20),
        ("TestName1", 10, "test_prefix_3", "add_key_1", "user_id_str", 60),
        ("TestName1", 10, "test_prefix_3", "add_key_2", None, None),
        ("TestName1", 10, "test_prefix_3", "add_key_2", None, 20),
        ("TestName1", 10, "test_prefix_3", "add_key_2", None, 60),
        ("TestName1", 10, "test_prefix_3", "add_key_2", 123, None),
        ("TestName1", 10, "test_prefix_3", "add_key_2", 123, 20),
        ("TestName1", 10, "test_prefix_3", "add_key_2", 123, 60),
        ("TestName1", 10, "test_prefix_3", "add_key_2", "user_id_str", None),
        ("TestName1", 10, "test_prefix_3", "add_key_2", "user_id_str", 20),
        ("TestName1", 10, "test_prefix_3", "add_key_2", "user_id_str", 60),
        ("TestName1", 20, "test_prefix_1", None, None, None),
        ("TestName1", 20, "test_prefix_1", None, None, 20),
        ("TestName1", 20, "test_prefix_1", None, None, 60),
        ("TestName1", 20, "test_prefix_1", None, 123, None),
        ("TestName1", 20, "test_prefix_1", None, 123, 20),
        ("TestName1", 20, "test_prefix_1", None, 123, 60),
        ("TestName1", 20, "test_prefix_1", None, "user_id_str", None),
        ("TestName1", 20, "test_prefix_1", None, "user_id_str", 20),
        ("TestName1", 20, "test_prefix_1", None, "user_id_str", 60),
        ("TestName1", 20, "test_prefix_1", "add_key_1", None, None),
        ("TestName1", 20, "test_prefix_1", "add_key_1", None, 20),
        ("TestName1", 20, "test_prefix_1", "add_key_1", None, 60),
        ("TestName1", 20, "test_prefix_1", "add_key_1", 123, None),
        ("TestName1", 20, "test_prefix_1", "add_key_1", 123, 20),
        ("TestName1", 20, "test_prefix_1", "add_key_1", 123, 60),
        ("TestName1", 20, "test_prefix_1", "add_key_1", "user_id_str", None),
        ("TestName1", 20, "test_prefix_1", "add_key_1", "user_id_str", 20),
        ("TestName1", 20, "test_prefix_1", "add_key_1", "user_id_str", 60),
        ("TestName1", 20, "test_prefix_1", "add_key_2", None, None),
        ("TestName1", 20, "test_prefix_1", "add_key_2", None, 20),
        ("TestName1", 20, "test_prefix_1", "add_key_2", None, 60),
        ("TestName1", 20, "test_prefix_1", "add_key_2", 123, None),
        ("TestName1", 20, "test_prefix_1", "add_key_2", 123, 20),
        ("TestName1", 20, "test_prefix_1", "add_key_2", 123, 60),
        ("TestName1", 20, "test_prefix_1", "add_key_2", "user_id_str", None),
        ("TestName1", 20, "test_prefix_1", "add_key_2", "user_id_str", 20),
        ("TestName1", 20, "test_prefix_1", "add_key_2", "user_id_str", 60),
        ("TestName1", 20, "test_prefix_2", None, None, None),
        ("TestName1", 20, "test_prefix_2", None, None, 20),
        ("TestName1", 20, "test_prefix_2", None, None, 60),
        ("TestName1", 20, "test_prefix_2", None, 123, None),
        ("TestName1", 20, "test_prefix_2", None, 123, 20),
        ("TestName1", 20, "test_prefix_2", None, 123, 60),
        ("TestName1", 20, "test_prefix_2", None, "user_id_str", None),
        ("TestName1", 20, "test_prefix_2", None, "user_id_str", 20),
        ("TestName1", 20, "test_prefix_2", None, "user_id_str", 60),
        ("TestName1", 20, "test_prefix_2", "add_key_1", None, None),
        ("TestName1", 20, "test_prefix_2", "add_key_1", None, 20),
        ("TestName1", 20, "test_prefix_2", "add_key_1", None, 60),
        ("TestName1", 20, "test_prefix_2", "add_key_1", 123, None),
        ("TestName1", 20, "test_prefix_2", "add_key_1", 123, 20),
        ("TestName1", 20, "test_prefix_2", "add_key_1", 123, 60),
        ("TestName1", 20, "test_prefix_2", "add_key_1", "user_id_str", None),
        ("TestName1", 20, "test_prefix_2", "add_key_1", "user_id_str", 20),
        ("TestName1", 20, "test_prefix_2", "add_key_1", "user_id_str", 60),
        ("TestName1", 20, "test_prefix_2", "add_key_2", None, None),
        ("TestName1", 20, "test_prefix_2", "add_key_2", None, 20),
        ("TestName1", 20, "test_prefix_2", "add_key_2", None, 60),
        ("TestName1", 20, "test_prefix_2", "add_key_2", 123, None),
        ("TestName1", 20, "test_prefix_2", "add_key_2", 123, 20),
        ("TestName1", 20, "test_prefix_2", "add_key_2", 123, 60),
        ("TestName1", 20, "test_prefix_2", "add_key_2", "user_id_str", None),
        ("TestName1", 20, "test_prefix_2", "add_key_2", "user_id_str", 20),
        ("TestName1", 20, "test_prefix_2", "add_key_2", "user_id_str", 60),
        ("TestName1", 20, "test_prefix_3", None, None, None),
        ("TestName1", 20, "test_prefix_3", None, None, 20),
        ("TestName1", 20, "test_prefix_3", None, None, 60),
        ("TestName1", 20, "test_prefix_3", None, 123, None),
        ("TestName1", 20, "test_prefix_3", None, 123, 20),
        ("TestName1", 20, "test_prefix_3", None, 123, 60),
        ("TestName1", 20, "test_prefix_3", None, "user_id_str", None),
        ("TestName1", 20, "test_prefix_3", None, "user_id_str", 20),
        ("TestName1", 20, "test_prefix_3", None, "user_id_str", 60),
        ("TestName1", 20, "test_prefix_3", "add_key_1", None, None),
        ("TestName1", 20, "test_prefix_3", "add_key_1", None, 20),
        ("TestName1", 20, "test_prefix_3", "add_key_1", None, 60),
        ("TestName1", 20, "test_prefix_3", "add_key_1", 123, None),
        ("TestName1", 20, "test_prefix_3", "add_key_1", 123, 20),
        ("TestName1", 20, "test_prefix_3", "add_key_1", 123, 60),
        ("TestName1", 20, "test_prefix_3", "add_key_1", "user_id_str", None),
        ("TestName1", 20, "test_prefix_3", "add_key_1", "user_id_str", 20),
        ("TestName1", 20, "test_prefix_3", "add_key_1", "user_id_str", 60),
        ("TestName1", 20, "test_prefix_3", "add_key_2", None, None),
        ("TestName1", 20, "test_prefix_3", "add_key_2", None, 20),
        ("TestName1", 20, "test_prefix_3", "add_key_2", None, 60),
        ("TestName1", 20, "test_prefix_3", "add_key_2", 123, None),
        ("TestName1", 20, "test_prefix_3", "add_key_2", 123, 20),
        ("TestName1", 20, "test_prefix_3", "add_key_2", 123, 60),
        ("TestName1", 20, "test_prefix_3", "add_key_2", "user_id_str", None),
        ("TestName1", 20, "test_prefix_3", "add_key_2", "user_id_str", 20),
        ("TestName1", 20, "test_prefix_3", "add_key_2", "user_id_str", 60),
        ("TestName1", 30, "test_prefix_1", None, None, None),
        ("TestName1", 30, "test_prefix_1", None, None, 20),
        ("TestName1", 30, "test_prefix_1", None, None, 60),
        ("TestName1", 30, "test_prefix_1", None, 123, None),
        ("TestName1", 30, "test_prefix_1", None, 123, 20),
        ("TestName1", 30, "test_prefix_1", None, 123, 60),
        ("TestName1", 30, "test_prefix_1", None, "user_id_str", None),
        ("TestName1", 30, "test_prefix_1", None, "user_id_str", 20),
        ("TestName1", 30, "test_prefix_1", None, "user_id_str", 60),
        ("TestName1", 30, "test_prefix_1", "add_key_1", None, None),
        ("TestName1", 30, "test_prefix_1", "add_key_1", None, 20),
        ("TestName1", 30, "test_prefix_1", "add_key_1", None, 60),
        ("TestName1", 30, "test_prefix_1", "add_key_1", 123, None),
        ("TestName1", 30, "test_prefix_1", "add_key_1", 123, 20),
        ("TestName1", 30, "test_prefix_1", "add_key_1", 123, 60),
        ("TestName1", 30, "test_prefix_1", "add_key_1", "user_id_str", None),
        ("TestName1", 30, "test_prefix_1", "add_key_1", "user_id_str", 20),
        ("TestName1", 30, "test_prefix_1", "add_key_1", "user_id_str", 60),
        ("TestName1", 30, "test_prefix_1", "add_key_2", None, None),
        ("TestName1", 30, "test_prefix_1", "add_key_2", None, 20),
        ("TestName1", 30, "test_prefix_1", "add_key_2", None, 60),
        ("TestName1", 30, "test_prefix_1", "add_key_2", 123, None),
        ("TestName1", 30, "test_prefix_1", "add_key_2", 123, 20),
        ("TestName1", 30, "test_prefix_1", "add_key_2", 123, 60),
        ("TestName1", 30, "test_prefix_1", "add_key_2", "user_id_str", None),
        ("TestName1", 30, "test_prefix_1", "add_key_2", "user_id_str", 20),
        ("TestName1", 30, "test_prefix_1", "add_key_2", "user_id_str", 60),
        ("TestName1", 30, "test_prefix_2", None, None, None),
        ("TestName1", 30, "test_prefix_2", None, None, 20),
        ("TestName1", 30, "test_prefix_2", None, None, 60),
        ("TestName1", 30, "test_prefix_2", None, 123, None),
        ("TestName1", 30, "test_prefix_2", None, 123, 20),
        ("TestName1", 30, "test_prefix_2", None, 123, 60),
        ("TestName1", 30, "test_prefix_2", None, "user_id_str", None),
        ("TestName1", 30, "test_prefix_2", None, "user_id_str", 20),
        ("TestName1", 30, "test_prefix_2", None, "user_id_str", 60),
        ("TestName1", 30, "test_prefix_2", "add_key_1", None, None),
        ("TestName1", 30, "test_prefix_2", "add_key_1", None, 20),
        ("TestName1", 30, "test_prefix_2", "add_key_1", None, 60),
        ("TestName1", 30, "test_prefix_2", "add_key_1", 123, None),
        ("TestName1", 30, "test_prefix_2", "add_key_1", 123, 20),
        ("TestName1", 30, "test_prefix_2", "add_key_1", 123, 60),
        ("TestName1", 30, "test_prefix_2", "add_key_1", "user_id_str", None),
        ("TestName1", 30, "test_prefix_2", "add_key_1", "user_id_str", 20),
        ("TestName1", 30, "test_prefix_2", "add_key_1", "user_id_str", 60),
        ("TestName1", 30, "test_prefix_2", "add_key_2", None, None),
        ("TestName1", 30, "test_prefix_2", "add_key_2", None, 20),
        ("TestName1", 30, "test_prefix_2", "add_key_2", None, 60),
        ("TestName1", 30, "test_prefix_2", "add_key_2", 123, None),
        ("TestName1", 30, "test_prefix_2", "add_key_2", 123, 20),
        ("TestName1", 30, "test_prefix_2", "add_key_2", 123, 60),
        ("TestName1", 30, "test_prefix_2", "add_key_2", "user_id_str", None),
        ("TestName1", 30, "test_prefix_2", "add_key_2", "user_id_str", 20),
        ("TestName1", 30, "test_prefix_2", "add_key_2", "user_id_str", 60),
        ("TestName1", 30, "test_prefix_3", None, None, None),
        ("TestName1", 30, "test_prefix_3", None, None, 20),
        ("TestName1", 30, "test_prefix_3", None, None, 60),
        ("TestName1", 30, "test_prefix_3", None, 123, None),
        ("TestName1", 30, "test_prefix_3", None, 123, 20),
        ("TestName1", 30, "test_prefix_3", None, 123, 60),
        ("TestName1", 30, "test_prefix_3", None, "user_id_str", None),
        ("TestName1", 30, "test_prefix_3", None, "user_id_str", 20),
        ("TestName1", 30, "test_prefix_3", None, "user_id_str", 60),
        ("TestName1", 30, "test_prefix_3", "add_key_1", None, None),
        ("TestName1", 30, "test_prefix_3", "add_key_1", None, 20),
        ("TestName1", 30, "test_prefix_3", "add_key_1", None, 60),
        ("TestName1", 30, "test_prefix_3", "add_key_1", 123, None),
        ("TestName1", 30, "test_prefix_3", "add_key_1", 123, 20),
        ("TestName1", 30, "test_prefix_3", "add_key_1", 123, 60),
        ("TestName1", 30, "test_prefix_3", "add_key_1", "user_id_str", None),
        ("TestName1", 30, "test_prefix_3", "add_key_1", "user_id_str", 20),
        ("TestName1", 30, "test_prefix_3", "add_key_1", "user_id_str", 60),
        ("TestName1", 30, "test_prefix_3", "add_key_2", None, None),
        ("TestName1", 30, "test_prefix_3", "add_key_2", None, 20),
        ("TestName1", 30, "test_prefix_3", "add_key_2", None, 60),
        ("TestName1", 30, "test_prefix_3", "add_key_2", 123, None),
        ("TestName1", 30, "test_prefix_3", "add_key_2", 123, 20),
        ("TestName1", 30, "test_prefix_3", "add_key_2", 123, 60),
        ("TestName1", 30, "test_prefix_3", "add_key_2", "user_id_str", None),
        ("TestName1", 30, "test_prefix_3", "add_key_2", "user_id_str", 20),
        ("TestName1", 30, "test_prefix_3", "add_key_2", "user_id_str", 60),
        ("TestName2", 10, "test_prefix_1", None, None, None),
        ("TestName2", 10, "test_prefix_1", None, None, 20),
        ("TestName2", 10, "test_prefix_1", None, None, 60),
        ("TestName2", 10, "test_prefix_1", None, 123, None),
        ("TestName2", 10, "test_prefix_1", None, 123, 20),
        ("TestName2", 10, "test_prefix_1", None, 123, 60),
        ("TestName2", 10, "test_prefix_1", None, "user_id_str", None),
        ("TestName2", 10, "test_prefix_1", None, "user_id_str", 20),
        ("TestName2", 10, "test_prefix_1", None, "user_id_str", 60),
        ("TestName2", 10, "test_prefix_1", "add_key_1", None, None),
        ("TestName2", 10, "test_prefix_1", "add_key_1", None, 20),
        ("TestName2", 10, "test_prefix_1", "add_key_1", None, 60),
        ("TestName2", 10, "test_prefix_1", "add_key_1", 123, None),
        ("TestName2", 10, "test_prefix_1", "add_key_1", 123, 20),
        ("TestName2", 10, "test_prefix_1", "add_key_1", 123, 60),
        ("TestName2", 10, "test_prefix_1", "add_key_1", "user_id_str", None),
        ("TestName2", 10, "test_prefix_1", "add_key_1", "user_id_str", 20),
        ("TestName2", 10, "test_prefix_1", "add_key_1", "user_id_str", 60),
        ("TestName2", 10, "test_prefix_1", "add_key_2", None, None),
        ("TestName2", 10, "test_prefix_1", "add_key_2", None, 20),
        ("TestName2", 10, "test_prefix_1", "add_key_2", None, 60),
        ("TestName2", 10, "test_prefix_1", "add_key_2", 123, None),
        ("TestName2", 10, "test_prefix_1", "add_key_2", 123, 20),
        ("TestName2", 10, "test_prefix_1", "add_key_2", 123, 60),
        ("TestName2", 10, "test_prefix_1", "add_key_2", "user_id_str", None),
        ("TestName2", 10, "test_prefix_1", "add_key_2", "user_id_str", 20),
        ("TestName2", 10, "test_prefix_1", "add_key_2", "user_id_str", 60),
        ("TestName2", 10, "test_prefix_2", None, None, None),
        ("TestName2", 10, "test_prefix_2", None, None, 20),
        ("TestName2", 10, "test_prefix_2", None, None, 60),
        ("TestName2", 10, "test_prefix_2", None, 123, None),
        ("TestName2", 10, "test_prefix_2", None, 123, 20),
        ("TestName2", 10, "test_prefix_2", None, 123, 60),
        ("TestName2", 10, "test_prefix_2", None, "user_id_str", None),
        ("TestName2", 10, "test_prefix_2", None, "user_id_str", 20),
        ("TestName2", 10, "test_prefix_2", None, "user_id_str", 60),
        ("TestName2", 10, "test_prefix_2", "add_key_1", None, None),
        ("TestName2", 10, "test_prefix_2", "add_key_1", None, 20),
        ("TestName2", 10, "test_prefix_2", "add_key_1", None, 60),
        ("TestName2", 10, "test_prefix_2", "add_key_1", 123, None),
        ("TestName2", 10, "test_prefix_2", "add_key_1", 123, 20),
        ("TestName2", 10, "test_prefix_2", "add_key_1", 123, 60),
        ("TestName2", 10, "test_prefix_2", "add_key_1", "user_id_str", None),
        ("TestName2", 10, "test_prefix_2", "add_key_1", "user_id_str", 20),
        ("TestName2", 10, "test_prefix_2", "add_key_1", "user_id_str", 60),
        ("TestName2", 10, "test_prefix_2", "add_key_2", None, None),
        ("TestName2", 10, "test_prefix_2", "add_key_2", None, 20),
        ("TestName2", 10, "test_prefix_2", "add_key_2", None, 60),
        ("TestName2", 10, "test_prefix_2", "add_key_2", 123, None),
        ("TestName2", 10, "test_prefix_2", "add_key_2", 123, 20),
        ("TestName2", 10, "test_prefix_2", "add_key_2", 123, 60),
        ("TestName2", 10, "test_prefix_2", "add_key_2", "user_id_str", None),
        ("TestName2", 10, "test_prefix_2", "add_key_2", "user_id_str", 20),
        ("TestName2", 10, "test_prefix_2", "add_key_2", "user_id_str", 60),
        ("TestName2", 10, "test_prefix_3", None, None, None),
        ("TestName2", 10, "test_prefix_3", None, None, 20),
        ("TestName2", 10, "test_prefix_3", None, None, 60),
        ("TestName2", 10, "test_prefix_3", None, 123, None),
        ("TestName2", 10, "test_prefix_3", None, 123, 20),
        ("TestName2", 10, "test_prefix_3", None, 123, 60),
        ("TestName2", 10, "test_prefix_3", None, "user_id_str", None),
        ("TestName2", 10, "test_prefix_3", None, "user_id_str", 20),
        ("TestName2", 10, "test_prefix_3", None, "user_id_str", 60),
        ("TestName2", 10, "test_prefix_3", "add_key_1", None, None),
        ("TestName2", 10, "test_prefix_3", "add_key_1", None, 20),
        ("TestName2", 10, "test_prefix_3", "add_key_1", None, 60),
        ("TestName2", 10, "test_prefix_3", "add_key_1", 123, None),
        ("TestName2", 10, "test_prefix_3", "add_key_1", 123, 20),
        ("TestName2", 10, "test_prefix_3", "add_key_1", 123, 60),
        ("TestName2", 10, "test_prefix_3", "add_key_1", "user_id_str", None),
        ("TestName2", 10, "test_prefix_3", "add_key_1", "user_id_str", 20),
        ("TestName2", 10, "test_prefix_3", "add_key_1", "user_id_str", 60),
        ("TestName2", 10, "test_prefix_3", "add_key_2", None, None),
        ("TestName2", 10, "test_prefix_3", "add_key_2", None, 20),
        ("TestName2", 10, "test_prefix_3", "add_key_2", None, 60),
        ("TestName2", 10, "test_prefix_3", "add_key_2", 123, None),
        ("TestName2", 10, "test_prefix_3", "add_key_2", 123, 20),
        ("TestName2", 10, "test_prefix_3", "add_key_2", 123, 60),
        ("TestName2", 10, "test_prefix_3", "add_key_2", "user_id_str", None),
        ("TestName2", 10, "test_prefix_3", "add_key_2", "user_id_str", 20),
        ("TestName2", 10, "test_prefix_3", "add_key_2", "user_id_str", 60),
        ("TestName2", 20, "test_prefix_1", None, None, None),
        ("TestName2", 20, "test_prefix_1", None, None, 20),
        ("TestName2", 20, "test_prefix_1", None, None, 60),
        ("TestName2", 20, "test_prefix_1", None, 123, None),
        ("TestName2", 20, "test_prefix_1", None, 123, 20),
        ("TestName2", 20, "test_prefix_1", None, 123, 60),
        ("TestName2", 20, "test_prefix_1", None, "user_id_str", None),
        ("TestName2", 20, "test_prefix_1", None, "user_id_str", 20),
        ("TestName2", 20, "test_prefix_1", None, "user_id_str", 60),
        ("TestName2", 20, "test_prefix_1", "add_key_1", None, None),
        ("TestName2", 20, "test_prefix_1", "add_key_1", None, 20),
        ("TestName2", 20, "test_prefix_1", "add_key_1", None, 60),
        ("TestName2", 20, "test_prefix_1", "add_key_1", 123, None),
        ("TestName2", 20, "test_prefix_1", "add_key_1", 123, 20),
        ("TestName2", 20, "test_prefix_1", "add_key_1", 123, 60),
        ("TestName2", 20, "test_prefix_1", "add_key_1", "user_id_str", None),
        ("TestName2", 20, "test_prefix_1", "add_key_1", "user_id_str", 20),
        ("TestName2", 20, "test_prefix_1", "add_key_1", "user_id_str", 60),
        ("TestName2", 20, "test_prefix_1", "add_key_2", None, None),
        ("TestName2", 20, "test_prefix_1", "add_key_2", None, 20),
        ("TestName2", 20, "test_prefix_1", "add_key_2", None, 60),
        ("TestName2", 20, "test_prefix_1", "add_key_2", 123, None),
        ("TestName2", 20, "test_prefix_1", "add_key_2", 123, 20),
        ("TestName2", 20, "test_prefix_1", "add_key_2", 123, 60),
        ("TestName2", 20, "test_prefix_1", "add_key_2", "user_id_str", None),
        ("TestName2", 20, "test_prefix_1", "add_key_2", "user_id_str", 20),
        ("TestName2", 20, "test_prefix_1", "add_key_2", "user_id_str", 60),
        ("TestName2", 20, "test_prefix_2", None, None, None),
        ("TestName2", 20, "test_prefix_2", None, None, 20),
        ("TestName2", 20, "test_prefix_2", None, None, 60),
        ("TestName2", 20, "test_prefix_2", None, 123, None),
        ("TestName2", 20, "test_prefix_2", None, 123, 20),
        ("TestName2", 20, "test_prefix_2", None, 123, 60),
        ("TestName2", 20, "test_prefix_2", None, "user_id_str", None),
        ("TestName2", 20, "test_prefix_2", None, "user_id_str", 20),
        ("TestName2", 20, "test_prefix_2", None, "user_id_str", 60),
        ("TestName2", 20, "test_prefix_2", "add_key_1", None, None),
        ("TestName2", 20, "test_prefix_2", "add_key_1", None, 20),
        ("TestName2", 20, "test_prefix_2", "add_key_1", None, 60),
        ("TestName2", 20, "test_prefix_2", "add_key_1", 123, None),
        ("TestName2", 20, "test_prefix_2", "add_key_1", 123, 20),
        ("TestName2", 20, "test_prefix_2", "add_key_1", 123, 60),
        ("TestName2", 20, "test_prefix_2", "add_key_1", "user_id_str", None),
        ("TestName2", 20, "test_prefix_2", "add_key_1", "user_id_str", 20),
        ("TestName2", 20, "test_prefix_2", "add_key_1", "user_id_str", 60),
        ("TestName2", 20, "test_prefix_2", "add_key_2", None, None),
        ("TestName2", 20, "test_prefix_2", "add_key_2", None, 20),
        ("TestName2", 20, "test_prefix_2", "add_key_2", None, 60),
        ("TestName2", 20, "test_prefix_2", "add_key_2", 123, None),
        ("TestName2", 20, "test_prefix_2", "add_key_2", 123, 20),
        ("TestName2", 20, "test_prefix_2", "add_key_2", 123, 60),
        ("TestName2", 20, "test_prefix_2", "add_key_2", "user_id_str", None),
        ("TestName2", 20, "test_prefix_2", "add_key_2", "user_id_str", 20),
        ("TestName2", 20, "test_prefix_2", "add_key_2", "user_id_str", 60),
        ("TestName2", 20, "test_prefix_3", None, None, None),
        ("TestName2", 20, "test_prefix_3", None, None, 20),
        ("TestName2", 20, "test_prefix_3", None, None, 60),
        ("TestName2", 20, "test_prefix_3", None, 123, None),
        ("TestName2", 20, "test_prefix_3", None, 123, 20),
        ("TestName2", 20, "test_prefix_3", None, 123, 60),
        ("TestName2", 20, "test_prefix_3", None, "user_id_str", None),
        ("TestName2", 20, "test_prefix_3", None, "user_id_str", 20),
        ("TestName2", 20, "test_prefix_3", None, "user_id_str", 60),
        ("TestName2", 20, "test_prefix_3", "add_key_1", None, None),
        ("TestName2", 20, "test_prefix_3", "add_key_1", None, 20),
        ("TestName2", 20, "test_prefix_3", "add_key_1", None, 60),
        ("TestName2", 20, "test_prefix_3", "add_key_1", 123, None),
        ("TestName2", 20, "test_prefix_3", "add_key_1", 123, 20),
        ("TestName2", 20, "test_prefix_3", "add_key_1", 123, 60),
        ("TestName2", 20, "test_prefix_3", "add_key_1", "user_id_str", None),
        ("TestName2", 20, "test_prefix_3", "add_key_1", "user_id_str", 20),
        ("TestName2", 20, "test_prefix_3", "add_key_1", "user_id_str", 60),
        ("TestName2", 20, "test_prefix_3", "add_key_2", None, None),
        ("TestName2", 20, "test_prefix_3", "add_key_2", None, 20),
        ("TestName2", 20, "test_prefix_3", "add_key_2", None, 60),
        ("TestName2", 20, "test_prefix_3", "add_key_2", 123, None),
        ("TestName2", 20, "test_prefix_3", "add_key_2", 123, 20),
        ("TestName2", 20, "test_prefix_3", "add_key_2", 123, 60),
        ("TestName2", 20, "test_prefix_3", "add_key_2", "user_id_str", None),
        ("TestName2", 20, "test_prefix_3", "add_key_2", "user_id_str", 20),
        ("TestName2", 20, "test_prefix_3", "add_key_2", "user_id_str", 60),
        ("TestName2", 30, "test_prefix_1", None, None, None),
        ("TestName2", 30, "test_prefix_1", None, None, 20),
        ("TestName2", 30, "test_prefix_1", None, None, 60),
        ("TestName2", 30, "test_prefix_1", None, 123, None),
        ("TestName2", 30, "test_prefix_1", None, 123, 20),
        ("TestName2", 30, "test_prefix_1", None, 123, 60),
        ("TestName2", 30, "test_prefix_1", None, "user_id_str", None),
        ("TestName2", 30, "test_prefix_1", None, "user_id_str", 20),
        ("TestName2", 30, "test_prefix_1", None, "user_id_str", 60),
        ("TestName2", 30, "test_prefix_1", "add_key_1", None, None),
        ("TestName2", 30, "test_prefix_1", "add_key_1", None, 20),
        ("TestName2", 30, "test_prefix_1", "add_key_1", None, 60),
        ("TestName2", 30, "test_prefix_1", "add_key_1", 123, None),
        ("TestName2", 30, "test_prefix_1", "add_key_1", 123, 20),
        ("TestName2", 30, "test_prefix_1", "add_key_1", 123, 60),
        ("TestName2", 30, "test_prefix_1", "add_key_1", "user_id_str", None),
        ("TestName2", 30, "test_prefix_1", "add_key_1", "user_id_str", 20),
        ("TestName2", 30, "test_prefix_1", "add_key_1", "user_id_str", 60),
        ("TestName2", 30, "test_prefix_1", "add_key_2", None, None),
        ("TestName2", 30, "test_prefix_1", "add_key_2", None, 20),
        ("TestName2", 30, "test_prefix_1", "add_key_2", None, 60),
        ("TestName2", 30, "test_prefix_1", "add_key_2", 123, None),
        ("TestName2", 30, "test_prefix_1", "add_key_2", 123, 20),
        ("TestName2", 30, "test_prefix_1", "add_key_2", 123, 60),
        ("TestName2", 30, "test_prefix_1", "add_key_2", "user_id_str", None),
        ("TestName2", 30, "test_prefix_1", "add_key_2", "user_id_str", 20),
        ("TestName2", 30, "test_prefix_1", "add_key_2", "user_id_str", 60),
        ("TestName2", 30, "test_prefix_2", None, None, None),
        ("TestName2", 30, "test_prefix_2", None, None, 20),
        ("TestName2", 30, "test_prefix_2", None, None, 60),
        ("TestName2", 30, "test_prefix_2", None, 123, None),
        ("TestName2", 30, "test_prefix_2", None, 123, 20),
        ("TestName2", 30, "test_prefix_2", None, 123, 60),
        ("TestName2", 30, "test_prefix_2", None, "user_id_str", None),
        ("TestName2", 30, "test_prefix_2", None, "user_id_str", 20),
        ("TestName2", 30, "test_prefix_2", None, "user_id_str", 60),
        ("TestName2", 30, "test_prefix_2", "add_key_1", None, None),
        ("TestName2", 30, "test_prefix_2", "add_key_1", None, 20),
        ("TestName2", 30, "test_prefix_2", "add_key_1", None, 60),
        ("TestName2", 30, "test_prefix_2", "add_key_1", 123, None),
        ("TestName2", 30, "test_prefix_2", "add_key_1", 123, 20),
        ("TestName2", 30, "test_prefix_2", "add_key_1", 123, 60),
        ("TestName2", 30, "test_prefix_2", "add_key_1", "user_id_str", None),
        ("TestName2", 30, "test_prefix_2", "add_key_1", "user_id_str", 20),
        ("TestName2", 30, "test_prefix_2", "add_key_1", "user_id_str", 60),
        ("TestName2", 30, "test_prefix_2", "add_key_2", None, None),
        ("TestName2", 30, "test_prefix_2", "add_key_2", None, 20),
        ("TestName2", 30, "test_prefix_2", "add_key_2", None, 60),
        ("TestName2", 30, "test_prefix_2", "add_key_2", 123, None),
        ("TestName2", 30, "test_prefix_2", "add_key_2", 123, 20),
        ("TestName2", 30, "test_prefix_2", "add_key_2", 123, 60),
        ("TestName2", 30, "test_prefix_2", "add_key_2", "user_id_str", None),
        ("TestName2", 30, "test_prefix_2", "add_key_2", "user_id_str", 20),
        ("TestName2", 30, "test_prefix_2", "add_key_2", "user_id_str", 60),
        ("TestName2", 30, "test_prefix_3", None, None, None),
        ("TestName2", 30, "test_prefix_3", None, None, 20),
        ("TestName2", 30, "test_prefix_3", None, None, 60),
        ("TestName2", 30, "test_prefix_3", None, 123, None),
        ("TestName2", 30, "test_prefix_3", None, 123, 20),
        ("TestName2", 30, "test_prefix_3", None, 123, 60),
        ("TestName2", 30, "test_prefix_3", None, "user_id_str", None),
        ("TestName2", 30, "test_prefix_3", None, "user_id_str", 20),
        ("TestName2", 30, "test_prefix_3", None, "user_id_str", 60),
        ("TestName2", 30, "test_prefix_3", "add_key_1", None, None),
        ("TestName2", 30, "test_prefix_3", "add_key_1", None, 20),
        ("TestName2", 30, "test_prefix_3", "add_key_1", None, 60),
        ("TestName2", 30, "test_prefix_3", "add_key_1", 123, None),
        ("TestName2", 30, "test_prefix_3", "add_key_1", 123, 20),
        ("TestName2", 30, "test_prefix_3", "add_key_1", 123, 60),
        ("TestName2", 30, "test_prefix_3", "add_key_1", "user_id_str", None),
        ("TestName2", 30, "test_prefix_3", "add_key_1", "user_id_str", 20),
        ("TestName2", 30, "test_prefix_3", "add_key_1", "user_id_str", 60),
        ("TestName2", 30, "test_prefix_3", "add_key_2", None, None),
        ("TestName2", 30, "test_prefix_3", "add_key_2", None, 20),
        ("TestName2", 30, "test_prefix_3", "add_key_2", None, 60),
        ("TestName2", 30, "test_prefix_3", "add_key_2", 123, None),
        ("TestName2", 30, "test_prefix_3", "add_key_2", 123, 20),
        ("TestName2", 30, "test_prefix_3", "add_key_2", 123, 60),
        ("TestName2", 30, "test_prefix_3", "add_key_2", "user_id_str", None),
        ("TestName2", 30, "test_prefix_3", "add_key_2", "user_id_str", 20),
        ("TestName2", 30, "test_prefix_3", "add_key_2", "user_id_str", 60),
        ("TestName3", 10, "test_prefix_1", None, None, None),
        ("TestName3", 10, "test_prefix_1", None, None, 20),
        ("TestName3", 10, "test_prefix_1", None, None, 60),
        ("TestName3", 10, "test_prefix_1", None, 123, None),
        ("TestName3", 10, "test_prefix_1", None, 123, 20),
        ("TestName3", 10, "test_prefix_1", None, 123, 60),
        ("TestName3", 10, "test_prefix_1", None, "user_id_str", None),
        ("TestName3", 10, "test_prefix_1", None, "user_id_str", 20),
        ("TestName3", 10, "test_prefix_1", None, "user_id_str", 60),
        ("TestName3", 10, "test_prefix_1", "add_key_1", None, None),
        ("TestName3", 10, "test_prefix_1", "add_key_1", None, 20),
        ("TestName3", 10, "test_prefix_1", "add_key_1", None, 60),
        ("TestName3", 10, "test_prefix_1", "add_key_1", 123, None),
        ("TestName3", 10, "test_prefix_1", "add_key_1", 123, 20),
        ("TestName3", 10, "test_prefix_1", "add_key_1", 123, 60),
        ("TestName3", 10, "test_prefix_1", "add_key_1", "user_id_str", None),
        ("TestName3", 10, "test_prefix_1", "add_key_1", "user_id_str", 20),
        ("TestName3", 10, "test_prefix_1", "add_key_1", "user_id_str", 60),
        ("TestName3", 10, "test_prefix_1", "add_key_2", None, None),
        ("TestName3", 10, "test_prefix_1", "add_key_2", None, 20),
        ("TestName3", 10, "test_prefix_1", "add_key_2", None, 60),
        ("TestName3", 10, "test_prefix_1", "add_key_2", 123, None),
        ("TestName3", 10, "test_prefix_1", "add_key_2", 123, 20),
        ("TestName3", 10, "test_prefix_1", "add_key_2", 123, 60),
        ("TestName3", 10, "test_prefix_1", "add_key_2", "user_id_str", None),
        ("TestName3", 10, "test_prefix_1", "add_key_2", "user_id_str", 20),
        ("TestName3", 10, "test_prefix_1", "add_key_2", "user_id_str", 60),
        ("TestName3", 10, "test_prefix_2", None, None, None),
        ("TestName3", 10, "test_prefix_2", None, None, 20),
        ("TestName3", 10, "test_prefix_2", None, None, 60),
        ("TestName3", 10, "test_prefix_2", None, 123, None),
        ("TestName3", 10, "test_prefix_2", None, 123, 20),
        ("TestName3", 10, "test_prefix_2", None, 123, 60),
        ("TestName3", 10, "test_prefix_2", None, "user_id_str", None),
        ("TestName3", 10, "test_prefix_2", None, "user_id_str", 20),
        ("TestName3", 10, "test_prefix_2", None, "user_id_str", 60),
        ("TestName3", 10, "test_prefix_2", "add_key_1", None, None),
        ("TestName3", 10, "test_prefix_2", "add_key_1", None, 20),
        ("TestName3", 10, "test_prefix_2", "add_key_1", None, 60),
        ("TestName3", 10, "test_prefix_2", "add_key_1", 123, None),
        ("TestName3", 10, "test_prefix_2", "add_key_1", 123, 20),
        ("TestName3", 10, "test_prefix_2", "add_key_1", 123, 60),
        ("TestName3", 10, "test_prefix_2", "add_key_1", "user_id_str", None),
        ("TestName3", 10, "test_prefix_2", "add_key_1", "user_id_str", 20),
        ("TestName3", 10, "test_prefix_2", "add_key_1", "user_id_str", 60),
        ("TestName3", 10, "test_prefix_2", "add_key_2", None, None),
        ("TestName3", 10, "test_prefix_2", "add_key_2", None, 20),
        ("TestName3", 10, "test_prefix_2", "add_key_2", None, 60),
        ("TestName3", 10, "test_prefix_2", "add_key_2", 123, None),
        ("TestName3", 10, "test_prefix_2", "add_key_2", 123, 20),
        ("TestName3", 10, "test_prefix_2", "add_key_2", 123, 60),
        ("TestName3", 10, "test_prefix_2", "add_key_2", "user_id_str", None),
        ("TestName3", 10, "test_prefix_2", "add_key_2", "user_id_str", 20),
        ("TestName3", 10, "test_prefix_2", "add_key_2", "user_id_str", 60),
        ("TestName3", 10, "test_prefix_3", None, None, None),
        ("TestName3", 10, "test_prefix_3", None, None, 20),
        ("TestName3", 10, "test_prefix_3", None, None, 60),
        ("TestName3", 10, "test_prefix_3", None, 123, None),
        ("TestName3", 10, "test_prefix_3", None, 123, 20),
        ("TestName3", 10, "test_prefix_3", None, 123, 60),
        ("TestName3", 10, "test_prefix_3", None, "user_id_str", None),
        ("TestName3", 10, "test_prefix_3", None, "user_id_str", 20),
        ("TestName3", 10, "test_prefix_3", None, "user_id_str", 60),
        ("TestName3", 10, "test_prefix_3", "add_key_1", None, None),
        ("TestName3", 10, "test_prefix_3", "add_key_1", None, 20),
        ("TestName3", 10, "test_prefix_3", "add_key_1", None, 60),
        ("TestName3", 10, "test_prefix_3", "add_key_1", 123, None),
        ("TestName3", 10, "test_prefix_3", "add_key_1", 123, 20),
        ("TestName3", 10, "test_prefix_3", "add_key_1", 123, 60),
        ("TestName3", 10, "test_prefix_3", "add_key_1", "user_id_str", None),
        ("TestName3", 10, "test_prefix_3", "add_key_1", "user_id_str", 20),
        ("TestName3", 10, "test_prefix_3", "add_key_1", "user_id_str", 60),
        ("TestName3", 10, "test_prefix_3", "add_key_2", None, None),
        ("TestName3", 10, "test_prefix_3", "add_key_2", None, 20),
        ("TestName3", 10, "test_prefix_3", "add_key_2", None, 60),
        ("TestName3", 10, "test_prefix_3", "add_key_2", 123, None),
        ("TestName3", 10, "test_prefix_3", "add_key_2", 123, 20),
        ("TestName3", 10, "test_prefix_3", "add_key_2", 123, 60),
        ("TestName3", 10, "test_prefix_3", "add_key_2", "user_id_str", None),
        ("TestName3", 10, "test_prefix_3", "add_key_2", "user_id_str", 20),
        ("TestName3", 10, "test_prefix_3", "add_key_2", "user_id_str", 60),
        ("TestName3", 20, "test_prefix_1", None, None, None),
        ("TestName3", 20, "test_prefix_1", None, None, 20),
        ("TestName3", 20, "test_prefix_1", None, None, 60),
        ("TestName3", 20, "test_prefix_1", None, 123, None),
        ("TestName3", 20, "test_prefix_1", None, 123, 20),
        ("TestName3", 20, "test_prefix_1", None, 123, 60),
        ("TestName3", 20, "test_prefix_1", None, "user_id_str", None),
        ("TestName3", 20, "test_prefix_1", None, "user_id_str", 20),
        ("TestName3", 20, "test_prefix_1", None, "user_id_str", 60),
        ("TestName3", 20, "test_prefix_1", "add_key_1", None, None),
        ("TestName3", 20, "test_prefix_1", "add_key_1", None, 20),
        ("TestName3", 20, "test_prefix_1", "add_key_1", None, 60),
        ("TestName3", 20, "test_prefix_1", "add_key_1", 123, None),
        ("TestName3", 20, "test_prefix_1", "add_key_1", 123, 20),
        ("TestName3", 20, "test_prefix_1", "add_key_1", 123, 60),
        ("TestName3", 20, "test_prefix_1", "add_key_1", "user_id_str", None),
        ("TestName3", 20, "test_prefix_1", "add_key_1", "user_id_str", 20),
        ("TestName3", 20, "test_prefix_1", "add_key_1", "user_id_str", 60),
        ("TestName3", 20, "test_prefix_1", "add_key_2", None, None),
        ("TestName3", 20, "test_prefix_1", "add_key_2", None, 20),
        ("TestName3", 20, "test_prefix_1", "add_key_2", None, 60),
        ("TestName3", 20, "test_prefix_1", "add_key_2", 123, None),
        ("TestName3", 20, "test_prefix_1", "add_key_2", 123, 20),
        ("TestName3", 20, "test_prefix_1", "add_key_2", 123, 60),
        ("TestName3", 20, "test_prefix_1", "add_key_2", "user_id_str", None),
        ("TestName3", 20, "test_prefix_1", "add_key_2", "user_id_str", 20),
        ("TestName3", 20, "test_prefix_1", "add_key_2", "user_id_str", 60),
        ("TestName3", 20, "test_prefix_2", None, None, None),
        ("TestName3", 20, "test_prefix_2", None, None, 20),
        ("TestName3", 20, "test_prefix_2", None, None, 60),
        ("TestName3", 20, "test_prefix_2", None, 123, None),
        ("TestName3", 20, "test_prefix_2", None, 123, 20),
        ("TestName3", 20, "test_prefix_2", None, 123, 60),
        ("TestName3", 20, "test_prefix_2", None, "user_id_str", None),
        ("TestName3", 20, "test_prefix_2", None, "user_id_str", 20),
        ("TestName3", 20, "test_prefix_2", None, "user_id_str", 60),
        ("TestName3", 20, "test_prefix_2", "add_key_1", None, None),
        ("TestName3", 20, "test_prefix_2", "add_key_1", None, 20),
        ("TestName3", 20, "test_prefix_2", "add_key_1", None, 60),
        ("TestName3", 20, "test_prefix_2", "add_key_1", 123, None),
        ("TestName3", 20, "test_prefix_2", "add_key_1", 123, 20),
        ("TestName3", 20, "test_prefix_2", "add_key_1", 123, 60),
        ("TestName3", 20, "test_prefix_2", "add_key_1", "user_id_str", None),
        ("TestName3", 20, "test_prefix_2", "add_key_1", "user_id_str", 20),
        ("TestName3", 20, "test_prefix_2", "add_key_1", "user_id_str", 60),
        ("TestName3", 20, "test_prefix_2", "add_key_2", None, None),
        ("TestName3", 20, "test_prefix_2", "add_key_2", None, 20),
        ("TestName3", 20, "test_prefix_2", "add_key_2", None, 60),
        ("TestName3", 20, "test_prefix_2", "add_key_2", 123, None),
        ("TestName3", 20, "test_prefix_2", "add_key_2", 123, 20),
        ("TestName3", 20, "test_prefix_2", "add_key_2", 123, 60),
        ("TestName3", 20, "test_prefix_2", "add_key_2", "user_id_str", None),
        ("TestName3", 20, "test_prefix_2", "add_key_2", "user_id_str", 20),
        ("TestName3", 20, "test_prefix_2", "add_key_2", "user_id_str", 60),
        ("TestName3", 20, "test_prefix_3", None, None, None),
        ("TestName3", 20, "test_prefix_3", None, None, 20),
        ("TestName3", 20, "test_prefix_3", None, None, 60),
        ("TestName3", 20, "test_prefix_3", None, 123, None),
        ("TestName3", 20, "test_prefix_3", None, 123, 20),
        ("TestName3", 20, "test_prefix_3", None, 123, 60),
        ("TestName3", 20, "test_prefix_3", None, "user_id_str", None),
        ("TestName3", 20, "test_prefix_3", None, "user_id_str", 20),
        ("TestName3", 20, "test_prefix_3", None, "user_id_str", 60),
        ("TestName3", 20, "test_prefix_3", "add_key_1", None, None),
        ("TestName3", 20, "test_prefix_3", "add_key_1", None, 20),
        ("TestName3", 20, "test_prefix_3", "add_key_1", None, 60),
        ("TestName3", 20, "test_prefix_3", "add_key_1", 123, None),
        ("TestName3", 20, "test_prefix_3", "add_key_1", 123, 20),
        ("TestName3", 20, "test_prefix_3", "add_key_1", 123, 60),
        ("TestName3", 20, "test_prefix_3", "add_key_1", "user_id_str", None),
        ("TestName3", 20, "test_prefix_3", "add_key_1", "user_id_str", 20),
        ("TestName3", 20, "test_prefix_3", "add_key_1", "user_id_str", 60),
        ("TestName3", 20, "test_prefix_3", "add_key_2", None, None),
        ("TestName3", 20, "test_prefix_3", "add_key_2", None, 20),
        ("TestName3", 20, "test_prefix_3", "add_key_2", None, 60),
        ("TestName3", 20, "test_prefix_3", "add_key_2", 123, None),
        ("TestName3", 20, "test_prefix_3", "add_key_2", 123, 20),
        ("TestName3", 20, "test_prefix_3", "add_key_2", 123, 60),
        ("TestName3", 20, "test_prefix_3", "add_key_2", "user_id_str", None),
        ("TestName3", 20, "test_prefix_3", "add_key_2", "user_id_str", 20),
        ("TestName3", 20, "test_prefix_3", "add_key_2", "user_id_str", 60),
        ("TestName3", 30, "test_prefix_1", None, None, None),
        ("TestName3", 30, "test_prefix_1", None, None, 20),
        ("TestName3", 30, "test_prefix_1", None, None, 60),
        ("TestName3", 30, "test_prefix_1", None, 123, None),
        ("TestName3", 30, "test_prefix_1", None, 123, 20),
        ("TestName3", 30, "test_prefix_1", None, 123, 60),
        ("TestName3", 30, "test_prefix_1", None, "user_id_str", None),
        ("TestName3", 30, "test_prefix_1", None, "user_id_str", 20),
        ("TestName3", 30, "test_prefix_1", None, "user_id_str", 60),
        ("TestName3", 30, "test_prefix_1", "add_key_1", None, None),
        ("TestName3", 30, "test_prefix_1", "add_key_1", None, 20),
        ("TestName3", 30, "test_prefix_1", "add_key_1", None, 60),
        ("TestName3", 30, "test_prefix_1", "add_key_1", 123, None),
        ("TestName3", 30, "test_prefix_1", "add_key_1", 123, 20),
        ("TestName3", 30, "test_prefix_1", "add_key_1", 123, 60),
        ("TestName3", 30, "test_prefix_1", "add_key_1", "user_id_str", None),
        ("TestName3", 30, "test_prefix_1", "add_key_1", "user_id_str", 20),
        ("TestName3", 30, "test_prefix_1", "add_key_1", "user_id_str", 60),
        ("TestName3", 30, "test_prefix_1", "add_key_2", None, None),
        ("TestName3", 30, "test_prefix_1", "add_key_2", None, 20),
        ("TestName3", 30, "test_prefix_1", "add_key_2", None, 60),
        ("TestName3", 30, "test_prefix_1", "add_key_2", 123, None),
        ("TestName3", 30, "test_prefix_1", "add_key_2", 123, 20),
        ("TestName3", 30, "test_prefix_1", "add_key_2", 123, 60),
        ("TestName3", 30, "test_prefix_1", "add_key_2", "user_id_str", None),
        ("TestName3", 30, "test_prefix_1", "add_key_2", "user_id_str", 20),
        ("TestName3", 30, "test_prefix_1", "add_key_2", "user_id_str", 60),
        ("TestName3", 30, "test_prefix_2", None, None, None),
        ("TestName3", 30, "test_prefix_2", None, None, 20),
        ("TestName3", 30, "test_prefix_2", None, None, 60),
        ("TestName3", 30, "test_prefix_2", None, 123, None),
        ("TestName3", 30, "test_prefix_2", None, 123, 20),
        ("TestName3", 30, "test_prefix_2", None, 123, 60),
        ("TestName3", 30, "test_prefix_2", None, "user_id_str", None),
        ("TestName3", 30, "test_prefix_2", None, "user_id_str", 20),
        ("TestName3", 30, "test_prefix_2", None, "user_id_str", 60),
        ("TestName3", 30, "test_prefix_2", "add_key_1", None, None),
        ("TestName3", 30, "test_prefix_2", "add_key_1", None, 20),
        ("TestName3", 30, "test_prefix_2", "add_key_1", None, 60),
        ("TestName3", 30, "test_prefix_2", "add_key_1", 123, None),
        ("TestName3", 30, "test_prefix_2", "add_key_1", 123, 20),
        ("TestName3", 30, "test_prefix_2", "add_key_1", 123, 60),
        ("TestName3", 30, "test_prefix_2", "add_key_1", "user_id_str", None),
        ("TestName3", 30, "test_prefix_2", "add_key_1", "user_id_str", 20),
        ("TestName3", 30, "test_prefix_2", "add_key_1", "user_id_str", 60),
        ("TestName3", 30, "test_prefix_2", "add_key_2", None, None),
        ("TestName3", 30, "test_prefix_2", "add_key_2", None, 20),
        ("TestName3", 30, "test_prefix_2", "add_key_2", None, 60),
        ("TestName3", 30, "test_prefix_2", "add_key_2", 123, None),
        ("TestName3", 30, "test_prefix_2", "add_key_2", 123, 20),
        ("TestName3", 30, "test_prefix_2", "add_key_2", 123, 60),
        ("TestName3", 30, "test_prefix_2", "add_key_2", "user_id_str", None),
        ("TestName3", 30, "test_prefix_2", "add_key_2", "user_id_str", 20),
        ("TestName3", 30, "test_prefix_2", "add_key_2", "user_id_str", 60),
        ("TestName3", 30, "test_prefix_3", None, None, None),
        ("TestName3", 30, "test_prefix_3", None, None, 20),
        ("TestName3", 30, "test_prefix_3", None, None, 60),
        ("TestName3", 30, "test_prefix_3", None, 123, None),
        ("TestName3", 30, "test_prefix_3", None, 123, 20),
        ("TestName3", 30, "test_prefix_3", None, 123, 60),
        ("TestName3", 30, "test_prefix_3", None, "user_id_str", None),
        ("TestName3", 30, "test_prefix_3", None, "user_id_str", 20),
        ("TestName3", 30, "test_prefix_3", None, "user_id_str", 60),
        ("TestName3", 30, "test_prefix_3", "add_key_1", None, None),
        ("TestName3", 30, "test_prefix_3", "add_key_1", None, 20),
        ("TestName3", 30, "test_prefix_3", "add_key_1", None, 60),
        ("TestName3", 30, "test_prefix_3", "add_key_1", 123, None),
        ("TestName3", 30, "test_prefix_3", "add_key_1", 123, 20),
        ("TestName3", 30, "test_prefix_3", "add_key_1", 123, 60),
        ("TestName3", 30, "test_prefix_3", "add_key_1", "user_id_str", None),
        ("TestName3", 30, "test_prefix_3", "add_key_1", "user_id_str", 20),
        ("TestName3", 30, "test_prefix_3", "add_key_1", "user_id_str", 60),
        ("TestName3", 30, "test_prefix_3", "add_key_2", None, None),
        ("TestName3", 30, "test_prefix_3", "add_key_2", None, 20),
        ("TestName3", 30, "test_prefix_3", "add_key_2", None, 60),
        ("TestName3", 30, "test_prefix_3", "add_key_2", 123, None),
        ("TestName3", 30, "test_prefix_3", "add_key_2", 123, 20),
        ("TestName3", 30, "test_prefix_3", "add_key_2", 123, 60),
        ("TestName3", 30, "test_prefix_3", "add_key_2", "user_id_str", None),
        ("TestName3", 30, "test_prefix_3", "add_key_2", "user_id_str", 20),
        ("TestName3", 30, "test_prefix_3", "add_key_2", "user_id_str", 60),
    ]

    for (
        test_name,
        test_value,
        test_prefix,
        test_add_key,
        test_user_id,
        test_ttl_value,
    ) in test_data:

        async with cache_manager() as manager:
            test_model = TestModel(
                name=test_name,
                value=test_value,
            )
            test_cache_key = manager._generate_handler_key(
                test_prefix,
                func_for_cache_test.__name__,
                test_add_key,
                test_user_id,
            )
            result = await manager.cache_handler(
                func_for_cache_test,
                TestModel,
                test_name,
                test_value,
                expire=test_ttl_value,
                prefix=test_prefix,
                additional_key=test_add_key,
                user_id=test_user_id,
            )

            ttl = await manager.redis.ttl(test_cache_key)
            cache_value = await manager.get_cache(test_cache_key)

            assert result == test_model
            if test_ttl_value is None:
                assert ttl == -1
            else:
                assert ttl == test_ttl_value
            assert cache_value == test_model.model_dump()


@pytest.mark.asyncio
async def test_func_invalidate_cache_by_prefix():

    test_data = [
        ("test_prefix_1", None, None),
        ("test_prefix_1", None, 123),
        ("test_prefix_1", None, "user_id_str"),
        ("test_prefix_1", "add_key_1", None),
        ("test_prefix_1", "add_key_1", 123),
        ("test_prefix_1", "add_key_1", "user_id_str"),
        ("test_prefix_1", "add_key_2", None),
        ("test_prefix_1", "add_key_2", 123),
        ("test_prefix_1", "add_key_2", "user_id_str"),
        ("test_prefix_2", None, None),
        ("test_prefix_2", None, 123),
        ("test_prefix_2", None, "user_id_str"),
        ("test_prefix_2", "add_key_1", None),
        ("test_prefix_2", "add_key_1", 123),
        ("test_prefix_2", "add_key_1", "user_id_str"),
        ("test_prefix_2", "add_key_2", None),
        ("test_prefix_2", "add_key_2", 123),
        ("test_prefix_2", "add_key_2", "user_id_str"),
    ]

    invalidate_prefix = "test_prefix_1"
    test_name = "TestName"
    test_value = 4
    test_model = TestModel(
        name=test_name,
        value=test_value,
    )

    async with cache_manager() as manager:

        keys = [
            manager._generate_handler_key(
                prefix,
                func_for_cache_test.__name__,
                key,
                user_id,
            )
            for prefix, key, user_id in test_data
        ]

        for elem in test_data:
            t_prefix, t_key, t_user_id = elem
            await manager.cache_handler(
                func_for_cache_test,
                TestModel,
                test_name,
                test_value,
                expire=60,
                prefix=t_prefix,
                additional_key=t_key,
                user_id=t_user_id,
            )

        for key in keys:
            result = await manager.get_cache(key)
            assert result == test_model.model_dump()

        await manager.invalidate_by_prefix(invalidate_prefix)
        for key in keys:
            result = await manager.get_cache(key)
            logger.info(f"{result}, {key}")
            if invalidate_prefix in key:
                assert result is None
            else:
                assert result == test_model.model_dump()
