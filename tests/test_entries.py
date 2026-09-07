import os
import tempfile
import unittest
import uuid

import quasilattice


class TestEntries(unittest.TestCase):
    def test_write(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            quasilattice.init(
                os.path.join(tmp_dir, "config.toml"),
                3,
                None,
                False,
                {
                    "quasilattice": {"archive_mode": True},
                    "logging": {"log_to_file": False},
                },
            )
            quasilattice.write_entry(
                {"entry_property": "entry_property_value"},
                "non-existent user",
                "non-existent api_key_id",
            )
            self.assertEqual(
                quasilattice.entries(),
                {
                    "83d2c85022095f67e758f76d3942b74acd84e1ac29109a28db587bd934eddd2b": {
                        "entry_property": "entry_property_value"
                    }
                },
            )

            test_dict2_uuid = uuid.UUID("72d67dd2-270b-4b56-b083-0aa37f4fa27b")
            quasilattice.write_entry(
                {
                    "uuid": str(test_dict2_uuid),
                    "entry_property": "entry_property_value",
                },
                "non-existent user",
                "non-existent api_key_id",
            )
            self.assertEqual(
                len(quasilattice.entries().keys()),
                3,
            )

    def test_read(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            quasilattice.init(
                os.path.join(tmp_dir, "config.toml"),
                3,
                None,
                False,
                {
                    "quasilattice": {"archive_mode": True},
                    "logging": {"log_to_file": False},
                },
            )

            test_dict1 = {"entry_property": "entry_property_value"}
            test_dict1_hash = (
                "83d2c85022095f67e758f76d3942b74acd84e1ac29109a28db587bd934eddd2b"
            )
            quasilattice.write_entry(
                test_dict1,
                "non-existent user",
                "non-existent api_key_id",
            )

            # test entry() by hash (str and bytes)
            self.assertEqual(
                quasilattice.entry(test_dict1_hash),
                test_dict1,
            )
            self.assertEqual(
                quasilattice.entry(bytes.fromhex(test_dict1_hash)),
                test_dict1,
            )

            # test entries() with one entry present
            self.assertEqual(
                quasilattice.entries(),
                {test_dict1_hash: test_dict1},
            )

            # write an entry with a uuid
            test_dict2_uuid = uuid.UUID("72d67dd2-270b-4b56-b083-0aa37f4fa27b")
            test_dict2 = {
                "uuid": str(test_dict2_uuid),
                "string": "test string",
                "number": 5895391.1324251,
                "bool": True,
                "null": None,
            }
            test_dict2_hash = (
                "03f4ad4ef27a169fcb37aaa20806e540546e95ad708d474db97e9d56a38cabf4"
            )
            quasilattice.write_entry(
                test_dict2,
                "non-existent user",
                "non-existent api_key_id",
            )

            # test entry() by uuid (str and bytes)
            self.assertEqual(
                quasilattice.entry(str(test_dict2_uuid)),
                test_dict2,
            )
            self.assertEqual(
                quasilattice.entry(test_dict2_uuid.bytes),
                test_dict2,
            )

            # test entry_hash() (str and bytes)
            self.assertEqual(
                quasilattice.entry_hash(str(test_dict2_uuid)),
                bytes.fromhex(test_dict2_hash),
            )
            self.assertEqual(
                quasilattice.entry_hash(test_dict2_uuid.bytes),
                bytes.fromhex(test_dict2_hash),
            )

            # test entries() by list[hash and uuid]
            self.assertEqual(
                quasilattice.entries(
                    [
                        test_dict1_hash,
                        str(test_dict2_uuid),
                    ]
                ),
                {
                    test_dict1_hash: test_dict1,
                    str(test_dict2_uuid): test_dict2,
                },
            )

            # write entry version 2
            test_dict2_v2 = {
                "uuid": str(test_dict2_uuid),
                "string": "test string MODIFIED",
                "number": 5895391.1324251,
                "bool": True,
                "null": None,
            }
            test_dict2_v2_hash = (
                "20e3775a11efe47f455f302682a1896ab8907ea97e343217f03c856a189c637f"
            )
            quasilattice.write_entry(
                test_dict2_v2,
                "non-existent user",
                "non-existent api_key_id",
            )

            # test entry_hash() updated with v2
            self.assertEqual(
                quasilattice.entry_hash(str(test_dict2_uuid)).hex(), test_dict2_v2_hash
            )

            # test entry_version_hashes()
            self.assertEqual(
                quasilattice.entry_version_hashes(str(test_dict2_uuid)),
                [bytes.fromhex(test_dict2_v2_hash), bytes.fromhex(test_dict2_hash)],
            )

            # test entry_versions()
            self.assertEqual(
                quasilattice.entry_versions(str(test_dict2_uuid)),
                {test_dict2_v2_hash: test_dict2_v2, test_dict2_hash: test_dict2},
            )

            # test entries_by_filter
            self.assertEqual(
                quasilattice.entries_by_filter("number"),
                {str(test_dict2_uuid): test_dict2_v2},
            )
            self.assertEqual(
                quasilattice.entries_by_filter("number__gt=500"),
                {str(test_dict2_uuid): test_dict2_v2},
            )
            self.assertEqual(quasilattice.entries_by_filter("number__lt=500"), {})
            self.assertEqual(
                quasilattice.entries_by_filter("number__lte=5895391.1324251"),
                {str(test_dict2_uuid): test_dict2_v2},
            )
            self.assertEqual(
                quasilattice.entries_by_filter(
                    "number__lte=5895391.1324251", include_outdated=True
                ),
                {test_dict2_v2_hash: test_dict2_v2, test_dict2_hash: test_dict2},
            )

    def test_delete(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            quasilattice.init(
                os.path.join(tmp_dir, "config.toml"),
                3,
                None,
                False,
                {
                    "quasilattice": {"archive_mode": True},
                    "logging": {"log_to_file": False},
                },
            )

            test_dict1 = {"entry_property": "entry_property_value"}
            test_dict1_hash = "83d2c85022095f67e758f76d3942b74acd84e1ac29109a28db587bd934eddd2b"
            quasilattice.write_entry(
                test_dict1,
                "non-existent user",
                "non-existent api_key_id",
            )

            # write an entry with a uuid
            test_dict2_uuid = uuid.UUID("72d67dd2-270b-4b56-b083-0aa37f4fa27b")
            test_dict2 = {
                "uuid": str(test_dict2_uuid),
                "string": "test string",
                "number": 5895391.1324251,
                "bool": True,
                "null": None,
            }
            test_dict2_hash = "03f4ad4ef27a169fcb37aaa20806e540546e95ad708d474db97e9d56a38cabf4"
            quasilattice.write_entry(
                test_dict2,
                "non-existent user",
                "non-existent api_key_id",
            )

            # write entry version 2
            test_dict2_v2 = {
                "uuid": str(test_dict2_uuid),
                "string": "test string MODIFIED",
                "number": 5895391.1324251,
                "bool": True,
                "null": None,
            }
            test_dict2_v2_hash = (
                "20e3775a11efe47f455f302682a1896ab8907ea97e343217f03c856a189c637f"
            )
            quasilattice.write_entry(
                test_dict2_v2,
                "non-existent user",
                "non-existent api_key_id",
            )

            self.assertEqual(
                quasilattice.entries(),
                {
                    test_dict1_hash: test_dict1,
                    test_dict2_hash: test_dict2,
                    test_dict2_v2_hash: test_dict2_v2,
                    str(test_dict2_uuid): test_dict2_v2,
                },
            )

            # test delete()
            quasilattice.delete_entry(test_dict2_v2_hash)

            self.assertEqual(
                quasilattice.entries(),
                {
                    test_dict1_hash: test_dict1,
                    test_dict2_hash: test_dict2,
                    str(test_dict2_uuid): test_dict2,
                },
            )

            # test undelete()
            quasilattice.undelete_entry(test_dict2_v2_hash)

            self.assertEqual(
                quasilattice.entries(),
                {
                    test_dict1_hash: test_dict1,
                    test_dict2_v2_hash: test_dict2_v2,
                    test_dict2_hash: test_dict2,
                    str(test_dict2_uuid): test_dict2_v2,
                },
            )

            # test delete() by uuid
            quasilattice.delete_entry(str(test_dict2_uuid))

            self.assertEqual(
                quasilattice.entries(),
                {
                    test_dict1_hash: test_dict1,
                },
            )
