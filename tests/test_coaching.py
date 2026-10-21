"""Known-coordinate regression checks; not validation on people or camera video.

Run node tests/pose.test.mjs first to generate the shared landmark fixtures.
"""
import copy
import json
import unittest
from pathlib import Path
from backend.reports import report

class CoachingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples=json.loads((Path(__file__).parent/'.test-data/known-movements.json').read_text())

    def test_personal_ranges_all_exercises_have_individual_coaching(self):
        for exercise,s in self.samples.items():
            with self.subTest(exercise=exercise):
                r=report(s)
                self.assertGreaterEqual(r['measured_cycles'],5)
                self.assertGreater(r['coverage'],90)
                self.assertEqual(r['coaching']['cards'][-1]['kind'],'practice')
                self.assertTrue(r['coaching']['next_session'])
                self.assertNotIn('Fake imported advice',str(r))

    def test_missing_tracking_does_not_produce_technique_claims(self):
        s=copy.deepcopy(self.samples['squat'])
        for f in s['frames']:
            for p in f['image']:p['visibility']=0
        r=report(s)
        self.assertEqual(r['coverage'],0)
        self.assertTrue(all(m['value'] is None for m in r['metrics']))
        self.assertFalse(any(c['kind']=='observed' for c in r['coaching']['cards']))
        self.assertEqual(r['coaching']['cards'][0]['kind'],'tracking')

    def test_single_frame_lean_does_not_become_a_technique_finding(self):
        s=copy.deepcopy(self.samples['squat'])
        for o in (0,1):s['frames'][40]['image'][11+o]['x']+=.4
        self.assertNotIn('lean',[c['key'] for c in report(s)['coaching']['cards']])

    def test_sustained_lean_has_evidence_and_an_action(self):
        s=copy.deepcopy(self.samples['squat'])
        for f in s['frames']:
            for o in (0,1):f['image'][11+o]['x']+=.3
        c=next(c for c in report(s)['coaching']['cards'] if c['key']=='lean')
        self.assertIn('%',c['evidence'])
        self.assertIn('comfortable',c['action'])

    def test_wrong_exercise_and_large_tracking_gaps_do_not_make_cycles(self):
        s=copy.deepcopy(self.samples['shoulder_press'])
        for f in s['frames']:
            for o in (0,1):f['image'][15+o]['y']=.9
        self.assertEqual(report(s)['measured_cycles'],0)
        s=copy.deepcopy(self.samples['squat'])
        for i,f in enumerate(s['frames']):f['timestamp']=i*1000
        self.assertEqual(report(s)['measured_cycles'],0)

    def test_short_set_explains_missing_metrics_without_fabricating_more(self):
        s=copy.deepcopy(self.samples['squat']);s['frames']=s['frames'][:8];s['duration']=.8
        r=report(s)
        self.assertTrue(any(c['key']=='short_set' for c in r['coaching']['cards']))
        self.assertTrue(all(m['value'] is None for m in r['metrics']))

if __name__=='__main__':unittest.main()
