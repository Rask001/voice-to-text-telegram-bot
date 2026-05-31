from dataclasses import dataclass


OWNER = "owner"
BROTHER = "brother"
FREE = "free"
STANDARD = "standard"
PREMIUM = "premium"


@dataclass(frozen=True)
class TariffPlan:
    code: str
    label: str
    daily_voice_limit: int | None
    max_voice_seconds: int | None
    minutes_limit_month: int | None
    minutes_limit_total: int | None
    trial_days: int | None = None


TARIFFS = {
    OWNER: TariffPlan(
        code=OWNER,
        label="Owner",
        daily_voice_limit=None,
        max_voice_seconds=None,
        minutes_limit_month=None,
        minutes_limit_total=None,
    ),
    BROTHER: TariffPlan(
        code=BROTHER,
        label="По-братски от Тоши",
        daily_voice_limit=10,
        max_voice_seconds=10 * 60,
        minutes_limit_month=67,
        minutes_limit_total=None,
    ),
    FREE: TariffPlan(
        code=FREE,
        label="Free",
        daily_voice_limit=3,
        max_voice_seconds=5 * 60,
        minutes_limit_month=15,
        minutes_limit_total=15,
        trial_days=3,
    ),
    STANDARD: TariffPlan(
        code=STANDARD,
        label="Standard",
        daily_voice_limit=30,
        max_voice_seconds=10 * 60,
        minutes_limit_month=300,
        minutes_limit_total=None,
    ),
    PREMIUM: TariffPlan(
        code=PREMIUM,
        label="Premium",
        daily_voice_limit=100,
        max_voice_seconds=15 * 60,
        minutes_limit_month=1500,
        minutes_limit_total=None,
    ),
}


def get_tariff(code: str) -> TariffPlan:
    return TARIFFS.get(code, TARIFFS[FREE])
