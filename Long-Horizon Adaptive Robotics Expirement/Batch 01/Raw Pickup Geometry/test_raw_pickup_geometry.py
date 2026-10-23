"""Bounded source/scope checks, without compiling a model or stepping physics."""
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

from raw_pickup_geometry import PANDA, VARIANTS, hand_xml


class StaticDeclarationTests(unittest.TestCase):
    def test_native_hand_collision_subset_keeps_fingers_and_pads(self):
        root = ET.fromstring(hand_xml({'north': [0., .074]}))
        self.assertEqual(len(root.findall('.//freejoint')), 1)
        self.assertEqual(len(root.findall('.//joint[@class="finger"]')), 2)
        self.assertEqual(len([g for g in root.findall('.//body/geom')
                              if g.get('class', '').startswith('fingertip_pad')]), 10)
        self.assertFalse(root.findall('.//body/geom[@class="visual"]'))
        self.assertEqual(len(root.findall('asset/mesh')), 2)
        self.assertEqual(root.find('.//site[@name="tcp"]').get('pos'), '0 0 .1034')

    def test_declared_origins_keep_northern_slot_fixed(self):
        self.assertEqual(len(VARIANTS), 5)
        for _, pitch, origin, _ in VARIANTS:
            self.assertAlmostEqual(origin + 3 * pitch, -.088)

    def test_native_vertex_is_an_actual_nominal_row_interference_witness(self):
        mesh = PANDA / 'assets/finger_0.obj'
        vertices = [tuple(map(float, line.split()[1:])) for line in mesh.read_text().splitlines() if line.startswith('v ')]
        self.assertIn((.008804, .015668, .035909), vertices)
        north = .04 + .015668
        height = .018 + .1034 - .0584 - .035909
        self.assertGreater(north, .074 - .021)
        self.assertLess(north, .074 + .021)
        self.assertGreater(height, 0.)
        self.assertLess(height, .036)
        self.assertLess(abs(-.008804), .021)


if __name__ == '__main__':
    unittest.main()
