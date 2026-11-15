import sys, zlib, struct, collections

NAMES = {0:'End',1:'ShowFrame',2:'DefineShape',6:'DefineBits',8:'JPEGTables',10:'DefineFont',11:'DefineText',12:'DoAction',
13:'DefineFontInfo',14:'DefineSound',15:'StartSound',18:'SoundStreamHead',19:'SoundStreamBlock',20:'DefineBitsLossless',
21:'DefineBitsJPEG2',22:'DefineShape2',26:'PlaceObject2',28:'RemoveObject2',32:'DefineShape3',33:'DefineText2',34:'DefineButton2',
35:'DefineBitsJPEG3',36:'DefineBitsLossless2',37:'DefineEditText',39:'DefineSprite',43:'FrameLabel',45:'SoundStreamHead2',
46:'DefineMorphShape',48:'DefineFont2',56:'ExportAssets',57:'ImportAssets',59:'DoInitAction',60:'DefineVideoStream',
62:'DefineFontInfo2',69:'FileAttributes',70:'PlaceObject3',73:'DefineFontAlignZones',74:'CSMTextSettings',75:'DefineFont3',
76:'SymbolClass',77:'Metadata',78:'DefineScalingGrid',82:'DoABC',83:'DefineShape4',84:'DefineMorphShape2',86:'DefineSceneAndFrameLabelData',
87:'DefineBinaryData',88:'DefineFontName',90:'DefineBitsJPEG4',91:'DefineFont4',9:'SetBackgroundColor',24:'Protect',41:'ProductInfo',65:'ScriptLimits',64:'EnableDebugger2',63:'DebugID'}

def read(path):
    d = open(path,'rb').read()
    sig, ver = d[:3], d[3]
    body = zlib.decompress(d[8:]) if sig == b'CWS' else d[8:]
    nbits = body[0] >> 3
    rect_bytes = (5 + 4*nbits + 7)//8
    pos = rect_bytes + 4
    return ver, body, pos

def walk(body, pos, end, counts, exports):
    while pos < end:
        code_len, = struct.unpack_from('<H', body, pos); pos += 2
        code, ln = code_len >> 6, code_len & 0x3f
        if ln == 0x3f:
            ln, = struct.unpack_from('<I', body, pos); pos += 4
        counts[NAMES.get(code, str(code))] += 1
        if code == 39:
            walk(body, pos+4, pos+ln, counts, exports)
        if code in (56, 76):
            n, = struct.unpack_from('<H', body, pos); p = pos+2
            for _ in range(n):
                cid, = struct.unpack_from('<H', body, p); p += 2
                e = body.index(b'\0', p); exports.append((cid, body[p:e].decode('latin1'))); p = e+1
        pos += ln
        if code == 0: break

for path in sys.argv[1:]:
    ver, body, pos = read(path)
    counts, exports = collections.Counter(), []
    walk(body, pos, len(body), counts, exports)
    keys = [k for k in counts if k.startswith(('Define','Sound','StartSound','Export','Symbol','DoABC','DoAction'))]
    print(f'== {path} v{ver} exports={len(exports)}')
    print('   ' + ', '.join(f'{k}:{counts[k]}' for k in sorted(keys)))
    print('   ' + ' '.join(n for _, n in exports[:40]))
