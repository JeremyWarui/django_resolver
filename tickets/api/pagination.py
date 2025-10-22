"""
Custom pagination classes for the API.
"""
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination for most list views.
    Allows customizing page size via query parameter.
    """
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

    def get_paginated_response(self, data):
        """
        Return a paginated response with additional pagination metadata.
        """
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'total_pages': self.page.paginator.num_pages,
            'current_page': self.page.number,
            'results': data
        })


class LargeResultsSetPagination(PageNumberPagination):
    """
    Pagination for views that might need to display more items per page.
    """
    page_size = 50
    page_size_query_param = 'page_size'
    max_page_size = 500
