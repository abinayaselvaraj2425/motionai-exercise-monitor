"""Read the supplied IntelliRehabDS archive without extracting or altering research labels."""
import zipfile,re,hashlib
from pathlib import Path
from functools import lru_cache
import numpy as np
ARCHIVE=Path(__file__).resolve().parent.parent/'data'/'SkeletonData.zip'
GESTURES=['Left elbow flexion','Right elbow flexion','Left shoulder flexion','Right shoulder flexion','Left shoulder abduction','Right shoulder abduction','Shoulder forward elevation','Left side tap','Right side tap']
LABELS={1:'Correct',2:'Incorrect',3:'Ambiguous / poorly executed'}
BONES=[[0,1],[1,20],[20,2],[2,3],[20,4],[4,5],[5,6],[6,7],[7,21],[6,22],[20,8],[8,9],[9,10],[10,11],[11,23],[10,24],[0,12],[12,13],[13,14],[14,15],[0,16],[16,17],[17,18],[18,19]]
@lru_cache(maxsize=1)
def catalog():
 if not ARCHIVE.is_file():return {'available':False,'records':[],'gestures':GESTURES}
 records=[]
 with zipfile.ZipFile(ARCHIVE) as z:
  for n in sorted(z.namelist()):
   if '/Simplified/' not in n or not n.endswith('.txt'):continue
   name=n.rsplit('/',1)[-1];parts=name[:-4].split('_')
   if len(parts)!=6:continue
   subject,date,gesture,rep,label,position=parts
   records.append({'id':name,'subject':subject,'session':date,'gesture':int(gesture),'movement':GESTURES[int(gesture)],'repetition':int(rep),'label':int(label),'annotation':LABELS.get(int(label),'Unknown'),'position':position})
 return {'available':True,'records':records,'gestures':GESTURES,'count':len(records),'subjects':len({r['subject'] for r in records}),'labels':{LABELS[k]:sum(r['label']==k for r in records) for k in LABELS},'archive_md5':hashlib.md5(ARCHIVE.read_bytes()).hexdigest(),'source':'https://zenodo.org/records/4610859','paper':'https://doi.org/10.3390/data6050046','notes':['The supplied release includes 30 subject IDs, including partial subject 217; the original study describes 29 participants.','Labels are original researcher annotations, not predictions by this application.','These rehabilitation gestures differ from the five live workout exercises. No correctness classifier was trained.']}
@lru_cache(maxsize=8)
def recording(name):
 record=next((r for r in catalog()['records'] if r['id']==name),None)
 if record is None:raise ValueError('Recording not found')
 with zipfile.ZipFile(ARCHIVE) as z:
  simple=next(n for n in z.namelist() if '/Simplified/' in n and n.endswith('/'+name))
  xyz=np.array([[float(v) for v in line.split(',')] for line in z.read(simple).decode().splitlines() if line.strip()],dtype=np.float32).reshape(-1,25,3)
  raw=simple.replace('/Simplified/','/RawData/')
  times=[];xy=[];confidence=[]
  def coordinate(value):return float(value.replace('∞','inf'))
  for line in z.read(raw).decode().splitlines():
   if '(' not in line:continue
   prefix=line.split('(',1)[0].strip(',').split(',')
   joints=re.findall(r'\(([^)]+)\)',line)
   if len(joints)!=25:raise ValueError('Raw joint count differs from Kinect 25 format')
   values=[j.split(',') for j in joints]
   times.append(float(prefix[2]));xy.append([[coordinate(j[-2]),coordinate(j[-1])] for j in values]);confidence.append([1. if j[1]=='Tracked' else .5 if j[1]=='Inferred' else 0. for j in values])
 if len(times)!=len(xyz):raise ValueError('Raw and simplified frame counts differ')
 timestamps=np.array(times);timestamps-=timestamps[0]
 if len(times)<2 or not np.isfinite(xyz).all() or np.any(np.diff(timestamps)<=0):raise ValueError('Recording has insufficient frames or invalid timing')
 viewer=xyz-xyz[:,0:1];viewer[:,:,2]*=-1
 return {'record':record,'frames':viewer.round(6).tolist(),'timestamps':timestamps.tolist(),'bones':BONES,'frame_count':len(times),'duration':float(timestamps[-1]/1000),'projection_available':bool(np.isfinite(xy).all()),'warnings':[] if np.isfinite(xy).all() else ['Raw image projections contain an infinite coordinate. Original 3D replay remains available; MotionBERT is disabled for this recording.'],'tracking_fraction':round(float(np.mean(np.array(confidence)==1)),3)},np.array(xy,dtype=np.float32),np.array(confidence,dtype=np.float32)
def model_input(name):
 data,xy,conf=recording(name)
 if not data['projection_available']:raise ValueError('This recording has an infinite raw image coordinate; use original Kinect replay instead.')
 # Kinect depth projection: normalize body bounding box over entire clip, confidence is the third channel.
 mapping=[0,16,17,18,12,13,14,1,2,3,3,4,5,6,8,9,10]
 pose=np.concatenate([xy[:,mapping],conf[:,mapping,None]],axis=2)
 pose[:,9,:2]=(xy[:,2]+xy[:,3])/2;pose[:,9,2]=np.minimum(conf[:,2],conf[:,3])*.5
 valid=pose[:,:,2]>0
 if not valid.any():raise ValueError('No tracked image joints')
 lo=pose[:,:,:2][valid].min(axis=0);hi=pose[:,:,:2][valid].max(axis=0);scale=float(max(hi-lo))
 if scale<1:raise ValueError('Degenerate image projection')
 pose[:,:,:2]=(pose[:,:,:2]-(lo+hi)/2)/(scale/2)
 if not np.isfinite(pose).all():raise ValueError('Non-finite image projection')
 return data,pose.astype(np.float32)
