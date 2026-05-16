"""
Unit tests for ReviewService.

All external dependencies (repository) are mocked so every test runs
without a live database.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from exceptions.review_exceptions import ReviewAlreadyExistsError, ReviewNotFoundError
from shared.schemas.review_schemas import CreateReview, UpdateReview


# ---------------------------------------------------------------------------
# create_product_review
# ---------------------------------------------------------------------------

class TestCreateProductReview:
    async def test_creates_review_and_returns_schema(
        self,
        review_service_unit,
        mock_review_repository: MagicMock,
        mock_review_orm: MagicMock,
    ) -> None:
        mock_review_repository.filter_by.return_value = []
        mock_review_repository.create.return_value = mock_review_orm

        product_id = uuid4()
        user_id = uuid4()
        data = CreateReview(comment="Excellent!", rating=5.0)

        result = await review_service_unit.create_product_review(user_id, product_id, data)

        assert result.id == mock_review_orm.id
        mock_review_repository.filter_by.assert_awaited_once_with(
            product_id=product_id, user_id=user_id
        )
        mock_review_repository.create.assert_awaited_once()

    async def test_raises_when_review_already_exists(
        self,
        review_service_unit,
        mock_review_repository: MagicMock,
        mock_review_orm: MagicMock,
    ) -> None:
        mock_review_repository.filter_by.return_value = [mock_review_orm]

        with pytest.raises(ReviewAlreadyExistsError):
            await review_service_unit.create_product_review(
                uuid4(), uuid4(), CreateReview(comment="Again", rating=3.0)
            )


# ---------------------------------------------------------------------------
# get_review_by_id
# ---------------------------------------------------------------------------

class TestGetReviewById:
    async def test_returns_review_schema(
        self,
        review_service_unit,
        mock_review_repository: MagicMock,
        mock_review_orm: MagicMock,
    ) -> None:
        mock_review_repository.get_by_id.return_value = mock_review_orm
        review_id = mock_review_orm.id

        result = await review_service_unit.get_review_by_id(review_id)

        assert result.id == review_id

    async def test_raises_when_not_found(
        self,
        review_service_unit,
        mock_review_repository: MagicMock,
    ) -> None:
        mock_review_repository.get_by_id.return_value = None

        with pytest.raises(ReviewNotFoundError):
            await review_service_unit.get_review_by_id(uuid4())


# ---------------------------------------------------------------------------
# get_reviews_by_user_id / get_reviews_by_product_id
# ---------------------------------------------------------------------------

class TestGetReviews:
    async def test_get_reviews_by_user_id(
        self,
        review_service_unit,
        mock_review_repository: MagicMock,
        mock_review_orm: MagicMock,
    ) -> None:
        user_id = uuid4()
        mock_review_repository.get_many_by_field.return_value = [mock_review_orm]

        result = await review_service_unit.get_reviews_by_user_id(user_id)

        assert len(result) == 1
        mock_review_repository.get_many_by_field.assert_awaited_once_with(
            field_name="user_id", value=user_id
        )

    async def test_raises_when_no_reviews_for_user(
        self,
        review_service_unit,
        mock_review_repository: MagicMock,
    ) -> None:
        mock_review_repository.get_many_by_field.return_value = []

        with pytest.raises(ReviewNotFoundError):
            await review_service_unit.get_reviews_by_user_id(uuid4())

    async def test_get_reviews_by_product_id(
        self,
        review_service_unit,
        mock_review_repository: MagicMock,
        mock_review_orm: MagicMock,
    ) -> None:
        product_id = uuid4()
        mock_review_repository.get_many_by_field.return_value = [mock_review_orm]

        result = await review_service_unit.get_reviews_by_product_id(product_id)

        assert len(result) == 1
        mock_review_repository.get_many_by_field.assert_awaited_once_with(
            field_name="product_id", value=product_id
        )

    async def test_raises_when_no_reviews_for_product(
        self,
        review_service_unit,
        mock_review_repository: MagicMock,
    ) -> None:
        mock_review_repository.get_many_by_field.return_value = []

        with pytest.raises(ReviewNotFoundError):
            await review_service_unit.get_reviews_by_product_id(uuid4())


# ---------------------------------------------------------------------------
# get_review_by_product_id_and_user_id
# ---------------------------------------------------------------------------

class TestGetReviewByProductAndUser:
    async def test_returns_review(
        self,
        review_service_unit,
        mock_review_repository: MagicMock,
        mock_review_orm: MagicMock,
    ) -> None:
        mock_review_repository.filter_by.return_value = [mock_review_orm]

        result = await review_service_unit.get_review_by_product_id_and_user_id(
            product_id=uuid4(), user_id=uuid4()
        )

        assert result.id == mock_review_orm.id

    async def test_raises_when_not_found(
        self,
        review_service_unit,
        mock_review_repository: MagicMock,
    ) -> None:
        mock_review_repository.filter_by.return_value = []

        with pytest.raises(ReviewNotFoundError):
            await review_service_unit.get_review_by_product_id_and_user_id(
                product_id=uuid4(), user_id=uuid4()
            )


# ---------------------------------------------------------------------------
# get_all_reviews
# ---------------------------------------------------------------------------

class TestGetAllReviews:
    async def test_returns_all_reviews(
        self,
        review_service_unit,
        mock_review_repository: MagicMock,
        mock_review_orm: MagicMock,
    ) -> None:
        mock_review_repository.get_all.return_value = [mock_review_orm]

        result = await review_service_unit.get_all_reviews()

        assert len(result) == 1

    async def test_raises_when_no_reviews(
        self,
        review_service_unit,
        mock_review_repository: MagicMock,
    ) -> None:
        mock_review_repository.get_all.return_value = []

        with pytest.raises(ReviewNotFoundError):
            await review_service_unit.get_all_reviews()


# ---------------------------------------------------------------------------
# update_product_review
# ---------------------------------------------------------------------------

class TestUpdateProductReview:
    async def test_updates_comment_and_rating(
        self,
        review_service_unit,
        mock_review_repository: MagicMock,
        mock_review_orm: MagicMock,
    ) -> None:
        mock_review_repository.filter_by.return_value = [mock_review_orm]
        mock_review_repository.update.return_value = mock_review_orm

        update_data = UpdateReview(comment="Updated comment", rating=3.0)
        result = await review_service_unit.update_product_review(
            product_id=uuid4(), user_id=uuid4(), update_data=update_data
        )

        assert result.id == mock_review_orm.id
        assert mock_review_orm.comment == "Updated comment"
        assert mock_review_orm.rating == 3.0

    async def test_raises_when_review_not_found(
        self,
        review_service_unit,
        mock_review_repository: MagicMock,
    ) -> None:
        mock_review_repository.filter_by.return_value = []

        with pytest.raises(ReviewNotFoundError):
            await review_service_unit.update_product_review(
                product_id=uuid4(),
                user_id=uuid4(),
                update_data=UpdateReview(rating=2.0),
            )


# ---------------------------------------------------------------------------
# delete_product_review
# ---------------------------------------------------------------------------

class TestDeleteProductReview:
    async def test_deletes_review_successfully(
        self,
        review_service_unit,
        mock_review_repository: MagicMock,
        mock_review_orm: MagicMock,
    ) -> None:
        mock_review_repository.get_by_id.return_value = mock_review_orm
        review_id = mock_review_orm.id

        await review_service_unit.delete_product_review(review_id)

        mock_review_repository.delete.assert_awaited_once_with(mock_review_orm)

    async def test_raises_when_review_not_found(
        self,
        review_service_unit,
        mock_review_repository: MagicMock,
    ) -> None:
        mock_review_repository.get_by_id.return_value = None

        with pytest.raises(ReviewNotFoundError):
            await review_service_unit.delete_product_review(uuid4())
