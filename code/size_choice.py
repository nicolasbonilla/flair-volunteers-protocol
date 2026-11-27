"""Why half a voxel: size options on artificial ellipsoids of known size. No person is involved."""
import numpy as np, sys
from scipy.spatial.distance import pdist
rng=np.random.default_rng(1)
def rot():
    q=rng.normal(size=4); q/=np.linalg.norm(q); w,x,y,z=q
    return np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],[2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],[2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]])
def vox(axes,side):
    n=int(np.ceil(max(axes)/side))+4; g=np.stack(np.meshgrid(*[np.arange(n)]*3,indexing='ij'),-1).reshape(-1,3)*side
    c=n*side/2+rng.random(3)*side; R=rot()
    return g[(((g-c)@R/(np.array(axes)/2))**2).sum(1)<=1]
def ext(p): return float(pdist(p).max()) if len(p)>1 else 0.
for name,ratio in (("bola",(1,1,1)),("ovalada 2:1:1",(1,.5,.5)),("alargada 3:1:1",(1,1/3,1/3))):
  for side in (1.0,1.2):
    for d in (3,4,5,8):
        e=[];v=[]
        for _ in range(300):
            p=vox([d*r for r in ratio],side); e.append(ext(p)); v.append(len(p)*side**3)
        e=np.array(e); print(f"{name:15s} vox {side} largo {d}: centros {e.mean():.2f}  +medio {e.mean()+side/2:.2f}  +1 {e.mean()+side:.2f} | %>=3: centros {100*(e>=3-1e-6).mean():.0f} medio {100*(e+side/2>=3-1e-6).mean():.0f} uno {100*(e+side>=3-1e-6).mean():.0f} vol14 {100*(np.array(v)>=14.1).mean():.0f}")
  for side in (1.0,1.2):
    for d in (1.5,2,2.5):
        e=np.array([ext(vox([d*r for r in ratio],side)) for _ in range(300)])
        print(f"   NO debe contar {name} vox {side} largo {d}: centros {100*(e>=3-1e-6).mean():.0f} medio {100*(e+side/2>=3-1e-6).mean():.0f} uno {100*(e+side>=3-1e-6).mean():.0f}")
