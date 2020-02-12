# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

import unittest
from pyiron_contrib.protocol.lazy import Lazy
from pyiron_contrib.protocol.io import InputChannel, Input, Output, NotData
import numpy as np


class TestInputStack(unittest.TestCase):

    def test_initialization(self):
        self.assertEqual(len(InputChannel()), 0)
        self.assertTrue(np.all(InputChannel([1, 2, 3]) == [1, 2, 3]))
        self.assertTrue(np.all(InputChannel(initlist=[1, 2, 3]) == [1, 2, 3]))
        self.assertTrue(np.all(InputChannel(default='a') == ['a']))
        self.assertRaises(ValueError, InputChannel.__init__, self, initlist=[1], default='a')

    def test_push(self):
        stack = InputChannel([0, 1])
        stack.push(2)
        self.assertTrue(np.all(stack == [0, 1, 2]))


class TestInput(unittest.TestCase):

    def test_input(self):
        self.assertRaises(TypeError, Input.__init__, {})
        input_dict = Input()

        # Only allow InputStacks to be assigned
        self.assertRaises(ValueError, input_dict.__setitem__, 'key', 1)
        self.assertRaises(ValueError, input_dict.__setattr__, 'key', 1)

        # Add some data channels
        input_dict.channel1 = InputChannel([1, NotData()])  # Will need to pass the first one
        input_dict['channel2'] = InputChannel(default=Lazy('a'))

        # Make sure they're both there
        self.assertEqual(len(input_dict), 2)
        self.assertEqual(len(~input_dict), 2)

        # Verify dictionary resolution
        ref_dict = {'channel1': 1, 'channel2': 'a'}
        for k, v in input_dict.resolve().items():
            self.assertEqual(v, ref_dict[k])

        # Break the data stack
        input_dict.channel3 = InputChannel(default=Lazy(NotData()))
        self.assertRaises(RuntimeError, input_dict.resolve)


class TestOutput(unittest.TestCase):

    def test_output(self):
        self.assertRaises(TypeError, Output.__init__, {})
        output = Output()

        # Fields must be initialized to the `NotData` type
        output.foo  # Editor warning "statement seems to have no effect" is a warning this is dangerous syntax...
        output.bar = NotData()  # Output automatically wraps with Lazy, so we don't need to
        output['baz'] = Lazy(NotData())  # But we *can* wrap with Lazy if we want. It won't re-wrap.
        self.assertRaises(ValueError, output.__setitem__, 'boa', 42)

        # Then we can set them to what we want
        output.foo = 'foo'
        output.baz = Lazy('baz')

        # Check that they wrap (unwrap) to (from) lazy ok
        for v in output.values():
            self.assertIsInstance(v, Lazy)

        for v in output.resolve().values():
            self.assertFalse(isinstance(v, Lazy))