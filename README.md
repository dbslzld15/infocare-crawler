## Infocare 사이트 Crawler 및 DB 적재 자동화

### 프로젝트 소개
|구분|내용|
|------|---|
|한줄 소개|인포케어 사이트 에서 지역별 통계 및 낙찰사례를 스크래핑하여 S3에 저장 후 저장된 데이터를 DB에 자동으로 적재합니다.|
|진행 기간|2020.09 ~ 2020.12|
|주요 기술| Python, AWS S3, AWS CloudWatch, AWS ECR, Docker, PostgreSQL|
|팀원 구성|개인 프로젝트|
|전담 역할|Crawler 구현 및 DB 적재 자동화|
|수상|없음|

### 프로젝트 개요
- 기존에 작성된 크롤러의 레거시 코드를 없애고 템플릿 구조에 맞게 리팩토링하였습니다.
- 해당 프로젝트의 경우 데이터를 수집하여 S3에 업로드하는 Crawler와 S3에 저장된 데이터를 DB에 저장하는 Store로 구성되어 있습니다.
- Crawler의 경우 한달 간격으로  [인포케어 사이트](http://www.infocare.co.kr) 에서 지역별 낙찰 통계 및 낙찰 사례 페이지를 스크래핑하여 S3에 저장합니다.
- Store는 S3에 업로드 된 html 데이터를 가져와 파싱을 진행 후 DB에 upsert 합니다.
- 배포를 위해 docker-compose 파일을 구성하였으며 develop 브랜치에 병합시에 ECR에 자동으로 배포되도록 git action 파일을 추가하였습니다.
- Pytest를 이용하여 페이지 요청 및 응답에 대한 테스트 코드를 작성하였습니다.

### 프로젝트 사용 기술 및 라이브러리


### ✔ Languauge

- Python

### ✔ Data Base

- PostgreSQL

### ✔ Dependency Management

- Poetry

### ✔ 협업

- Github

### ✔ Infra

- Docker
- AWS S3
- AWS CloudWatch
- AWS ECR
- Git Action

### ✔ Library

- BeautifulSoup
- SqlAlchemy
- Boto3
- Pytest 등


### [🛠 자세한 설명]

[노션 문서](https://www.notion.so/Infocare-Crawler-DB-40f63162d4d44034a4de0e61d14e29d5)
