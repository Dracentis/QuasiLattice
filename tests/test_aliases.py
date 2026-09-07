import os
import tempfile
import unittest
import uuid

import quasilattice


def setup_simple_test_env(tmp_dir):
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
    return (
        test_dict1_hash,
        test_dict1,
        test_dict2_uuid,
        test_dict2_hash,
        test_dict2,
        test_dict2_v2_hash,
        test_dict2_v2,
    )


class TestAliases(unittest.TestCase):
    def test_add_alias(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            (
                test_dict1_hash,
                test_dict1,
                test_dict2_uuid,
                test_dict2_hash,
                test_dict2,
                test_dict2_v2_hash,
                test_dict2_v2,
            ) = setup_simple_test_env(tmp_dir)

            self.assertEqual(
                quasilattice.entries(),
                {
                    test_dict1_hash: test_dict1,
                    test_dict2_hash: test_dict2,
                    test_dict2_v2_hash: test_dict2_v2,
                    str(test_dict2_uuid): test_dict2_v2,
                },
            )

            quasilattice.add_alias(
                "test_dict2",
                test_dict2_uuid,
                "non-existent user",
                "non-existent api_key",
            )

            self.assertTrue(
                "test_dict2" in quasilattice.aliases(test_dict2_uuid)
            )

            quasilattice.remove_alias(
                "test_dict2",
                test_dict2_uuid,
                "non-existent user",
                "non-existent api_key",)

            self.assertTrue(
                "test_dict2" not in quasilattice.aliases(test_dict2_uuid)
            )
