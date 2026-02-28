from pydantic import BaseModel, ConfigDict, model_validator


class OHLCVRow(BaseModel):
    open: float
    high: float
    low: float
    close: float
    volume: int


class StockHistoryResult(BaseModel):
    symbol: str
    period: str
    data: dict[str, OHLCVRow]

    @model_validator(mode="after")
    def data_not_empty(self) -> "StockHistoryResult":
        if not self.data:
            raise ValueError("data has no rows")
        return self


class TopGainerResult(BaseModel):
    timestamp: str
    symbol: str
    name: str | None
    exchange: str
    price: float
    change_absolute: float
    change_pct: float
    volume: int
    market_cap: int | None


class AnalyzerInput(BaseModel):
    model_config = ConfigDict(extra="allow")
