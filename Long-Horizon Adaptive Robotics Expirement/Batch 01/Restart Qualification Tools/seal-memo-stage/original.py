"""Protected, source-bound physical-class export; no physics execution.

The integration must call seal_model immediately after MjModel.from_xml_string,
before exposing the model to controllers. Class identity uses the entire XML
compilation input after a narrow, checked generator whitelist, exact dependency
bytes, and the complete exposed compiled-model surface sealed at construction.
This is not a claim that selected MuJoCo arrays are a complete physics model.
Only the source-declared binary process-mark color may change after compilation.
"""
from __future__ import annotations

import colorsys
import copy
import hashlib
import math
import struct
import weakref
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

from restart_compatibility import (COMPONENTS, OBS_SCHEMA, SPEC_SCHEMA, box_aggregate,
                           close, digest, finite, sha, vector)

EXPORT_SCHEMA = 'source-bound-restart-export-1'
DOMAIN = {'allowed_part_counts': [3, 6, 10],
          'main_geom_mass_kg': {'min': .09, 'max': .11, 'max_exclusive': True},
          'main_geom_sliding_friction': {'min': 1.1, 'max': 1.3, 'max_exclusive': True}}
RULES = {'schema': EXPORT_SCHEMA, 'basis': 'whole normalized XML plus sealed compilation',
         'variable_xml': ['registered body initial planar raw-slot jitter +/-0.003m',
                          'registered main box mass [0.09,0.11)kg',
                          'registered main box sliding friction [1.1,1.3)',
                          'generator tag hue +/-0.004 around population index palette',
                          'legal alternating A/B population 3,6,10 plus two inserts'],
         'post_compile_variable': 'registered mark geom rgba: raw .03,.03,.03,1 or processed 1,1,1,1',
         'derived_mass_rule': 'axis-aligned-box-aggregate-1',
         'unknown_model_properties': 'unsupported; fail closed',
         'source_domain_is_measured': False}


class UnsupportedEvidence(ValueError):
    pass


def file_sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def source_binding(runtime_dir, mujoco_package):
    """Hash current protected sources/assets/runtime binaries; no seeds or runs.

    Caller keeps the returned identities in the protected release. Missing
    files are errors, never empty identities. Package binaries are included,
    not merely a reported version string.
    """
    root = Path(runtime_dir).resolve()
    sources = {name: file_sha(root / name) for name in
               ('cell.py', 'actuation.py', 'evaluator.py', 'sensor_worker.py',
                'restart_state.py', 'restart_compatibility.py', 'restart_qualification.py')}
    sources['descriptor_exporter'] = file_sha(__file__)
    assets = {p.relative_to(root / 'vendor' / 'panda').as_posix(): file_sha(p)
              for p in sorted((root / 'vendor' / 'panda').rglob('*')) if p.is_file()}
    package = Path(mujoco_package.__file__).resolve().parent
    binaries = {p.relative_to(package).as_posix(): file_sha(p)
                for p in sorted(package.rglob('*'))
                if p.is_file() and p.suffix.lower() in ('.pyd', '.dll', '.so', '.dylib')}
    if not assets or not binaries:
        raise UnsupportedEvidence('asset or MuJoCo binary identity missing')
    sources['robot_assets'] = digest(assets)
    sources['mujoco_build'] = digest({'version': mujoco_package.__version__, 'binaries': binaries})
    return sources


def _numbers(text, count):
    try:
        values = [float(x) for x in text.split()]
    except (AttributeError, ValueError):
        raise UnsupportedEvidence('missing/malformed XML vector') from None
    if len(values) != count or not all(finite(x) for x in values):
        raise UnsupportedEvidence('incomplete/nonfinite XML vector')
    return values


def _tree(node):
    if (node.text or '').strip() or (node.tail or '').strip():
        raise UnsupportedEvidence('unexpected XML text')
    return {'tag': node.tag, 'attributes': dict(sorted(node.attrib.items())),
            'children': [_tree(child) for child in node]}


