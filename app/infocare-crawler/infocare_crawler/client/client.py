import functools
import json
import typing
import random
import time
import bs4
import requests
from requests_toolbelt.sessions import BaseUrlSession
from tanker.utils.requests import apply_proxy
from tanker.utils.retryer import Retryer
from tanker.utils.retryer.strategy import ExponentialModulusBackoffStrategy
from crawler.utils.encrpytion import encrypt
from infocare_crawler.client.exc import (
    InfocareClientResponseError, InfocareClientParseError,
)
from .data import InfocareChkID, InfocareSiDo, \
    InfocareSiGunGu, InfocareDongLi, InfocareBidsResponse, \
    InfocareMainUsingType, InfocareSearchResponse, InfocareSubUsingType

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    " AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/84.0.4147.135 Safari/537.36"
)


class InfocareClient(object):
    def __init__(self, config: typing.Dict[str, typing.Any]) -> None:
        super().__init__()

        proxy = config.get("PROXY_HOST") or None
        self.config = config
        # Header Settings
        self.session = BaseUrlSession("http://www.infocare.co.kr/")
        self.session.headers.update({"User-Agent": USER_AGENT})

        if proxy:
            apply_proxy(self.session, proxy)

        self.retryer = Retryer(
            strategy_factory=(
                ExponentialModulusBackoffStrategy.create_factory(2, 10)
            ),
            should_retry=lambda e: isinstance(
                e, (requests.exceptions.ConnectionError,)
            ),
            default_max_trials=3,
        )

    def _handle_json_response(
            self, r: requests.Response
    ) -> typing.Dict[str, typing.Any]:
        r.raise_for_status()

        try:
            data = r.json()
            return data
        except (json.JSONDecodeError, ValueError):
            raise InfocareClientResponseError(
                r.status_code, r.text)

    def _handle_text_response(self, r: requests.Response) -> str:
        r.raise_for_status()
        time.sleep(float(self.config['CLIENT_DELAY']))
        try:
            r.json()
        except (json.JSONDecodeError, ValueError):
            r.encoding = "cp949"
            return r.text
        else:
            raise InfocareClientResponseError(
                r.status_code, r.text)

    def fetch_chk_id(self) -> InfocareChkID:
        params = {
            'PC_Use': '',
        }

        response = self._handle_text_response(
            self.retryer.run(
                functools.partial(self.session.get,
                                  '/index.asp', params=params)
            )
        )

        return InfocareChkID.from_html(response)

    def login(
            self, login_id: str, login_pw: str, chk_id: str
    ) -> None:
        id = login_id + chk_id
        pw = login_pw + chk_id

        data = {
            'sid': chk_id,
            'userid': encrypt(id),
            'password': encrypt(pw),
            'submitimg.x': random.randint(15, 20),
            'submitimg.y': random.randint(15, 20),
        }

        self.session.cookies.update({
            'chkCookie': chk_id
        })

        self._handle_text_response(
            self.retryer.run(
                functools.partial(self.session.post,
                                  '/login/loginok.asps', data=data)
            )
        )

    def logout(self) -> None:

        self._handle_text_response(
            self.retryer.run(
                functools.partial(
                    self.session.get,
                    "/login/logoutok.asp"
                )
            )
        )

    def fetch_sido_list(self) -> typing.List[InfocareSiDo]:  # 시/도를 가져옴

        params = {
            'url_from': 'bubwon',
        }

        response = self._handle_text_response(
            self.retryer.run(
                functools.partial(
                    self.session.get,
                    "/bubwon/kyung_statistics/statistics_detail.asp",
                    params=params
                )
            )
        )

        soup = bs4.BeautifulSoup(response, 'lxml')

        do_list = soup.find(
            'select', attrs={'name': 'addr_do'}).find_all('option')

        if do_list[0]['value'] == '':
            do_list = do_list[1:]

        if not do_list:
            raise InfocareClientParseError("cannot find a sido list")

        return [InfocareSiDo.from_html(x) for x in do_list]

    def fetch_sigungu_list(
            self, sido: str) -> typing.List[InfocareSiGunGu]:  # 시/군/구를 가져옴
        params = {
            'url_from': 'bubwon',
            'addr_do': sido.encode('euc-kr'),
            'yong_set': '',
            'yong_desc': '',
        }

        response = self._handle_text_response(
            self.retryer.run(
                functools.partial(
                    self.session.get,
                    "/bubwon/kyung_statistics/statistics_detail.asp",
                    params=params
                )
            )
        )

        soup = bs4.BeautifulSoup(response, 'lxml')

        sigungu_list = soup.find(
            'select', attrs={'name': 'addr_si'}).find_all('option')

        if sigungu_list[0]['value'] == '':
            sigungu_list = sigungu_list[1:]

        if not sigungu_list:
            raise InfocareClientParseError("cannot find a sigungu list")

        return [InfocareSiGunGu.from_html(x) for x in sigungu_list]

    def fetch_dongli_list(
            self, sido: str, sigungu: str
    ) -> typing.List[InfocareDongLi]:  # 해당 시/군/구에 해당하는 읍/면/동을 가져옴

        params = {
            'url_from': 'bubwon',
            'addr_do': sido.encode('euc-kr'),
            'addr_si': sigungu.encode('euc-kr'),
            'yong_set': '',
            'yong_desc': '',
        }

        response = self._handle_text_response(
            self.retryer.run(
                functools.partial(
                    self.session.get,
                    "/bubwon/kyung_statistics/statistics_detail.asp",
                    params=params
                )
            )
        )

        soup = bs4.BeautifulSoup(response, 'lxml')

        dongli_list = soup.find(
            'select', attrs={'name': 'addr_dong'}).find_all('option')

        if dongli_list[0]['value'] == '':
            dongli_list = dongli_list[1:]

        if not dongli_list:
            raise InfocareClientParseError("cannot find a dongli list")

        return [InfocareDongLi.from_html(x) for x in dongli_list]

    def fetch_main_using_type(
            self) -> typing.List[InfocareMainUsingType]:  # 용도 대분류를 가져옴

        params = {
            'url_from': 'bubwon',
        }

        response = self._handle_text_response(
            self.retryer.run(
                functools.partial(
                    self.session.get,
                    "/bubwon/kyung_statistics/statistics_detail.asp",
                    params=params
                )
            )
        )

        soup = bs4.BeautifulSoup(response, 'lxml')

        main_using_type_list = soup.find(
            'select', attrs={'name': 'yong_set'}).find_all('option')

        if main_using_type_list[0]['value'] == '':
            main_using_type_list = main_using_type_list[1:]

        if not main_using_type_list:
            raise InfocareClientParseError(
                "cannot find a main using type list")

        return [InfocareMainUsingType.from_html(x) for x in
                main_using_type_list]

    def fetch_sub_using_type(
            self, main_using_type: str) -> typing.List[InfocareSubUsingType]:
        params = {
            'url_from': 'bubwon',
            'addr_do': '',
            'addr_si': '',
            'addr_dong': '',
            'sbunji': '',
            'ebunji': '',
            'yong_set': main_using_type.encode('euc-kr'),
            'yong_desc': '',
        }

        response = self._handle_text_response(
            self.retryer.run(
                functools.partial(
                    self.session.get,
                    "/bubwon/kyung_statistics/statistics_detail.asp",
                    params=params
                )
            )
        )

        soup = bs4.BeautifulSoup(response, 'lxml')

        sub_using_type_list = soup.find(
            'select', attrs={'name': 'yong_desc'}).find_all('option')

        if sub_using_type_list[0]['value'] == '':
            sub_using_type_list = sub_using_type_list[1:]

        if not sub_using_type_list:
            raise InfocareClientParseError("cannot find a sub using type list")

        return [InfocareSubUsingType.from_html(x) for x in sub_using_type_list]

    def fetch_statistics_page(
            self, sido: str, sigungu: str, dong: str,
            main_using_type: str, sub_using_type: str
    ) -> InfocareSearchResponse:
        params = {
            'SearchYN': 'Y',
            'url_from': 'bubwon',
            'addr_do': sido.encode('euc-kr'),
            'addr_si': sigungu.encode('euc-kr'),
            'addr_dong': dong.encode('euc-kr'),
            'sbunji': '',
            'ebunji': '',
            'yong_set': main_using_type.encode('euc-kr'),
            'yong_desc': sub_using_type.encode('euc-kr'),
        }

        response = self._handle_text_response(
            self.retryer.run(
                functools.partial(
                    self.session.get,
                    "/bubwon/kyung_statistics/statistics_detail.asp",
                    params=params
                )
            )
        )

        return InfocareSearchResponse.from_html(response)

    def fetch_bid_page(
            self, sido: str, sigungu: str, dong: str, main_using_type: str,
            sub_using_type: str, term1: str, term2: str, category: str
    ) -> "InfocareBidsResponse":

        params = {
            'url_from': 'bubwon',
            'mode': 'pop',
            'addr_do': sido.encode('euc-kr'),
            'addr_si': sigungu.encode('euc-kr'),
            'addr_dong': dong.encode('euc-kr'),
            'sbunji': '',
            'ebunji': '',
            'yong_set': main_using_type.encode('euc-kr'),
            'yong_desc': sub_using_type.encode('euc-kr'),
            'order': 'kmday_last desc',
            'term1': term1,
            'term2': term2,
            'Category': category,
            'scale': 'dong',
        }

        response = self._handle_text_response(
            self.retryer.run(
                functools.partial(
                    self.session.get,
                    "/bubwon/kyung_statistics/stat_example.asp",
                    params=params
                )
            )
        )

        return InfocareBidsResponse.from_html(response)
