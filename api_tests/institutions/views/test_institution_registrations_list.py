from nose.tools import *  # flake8: noqa

from tests.base import ApiTestCase
from osf_tests.factories import (
    AuthUserFactory,
    InstitutionFactory,
    NodeFactory,
    ProjectFactory,
    RegistrationFactory,
    WithdrawnRegistrationFactory
)

from framework.auth import Auth
from api.base.settings.defaults import API_BASE
from api_tests.registrations.filters.test_filters import RegistrationListFilteringMixin

class TestInstitutionRegistrationList(ApiTestCase):
    def setUp(self):
        super(TestInstitutionRegistrationList, self).setUp()
        self.institution = InstitutionFactory()
        self.registration1 = RegistrationFactory(is_public=True, is_registration=True)
        self.registration1.affiliated_institutions.add(self.institution)
        self.registration1.save()
        self.user1 = AuthUserFactory()
        self.user2 = AuthUserFactory()
        self.registration2 = RegistrationFactory(creator=self.user1, is_public=False, is_registration=True)
        self.registration2.affiliated_institutions.add(self.institution)
        self.registration2.add_contributor(self.user2, auth=Auth(self.user1))
        self.registration2.save()
        self.registration3 = RegistrationFactory(creator=self.user2, is_public=False, is_registration=True)
        self.registration3.affiliated_institutions.add(self.institution)
        self.registration3.save()

        self.institution_node_url = '/{0}institutions/{1}/registrations/'.format(API_BASE, self.institution._id)

    def test_return_all_public_nodes(self):
        res = self.app.get(self.institution_node_url)

        assert_equal(res.status_code, 200)
        ids = [each['id'] for each in res.json['data']]

        assert_in(self.registration1._id, ids)
        assert_not_in(self.registration2._id, ids)
        assert_not_in(self.registration3._id, ids)

    def test_does_not_return_private_nodes_with_auth(self):
        res = self.app.get(self.institution_node_url, auth=self.user1.auth)

        assert_equal(res.status_code, 200)
        ids = [each['id'] for each in res.json['data']]

        assert_in(self.registration1._id, ids)
        assert_not_in(self.registration2._id, ids)
        assert_not_in(self.registration3._id, ids)

    def test_doesnt_return_retractions_without_auth(self):
        self.registration2.is_public = True
        self.registration2.save()
        retraction = WithdrawnRegistrationFactory(registration=self.registration2, user=self.user1)
        assert_true(self.registration2.is_retracted)

        res = self.app.get(self.institution_node_url)

        assert_equal(res.status_code, 200)
        ids = [each['id'] for each in res.json['data']]

        assert_not_in(self.registration2._id, ids)

    def test_doesnt_return_retractions_with_auth(self):
        retraction = WithdrawnRegistrationFactory(registration=self.registration2, user=self.user1)

        assert_true(self.registration2.is_retracted)

        res = self.app.get(self.institution_node_url, auth=self.user1.auth)

        assert_equal(res.status_code, 200)
        ids = [each['id'] for each in res.json['data']]

        assert_not_in(self.registration2._id, ids)


class TestRegistrationListFiltering(RegistrationListFilteringMixin, ApiTestCase):

    def _setUp(self):
        self.user = AuthUserFactory()
        self.institution = InstitutionFactory()

        self.A = ProjectFactory(creator=self.user)
        self.B1 = NodeFactory(parent=self.A, creator=self.user)
        self.B2 = NodeFactory(parent=self.A, creator=self.user)
        self.C1 = NodeFactory(parent=self.B1, creator=self.user)
        self.C2 = NodeFactory(parent=self.B2, creator=self.user)
        self.D2 = NodeFactory(parent=self.C2, creator=self.user)

        self.A.affiliated_institutions.add(self.institution)
        self.B1.affiliated_institutions.add(self.institution)
        self.B2.affiliated_institutions.add(self.institution)
        self.C1.affiliated_institutions.add(self.institution)
        self.C2.affiliated_institutions.add(self.institution)
        self.D2.affiliated_institutions.add(self.institution)

        self.A.save()
        self.B1.save()
        self.B2.save()
        self.C1.save()
        self.C2.save()
        self.D2.save()

        self.node_A = RegistrationFactory(project=self.A, creator=self.user)
        self.node_B2 = RegistrationFactory(project=self.B2, creator=self.user)

        self.url = '/{}registrations/?'.format(API_BASE)
