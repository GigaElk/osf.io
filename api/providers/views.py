from django.db.models import Case, CharField, Q, Value, When
from guardian.shortcuts import get_objects_for_user
from rest_framework.exceptions import ValidationError
from rest_framework import generics
from rest_framework import permissions as drf_permissions
from rest_framework.exceptions import NotAuthenticated, NotFound

from api.base import permissions as base_permissions
from api.base.exceptions import InvalidFilterValue, InvalidFilterOperator, Conflict
from api.base.filters import PreprintFilterMixin, ListFilterMixin
from api.base.views import JSONAPIBaseView
from api.base.pagination import MaxSizePagination, IncreasedPageSizePagination
from api.base.utils import get_object_or_error, get_user_auth, is_truthy
from api.licenses.views import LicenseList
from api.collections.permissions import CanSubmitToCollectionOrPublic
from api.collections.serializers import CollectedMetaSerializer, CollectedMetaCreateSerializer
from api.preprints.permissions import PreprintPublishedOrAdmin
from api.preprints.serializers import PreprintSerializer
from api.providers.permissions import CanAddModerator, CanDeleteModerator, CanUpdateModerator, CanSetUpProvider, GROUP_FORMAT, GroupHelper, MustBeModerator, PERMISSIONS
from api.providers.serializers import CollectionProviderSerializer, PreprintProviderSerializer, ModeratorSerializer
from api.taxonomies.serializers import TaxonomySerializer
from api.taxonomies.utils import optimize_subject_query
from framework.auth.oauth_scopes import CoreScopes
from osf.models import AbstractNode, CollectionProvider, CollectedGuidMetadata, NodeLicense, OSFUser, Subject, PreprintProvider, WhitelistedSHAREPreprintProvider


class GenericProviderList(JSONAPIBaseView, generics.ListAPIView, ListFilterMixin):
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.TokenHasScope,
    )

    required_read_scopes = [CoreScopes.ALWAYS_PUBLIC]
    required_write_scopes = [CoreScopes.NULL]

    pagination_class = MaxSizePagination
    ordering = ('name', )

    def get_default_queryset(self):
        return self.model_class.objects.all()

    # overrides ListAPIView
    def get_queryset(self):
        return self.get_queryset_from_request()


class CollectionProviderList(GenericProviderList):
    model_class = CollectionProvider
    serializer_class = CollectionProviderSerializer
    view_category = 'collection-providers'
    view_name = 'collection-providers-list'


class PreprintProviderList(GenericProviderList):
    """The documentation for this endpoint can be found [here](https://developer.osf.io/#operation/preprint_provider_list).
    """

    model_class = PreprintProvider
    serializer_class = PreprintProviderSerializer
    view_category = 'preprint-providers'
    view_name = 'preprint-providers-list'

    def get_renderer_context(self):
        context = super(PreprintProviderList, self).get_renderer_context()
        context['meta'] = {
            'whitelisted_providers': WhitelistedSHAREPreprintProvider.objects.all().values_list('provider_name', flat=True)
        }
        return context

    def build_query_from_field(self, field_name, operation):
        if field_name == 'permissions':
            if operation['op'] != 'eq':
                raise InvalidFilterOperator(value=operation['op'], valid_operators=['eq'])
            auth = get_user_auth(self.request)
            auth_user = getattr(auth, 'user', None)
            if not auth_user:
                raise NotAuthenticated()
            value = operation['value'].lstrip('[').rstrip(']')
            permissions = [v.strip() for v in value.split(',')]
            if any(p not in PERMISSIONS for p in permissions):
                valid_permissions = ', '.join(PERMISSIONS.keys())
                raise InvalidFilterValue('Invalid permission! Valid values are: {}'.format(valid_permissions))
            return Q(id__in=get_objects_for_user(auth_user, permissions, PreprintProvider, any_perm=True))

        return super(PreprintProviderList, self).build_query_from_field(field_name, operation)


