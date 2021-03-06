"""
Copyright 2017-present, Airbnb Inc.

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

   http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
"""
# pylint: disable=no-self-use,unused-argument,attribute-defined-outside-init,protected-access
from collections import OrderedDict

from mock import call, patch
from moto import mock_s3, mock_kms
from nose.tools import assert_false, assert_is_instance, assert_true

from stream_alert.alert_processor.outputs import carbonblack
from stream_alert.alert_processor.outputs.carbonblack import CarbonBlackOutput
from stream_alert_cli.helpers import MockCBAPI, put_mock_creds
from tests.unit.stream_alert_alert_processor import (
    ACCOUNT_ID,
    CONFIG,
    FUNCTION_NAME,
    KMS_ALIAS,
    REGION
)
from tests.unit.stream_alert_alert_processor.helpers import (
    get_alert,
    remove_temp_secrets
)


@patch('stream_alert.alert_processor.outputs.output_base.OutputDispatcher.MAX_RETRY_ATTEMPTS', 1)
class TestCarbonBlackOutput(object):
    """Test class for CarbonBlackOutput"""
    DESCRIPTOR = 'unit_test_carbonblack'
    SERVICE = 'carbonblack'
    OUTPUT = ':'.join([SERVICE, DESCRIPTOR])
    CREDS = {'url': 'carbon.foo.bar',
             'ssl_verify': 'Y',
             'token': '1234567890127a3d7f37f4153270bff41b105899'}

    def setup(self):
        """Setup before each method"""
        self._mock_s3 = mock_s3()
        self._mock_s3.start()
        self._mock_kms = mock_kms()
        self._mock_kms.start()
        self._dispatcher = CarbonBlackOutput(REGION, ACCOUNT_ID, FUNCTION_NAME, CONFIG)
        remove_temp_secrets()
        output_name = self._dispatcher.output_cred_name(self.DESCRIPTOR)
        put_mock_creds(output_name, self.CREDS, self._dispatcher.secrets_bucket, REGION, KMS_ALIAS)

    def teardown(self):
        """Teardown after each method"""
        self._mock_s3.stop()
        self._mock_kms.stop()

    def test_get_user_defined_properties(self):
        """CarbonBlackOutput - User Defined Properties"""
        assert_is_instance(CarbonBlackOutput.get_user_defined_properties(), OrderedDict)

    @patch('logging.Logger.error')
    def test_dispatch_no_context(self, mock_logger):
        """CarbonBlackOutput - Dispatch No Context"""
        assert_false(self._dispatcher.dispatch(get_alert(), self.OUTPUT))
        mock_logger.assert_has_calls([
            call('[%s] Alert must contain context to run actions', 'carbonblack'),
            call('Failed to send alert to %s:%s', 'carbonblack', 'unit_test_carbonblack')
        ])

    @patch.object(carbonblack, 'CbResponseAPI', side_effect=MockCBAPI)
    def test_dispatch_already_banned(self, mock_cb):
        """CarbonBlackOutput - Dispatch Already Banned"""
        alert_context = {
            'carbonblack': {
                'action': 'ban',
                'value': 'BANNED_ENABLED_HASH'
            }
        }
        assert_true(self._dispatcher.dispatch(get_alert(context=alert_context), self.OUTPUT))

    @patch.object(carbonblack, 'CbResponseAPI', side_effect=MockCBAPI)
    def test_dispatch_banned_disabled(self, mock_cb):
        """CarbonBlackOutput - Dispatch Banned Disabled"""
        alert_context = {
            'carbonblack': {
                'action': 'ban',
                'value': 'BANNED_DISABLED_HASH'
            }
        }
        assert_true(self._dispatcher.dispatch(get_alert(context=alert_context), self.OUTPUT))

    @patch.object(carbonblack, 'CbResponseAPI', side_effect=MockCBAPI)
    def test_dispatch_not_banned(self, mock_cb):
        """CarbonBlackOutput - Dispatch Not Banned"""
        alert_context = {
            'carbonblack': {
                'action': 'ban',
                'value': 'NOT_BANNED_HASH'
            }
        }
        assert_true(self._dispatcher.dispatch(get_alert(context=alert_context), self.OUTPUT))

    @patch('logging.Logger.error')
    @patch.object(carbonblack, 'CbResponseAPI', side_effect=MockCBAPI)
    def test_dispatch_invalid_action(self, mock_cb, mock_logger):
        """CarbonBlackOutput - Invalid Action"""
        alert_context = {
            'carbonblack': {
                'action': 'rickroll',
            }
        }
        assert_false(self._dispatcher.dispatch(get_alert(context=alert_context), self.OUTPUT))

        mock_logger.assert_has_calls([
            call('[%s] Action not supported: %s', 'carbonblack', 'rickroll'),
            call('Failed to send alert to %s:%s', 'carbonblack', 'unit_test_carbonblack')
        ])
