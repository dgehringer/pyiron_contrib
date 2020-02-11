# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

import unittest
import numpy as np
from pyiron_contrib.protocol.utils.lazy import Lazy


class Adder:
    """A dummy class for playing around with lazy resolution with arguments."""
    def __init__(self, x):
        self.x = x

    @staticmethod
    def deep_add(x):
        return Adder(x)

    def add(self, y, z):
        return self.x + y + z


class TestLazy(unittest.TestCase):
    """
    Test that deferred resolution is working under a variety of conditions.

    TODO: Add tests for the rest of the magic methods that are set at class definition time.
    """

    @classmethod
    def tearDownClass(cls):
        pass

    @classmethod
    def setUpClass(cls):
        pass

    def setUp(self):
        pass

    def test_chaining_getitem_add_sub_mul_truediv(self):
        # Add to a lazy variable
        lazy = Lazy()

        array_slice_chain = lazy[:3]
        array_shape_chain = array_slice_chain.shape[0]  # Chain off a chain

        lazy.value = np.arange(5)  # Set value *after* defining lazy chains

        self.assertTrue(np.all(~array_slice_chain + np.ones(3) == np.array([1, 2, 3])))  # Resolve and add *together*
        self.assertEqual(~(array_shape_chain - 2), 1)  # Also explicitly resolve *after* adding

        # Add two lazy variables together
        lazy_2 = Lazy(value=np.arange(5)[::-1])  # Set the value at instantiation

        self.assertTrue(np.all(~(array_slice_chain + lazy_2[:3]) == np.array([4, 4, 4])))

        broken_array_chain = array_slice_chain + lazy_2[[0, 1, 2, 3]]
        self.assertIsInstance(broken_array_chain, Lazy)
        self.assertRaises(ValueError, broken_array_chain.resolve)  # wrong lengths

        # Addition chain
        self.assertEqual(~(array_shape_chain + lazy_2[:4].shape[0] + 2), 3 + 4 + 2)

        # Other operators
        self.assertEqual(~(array_shape_chain * 3), 9)
        self.assertEqual(~(array_shape_chain / 3), 1)
        self.assertEqual(~(array_shape_chain - 3), 0)

    def test_call(self):
        lazy = Lazy()
        lazy.value = Adder(0)
        chain = lazy.deep_add(1).add(2, 3)
        self.assertEqual(~chain, 6)

    def test_iadd_isub_imult_itruediv(self):
        lazy = Lazy()
        lazy *= 3
        array = np.ones(3)
        lazy.value = array.copy()
        self.assertTrue(np.all(~lazy == 3 * array))

        lazy += 2
        self.assertTrue(np.all(~lazy == 3*array + 2))

        lazy -= 2
        self.assertTrue(np.all(~lazy == 3 * array))

        lazy /= 3.
        self.assertTrue(np.all(~lazy == array))
