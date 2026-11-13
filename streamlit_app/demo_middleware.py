"""CSRF protection for the Streamlit demo comes from the key in every address."""


class TokenAddressCsrf:
    """Skip Django's cookie and Origin checks behind streamlit_app.py.

    Streamlit Cloud drops cookies and its frames may send ``Origin: null``.
    Every site address carries a random per-tab key that another site cannot
    know, so a forged cross-site request cannot reach a signed-in session.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request._dont_enforce_csrf_checks = True
        return self.get_response(request)
