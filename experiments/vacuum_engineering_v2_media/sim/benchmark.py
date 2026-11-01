"""Isolated ROS/Gazebo placement benchmarks with per-run evidence and video."""
import argparse
import csv
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import socket

ROOT = Path(__file__).resolve().parent


def terminate(process):
    if process is None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seeds', nargs='+', type=int, default=[1446070182, 20261031, 8675309])
    parser.add_argument('--modes', nargs='+', choices=['coarse', 'precise'], default=['coarse'])
    parser.add_argument('--timeout', type=int, default=650)
    parser.add_argument('--no-video', action='store_true')
    args = parser.parse_args()
    if args.timeout < 60:
        parser.error('--timeout must be at least 60 seconds')
    output = ROOT / 'benchmark_results' / time.strftime('%Y%m%d_%H%M%S')
    output.mkdir(parents=True)
    print('RESULT DIRECTORY: ' + str(output), flush=True)
    results = []
    for mode in args.modes:
        for seed in args.seeds:
            label = '{}_{}'.format(mode, seed)
            env = os.environ.copy()
            ros_port, gazebo_port = port(), port()
            telemetry_path = output / (label + '_telemetry.jsonl')
            env.update(SUKETHON_SEED=str(seed), ROS_MASTER_URI='http://127.0.0.1:{}'.format(ros_port),
                       GAZEBO_MASTER_URI='http://127.0.0.1:{}'.format(gazebo_port), ROS_HOSTNAME='localhost',
                       SUKETHON_TELEMETRY=str(telemetry_path))
            processes, logs = [], []
            def launch(command, suffix):
                log = (output / (label + suffix + '.log')).open('w')
                logs.append(log)
                process = subprocess.Popen(command, cwd=str(ROOT), env=env, stdout=log,
                                           stderr=subprocess.STDOUT, start_new_session=True)
                processes.append(process)
                return process
            row = {'mode': mode, 'seed': seed, 'status': 'error'}
            started = time.monotonic()
            try:
                subprocess.run([sys.executable, str(ROOT / 'generate_world.py')], env=env, check=True,
                               stdout=subprocess.DEVNULL)
                source = ROOT / 'last_run.json'
                previous = source.stat().st_mtime_ns if source.exists() else 0
                launch(['roscore', '-p', str(ros_port)], '_roscore')
                deadline = time.monotonic() + 25
                while True:
                    check = subprocess.run(['rosparam', 'list'], env=env, stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL, timeout=4)
                    if check.returncode == 0:
                        break
                    if time.monotonic() > deadline:
                        raise RuntimeError('ROS master startup timeout')
                    time.sleep(.3)
                server = launch([sys.executable, str(ROOT / 'run_sim.py'), 'server'], '_gazebo')
                time.sleep(8)
                if server.poll() is not None:
                    raise RuntimeError('Gazebo exited during startup')
                recorder = None
                if not args.no_video:
                    recorder = launch([sys.executable, str(ROOT / 'record_camera.py'), '--no-preview',
                                       '--seconds', str(args.timeout + 20)], '_video')
                executor = launch([sys.executable, '-u', str(ROOT / 'execute.py'), '--placement-mode', mode], '')
                try:
                    code = executor.wait(timeout=args.timeout)
                except subprocess.TimeoutExpired:
                    row['status'] = 'timeout'
                    raise RuntimeError('Executor timeout')
                row['return_code'] = code
                if not source.exists() or source.stat().st_mtime_ns <= previous:
                    raise RuntimeError('Executor produced no fresh result')
                payload = json.loads(source.read_text())
                if payload.get('scene_seed') != seed or payload.get('placement_mode') != mode:
                    raise RuntimeError('Result belongs to another run')
                (output / (label + '.json')).write_text(json.dumps(payload, indent=2))
                records = payload.get('box_records', [])
                row.update(status=payload['status'], elapsed_seconds=payload['elapsed_seconds'],
                           placed=len(records), passed=sum(bool(r['pass']) for r in records),
                           max_center_mm=max((r['center_mm'] for r in records), default=None),
                           max_yaw_deg=max((r['yaw_deg'] for r in records), default=None),
                           regrasp_count=payload['regrasp_count'], failure=payload.get('reason'),
                           first_pass_failed=sum(c.get('stage') == 'released' and c.get('attempt') == 0
                                                 and (c['error_m'] > .01 or c['yaw_rad'] > .0872664626)
                                                 for c in payload.get('visual_corrections', [])))
                if code != 0 and row['status'] == 'complete':
                    row['status'] = 'error'
                if recorder is not None:
                    recorder.wait(timeout=30)
                    row['video_return_code'] = recorder.returncode
            except Exception as exc:
                row['error'] = str(exc)
            finally:
                for process in reversed(processes):
                    terminate(process)
                for log in logs:
                    log.close()
                row['wall_seconds'] = round(time.monotonic() - started, 2)
                results.append(row)
                (output / 'summary.json').write_text(json.dumps(results, indent=2))
                with (output / 'summary.csv').open('w', newline='') as stream:
                    writer = csv.DictWriter(stream, fieldnames=sorted({k for r in results for k in r}))
                    writer.writeheader()
                    writer.writerows(results)
                print(json.dumps(row), flush=True)
    return 0 if all(r['status'] == 'complete' and r.get('passed') == 8 for r in results) else 1


if __name__ == '__main__':
    raise SystemExit(main())
