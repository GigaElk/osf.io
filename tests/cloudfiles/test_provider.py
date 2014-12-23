import pytest

from unittest import mock
from tests.utils import async

import time

import furl
import json
import aiohttp
import aiohttp.multidict
import aiohttpretty

from waterbutler.core import exceptions

from waterbutler.cloudfiles import settings
from waterbutler.cloudfiles.provider import CloudFilesProvider


@pytest.fixture
def auth():
    return {
        'name': 'cat',
        'email': 'cat@cat.com',
    }


@pytest.fixture
def credentials():
    return {
        'username': 'prince',
        'token': 'revolutionary',
        'region': 'iad',
    }


@pytest.fixture
def settings():
    return {'container': 'purple rain'}


@pytest.fixture
def provider(auth, credentials, settings):
    return CloudFilesProvider(auth, credentials, settings)


@pytest.fixture
def auth_json():
    return {
        "access": {
            "serviceCatalog": [
                {
                    "name": "cloudFiles",
                    "type": "object-store",
                    "endpoints": [
                        {
                            "publicURL": "https://storage101.iad3.clouddrive.com/v1/MossoCloudFS_926294",
                            "internalURL": "https://snet-storage101.iad3.clouddrive.com/v1/MossoCloudFS_926294",
                            "region": "IAD",
                            "tenantId": "MossoCloudFS_926294"
                        },
                    ]
                }
            ],
            "token": {
                "RAX-AUTH:authenticatedBy": [
                    "APIKEY"
                ],
                "tenant": {
                    "name": "926294",
                    "id": "926294"
                },
                "id": "2322f6b2322f4dbfa69802baf50b0832",
                "expires": "2014-12-17T09:12:26.069Z"
            },
            "user": {
                "name": "osf-production",
                "roles": [
                    {
                        "name": "object-store:admin",
                        "id": "10000256",
                        "description": "Object Store Admin Role for Account User"
                    },
                    {
                        "name": "compute:default",
                        "description": "A Role that allows a user access to keystone Service methods",
                        "id": "6",
                        "tenantId": "926294"
                    },
                    {
                        "name": "object-store:default",
                        "description": "A Role that allows a user access to keystone Service methods",
                        "id": "5",
                        "tenantId": "MossoCloudFS_926294"
                    },
                    {
                        "name": "identity:default",
                        "id": "2",
                        "description": "Default Role."
                    }
                ],
                "id": "secret",
                "RAX-AUTH:defaultRegion": "IAD"
            }
        }
    }


# Metadata Test Scenarios
# (folder_root_empty)
# (folder_root)
#   level1/  (folder_root_level1)
#   level1/level2/ (folder_root_level1_level2)
#   level1/level2/file2.file - (file_root_level1_level2_file2_txt)
#   level1_empty/ (folder_root_level1_empty)
#   similar (file_similar)
#   similar.name (file_similar_name)
#   does_not_exist (404)
#   does_not_exist/ (404)


@pytest.fixture
def folder_root_empty():
    return []


@pytest.fixture
def folder_root():
    return [
        {
            'last_modified': '2014-12-19T22:08:23.006360',
            'content_type': 'application/directory',
            'hash': 'd41d8cd98f00b204e9800998ecf8427e',
            'name': 'level1',
            'bytes': 0
        },
        {
            'subdir': 'level1/'
        },
        {
            'last_modified': '2014-12-19T23:22:23.232240',
            'content_type': 'application/x-www-form-urlencoded;charset=utf-8',
            'hash': 'edfa12d00b779b4b37b81fe5b61b2b3f',
            'name': 'similar',
            'bytes': 190
        },
        {
            'last_modified': '2014-12-19T23:22:14.728640',
            'content_type': 'application/x-www-form-urlencoded;charset=utf-8',
            'hash': 'edfa12d00b779b4b37b81fe5b61b2b3f',
            'name': 'similar.file',
            'bytes': 190
        },
        {
            'last_modified': '2014-12-19T23:20:16.718860',
            'content_type': 'application/directory',
            'hash': 'd41d8cd98f00b204e9800998ecf8427e',
            'name': 'level1_empty',
            'bytes': 0
        }
    ]


