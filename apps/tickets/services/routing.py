from apps.org.models import Section


class ServiceNotAvailableError(Exception):
    pass


def resolve_routing(requester_campus_id, service_item_id):
    """Return the matching Section for the given campus and service item.

    Traversal: Section → campus_department__campus, section_type → service_categories → service_items.
    Raises ServiceNotAvailableError if no active section handles the service at the campus.
    """
    section = (
        Section.objects.filter(
            campus_department__campus_id=requester_campus_id,
            section_type__service_categories__service_items__id=service_item_id,
            is_active=True,
        )
        .select_related(
            "campus_department__head_of_department",
            "campus_department__campus",
            "hos",
            "section_type",
        )
        .first()
    )
    if section is None:
        raise ServiceNotAvailableError(
            "No active section handles this service at the requester's campus."
        )
    return section
