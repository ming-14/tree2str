#!/usr/bin/env python3
import os,sys,glob,pickle
from struct import unpack_from,unpack
from pathlib import Path
try:
    import stringzilla
    STRINGZILLA_AVAILABLE=True
except ImportError:
    STRINGZILLA_AVAILABLE=False
PROGRAM_VER="2.48"
HEADER_FRONT_SIZE=2048
MAX_FILE_SIZE=1024*1024*10
class TrIDError(Exception): pass


class TrIDDef(object):
    __slots__=('filetype','ext','mime','filename','tag','rem','refurl','user','email','home','filenum','checkstrings','refine','patterns','strings')
    def __init__(self):
        self.filetype="";self.ext=[];self.mime="";self.filename="";self.tag=0;self.rem="";self.refurl="";self.user="";self.email="";self.home="";self.filenum=0;self.checkstrings=True;self.refine="";self.patterns=[];self.strings=[]
    def __str__(self):
        return f"FileType: '{self.filetype}', Ext: '{self.ext}', Patterns: {len(self.patterns)}, Strings: {len(self.strings)}"


class TrIDResult(object):
    __slots__=('perc','pts','patt','str','triddef')
    def __init__(self): self.perc=0;self.pts=0;self.patt=0;self.str=0;self.triddef=""
    def __str__(self):         return f"Result: FileType='{self.triddef.filetype}')"


class TrIDDefsBlock:
    __slots__=('version','defs_num','defs_group')
    def __init__(self,version=1,defs_num=0,defs_group=None): self.version=version;self.defs_num=defs_num;self.defs_group=defs_group if defs_group is not None else {}


def errprint(msg): print(f"trid: {msg}",file=sys.stderr)


def get_files(filenames,recursive=False):
    result=[]
    for arg in filenames:
        if os.path.isfile(arg): result.append(arg); continue
        if os.path.isdir(arg):
            if recursive:
                for root,_,files_ in os.walk(arg):
                    for f in files_: result.append(os.path.join(root,f))
            else:
                try:
                    for item in os.listdir(arg):
                        full_path=os.path.join(arg,item)
                        if os.path.isfile(full_path): result.append(full_path)
                except (OSError,PermissionError): pass
            continue
        has_wildcard='*' in arg or '?' in arg or '[' in arg
        if not has_wildcard:
            result.extend(m for m in glob.glob(arg,recursive=False) if os.path.isfile(m))
            continue
        if recursive and '**' not in arg:
            dir_part=os.path.dirname(arg) or '.'
            base_part=os.path.basename(arg)
            pattern=os.path.join(dir_part,'**',base_part) if base_part else arg+'**/*'
        else: pattern=arg
        result.extend(m for m in glob.glob(pattern,recursive=recursive) if os.path.isfile(m))
    return result


def LoadDataFromFile(filename):
    filesize=os.path.getsize(filename)
    with open(filename,"rb") as f:
        if filesize<=MAX_FILE_SIZE: data=f.read()
        else:
            part_size=MAX_FILE_SIZE//2
            data=f.read(part_size)
            f.seek(filesize-part_size)
            data+=b"|"+f.read()
    return data.upper()


def trdblock2patts(chunk):
    patts=[]; pattn=unpack_from("<h",chunk)[0]; cpos=2
    for _ in range(pattn):
        patpos=unpack_from("<h",chunk,offset=cpos)[0]
        patlen=unpack_from("<h",chunk,offset=cpos+2)[0]
        patt=chunk[cpos+4:cpos+4+patlen]
        patts.append((patpos,patt))
        cpos+=4+patlen
    return patts


def trdblock2strs(chunk):
    strings=[]; strn=unpack_from("<h",chunk)[0]; cpos=2
    for _ in range(strn):
        slen=unpack_from("<i",chunk,offset=cpos)[0]
        strings.append(chunk[cpos+4:cpos+4+slen])
        cpos+=4+slen
    return strings


def trdblock2def(block):
    triddef=TrIDDef(); defpos=0
    while defpos<len(block)-8:
        chunkid=block[defpos:defpos+4]
        chunklen=unpack_from("<i",block,offset=defpos+4)[0]
        chunk=block[defpos+8:defpos+8+chunklen]
        if chunkid==b"DATA":
            subpos=0
            while subpos<len(chunk)-8:
                subchunkid=chunk[subpos:subpos+4]
                subchunklen=unpack_from("<i",chunk,offset=subpos+4)[0]
                subchunk=chunk[subpos+8:subpos+8+subchunklen]
                subpos+=8+subchunklen
                if subchunkid==b"PATT": triddef.patterns=trdblock2patts(subchunk)
                elif subchunkid==b"STRN": triddef.strings=trdblock2strs(subchunk)
        elif chunkid==b"INFO":
            infopos=0
            while infopos<len(chunk)-6:
                infotype=chunk[infopos:infopos+4]
                infolen=unpack_from("<h",chunk,offset=infopos+4)[0]
                infotext=chunk[infopos+6:infopos+6+infolen]
                infopos+=6+infolen
                if infotype==b"TYPE": triddef.filetype=infotext.decode()
                elif infotype==b"EXT ": triddef.ext=infotext.decode()
                elif infotype==b"TAG ": triddef.tag=unpack("<i",infotext)[0]
                elif infotype==b"MIME": triddef.mime=infotext.decode()
                elif infotype==b"NAME": triddef.filename=infotext.decode()
                elif infotype==b"FNUM": triddef.filenum=unpack("<i",infotext)[0]
                elif infotype==b"RURL": triddef.refurl=infotext.decode()
                elif infotype==b"USER": triddef.user=infotext.decode()
                elif infotype==b"MAIL": triddef.email=infotext.decode()
                elif infotype==b"HOME": triddef.home=infotext.decode()
                elif infotype==b"REM ": triddef.rem=infotext.decode()
        defpos+=8+chunklen
    return triddef


