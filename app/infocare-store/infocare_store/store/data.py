import typing
import attr
import structlog

logger = structlog.get_logger(__name__)


@attr.s
class CrawlerStatistics(object):
    #: 지역
    region_count: int = attr.ib(default=0)
    #: 수집한 데이터 갯수
    statistics_count: int = attr.ib(default=0)
    #: 낙찰사례 더보기 사례 갯수
    bids_count: int = attr.ib(default=0)

    class CrawlerStatisticsData(typing.Dict):
        region_count: int
        statistics_count: int
        bids_count: int

    @classmethod
    def from_json(cls, data: CrawlerStatisticsData) -> "CrawlerStatistics":
        return cls(
            region_count=data["region_count"],
            statistics_count=data["statistics_count"],
            bids_count=data["bids_count"],
        )


@attr.s(frozen=True)
class CrawlerLogResponse(object):
    time_stamp: float = attr.ib()
    run_by: str = attr.ib()
    finish_time_stamp: float = attr.ib()
    total_statistics: CrawlerStatistics = attr.ib()

    class CrawlerLogResponseData(typing.Dict):
        time_stamp: str
        run_by: str
        finish_time_stamp: str
        total_statistics: CrawlerStatistics.CrawlerStatisticsData

    @classmethod
    def from_json(cls, data: CrawlerLogResponseData) -> "CrawlerLogResponse":
        return cls(
            time_stamp=float(data["time_stamp"]),
            run_by=data["run_by"],
            finish_time_stamp=float(data["finish_time_stamp"]),
            total_statistics=CrawlerStatistics.from_json(
                data["total_statistics"]
            ),
        )