def _registry(registry):
    if not isinstance(registry, dict):
        raise UnsupportedEvidence('registry missing')
    n = len(registry) - 2
    if n not in DOMAIN['allowed_part_counts']:
        raise UnsupportedEvidence('unsupported part population')
    identities = [(f'{"A" if i % 2 == 0 else "B"}{i+1}', 'part', 'A' if i % 2 == 0 else 'B') for i in range(n)]
    identities += [('insert_A', 'insert', 'A'), ('insert_B', 'insert', 'B')]
    if set(registry) != {row[0] for row in identities}:
        raise UnsupportedEvidence('registry is not the exact generated population')
    for identity, kind, family in identities:
        row = registry[identity]
        if (not isinstance(row, dict) or set(row) != {'kind', 'family', 'hue', 'half'}
                or row['kind'] != kind or row['family'] != family or not finite(row['hue'])
                or row['half'] != ([.021, .021, .018] if kind == 'part' else [.025, .025, .008])):
            raise UnsupportedEvidence('registry template differs from declared generator')
    return identities


def normalize_scene(xml, registry):
    """Canonicalize only reviewed generator variation; retain every other field.

    XML attribute order/indentation are immaterial. Attribute values outside the
    explicit whitelist remain exact, including all unknown/new fixed fields.
    Initial layout and visual membership are checked here, not erased blindly.
    """
    if not isinstance(xml, str) or '<!DOCTYPE' in xml or '<!ENTITY' in xml:
        raise UnsupportedEvidence('unsupported XML input')
    root = ET.fromstring(xml)
    if root.findall('.//include'):
        raise UnsupportedEvidence('unexpanded includes are unsupported')
    identities = _registry(registry)
    world, asset = root.find('worldbody'), root.find('asset')
    if world is None or asset is None:
        raise UnsupportedEvidence('worldbody/asset missing')
    templates, instances = {}, []
    for index, (identity, kind, family) in enumerate(identities):
        bodies = root.findall(f".//body[@name='{identity}']")
        materials = root.findall(f".//material[@name='tagmat_{identity}']")
        if len(bodies) != 1 or bodies[0] not in list(world) or len(materials) != 1 or materials[0] not in list(asset):
            raise UnsupportedEvidence('missing/duplicate/non-root generated entity')
        body, material = bodies[0], materials[0]
        if len(body) != 4 or [child.tag for child in body] != ['freejoint', 'geom', 'geom', 'geom']:
            raise UnsupportedEvidence('entity is not the reviewed free box with two marks')
        joint, main, tag, mark = body
        if joint.get('name') != 'free_' + identity or [g.get('name') for g in (main, tag, mark)] != [p + identity for p in ('part_', 'tag_', 'mark_')]:
            raise UnsupportedEvidence('entity child identity mismatch')
        position = _numbers(body.get('pos'), 3)
        if kind == 'part':
            row, col = divmod(index, 3)
            center = [.32 + .085 * col, -.373 + .095 * row, .021]
            if any(abs(position[i] - center[i]) > .003 + 1e-12 for i in (0, 1)) or position[2] != center[2]:
                raise UnsupportedEvidence('raw stock outside declared initial slot jitter')
        else:
            zone = world.find("geom[@name='zone_" + ('fixture' if identity == 'insert_A' else 'insert_home_B') + "']")
            if zone is None or position != _numbers(zone.get('pos'), 3)[:2] + [.009]:
                raise UnsupportedEvidence('insert initial pose differs from declared zone')
        mass = _numbers(main.get('mass'), 1)[0]
        friction = _numbers(main.get('friction'), 3)
        if not (.09 <= mass < .11 and 1.1 <= friction[0] < 1.3) or friction[1:] != [.015, .001]:
            raise UnsupportedEvidence('mass/friction outside reviewed generator domain')
        half = registry[identity]['half']
        boxes = []
        for g, expected_half, expected_position, gm in (
                (main, half, [0., 0., 0.], 'sampled_main_geom_mass'),
                (tag, [.014, .014, .0003], [0., 0., half[2] + .0004], .0001),
                (mark, [.004, .014, .0003], [.018, 0., half[2] + .0004], .0001)):
            if (g.get('type') != 'box' or _numbers(g.get('size'), 3) != expected_half
                    or _numbers(g.get('pos', '0 0 0'), 3) != expected_position
                    or any(k in g.attrib for k in ('quat', 'axisangle', 'euler', 'xyaxes', 'zaxis', 'fromto', 'density'))
                    or (gm != 'sampled_main_geom_mass' and _numbers(g.get('mass'), 1)[0] != gm)):
                raise UnsupportedEvidence('unsupported mass-contributing shape/transform')
            boxes.append({'half_size_m': expected_half, 'position_m': expected_position, 'mass_kg': gm})
        hue = registry[identity]['hue']
        base = (index + .25) / len(identities)
        delta = (hue - base + .5) % 1. - .5
        rgba = _numbers(material.get('rgba'), 4)
        if not 0. <= hue < 1. or not -.004 - 1e-12 <= delta <= .004 + 1e-12 or not all(close(a, b) for a, b in zip(rgba, [*colorsys.hsv_to_rgb(hue, .95, .35), 1.])):
            raise UnsupportedEvidence('tag color/hue does not follow public generator')
        # Renaming is limited to exact known references, never textual replace.
        body.set('name', '$entity'); body.set('pos', '$declared_initial_pose')
        joint.set('name', 'free_$entity')
        for g, prefix in ((main, 'part_'), (tag, 'tag_'), (mark, 'mark_')):
            g.set('name', prefix + '$entity')
        if tag.get('material') != 'tagmat_' + identity:
            raise UnsupportedEvidence('tag material reference differs')
        tag.set('material', 'tagmat_$entity'); main.set('mass', '$sampled_main_geom_mass')
        main.set('friction', '$sampled_sliding .015 .001')
        material.set('name', 'tagmat_$entity'); material.set('rgba', '$declared_tag_palette')
        template = {'inertia_rule': RULES['derived_mass_rule'], 'mass_boxes': boxes,
                    'fixed_friction_tail': [.015, .001],
                    'all_other_compilation_input_fields': {'body': _tree(body), 'material': _tree(material)}}
        key = kind + ':' + family
        if key in templates and templates[key] != template:
            raise UnsupportedEvidence('same-family entity templates disagree')
        templates[key] = template
        instances.append({'id': identity, 'kind': kind, 'family': family, 'template_sha256': digest(template),
                          'main_geom_mass_kg': mass, 'main_geom_friction': friction,
                          'initial_position_world_m': position, 'tag_hue': hue})
        world.remove(body); asset.remove(material)
    return {'fixed_xml': _tree(root), 'templates': templates, 'objects': instances,
            'part_count': len(identities) - 2}