@pytest.fixture
def folder_root_level1():
    return [
        {
            'last_modified': '2014-12-19T22:08:26.958830',
            'content_type': 'application/directory',
            'hash': 'd41d8cd98f00b204e9800998ecf8427e',
            'name': 'level1/level2',
            'bytes': 0
        },
        {
            'subdir': 'level1/level2/'
        }
    ]


@pytest.fixture
def folder_root_level1_level2():
    return [
        {
            'name': 'level1/level2/file2.txt',
            'content_type': 'application/x-www-form-urlencoded;charset=utf-8',
            'last_modified': '2014-12-19T23:25:22.497420',
            'bytes': 1365336,
            'hash': 'ebc8cdd3f712fd39476fb921d43aca1a'
        }
    ]


@pytest.fixture
def file_root_level1_level2_file2_txt():
    return aiohttp.multidict.CaseInsensitiveMultiDict([
        ('ORIGIN', 'https://mycloud.rackspace.com'),
        ('CONTENT-LENGTH', '216945'),
        ('ACCEPT-RANGES', 'bytes'),
        ('LAST-MODIFIED', 'Mon, 22 Dec 2014 19:01:02 GMT'),
        ('ETAG', '44325d4f13b09f3769ede09d7c20a82c'),
        ('X-TIMESTAMP', '1419274861.04433'),
        ('CONTENT-TYPE', 'text/plain'),
        ('X-TRANS-ID', 'tx836375d817a34b558756a-0054987deeiad3'),
        ('DATE', 'Mon, 22 Dec 2014 20:24:14 GMT')
    ])


@pytest.fixture
def folder_root_level1_empty():
    return aiohttp.multidict.CaseInsensitiveMultiDict([
        ('ORIGIN', 'https://mycloud.rackspace.com'),
        ('CONTENT-LENGTH', '0'),
        ('ACCEPT-RANGES', 'bytes'),
        ('LAST-MODIFIED', 'Mon, 22 Dec 2014 18:58:56 GMT'),
        ('ETAG', 'd41d8cd98f00b204e9800998ecf8427e'),
        ('X-TIMESTAMP', '1419274735.03160'),
        ('CONTENT-TYPE', 'application/directory'),
        ('X-TRANS-ID', 'txd78273e328fc4ba3a98e3-0054987eeeiad3'),
        ('DATE', 'Mon, 22 Dec 2014 20:28:30 GMT')
    ])


@pytest.fixture
def file_root_similar():
    return aiohttp.multidict.CaseInsensitiveMultiDict([
        ('ORIGIN', 'https://mycloud.rackspace.com'),
        ('CONTENT-LENGTH', '190'),
        ('ACCEPT-RANGES', 'bytes'),
        ('LAST-MODIFIED', 'Fri, 19 Dec 2014 23:22:24 GMT'),
        ('ETAG', 'edfa12d00b779b4b37b81fe5b61b2b3f'),
        ('X-TIMESTAMP', '1419031343.23224'),
        ('CONTENT-TYPE', 'application/x-www-form-urlencoded;charset=utf-8'),
        ('X-TRANS-ID', 'tx7cfeef941f244807aec37-005498754diad3'),
        ('DATE', 'Mon, 22 Dec 2014 19:47:25 GMT')
    ])


@pytest.fixture
def file_root_similar_name():
    return aiohttp.multidict.CaseInsensitiveMultiDict([
        ('ORIGIN', 'https://mycloud.rackspace.com'),
        ('CONTENT-LENGTH', '190'),
        ('ACCEPT-RANGES', 'bytes'),
        ('LAST-MODIFIED', 'Mon, 22 Dec 2014 19:07:12 GMT'),
        ('ETAG', 'edfa12d00b779b4b37b81fe5b61b2b3f'),
        ('X-TIMESTAMP', '1419275231.66160'),
        ('CONTENT-TYPE', 'application/x-www-form-urlencoded;charset=utf-8'),
        ('X-TRANS-ID', 'tx438cbb32b5344d63b267c-0054987f3biad3'),
        ('DATE', 'Mon, 22 Dec 2014 20:29:47 GMT')
    ])


@pytest.fixture
def token(auth_json):
    return auth_json['access']['token']['id']