class GenericProviderDetail(JSONAPIBaseView, generics.RetrieveAPIView):
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.TokenHasScope,
    )

    required_read_scopes = [CoreScopes.ALWAYS_PUBLIC]
    required_write_scopes = [CoreScopes.PROVIDERS_WRITE]

    def get_object(self):
        provider = get_object_or_error(self.model_class, self.kwargs['provider_id'], self.request, display_name=self.model_class.__name__)
        self.check_object_permissions(self.request, provider)
        return provider

class CollectionProviderDetail(GenericProviderDetail):
    model_class = CollectionProvider
    serializer_class = CollectionProviderSerializer
    view_category = 'collection-providers'
    view_name = 'collection-provider-detail'


class PreprintProviderDetail(GenericProviderDetail, generics.UpdateAPIView):
    """The documentation for this endpoint can be found [here](https://developer.osf.io/#operation/preprint_provider_detail).
    """
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.TokenHasScope,
        CanSetUpProvider,
    )
    model_class = PreprintProvider
    serializer_class = PreprintProviderSerializer
    view_category = 'preprint-providers'
    view_name = 'preprint-provider-detail'

    def perform_update(self, serializer):
        if serializer.instance.is_reviewed:
            raise Conflict('Reviews settings may be set only once. Contact support@osf.io if you need to update them.')
        super(PreprintProviderDetail, self).perform_update(serializer)


class GenericProviderTaxonomies(JSONAPIBaseView, generics.ListAPIView):
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.TokenHasScope,
    )

    required_read_scopes = [CoreScopes.ALWAYS_PUBLIC]
    required_write_scopes = [CoreScopes.NULL]

    serializer_class = TaxonomySerializer
    pagination_class = IncreasedPageSizePagination
    view_name = 'taxonomy-list'

    ordering = ('-id',)

    def is_valid_subject(self, allows_children, allowed_parents, sub):
        # TODO: Delet this when all PreprintProviders have a mapping
        if sub._id in allowed_parents:
            return True
        if sub.parent:
            if sub.parent._id in allows_children:
                return True
            if sub.parent.parent:
                if sub.parent.parent._id in allows_children:
                    return True
        return False

    def get_queryset(self):
        parent = self.request.query_params.get('filter[parents]', None) or self.request.query_params.get('filter[parent]', None)
        provider = get_object_or_error(self._model_class, self.kwargs['provider_id'], self.request, display_name=self._model_class.__name__)
        if parent:
            if parent == 'null':
                return provider.top_level_subjects
            if provider.subjects.exists():
                return optimize_subject_query(provider.subjects.filter(parent___id=parent))
            else:
                # TODO: Delet this when all PreprintProviders have a mapping
                #  Calculate this here to only have to do it once.
                allowed_parents = [id_ for sublist in provider.subjects_acceptable for id_ in sublist[0]]
                allows_children = [subs[0][-1] for subs in provider.subjects_acceptable if subs[1]]
                return [sub for sub in optimize_subject_query(Subject.objects.filter(parent___id=parent)) if provider.subjects_acceptable == [] or self.is_valid_subject(allows_children=allows_children, allowed_parents=allowed_parents, sub=sub)]
        return optimize_subject_query(provider.all_subjects)


class CollectionProviderTaxonomies(GenericProviderTaxonomies):
    view_category = 'collection-providers'
    _model_class = CollectionProvider  # Not actually the model being serialized, privatize to avoid issues


class PreprintProviderTaxonomies(GenericProviderTaxonomies):
    """The documentation for this endpoint can be found [here](https://developer.osf.io/#operation/preprint_provider_taxonomies_list).
    """
    view_category = 'preprint-providers'
    _model_class = PreprintProvider  # Not actually the model being serialized, privatize to avoid issues