def _surface(value, path='model'):
    """Hash all public data attributes, including nested options/visual/statistic.

    Arrays retain dtype, shape, byte identity. Any unhandled exposed property is
    rejected. No hand-selected list can silently omit a new solver setting.
    """
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise UnsupportedEvidence(path + ': nonfinite scalar')
        return value
    if isinstance(value, bytes):
        return {'bytes_sha256': hashlib.sha256(value).hexdigest(), 'length': len(value)}
    if hasattr(value, 'dtype') and hasattr(value, 'shape') and hasattr(value, 'tobytes'):
        if value.dtype.kind in 'fc' and not np.isfinite(value).all():
            raise UnsupportedEvidence(path + ': nonfinite array')
        return {'dtype': str(value.dtype), 'shape': list(value.shape), 'sha256': hashlib.sha256(value.tobytes()).hexdigest()}
    if isinstance(value, (tuple, list)):
        return [_surface(v, path) for v in value]
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            raise UnsupportedEvidence(path + ': non-string mapping keys')
        return {k: _surface(v, path + '.' + k) for k, v in sorted(value.items())}
    if type(value).__module__.startswith('mujoco.'):
        result = {}
        for name in dir(value):
            if name.startswith('_'):
                continue
            field = getattr(value, name)
            if not callable(field):
                result[name] = _surface(field, path + '.' + name)
        if result:
            return result
    raise UnsupportedEvidence(path + ': unsupported property ' + type(value).__name__)


def _model_surface(model, mark_indices):
    result = _surface(model)
    colors = model.geom_rgba.copy()
    for index in mark_indices:
        color = colors[index].tolist()
        # MuJoCo stores rgba as float32; this allowance is visual representation
        # roundoff only and never changes a physical/grip/route threshold.
        if not (len(color) == 4 and all(abs(a - b) <= 2e-8 for a, b in zip(color, [.03, .03, .03, 1.]))
                or color == [1., 1., 1., 1.]):
            raise UnsupportedEvidence('process mark color outside binary source rule')
        colors[index] = [0., 0., 0., 0.]
    result['geom_rgba'] = _surface(colors)
    return result




