import ctypes
import inspect
import unittest
from typing import get_type_hints

import numpy as np
from comtypes import IUnknown
from pygrabber.dshow_core import qedit
from pygrabber.dshow_graph import BufferPointer, SampleGrabberCallback


class DirectShowCallbackTests(unittest.TestCase):
    def test_buffer_signature_matches_the_native_interface(self) -> None:
        parameters = inspect.signature(SampleGrabberCallback.BufferCB).parameters
        self.assertEqual(tuple(parameters), ("self", "this", "SampleTime", "pBuffer", "BufferLen"))
        hints = get_type_hints(SampleGrabberCallback.BufferCB)
        method = next(method for method in qedit.ISampleGrabberCB._methods_ if method.name == "BufferCB")
        self.assertIs(hints["pBuffer"], method.argtypes[1])
        self.assertIs(BufferPointer, ctypes.POINTER(ctypes.c_ubyte))
        self.assertEqual(hints["this"], int | None)
        self.assertIs(hints["SampleTime"], float)
        self.assertIs(hints["BufferLen"], int)
        self.assertIs(hints["return"], int)

    def test_native_call_copies_and_flips_the_requested_frame(self) -> None:
        frames = []
        callback = SampleGrabberCallback(frames.append)
        callback.image_resolution = (2, 2)
        native = callback.QueryInterface(qedit.ISampleGrabberCB)
        source = (ctypes.c_ubyte * 12)(*range(12))
        pointer = ctypes.cast(source, BufferPointer)
        self.assertEqual(native.BufferCB(0.25, pointer, len(source)), 0)
        self.assertEqual(frames, [])

        callback.grab_frame()
        self.assertEqual(native.BufferCB(0.5, pointer, len(source)), 0)
        self.assertEqual(len(frames), 1)
        expected = np.arange(12, dtype=np.uint8).reshape(2, 2, 3)[::-1]
        np.testing.assert_array_equal(frames[0], expected)
        self.assertEqual(frames[0].dtype, np.dtype(np.uint8))
        source[0] = 255
        np.testing.assert_array_equal(frames[0], expected)
        self.assertEqual(native.BufferCB(0.75, pointer, len(source)), 0)
        self.assertEqual(len(frames), 1)
        sample_method = next(method for method in qedit.ISampleGrabberCB._methods_ if method.name == "SampleCB")
        self.assertEqual(native.SampleCB(1.0, sample_method.argtypes[1]()), 0)

    def test_native_override_receives_this_and_preserves_hresult(self) -> None:
        calls = []

        class Override(SampleGrabberCallback):
            def BufferCB(self, this: int | None, SampleTime: float, pBuffer: BufferPointer, BufferLen: int) -> int:
                calls.append((this, SampleTime, pBuffer[0], BufferLen))
                return 1

        callback = Override(lambda frame: None)
        native = callback.QueryInterface(qedit.ISampleGrabberCB)
        source = (ctypes.c_ubyte * 1)(42)
        self.assertEqual(native.BufferCB(1.25, ctypes.cast(source, BufferPointer), len(source)), 1)
        self.assertEqual(calls, [(ctypes.cast(native, ctypes.c_void_p).value, 1.25, 42, 1)])
        identity = native.QueryInterface(IUnknown)
        canonical = callback.QueryInterface(IUnknown)
        self.assertEqual(ctypes.cast(identity, ctypes.c_void_p).value, ctypes.cast(canonical, ctypes.c_void_p).value)
        self.assertEqual(str(qedit.ISampleGrabberCB._iid_), "{0579154A-2B53-4994-B0D0-E773148EFF85}")


if __name__ == "__main__":
    unittest.main()
