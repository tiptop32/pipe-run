from app.db.base import Base  # noqa: F401
from app.features.pipelines.models import AllureReport, CustomPipeline, ScheduleBookmark, UserProject  # noqa: F401

target_metadata = Base.metadata
