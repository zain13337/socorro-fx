# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

from glom import glom
import markus

from socorro.processor.rules.base import Rule


METRICS = markus.get_metrics("processor")


class DeNullRule(Rule):
    """Removes nulls from keys and values

    Sometimes crash reports come in with junk data. This removes the egregious
    junk that causes downstream processing and storage problems.

    """

    def de_null(self, s):
        """Remove nulls from bytes and str values

        :arg str/bytes value: The str or bytes to remove nulls from

        :returns: str or bytes without nulls

        """
        if isinstance(s, bytes) and b"\0" in s:
            return s.replace(b"\0", b"")

        if isinstance(s, str) and "\0" in s:
            return s.replace("\0", "")

        # If it's not a bytes or a str, it's something else and we should
        # return it as is
        return s

    def action(self, raw_crash, raw_dumps, processed_crash, processor_meta):
        had_nulls = False

        # Go through the raw crash and de-null keys and values
        for key, val in list(raw_crash.items()):
            new_key = self.de_null(key)
            if key != new_key:
                had_nulls = True
                del raw_crash[key]

            new_val = self.de_null(val)
            if val != new_val:
                had_nulls = True
                raw_crash[new_key] = new_val

        if had_nulls:
            METRICS.incr("denullrule.has_nulls")


class DeNoneRule(Rule):
    """Removes keys that have None values

    Sometimes crash reports can have None values. That's unhelpful and usually
    a bug in the crash reporter. This removes keys have None values.

    """

    def action(self, raw_crash, raw_dumps, processed_crash, processor_meta):
        had_nones = False

        # Remove keys that have None values
        for key, val in list(raw_crash.items()):
            if val is None:
                had_nones = True
                del raw_crash[key]

        if had_nones:
            METRICS.incr("denonerule.had_nones")


class IdentifierRule(Rule):
    def action(self, raw_crash, raw_dumps, processed_crash, processor_meta):
        if "uuid" in raw_crash:
            processed_crash["crash_id"] = raw_crash["uuid"]
            processed_crash["uuid"] = raw_crash["uuid"]


class CPUInfoRule(Rule):
    def action(self, raw_crash, raw_dumps, processed_crash, processor_meta):
        # This is the CPU that the product was built for
        processed_crash["cpu_arch"] = glom(
            processed_crash, "json_dump.system_info.cpu_arch", default=""
        )

        # This is the CPU info of the machine the product was running on
        processed_crash["cpu_info"] = glom(
            processed_crash, "json_dump.system_info.cpu_info", default=""
        )
        processed_crash["cpu_count"] = glom(
            processed_crash, "json_dump.system_info.cpu_count", default=0
        )


class OSInfoRule(Rule):
    def action(self, raw_crash, raw_dumps, processed_crash, processor_meta):
        os_name = glom(
            processed_crash, "json_dump.system_info.os", default="Unknown"
        ).strip()
        processed_crash["os_name"] = os_name

        os_ver = glom(
            processed_crash, "json_dump.system_info.os_ver", default=""
        ).strip()
        processed_crash["os_version"] = os_ver
