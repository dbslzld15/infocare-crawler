class InfocareStoreError(Exception):
    pass


class InfocareStoreS3NotFound(InfocareStoreError):
    pass


class InfocareStoreCrawlerLogNotFound(InfocareStoreError):
    pass


class InfocareStoreRegionNotFound(InfocareStoreError):
    pass
