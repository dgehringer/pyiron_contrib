# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

import unittest
from pyiron_contrib.protocol.lazy import Lazy
from pyiron_contrib.protocol.io import NotData, IOChannel, InputChannel, OutputChannel, Input, Output
import numpy as np


class TestChannel(unittest.TestCase):

    def test_channel(self):
        channel = IOChannel(['a'])
        self.assertTrue(np.all(channel == ['a']))
        channel.push('b')
        self.assertTrue(np.all(channel == ['a', 'b']))
        channel.append('c')
        self.assertTrue(np.all(channel == ['a', 'b', 'c']))
        channel += 'd'
        self.assertTrue(np.all(channel == ['a', 'b', 'c', 'd']))
        channel[0] = 'z'
        self.assertTrue(np.all(channel == ['a', 'b', 'c', 'd']))

    def test_input_channel(self):
        self.assertEqual(len(InputChannel()), 0)
        self.assertTrue(np.all(InputChannel([1, 2, 3]) == [1, 2, 3]))
        self.assertTrue(np.all(InputChannel(initlist=[1, 2, 3]) == [1, 2, 3]))
        self.assertTrue(np.all(InputChannel(default='a') == ['a']))
        self.assertRaises(ValueError, InputChannel.__init__, self, initlist=[1], default='a')

    def test_output_channel(self):
        channel = OutputChannel(3)
        for i in range(3):
            channel.push(i)
        self.assertEqual(len(channel), 3)

        channel.buffer_length = 4
        self.assertEqual(len(channel), 4)
        self.assertIsInstance(channel[0], NotData)
        channel.buffer_length = 2
        self.assertEqual(len(channel), 2)
        self.assertTrue(np.all(channel == [1, 2]))

        with self.assertRaises(ValueError):
            channel.buffer_length = 'a'
        with self.assertRaises(ValueError):
            channel.buffer_length = 0


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
        with self.assertRaises(ValueError):
            output.foo = 1

        output.foo = OutputChannel(buffer_length=2)  # Output automatically wraps with Lazy, so we don't need to
        output.add_channel('bar')
        output['baz'] = Lazy(OutputChannel())  # But we *can* wrap with Lazy if we want. It won't re-wrap.

        ~output.foo.push(0)
        output.bar.push(1).resolve()
        output.baz.resolve().push(2)
        # TODO: These are all gross syntax. Work out a better way to push to Lazy lists, or make it a list of Lazies.
        #       Maybe we can decorate the added Lazy items so they do something special on a `push` call?

        # Check that they wrap (unwrap) to (from) lazy ok
        ref_dict = {
            'foo': [NotData(), 0],
            'bar': [1],
            'baz': [2]
        }
        for k, v in output.resolve().items():
            self.assertTrue(all(vi == ref for vi, ref in zip(v, ref_dict[k])))
