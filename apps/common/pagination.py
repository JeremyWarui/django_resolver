from rest_framework.pagination import PageNumberPagination, CursorPagination
from rest_framework.response import Response


class ConfigListPagination(PageNumberPagination):
    """For admin config lists — /campuses/, /sections/, /priorities/, etc."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class TicketFeedPagination(PageNumberPagination):
    """For the ticket queue — activity-first, ordered -updated_at.
    PageNumber because the sort key moves constantly, ruling out cursor (D6/§3.7)."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = "-updated_at"


class AppendOnlyFeedPagination(CursorPagination):
    """For immutable append-only feeds: logs, comments, audit trail.
    Ordered -created_at tie-broken by id.
    Envelope: { results, meta: { nextCursor, prevCursor, total } }
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
    ordering = ("-created_at", "id")

    def get_paginated_response(self, data):
        return Response(
            {
                "results": data,
                "meta": {
                    "nextCursor": self.get_next_link(),
                    "prevCursor": self.get_previous_link(),
                    "total": None,  # cursor pagination does not provide a total count
                },
            }
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "results": schema,
                "meta": {
                    "type": "object",
                    "properties": {
                        "nextCursor": {"type": "string", "nullable": True},
                        "prevCursor": {"type": "string", "nullable": True},
                        "total": {"type": "integer", "nullable": True},
                    },
                },
            },
        }
