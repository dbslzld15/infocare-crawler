import typing
import tempfile
import pytz
import datetime
import re
import attr
import structlog
from tanker.slack import SlackClient
from tanker.utils.datetime import tznow, timestamp
from crawler.aws_client import S3Client
from crawler.utils.download import write_file
from infocare_crawler.client import InfocareClient
from .data import CrawlerStatistics, slack_failure_percentage_statistics
from infocare_crawler.client.data import InfocareSearchResponse

logger = structlog.get_logger(__name__)

SeoulTZ = pytz.timezone("Asia/Seoul")


class InfoCareCrawler(object):
    def __init__(
        self,
        config: typing.Dict[str, typing.Any],
    ):
        super().__init__()
        self.config = config

        self.slack_client = SlackClient(
            config.get("SLACK_CHANNEL"), config.get("SLACK_API_TOKEN")
        )
        self.info_care_client = InfocareClient(config)
        self.s3_client = S3Client(config)
        self.total_statistics = CrawlerStatistics()
        self.failure_statistics = CrawlerStatistics()
        self.crawling_date: datetime.datetime = tznow(
            pytz.timezone("Asia/Seoul")
        )
        self.crawling_start_time: str = str(timestamp(self.crawling_date))

    def run(self, run_by: str) -> None:
        self.slack_client.send_info_slack(
            f"TIME_STAMP: {self.crawling_start_time}\n"
            f"크롤링 시작합니다 "
            f"({self.config['ENVIRONMENT']}, {run_by})"
        )
        self.crawl()
        self.update_crawler_log(run_by)

        statistics = slack_failure_percentage_statistics(
            self.total_statistics, self.failure_statistics
        )
        
        self.slack_client.send_info_slack(
            f"크롤링 완료\n"
            f"TIME_STAMP: {self.crawling_start_time}\n\n"
            f"statistics:\n"
            f"region_count\n{statistics['region_count']}\n\n"
            f"statistics_count\n{statistics['statistics_count']}\n\n"
            f"bids_count\n{statistics['bids_count']}"
        )

    def crawl(self) -> None:
        login_id = self.config["LOGIN_ID"]
        login_pw = self.config["LOGIN_PW"]

        chk_id = self.info_care_client.fetch_chk_id().chk_id
        self.info_care_client.login(login_id, login_pw, chk_id)

        # 도, 시군구, 읍면동 리스트를 받아와 검색
        try:
            self.crawl_sido_region()
        except Exception as e:
            raise e
        finally:
            self.info_care_client.logout()

    def crawl_sido_region(self) -> None:
        try:
            do_list = self.info_care_client.fetch_sido_list()
        except Exception as e:
            self.failure_statistics.region_count += 1
            raise e

        for do in do_list:
            if re.search(self.config["SIDO"], do.sido_name):
                self.crawl_sigungu_region(do.sido_name)

    def crawl_sigungu_region(self, sido: str) -> None:
        try:
            si_list = self.info_care_client.fetch_sigungu_list(sido)
        except Exception as e:
            self.failure_statistics.region_count += 1
            raise e

        for si in si_list:
            if re.search(self.config["SIGUNGU"], si.sigungu_name):
                self.crawl_dongli_region(sido, si.sigungu_name)

    def crawl_dongli_region(self, sido: str, sigungu: str) -> None:
        try:
            dongli_list = self.info_care_client.fetch_dongli_list(
                sido, sigungu
            )
        except Exception as e:
            self.failure_statistics.region_count += 1
            raise e

        for dong in dongli_list:
            if re.search(self.config["DONGLI"], dong.dongli_name):
                self.crawl_main_using_type(sido, sigungu, dong.dongli_name)

    def crawl_main_using_type(
        self, sido: str, sigungu: str, dongli: str
    ) -> None:
        try:
            main_using_list = self.info_care_client.fetch_main_using_type()
        except Exception as e:
            self.failure_statistics.region_count += 1
            raise e

        for main_using in main_using_list:
            main_using_type = main_using.main_using_type

            if re.search(self.config["MAIN_USING_TYPE"], main_using_type):
                self.crawl_sub_using_type(
                    sido, sigungu, dongli, main_using_type
                )

    def crawl_sub_using_type(
        self, sido: str, sigungu: str, dongli: str, main_using_type: str
    ) -> None:
        try:
            sub_using_list = self.info_care_client.fetch_sub_using_type(
                main_using_type
            )
        except Exception as e:
            self.failure_statistics.region_count += 1
            raise e

        for sub_using in sub_using_list:
            sub_using_type = sub_using.sub_using_type

            if re.search(self.config["SUB_USING_TYPE"], sub_using_type):

                logger.info(
                    "Crawling Statistics",
                    sido=sido,
                    sigungu=sigungu,
                    dong=dongli,
                    main_using_type=main_using_type,
                    sub_using_type=sub_using_type,
                )
                data = self.info_care_client.fetch_statistics_page(
                    sido, sigungu, dongli, main_using_type, sub_using_type
                )
                self.crawl_html_data(
                    data,
                    sido,
                    sigungu,
                    dongli,
                    main_using_type,
                    sub_using_type,
                )

        self.total_statistics.region_count += 1

    def crawl_html_data(
        self,
        search_data: InfocareSearchResponse,
        sido: str,
        sigungu: str,
        dongli: str,
        main_using_type: str,
        sub_using_type: str,
    ) -> None:

        start_date = search_data.term1
        end_date = search_data.term2
        try:
            self.download_html_data(
                search_data.raw_data,
                sido,
                sigungu,
                dongli,
                main_using_type,
                sub_using_type,
                "statistics",
            )
        except Exception as e:
            self.failure_statistics.statistics_count += 1
            raise e

        self.total_statistics.statistics_count += 1

        # 낙찰사례가 1개 이상인경우 more 버튼의 페이지 다운로드
        if search_data.bids_count > 0:
            try:
                big_page = self.info_care_client.fetch_bid_page(
                    sido,
                    sigungu,
                    dongli,
                    main_using_type,
                    sub_using_type,
                    start_date,
                    end_date,
                    search_data.category,
                )
                self.download_html_data(
                    big_page.raw_data,
                    sido,
                    sigungu,
                    dongli,
                    main_using_type,
                    sub_using_type,
                    "bid",
                )
            except Exception as e:
                self.failure_statistics.bids_count += 1
                raise e

            self.total_statistics.bids_count += 1

    def download_html_data(
        self,
        data: str,
        sido: str,
        sigungu: str,
        dongli: str,
        main_using_type: str,
        sub_using_type: str,
        data_type: str,
    ) -> None:

        file_name = (
            f"{sido}_"
            f"{sigungu}_"
            f"{dongli}_"
            f"{main_using_type}_"
            f"{sub_using_type}_"
            f"{data_type}"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = str(temp_dir) + "\\"
            file_name = f"{file_name}.html"
            file_path = temp_path + file_name
            write_file(file_path, data)

            self.store_detail(
                sido,
                sigungu,
                dongli,
                main_using_type,
                sub_using_type,
                file_path,
                file_name,
                data_type,
            )

    def store_detail(
        self,
        sido: str,
        sigungu: str,
        dongli: str,
        main_using_type: str,
        sub_using_type: str,
        file_path: str,
        file_name: str,
        data_type: str,
    ) -> None:

        folder_name = (
            f"{self.config['ENVIRONMENT']}/"
            f"{self.crawling_date.year}/"
            f"{self.crawling_date.month:02}/"
            f"{self.crawling_date.day:02}/"
            f"{str(self.crawling_start_time)}/"
            f"data/"
            f"{sido}/"
            f"{sigungu}/"
            f"{dongli}/"
            f"{main_using_type}/"
            f"{sub_using_type}"
        )

        if data_type == "bid":
            folder_name += f"/{data_type}"

        self.s3_client.upload_any_file(
            folder_name=folder_name,
            file_name=file_name,
            file_path=file_path,
            mime_type="text/html",
            mode="rb",
        )

    def update_crawler_log(self, run_by: str) -> None:
        total_statistics = attr.asdict(self.total_statistics)

        data = {
            "time_stamp": self.crawling_start_time,
            "run_by": run_by,
            "finish_time_stamp": str(timestamp(tznow())),
            "total_statistics": total_statistics,
        }

        folder_name = (
            f"{self.config['ENVIRONMENT']}/"
            f"{self.crawling_date.year}/"
            f"{self.crawling_date.month:02}/"
            f"{self.crawling_date.day:02}/"
            f"{str(self.crawling_start_time)}/"
            f"crawler-log"
        )

        file_name = f"{self.crawling_start_time}.json"

        self.s3_client.upload_json(
            folder_name=folder_name, file_name=file_name, data=data
        )
