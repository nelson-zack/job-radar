"""
Contains core data models used across the Job Radar project.
"""

from pydantic import BaseModel
from typing import Optional, List

class Job(BaseModel):
    """
    Represents a job listing with key details.

    Attributes:
        title (str): The job title.
        company (str): The company offering the job.
        location (Optional[str]): The job location, if available.
        url (str): The URL to the job listing.
        source (str): The source site where the job was found.
        description (Optional[str]): The job description text, if available.
        tags (Optional[List[str]]): Tags for filtering/classification.
    """
    title: str
    company: str
    url: str
    location: Optional[str] = None
    source: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = []