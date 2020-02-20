# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import copy
from io import BytesIO
import json
from unittest import mock

from configman.dotdict import DotDict
import requests_mock
import pytest

from socorro.lib.datetimeutil import datetime_from_isodate_string
from socorro.lib.util import dotdict_to_dict
from socorro.processor.rules.mozilla import (
    AddonsRule,
    BetaVersionRule,
    ConvertModuleSignatureInfoRule,
    DatesAndTimesRule,
    ESRVersionRewrite,
    EnvironmentRule,
    ExploitablityRule,
    FlashVersionRule,
    JavaProcessRule,
    ModulesInStackRule,
    MozCrashReasonRule,
    OSPrettyVersionRule,
    OutOfMemoryBinaryRule,
    PHCRule,
    PluginContentURL,
    PluginRule,
    PluginUserComment,
    ProductRewrite,
    ProductRule,
    SignatureGeneratorRule,
    ThemePrettyNameRule,
    TopMostFilesRule,
    UserDataRule,
)
from socorro.signature.generator import SignatureGenerator
from socorro.unittest import WHATEVER
from socorro.unittest.processor import get_basic_processor_meta


canonical_standard_raw_crash = DotDict(
    {
        "uuid": "00000000-0000-0000-0000-000002140504",
        "InstallTime": "1335439892",
        "AdapterVendorID": "0x1002",
        "TotalVirtualMemory": "4294836224",
        "Comments": "why did my browser crash?  #fail",
        "Theme": "classic/1.0",
        "Version": "12.0",
        "Email": "noreply@mozilla.com",
        "Vendor": "Mozilla",
        "EMCheckCompatibility": "true",
        "Throttleable": "1",
        "id": "{ec8030f7-c20a-464f-9b0e-13a3a9e97384}",
        "buildid": "20120420145725",
        "AvailablePageFile": "10641510400",
        "version": "12.0",
        "AdapterDeviceID": "0x7280",
        "ReleaseChannel": "release",
        "submitted_timestamp": "2012-05-08T23:26:33.454482+00:00",
        "URL": "http://www.mozilla.com",
        "timestamp": 1336519593.454627,
        "Notes": (
            "AdapterVendorID: 0x1002, AdapterDeviceID: 0x7280, "
            "AdapterSubsysID: 01821043, "
            "AdapterDriverVersion: 8.593.100.0\nD3D10 Layers? D3D10 "
            "Layers- D3D9 Layers? D3D9 Layers- "
        ),
        "CrashTime": "1336519554",
        "Winsock_LSP": (
            "MSAFD Tcpip [TCP/IPv6] : 2 : 1 :  \n "
            "MSAFD Tcpip [UDP/IPv6] : 2 : 2 : "
            "%SystemRoot%\\system32\\mswsock.dll \n "
            "MSAFD Tcpip [RAW/IPv6] : 2 : 3 :  \n "
            "MSAFD Tcpip [TCP/IP] : 2 : 1 : "
            "%SystemRoot%\\system32\\mswsock.dll \n "
            "MSAFD Tcpip [UDP/IP] : 2 : 2 :  \n "
            "MSAFD Tcpip [RAW/IP] : 2 : 3 : "
            "%SystemRoot%\\system32\\mswsock.dll \n "
            "\u041f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a "
            "\u0443\u0441\u043b\u0443\u0433 RSVP TCPv6 : 2 : 1 :  \n "
            "\u041f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a "
            "\u0443\u0441\u043b\u0443\u0433 RSVP TCP : 2 : 1 : "
            "%SystemRoot%\\system32\\mswsock.dll \n "
            "\u041f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a "
            "\u0443\u0441\u043b\u0443\u0433 RSVP UDPv6 : 2 : 2 :  \n "
            "\u041f\u043e\u0441\u0442\u0430\u0432\u0449\u0438\u043a "
            "\u0443\u0441\u043b\u0443\u0433 RSVP UDP : 2 : 2 : "
            "%SystemRoot%\\system32\\mswsock.dll"
        ),
        "FramePoisonBase": "00000000f0de0000",
        "AvailablePhysicalMemory": "2227773440",
        "FramePoisonSize": "65536",
        "StartupTime": "1336499438",
        "Add-ons": (
            "adblockpopups@jessehakanen.net:0.3,"
            "dmpluginff%40westbyte.com:1%2C4.8,"
            "firebug@software.joehewitt.com:1.9.1,"
            "killjasmin@pierros14.com:2.4,"
            "support@surfanonymous-free.com:1.0,"
            "uploader@adblockfilters.mozdev.org:2.1,"
            "{a0d7ccb3-214d-498b-b4aa-0e8fda9a7bf7}:20111107,"
            "{d10d0bf8-f5b5-c8b4-a8b2-2b9879e08c5d}:2.0.3,"
            "anttoolbar@ant.com:2.4.6.4,"
            "{972ce4c6-7e08-4474-a285-3208198ce6fd}:12.0,"
            "elemhidehelper@adblockplus.org:1.2.1"
        ),
        "BuildID": "20120420145725",
        "SecondsSinceLastCrash": "86985",
        "ProductName": "Firefox",
        "legacy_processing": 0,
        "AvailableVirtualMemory": "3812708352",
        "SystemMemoryUsePercentage": "48",
        "ProductID": "{ec8030f7-c20a-464f-9b0e-13a3a9e97384}",
        "Distributor": "Mozilla",
        "Distributor_version": "12.0",
    }
)

canonical_processed_crash = DotDict(
    {
        "json_dump": {
            "sensitive": {"exploitability": "high"},
            "modules": [
                {
                    "end_addr": "0x12e6000",
                    "filename": "plugin-container.exe",
                    "version": "26.0.0.5084",
                    "debug_id": "8385BD80FD534F6E80CF65811735A7472",
                    "debug_file": "plugin-container.pdb",
                    "base_addr": "0x12e0000",
                },
                {
                    "end_addr": "0x12e6000",
                    "filename": "plugin-container.exe",
                    "version": "26.0.0.5084",
                    "debug_id": "8385BD80FD534F6E80CF65811735A7472",
                    "debug_file": "plugin-container.pdb",
                    "base_addr": "0x12e0000",
                },
                {
                    "end_addr": "0x12e6000",
                    "filename": "FlashPlayerPlugin9_1_3_08.exe",
                    "debug_id": "8385BD80FD534F6E80CF65811735A7472",
                    "debug_file": "plugin-container.pdb",
                    "base_addr": "0x12e0000",
                },
                {
                    "end_addr": "0x12e6000",
                    "filename": "plugin-container.exe",
                    "version": "26.0.0.5084",
                    "debug_id": "8385BD80FD534F6E80CF65811735A7472",
                    "debug_file": "plugin-container.pdb",
                    "base_addr": "0x12e0000",
                },
            ],
        }
    }
)


