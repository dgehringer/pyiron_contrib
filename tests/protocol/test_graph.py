# coding: utf-8
# Copyright (c) Max-Planck-Institut für Eisenforschung GmbH - Computational Materials Design (CM) Department
# Distributed under the terms of "New BSD License", see the LICENSE file.

import unittest
from pyiron_contrib.protocol.graph import Vertex, Graph, DotDict, Vertices, Edges
import numpy as np


class DummyVertex(Vertex):
    def init_io_channels(self):
        self.input.add_channel('x')
        self.output.add_channel('y')

    def function(self, x):
        return {'y': x + 1}


class DummyGraph(Graph):
    def init_io_channels(self):
        self.input.add_channel('x0')
        self.input.add_channel('x1')
        self.output.add_channel('sum')

    def set_vertices(self):
        self.vertices.v1 = DummyVertex()
        self.vertices.v2 = DummyVertex()
        self.vertices.v3 = DummyVertex()

    def set_edges(self):
        v1, v2, v3 = self.vertices.v1, self.vertices.v2, self.vertices.v3
        self.edges.set_flow_chain(
            v1,
            v2, Vertex.DEFAULT_STATE,
            v3
        )
        self.starting_vertex = v1

    def wire_data_flow(self):
        v1, v2, v3 = self.vertices.v1, self.vertices.v2, self.vertices.v3
        v1.input.x += self.input.x0 + self.input.x1
        v2.input.x += v1.output.y[-1]
        v3.input.x += v2.output.y[-1]

    def get_output(self):
        return {'sum': ~self.vertices.v3.output.y[-1]}


class TestDicts(unittest.TestCase):

    def setUp(self):
        self.v1 = DummyVertex(vertex_name='v1')
        self.v2 = DummyVertex(vertex_name='v2')

    def test_dotdict(self):
        ddict = DotDict({'foo': 0})
        self.assertEqual(ddict.foo, 0)
        ddict.bar = 'abc'
        self.assertTrue(ddict.bar, 'abc')

    def test_vertices(self):
        with self.assertRaises(TypeError):
            verts = Vertices(foo=None)
        verts = Vertices(DummyGraph())
        self.assertRaises(TypeError, verts.__setitem__, verts, 'foo', 1)
        verts.foo = self.v1
        self.assertEqual(self.v1.vertex_name, 'foo')
        verts.bar = DummyVertex()
        self.assertEqual(verts.bar.vertex_name, 'bar')

    def test_edges(self):
        with self.assertRaises(TypeError):
            edges = Edges(foo=None)
        edges = Edges()
        self.assertRaises(TypeError, edges.__setitem__, 'foo', 1)
        self.assertRaises(ValueError, edges.__setitem__, 'foo', self.v1)
        edges.initialize(self.v1)
        self.assertTrue(np.all(v is None for v in edges.v1.values()))
        edges.v2 = self.v2
        self.assertTrue(np.all(v is None for v in edges.v2.values()))

        self.assertRaises(TypeError, edges.set_flow_chain, self.v1, 'next', 'should_be_a_vertex')
        self.assertRaises(KeyError, edges.set_flow_chain, self.v1, 'not_a_state', self.v2)
        edges.set_flow_chain(self.v1, self.v2, 'next', self.v1)
        self.assertEqual(edges.v1.next, 'v2')
        self.assertEqual(edges['v2']['next'], 'v1')


class TestVertex(unittest.TestCase):
    pass


class TestGraph(unittest.TestCase):

    def test_graph(self):
        graph = DummyGraph()

        # Check setup
        self.assertTrue(np.all(list(graph.vertices.keys()) == ['v1', 'v2', 'v3']))
        ref_edges = {
            'v1': {'next': 'v2'},
            'v2': {'next': 'v3'},
            'v3': {'next': None},
        }
        for k, v in graph.edges.items():
            for s, vv in v.items():
                self.assertEqual(vv, ref_edges[k][s])

        # Check resolution
        graph.input.x0 += 1
        graph.input.x1 += -1
        graph.execute()
        self.assertEqual(~graph.v1.output.y[-1], 1)
        self.assertEqual(~graph.v2.output.y[-1], 2)
        self.assertEqual(~graph.v3.output.y[-1], 3)
        self.assertEqual(~graph.output.sum[-1], 3)