class _SurfaceNode:
    __slots__ = ('token', 'descriptor', 'children')

    def __init__(self, token, descriptor, children=()):
        self.token, self.descriptor, self.children = token, descriptor, children


# Values contain bytes, primitive descriptors and weak references only. No node
# retains the native model. Retiring a model releases its entire byte baseline.
_SURFACE_MEMOS = weakref.WeakKeyDictionary()


def _observed_surface(value, previous=None, path='model'):
    """Read every current public field; reuse hashes only for exact byte matches.

    Same canonical representation and unsupported-property policy as _surface.
    This is a complete current comparison, not a simulation-time cache.
    """
    def leaf(token, describe):
        if previous is not None and previous.token == token:
            return previous
        return _SurfaceNode(token, describe())

    if value is None or type(value) in (str, bool, int):
        return leaf(('scalar', type(value), value), lambda: value)
    if type(value) is float:
        if not math.isfinite(value):
            raise UnsupportedEvidence(path + ': nonfinite scalar')
        # Python equality equates positive/negative zero, but canonical JSON
        # preserves them. Compare the exact float representation instead.
        return leaf(('float', struct.pack('>d', value)), lambda: value)
    if isinstance(value, bytes):
        return leaf(('bytes', value), lambda: {'bytes_sha256': hashlib.sha256(value).hexdigest(), 'length': len(value)})
    if hasattr(value, 'dtype') and hasattr(value, 'shape') and hasattr(value, 'tobytes'):
        token = ('array', str(value.dtype), tuple(value.shape), value.tobytes())
        if previous is not None and previous.token == token:
            return previous
        if value.dtype.kind in 'fc' and not np.isfinite(value).all():
            raise UnsupportedEvidence(path + ': nonfinite array')
        return _SurfaceNode(token, {'dtype': token[1], 'shape': list(token[2]),
                                    'sha256': hashlib.sha256(token[3]).hexdigest()})
    if isinstance(value, (tuple, list)):
        token = ('sequence', type(value), len(value))
        old = previous.children if previous is not None and previous.token == token else (None,) * len(value)
        children = tuple(_observed_surface(v, old[i], path) for i, v in enumerate(value))
        if previous is not None and previous.token == token and all(a is b for a, b in zip(children, old)):
            return previous
        return _SurfaceNode(token, [child.descriptor for child in children], children)
    if isinstance(value, dict):
        if not all(isinstance(k, str) for k in value):
            raise UnsupportedEvidence(path + ': non-string mapping keys')
        fields = [(k, v) for k, v in sorted(value.items())]
        kind = ('mapping',)
    elif type(value).__module__.startswith('mujoco.'):
        fields = []
        for name in dir(value):
            if name.startswith('_'):
                continue
            field = getattr(value, name)
            if not callable(field):
                fields.append((name, field))
        if not fields:
            raise UnsupportedEvidence(path + ': unsupported property ' + type(value).__name__)
        kind = ('native', type(value))
    else:
        raise UnsupportedEvidence(path + ': unsupported property ' + type(value).__name__)
    token = (*kind, tuple(k for k, _ in fields))
    old = previous.children if previous is not None and previous.token == token else (None,) * len(fields)
    children = tuple(_observed_surface(v, old[i], path + '.' + k) for i, (k, v) in enumerate(fields))
    if previous is not None and previous.token == token and all(a is b for a, b in zip(children, old)):
        return previous
    return _SurfaceNode(token, {k: child.descriptor for (k, _), child in zip(fields, children)}, children)