@pytest.fixture
def endpoint(auth_json):
    return auth_json['access']['serviceCatalog'][0]['endpoints'][0]['publicURL']


@pytest.fixture
def temp_url_key():
    return 'temporary beret'


@pytest.fixture
def mock_auth(auth_json):
    aiohttpretty.register_json_uri(
        'POST',
        settings.AUTH_URL,
        body=auth_json,
    )


@pytest.fixture
def mock_temp_key(endpoint, temp_url_key):
    aiohttpretty.register_uri(
        'HEAD',
        endpoint,
        status=204,
        headers={'X-Account-Meta-Temp-URL-Key': temp_url_key},
    )


@pytest.fixture
def mock_time(monkeypatch):
    mock_time = mock.Mock()
    mock_time.return_value = 10
    monkeypatch.setattr(time, 'time', mock_time)


@pytest.fixture
def connected_provider(provider, token, endpoint, temp_url_key, mock_time):
    provider.token = token
    provider.endpoint = endpoint
    provider.temp_url_key = temp_url_key.encode()
    return provider


@async
@pytest.mark.aiohttpretty
def test_download(connected_provider):
    path = 'lets-go-crazy'
    body = b'dearly-beloved'
    url = connected_provider.generate_url(path)
    aiohttpretty.register_uri('GET', url, body=body)
    result = yield from connected_provider.download(path)
    content = yield from result.response.read()
    assert content == body


@async
@pytest.mark.aiohttpretty
def test_download_accept_url(connected_provider):
    path = 'lets-go-crazy'
    body = b'dearly-beloved'
    url = connected_provider.generate_url(path)
    result = yield from connected_provider.download(path, accept_url=True)
    assert result == url
    aiohttpretty.register_uri('GET', url, body=body)
    response = yield from aiohttp.request('GET', url)
    content = yield from response.read()
    assert content == body


@async
@pytest.mark.aiohttpretty
def test_download_not_found(connected_provider):
    path = 'lets-go-crazy'
    url = connected_provider.generate_url(path)
    aiohttpretty.register_uri('GET', url, status=404)
    with pytest.raises(exceptions.DownloadError):
        yield from connected_provider.download(path)


@async
@pytest.mark.aiohttpretty
def test_metadata_folder_root_empty(connected_provider, folder_root_empty):
    path = '/'
    body = json.dumps(folder_root_empty).encode('utf-8')
    url = furl.furl(connected_provider.build_url(''))
    url.args.update({'prefix': path, 'delimiter': '/'})
    aiohttpretty.register_uri('GET', url.url, status=200, body=body)
    result = yield from connected_provider.metadata(path)

    assert len(result) == 0
    assert result == []


@async
@pytest.mark.aiohttpretty
def test_metadata_folder_root(connected_provider, folder_root):
    path = '/'
    body = json.dumps(folder_root).encode('utf-8')
    url = furl.furl(connected_provider.build_url(''))
    url.args.update({'prefix': path, 'delimiter': '/'})
    aiohttpretty.register_uri('GET', url.url, status=200, body=body)
    result = yield from connected_provider.metadata(path)

    assert len(result) == 4
    assert result[0]['name'] == 'level1'
    assert result[0]['path'] == 'level1/'
    assert result[0]['kind'] == 'folder'
    assert result[1]['name'] == 'similar'
    assert result[1]['path'] == 'similar'
    assert result[1]['kind'] == 'file'
    assert result[2]['name'] == 'similar.file'
    assert result[2]['path'] == 'similar.file'
    assert result[2]['kind'] == 'file'
    assert result[3]['name'] == 'level1_empty'
    assert result[3]['path'] == 'level1_empty/'
    assert result[3]['kind'] == 'folder'


@async
@pytest.mark.aiohttpretty
def test_metadata_folder_root_level1(connected_provider, folder_root_level1):
    path = 'level1/'
    body = json.dumps(folder_root_level1).encode('utf-8')
    url = furl.furl(connected_provider.build_url(''))
    url.args.update({'prefix': path, 'delimiter': '/'})
    aiohttpretty.register_uri('GET', url.url, status=200, body=body)
    result = yield from connected_provider.metadata(path)

    assert len(result) == 1
    assert result[0]['name'] == 'level2'
    assert result[0]['path'] == 'level1/level2/'
    assert result[0]['kind'] == 'folder'