class GenericProviderHighlightedSubjectList(JSONAPIBaseView, generics.ListAPIView):
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.TokenHasScope,
    )

    view_name = 'highlighted-taxonomy-list'

    required_read_scopes = [CoreScopes.ALWAYS_PUBLIC]
    required_write_scopes = [CoreScopes.NULL]

    serializer_class = TaxonomySerializer

    def get_queryset(self):
        provider = get_object_or_error(self._model_class, self.kwargs['provider_id'], self.request, display_name=self._model_class.__name__)
        return optimize_subject_query(Subject.objects.filter(id__in=[s.id for s in provider.highlighted_subjects]).order_by('text'))


class CollectionProviderHighlightedSubjectList(GenericProviderHighlightedSubjectList):
    view_category = 'collection-providers'
    _model_class = CollectionProvider


class PreprintProviderHighlightedSubjectList(GenericProviderHighlightedSubjectList):
    view_category = 'preprint-providers'
    _model_class = PreprintProvider


class GenericProviderLicenseList(LicenseList):
    """The documentation for this endpoint can be found [here](https://developer.osf.io/#operation/preprint_provider_licenses_list)
    """
    ordering = ()  # TODO: should be ordered once the frontend for selecting default licenses no longer relies on order

    def get_default_queryset(self):
        return NodeLicense.objects.preprint_licenses()

    def get_queryset(self):
        provider = get_object_or_error(self._model_class, self.kwargs['provider_id'], self.request, display_name=self._model_class.__name__)
        if not provider.licenses_acceptable.count():
            if not provider.default_license:
                return super(GenericProviderLicenseList, self).get_queryset()
            return [provider.default_license] + [license for license in super(GenericProviderLicenseList, self).get_queryset() if license != provider.default_license]
        if not provider.default_license:
            return provider.licenses_acceptable.get_queryset()
        return [provider.default_license] + [license for license in provider.licenses_acceptable.all() if license != provider.default_license]


class CollectionProviderLicenseList(GenericProviderLicenseList):
    view_category = 'collection-providers'
    _model_class = CollectionProvider


class PreprintProviderLicenseList(GenericProviderLicenseList):
    view_category = 'preprint-providers'
    _model_class = PreprintProvider


class PreprintProviderPreprintList(JSONAPIBaseView, generics.ListAPIView, PreprintFilterMixin):
    """The documentation for this endpoint can be found [here](https://developer.osf.io/#operation/preprint_providers_preprints_list).
    """
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        base_permissions.TokenHasScope,
        PreprintPublishedOrAdmin,
    )

    ordering = ('-created')

    serializer_class = PreprintSerializer
    model_class = AbstractNode

    required_read_scopes = [CoreScopes.NODE_PREPRINTS_READ]
    required_write_scopes = [CoreScopes.NULL]

    view_category = 'preprint-providers'
    view_name = 'preprints-list'

    def get_default_queryset(self):
        auth = get_user_auth(self.request)
        auth_user = getattr(auth, 'user', None)
        provider = get_object_or_error(PreprintProvider, self.kwargs['provider_id'], self.request, display_name='PreprintProvider')

        # Permissions on the list objects are handled by the query
        return self.preprints_queryset(provider.preprint_services.all(), auth_user)

    # overrides ListAPIView
    def get_queryset(self):
        return self.get_queryset_from_request()

    # overrides APIView
    def get_renderer_context(self):
        context = super(PreprintProviderPreprintList, self).get_renderer_context()
        show_counts = is_truthy(self.request.query_params.get('meta[reviews_state_counts]', False))
        if show_counts:
            # TODO don't duplicate the above
            auth = get_user_auth(self.request)
            auth_user = getattr(auth, 'user', None)
            provider = get_object_or_error(PreprintProvider, self.kwargs['provider_id'], self.request, display_name='PreprintProvider')
            if auth_user and auth_user.has_perm('view_submissions', provider):
                context['meta'] = {
                    'reviews_state_counts': provider.get_reviewable_state_counts(),
                }
        return context

