import sys; from PIL import Image; import numpy as np; from scipy import ndimage
def runs(m):
  r=[];s=None
  for i,v in enumerate(m):
    if v and s is None:s=i
    if not v and s is not None:r.append((s,i));s=None
  if s is not None:r.append((s,len(m)))
  return r
def extract(path):
  im=np.array(Image.open(path).convert('RGBA'))
  im[im[:,:,3]<24]=0
  a=im[:,:,3]>40
  rows=[r for r in runs(a.any(1)) if r[1]-r[0]>100]; cols=[c for c in runs(a.any(0)) if c[1]-c[0]>60]
  assert len(rows)==4 and len(cols)==4,(rows,cols)
  out=[]
  for r,(y0,y1) in enumerate(rows):
    row=[]
    for c,(x0,x1) in enumerate(cols):
      sub=im[max(0,y0-10):y1+10, max(0,x0-10):x1+10].copy()
      lab,n=ndimage.label(sub[:,:,3]>0)
      sizes=ndimage.sum(np.ones_like(lab),lab,range(1,n+1))
      big=int(np.argmax(sizes))+1; bot=np.nonzero(lab==big)[0].max()
      objs=ndimage.find_objects(lab)
      keep=[i+1 for i,s in enumerate(sizes) if s>=0.002*sizes.max() and objs[i][0].start<bot-4]
      sub[~np.isin(lab,keep)]=0
      ys,xs=np.nonzero(sub[:,:,3]); sub=sub[ys.min():ys.max()+1, xs.min():xs.max()+1]
      row.append(sub)
    out.append(row)
  return out
TARGET=268.0; S=0.5
chars={n:extract(p) for n,p in [('arthur','arthur_sheet.png'),('gwen','gwen_sheet.png')]}
prepared={}
for n,rows in chars.items():
  ref=np.median([f.shape[0] for f in rows[2]])
  fr=[]
  for r,row in enumerate(rows):
    rh=np.median([f.shape[0] for f in row])
    k=TARGET/ref*(ref/rh if r==0 else 1.0)   # idle row normalized to walk height
    for c,f in enumerate(row):
      p=Image.fromarray(f); p=p.resize((max(1,round(p.width*k*S)),max(1,round(p.height*k*S))),Image.LANCZOS)
      arr=np.array(p); h=arr.shape[0]
      hx=np.nonzero(arr[:int(h*0.3),:,3]>0)[1].mean()
      fr.append((r,c,p,hx))
  prepared[n]=fr
allf=[f for v in prepared.values() for f in v]
L=max(f[3] for f in allf); R=max(f[2].width-f[3] for f in allf); U=max(f[2].height for f in allf)
W=int(np.ceil(max(L,R)*2))+4; H=int(U)+4; W+=W%2; H+=H%2
print('cell',W,H)
for n,fr in prepared.items():
  sheet=Image.new('RGBA',(W*4,H*4),(0,0,0,0))
  for r,c,p,hx in fr:
    sheet.alpha_composite(p,(c*W+int(round(W/2-hx)), r*H+H-2-p.height))
  sheet.save(f'{n}_frames.png'); print(n, sheet.size)
