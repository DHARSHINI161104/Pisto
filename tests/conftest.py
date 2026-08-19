import os
import tempfile

_tmp = tempfile.mkdtemp(prefix="rifle_test_")
os.environ["RIFLE_DB"] = os.path.join(_tmp, "test.db")
os.environ["RIFLE_DISABLE_CAMERA"] = "1"