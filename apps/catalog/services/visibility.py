from apps.catalog.models import ServiceCategory


def get_visible_categories(campus_id):
    """R5: Return ServiceCategories served at campus_id.

    A category is visible iff an active Section of its section_type
    exists within a CampusDepartment at the given campus.
    Traversal: ServiceCategory → SectionType → Section (is_active=True)
               → CampusDepartment → campus_id.
    """
    return (
        ServiceCategory.objects.filter(
            is_active=True,
            section_type__sections__is_active=True,
            section_type__sections__campus_department__campus_id=campus_id,
        )
        .select_related("section_type__department", "default_priority")
        .prefetch_related("service_items")
        .distinct()
        .order_by("section_type", "name")
    )
