import typing
from abc import abstractmethod, ABCMeta
import attr
import bs4
import re

from infocare_crawler.client.exc import InfocareDataParseError


class InfocareData(metaclass=ABCMeta):
    @abstractmethod
    def to_html(self) -> str:
        pass


class InfocareIndexData(InfocareData):
    @abstractmethod
    def pk(self) -> str:
        pass


@attr.s(frozen=True)
class InfocareChkID(InfocareData):
    # data: 461908924
    # descripition: 로그인 쿠키 체크
    chk_id: str = attr.ib()
    # Raw 페이지 네이션
    raw_data: str = attr.ib()

    @classmethod
    def from_html(cls, data: str) -> "InfocareChkID":
        varlist = {}
        value: typing.Optional[str]
        var_values = data.split("var ")[1:]  # get each var entry

        for v in var_values:
            name = v.split("=")[0].strip()  # first part is the var [name = "]
            try:
                value = v.split("'")[1]
            except IndexError:
                value = None
            varlist[name] = value

        if varlist['chkID'] is None:
            raise InfocareDataParseError("chkID Not Found Error")
        else:
            chk_id = varlist['chkID']

        return cls(
            chk_id=chk_id,
            raw_data=data
        )

    def to_html(self) -> str:
        return self.raw_data


@attr.s(frozen=True)
class InfocareSiDo(InfocareData):
    # data: 강원, 경기, 경남 ,경북 ...
    # description: 시/도
    sido_name: str = attr.ib()
    # RAW DATA: 페이지 네이션
    raw_data: str = attr.ib()

    @classmethod
    def from_html(cls, data: bs4.element.Tag) -> "InfocareSiDo":
        sido_name = data['value']

        return cls(
            sido_name=sido_name,
            raw_data=data.text
        )

    def to_html(self) -> str:
        return self.raw_data


@attr.s
class InfocareSiGunGu(InfocareData):
    # data: 가평군, 고양시 일산서구, 군포시, 안양시
    # description: 시/군/구
    sigungu_name: str = attr.ib()
    # RAW DATA: 페이지 네이션
    raw_data: str = attr.ib()

    @classmethod
    def from_html(cls, data: bs4.element.Tag) -> "InfocareSiGunGu":
        sigungu_name = data['value']

        return cls(
            sigungu_name=sigungu_name,
            raw_data=data.text
        )

    def to_html(self) -> str:
        return self.raw_data


@attr.s
class InfocareDongLi(InfocareData):
    # data: 괴란동, 구미동, 반포동, 천곡동 ..
    # description: 읍/면/동
    dongli_name: str = attr.ib()
    # RAW DATA: 페이지 네이션
    raw_data: str = attr.ib()

    @classmethod
    def from_html(cls, data: bs4.element.Tag) -> "InfocareDongLi":
        dongli_name = data['value']

        return cls(
            dongli_name=dongli_name,
            raw_data=data.text,
        )

    def to_html(self) -> str:
        return self.raw_data


@attr.s(frozen=True)
class InfocareMainUsingType(InfocareData):
    # data: 주택, 집합건물, 상가, 공장, 특수부동산, 토지 ..
    # description: 용도- 대분류
    main_using_type: str = attr.ib()
    # RAW DATA: 페이지 네이션
    raw_data: str = attr.ib()

    @classmethod
    def from_html(cls, data: bs4.element.Tag) -> "InfocareMainUsingType":
        main_using_type = data['value']

        return cls(
            main_using_type=main_using_type,
            raw_data=data.text,
        )

    def to_html(self) -> str:
        return self.raw_data


@attr.s(frozen=True)
class InfocareSubUsingType(InfocareData):
    # data: 아파트
    # description: 용도- 소분류
    sub_using_type: str = attr.ib()
    # RAW DATA: 페이지 네이션
    raw_data: str = attr.ib()

    @classmethod
    def from_html(cls, data: bs4.element.Tag) -> "InfocareSubUsingType":
        sub_using_type = data['value']

        return cls(
            sub_using_type=sub_using_type,
            raw_data=data.text,
        )

    def to_html(self) -> str:
        return self.raw_data


@attr.s(frozen=True)
class InfocareSearchResponse(InfocareData):
    # data: 8
    # description: 1년간 낙찰 건수
    bids_count: int = attr.ib()
    # data: 201909
    # description: 기준 통계기간 시작 날짜
    term1: str = attr.ib()
    # data: 202008
    # description: 기준 통계기간 종료 날짜
    term2: str = attr.ib()
    # data: 2
    # description: ?
    category: str = attr.ib()
    # RAW DATA: 페이지 네이션
    raw_data: str = attr.ib()

    @classmethod
    def from_html(cls, data: str
                  ) -> "InfocareSearchResponse":
        soup = bs4.BeautifulSoup(data, 'lxml')

        table = soup.find(
            'table', attrs={'class': 'nakRateRep ml20'})

        tds = table.find_all('td', attrs={'class': 'desc'})

        bids_count: int = 0

        for td in tds:
            try:
                bids = re.findall('낙찰건수: (.+) 건', td.text)
                if bids:
                    bids_count = int(bids[0])
            except TypeError:
                pass

        more_href = soup.find(
            'a', attrs={'class': 'noprint'}, href=True
        )

        hrefs = more_href['href'].split(',')
        term1 = hrefs[-3].replace('\'', '')
        term2 = hrefs[-2].replace('\'', '')
        category = hrefs[-1].replace('\'', '').replace(')', '')
        raw_data = str(soup)
        raw_data = raw_data.replace(
            "top.location.href = \'/main.asp\';", '')
        return cls(
            bids_count=bids_count,
            raw_data=raw_data,
            term1=term1,
            term2=term2,
            category=category,
        )

    def to_html(self) -> str:
        return self.raw_data


@attr.s(frozen=True)
class InfocareBidsResponse(InfocareData):
    # RAW DATA: 페이지 네이션
    raw_data: str = attr.ib()

    @classmethod
    def from_html(cls, data: str
                  ) -> "InfocareBidsResponse":

        soup = bs4.BeautifulSoup(data, 'lxml')

        return cls(
            raw_data=str(soup)
        )

    def to_html(self) -> str:
        return self.raw_data
