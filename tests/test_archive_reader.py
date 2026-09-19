"""Basic offline tests, using only synthetic mission records."""
import json
import os
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEMO = ROOT / 'examples' / 'tricorder_uploads.example.jsonl'
READER = ROOT / 'tricorder' / 'tricorder_archive_reader.py'
MID = 'mission_20000101_120000_DEMO-001.jsonl'

def run_reader(mode, mission_id=None):
    env = dict(os.environ, TRICORDER_ARCHIVE_PATH=str(DEMO))
    args = [sys.executable, str(READER), mode]
    if mission_id is not None:
        args.append(mission_id)
    return json.loads(subprocess.check_output(args, env=env, text=True))

def test_demo_catalog():
    result = run_reader('catalog')
    assert result['count'] == 1

def test_demo_scans_have_all_four_sampled_sensors():
    result = run_reader('scans', MID)
    series = {s['name'] for s in result['results'][0]['series']}
    assert {'tricorder_color','tricorder_magnetic','tricorder_orientation'} <= series

def test_unknown_mission_is_empty():
    assert run_reader('scans','not_a_real_mission')['count']==0
