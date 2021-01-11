import datetime
import re
import typing

import pytz
import structlog
from crawler.aws_client import S3Client
from crawler.infocare_schema import (
    InfocareStatisticResponse,
    InfocareBidResponse,
    MAIN_USAGE_TYPE,
)
from infocare_store.db import create_session_factory, init_loan_db_schema
from loan_model.models.infocare.infocare_bid import InfocareBid
from loan_model.models.infocare.infocare_dong import InfocareDong
from loan_model.models.infocare.infocare_gugun import InfocareGugun
from loan_model.models.infocare.infocare_sido import InfocareSido
from loan_model.models.infocare.infocare_statistics import InfocareStatistics
from tanker.slack import SlackClient
from tanker.utils.datetime import tzfromtimestamp
from tanker.utils.datetime import tznow

from .exc import InfocareStoreS3NotFound, InfocareStoreRegionNotFound

logger = structlog.get_logger(__name__)


class InfocareStore(object):
    def __init__(self, config: typing.Dict[str, typing.Any]) -> None:
        super().__init__()
        self.config = config
        self.session_factory = create_session_factory(config)
        self.s3_client = S3Client(config)
        self.slack_client = SlackClient(
            config.get("SLACK_CHANNEL"), config.get("SLACK_API_TOKEN")
        )
        self.storing_date: datetime.datetime = tznow(
            pytz.timezone("Asia/Seoul")
        )
        self.region_level_1 = self.config["REGION_REGEX_LEVEL_1"]
        self.region_level_2 = self.config["REGION_REGEX_LEVEL_2"]
        self.region_level_3 = self.config["REGION_REGEX_LEVEL_3"]
        self.competed_sido_ids: typing.Dict[str, int] = dict()
        self.completed_gugun_ids: typing.Dict[str, int] = dict()

    def run(self, run_by: str) -> None:
        if self.config["ENVIRONMENT"] == "local":
            session = self.session_factory()
            try:
                init_loan_db_schema(session)
            except Exception:
                raise
            finally:
                session.close()

        self.slack_client.send_info_slack(
            f"Store 시작합니다. ({self.config['ENVIRONMENT']}, {run_by})"
        )
        crawler_log_id = self.config["CRAWLER_LOG_ID"]

        if crawler_log_id:
            self.fetch_received_log_folder()  # 수동 log id 폴더 저장
        else:
            self.fetch_latest_log_folder()  # 최신 log id 폴더 저장

        self.slack_client.send_info_slack(
            f"Store 종료합니다. ({self.config['ENVIRONMENT']}, {run_by})"
        )

    def fetch_latest_log_folder(self) -> None:
        env_prefix = f"{self.config['ENVIRONMENT']}/"
        year_prefix = self.fetch_latest_date_folder(env_prefix)
        month_prefix = self.fetch_latest_date_folder(year_prefix)
        day_prefix = self.fetch_latest_date_folder(month_prefix)
        log_id_prefix = self.fetch_latest_date_folder(day_prefix)
        self.fetch_sido_region_folder(log_id_prefix)

    def fetch_latest_date_folder(self, base_prefix: str) -> str:
        date_list: typing.List[str] = list()
        for response in self.s3_client.get_objects(base_prefix, Delimiter="/"):
            prefixes = response.common_prefixes
            if not prefixes:
                raise InfocareStoreS3NotFound("not found date list")
            for date_prefix in prefixes:
                date = (
                    date_prefix["Prefix"]
                    .replace(base_prefix, "")
                    .replace("/", "")
                    .strip()
                )
                date_list.append(date)
            date_list.sort()
        base_prefix += date_list[-1] + "/"

        return base_prefix

    def fetch_received_log_folder(self) -> None:
        crawler_log_id = self.config["CRAWLER_LOG_ID"]
        crawler_date = tzfromtimestamp(float(crawler_log_id))
        log_id_prefix = (
            f"{self.config['ENVIRONMENT']}/"
            f"{crawler_date.year}/"
            f"{crawler_date.month}/"
            f"{crawler_date.day}/"
            f"{crawler_log_id}/"
        )
        self.fetch_sido_region_folder(log_id_prefix)

    def fetch_sido_region_folder(self, log_id_prefix: str) -> None:
        data_prefix = log_id_prefix + "data/"
        sido_check: bool = False
        for response in self.s3_client.get_objects(data_prefix, Delimiter="/"):
            prefixes = response.common_prefixes
            if not prefixes:
                raise InfocareStoreS3NotFound("not found sido region list")
            for sido_prefix in prefixes:
                sido_name = (
                    sido_prefix["Prefix"]
                    .replace(data_prefix, "")
                    .replace("/", "")
                    .strip()
                )
                if re.search(self.region_level_1, sido_name):
                    sido_check = True
                    self.fetch_gugun_region_folder(sido_prefix["Prefix"])

        if not sido_check:
            raise InfocareStoreRegionNotFound(
                f"not found sido({self.region_level_1})"
            )

    def fetch_gugun_region_folder(self, sido_prefix: str) -> None:
        gugun_check: bool = False
        for response in self.s3_client.get_objects(sido_prefix, Delimiter="/"):
            prefixes = response.common_prefixes
            if not prefixes:
                raise InfocareStoreS3NotFound("not found gugun region list")
            for gugun_prefix in prefixes:
                gugun_name = (
                    gugun_prefix["Prefix"]
                    .replace(sido_prefix, "")
                    .replace("/", "")
                    .strip()
                )
                if re.search(self.region_level_2, gugun_name):
                    gugun_check = True
                    self.fetch_dong_region_folder(gugun_prefix["Prefix"])

        if not gugun_check:
            raise InfocareStoreRegionNotFound(
                f"not found gugun({self.region_level_2})"
            )

    def fetch_dong_region_folder(self, gugun_prefix: str) -> None:
        dong_check: bool = False
        for response in self.s3_client.get_objects(
            gugun_prefix, Delimiter="/"
        ):
            prefixes = response.common_prefixes
            if not prefixes:
                raise InfocareStoreS3NotFound("not found dong region list")
            for dong_prefix in prefixes:
                dong_name = (
                    dong_prefix["Prefix"]
                    .replace(gugun_prefix, "")
                    .replace("/", "")
                    .strip()
                )
                if re.search(self.region_level_3, dong_name):
                    dong_check = True
                    self.fetch_main_using_type_folder(dong_prefix["Prefix"])

        if not dong_check:
            raise InfocareStoreRegionNotFound(
                f"not found dong({self.region_level_3})"
            )

    def fetch_main_using_type_folder(self, dong_prefix: str) -> None:
        for response in self.s3_client.get_objects(dong_prefix, Delimiter="/"):
            prefixes = response.common_prefixes
            if not prefixes:
                raise InfocareStoreS3NotFound("not found main using list")
            for main_using_prefix in prefixes:
                self.fetch_sub_using_type_folder(main_using_prefix["Prefix"])

    def fetch_sub_using_type_folder(self, main_using_prefix: str) -> None:
        for response in self.s3_client.get_objects(
            main_using_prefix, Delimiter="/"
        ):
            prefixes = response.common_prefixes
            if not prefixes:
                raise InfocareStoreS3NotFound("not found sub using list")
            for sub_using_prefix in prefixes:
                self.fetch_statistics_folder(sub_using_prefix["Prefix"])

    def fetch_statistics_folder(self, sub_using_prefix: str) -> None:
        """
        인포케어 통계 html 파일에는 선택된 시도, 시군구, 동읍면에 대한 통계가 드롭다운형식으로
        저장되어있음. 해당 드롭다운의 인덱스를 활용하여 중복데이터 저장을 방지합니다.

        만약에 시도가 바뀌었다면 드롭다운에서의 시군구와 동읍면의 인덱스는 첫번째일것이며
        만약에 시군구가 바뀌었다면 드롭다운에서의 동읍면의 인덱스는 첫번째일것입니다.

        해당 html 파일에서 데이터가 선택된 시,도에 대한
        첫번째 시군구 and 첫번째 동읍면이라면 시,도가 바뀐것으로
        시도, 시군구, 동읍면의 통계를 전부 저장합니다.

        해당 html 파일에서 데이터가 선택된 시군구에 대한
        첫번째 동읍면이라면 시군구가 바뀐것으로
        시군구, 동읍면 통계를 전부 저장합니다.

        위의 2가지 케이스에 해당하지 않으면 동읍면 통계만 저장합니다.
        """

        for response in self.s3_client.get_objects(
            sub_using_prefix, Delimiter="/"
        ):
            contents = response.contents
            prefixes = response.common_prefixes
            if not contents:
                raise InfocareStoreS3NotFound("not found statistics data")
            for content in contents:
                file_prefix = content["Key"]
                s3_response = self.s3_client.get_object(file_prefix)
                statistics_data = s3_response.body.read().decode("utf-8")
                statistics = InfocareStatisticResponse.from_html(
                    statistics_data
                )

                # 시,도 통계 저장
                if (
                    statistics.first_gugun_name == statistics.gugun_name
                    and statistics.first_dong_name == statistics.dong_name
                ):
                    db_sido_id = self.store_sido_region(statistics.sido_name)
                    self.store_statistics_data(
                        statistics,
                        db_sido_id=db_sido_id,
                    )
                    # sido id 캐싱
                    self.competed_sido_ids.update(
                        {statistics.sido_name: db_sido_id}
                    )
                # 시,군,구 통계 저장
                if statistics.first_dong_name == statistics.dong_name:
                    sido_name = statistics.sido_name
                    db_sido_id = self.competed_sido_ids[sido_name]
                    db_gugun_id = self.store_gugun_region(
                        statistics.gugun_name, db_sido_id
                    )
                    self.store_statistics_data(
                        statistics,
                        db_gugun_id=db_gugun_id,
                    )
                    # gugun id 캐싱
                    self.completed_gugun_ids.update(
                        {statistics.gugun_name: db_gugun_id}
                    )
                # 읍,면,동 통계 저장
                gugun_name = statistics.gugun_name
                db_gugun_id = self.completed_gugun_ids[gugun_name]
                db_dong_id = self.store_dong_region(
                    statistics.dong_name, db_gugun_id
                )
                self.store_statistics_data(
                    statistics,
                    db_dong_id=db_dong_id,
                )

                if prefixes:  # 낙찰사례 페이지 저장
                    for bid_prefix in prefixes:
                        self.fetch_bid_folder(
                            bid_prefix["Prefix"], statistics, db_dong_id
                        )
                else:  # 해당 동에 대한 낙찰사례가 없는경우 전에 있던 낙찰사례를 만료시킴
                    self.store_bid_expired_check(
                        statistics_data=statistics,
                        db_dong_id=db_dong_id,
                        bid_list=[],
                    )

    def fetch_bid_folder(
        self,
        bid_prefix: str,
        statistics_data: InfocareStatisticResponse,
        db_dong_id: int,
    ) -> None:  # 낙찰사례 페이지일 경우,
        for response in self.s3_client.get_objects(bid_prefix, Delimiter="/"):
            contents = response.contents
            if not contents:
                raise InfocareStoreS3NotFound("not found bid data")
            for content in contents:
                file_prefix = content["Key"]
                s3_response = self.s3_client.get_object(file_prefix)
                bid_data = s3_response.body.read().decode("utf-8")
                bid_response = InfocareBidResponse.from_html(bid_data)
                bid_list = bid_response.infocare_bid_list
                self.store_bid_expired_check(
                    bid_list=bid_list,
                    statistics_data=statistics_data,
                    db_dong_id=db_dong_id,
                )  # 해당 동에 대한 낙찰사례를 순회하며 만료시킴
                self.store_bid_data(bid_list, statistics_data, db_dong_id)

    def store_sido_region(self, sido_name: str) -> int:
        session = self.session_factory()
        try:
            db_sido = InfocareSido.create_or_update(session, sido_name)
            db_sido_id = db_sido.id
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        return db_sido_id

    def store_gugun_region(self, gugun_name: str, db_sido_id: int) -> int:
        session = self.session_factory()
        try:
            db_gugun = InfocareGugun.create_or_update(
                session, gugun_name, db_sido_id
            )
            db_gugun_id = db_gugun.id
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        return db_gugun_id

    def store_dong_region(self, dong_name: str, db_gugun_id: int) -> int:
        session = self.session_factory()
        try:
            db_dong = InfocareDong.create_or_update(
                session, dong_name, db_gugun_id
            )
            db_dong_id = db_dong.id
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

        return db_dong_id

    def store_statistics_data(
        self,
        data: InfocareStatisticResponse,
        *,
        db_sido_id: typing.Optional[int] = None,
        db_gugun_id: typing.Optional[int] = None,
        db_dong_id: typing.Optional[int] = None,
    ) -> None:
        session = self.session_factory()
        # Store sido statistics
        if db_sido_id:
            if data.sido_year_bid_count == 0:
                return
            try:
                InfocareStatistics.create_or_update(
                    session,
                    data.start_date,
                    data.end_date,
                    MAIN_USAGE_TYPE[data.main_usage_type],
                    data.sub_usage_type,
                    data.sido_year_avg_price_rate,
                    data.sido_year_avg_bid_rate,
                    data.sido_year_bid_count,
                    data.sido_six_month_avg_price_rate,
                    data.sido_six_month_avg_bid_rate,
                    data.sido_six_month_bid_count,
                    data.sido_three_month_avg_price_rate,
                    data.sido_three_month_avg_bid_rate,
                    data.sido_three_month_bid_count,
                    db_sido_id,
                    db_gugun_id,
                    db_dong_id,
                )
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
            logger.info("Store Sido Statistics", sido=data.sido_name)

        # Store gugun statistics
        elif db_gugun_id:
            if data.gugun_year_bid_count == 0:
                return
            try:
                InfocareStatistics.create_or_update(
                    session,
                    data.start_date,
                    data.end_date,
                    MAIN_USAGE_TYPE[data.main_usage_type],
                    data.sub_usage_type,
                    data.gugun_year_avg_price_rate,
                    data.gugun_year_avg_bid_rate,
                    data.gugun_year_bid_count,
                    data.gugun_six_month_avg_price_rate,
                    data.gugun_six_month_avg_bid_rate,
                    data.gugun_six_month_bid_count,
                    data.gugun_three_month_avg_price_rate,
                    data.gugun_three_month_avg_bid_rate,
                    data.gugun_three_month_bid_count,
                    db_sido_id,
                    db_gugun_id,
                    db_dong_id,
                )
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
            logger.info(
                "Store Gugun Statistics",
                sido=data.sido_name,
                gugun=data.gugun_name,
            )

        # Store dong statistics
        elif db_dong_id:
            if data.dongli_year_bid_count == 0:
                return
            try:
                InfocareStatistics.create_or_update(
                    session,
                    data.start_date,
                    data.end_date,
                    MAIN_USAGE_TYPE[data.main_usage_type],
                    data.sub_usage_type,
                    data.dongli_year_avg_price_rate,
                    data.dongli_year_avg_bid_rate,
                    data.dongli_year_bid_count,
                    data.dongli_six_month_avg_price_rate,
                    data.dongli_six_month_avg_bid_rate,
                    data.dongli_six_month_bid_count,
                    data.dongli_three_month_avg_price_rate,
                    data.dongli_three_month_avg_bid_rate,
                    data.dongli_three_month_bid_count,
                    db_sido_id,
                    db_gugun_id,
                    db_dong_id,
                )
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
            logger.info(
                "Store Dong Statistics",
                sido=data.sido_name,
                gugun=data.gugun_name,
                dong=data.dong_name,
            )

    def store_bid_data(
        self,
        bid_list: typing.List[InfocareBid],
        statistics_data: InfocareStatisticResponse,
        db_dong_id: int,
    ) -> None:
        for bid in bid_list:
            session = self.session_factory()
            try:
                InfocareBid.create_or_update(
                    session,
                    bid.case_number,
                    bid.address,
                    MAIN_USAGE_TYPE[statistics_data.main_usage_type],
                    statistics_data.sub_usage_type,
                    bid.bid_date,
                    bid.estimated_price,
                    bid.lowest_price,
                    bid.success_price,
                    bid.success_bid_rate,
                    db_dong_id,
                )
                session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()
            logger.info("Store Bid Statistics", bid=bid.address)

    def store_bid_expired_check(
        self,
        *,
        statistics_data: InfocareStatisticResponse,
        db_dong_id: int,
        bid_list: typing.List[InfocareBid],
    ) -> None:
        session = self.session_factory()

        try:
            db_bid_list = (
                session.query(InfocareBid)
                .filter(
                    InfocareBid.infocare_dong_id == db_dong_id,
                    InfocareBid.expired_date.is_(None),
                )
                .all()
            )

            for db_bid in db_bid_list:
                expired_check = True
                if bid_list:
                    for bid in bid_list:
                        if (
                            db_bid.bid_date == bid.bid_date.date()
                            and db_bid.case_number == bid.case_number
                            and db_bid.address == bid.address
                            and db_bid.main_usage_type.name
                            == MAIN_USAGE_TYPE[statistics_data.main_usage_type]
                            and db_bid.sub_usage_type
                            == statistics_data.sub_usage_type
                        ):
                            expired_check = False

                if expired_check:  # db에 저장된 해당 데이터가 만료되었으면
                    InfocareBid.update_expired_date(
                        session, db_bid, self.storing_date
                    )
                    session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
