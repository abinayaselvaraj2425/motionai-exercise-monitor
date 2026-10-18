"""Verify actual supplied research data and real cross-sensor model inference."""
import unittest
import numpy as np
from backend.dataset import catalog,recording,model_input
from backend import submission_api as api
class DatasetTests(unittest.TestCase):
 def test_archive_labels_and_input(self):
  c=catalog();self.assertEqual(c['count'],2589);self.assertEqual(c['archive_md5'],'c243bcdbd1492e4928032e158accdd29');self.assertEqual(c['labels']['Correct'],2047)
  data,t=model_input(c['records'][0]['id']);self.assertEqual(t.shape,(data['frame_count'],17,3));self.assertTrue(np.isfinite(t).all());self.assertEqual(len(data['frames'][0]),25);self.assertTrue(np.all(np.diff(data['timestamps'])>0));self.assertTrue(np.all((t[:,:,2]>=0)&(t[:,:,2]<=1)))
  self.assertFalse(recording('101_18_0_6_1_chair.txt')[0]['projection_available'])
  with self.assertRaises(ValueError):model_input('101_18_0_6_1_chair.txt')
  with self.assertRaises(ValueError):recording('../submission_api.py')
 def test_actual_research_model(self):
  if api.model is None:api.load_model()
  c=catalog();name=c['records'][0]['id'];data=recording(name)[0];result=api.research_analysis(name)
  self.assertEqual(len(result['frames']),data['frame_count']);self.assertEqual(len(result['frames'][0]),17);self.assertGreaterEqual(result['windows'],1);self.assertTrue(np.isfinite(result['frames']).all())
