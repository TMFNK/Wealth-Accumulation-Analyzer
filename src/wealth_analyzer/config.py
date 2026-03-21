from __future__ import annotations

import re
import tomllib
from datetime import date
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _parse_iso_date(value: str) -> date:
    # date.fromisoformat is strict and matches YYYY-MM-DD.
    if not _ISO_DATE_RE.fullmatch(value):
        raise ValueError("must be an ISO date string YYYY-MM-DD")
    return date.fromisoformat(value)


def _parse_date_like(value: Any, *, allow_today: bool) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        if allow_today and value == "today":
            return date.today()
        return _parse_iso_date(value)
    raise TypeError("must be a date or ISO date string")


class GeneralConfig(BaseModel):
    start_date: date
    end_date: date
    cache_ttl_days: int = Field(default=1, ge=0)

    @field_validator("start_date", mode="before")
    @classmethod
    def _parse_start_date(cls, v: Any) -> date:
        return _parse_date_like(v, allow_today=False)

    @field_validator("end_date", mode="before")
    @classmethod
    def _parse_end_date(cls, v: Any) -> date:
        return _parse_date_like(v, allow_today=True)

    @model_validator(mode="after")
    def _validate_range(self) -> "GeneralConfig":
        if self.start_date >= self.end_date:
            raise ValueError("start_date must be before end_date")
        return self


class InvestmentConfig(BaseModel):
    lump_sum_amount: float = Field(gt=0)
    dca_monthly_amount: float = Field(gt=0)
    risk_free_rate: float = Field(ge=0.0, le=1.0)


class TickersConfig(BaseModel):
    stocks: list[str]
    etfs: list[str]
    qqqm_proxy: str = "QQQ"

    @field_validator("stocks", "etfs")
    @classmethod
    def _non_empty_list(cls, v: Any) -> Any:
        if not isinstance(v, list) or not v:
            raise ValueError("must be a non-empty list")
        return v

    @field_validator("qqqm_proxy")
    @classmethod
    def _non_empty_str(cls, v: Any) -> Any:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("must be a non-empty string")
        return v.strip()


class OutputConfig(BaseModel):
    output_dir: str = "outputs"
    chart_dpi: int = Field(default=150, gt=0)
    excel_filename: str = "wealth_analysis_{date}.xlsx"
    pdf_filename: str = "wealth_analysis_{date}.pdf"
    log_level: str = "INFO"


class AppConfig(BaseSettings):
    general: GeneralConfig
    investment: InvestmentConfig
    tickers: TickersConfig
    output: OutputConfig

    model_config = SettingsConfigDict(extra="forbid")


def load_config(path: str = "config.toml") -> AppConfig:
    with open(path, "rb") as f:
        raw = tomllib.load(f)
    return AppConfig(**raw)