class TestConvertModuleSignatureInfoRule:
    def test_no_value(self):
        raw_crash = DotDict()
        raw_dumps = {}
        processed_crash = {}
        processor_meta = get_basic_processor_meta()

        rule = ConvertModuleSignatureInfoRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert raw_crash == {}
        assert processed_crash == {}

    def test_string_value(self):
        raw_crash = DotDict({"ModuleSignatureInfo": "{}"})
        raw_dumps = {}
        processed_crash = {}
        processor_meta = get_basic_processor_meta()

        rule = ConvertModuleSignatureInfoRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert raw_crash == {"ModuleSignatureInfo": "{}"}
        assert processed_crash == {}

    def test_object_value(self):
        raw_crash = DotDict({"ModuleSignatureInfo": {"foo": "bar"}})
        raw_dumps = {}
        processed_crash = {}
        processor_meta = get_basic_processor_meta()

        rule = ConvertModuleSignatureInfoRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert raw_crash == {"ModuleSignatureInfo": '{"foo": "bar"}'}
        assert processed_crash == {}

    def test_object_value_with_dict(self):
        raw_crash = {"ModuleSignatureInfo": {"foo": "bar"}}
        raw_dumps = {}
        processed_crash = {}
        processor_meta = get_basic_processor_meta()

        rule = ConvertModuleSignatureInfoRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert raw_crash == {"ModuleSignatureInfo": '{"foo": "bar"}'}
        assert processed_crash == {}


