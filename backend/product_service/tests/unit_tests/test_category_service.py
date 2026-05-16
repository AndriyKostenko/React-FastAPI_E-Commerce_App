"""
Unit tests for CategoryService.

All external dependencies (repository, image processing) are mocked
so every test runs without a live database or filesystem.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from exceptions.category_exceptions import CategoryCreationError, CategoryNotFoundError
from shared.schemas.category_schema import CreateCategory


# ---------------------------------------------------------------------------
# create_category
# ---------------------------------------------------------------------------

class TestCreateCategory:
    async def test_creates_category_and_returns_schema(
        self,
        category_service_unit,
        mock_category_repository: MagicMock,
        mock_category_orm: MagicMock,
    ) -> None:
        mock_category_repository.get_by_field.return_value = None
        mock_category_repository.create.return_value = mock_category_orm

        data = CreateCategory(name="Electronics")
        result = await category_service_unit.create_category(data)

        assert result.name == "electronics"
        mock_category_repository.get_by_field.assert_awaited_once_with("name", "electronics")
        mock_category_repository.create.assert_awaited_once()

    async def test_raises_when_category_already_exists(
        self,
        category_service_unit,
        mock_category_repository: MagicMock,
        mock_category_orm: MagicMock,
    ) -> None:
        mock_category_repository.get_by_field.return_value = mock_category_orm

        data = CreateCategory(name="Electronics")
        with pytest.raises(CategoryCreationError):
            await category_service_unit.create_category(data)

    async def test_name_normalized_to_lowercase(
        self,
        category_service_unit,
        mock_category_repository: MagicMock,
        mock_category_orm: MagicMock,
    ) -> None:
        mock_category_repository.get_by_field.return_value = None
        mock_category_repository.create.return_value = mock_category_orm

        data = CreateCategory(name="HOME APPLIANCES")
        await category_service_unit.create_category(data)

        created = mock_category_repository.create.call_args[0][0]
        assert created.name == "home appliances"


# ---------------------------------------------------------------------------
# get_all_categories
# ---------------------------------------------------------------------------

class TestGetAllCategories:
    async def test_returns_category_list(
        self,
        category_service_unit,
        mock_category_repository: MagicMock,
        mock_category_orm: MagicMock,
    ) -> None:
        mock_category_repository.get_all.return_value = [mock_category_orm]

        result = await category_service_unit.get_all_categories()

        assert len(result) == 1
        assert result[0].id == mock_category_orm.id

    async def test_raises_when_no_categories(
        self,
        category_service_unit,
        mock_category_repository: MagicMock,
    ) -> None:
        mock_category_repository.get_all.return_value = []

        with pytest.raises(CategoryNotFoundError):
            await category_service_unit.get_all_categories()


# ---------------------------------------------------------------------------
# get_category_by_id
# ---------------------------------------------------------------------------

class TestGetCategoryById:
    async def test_returns_category_schema(
        self,
        category_service_unit,
        mock_category_repository: MagicMock,
        mock_category_orm: MagicMock,
    ) -> None:
        mock_category_repository.get_by_id.return_value = mock_category_orm
        category_id = mock_category_orm.id

        result = await category_service_unit.get_category_by_id(category_id)

        assert result.id == category_id

    async def test_raises_when_not_found(
        self,
        category_service_unit,
        mock_category_repository: MagicMock,
    ) -> None:
        mock_category_repository.get_by_id.return_value = None

        with pytest.raises(CategoryNotFoundError):
            await category_service_unit.get_category_by_id(uuid4())


# ---------------------------------------------------------------------------
# get_category_by_name
# ---------------------------------------------------------------------------

class TestGetCategoryByName:
    async def test_returns_category_by_name(
        self,
        category_service_unit,
        mock_category_repository: MagicMock,
        mock_category_orm: MagicMock,
    ) -> None:
        mock_category_repository.get_by_field.return_value = mock_category_orm

        result = await category_service_unit.get_category_by_name("Electronics")

        mock_category_repository.get_by_field.assert_awaited_once_with("name", value="electronics")
        assert result.name == mock_category_orm.name

    async def test_raises_when_name_not_found(
        self,
        category_service_unit,
        mock_category_repository: MagicMock,
    ) -> None:
        mock_category_repository.get_by_field.return_value = None

        with pytest.raises(CategoryNotFoundError):
            await category_service_unit.get_category_by_name("Unknown")


# ---------------------------------------------------------------------------
# update_category
# ---------------------------------------------------------------------------

class TestUpdateCategory:
    async def test_updates_name_and_returns_schema(
        self,
        category_service_unit,
        mock_category_repository: MagicMock,
        mock_category_orm: MagicMock,
    ) -> None:
        mock_category_repository.update_by_id.return_value = mock_category_orm
        category_id = mock_category_orm.id

        result = await category_service_unit.update_category(category_id, name="Audio")

        mock_category_repository.update_by_id.assert_awaited_once_with(
            category_id, data={"name": "audio"}
        )
        assert result.id == category_id

    async def test_raises_when_category_not_found(
        self,
        category_service_unit,
        mock_category_repository: MagicMock,
    ) -> None:
        mock_category_repository.update_by_id.return_value = None

        with pytest.raises(CategoryNotFoundError):
            await category_service_unit.update_category(uuid4(), name="Audio")

    async def test_no_fields_provided_results_in_empty_update(
        self,
        category_service_unit,
        mock_category_repository: MagicMock,
        mock_category_orm: MagicMock,
    ) -> None:
        mock_category_repository.update_by_id.return_value = mock_category_orm

        result = await category_service_unit.update_category(mock_category_orm.id)

        mock_category_repository.update_by_id.assert_awaited_once_with(
            mock_category_orm.id, data={}
        )
        assert result is not None


# ---------------------------------------------------------------------------
# delete_category
# ---------------------------------------------------------------------------

class TestDeleteCategory:
    async def test_deletes_category_successfully(
        self,
        category_service_unit,
        mock_category_repository: MagicMock,
    ) -> None:
        mock_category_repository.delete_by_id.return_value = True
        category_id = uuid4()

        await category_service_unit.delete_category(category_id)

        mock_category_repository.delete_by_id.assert_awaited_once_with(category_id)

    async def test_raises_when_category_not_found(
        self,
        category_service_unit,
        mock_category_repository: MagicMock,
    ) -> None:
        mock_category_repository.delete_by_id.return_value = False

        with pytest.raises(CategoryNotFoundError):
            await category_service_unit.delete_category(uuid4())