def _model_surface_sha(model, seal):
    """Memoize only a verified descriptor; compare every live native field first."""
    key = (seal['seal_sha256'], seal['compiled_surface_sha256'], tuple(seal['mark_indices']))
    try:
        prior = _SURFACE_MEMOS.get(model)
    except TypeError:
        # Preserve the original verifier for non-weak-referenceable test/native
        # providers. Actual MjModel supports weak keys; never keep a strong key.
        return digest(_model_surface(model, seal['mark_indices']))
    if prior is None or prior[0]() is not model or prior[1] != key:
        prior = None
    root = _observed_surface(model, None if prior is None else prior[2])
    # Keep the existing binary-color rule and its error ordering. Raw rgba is
    # included in the full live comparison; only these checked marks normalize.
    colors = model.geom_rgba.copy()
    for index in seal['mark_indices']:
        color = colors[index].tolist()
        if not (len(color) == 4 and all(abs(a - b) <= 2e-8 for a, b in zip(color, [.03, .03, .03, 1.]))
                or color == [1., 1., 1., 1.]):
            raise UnsupportedEvidence('process mark color outside binary source rule')
        colors[index] = [0., 0., 0., 0.]
    normalized_colors = _surface(colors)
    if prior is not None and root is prior[2]:
        observed_sha = prior[3]
    else:
        surface = dict(root.descriptor)
        surface['geom_rgba'] = normalized_colors
        observed_sha = digest(surface)
    # An altered or unsupported model never establishes a reusable baseline.
    if observed_sha == seal['compiled_surface_sha256']:
        _SURFACE_MEMOS[model] = (weakref.ref(model), key, root, observed_sha)
    return observed_sha


def _mass_properties(model, body_id):
    mass = float(model.body_mass[body_id])
    com = model.body_ipos[body_id].tolist()
    q = model.body_iquat[body_id].tolist()
    if not vector(q, 4) or not close(sum(v * v for v in q), 1.):
        raise UnsupportedEvidence('compiled inertial orientation is malformed')
    w, x, y, z = q
    r = [[1-2*(y*y+z*z), 2*(x*y-z*w), 2*(x*z+y*w)],
         [2*(x*y+z*w), 1-2*(x*x+z*z), 2*(y*z-x*w)],
         [2*(x*z-y*w), 2*(y*z+x*w), 1-2*(x*x+y*y)]]
    diagonal = model.body_inertia[body_id].tolist()
    tensor = [[sum(r[i][k] * diagonal[k] * r[j][k] for k in range(3)) for j in range(3)] for i in range(3)]
    return {'mass_kg': mass, 'center_of_mass_body_m': com, 'inertia_tensor_body_kg_m2': tensor}


def seal_model(model, xml, registry, sources):
    """Capture at the direct compilation site; no preexisting model accepted by integration.

    This function never steps physics or compiles another model. Its attestation
    is meaningful only with the pinned caller source proving construction order.
    """
    required = {'descriptor_exporter', 'cell.py', 'actuation.py', 'evaluator.py', 'sensor_worker.py',
                'restart_state.py', 'restart_compatibility.py', 'restart_qualification.py', 'robot_assets', 'mujoco_build'}
    if not isinstance(sources, dict) or set(sources) != required or any(not sha(v) for v in sources.values()):
        raise UnsupportedEvidence('complete protected source/build/asset binding required')
    scene = normalize_scene(xml, registry)
    marks, object_rows = [], []
    for row in scene['objects']:
        identity = row['id']
        body_id, geom_id, mark_id = int(model.body(identity).id), int(model.geom('part_' + identity).id), int(model.geom('mark_' + identity).id)
        if int(model.geom_bodyid[geom_id]) != body_id or int(model.geom_bodyid[mark_id]) != body_id:
            raise UnsupportedEvidence('compiled semantic body/geom attachment mismatch')
        actual = _mass_properties(model, body_id)
        expected = box_aggregate(scene['templates'][row['kind'] + ':' + row['family']], row['main_geom_mass_kg'])
        if not _numeric_tree_close(actual, expected) or not _numeric_tree_close(model.geom_friction[geom_id].tolist(), row['main_geom_friction']):
            raise UnsupportedEvidence('compiled mass/contact properties disagree with sealed source')
        marks.append(mark_id)
        object_rows.append({**row, 'compiled_mass_properties': actual})
    surface = _model_surface(model, marks)
    fixed_identity = {'normalized_whole_xml': digest(scene['fixed_xml']), 'assets': sources['robot_assets'],
                      'compiler': sources['mujoco_build'], 'rules': digest(RULES)}
    components = {
        'robot_geometry_and_joints': digest(fixed_identity),
        'fixed_static_geometry': digest(fixed_identity),
        'native_actuators': digest(fixed_identity),
        'contact_solver_and_integration': digest(fixed_identity),
        'recovery_controller': digest({k: sources[k] for k in ('cell.py', 'actuation.py', 'restart_state.py', 'restart_qualification.py')}),
        'perception_and_registry': digest({k: sources[k] for k in ('cell.py', 'sensor_worker.py', 'evaluator.py')}),
        'compiled_canonicalization_rules': digest({'rules': RULES, 'exporter': sources['descriptor_exporter'],
                                                'compiler': sources['mujoco_build']})}
    assert set(components) == COMPONENTS
    result = {'schema_version': EXPORT_SCHEMA, 'scene_xml_sha256': hashlib.sha256(xml.encode()).hexdigest(),
              'source_hashes': copy.deepcopy(sources), 'registry_sha256': digest(registry),
              'mark_indices': marks, 'compiled_surface': surface, 'compiled_surface_sha256': digest(surface),
              'component_sha256': components, 'templates': scene['templates'],
              'part_count': scene['part_count'], 'objects': object_rows,
              'compilation_attestation': 'source-bound direct MjModel.from_xml_string construction'}
    result['seal_sha256'] = digest(result)
    return result