class CollectionProviderSubmissionList(JSONAPIBaseView, generics.ListCreateAPIView, ListFilterMixin):
    permission_classes = (
        drf_permissions.IsAuthenticatedOrReadOnly,
        CanSubmitToCollectionOrPublic,
        base_permissions.TokenHasScope,
    )
    required_read_scopes = [CoreScopes.COLLECTED_META_READ]
    required_write_scopes = [CoreScopes.COLLECTED_META_WRITE]

    model_class = CollectedGuidMetadata
    serializer_class = CollectedMetaSerializer
    view_category = 'collected-metadata'
    view_name = 'provider-collected-metadata-list'

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return CollectedMetaCreateSerializer
        else:
            return CollectedMetaSerializer

    def get_default_queryset(self):
        provider = get_object_or_error(CollectionProvider, self.kwargs['provider_id'], self.request, display_name='CollectionProvider')
        if provider and provider.primary_collection:
            return provider.primary_collection.collectedguidmetadata_set.all()
        return CollectedGuidMetadata.objects.none()

    def get_queryset(self):
        return self.get_queryset_from_request()

    def perform_create(self, serializer):
        user = self.request.user
        provider = get_object_or_error(CollectionProvider, self.kwargs['provider_id'], self.request, display_name='CollectionProvider')
        if provider and provider.primary_collection:
            return serializer.save(creator=user, collection=provider.primary_collection)
        raise ValidationError('Provider {} has no primary collection to submit to.'.format(provider.name))


class ModeratorMixin(object):
    model_class = OSFUser

    def get_provider(self):
        return get_object_or_error(PreprintProvider, self.kwargs['provider_id'], self.request, display_name='PreprintProvider')

    def get_serializer_context(self, *args, **kwargs):
        ctx = super(ModeratorMixin, self).get_serializer_context(*args, **kwargs)
        ctx.update({'provider': self.get_provider()})
        return ctx


class PreprintProviderModeratorsList(ModeratorMixin, JSONAPIBaseView, generics.ListCreateAPIView, ListFilterMixin):
    permission_classes = (
        drf_permissions.IsAuthenticated,
        base_permissions.TokenHasScope,
        MustBeModerator,
        CanAddModerator,
    )
    view_category = 'moderators'
    view_name = 'provider-moderator-list'

    required_read_scopes = [CoreScopes.MODERATORS_READ]
    required_write_scopes = [CoreScopes.MODERATORS_WRITE]

    serializer_class = ModeratorSerializer

    def get_default_queryset(self):
        provider = self.get_provider()
        group_helper = GroupHelper(provider)
        admin_group = group_helper.get_group('admin')
        mod_group = group_helper.get_group('moderator')
        return (admin_group.user_set.all() | mod_group.user_set.all()).annotate(permission_group=Case(
            When(groups=admin_group, then=Value('admin')),
            default=Value('moderator'),
            output_field=CharField()
        )).order_by('fullname')

    def get_queryset(self):
        return self.get_queryset_from_request()

class PreprintProviderModeratorsDetail(ModeratorMixin, JSONAPIBaseView, generics.RetrieveUpdateDestroyAPIView):
    permission_classes = (
        drf_permissions.IsAuthenticated,
        base_permissions.TokenHasScope,
        MustBeModerator,
        CanUpdateModerator,
        CanDeleteModerator,
    )
    view_category = 'moderators'
    view_name = 'provider-moderator-detail'

    required_read_scopes = [CoreScopes.MODERATORS_READ]
    required_write_scopes = [CoreScopes.MODERATORS_WRITE]

    serializer_class = ModeratorSerializer

    def get_object(self):
        provider = self.get_provider()
        user = get_object_or_error(OSFUser, self.kwargs['moderator_id'], self.request, display_name='OSFUser')
        try:
            perm_group = user.groups.filter(name__contains=GROUP_FORMAT.format(provider_id=provider._id, group='')).order_by('name').first().name.split('_')[-1]
        except AttributeError:
            # Group doesn't exist -- users not moderator
            raise NotFound
        setattr(user, 'permission_group', perm_group)
        return user

    def perform_destroy(self, instance):
        try:
            self.get_provider().remove_from_group(instance, instance.permission_group)
        except ValueError as e:
            raise ValidationError(e.message)