def trdpkg2defs(filename,usecache=False):
    path=Path(filename); cachefilename=path.parent/('.'+path.name+".cache"); cached=False
    if usecache and os.path.exists(cachefilename):
        if os.path.getmtime(cachefilename)>os.path.getmtime(filename):
            with open(cachefilename,"rb") as f: TDB=pickle.load(f)
            if isinstance(TDB,TrIDDefsBlock) and TDB.version==1: cached=True
    if not cached:
        triddefs=[]
        try: package=open(filename,"rb").read()
        except IOError as e: raise TrIDError(f"I/O Error: unable to read TrID definitions from {filename}: {e}")
        if package[:4]+package[8:12]!=b"RIFFTRID": raise TrIDError(f"File {filename} is not a TrID definitions package!")
        pkglen=unpack_from("<i",package,offset=4)[0]
        if (pkglen+8)!=len(package): raise TrIDError(f"TrID definitions package {filename} length mismatch!")
        infoBlock=package[12:24]; defsnum=unpack_from("<i",infoBlock,offset=8)[0]
        blen=unpack_from("<i",package,offset=28)[0]; package=package[32:32+blen]
        loopdefpos=0
        for _ in range(defsnum):
            if loopdefpos<len(package)-8:
                chunkid=package[loopdefpos:loopdefpos+4]
                if chunkid==b"DEF ":
                    blen=unpack_from("<i",package,offset=loopdefpos+4)[0]
                    defblock=package[loopdefpos+8:loopdefpos+8+blen]
                    loopdefpos+=8+blen
                    triddefs.append(trdblock2def(defblock))
        TDB=TrIDDefsBlock(version=1,defs_num=len(triddefs),defs_group={})
        for b in range(-1,256): TDB.defs_group[b]=[]
        for triddef in triddefs:
            ppos=triddef.patterns[0][0]; pbyte=triddef.patterns[0][1][0]
            if ppos==0: TDB.defs_group[pbyte].append(triddef)
            else: TDB.defs_group[-1].append(triddef)
    if usecache and not cached: open(cachefilename,"wb").write(pickle.dumps(TDB,-1))
    return TDB


def tridAnalyze(filename,TDB):
    results=[]; totalpts=0; foundcache={}; stopcache={}
    try: filesize=os.path.getsize(filename)
    except OSError as e: errprint(f"I/O Error: unable to access file {filename}: {e}"); return results
    if filesize==0: return results
    try:
        with open(filename,"rb") as f:
            if filesize<=MAX_FILE_SIZE:
                data=f.read()
            else:
                part_size=MAX_FILE_SIZE//2
                data=f.read(part_size)
                f.seek(filesize-part_size)
                data+=b"|"+f.read()
    except OSError as e: errprint(f"I/O Error: unable to read file {filename}: {e}"); return results
    frontsize=min(filesize,HEADER_FRONT_SIZE)
    frontblock=data[:frontsize]
    filebuffer=data.upper()
    if STRINGZILLA_AVAILABLE: filebufferZ=stringzilla.Str(filebuffer)
    for lst in TDB.defs_group.values():
        for triddef in lst:
            pts=0
            patt_ok=True
            for pattern in triddef.patterns:
                ppos,pbytes=pattern[0],pattern[1]; plen=len(pbytes)
                if frontsize>=ppos+plen:
                    if pbytes==frontblock[ppos:ppos+plen]: pts+=plen*1000 if ppos==0 else plen
                    else: patt_ok=False; pts=0; break
                else: patt_ok=False; pts=0; break
            if not patt_ok: continue
            if triddef.strings:
                if any(s in stopcache for s in triddef.strings): continue
                for string in triddef.strings:
                    if string in foundcache: pts+=len(string)*500
                    else:
                        if STRINGZILLA_AVAILABLE: found=filebufferZ.find(string)!=-1
                        else: found=string in filebuffer
                        if found: pts+=len(string)*500; foundcache[string]=True
                        else: stopcache[string]=True; pts=0; break
            if pts>0:
                totalpts+=pts
                tr=TrIDResult(); tr.pts=pts; tr.patt=len(triddef.patterns); tr.str=len(triddef.strings); tr.triddef=triddef
                results.append(tr)
    for res in results: res.perc=res.pts*100/totalpts if totalpts else 0
    return sorted(results,key=lambda r: r.pts,reverse=True)