def _numeric_tree_close(actual, expected):
    if isinstance(expected, dict):
        return isinstance(actual, dict) and set(actual) == set(expected) and all(_numeric_tree_close(actual[k], v) for k, v in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(_numeric_tree_close(a, e) for a, e in zip(actual, expected))
    return finite(actual) and finite(expected) and close(actual, expected)


def class_spec_from_seal(seal):
    """Return a domain descriptor proposal only, never calibration/readiness."""
    _check_seal(seal)
    return {'schema_version': SPEC_SCHEMA, 'required_source_hashes': copy.deepcopy(seal['source_hashes']),
            'component_sha256': copy.deepcopy(seal['component_sha256']), 'templates': copy.deepcopy(seal['templates']),
            'declared_domain': copy.deepcopy(DOMAIN)}


def _check_seal(seal):
    if not isinstance(seal, dict) or seal.get('schema_version') != EXPORT_SCHEMA or not sha(seal.get('seal_sha256')):
        raise UnsupportedEvidence('source-bound compile seal unavailable')
    if digest({k: v for k, v in seal.items() if k != 'seal_sha256'}) != seal['seal_sha256']:
        raise UnsupportedEvidence('compile seal was altered')


def export_observation(model, xml, registry, seal, *, physical_configuration_sha256):
    """Read-only capture; changed/missing compile evidence remains unknown."""
    try:
        _check_seal(seal)
        if not sha(physical_configuration_sha256):
            raise UnsupportedEvidence('exact physical configuration identity missing')
        if hashlib.sha256(xml.encode()).hexdigest() != seal['scene_xml_sha256'] or digest(registry) != seal['registry_sha256']:
            raise UnsupportedEvidence('source XML/registry changed after sealed construction')
        if _model_surface_sha(model, seal) != seal['compiled_surface_sha256']:
            raise UnsupportedEvidence('compiled model differs from sealed source construction')
        return {'schema_version': OBS_SCHEMA, 'export_schema': EXPORT_SCHEMA, 'export_state': 'pass',
                'source_hashes': copy.deepcopy(seal['source_hashes']), 'component_sha256': copy.deepcopy(seal['component_sha256']),
                'part_count': seal['part_count'], 'objects': copy.deepcopy(seal['objects']),
                'physical_configuration_sha256': physical_configuration_sha256, 'scene_xml_sha256': seal['scene_xml_sha256'],
                'compiled_surface_sha256': seal['compiled_surface_sha256'], 'compile_seal_sha256': seal['seal_sha256'],
                'evidence_basis': 'declared source domain and unmutated sealed compilation; no measured recovery inferred'}
    except (UnsupportedEvidence, ValueError, TypeError, KeyError, AttributeError) as error:
        return {'schema_version': OBS_SCHEMA, 'export_schema': EXPORT_SCHEMA, 'export_state': 'unknown',
                'reason': str(error), 'physical_configuration_sha256': physical_configuration_sha256}
