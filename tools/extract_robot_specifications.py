"""Read SDF and Git evidence without generating worlds or restoring deleted sources.
Run: python tools/extract_robot_specifications.py --self-test
Run: python tools/extract_robot_specifications.py --output docs/robot_sensor_specifications.json
Only --output writes a file. All dimensions are metres; bounds are initial SDF poses.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def pose(element):
    node = element.find('pose')
    if node is not None and node.get('relative_to'):
        raise ValueError('relative_to frames require explicit resolution')
    values = list(map(float, node.text.split())) if node is not None else [0.] * 6
    if len(values) != 6 or not all(math.isfinite(x) for x in values):
        raise ValueError('Expected six finite pose coordinates')
    x, y, z, r, p, a = values
    cr, sr, cp, sp, ca, sa = math.cos(r), math.sin(r), math.cos(p), math.sin(p), math.cos(a), math.sin(a)
    return [[ca*cp, ca*sp*sr-sa*cr, ca*sp*cr+sa*sr, x],
            [sa*cp, sa*sp*sr+ca*cr, sa*sp*cr-ca*sr, y],
            [-sp, cp*sr, cp*cr, z], [0, 0, 0, 1]]


def multiply(a, b):
    return [[sum(a[i][k]*b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def primitive_bounds(geometry, transform):
    if geometry is None or len(geometry) != 1:
        raise ValueError('Expected exactly one supported primitive')
    g = geometry[0]
    if g.tag == 'box':
        dims = list(map(float, g.findtext('size').split()))
        if len(dims) != 3 or min(dims) <= 0:
            raise ValueError('Box dimensions must be positive')
        extent = [sum(abs(transform[i][j])*dims[j]/2 for j in range(3)) for i in range(3)]
    elif g.tag == 'sphere':
        radius = float(g.findtext('radius'))
        if radius <= 0:
            raise ValueError('Sphere radius must be positive')
        extent = [radius]*3
    elif g.tag == 'cylinder':
        radius, length = float(g.findtext('radius')), float(g.findtext('length'))
        if min(radius, length) <= 0:
            raise ValueError('Cylinder dimensions must be positive')
        extent = [radius*math.hypot(transform[i][0], transform[i][1])+length/2*abs(transform[i][2]) for i in range(3)]
    else:
        raise ValueError('Unsupported geometry: '+g.tag)
    if not all(math.isfinite(v) for v in extent):
        raise ValueError('Nonfinite geometry')
    return {'min': [transform[i][3]-extent[i] for i in range(3)],
            'max': [transform[i][3]+extent[i] for i in range(3)]}


def union(items):
    if not items:
        raise ValueError('Cannot bound empty geometry')
    lo = [min(v['min'][i] for v in items) for i in range(3)]
    hi = [max(v['max'][i] for v in items) for i in range(3)]
    return {'min': lo, 'max': hi, 'size': [b-a for a, b in zip(lo, hi)]}


def footprint(width, height, hfov, distance):
    if min(width, height, distance) <= 0 or not 0 < hfov < math.pi:
        raise ValueError('Invalid pinhole parameters')
    fx = width/(2*math.tan(hfov/2))
    vfov = 2*math.atan(height/width*math.tan(hfov/2))
    w, h = 2*distance*math.tan(hfov/2), 2*distance*math.tan(vfov/2)
    return {'distance_m': distance, 'width_m': w, 'height_m': h,
            'area_m2': w*h, 'theoretical_samples_per_m2': width*height/(w*h),
            'center_pitch_mm': 1000*distance/fx}


def git_read(path):
    return subprocess.check_output(['git', 'show', 'HEAD:'+path], cwd=ROOT, text=True, encoding='utf-8')


def extract():
    world = ROOT/'sim/stacking.world'
    sdf = ET.parse(world).getroot()
    model = sdf.find("./world/model[@name='gantry']")
    if model is None:
        raise ValueError('gantry model missing')
    primitives = []
    for link in model.findall('link'):
        for kind in ('visual', 'collision'):
            for item in link.findall(kind):
                matrix = multiply(multiply(pose(model), pose(link)), pose(item))
                primitives.append({'link': link.get('name'), 'name': item.get('name'), 'kind': kind,
                                   'primitive': item.find('geometry')[0].tag,
                                   **primitive_bounds(item.find('geometry'), matrix)})
    bounds = {kind: union([p for p in primitives if p['kind'] == kind]) for kind in ('visual', 'collision')}
    link_bounds = {link.get('name'): union([p for p in primitives if p['kind'] == 'visual' and p['link'] == link.get('name')])
                   for link in model.findall('link') if link.findall('visual')}
    cameras = []
    for camera_model in sdf.findall('./world/model'):
        for link in camera_model.findall('link'):
            for sensor in link.findall('sensor'):
                camera = sensor.find('camera')
                if camera is None:
                    continue
                width, height = int(camera.findtext('image/width')), int(camera.findtext('image/height'))
                hfov = float(camera.findtext('horizontal_fov'))
                cameras.append({'model': camera_model.get('name'), 'sensor': sensor.get('name'), 'type': sensor.get('type'),
                                'model_pose': camera_model.findtext('pose'), 'width': width, 'height': height,
                                'rate_hz': float(sensor.findtext('update_rate')), 'hfov_rad': hfov,
                                'vfov_rad': 2*math.atan(height/width*math.tan(hfov/2)),
                                'focal_length_px_pinhole': width/(2*math.tan(hfov/2)),
                                'principal_point_default_noetic': [(width+1)/2, (height+1)/2],
                                'plugin': dict((n.tag, n.text) for n in sensor.find('plugin')),
                                'footprints': [footprint(width, height, hfov, d) for d in (1, 2, 3, 4.1, 4.08, 3.8, 3.52, 3.85, 3.62)]})
    experiment = 'experiments/vacuum_engineering_v1/'
    return {'classification': 'configured geometry and theoretical calculations, not physical accuracy or measured valid point counts',
            'git_head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
            'world_sha256': hashlib.sha256(world.read_bytes()).hexdigest(),
            'experiment_present_on_disk': (ROOT/experiment).exists(),
            'experiment_generator_matches_baseline_head': git_read(experiment+'sim/generate_world.py') == git_read('sim/generate_world.py'),
            'initial_sdf_bounds_m': bounds, 'initial_visual_link_bounds_m': link_bounds,
            'primitives': primitives, 'cameras': cameras,
            'vacuum_experiment_committed_config': json.loads(git_read(experiment+'sim/vacuum_parameters.json'))}


def self_test():
    identity = pose(ET.fromstring('<link/>'))
    b = primitive_bounds(ET.fromstring('<geometry><box><size>2 4 6</size></box></geometry>'), identity)
    assert b['max'] == [1, 2, 3]
    rotation = pose(ET.fromstring('<link><pose>1 2 3 0 1.5707963267948966 0</pose></link>'))
    c = primitive_bounds(ET.fromstring('<geometry><cylinder><radius>2</radius><length>6</length></cylinder></geometry>'), rotation)
    assert all(abs(a-b)<1e-9 for a,b in zip(c['max'], [4,4,5]))
    s = primitive_bounds(ET.fromstring('<geometry><sphere><radius>2</radius></sphere></geometry>'), rotation)
    assert s['min'] == [-1,0,1]
    local = pose(ET.fromstring('<link><pose>0 0 2 0 0 0</pose></link>'))
    composed = multiply(rotation, local)
    assert all(abs(composed[i][3]-v)<1e-9 for i,v in enumerate([3,2,3]))
    try:
        pose(ET.fromstring('<link><pose relative_to="other">0 0 0 0 0 0</pose></link>'))
    except ValueError:
        pass
    else:
        raise AssertionError('Unresolved frame accepted')
    for bad in ('<geometry><mesh/></geometry>', '<geometry><sphere><radius>-1</radius></sphere></geometry>'):
        try:
            primitive_bounds(ET.fromstring(bad), identity)
        except ValueError:
            pass
        else:
            raise AssertionError('Invalid geometry was accepted')
    try:
        footprint(960,960,1.2,0)
    except ValueError:
        pass
    else:
        raise AssertionError('Invalid distance accepted')
    f1, f2 = footprint(960,960,1.2,1), footprint(960,960,1.2,2)
    assert abs(f1['theoretical_samples_per_m2']/f2['theoretical_samples_per_m2']-4)<1e-9
    result = extract()
    assert len(result['cameras']) == 2
    assert len([p for p in result['primitives'] if p['kind']=='collision']) == 2
    assert result['experiment_generator_matches_baseline_head']
    print('PASS: primitive rotations, pose composition, invalid input, inverse-square density, source parity and collision count')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    try:
        if args.self_test:
            self_test()
        if args.output:
            args.output.write_text(json.dumps(extract(), ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
            print(args.output)
        elif not args.self_test:
            print(json.dumps(extract(), ensure_ascii=False, indent=2))
    except (OSError, ValueError, ET.ParseError, subprocess.CalledProcessError) as exc:
        parser.exit(1, 'Specification extraction failed: '+str(exc)+'\n')
