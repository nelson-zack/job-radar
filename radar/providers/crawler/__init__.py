# minimal package marker
from .frontier import CrawlFrontier
from .fetch import Fetcher
from .extract import is_job_page, extract_job
from .registry import get_extractor_for