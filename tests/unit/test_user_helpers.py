"""Unit tests for helpers in app.api.user."""

from __future__ import annotations

import pytest

from app.api.user import _extract_cloudinary_public_id


@pytest.mark.parametrize(
    "url,expected",
    [
        (
            "https://res.cloudinary.com/demo/image/upload/v1234567890/folder/name.jpg",
            "folder/name",
        ),
        (
            "https://res.cloudinary.com/demo/image/upload/folder/name.png",
            "folder/name",
        ),
    ],
)
def test_extract_cloudinary_public_id(url, expected):
    """Test that the Cloudinary public ID is extracted from a URL."""
    assert _extract_cloudinary_public_id(url) == expected
