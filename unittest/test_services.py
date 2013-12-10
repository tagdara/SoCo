# -*- coding: utf-8 -*-
""" Tests for the services module """

# These tests require pytest, and mock. Mock comes with Python 3.3, but has
# also been backported for Python 2.7. It is available on pypi.

from __future__ import unicode_literals

import pytest
from soco.services import Service
from soco.exceptions import SoCoUPnPException

try:
    from unittest import mock
except:
    import mock  # TODO: add mock to requirements

# Dummy known-good errors/responses etc.  These are not necessarily valid as
# actual commands, but are valid XML/UPnP. They also contain unicode characters
# to test unicode handling.

DUMMY_ERROR = "".join([
    '<?xml version="1.0"?>',
    '<s:Envelope ',
    'xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" ',
    's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">',
        '<s:Body>',
            '<s:Fault>',
                '<faultcode>s:Client</faultcode>',
                '<faultstring>UPnPError</faultstring>',
                '<detail>',
                    '<UPnPError xmlns="urn:schemas-upnp-org:control-1-0">',
                        '<errorCode>607</errorCode>',
                        '<errorDescription>Oops μИⅠℂ☺ΔЄ💋</errorDescription>',
                    '</UPnPError>',
                '</detail>',
            '</s:Fault>',
        '</s:Body>',
    '</s:Envelope>'])  # noqa PEP8

DUMMY_VALID_RESPONSE = "".join([
    '<?xml version="1.0"?>',
    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"',
        ' s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">',
        '<s:Body>',
            '<u:GetLEDStateResponse ',
                'xmlns:u="urn:schemas-upnp-org:service:DeviceProperties:1">',
                '<CurrentLEDState>On</CurrentLEDState>',
                '<Unicode>μИⅠℂ☺ΔЄ💋</Unicode>',
        '</u:GetLEDStateResponse>',
        '</s:Body>',
    '</s:Envelope>'])  # noqa PEP8

DUMMY_VALID_ACTION = "".join([
    '<?xml version="1.0"?>',
    '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"',
        ' s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">',
        '<s:Body>',
            '<u:SetAVTransportURI ',
                'xmlns:u="urn:schemas-upnp-org:service:Service:1">',
                '<InstanceID>0</InstanceID>',
                '<CurrentURI>URI</CurrentURI>',
                '<CurrentURIMetaData></CurrentURIMetaData>',
                '<Unicode>μИⅠℂ☺ΔЄ💋</Unicode>'
            '</u:SetAVTransportURI>',
        '</s:Body>'
    '</s:Envelope>'])  # noqa PEP8


@pytest.fixture()
def service():
    """ A mock Service, for use as a test fixture """

    mock_soco = mock.MagicMock()
    mock_soco.speaker_ip = "192.168.1.101"
    return Service(mock_soco)


def test_init_defaults(service):
    """ Check default properties are set up correctly """
    assert service.service_type == "Service"
    assert service.version == 1
    assert service.service_id == "Service"
    assert service.base_url == "http://192.168.1.101:1400"
    assert service.control_url == "/Service/Control"
    assert service.scpd_url == "/xml/Service1.xml"


def test_method_dispatcher_function_creation(service):
    """ Testing __getattr__ functionality """
    import inspect
    # There should be no testing method
    assert 'testing' not in service.__dict__.keys()
    # but we should be able to inspect it
    assert inspect.ismethod(service.testing)
    # and then, having examined it, the method should be cached on the instance
    assert 'testing' in service.__dict__.keys()
    assert service.testing.__name__ == "testing"
    # check that send_command is actually called when we invoke a method
    service.send_command = lambda x, y: "Hello {}".format(x)
    assert service.testing(service) == "Hello testing"


def test_method_dispatcher_arg_count(service):
    """ _dispatcher should take zero or one arguments """
    service.send_command = mock.Mock()
    # http://bugs.python.org/issue7688
    # __name__ must be a string in python 2
    method = service.__getattr__(str('test'))
    assert method('onearg')
    assert method()  # no args
    with pytest.raises(TypeError):
        method('two', 'args')


def test_wrap(service):
    """ wrapping args in XML properly """
    assert service.wrap_arguments([('first', 'one'), ('second', 2)]) == \
        "<first>one</first><second>2</second>"
    assert service.wrap_arguments() == ""
    # Unicode
    assert service.wrap_arguments([('unicode', "μИⅠℂ☺ΔЄ💋")]) == \
        "<unicode>μИⅠℂ☺ΔЄ💋</unicode>"
    # XML escaping - do we also need &apos; ?
    assert service.wrap_arguments([('weird', '&<"2')]) == \
        "<weird>&amp;&lt;&quot;2</weird>"


def test_unwrap(service):
    """ unwrapping args from XML """
    assert service.unwrap_arguments(DUMMY_VALID_RESPONSE) == {
        "CurrentLEDState": "On",
        "Unicode": "μИⅠℂ☺ΔЄ💋"}


def test_build_command(service):
    """ Test creation of SOAP body and headers from a command """
    headers, body = service.build_command('SetAVTransportURI', [
        ('InstanceID', 0),
        ('CurrentURI', 'URI'),
        ('CurrentURIMetaData', ''),
        ('Unicode', 'μИⅠℂ☺ΔЄ💋')
        ])
    assert body == DUMMY_VALID_ACTION
    assert headers == {
        'Content-Type': 'text/xml; charset="utf-8"',
        'SOAPACTION':
        'urn:schemas-upnp-org:service:Service:1#SetAVTransportURI'}


def test_send_command(service):
    """ Calling a command should result in a http request """
    with mock.patch('requests.post') as fake_post:
        response = fake_post()
        response.headers = {}        
        response.status_code = 200
        response.text = DUMMY_VALID_RESPONSE
        result = service.send_command('SetAVTransportURI', [
            ('InstanceID', 0),
            ('CurrentURI', 'URI'),
            ('CurrentURIMetaData', ''),
            ('Unicode', 'μИⅠℂ☺ΔЄ💋')
            ])
        fake_post.assert_called_with(
            'http://192.168.1.101:1400/Service/Control',
            headers=mock.ANY, data=DUMMY_VALID_ACTION)
        assert result == {'CurrentLEDState': 'On', 'Unicode': "μИⅠℂ☺ΔЄ💋"}


def test_handle_upnp_error(service):
    """ Check errors are extracted properly """
    with pytest.raises(SoCoUPnPException) as E:
        service.handle_upnp_error(DUMMY_ERROR)
    assert "UPnP Error 607" in E.value.message
    assert E.value.error_code == '607'
    assert E.value.error_description == 'Signature Failure'
    # TODO: Try this with a None Error Code

# TODO: test iter_actions
