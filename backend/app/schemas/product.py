"""
Product Pydantic schemas.
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ProductBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, examples=["Organic Honey 500g"])
    category: str = Field(..., min_length=1, max_length=100, examples=["Food & Beverage"])
    scanned_image_url: str | None = Field(default=None, examples=["https://storage.example.com/img.png"])


class ProductCreate(ProductBase):
    pass


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    scanned_image_url: str | None = None


class ProductRead(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
