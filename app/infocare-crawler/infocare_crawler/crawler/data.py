import typing

import attr


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
    time_stamp: int = attr.ib()
    run_by: str = attr.ib()
    finish_time_stamp: int = attr.ib()
    total_statistics: CrawlerStatistics = attr.ib()

    class CrawlerLogResponseData(typing.Dict):
        time_stamp: str
        run_by: str
        finish_time_stamp: str
        total_statistics: CrawlerStatistics.CrawlerStatisticsData

    @classmethod
    def from_json(cls, data: CrawlerLogResponseData) -> "CrawlerLogResponse":
        return cls(
            time_stamp=int(data["time_stamp"]),
            run_by=data["run_by"],
            finish_time_stamp=int(data["finish_time_stamp"]),
            total_statistics=CrawlerStatistics.from_json(
                data["total_statistics"]
            ),
        )


def slack_failure_percentage_statistics(
    total_statistics: CrawlerStatistics, failure_statistics: CrawlerStatistics,
) -> typing.Dict[str, typing.Any]:
    total_statistics_dict = attr.asdict(total_statistics)
    failure_statistics_dict = attr.asdict(failure_statistics)

    keys = tuple(total_statistics_dict.keys())

    result = dict()
    for key in keys:
        total_value = total_statistics_dict[key]
        failure_value = failure_statistics_dict[key]
        try:
            result[key] = (
                f"total: {total_value}\n"
                f"fail: {failure_value}\n"
                f"{100 *  failure_value / total_value}%"
            )
        except ZeroDivisionError:
            result[key] = (
                f"total: {total_value}\n"
                f"fail: {failure_value}\n"
            )

    return result
