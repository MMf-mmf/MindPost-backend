from django.contrib.auth.backends import ModelBackend


# AS OFF NOW THIS IS NOT USED SINCE THE DJANGO ADMIN DOES NOT INTEGRATE WITH THIS TO WELL
# ONCE WE GUILD OUT A CUSTOM USER INTERFACE WE WILL ITERATE ON THIS PERMISSION OR PERHAPS SIMPLY USE A VIEW BASED PERMISSION ?
class PropertyBasedPermissionBackend(ModelBackend):
    """
    Permission backend that checks if user is the asset manager for a property
    before allowing certain actions on related models.
    """

    def has_perm(self, user_obj, perm, obj=None):
        # First check if the user has standard permissions
        if super().has_perm(user_obj, perm, obj):
            return True

        # Skip if no object provided or user not authenticated
        if not obj or not user_obj.is_authenticated:
            return False

        # Check for property-based permissions
        if perm in [
            "property_app.change_property",
            "property_app.view_property",
            "compliance_app.change_licenses",
            "compliance_app.view_licenses",
            "compliance_app.change_insurance",
            "compliance_app.view_insurance",
        ]:

            # Get the property object from different models
            property_obj = None

            if hasattr(obj, "property"):
                property_obj = obj.property
            elif hasattr(obj, "insured_facility"):
                property_obj = obj.insured_facility
            elif hasattr(obj, "facility"):
                property_obj = obj.facility
            elif obj.__class__.__name__ == "Property":
                property_obj = obj

            # Check if user is the asset manager for this property
            if (
                property_obj
                and hasattr(property_obj, "asset_manager")
                and property_obj.asset_manager
            ):
                # Assuming the user model has an assetmanager attribute or relation
                if (
                    hasattr(user_obj, "assetmanager")
                    and user_obj.assetmanager == property_obj.asset_manager
                ):
                    return True

        return False
