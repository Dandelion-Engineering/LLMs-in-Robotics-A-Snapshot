ZONES = {'fixture': (0.57, 0), 'inspection': (0.34, 0.2), 'parking1': (0.34, 0.04), 'parking2': (0.46, 0.12), 'tray1': (0.4, 0.33), 'tray2': (0.61, 0.33), 'tray3': (0.65, -0.29), 'quarantine': (0.2, 0.29), 'insert_home_A': (0.18, -0.25), 'insert_home_B': (0.18, -0.34)}
PART_HALF = np.array([0.021, 0.021, 0.018])
HOME = np.array([0.8, -0.5, 0, -2.2, 0, 1.7, 0.7854])
DT = 0.002
FIXTURE_JAW_SLOT_HALF_M = 0.02
IK_MAX_ITERATIONS = 480

def zone_half(name):
    return np.array([0.092, 0.065]) if name.startswith('tray') else np.array([0.053, 0.053])

def _sub(parent, tag, **attrs):
    return ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})

def build_scene(n=3, seed=0, layout_seed=None):
    """Generated geometry; Menagerie Panda rigid body/actuators preserved."""
    source = HERE / 'vendor' / 'panda' / 'panda.xml'
    root = ET.parse(source).getroot()
    root.find('compiler').set('meshdir', str(source.parent / 'assets'))
    root.find('option').set('timestep', str(DT))
    root.find('option').set('iterations', '80')
    root.find('option').set('cone', 'elliptic')
    for key in root.findall('keyframe'):
        root.remove(key)
    visual = _sub(root, 'visual')
    _sub(visual, 'global', offwidth=640, offheight=480)
    _sub(visual, 'headlight', ambient='.65 .65 .65', diffuse='.45 .45 .45', specular='0 0 0')
    world = root.find('worldbody')
    _sub(world, 'geom', name='table', type='plane', size='1 1 .1', rgba='.24 .27 .30 1', friction='1 .01 .001')
    _sub(world, 'camera', name='overhead', pos='.43 0 1.25', xyaxes='1 0 0 0 1 0', fovy='48')
    _sub(world, 'camera', name='oblique', pos='1.05 -.85 .95', xyaxes='.80 .60 0 -.36 .48 .80', fovy='48')
    hand = root.find(".//body[@name='hand']")
    _sub(hand, 'site', name='tcp', pos='0 0 .1034', size='.004', rgba='1 0 0 1')
    _sub(hand, 'camera', name='wrist', pos='.06 0 .05', xyaxes='1 0 0 0 -1 0', fovy='70')
    for geom in root.findall('.//geom'):
        if geom.get('class', '').startswith('fingertip_pad'):
            geom.set('friction', '1.5 .02 .001')
    for name, (x, y) in ZONES.items():
        half = zone_half(name)
        _sub(world, 'geom', name='zone_' + name, type='box', pos=f'{x} {y} -.001', size=f'{half[0]} {half[1]} .001', rgba='.36 .39 .41 1', contype='0', conaffinity='0')
        if name == 'fixture':
            edge_half = (0.053 - FIXTURE_JAW_SLOT_HALF_M) / 2
            edge_center = (0.053 + FIXTURE_JAW_SLOT_HALF_M) / 2
            walls = [(0.049, 0, 0.004, 0.053), (-0.049, 0, 0.004, 0.053)]
            walls.extend(((dx, dy, edge_half, 0.004) for dx in (-edge_center, edge_center) for dy in (-0.049, 0.049)))
            for dx, dy, sx, sy in walls:
                _sub(world, 'geom', name=f'fixture_wall_{dx}_{dy}', type='box', pos=f'{x + dx} {y + dy} .006', size=f'{sx} {sy} .006', rgba='.5 .5 .5 1')
    asset = root.find('asset')
    rng = np.random.default_rng(seed)
    layout_rng = np.random.default_rng(seed if layout_seed is None else layout_seed)
    registry = {}
    names = [f"{('A' if i % 2 == 0 else 'B')}{i + 1}" for i in range(n)] + ['insert_A', 'insert_B']
    for i, name in enumerate(names):
        hue = ((i + 0.25) / len(names) + rng.uniform(-0.004, 0.004)) % 1
        color = colorsys.hsv_to_rgb(hue, 0.95, 0.35)
        rgb = ' '.join((str(v) for v in color))
        _sub(asset, 'material', name='tagmat_' + name, rgba=rgb + ' 1', emission='.7', specular='0', shininess='0')
        if name.startswith('insert'):
            x, y = ZONES['fixture'] if name == 'insert_A' else ZONES['insert_home_B']
            half = [0.025, 0.025, 0.008]
            z = 0.009
        else:
            row, col = divmod(i, 3)
            x, y = (0.32 + 0.085 * col, -0.31 + 0.074 * row)
            x, y = (x + layout_rng.uniform(-0.003, 0.003), y + layout_rng.uniform(-0.003, 0.003))
            half = PART_HALF
            z = 0.021
        body = _sub(world, 'body', name=name, pos=f'{x} {y} {z}')
        _sub(body, 'freejoint', name='free_' + name)
        size = ' '.join(map(str, half))
        mass = float(rng.uniform(0.09, 0.11))
        friction = float(rng.uniform(1.1, 1.3))
        _sub(body, 'geom', name='part_' + name, type='box', size=size, mass=mass, rgba='.60 .61 .62 1', friction=f'{friction} .015 .001', condim='4')
        _sub(body, 'geom', name='tag_' + name, type='box', size='.014 .014 .0003', pos=f'0 0 {half[2] + 0.0004}', material='tagmat_' + name, contype='0', conaffinity='0', mass='.0001')
        _sub(body, 'geom', name='mark_' + name, type='box', size='.004 .014 .0003', pos=f'.018 0 {half[2] + 0.0004}', rgba='.03 .03 .03 1', contype='0', conaffinity='0', mass='.0001')
        registry[name] = {'family': name[-1] if name.startswith('insert') else name[0], 'hue': hue, 'half': list(map(float, half)), 'kind': 'insert' if name.startswith('insert') else 'part'}
    return (ET.tostring(root, encoding='unicode'), registry)

def ik(self, xyz, initial=None, configuration=None):
    d = self.ikdata
    d.qpos[:] = self.data.qpos if configuration is None else configuration
    d.qpos[:7] = d.qpos[:7] if initial is None else initial
    target_rotation = self.diagnostic_target_rotation
    for _ in range(IK_MAX_ITERATIONS):
        mujoco.mj_forward(self.model, d)
        current = d.site_xmat[self.tcp].reshape(3, 3)
        rot_error = 0.5 * sum((np.cross(current[:, i], target_rotation[:, i]) for i in range(3)), start=np.zeros(3))
        pos_error = np.array(xyz) - d.site_xpos[self.tcp]
        if np.linalg.norm(pos_error) < 0.001 and np.linalg.norm(rot_error) < 0.01:
            return d.qpos[:7].copy()
        mujoco.mj_jacSite(self.model, d, self.jacp, self.jacr, self.tcp)
        jac = np.vstack((self.jacp[:, :7], self.jacr[:, :7] * 0.4))
        error = np.r_[pos_error, rot_error * 0.4]
        dq = jac.T @ np.linalg.solve(jac @ jac.T + np.eye(6) * 0.002, error)
        d.qpos[:7] += np.clip(dq, -0.15, 0.15)
        ranges = self.model.jnt_range[:7]
        d.qpos[:7] = np.clip(d.qpos[:7], ranges[:, 0] + 0.015, ranges[:, 1] - 0.015)
    raise ValueError(f'IK did not converge at {xyz}, error={pos_error}')