class TestProductRule(object):
    def test_everything_we_hoped_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = ProductRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.product == "Firefox"
        assert processed_crash.version == "12.0"
        assert processed_crash.productid == "{ec8030f7-c20a-464f-9b0e-13a3a9e97384}"
        assert processed_crash.release_channel == "release"
        assert processed_crash.build == "20120420145725"

    def test_stuff_missing(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        del raw_crash.Version
        del raw_crash.Distributor
        del raw_crash.Distributor_version
        del raw_crash.ReleaseChannel

        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = ProductRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.product == "Firefox"
        assert processed_crash.version == ""
        assert processed_crash.productid == "{ec8030f7-c20a-464f-9b0e-13a3a9e97384}"
        assert processed_crash.release_channel == ""
        assert processed_crash.build == "20120420145725"


class TestUserDataRule(object):
    def test_everything_we_hoped_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = UserDataRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.url == "http://www.mozilla.com"
        assert processed_crash.user_comments == "why did my browser crash?  #fail"
        assert processed_crash.email == "noreply@mozilla.com"
        assert processed_crash.user_id == ""

    def test_stuff_missing(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        del raw_crash.URL
        del raw_crash.Comments
        del raw_crash.Email

        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = UserDataRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.url is None
        assert processed_crash.user_comments is None
        assert processed_crash.email is None


class TestEnvironmentRule(object):
    def test_everything_we_hoped_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = EnvironmentRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.app_notes == raw_crash.Notes

    def test_stuff_missing(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        del raw_crash.Notes

        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = EnvironmentRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.app_notes == ""


class TestPluginRule(object):
    def test_plugin_hang(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.PluginHang = 1
        raw_crash.Hang = 0
        raw_crash.ProcessType = "plugin"
        raw_crash.PluginFilename = "x.exe"
        raw_crash.PluginName = "X"
        raw_crash.PluginVersion = "0.0"
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = PluginRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.hangid == "fake-00000000-0000-0000-0000-000002140504"
        assert processed_crash.hang_type == -1
        assert processed_crash.process_type == "plugin"
        assert processed_crash.PluginFilename == "x.exe"
        assert processed_crash.PluginName == "X"
        assert processed_crash.PluginVersion == "0.0"

    def test_browser_hang(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.Hang = 1
        raw_crash.ProcessType = "browser"
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = PluginRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.hangid is None
        assert processed_crash.hang_type == 1
        assert processed_crash.process_type == "browser"
        assert "PluginFilename" not in processed_crash
        assert "PluginName" not in processed_crash
        assert "PluginVersion" not in processed_crash


class TestAddonsRule(object):
    def test_action_nothing_unexpected(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        addons_rule = AddonsRule()
        addons_rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        # the raw crash & raw_dumps should not have changed
        assert raw_crash == canonical_standard_raw_crash
        assert raw_dumps == {}

        expected_addon_list = [
            "adblockpopups@jessehakanen.net:0.3",
            "dmpluginff@westbyte.com:1,4.8",
            "firebug@software.joehewitt.com:1.9.1",
            "killjasmin@pierros14.com:2.4",
            "support@surfanonymous-free.com:1.0",
            "uploader@adblockfilters.mozdev.org:2.1",
            "{a0d7ccb3-214d-498b-b4aa-0e8fda9a7bf7}:20111107",
            "{d10d0bf8-f5b5-c8b4-a8b2-2b9879e08c5d}:2.0.3",
            "anttoolbar@ant.com:2.4.6.4",
            "{972ce4c6-7e08-4474-a285-3208198ce6fd}:12.0",
            "elemhidehelper@adblockplus.org:1.2.1",
        ]
        assert processed_crash.addons == expected_addon_list
        assert processed_crash.addons_checked

    def test_action_colon_in_addon_version(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash["Add-ons"] = "adblockpopups@jessehakanen.net:0:3:1"
        raw_crash["EMCheckCompatibility"] = "Nope"
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        addons_rule = AddonsRule()
        addons_rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected_addon_list = ["adblockpopups@jessehakanen.net:0:3:1"]
        assert processed_crash.addons == expected_addon_list
        assert not processed_crash.addons_checked

    def test_action_addon_is_nonsense(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash["Add-ons"] = "naoenut813teq;mz;<[`19ntaotannn8999anxse `"
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        addons_rule = AddonsRule()
        addons_rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected_addon_list = ["naoenut813teq;mz;<[`19ntaotannn8999anxse `:NO_VERSION"]
        assert processed_crash.addons == expected_addon_list
        assert processed_crash.addons_checked


class TestDatesAndTimesRule(object):
    def test_get_truncate_or_warn(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        processor_notes = []
        ret = DatesAndTimesRule._get_truncate_or_warn(
            raw_crash, "submitted_timestamp", processor_notes, "", 50
        )
        assert ret == "2012-05-08T23:26:33.454482+00:00"
        assert processor_notes == []

        processor_notes = []
        ret = DatesAndTimesRule._get_truncate_or_warn(
            raw_crash,
            "terrible_timestamp",
            processor_notes,
            "2012-05-08T23:26:33.454482+00:00",
            "50",
        )
        assert ret == "2012-05-08T23:26:33.454482+00:00"
        assert processor_notes == ["WARNING: raw_crash missing terrible_timestamp"]

        raw_crash.submitted_timestamp = 17
        processor_notes = []
        ret = DatesAndTimesRule._get_truncate_or_warn(
            raw_crash,
            "submitted_timestamp",
            processor_notes,
            "2012-05-08T23:26:33.454482+00:00",
            "50",
        )
        assert ret == "2012-05-08T23:26:33.454482+00:00"
        try:
            42[:1]
        except TypeError as err:
            type_error_value = str(err)
        expected = [
            "WARNING: raw_crash[submitted_timestamp] contains unexpected "
            "value: 17; %s" % type_error_value
        ]
        assert processor_notes == expected

    def test_everything_we_hoped_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = DatesAndTimesRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected = datetime_from_isodate_string(raw_crash.submitted_timestamp)
        assert processed_crash.submitted_timestamp == expected
        assert processed_crash.date_processed == processed_crash.submitted_timestamp
        assert processed_crash.crash_time == 1336519554
        expected = datetime_from_isodate_string("2012-05-08 23:25:54+00:00")
        assert processed_crash.client_crash_date == expected
        assert processed_crash.install_age == 1079662
        assert processed_crash.uptime == 20116
        assert processed_crash.last_crash == 86985

    def test_bad_timestamp(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.timestamp = "hi there"
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = DatesAndTimesRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected = datetime_from_isodate_string(raw_crash.submitted_timestamp)
        assert processed_crash.submitted_timestamp == expected
        assert processed_crash.date_processed == processed_crash.submitted_timestamp
        assert processed_crash.crash_time == 1336519554
        expected = datetime_from_isodate_string("2012-05-08 23:25:54+00:00")
        assert processed_crash.client_crash_date == expected
        assert processed_crash.install_age == 1079662
        assert processed_crash.uptime == 20116
        assert processed_crash.last_crash == 86985
        assert processor_meta.processor_notes == ['non-integer value of "timestamp"']

    def test_bad_timestamp_and_no_crash_time(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.timestamp = "hi there"
        del raw_crash.CrashTime
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = DatesAndTimesRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected = datetime_from_isodate_string(raw_crash.submitted_timestamp)
        assert processed_crash.submitted_timestamp == expected
        assert processed_crash.date_processed == processed_crash.submitted_timestamp
        assert processed_crash.crash_time == 0
        expected = datetime_from_isodate_string("1970-01-01 00:00:00+00:00")
        assert processed_crash.client_crash_date == expected
        assert processed_crash.install_age == -1335439892
        assert processed_crash.uptime == 0
        assert processed_crash.last_crash == 86985

        expected = [
            'non-integer value of "timestamp"',
            "WARNING: raw_crash missing CrashTime",
        ]
        assert processor_meta.processor_notes == expected

    def test_no_startup_time_bad_timestamp(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.timestamp = "hi there"
        del raw_crash.StartupTime
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = DatesAndTimesRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected = datetime_from_isodate_string(raw_crash.submitted_timestamp)
        assert processed_crash.submitted_timestamp == expected
        assert processed_crash.date_processed == processed_crash.submitted_timestamp
        assert processed_crash.crash_time == 1336519554
        expected = datetime_from_isodate_string("2012-05-08 23:25:54+00:00")
        assert processed_crash.client_crash_date == expected
        assert processed_crash.install_age == 1079662
        assert processed_crash.uptime == 0
        assert processed_crash.last_crash == 86985

        expected = ['non-integer value of "timestamp"']
        assert processor_meta.processor_notes == expected

    def test_no_startup_time(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        del raw_crash.StartupTime
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = DatesAndTimesRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected = datetime_from_isodate_string(raw_crash.submitted_timestamp)
        assert processed_crash.submitted_timestamp == expected
        assert processed_crash.date_processed == processed_crash.submitted_timestamp
        assert processed_crash.crash_time == 1336519554
        expected = datetime_from_isodate_string("2012-05-08 23:25:54+00:00")
        assert processed_crash.client_crash_date == expected
        assert processed_crash.install_age == 1079662
        assert processed_crash.uptime == 0
        assert processed_crash.last_crash == 86985
        assert processor_meta.processor_notes == []

    def test_bad_startup_time(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.StartupTime = "feed the goats"
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = DatesAndTimesRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected = datetime_from_isodate_string(raw_crash.submitted_timestamp)
        assert processed_crash.submitted_timestamp == expected
        assert processed_crash.date_processed == processed_crash.submitted_timestamp
        assert processed_crash.crash_time == 1336519554
        expected = datetime_from_isodate_string("2012-05-08 23:25:54+00:00")
        assert processed_crash.client_crash_date == expected
        assert processed_crash.install_age == 1079662
        assert processed_crash.uptime == 1336519554
        assert processed_crash.last_crash == 86985
        assert processor_meta.processor_notes == ['non-integer value of "StartupTime"']

    def test_bad_install_time(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.InstallTime = "feed the goats"
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = DatesAndTimesRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected = datetime_from_isodate_string(raw_crash.submitted_timestamp)
        assert processed_crash.submitted_timestamp == expected
        assert processed_crash.date_processed == processed_crash.submitted_timestamp
        assert processed_crash.crash_time == 1336519554
        expected = datetime_from_isodate_string("2012-05-08 23:25:54+00:00")
        assert processed_crash.client_crash_date == expected
        assert processed_crash.install_age == 1336519554
        assert processed_crash.uptime == 20116
        assert processed_crash.last_crash == 86985
        assert processor_meta.processor_notes == ['non-integer value of "InstallTime"']

    def test_bad_seconds_since_last_crash(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.SecondsSinceLastCrash = "feed the goats"
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = DatesAndTimesRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        expected = datetime_from_isodate_string(raw_crash.submitted_timestamp)
        assert processed_crash.submitted_timestamp == expected
        assert processed_crash.date_processed == processed_crash.submitted_timestamp
        assert processed_crash.crash_time == 1336519554
        expected = datetime_from_isodate_string("2012-05-08 23:25:54+00:00")
        assert processed_crash.client_crash_date == expected
        assert processed_crash.install_age == 1079662
        assert processed_crash.uptime == 20116
        assert processed_crash.last_crash is None
        assert processor_meta.processor_notes == [
            'non-integer value of "SecondsSinceLastCrash"'
        ]


class TestJavaProcessRule(object):
    def test_everything_we_hoped_for(self):
        raw_crash = {
            "JavaStackTrace": (
                "Exception: some messge\n"
                "\tat org.File.function(File.java:100)\n"
                "\tCaused by: Exception: some other message\n"
                "\t\tat org.File.function(File.java:100)"
            )
        }
        raw_dumps = {}
        processed_crash = {}
        processor_meta = get_basic_processor_meta()

        rule = JavaProcessRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        # The entire JavaStackTrace blob
        assert processed_crash["java_stack_trace_raw"] == raw_crash["JavaStackTrace"]

        # Everything except the exception message and "Caused by" section
        # which can contain PII
        assert (
            processed_crash["java_stack_trace"]
            == "Exception\n\tat org.File.function(File.java:100)"
        )

    def test_malformed(self):
        raw_crash = {"JavaStackTrace": "junk\n\tat org.File.function\njunk"}

        raw_dumps = {}
        processed_crash = {}
        processor_meta = get_basic_processor_meta()

        rule = JavaProcessRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        # The entire JavaStackTrace blob
        assert processed_crash["java_stack_trace_raw"] == raw_crash["JavaStackTrace"]

        # The data is malformed, so this should just show "malformed"
        assert processed_crash["java_stack_trace"] == "malformed"

        # Make sure there's a note in the notes about it
        assert "malformed java stack trace" in processor_meta.processor_notes[0]


class TestMozCrashReasonRule(object):
    def test_no_mozcrashreason(self):
        raw_crash = {}
        raw_dumps = {}
        processed_crash = {}
        processor_meta = get_basic_processor_meta()

        rule = MozCrashReasonRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash == {}

    def test_good_mozcrashreason(self):
        raw_crash = {"MozCrashReason": "MOZ_CRASH(OOM)"}
        raw_dumps = {}
        processed_crash = {}
        processor_meta = get_basic_processor_meta()

        rule = MozCrashReasonRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash == {
            "moz_crash_reason_raw": "MOZ_CRASH(OOM)",
            "moz_crash_reason": "MOZ_CRASH(OOM)",
        }

    def test_bad_mozcrashreason(self):
        rule = MozCrashReasonRule()

        bad_reasons = [
            "byte index 21548 is not a char boundary",
            'Failed to load module "jar:file..."'
            "do not use eval with system privileges: jar:file...",
        ]
        for reason in bad_reasons:
            raw_crash = {"MozCrashReason": reason}
            raw_dumps = {}
            processed_crash = {}
            processor_meta = get_basic_processor_meta()

            rule.action(raw_crash, raw_dumps, processed_crash, processor_meta)
            assert processed_crash == {
                "moz_crash_reason_raw": reason,
                "moz_crash_reason": "sanitized--see moz_crash_reason_raw",
            }


class TestOutOfMemoryBinaryRule(object):
    def test_extract_memory_info(self):
        processor_meta = get_basic_processor_meta()

        with mock.patch(
            "socorro.processor.rules.mozilla.gzip.open"
        ) as mocked_gzip_open:
            ret = json.dumps({"mysterious": ["awesome", "memory"]})
            mocked_gzip_open.return_value = BytesIO(ret.encode("utf-8"))
            rule = OutOfMemoryBinaryRule()
            # Stomp on the value to make it easier to test with
            rule.MAX_SIZE_UNCOMPRESSED = 1024
            memory = rule._extract_memory_info(
                "a_pathname", processor_meta.processor_notes
            )
            mocked_gzip_open.assert_called_with("a_pathname", "rb")
            assert memory == {"mysterious": ["awesome", "memory"]}

    def test_extract_memory_info_too_big(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.JavaStackTrace = "this is a Java Stack trace"
        raw_dumps = {"memory_report": "a_pathname"}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        with mock.patch(
            "socorro.processor.rules.mozilla.gzip.open"
        ) as mocked_gzip_open:
            opened = mock.Mock()
            opened.read.return_value = json.dumps({"some": "notveryshortpieceofjson"})

            def gzip_open(filename, mode):
                assert mode == "rb"
                return opened

            mocked_gzip_open.side_effect = gzip_open
            rule = OutOfMemoryBinaryRule()

            # Stomp on the value to make it easier to test with
            rule.MAX_SIZE_UNCOMPRESSED = 5

            memory = rule._extract_memory_info(
                "a_pathname", processor_meta.processor_notes
            )
            expected_error_message = (
                "Uncompressed memory info too large %d (max: %s)"
                % (35, rule.MAX_SIZE_UNCOMPRESSED)
            )
            assert memory == {"ERROR": expected_error_message}
            assert processor_meta.processor_notes == [expected_error_message]
            opened.close.assert_called_with()

            rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
            assert "memory_report" not in processed_crash
            assert processed_crash.memory_report_error == expected_error_message

    def test_extract_memory_info_with_trouble(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.JavaStackTrace = "this is a Java Stack trace"
        raw_dumps = {"memory_report": "a_pathname"}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        with mock.patch(
            "socorro.processor.rules.mozilla.gzip.open"
        ) as mocked_gzip_open:
            mocked_gzip_open.side_effect = IOError
            rule = OutOfMemoryBinaryRule()

            memory = rule._extract_memory_info(
                "a_pathname", processor_meta.processor_notes
            )
            assert memory["ERROR"] == "error in gzip for a_pathname: OSError()"
            assert processor_meta.processor_notes == [
                "error in gzip for a_pathname: OSError()"
            ]

            rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
            assert "memory_report" not in processed_crash
            assert (
                processed_crash.memory_report_error
                == "error in gzip for a_pathname: OSError()"
            )

    def test_extract_memory_info_with_json_trouble(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.JavaStackTrace = "this is a Java Stack trace"
        raw_dumps = {"memory_report": "a_pathname"}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        with mock.patch(
            "socorro.processor.rules.mozilla.gzip.open"
        ) as mocked_gzip_open:
            with mock.patch(
                "socorro.processor.rules.mozilla.json.loads"
            ) as mocked_json_loads:
                mocked_json_loads.side_effect = ValueError

                rule = OutOfMemoryBinaryRule()
                memory = rule._extract_memory_info(
                    "a_pathname", processor_meta.processor_notes
                )
                mocked_gzip_open.assert_called_with("a_pathname", "rb")
                assert memory == {"ERROR": "error in json for a_pathname: ValueError()"}
                expected = ["error in json for a_pathname: ValueError()"]
                assert processor_meta.processor_notes == expected
                mocked_gzip_open.return_value.close.assert_called_with()

                rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
                assert "memory_report" not in processed_crash
                expected = "error in json for a_pathname: ValueError()"
                assert processed_crash.memory_report_error == expected

    def test_everything_we_hoped_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.JavaStackTrace = "this is a Java Stack trace"
        raw_dumps = {"memory_report": "a_pathname"}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        class MyOutOfMemoryBinaryRule(OutOfMemoryBinaryRule):
            @staticmethod
            def _extract_memory_info(dump_pathname, processor_notes):
                assert dump_pathname == raw_dumps["memory_report"]
                assert processor_notes == []
                return "mysterious-awesome-memory"

        with mock.patch("socorro.processor.rules.mozilla.temp_file_context"):
            rule = MyOutOfMemoryBinaryRule()
            rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
            assert processed_crash.memory_report == "mysterious-awesome-memory"

    def test_this_is_not_the_crash_you_are_looking_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.JavaStackTrace = "this is a Java Stack trace"
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = OutOfMemoryBinaryRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert "memory_report" not in processed_crash


class TestProductRewriteRule(object):
    def test_product_map_rewrite(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash["ProductName"] = "Fennec"
        raw_crash["ProductID"] = "{aa3c5121-dab2-40e2-81ca-7ea25febc110}"
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = ProductRewrite()
        rule.act(raw_crash, {}, processed_crash, processor_meta)

        assert raw_crash.ProductName == "FennecAndroid"
        assert raw_crash.OriginalProductName == "Fennec"

        # processed_crash should be unchanged
        assert processed_crash == DotDict()
        assert processor_meta.processor_notes == [
            "Rewriting ProductName from 'Fennec' to 'FennecAndroid'"
        ]


class TestESRVersionRewrite(object):
    def test_everything_we_hoped_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.ReleaseChannel = "esr"
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = ESRVersionRewrite()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert raw_crash.Version == "12.0esr"

        # processed_crash should be unchanged
        assert processed_crash == DotDict()

    def test_this_is_not_the_crash_you_are_looking_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.ReleaseChannel = "not_esr"
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = ESRVersionRewrite()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert raw_crash.Version == "12.0"

        # processed_crash should be unchanged
        assert processed_crash == DotDict()

    def test_this_is_really_broken(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.ReleaseChannel = "esr"
        del raw_crash.Version
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = ESRVersionRewrite()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert "Version" not in raw_crash
        assert processor_meta.processor_notes == [
            '"Version" missing from esr release raw_crash'
        ]

        # processed_crash should be unchanged
        assert processed_crash == DotDict()


class TestPluginContentURL(object):
    def test_everything_we_hoped_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.PluginContentURL = "http://mozilla.com"
        raw_crash.URL = "http://google.com"
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = PluginContentURL()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert raw_crash.URL == "http://mozilla.com"

        # processed_crash should be unchanged
        assert processed_crash == DotDict()

    def test_this_is_not_the_crash_you_are_looking_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.URL = "http://google.com"
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = PluginContentURL()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert raw_crash.URL == "http://google.com"

        # processed_crash should be unchanged
        assert processed_crash == DotDict()


class TestPluginUserComment(object):
    def test_everything_we_hoped_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.PluginUserComment = "I hate it when this happens"
        raw_crash.Comments = "I wrote something here, too"
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = PluginUserComment()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert raw_crash.Comments == "I hate it when this happens"

        # processed_crash should be unchanged
        assert processed_crash == DotDict()

    def test_this_is_not_the_crash_you_are_looking_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_crash.Comments = "I wrote something here"
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = PluginUserComment()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert raw_crash.Comments == "I wrote something here"

        # processed_crash should be unchanged
        assert processed_crash == DotDict()


class TestExploitablityRule(object):
    def test_everything_we_hoped_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = copy.deepcopy(canonical_processed_crash)
        processor_meta = get_basic_processor_meta()

        rule = ExploitablityRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.exploitability == "high"

        # raw_crash should be unchanged
        assert raw_crash == canonical_standard_raw_crash

    def test_this_is_not_the_crash_you_are_looking_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = ExploitablityRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.exploitability == "unknown"

        # raw_crash should be unchanged
        assert raw_crash == canonical_standard_raw_crash


class TestFlashVersionRule(object):
    def test_get_flash_version(self):
        rule = FlashVersionRule()

        assert (
            rule._get_flash_version(filename="NPSWF32_1_2_3.dll", version="1.2.3")
            == "1.2.3"
        )
        assert rule._get_flash_version(filename="NPSWF32_1_2_3.dll") == "1.2.3"

        data = rule._get_flash_version(
            filename="FlashPlayerPlugin_2_3_4.exe", version="2.3.4"
        )
        assert data == "2.3.4"
        assert (
            rule._get_flash_version(filename="FlashPlayerPlugin_2_3_4.exe") == "2.3.4"
        )

        data = rule._get_flash_version(
            filename="libflashplayer3.4.5.so", version="3.4.5"
        )
        assert data == "3.4.5"
        assert rule._get_flash_version(filename="libflashplayer3.4.5.so") == "3.4.5"

        assert (
            rule._get_flash_version(filename="Flash Player-", version="4.5.6")
            == "4.5.6"
        )
        assert rule._get_flash_version(filename="Flash Player-.4.5.6") == ".4.5.6"

        ret = rule._get_flash_version(
            filename="Flash Player-",
            version=".4.5.6",
            debug_id="83CF4DC03621B778E931FC713889E8F10",
        )
        assert ret == ".4.5.6"
        ret = rule._get_flash_version(
            filename="Flash Player-.4.5.6", debug_id="83CF4DC03621B778E931FC713889E8F10"
        )
        assert ret == ".4.5.6"
        ret = rule._get_flash_version(
            filename="Flash Player-", debug_id="83CF4DC03621B778E931FC713889E8F10"
        )
        assert ret == "9.0.16.0"

    def test_everything_we_hoped_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = copy.deepcopy(canonical_processed_crash)
        processor_meta = get_basic_processor_meta()

        rule = FlashVersionRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.flash_version == "9.1.3.08"

        # raw_crash should be unchanged
        assert raw_crash == canonical_standard_raw_crash


class TestTopMostFilesRule(object):
    def test_everything_we_hoped_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processed_crash.json_dump = {
            "crash_info": {"crashing_thread": 0},
            "crashing_thread": {
                "frames": [
                    {"source": "not-the-right-file.dll"},
                    {"file": "not-the-right-file.cpp"},
                ]
            },
            "threads": [{"frames": [{"source": "dwight.dll"}, {"file": "wilma.cpp"}]}],
        }

        processor_meta = get_basic_processor_meta()

        rule = TopMostFilesRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.topmost_filenames == "wilma.cpp"

        # raw_crash should be unchanged
        assert raw_crash == canonical_standard_raw_crash

    def test_missing_key(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        expected_raw_crash = copy.deepcopy(raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = TopMostFilesRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.topmost_filenames is None

        # raw_crash should be unchanged
        assert raw_crash == expected_raw_crash

    def test_missing_key_2(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processed_crash.json_dump = {
            "crashing_thread": {
                "frames": [{"filename": "dwight.dll"}, {"filename": "wilma.cpp"}]
            }
        }

        processor_meta = get_basic_processor_meta()

        rule = TopMostFilesRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash.topmost_filenames is None

        # raw_crash should be unchanged
        assert raw_crash == canonical_standard_raw_crash


class TestModulesInStackRule(object):
    def test_basic(self):
        raw_crash = {}
        raw_dumps = {}
        processed_crash = DotDict(
            {
                "json_dump": {
                    "modules": [
                        {"filename": "libxul.dll", "debug_id": "ABCDEF"},
                        {"filename": "libnss3.dll", "debug_id": "012345"},
                        {"filename": "mozglue.dll", "debug_id": "ABC345"},
                    ],
                    "crash_info": {"crashing_thread": 0},
                    "threads": [
                        {
                            "frames": [
                                {"module": "libxul.dll"},
                                {"module": "mozglue.dll"},
                            ]
                        }
                    ],
                }
            }
        )

        processor_meta = get_basic_processor_meta()

        rule = ModulesInStackRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert (
            processed_crash["modules_in_stack"]
            == "libxul.dll/ABCDEF;mozglue.dll/ABC345"
        )

    @pytest.mark.parametrize(
        "processed_crash",
        [
            {},
            {"json_dump": {}},
            {"json_dump": {"crash_info": {}}},
            {"json_dump": {"crash_info": {"crashing_thread": 0}}},
            {"json_dump": {"crash_info": {"crashing_thread": 10}, "threads": []}},
            {"json_dump": {"crash_info": {"crashing_thread": 0}, "threads": [{}]}},
            {
                "json_dump": {
                    "crash_info": {"crashing_thread": 0},
                    "threads": [{"frames": []}],
                }
            },
            {
                "modules": [],
                "json_dump": {
                    "crash_info": {"crashing_thread": 0},
                    "threads": [{"frames": [{"module": "libxul.so"}]}],
                },
            },
        ],
    )
    def test_missing_things(self, processed_crash):
        processor_meta = get_basic_processor_meta()
        rule = ModulesInStackRule()

        rule.act({}, {}, processed_crash, processor_meta)
        assert "modules_in_stack" not in processed_crash

    @pytest.mark.parametrize(
        "item, expected",
        [
            ({}, "/"),
            ({"filename": "libxul.so"}, "libxul.so/"),
            ({"debug_id": "ABCDEF"}, "/ABCDEF"),
            ({"filename": "libxul.so", "debug_id": "ABCDEF"}, "libxul.so/ABCDEF"),
            (
                {"filename": "libxul_2.dll", "debug_id": "ABCDEF0123456789"},
                "libxul_2.dll/ABCDEF0123456789",
            ),
            ({"filename": " l\nib (foo)", "debug_id": "this is bad"}, "libfoo/bad"),
        ],
    )
    def test_format_module(self, item, expected):
        rule = ModulesInStackRule()
        assert rule.format_module(item) == expected


class TestBetaVersionRule(object):
    API_URL = "http://example.com/api/VersionString"

    def build_rule(self):
        return BetaVersionRule(version_string_api=self.API_URL)

    def test_beta_channel_known_version(self):
        # Beta channel with known version gets converted correctly
        raw_crash = {}
        raw_dumps = {}
        processed_crash = {
            "product": "Firefox",
            "release_channel": "beta",
            "version": "3.0",
            "build": "20001001101010",
        }
        processor_meta = get_basic_processor_meta()

        rule = self.build_rule()
        with requests_mock.Mocker() as req_mock:
            req_mock.get(
                self.API_URL + "?product=Firefox&channel=beta&build_id=20001001101010",
                json={"hits": [{"version_string": "3.0b1"}], "total": 1},
            )
            rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash["version"] == "3.0b1"
        assert processor_meta.processor_notes == []

    def test_release_channel(self):
        """Release channel doesn't trigger rule"""
        raw_crash = {}
        raw_dumps = {}
        processed_crash = {
            "product": "Firefox",
            "version": "2.0",
            "release_channel": "release",
            "build": "20000801101010",
        }
        processor_meta = get_basic_processor_meta()

        rule = self.build_rule()
        with requests_mock.Mocker():
            rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash["version"] == "2.0"
        assert len(processor_meta.processor_notes) == 0

    def test_nightly_channel(self):
        """Nightly channel doesn't trigger rule"""
        raw_crash = {}
        raw_dumps = {}
        processed_crash = {
            "product": "Firefox",
            "version": "5.0a1",
            "release_channel": "nightly",
            "build": "20000105101010",
        }
        processor_meta = get_basic_processor_meta()

        rule = self.build_rule()
        with requests_mock.Mocker():
            rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash["version"] == "5.0a1"
        assert processor_meta.processor_notes == []

    def test_bad_buildid(self):
        """Invalid buildids don't cause errors"""
        raw_crash = {}
        raw_dumps = {}
        processed_crash = {
            "product": "Firefox",
            "release_channel": "beta",
            "version": "5.0",
            "build": '2",381,,"',
        }
        processor_meta = get_basic_processor_meta()

        rule = self.build_rule()
        with requests_mock.Mocker() as req_mock:
            # NOTE(willkg): Is it possible to validate the buildid and
            # reject it without doing an HTTP round-trip?
            req_mock.get(
                self.API_URL + '?product=Firefox&channel=beta&build_id=2",381,,"',
                json={"hits": [], "total": 0},
            )
            rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash["version"] == "5.0b0"
        assert processor_meta.processor_notes == [
            "release channel is beta but no version data was found - "
            'added "b0" suffix to version number'
        ]

    def test_beta_channel_unknown_version(self):
        """Beta crash that Buildhub doesn't know about gets b0"""
        raw_crash = {}
        raw_dumps = {}
        processed_crash = {
            "product": "Firefox",
            "version": "3.0.1",
            "release_channel": "beta",
            "build": "220000101101011",
        }
        processor_meta = get_basic_processor_meta()

        rule = self.build_rule()
        with requests_mock.Mocker() as req_mock:
            req_mock.get(
                self.API_URL + "?product=Firefox&channel=beta&build_id=220000101101011",
                json={"hits": [], "total": 0},
            )
            rule.action(raw_crash, raw_dumps, processed_crash, processor_meta)

        assert processed_crash["version"] == "3.0.1b0"
        assert processor_meta.processor_notes == [
            "release channel is beta but no version data was found - "
            'added "b0" suffix to version number'
        ]

    def test_aurora_channel(self):
        """Test aurora channel lookup"""
        raw_crash = {}
        raw_dumps = {}
        processed_crash = {
            "product": "Firefox",
            "version": "3.0",
            "release_channel": "aurora",
            "build": "20001001101010",
        }
        processor_meta = get_basic_processor_meta()

        rule = self.build_rule()
        with requests_mock.Mocker() as req_mock:
            req_mock.get(
                self.API_URL
                + "?product=Firefox&channel=aurora&build_id=20001001101010",
                json={"hits": [{"version_string": "3.0b1"}], "total": 0},
            )
            rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash["version"] == "3.0b1"
        assert processor_meta.processor_notes == []


class TestOsPrettyName:
    @pytest.mark.parametrize(
        "os_name, os_version, expected",
        [
            # Known windows version
            ("Windows NT", "10.0.11.7600", "Windows 10"),
            # Unknown windows version
            ("Windows NT", "15.2", "Windows Unknown"),
            # A valid version of Mac OS X
            ("Mac OS X", "10.18.324", "OS X 10.18"),
            # An invalid version of Mac OS X
            ("Mac OS X", "12.1", "OS X Unknown"),
            # Generic Linux
            ("Linux", "0.0.12.13", "Linux"),
        ],
    )
    def test_everything_we_hoped_for(self, os_name, os_version, expected):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processor_meta = get_basic_processor_meta()

        rule = OSPrettyVersionRule()

        processed_crash = {"os_name": os_name, "os_version": os_version}

        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash["os_pretty_version"] == expected

    def test_lsb_release(self):
        # If this is Linux and there's data in json_dump.lsb_release.description,
        # use that
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processor_meta = get_basic_processor_meta()

        rule = OSPrettyVersionRule()

        processed_crash = {
            "os_name": "Linux",
            "os_version": "0.0.0 Linux etc",
            "json_dump": {"lsb_release": {"description": "Ubuntu 18.04 LTS"}},
        }

        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash["os_pretty_version"] == "Ubuntu 18.04 LTS"

    @pytest.mark.parametrize(
        "os_name, os_version, expected",
        [
            ("Linux", None, "Linux"),
            (None, None, None),
            ("Windows NT", "NaN", "Windows NT"),
        ],
    )
    def test_junk_data(self, os_name, os_version, expected):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processor_meta = get_basic_processor_meta()

        rule = OSPrettyVersionRule()

        # Now try some bogus processed_crashes.
        processed_crash = {}
        if os_name is not None:
            processed_crash["os_name"] = os_name
        if os_version is not None:
            processed_crash["os_version"] = os_version

        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash["os_pretty_version"] == expected

    def test_dotdict(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processor_meta = get_basic_processor_meta()

        rule = OSPrettyVersionRule()

        processed_crash = DotDict(
            {"os_name": "Windows NT", "os_version": "10.0.11.7600"}
        )
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash["os_pretty_version"] == "Windows 10"

    def test_none(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processor_meta = get_basic_processor_meta()

        rule = OSPrettyVersionRule()

        processed_crash = {"os_name": None, "os_version": None}
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)
        assert processed_crash["os_pretty_version"] is None


class TestThemePrettyNameRule(object):
    def test_everything_we_hoped_for(self):
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        raw_dumps = {}
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()
        processed_crash.addons = [
            "adblockpopups@jessehakanen.net:0.3",
            "dmpluginff@westbyte.com:1,4.8",
            "firebug@software.joehewitt.com:1.9.1",
            "killjasmin@pierros14.com:2.4",
            "support@surfanonymous-free.com:1.0",
            "uploader@adblockfilters.mozdev.org:2.1",
            "{a0d7ccb3-214d-498b-b4aa-0e8fda9a7bf7}:20111107",
            "{d10d0bf8-f5b5-c8b4-a8b2-2b9879e08c5d}:2.0.3",
            "anttoolbar@ant.com:2.4.6.4",
            "{972ce4c6-7e08-4474-a285-3208198ce6fd}:12.0",
            "elemhidehelper@adblockplus.org:1.2.1",
        ]

        rule = ThemePrettyNameRule()
        rule.act(raw_crash, raw_dumps, processed_crash, processor_meta)

        # the raw crash & raw_dumps should not have changed
        assert dotdict_to_dict(raw_crash) == dotdict_to_dict(
            canonical_standard_raw_crash
        )
        assert raw_dumps == {}

        expected_addon_list = [
            "adblockpopups@jessehakanen.net:0.3",
            "dmpluginff@westbyte.com:1,4.8",
            "firebug@software.joehewitt.com:1.9.1",
            "killjasmin@pierros14.com:2.4",
            "support@surfanonymous-free.com:1.0",
            "uploader@adblockfilters.mozdev.org:2.1",
            "{a0d7ccb3-214d-498b-b4aa-0e8fda9a7bf7}:20111107",
            "{d10d0bf8-f5b5-c8b4-a8b2-2b9879e08c5d}:2.0.3",
            "anttoolbar@ant.com:2.4.6.4",
            "{972ce4c6-7e08-4474-a285-3208198ce6fd} (default theme):12.0",
            "elemhidehelper@adblockplus.org:1.2.1",
        ]
        assert processed_crash.addons == expected_addon_list

    def test_missing_key(self):
        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        rule = ThemePrettyNameRule()

        # Test with missing key.
        res = rule.predicate({}, {}, processed_crash, processor_meta)
        assert res is False

        # Test with empty list.
        processed_crash.addons = []
        res = rule.predicate({}, {}, processed_crash, processor_meta)
        assert res is False

        # Test with key missing from list.
        processed_crash.addons = [
            "adblockpopups@jessehakanen.net:0.3",
            "dmpluginff@westbyte.com:1,4.8",
        ]
        res = rule.predicate({}, {}, processed_crash, processor_meta)
        assert res is False

    def test_with_malformed_addons_field(self):
        rule = ThemePrettyNameRule()

        processed_crash = DotDict()
        processor_meta = get_basic_processor_meta()

        processed_crash.addons = [
            "addon_with_no_version",
            "{972ce4c6-7e08-4474-a285-3208198ce6fd}",
            "elemhidehelper@adblockplus.org:1.2.1",
        ]
        rule.act({}, {}, processed_crash, processor_meta)

        expected_addon_list = [
            "addon_with_no_version",
            "{972ce4c6-7e08-4474-a285-3208198ce6fd} (default theme)",
            "elemhidehelper@adblockplus.org:1.2.1",
        ]
        assert processed_crash.addons == expected_addon_list


class TestSignatureGeneratorRule:
    def test_signature(self):
        rule = SignatureGeneratorRule()
        raw_crash = copy.deepcopy(canonical_standard_raw_crash)
        processed_crash = DotDict(
            {
                "json_dump": {
                    "crash_info": {"crashing_thread": 0},
                    "crashing_thread": 0,
                    "threads": [
                        {
                            "frames": [
                                {
                                    "frame": 0,
                                    "function": "Alpha<Bravo<Charlie>, Delta>::Echo<Foxtrot>",
                                    "file": "foo.cpp",
                                },
                                {
                                    "frame": 1,
                                    "function": "std::something::something",
                                    "file": "foo.rs",
                                },
                            ]
                        }
                    ],
                }
            }
        )
        processor_meta = get_basic_processor_meta()

        rule.action(raw_crash, {}, processed_crash, processor_meta)

        assert processed_crash["signature"] == "Alpha<T>::Echo<T>"
        assert (
            processed_crash["proto_signature"]
            == "Alpha<T>::Echo<T> | std::something::something"
        )
        assert processor_meta["processor_notes"] == []

    def test_empty_raw_and_processed_crashes(self):
        rule = SignatureGeneratorRule()
        raw_crash = {}
        processed_crash = {}
        processor_meta = get_basic_processor_meta()

        rule.action(raw_crash, {}, processed_crash, processor_meta)

        # NOTE(willkg): This is what the current pipeline yields. If any of
        # those parts change, this might change, too. The point of this test is
        # that we can pass in empty dicts and the SignatureGeneratorRule and
        # the generation rules in the default pipeline don't fall over.
        assert processed_crash["signature"] == "EMPTY: no crashing thread identified"
        assert "proto_signature" not in processed_crash
        assert processor_meta["processor_notes"] == [
            "SignatureGenerationRule: CSignatureTool: No signature could be created because we do not know which thread crashed"  # noqa
        ]

    @mock.patch("socorro.lib.sentry_client.get_hub")
    @mock.patch("socorro.lib.sentry_client.is_enabled", return_value=True)
    def test_rule_fail_and_capture_error(self, client_enabled, mock_get_hub):
        exc_value = Exception("Cough")

        class BadRule(object):
            def predicate(self, raw_crash, processed_crash):
                raise exc_value

        rule = SignatureGeneratorRule()

        # Override the regular SigntureGenerator with one with a BadRule
        # in the pipeline
        rule.generator = SignatureGenerator(
            pipeline=[BadRule()], error_handler=rule._error_handler
        )

        raw_crash = {}
        processed_crash = {}
        processor_meta = get_basic_processor_meta()

        rule.action(raw_crash, {}, processed_crash, processor_meta)

        # NOTE(willkg): The signature is an empty string because there are no
        # working rules that add anything to it.
        assert processed_crash["signature"] == ""
        assert "proto_signature" not in processed_crash
        assert processor_meta["processor_notes"] == ["BadRule: Rule failed: Cough"]

        # Make sure captureExeption was called with the right args.
        assert mock_get_hub.return_value.capture_exception.call_args_list == [
            mock.call(error=(Exception, exc_value, WHATEVER))
        ]


class TestPHCRule:
    def test_predicate(self):
        rule = PHCRule()
        assert rule.predicate({}, (), {}, {}) is False

    @pytest.mark.parametrize(
        "base_address, expected",
        [(None, None), ("", None), ("foo", None), ("10", "0xa"), ("100", "0x64")],
    )
    def test_phc_base_address(self, base_address, expected):
        raw_crash = {"PHCKind": "FreedPage"}
        if base_address is not None:
            raw_crash["PHCBaseAddress"] = base_address

        rule = PHCRule()
        processed_crash = {}
        rule.action(raw_crash, (), processed_crash, {})
        if expected is None:
            assert "phc_base_address" not in processed_crash
        else:
            assert processed_crash["phc_base_address"] == expected

    @pytest.mark.parametrize(
        "usable_size, expected", [(None, None), ("", None), ("foo", None), ("10", 10)]
    )
    def test_phc_usable_size(self, usable_size, expected):
        raw_crash = {"PHCKind": "FreedPage"}
        if usable_size is not None:
            raw_crash["PHCUsableSize"] = usable_size

        rule = PHCRule()
        processed_crash = {}
        rule.action(raw_crash, (), processed_crash, {})
        if expected is None:
            assert "phc_usable_size" not in processed_crash
        else:
            assert processed_crash["phc_usable_size"] == expected

    def test_copied_values(self):
        raw_crash = {
            "PHCKind": "FreedPage",
            "PHCUsableSize": "8",
            "PHCBaseAddress": "10",
            "PHCAllocStack": "100,200",
            "PHCFreeStack": "300,400",
        }
        rule = PHCRule()
        processed_crash = {}
        rule.action(raw_crash, (), processed_crash, {})
        assert processed_crash == {
            "phc_kind": "FreedPage",
            "phc_usable_size": 8,
            "phc_base_address": "0xa",
            "phc_alloc_stack": "100,200",
            "phc_free_stack": "300,400",
        }
