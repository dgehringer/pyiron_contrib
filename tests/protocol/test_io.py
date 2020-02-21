# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

import os
from pyiron import Project
from pyiron.base.generic.hdfio import ProjectHDFio
from pyiron_contrib.protocol.data_types import Lazy, NotData
from pyiron_contrib.protocol.io import IOChannel, InputChannel, OutputChannel, Input, Output
import numpy as np
from pyiron_contrib.utils.hdf_tester import TestHasProjectHDF


class TestChannel(TestHasProjectHDF):

    @classmethod
    def setUpClass(cls):
        cls.execution_path = os.path.dirname(os.path.abspath(__file__))
        cls.project = Project(os.path.join(cls.execution_path, "channel_tests"))
        cls.hdf = ProjectHDFio(cls.project, "channel")

    @classmethod
    def tearDownClass(cls):
        cls.execution_path = os.path.dirname(os.path.abspath(__file__))
        os.remove(os.path.join(cls.execution_path, 'pyiron.log'))
        project = Project(os.path.join(cls.execution_path, "channel_tests"))
        project.remove(enable=True)

    def test_channel(self):
        channel = IOChannel(['a'])
        self.assertTrue(np.all(channel.value == ['a']))
        channel.push('b')
        self.assertTrue(np.all(channel.value == ['a', 'b']))
        channel.append('c')
        self.assertTrue(np.all(channel.value == ['a', 'b', 'c']))
        channel += 'd'
        self.assertTrue(np.all(channel.value == ['a', 'b', 'c', 'd']))
        channel[0] = 'z'
        channel.logger.warning("You should have just gotten a warning about not being able to assign; it's intentional")
        self.assertTrue(np.all(channel.value == ['a', 'b', 'c', 'd']))

    def test_input_channel(self):
        self.assertEqual(len(InputChannel()), 0)
        self.assertTrue(np.all(InputChannel([1, 2, 3]).resolve() == [1, 2, 3]))
        self.assertTrue(np.all(InputChannel(default='a').resolve() == 'a'))

    def test_input_channel_hdf(self):
        saving = InputChannel()
        saving.push(1)
        saving.push(Lazy('a'))
        saving.to_hdf(self.hdf, 'input_channel')
        loading = InputChannel()
        loading.from_hdf(self.hdf, 'input_channel')
        self.assertEqual(saving.resolve(), loading.resolve())
        self.assertEqual(len(loading.value), 1)

    def test_output_channel(self):
        channel = OutputChannel(3)
        for i in range(3):
            channel.push(i)
        self.assertEqual(len(channel), 3)

        channel.buffer_length = 4
        self.assertEqual(len(channel), 4)
        self.assertIsInstance(~channel[0], NotData)
        channel.buffer_length = 2
        self.assertEqual(len(channel), 2)
        self.assertTrue(np.all(channel.resolve() == [1, 2]))

        with self.assertRaises(ValueError):
            channel.buffer_length = 'a'
        with self.assertRaises(ValueError):
            channel.buffer_length = 0

    def test_output_channel_hdf(self):
        saving = OutputChannel()
        saving.push(1)
        saving.push(Lazy('a'))
        saving.to_hdf(self.hdf, 'output_channel')
        loading = OutputChannel()
        loading.from_hdf(self.hdf, 'output_channel')
        self.assertTrue(np.all(s == l for s, l in zip(saving.resolve(), loading.resolve())))
        self.assertEqual(len(loading.value), 1)


class TestInput(TestHasProjectHDF):

    def test_input(self):
        self.assertRaises(TypeError, Input.__init__, {})
        input_dict = Input()

        # Only allow InputStacks to be assigned
        self.assertRaises(ValueError, input_dict.__setitem__, 'key', 1)
        self.assertRaises(ValueError, input_dict.__setattr__, 'key', 1)

        # Add some data channels
        input_dict.channel1 = InputChannel(1)
        input_dict.channel1 += NotData()  # Will need to pass the first one
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

    def test_hdf(self):
        saving = Input()
        saving.add_channel('foo', 1)
        saving.foo.push(Lazy(2))
        saving.add_channel('bar')
        saving.bar.push('bar')
        saving.to_hdf(self.hdf, 'input')
        loading = Input()
        loading.from_hdf(self.hdf, 'input')
        for k, schan in saving.items():
            lchan = loading[k]
            self.assertEqual(schan.resolve(), lchan.resolve())


class TestOutput(TestHasProjectHDF):

    def test_output(self):
        self.assertRaises(TypeError, Output.__init__, {})
        output = Output()

        # Fields must be initialized to the `NotData` type
        with self.assertRaises(ValueError):
            output.foo = 1

        output.foo = OutputChannel(buffer_length=2)  # Output automatically wraps with Lazy, so we don't need to
        output.add_channel('bar')
        output['baz'] = OutputChannel() # But we *can* wrap with Lazy if we want. It won't re-wrap.

        output.foo.push(0)
        output.bar.append(1)
        output.baz += 2
        self.assertIsInstance(output.foo, Lazy)
        self.assertIsInstance(output.bar, Lazy)
        self.assertIsInstance(output.baz, Lazy)

        # Check that they wrap (unwrap) to (from) lazy ok
        ref_dict = {
            'foo': [NotData(), 0],
            'bar': [1],
            'baz': [2]
        }
        for k, v in output.resolve().items():
            self.assertTrue(all(vi == ref for vi, ref in zip(v, ref_dict[k])))

    def test_hdf(self):
        saving = Output()
        saving.add_channel('foo')
        saving.foo.push(1)
        saving.foo.push(Lazy(2))
        saving.add_channel('bar')
        saving.bar.push('bar')
        saving.to_hdf(self.hdf, 'input')
        loading = Output()
        loading.from_hdf(self.hdf, 'input')
        for k, schan in saving.items():
            lchan = loading[k]
            self.assertTrue(s == l for s, l in zip(schan.resolve(), lchan.resolve()))
