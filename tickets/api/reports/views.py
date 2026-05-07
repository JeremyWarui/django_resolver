"""
API views for generating and downloading reports.
"""

from datetime import datetime, timedelta
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from tickets.api.permissions import IsTechnicianOrAdmin

from .report_generator import (
    TicketLifecycleReport,
    TechnicianPerformanceReport,
    FacilityHealthReport,
    PendingAnalysisReport,
    ComprehensiveReport,
)


class GenerateReportView(generics.GenericAPIView):
    """
    Generate and download reports in Excel format.

    Query Parameters:
    - report_type: ticket-lifecycle, technician-performance, facility-health,
                   pending-analysis, comprehensive
    - start_date: Start date for filtering (YYYY-MM-DD)
    - end_date: End date for filtering (YYYY-MM-DD)
    - timeframe: day, week, month, quarter, year (alternative to explicit dates)
    - status: Ticket status filter (for ticket-lifecycle)
    - section_id: Section ID filter (for ticket-lifecycle)
    - technician_id: Technician ID filter
    """

    permission_classes = [
        IsTechnicianOrAdmin
    ]  # Only technicians and above can generate reports

    def get(self, request, format=None):
        """Generate and return Excel report as downloadable file."""
        report_type = request.query_params.get("report_type", "ticket-lifecycle")

        # Parse date filters
        start_date = request.query_params.get("start_date")
        end_date = request.query_params.get("end_date")
        # No default - show all tickets if not specified
        timeframe = request.query_params.get("timeframe")

        # If timeframe is provided instead of explicit dates
        if not start_date and not end_date and timeframe:
            end_date = timezone.now()
            if timeframe == "day":
                start_date = end_date - timedelta(days=1)
            elif timeframe == "week":
                start_date = end_date - timedelta(days=7)
            elif timeframe == "month":
                start_date = end_date - timedelta(days=30)
            elif timeframe == "quarter":
                start_date = end_date - timedelta(days=90)
            elif timeframe == "year":
                start_date = end_date - timedelta(days=365)
            # If timeframe is None or not recognized, don't set dates (show all tickets)
        else:
            # Parse explicit dates
            if start_date:
                start_date = datetime.strptime(start_date, "%Y-%m-%d")
                start_date = timezone.make_aware(start_date)
            if end_date:
                end_date = datetime.strptime(end_date, "%Y-%m-%d")
                end_date = timezone.make_aware(end_date)

        # Get additional filters
        status_filter = request.query_params.get("status")
        section_id = request.query_params.get("section_id")
        technician_id = request.query_params.get("technician_id")

        # Generate the appropriate report
        try:
            if report_type == "ticket-lifecycle":
                report_gen = TicketLifecycleReport()
                excel_buffer = report_gen.generate(
                    start_date=start_date,
                    end_date=end_date,
                    status=status_filter,
                    section_id=section_id,
                    technician_id=technician_id,
                )
                filename = (
                    f'Ticket_Lifecycle_Report_{datetime.now().strftime("%Y%m%d")}.xlsx'
                )

            elif report_type == "technician-performance":
                report_gen = TechnicianPerformanceReport()
                excel_buffer = report_gen.generate(
                    start_date=start_date,
                    end_date=end_date,
                    technician_id=technician_id,
                )
                filename = f'Technician_Performance_Report_{datetime.now().strftime("%Y%m%d")}.xlsx'

            elif report_type == "facility-health":
                report_gen = FacilityHealthReport()
                excel_buffer = report_gen.generate(
                    start_date=start_date, end_date=end_date
                )
                filename = (
                    f'Facility_Health_Report_{datetime.now().strftime("%Y%m%d")}.xlsx'
                )

            elif report_type == "pending-analysis":
                report_gen = PendingAnalysisReport()
                excel_buffer = report_gen.generate()
                filename = (
                    f'Pending_Analysis_Report_{datetime.now().strftime("%Y%m%d")}.xlsx'
                )

            elif report_type == "comprehensive":
                report_gen = ComprehensiveReport()
                excel_buffer = report_gen.generate(
                    start_date=start_date, end_date=end_date
                )
                filename = (
                    f'Comprehensive_Report_{datetime.now().strftime("%Y%m%d")}.xlsx'
                )

            else:
                return Response(
                    {"error": f"Invalid report type: {report_type}"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            # Create HTTP response with Excel file
            response = HttpResponse(
                excel_buffer.read(),
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = f'attachment; filename="{filename}"'

            return response

        except Exception as e:
            return Response(
                {"error": f"Error generating report: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ReportTypesView(generics.GenericAPIView):
    """Return available report types and their configurations."""

    permission_classes = [
        IsTechnicianOrAdmin
    ]  # Only technicians and above can view report types

    def get(self, request, format=None):
        """Get list of available report types."""
        report_types = [
            {
                "id": "ticket-lifecycle",
                "name": "Ticket Lifecycle Report",
                "description": "Comprehensive ticket audit trail with all lifecycle data",
                "filters": [
                    "start_date",
                    "end_date",
                    "status",
                    "section_id",
                    "technician_id",
                ],
                "columns": [
                    "Ticket No",
                    "Title",
                    "Section",
                    "Facility",
                    "Raised By",
                    "Assigned To",
                    "Status",
                    "Created At",
                    "Resolved At",
                    "Resolution Time",
                    "Pending Reason",
                ],
            },
            {
                "id": "technician-performance",
                "name": "Technician Performance Report",
                "description": "Performance metrics for all or specific technicians",
                "filters": ["start_date", "end_date", "technician_id"],
                "columns": [
                    "Technician",
                    "Email",
                    "Total Tickets",
                    "Resolved",
                    "Pending",
                    "In Progress",
                    "Avg Resolution Time",
                    "Avg Rating",
                ],
            },
            {
                "id": "facility-health",
                "name": "Facility Health Report",
                "description": "Health metrics and maintenance needs by facility",
                "filters": ["start_date", "end_date"],
                "columns": [
                    "Facility",
                    "Type",
                    "Location",
                    "Total Tickets",
                    "Open Tickets",
                    "Avg Response Time",
                    "Status",
                ],
            },
            {
                "id": "pending-analysis",
                "name": "Pending Tickets Analysis",
                "description": "All pending tickets with reasons and priorities",
                "filters": [],
                "columns": [
                    "Ticket No",
                    "Title",
                    "Section",
                    "Facility",
                    "Assigned To",
                    "Created At",
                    "Updated At",
                    "Pending Duration",
                    "Pending Reason",
                    "Priority",
                ],
            },
            {
                "id": "comprehensive",
                "name": "Comprehensive Report",
                "description": "All reports combined into one Excel workbook",
                "filters": ["start_date", "end_date"],
                "columns": ["Multiple sheets with all data"],
            },
        ]

        return Response(
            {
                "report_types": report_types,
                "timeframe_options": [
                    {"value": "day", "label": "Last 24 Hours"},
                    {"value": "week", "label": "Last 7 Days"},
                    {"value": "month", "label": "Last 30 Days"},
                    {"value": "quarter", "label": "Last 3 Months"},
                    {"value": "year", "label": "Last Year"},
                ],
            }
        )
