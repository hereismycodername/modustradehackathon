"""Static file URLs that follow the URL prefix of the current request."""
from django.contrib.staticfiles.storage import StaticFilesStorage
from django.urls import get_script_prefix
from django.utils.encoding import filepath_to_uri


class ScriptPrefixStaticFilesStorage(StaticFilesStorage):
    """The stock storage remembers the prefix of the first request it saw.

    The demo site is reached as /django/ locally and under an extra path on
    Streamlit Cloud, so every URL is built from the request being served.
    """

    def url(self, name):
        return get_script_prefix() + "static/" + filepath_to_uri(name).lstrip("/")
