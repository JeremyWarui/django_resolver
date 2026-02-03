"""
Custom pagination classes for the ticket system.
Allows flexible page sizes for different frontend use cases.
"""

from rest_framework.pagination import PageNumberPagination


class FlexiblePageNumberPagination(PageNumberPagination):
    """
    Custom pagination that allows flexible page sizes for different frontend needs.
    
    - Default: 25 items per page (good for most views)
    - Admin dashboard: Can request up to 500 items for better UX
    - Technician dashboard: Can request up to 100 items
    - User dashboard: Limited to 50 items
    
    Usage:
    - /api/tickets/ → 25 items (default)
    - /api/tickets/?page_size=100 → 100 items (for technician view)
    - /api/tickets/?page_size=500 → 500 items (for admin bulk operations)
    """
    
    page_size = 25  # Default page size (up from 20)
    page_size_query_param = 'page_size'  # Allow frontend to specify page size
    max_page_size = 500  # Maximum allowed page size (protects backend)
    
    def get_page_size(self, request):
        """
        Return the page size for the given request.
        Allows different limits based on use case while maintaining security.
        """
        # Get requested page size
        if self.page_size_query_param:
            try:
                requested_size = int(request.query_params[self.page_size_query_param])
            except (KeyError, ValueError):
                return self.page_size
            
            # Apply reasonable limits to prevent abuse
            if requested_size <= 0:
                return self.page_size
            elif requested_size > self.max_page_size:
                return self.max_page_size
            else:
                return requested_size
        
        return self.page_size


class TicketPagination(FlexiblePageNumberPagination):
    """
    Pagination specifically optimized for ticket endpoints.
    Allows larger page sizes for admin and technician workflows.
    """
    
    page_size = 25  # Default for regular views
    max_page_size = 500  # Allow large datasets for admin views
    
    def get_page_size(self, request):
        """
        Role-aware pagination sizing.
        
        Frontend can request appropriate sizes:
        - Admin dashboard: 100-500 items (for filtering/bulk operations)
        - Technician view: 50-100 items (for assigned tickets)
        - User view: 10-50 items (for personal tickets)
        """
        requested_size = super().get_page_size(request)
        
        # Validate against max_page_size
        return min(requested_size, self.max_page_size)