@async
@pytest.mark.aiohttpretty
def test_metadata_folder_root_level1_level2(connected_provider, folder_root_level1_level2):
    path = 'level1/level2/'
    body = json.dumps(folder_root_level1_level2).encode('utf-8')
    url = furl.furl(connected_provider.build_url(''))
    url.args.update({'prefix': path, 'delimiter': '/'})
    aiohttpretty.register_uri('GET', url.url, status=200, body=body)
    result = yield from connected_provider.metadata(path)

    assert len(result) == 1
    assert result[0]['name'] == 'file2.txt'
    assert result[0]['path'] == 'level1/level2/file2.txt'
    assert result[0]['kind'] == 'file'


@async
@pytest.mark.aiohttpretty
def test_metadata_file_root_level1_level2_file2_txt(connected_provider, file_root_level1_level2_file2_txt):
    path = 'level1/level2/file2.txt'
    url = furl.furl(connected_provider.build_url(path))
    aiohttpretty.register_uri('HEAD', url.url, status=200, headers=file_root_level1_level2_file2_txt)
    result = yield from connected_provider.metadata(path)

    assert result['name'] == 'file2.txt'
    assert result['path'] == 'level1/level2/file2.txt'
    assert result['kind'] == 'file'
    assert result['content_type'] == 'text/plain'


@async
@pytest.mark.aiohttpretty
def test_metadata_folder_root_level1_empty(connected_provider, folder_root_level1_empty):
    path = 'level1_empty/'
    folder_url = furl.furl(connected_provider.build_url(''))
    folder_url.args.update({'prefix': path, 'delimiter': '/'})
    folder_body = json.dumps([]).encode('utf-8')
    file_url = furl.furl(connected_provider.build_url(path.rstrip('/')))
    aiohttpretty.register_uri('GET', folder_url.url, status=200, body=folder_body)
    aiohttpretty.register_uri('HEAD', file_url.url, status=200, headers=folder_root_level1_empty)
    result = yield from connected_provider.metadata(path)

    assert result == []


@async
@pytest.mark.aiohttpretty
def test_metadata_file_root_similar(connected_provider, file_root_similar):
    path = 'similar'
    url = furl.furl(connected_provider.build_url(path))
    aiohttpretty.register_uri('HEAD', url.url, status=200, headers=file_root_similar)
    result = yield from connected_provider.metadata(path)

    assert result['name'] == 'similar'
    assert result['path'] == 'similar'
    assert result['kind'] == 'file'


@async
@pytest.mark.aiohttpretty
def test_metadata_file_root_similar_name(connected_provider, file_root_similar_name):
    path = 'similar.name'
    url = furl.furl(connected_provider.build_url(path))
    aiohttpretty.register_uri('HEAD', url.url, status=200, headers=file_root_similar_name)
    result = yield from connected_provider.metadata(path)

    assert result['name'] == 'similar.name'
    assert result['path'] == 'similar.name'
    assert result['kind'] == 'file'


@async
@pytest.mark.aiohttpretty
def test_metadata_file_does_not_exist(connected_provider):
    path = 'does_not.exist'
    url = furl.furl(connected_provider.build_url(path))
    aiohttpretty.register_uri('HEAD', url.url, status=404)
    with pytest.raises(exceptions.MetadataError):
        yield from connected_provider.metadata(path)


@async
@pytest.mark.aiohttpretty
def test_metadata_folder_does_not_exist(connected_provider):
    path = 'does_not_exist/'
    folder_url = furl.furl(connected_provider.build_url(''))
    folder_url.args.update({'prefix': path, 'delimiter': '/'})
    folder_body = json.dumps([]).encode('utf-8')
    file_url = furl.furl(connected_provider.build_url(path.rstrip('/')))
    aiohttpretty.register_uri('GET', folder_url.url, status=200, body=folder_body)
    aiohttpretty.register_uri('HEAD', file_url.url, status=404)
    with pytest.raises(exceptions.MetadataError):
        yield from connected_provider.metadata(path)
